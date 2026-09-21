"""Test the stock llama-server PrefixLM path against pinned HF references."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import threading
import urllib.error
import urllib.request

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-only', action='store_true', help='Test exact-prefix caching without persistence')
    parser.add_argument('--decoder', action='store_true', help='Run resumption checks against ordinary causal decoder mode')
    parser.add_argument('--resumption', action='store_true', help='Test retained and file-backed stochastic continuation')
    parser.add_argument('--resume-only', action='store_true', help='Test restoring the existing checkpoint after server restart')
    parser.add_argument('--fixed-lora', action='store_true', help='Verify a fixed startup LoRA is present')
    parser.add_argument('--parallel', action='store_true', help='Exercise two live server slots')
    parser.add_argument('--url', default='http://127.0.0.1:18181')
    parser.add_argument('--reference', type=Path, default=Path('logs/mimir-chat/chat-reference.json'))
    parser.add_argument('--short-reference', type=Path, default=Path('logs/prefixlm-comparison/real/prompts.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checks = []
    passed = False

    def request(path, body=None):
        req = urllib.request.Request(args.url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=90) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def require(ok, name, result=None):
        checks.append({'name': name, 'pass': ok, **({'result': result} if result is not None else {})})
        if not ok:
            raise AssertionError((name, result))

    def response_text(result):
        return ''.join(part.get('text', '') for item in result.get('output', [])
                       if item.get('type') == 'message' for part in item.get('content', []))

    try:
        deadline = time.monotonic() + 120
        while True:
            try:
                if request('/health')[0] == 200:
                    break
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('server did not become ready')
            time.sleep(0.5)
        if args.fixed_lora:
            code, adapters = request('/lora-adapters')
            require(code == 200 and len(adapters) == 1 and adapters[0]['scale'] == 1, 'fixed startup LoRA present', adapters)
            code, got = request('/lora-adapters', [{'id': 0, 'scale': 0.5}])
            require(400 <= code < 500, 'server dynamic adapter changes rejected', got)
        references = json.loads(args.reference.read_text())
        def check_resumption(save):
            body = {'prompt': references[0]['prompt_tokens'], 'temperature': 0.7, 'seed': 123,
                    'n_predict': 24, 'ignore_eos': True, 'return_tokens': True, 'id_slot': 0, 'cache_prompt': False}
            code, baseline = request('/completion', body)
            require(code == 200 and len(baseline.get('tokens', [])) == 24, 'stochastic resumption reference', baseline)
            destination = 1 if args.parallel and not save else 0
            if save:
                code, first = request('/completion', body | {'n_predict': 8, 'retain_state': True})
                require(code == 200 and first.get('tokens') == baseline['tokens'][:8], 'retained generation matches stochastic prefix', first)
                code, slots = request('/slots')
                require(code == 200 and slots[0].get('resume_ready'), 'idle retained generation is resumable', slots)
                if args.parallel:
                    automatic = dict(body, n_predict=2)
                    del automatic['id_slot']
                    code, got = request('/completion', automatic)
                    require(code == 200 and got.get('id_slot') == 1, 'automatic requests preserve retained slots', got)
                code, got = request('/completion', body | {'n_predict': 16, 'resume': True, 'seed': 124})
                require(code == 400, 'resume rejects changed sampling settings', got)
                for changed in [{'backend_sampling': True}, {'cache_prompt': True}]:
                    code, got = request('/completion', body | {'n_predict': 16, 'resume': True} | changed)
                    require(code == 400, 'resume rejects changed sampling execution path', got)
                code, got = request('/completion', body | {'n_predict': 16, 'resume': True, 'prompt': references[1]['prompt_tokens']})
                require(code == 400, 'resume rejects a new chat turn', got)
                code, got = request('/slots/0?action=save', {'filename': 'prefix-resume.bin'})
                require(code == 200 and got.get('n_saved', got.get('n_tokens', 1)) > 0, 'save complete generation snapshot', got)
                code, continuation = request('/completion', body | {'n_predict': 16, 'resume': True})
                require(code == 200 and continuation.get('tokens') == baseline['tokens'][8:], 'in-memory stochastic continuation', continuation)
                require(first['content'] + continuation['content'] == baseline['content'], 'resumed text has no repeated or missing bytes')
            code, got = request(f'/slots/{destination}?action=restore', {'filename': 'prefix-resume.bin'})
            require(code == 200, 'restore persisted generation' + (' after restart with ID remap' if not save else ''), got)
            code, continuation = request('/completion', body | {'id_slot': destination, 'n_predict': 16, 'resume': True})
            require(code == 200 and continuation.get('tokens') == baseline['tokens'][8:], 'persisted stochastic continuation', continuation)
            if save and first['content'] and len(baseline['content']) > len(first['content']):
                boundary = len(first['content'])
                stop = baseline['content'][:boundary + 3]
                stopped = body | {'stop': [stop]}
                code, expected = request('/completion', stopped)
                require(code == 200, 'cross-boundary stop reference', expected)
                code, head = request('/completion', stopped | {'n_predict': 8, 'retain_state': True})
                require(code == 200 and head.get('stop_type') == 'limit', 'retain partial stop string', head)
                code, tail = request('/completion', stopped | {'n_predict': 16, 'resume': True})
                require(code == 200 and head['content'] + tail['content'] == expected['content'],
                        'cross-boundary stop text is neither repeated nor emitted early', tail)
            code, slots = request('/slots')
            require(code == 200 and all(not slot.get('resume_ready') and (args.decoder or slot.get('n_prompt_tokens', 0) == 0) for slot in slots),
                    'consumed snapshots release capacity', slots)
        def check_exact_cache():
            body = {'prompt': references[0]['prompt_tokens'], 'temperature': 0.7, 'seed': 123,
                    'n_predict': 16, 'ignore_eos': True, 'return_tokens': True, 'id_slot': 0, 'cache_prompt': True, 'n_probs': 3, 'post_sampling_probs': False}
            request('/slots/0?action=erase', {})
            code, cold = request('/completion', body)
            require(code == 200, 'exact cache cold', cold)
            code, warm = request('/completion', body)
            require(code == 200 and warm.get('tokens') == cold['tokens'] and warm['timings']['prompt_n'] == 0,
                    'exact cache hit skips prefill with fresh random stream', warm)
            require(warm.get('completion_probabilities') == cold.get('completion_probabilities'),
                    'cached boundary probabilities match cold prefill')
            code, changed = request('/completion', body | {'prompt': references[1]['prompt_tokens']})
            require(code == 200 and changed['timings']['prompt_n'] == len(references[1]['prompt_tokens']),
                    'extended chat prefix misses exact cache', changed)
        if args.cache_only:
            check_exact_cache()
            passed = True
            return
        if args.resume_only:
            check_resumption(False)
            for case in json.loads((args.output.parent / 'extended-reference.json').read_text()):
                destination = 1 if args.parallel else 0
                code, got = request(f'/slots/{destination}?action=restore', {'filename': case['filename']})
                require(code == 200, case['label'] + ' fresh-process restore', got)
                body = case['body'] | {'id_slot': destination, 'resume': True}
                code, got = request(case['endpoint'], body)
                actual = (got.get('tokens') if case['endpoint'] == '/completion' else response_text(got)
                          if case['endpoint'] == '/v1/responses' else got.get('choices', [{}])[0].get('message'))
                require(code == 200 and actual == case['expected'], case['label'] + ' fresh-process continuation', got)
            passed = True
            return
        if not args.decoder:
            for i, case in enumerate(references):
                code, got = request('/completion', {'prompt': case['prompt_tokens'], 'temperature': 0,
                                                    'n_predict': 32, 'return_tokens': True})
                require(code == 200 and got.get('content') == case['answer'], f'HF token prompt turn {i}', got)
                require(got.get('timings', {}).get('prompt_n') == len(case['prompt_tokens']),
                        f'complete prefix evaluated turn {i}')
            for case in json.loads(args.short_reference.read_text())[:2]:
                code, got = request('/completion', {'prompt': case['token_ids'], 'temperature': 0,
                                                    'n_predict': 4, 'return_tokens': True})
                require(code == 200 and got.get('tokens') == case['reference_answer_ids'], f"HF greedy {case['id']}", got)
            messages = []
            for i, case in enumerate(references):
                messages.append({'role': 'user', 'content': case['text']})
                code, rendered = request('/apply-template', {'messages': messages, 'add_generation_prompt': True,
                                                            'chat_template_kwargs': {'enable_thinking': False}})
                require(code == 200, f'chat template render {i}', rendered)
                code, tokenized = request('/tokenize', {'content': rendered['prompt'], 'add_special': True, 'parse_special': True})
                require(code == 200 and tokenized.get('tokens') == case['prompt_tokens'], f'chat template token parity {i}', tokenized)
                code, got = request('/v1/chat/completions', {'messages': messages, 'temperature': 0, 'max_tokens': 32,
                                                             'chat_template_kwargs': {'enable_thinking': False}})
                require(code == 200 and got['choices'][0]['message']['content'] == case['answer'], f'HF chat conversation turn {i}', got)
                messages.append({'role': 'assistant', 'content': case['answer']})
            base = {'prompt': references[0]['prompt_tokens'], 'temperature': 0, 'n_predict': 1}
            for name, extra in [('cache shifting', {'n_cache_reuse': 4}),
                                ('speculation', {'speculative.type': 'ngram-simple'}), ('oversized prefix', {'prompt': [2] * 225})]:
                code, got = request('/completion', base | extra)
                require(400 <= code < 500, f'reject {name}', got)
            code, got = request('/v1/chat/completions', {'messages': [{'role': 'user', 'content': references[0]['text']}],
                               'n': 2, 'temperature': 0, 'max_tokens': 32,
                               'chat_template_kwargs': {'enable_thinking': False}})
            if args.parallel:
                require(code == 200 and len(got.get('choices', [])) == 2 and
                        all(c['message']['content'] == references[0]['answer'] for c in got['choices']),
                        'shared-prefix children match independent answer', got)
            else:
                require(400 <= code < 500, 'children require enough slots', got)
            with ThreadPoolExecutor(max_workers=2) as pool:
                pending = [pool.submit(request, '/completion', {'prompt': case['prompt_tokens'], 'temperature': 0, 'n_predict': 32})
                           for case in references]
                for case, future in zip(references, pending, strict=True):
                    code, got = future.result()
                    require(code == 200 and got.get('content') == case['answer'] and got['timings']['cache_n'] == 0,
                            'queued requests stay isolated', got)
            if args.parallel:
                long_request = {'prompt': references[0]['prompt_tokens'], 'temperature': 0,
                                'n_predict': 32, 'ignore_eos': True, 'return_tokens': True}
                code, serial = request('/completion', long_request)
                require(code == 200 and len(serial['tokens']) == 32, 'serial concurrency reference', serial)

                def open_stream(body):
                    req = urllib.request.Request(args.url + '/completion',
                        data=json.dumps(body | {'stream': True}).encode(), headers={'Content-Type': 'application/json'})
                    return urllib.request.urlopen(req, timeout=90)

                def read_stream(body, started):
                    chunks, final = [], None
                    with open_stream(body) as reply:
                        for raw in reply:
                            if not raw.startswith(b'data: '):
                                continue
                            value = raw[6:].strip()
                            if value == b'[DONE]':
                                break
                            event = json.loads(value)
                            if event.get('stop'):
                                final = event
                            else:
                                chunks.extend(event.get('tokens', []))
                                if event.get('tokens'):
                                    started.set()
                    return chunks, final

                for cancel_other in [False, True]:
                    started = threading.Event()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(read_stream, long_request, started)
                        require(started.wait(30), 'first sequence starts')
                        other = {'prompt': references[1]['prompt_tokens'], 'temperature': 0,
                                 'n_predict': 32, 'return_tokens': True}
                        if cancel_other:
                            with open_stream(other | {'ignore_eos': True}) as reply:
                                require(bool(reply.readline()), 'second sequence starts before cancellation')
                        else:
                            code, got = request('/completion', other)
                            require(code == 200 and got.get('content') == references[1]['answer'],
                                    'new prefix during active answer', got)
                        require(not pending.done(), 'two sequences actually overlap')
                        tokens, final = pending.result(timeout=90)
                        require(tokens == serial['tokens'] and final is not None and final['timings']['cache_n'] == 0,
                                'unrelated answer survives ' + ('cancellation' if cancel_other else 'prefill'),
                                {'tokens': tokens, 'final': final})
            streaming = urllib.request.Request(args.url + '/completion',
                data=json.dumps(base | {'n_predict': 64, 'stream': True, 'ignore_eos': True}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(streaming, timeout=90) as reply:
                require(bool(reply.readline()), 'stream starts before disconnect')
            for operation in ['save', 'restore']:
                code, got = request('/slots/0?action=' + operation, {'filename': 'prefix-test.bin'})
                require(400 <= code < 500, f'reject slot {operation}', got)
            code, got = request('/completion', base | {'n_predict': 32})
            require(code == 200 and got.get('content') == references[0]['answer'], 'recovery after rejected requests', got)
            code, slots = request('/slots')
            require(code == 200 and all(not slot['is_processing'] and slot.get('n_prompt_tokens', 0) == 0 for slot in slots),
                    'idle slots release prefix capacity', slots)
        if args.resumption:
            check_resumption(True)
            extended = []
            for label, extra in [
                ('grammar', {'grammar': 'root ::= [0-9]+'}),
                ('reasoning', {'reasoning_budget_tokens': 3, 'reasoning_budget_start_tag': '<think>',
                               'reasoning_budget_end_tags': ['</think>'], 'reasoning_budget_message': 'Done.', 'generation_prompt': '<think>'}),
                ('backend', {'backend_sampling': True}),
            ]:
                body = {'prompt': references[0]['prompt_tokens'], 'temperature': 0.7, 'seed': 123,
                        'n_predict': 16, 'ignore_eos': True, 'return_tokens': True, 'id_slot': 0, 'cache_prompt': False} | extra
                code, full = request('/completion', body)
                require(code == 200, f'{label} baseline', full)
                code, head = request('/completion', body | {'n_predict': 6, 'retain_state': True})
                require(code == 200 and head.get('tokens') == full['tokens'][:6], f'{label} retained head', head)
                code, saved = request('/slots/0?action=save', {'filename': f'{label}-resume.bin'})
                require(code == 200, f'{label} save', saved)
                code, restored = request('/slots/0?action=restore', {'filename': f'{label}-resume.bin'})
                require(code == 200, f'{label} restore', restored)
                extended.append({'label': label, 'filename': f'{label}-resume.bin', 'body': body | {'n_predict': 10},
                                 'endpoint': '/completion', 'expected': full['tokens'][6:]})
                code, tail = request('/completion', body | {'n_predict': 10, 'resume': True})
                require(code == 200 and head['tokens'] + tail.get('tokens', []) == full['tokens'], f'{label} continuation', tail)
            body = {'messages': [{'role': 'user', 'content': references[0]['text']}], 'temperature': 0.7,
                    'seed': 123, 'max_tokens': 16, 'ignore_eos': True, 'id_slot': 0, 'cache_prompt': False,
                    'chat_template_kwargs': {'enable_thinking': False}}
            code, full = request('/v1/chat/completions', body)
            require(code == 200, 'OpenAI continuation baseline', full)
            code, head = request('/v1/chat/completions', body | {'max_tokens': 6, 'retain_state': True})
            require(code == 200, 'OpenAI retain', head)
            code, saved = request('/slots/0?action=save', {'filename': 'openai-resume.bin'})
            require(code == 200, 'OpenAI save parser continuation', saved)
            extended.append({'label': 'OpenAI', 'filename': 'openai-resume.bin', 'body': body | {'max_tokens': 10},
                             'endpoint': '/v1/chat/completions', 'expected': full['choices'][0]['message']})
            (args.output.parent / 'extended-reference.json').write_text(json.dumps(extended, indent=2) + '\n')
            code, tail = request('/v1/chat/completions', body | {'max_tokens': 10, 'resume': True})
            require(code == 200 and tail['choices'][0]['message'] == full['choices'][0]['message'],
                    'OpenAI nonstream resumed message is cumulative', tail)
            request('/v1/chat/completions', body | {'max_tokens': 6, 'retain_state': True})
            stream_request = urllib.request.Request(args.url + '/v1/chat/completions',
                data=json.dumps(body | {'max_tokens': 10, 'resume': True, 'stream': True}).encode(),
                headers={'Content-Type': 'application/json'})
            content = ''
            with urllib.request.urlopen(stream_request, timeout=90) as reply:
                for raw in reply:
                    if raw.startswith(b'data: ') and raw[6:].strip() != b'[DONE]':
                        event = json.loads(raw[6:])
                        for choice in event.get('choices', []):
                            content += choice.get('delta', {}).get('content', '') or ''
            require(head['choices'][0]['message']['content'] + content == full['choices'][0]['message']['content'],
                    'OpenAI stream emits only continuation deltas')
            response_body = {'input': references[0]['text'], 'temperature': 0.7, 'seed': 123,
                             'max_output_tokens': 16, 'ignore_eos': True, 'id_slot': 0, 'cache_prompt': False,
                             'chat_template_kwargs': {'enable_thinking': False}}
            code, response_full = request('/v1/responses', response_body)
            require(code == 200, 'Responses baseline', response_full)
            code, response_head = request('/v1/responses', response_body | {'max_output_tokens': 6, 'retain_state': True})
            require(code == 200, 'Responses retain', response_head)
            code, saved = request('/slots/0?action=save', {'filename': 'responses-resume.bin'})
            require(code == 200, 'Responses save', saved)
            extended.append({'label': 'Responses', 'filename': 'responses-resume.bin',
                             'body': response_body | {'max_output_tokens': 10}, 'endpoint': '/v1/responses',
                             'expected': response_text(response_full)})
            (args.output.parent / 'extended-reference.json').write_text(json.dumps(extended, indent=2) + '\n')
            code, response_tail = request('/v1/responses', response_body | {'max_output_tokens': 10, 'resume': True})
            require(code == 200 and response_text(response_tail) == response_text(response_full),
                    'Responses resumed message is cumulative', response_tail)
            if args.decoder:
                # Legacy prompt/KV files remain valid alongside retained generations.
                body = {'prompt': references[0]['prompt_tokens'], 'n_predict': 3, 'temperature': 0,
                        'id_slot': 0, 'cache_prompt': False}
                code, ordinary = request('/completion', body)
                require(code == 200, 'ordinary completion replaces retained state', ordinary)
                code, saved = request('/slots/0?action=save', {'filename': 'ordinary-kv.bin'})
                require(code == 200, 'legacy prompt KV save', saved)
                code, restored = request('/slots/0?action=restore', {'filename': 'ordinary-kv.bin'})
                require(code == 200, 'legacy prompt KV restore', restored)
                code, rejected = request('/completion', body | {'resume': True})
                require(code == 400, 'legacy KV file is not a retained generation', rejected)
            else:
                check_exact_cache()
        passed = True
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'pass': passed and bool(checks) and all(c['pass'] for c in checks), 'checks': checks}, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(checks)} stock server checks passed')


if __name__ == '__main__':
    _main()
