"""Bounded templated PrefixLM qualification; raw evidence is retained on failure."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

import numpy as np

__all__ = []


def _save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def _prepare(model_path, out):
    import torch
    from transformers import AutoTokenizer, HrmTextForCausalLM
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    conversations = [
        ('danish-unicode', [{'role': 'user', 'content': 'Ret denne sætning og behold æ, ø og å: "pigen fra århus køber æbler".'}],
         'Pigen fra Århus køber æbler.'),
        ('english-instruction', [{'role': 'user', 'content': 'Give two reasons to save water, separated by a semicolon. No introduction.'}],
         'Protect ecosystems; reduce energy use.'),
        ('multiturn', [{'role': 'user', 'content': 'Jeg hedder Søren og bor i Odense.'},
                       {'role': 'assistant', 'content': 'Hej Søren! Hvordan kan jeg hjælpe dig?'},
                       {'role': 'user', 'content': 'Hvad hedder jeg, og hvor bor jeg? Svar kort.'}],
         'Du hedder Søren og bor i Odense.'),
        ('near-limit', [{'role': 'user', 'content': ''}], 'Kodeordet er ravn.'),
    ]
    def render(messages):
        return tokenizer.apply_chat_template(messages, tokenize=True, return_dict=False,
                                             add_generation_prompt=True, enable_thinking=False)
    # Grow natural-language context, then trim source text (never the template).
    filler = ' Arkivet indeholder gamle breve om vejret, havnen og byens historie.'
    content = 'Læs notatet. Kodeordet er ravn.' + filler * 50
    suffix = '\nHvad er kodeordet? Svar med en kort sætning.'
    while len(render([{'role': 'user', 'content': content + suffix}])) > 480:
        content = content[:-1]
    conversations[-1][1][0]['content'] = content + suffix
    # A medium length multi-turn prompt without adding another evaluation case.
    conversations[2][1][0]['content'] += ' Jeg holder af at læse bøger, gå ture og lave mad.' * 6
    model = HrmTextForCausalLM.from_pretrained(model_path, dtype=torch.float32,
                                             attn_implementation='eager').eval()
    cases, specification = [], []
    with torch.inference_mode():
        for name, messages, answer in conversations:
            prefix = render(messages)
            targets = tokenizer.encode(answer, add_special_tokens=False) + [tokenizer.eos_token_id]
            ids = torch.tensor([prefix + targets])
            types = torch.tensor([[1] * len(prefix) + [0] * len(targets)])
            # Full-forward mixed mask is independent of llama.cpp's cached execution.
            logits = model(ids, token_type_ids=types, use_cache=False,
                           logits_to_keep=len(targets) + 1).logits[0].float().numpy()
            assert np.isfinite(logits).all() and len(prefix) + len(targets) <= 512
            first_path = out / f'{name}-prefix.f32'
            chunk_path = out / f'{name}-answer.f32'
            logits[:1].tofile(first_path)
            logits[1:].tofile(chunk_path)
            for chunked in [False, True]:
                steps = [{'tokens': prefix, 'prefix': True, 'all_logits': False, 'reference': str(first_path)}]
                if chunked:
                    steps.append({'tokens': targets, 'prefix': False, 'reference': str(chunk_path)})
                else:
                    for i, token in enumerate(targets):
                        path = out / f'{name}-{i}.f32'
                        logits[i + 1:i + 2].tofile(path)
                        steps.append({'tokens': [token], 'prefix': False, 'reference': str(path)})
                specification.append({'name': name + ('-chunk' if chunked else '-single'), 'steps': steps})
            cases.append({'name': name, 'messages': messages, 'prompt_tokens': prefix,
                          'answer': answer, 'answer_tokens': targets, 'reference': str(first_path),
                          'answer_reference': str(chunk_path),
                          'template_sha256': hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()})
            print(name, len(prefix), len(targets), flush=True)
    _save(out / 'cases.json', cases)
    _save(out / 'specification.json', {'n_ctx': 512, 'n_ubatch': 480, 'n_gpu_layers': 999,
                                     'max_abs': 0.03, 'cases': specification})


def _evaluate(args, out):
    for weight in args.weights.split(','):
        for flash in [False, True]:
            label = weight + ('-flash' if flash else '-unfused')
            dump = out / label
            dump.mkdir(exist_ok=True)
            spec = json.loads((out / 'specification.json').read_text())
            model_path = (Path('logs/mimir-chat/mimir-text-f32.gguf').resolve() if weight == 'f32'
                          else args.models / f'mimir-{weight}.gguf')
            spec.update(model=str(model_path), flash=flash,
                        logits_dir=str(dump), report=str(out / f'{label}.json'))
            path = out / f'{label}-spec.json'
            _save(path, spec)
            Path(spec['report']).unlink(missing_ok=True)
            with (out / f'{label}.log').open('w') as log:
                result = subprocess.run([str(args.runner), '--prefix-reference', str(path)], stdout=log, stderr=log)
            if result.returncode not in [0, 1] or not Path(spec['report']).exists():
                raise RuntimeError(f'{label}: runner failed ({result.returncode})')
            print(label, 'complete; strict reference exit', result.returncode, flush=True)


def _request(url, path, body=None):
    req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)


def _benchmark(args, out):
    cases = json.loads((out / 'cases.json').read_text())
    selected = [cases[0], cases[2], cases[3]]
    results = []
    for weight in ['bf16', 'q8_0', 'q4_k_m']:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        command = [str(args.server), '-m', str(args.models / f'mimir-{weight}.gguf'),
                   '-ngl', '999', '-c', '512', '-b', '480', '-ub', '480', '-np', '1',
                   '-fa', 'on', '-t', '4', '--host', '127.0.0.1', '--port', str(port)]
        url = f'http://127.0.0.1:{port}'
        with (out / f'benchmark-{weight}.log').open('w') as log:
            # macOS time reports peak process RSS; this is not total GPU/unified-memory use.
            process = subprocess.Popen(['/usr/bin/time', '-l', *command], stdout=log, stderr=log,
                                       start_new_session=True)
            try:
                deadline = time.monotonic() + 120
                while True:
                    try:
                        _request(url, '/health')
                        break
                    except OSError:
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError('server failed to start')
                        time.sleep(.5)
                for case in selected:
                    rendered = _request(url, '/apply-template', {'messages': case['messages'],
                        'add_generation_prompt': True, 'chat_template_kwargs': {'enable_thinking': False}})
                    tokens = _request(url, '/tokenize', {'content': rendered['prompt'],
                                                        'add_special': True, 'parse_special': True})['tokens']
                    assert tokens == case['prompt_tokens'], 'Server/HF template token mismatch'
                # One warmup per length, then three rounds with reversed middle-round order.
                for round_index in range(4):
                    order = list(reversed(selected)) if round_index == 2 else selected
                    for case in order:
                        start = time.perf_counter()
                        response = _request(url, '/completion', {'prompt': case['prompt_tokens'],
                            'n_predict': 16, 'temperature': 0, 'ignore_eos': True, 'return_tokens': True})
                        elapsed = time.perf_counter() - start
                        timings = response['timings']
                        assert timings['prompt_n'] == len(case['prompt_tokens']) and timings['cache_n'] == 0
                        assert len(response['tokens']) == 16 and not response.get('truncated', False)
                        results.append({'weight': weight, 'case': case['name'], 'round': round_index,
                            'warmup': round_index == 0, 'elapsed_s': elapsed, 'timings': timings,
                            'tokens': response['tokens'], 'command': command})
                        _save(out / 'benchmark.json', results)
                        print(weight, case['name'], round_index, round(elapsed, 2), flush=True)
            finally:
                # Signal the child server, letting time reap it and print its resource record.
                children = subprocess.run(['pgrep', '-P', str(process.pid)], capture_output=True, text=True)
                for pid in children.stdout.split():
                    import os
                    import signal
                    os.kill(int(pid), signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    import os
                    import signal
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def _controls(args, out):
    import shutil
    import gguf
    source = Path('logs/mimir-review/reference/hrm_text-dense.gguf')
    records = []
    for mode in ['causal', 'bidirectional']:
        model = out / f'control-{mode}.gguf'
        shutil.copyfile(source, model)
        reader = gguf.GGUFReader(model, mode='r+')
        field = reader.fields['hrm_text.attention.causal']
        field.parts[field.data[0]][0] = mode == 'causal'
        del reader
        for round_index, build in enumerate(['baseline', 'patched', 'patched', 'baseline']):
            executable = (Path('logs/mimir-review/baseline-build/bin/llama-bench')
                          if build == 'baseline' else args.runner.parent / 'llama-bench')
            path = out / f'control-{mode}-{round_index}-{build}.json'
            command = [str(executable), '-m', str(model), '-ngl', '0', '-t', '4',
                       '-p', '256', '-n', '16' if mode == 'causal' else '0',
                       '-b', '256', '-ub', '256', '-r', '25', '-o', 'json']
            with path.open('w') as output, path.with_suffix('.log').open('w') as log:
                subprocess.run(command, stdout=output, stderr=log, check=True)
            records.append({'mode': mode, 'round': round_index, 'build': build,
                            'command': command, 'results': json.loads(path.read_text())})
            _save(out / 'controls.json', records)
            print(mode, round_index, build, flush=True)


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'evaluate', 'benchmark', 'controls'])
    parser.add_argument('--output', type=Path, default=Path('logs/mimir-qualification'))
    parser.add_argument('--weights', default='bf16,q8_0,q4_k_m')
    parser.add_argument('--hf', type=Path, default=Path('logs/prefixlm-comparison/mimir-hf'))
    parser.add_argument('--models', type=Path, default=Path('logs/mimir-review'))
    parser.add_argument('--runner', type=Path, default=Path('logs/mimir-engine/build/bin/test-llama-archs'))
    parser.add_argument('--server', type=Path, default=Path('logs/mimir-engine/build/bin/llama-server'))
    args = parser.parse_args()
    for key in ['output', 'hf', 'models', 'runner', 'server']:
        setattr(args, key, getattr(args, key).resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == 'prepare':
        _prepare(args.hf, args.output)
    elif args.phase == 'evaluate':
        _evaluate(args, args.output)
    elif args.phase == 'benchmark':
        _benchmark(args, args.output)
    else:
        _controls(args, args.output)


if __name__ == '__main__':
    _main()
