"""Full-checkpoint v1/Mimir2 export and vLLM parity; no W&B or production servers."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import torch
from safetensors.torch import load_file
from transformers import AutoTokenizer

from smoke_vllm_launch_modes import cases


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def prepare(args):
    from vllm.model_executor.models.mimir2 import pack_weights
    old = load_file(str(args.original / 'model.safetensors'))
    new = dict(pack_weights(load_file(str(args.mimir2 / 'model.safetensors')).items()))
    # Native production uses attn, Mimir2 uses self_attn; both pack G/Q/K/V.
    new = {k.replace('.self_attn.', '.attn.'): v for k, v in new.items()}
    if set(old) != set(new):
        raise RuntimeError({'missing': sorted(set(old)-set(new)), 'extra': sorted(set(new)-set(old))})
    differences = [k for k in old if not torch.equal(old[k], new[k])]
    assert not differences, differences
    report = {'tensor_count': len(old), 'numel': sum(v.numel() for v in old.values()),
              'all_weights_bitwise_equal': True, 'tokenizer_repairs': {}}
    reference_cfg = json.loads((args.original / 'config.json').read_text())
    for folder in args.repair_export:
        cfg = json.loads((folder / 'config.json').read_text())
        generation = json.loads((folder / 'generation_config.json').read_text())
        report['tokenizer_repairs'][str(folder)] = {k: cfg.get(k) for k in ('bos_token_id', 'eos_token_id', 'pad_token_id')}
        tok = AutoTokenizer.from_pretrained(args.original, fix_mistral_regex=True)
        for field, token in (('bos_token', '<bos>'), ('eos_token', '<turn|>'), ('pad_token', '<pad>')):
            setattr(tok, field, token)
            key = field + '_id'
            assert getattr(tok, key) == reference_cfg[key]
            cfg[key] = generation[key] = reference_cfg[key]
        tok.init_kwargs['fix_mistral_regex'] = True
        # Materialize the effective production pretokenizer: new model configs
        # make Transformers skip the legacy runtime regex patch.
        tok.save_pretrained(folder)
        save(folder / 'config.json', cfg)
        save(folder / 'generation_config.json', generation)
        receipt_path = folder / 'export_receipt.json'
        receipt = json.loads(receipt_path.read_text())
        receipt['effective_tokenizer_reference'] = str(args.original.resolve())
        receipt['special_token_ids'] = {k: cfg[k] for k in ('bos_token_id', 'eos_token_id', 'pad_token_id')}
        save(receipt_path, receipt)
    config = json.loads((args.mimir2 / 'config.json').read_text())
    keys = ('vocab_size', 'hidden_size', 'intermediate_size', 'num_attention_heads',
            'head_dim', 'H_cycles', 'L_cycles', 'embedding_scale', 'rms_norm_eps',
            'max_position_embeddings', 'prefix_lm', 'rope_parameters',
            'bos_token_id', 'eos_token_id', 'pad_token_id')
    report['configuration'] = {k: {'v1': reference_cfg.get(k), 'mimir2': config.get(k)} for k in keys}
    assert all(v['v1'] == v['mimir2'] for v in report['configuration'].values())
    assert reference_cfg['num_hidden_layers'] == config['num_layers_per_stack']
    report['physical_layers_per_stack'] = config['num_layers_per_stack']
    report['expanded_cache_slots'] = config['num_hidden_layers']
    tokenizers = [AutoTokenizer.from_pretrained(p, fix_mistral_regex=True) for p in (args.original, args.mimir2)]
    template = Path('evaluation/chat_templates/gemma4_native_chat.jinja').read_text()
    prompts = []
    for item in cases():
        texts = [tok.apply_chat_template(item['messages'], tools=item.get('tools'),
                 chat_template=template, tokenize=False, add_generation_prompt=True,
                 enable_thinking=False) for tok in tokenizers]
        ids = [tok.encode(text, add_special_tokens=False) for tok, text in zip(tokenizers, texts)]
        assert texts[0] == texts[1] and ids[0] == ids[1], item['id']
        prompts.append({'id': item['id'], 'messages': item['messages'], 'prompt': texts[0], 'token_ids': ids[0]})
    report['identical_prompt_tokenization'] = len(prompts)
    report['effective_pretokenizer_identical'] = (tokenizers[0].backend_tokenizer.pre_tokenizer.__getstate__()
                                                == tokenizers[1].backend_tokenizer.pre_tokenizer.__getstate__())
    report['template_sha256'] = hashlib.sha256(template.encode()).hexdigest()
    save(args.output / 'prompts.json', prompts)
    save(args.output / 'export_comparison.json', report)
    print(json.dumps(report, indent=2), flush=True)


def worker(args):
    from vllm import LLM, SamplingParams
    prompts = json.loads((args.output / 'prompts.json').read_text())
    tokenizer = AutoTokenizer.from_pretrained(args.model, fix_mistral_regex=True)
    for p in prompts:
        assert tokenizer.encode(p['prompt'], add_special_tokens=False) == p['token_ids'], p['id']
    tick = time.monotonic()
    engine = LLM(model=str(args.model), dtype='bfloat16', enforce_eager=False,
                 max_model_len=512, max_num_seqs=2, max_num_batched_tokens=512,
                 kv_cache_memory_bytes=512 * 1024 * 1024, gpu_memory_utilization=0.06,
                 attention_backend='FLASH_ATTN', enable_prefix_caching=False,
                 enable_chunked_prefill=False, seed=0)
    result = {'model': str(args.model), 'startup_seconds': time.monotonic()-tick,
              'enforce_eager': False, 'rows': [], 'teacher_forced': []}
    params = SamplingParams(temperature=0, max_tokens=64, logprobs=5, seed=0,
                            stop_token_ids=[tokenizer.eos_token_id], skip_special_tokens=False)
    try:
        outputs = engine.generate([{'prompt_token_ids': p['token_ids']} for p in prompts], params, use_tqdm=False)
        for p, request in zip(prompts, outputs, strict=True):
            o = request.outputs[0]
            result['rows'].append({'id': p['id'], 'tokens': list(o.token_ids), 'text': o.text,
                'finish_reason': o.finish_reason, 'stop_reason': o.stop_reason,
                'logprobs': [{str(k): {'logprob': v.logprob, 'rank': v.rank} for k, v in row.items()} for row in o.logprobs]})
            print(args.label, p['id'], repr(o.text), flush=True)
        # Both backends score precisely the same baseline continuation, even if greedy paths diverge.
        reference = json.loads(args.teacher.read_text()) if args.teacher else result
        contexts = [{'prompt_token_ids': p['token_ids'] + row['tokens']}
                    for p, row in zip(prompts, reference['rows'], strict=True)]
        scored = engine.generate(contexts, SamplingParams(temperature=0, max_tokens=1, prompt_logprobs=1), use_tqdm=False)
        # PrefixLM prefill makes the entire prompt bidirectional, so these are
        # not causal continuation likelihoods. They only test matched execution.
        for p, request in zip(prompts, scored, strict=True):
            values = []
            for token, row in zip(request.prompt_token_ids, request.prompt_logprobs, strict=True):
                values.append(None if row is None else row[token].logprob)
            result['teacher_forced'].append({'id': p['id'], 'prefill_logprobs': values})
    finally:
        result['seconds'] = time.monotonic()-tick
        save(args.output / f'{args.label}.json', result)
        engine.llm_engine.engine_core.shutdown()


def summarize(args):
    a = json.loads((args.output / 'v1.json').read_text())
    b = json.loads((args.output / 'mimir2.json').read_text())
    rows, all_deltas, probability_deltas = [], [], []
    for x, y in zip(a['rows'], b['rows'], strict=True):
        common = 0
        deltas = []
        for i, (t, u) in enumerate(zip(x['tokens'], y['tokens'])):
            if t != u:
                break
            common += 1
            deltas.append(abs(x['logprobs'][i][str(t)]['logprob']-y['logprobs'][i][str(t)]['logprob']))
            probability_deltas.append(abs(math.exp(x['logprobs'][i][str(t)]['logprob'])
                                          - math.exp(y['logprobs'][i][str(t)]['logprob'])))
        all_deltas.extend(deltas)
        rows.append({'id': x['id'], 'identical_tokens': x['tokens']==y['tokens'],
                     'common_prefix': common, 'v1_tokens': len(x['tokens']), 'mimir2_tokens': len(y['tokens']),
                     'max_common_logprob_delta': max(deltas, default=0),
                     'v1_text': x['text'], 'mimir2_text': y['text']})
    prefill = [abs(x-y) for arow, brow in zip(a['teacher_forced'], b['teacher_forced'], strict=True)
               for x, y in zip(arow['prefill_logprobs'], brow['prefill_logprobs'], strict=True) if x is not None and y is not None]
    summary = {'identical': sum(r['identical_tokens'] for r in rows), 'total': len(rows),
               'matched_generated_tokens': sum(r['common_prefix'] for r in rows),
               'total_generated_tokens': sum(r['v1_tokens'] for r in rows),
               'mean_generated_logprob_delta': sum(all_deltas)/len(all_deltas),
               'max_generated_logprob_delta': max(all_deltas),
               'max_generated_probability_delta': max(probability_deltas),
               'max_prefill_logprob_delta': max(prefill), 'rows': rows}
    env_check = args.output / 'v1_mimir2_env.json'
    if env_check.exists():
        original_new_env = json.loads(env_check.read_text())
        summary['original_model_environment_control_identical'] = (
            a['rows'] == original_new_env['rows']
            and a['teacher_forced'] == original_new_env['teacher_forced'])
    save(args.output / 'summary.json', summary)
    lines = ['# 3.82M Control: HRM-Text vs Mimir2', '',
             'Both use EMA, BF16, compiled vLLM, FA4, the same prompt IDs and greedy decoding. No W&B writes.', '',
             '## Findings', '',
             '- All 131 packed/canonical weight tensors (1,786,775,040 elements) are bit-identical.',
             '- Fixed missing BOS/EOS/PAD assignments and materialized the production regex preprocessing in both queued Mimir2 exports.',
             '- Prompt tokenization matches across the actual production and development environments.',
             f"- Original HRM-Text across both environments has identical tokens and logprobs: {summary.get('original_model_environment_control_identical', 'not tested')}. Remaining differences are between compiled model implementations, not the tested environment change.",
             f"- Identical generations: {summary['identical']}/{summary['total']} prompts, {summary['matched_generated_tokens']}/{summary['total_generated_tokens']} tokens.",
             f"- Mean/max generated-token logprob difference: {summary['mean_generated_logprob_delta']:.6g}/{summary['max_generated_logprob_delta']:.6g} nats.",
             f"- Maximum generated-token probability difference: {100*summary['max_generated_probability_delta']:.4g} percentage points.",
             f"- Matched bidirectional-prefill diagnostic maximum logprob difference: {max(prefill):.6g} nats. This is not a causal continuation likelihood or perplexity measurement.",
             '- These are short prompts (26-109 tokens), at most 64 generated tokens and two active requests. This is full-weight parity evidence, not proof of equality for every context/batch or downstream benchmark.',
             '- The tool-call probe intentionally uses only the normal end-of-turn stop token; both produce the same valid call followed by a degenerate tool-response tail. It tests parity, not successful tool-protocol stopping.', '',
             '## Per Prompt', '',
             '| Prompt | Identical tokens | Common prefix / v1 tokens | Max common-token logprob delta |',
             '| --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['id']} | {r['identical_tokens']} | {r['common_prefix']}/{r['v1_tokens']} | {r['max_common_logprob_delta']:.6g} |")
    for r in rows:
        lines.extend(['', '## '+r['id'], '', '### HRM-Text', '', '```text', r['v1_text'], '```', '',
                      '### Mimir2', '', '```text', r['mimir2_text'], '```'])
    (args.output / 'report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'worker', 'summarize'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--original', type=Path)
    p.add_argument('--mimir2', type=Path)
    p.add_argument('--repair-export', type=Path, action='append', default=[])
    p.add_argument('--model', type=Path)
    p.add_argument('--label')
    p.add_argument('--teacher', type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    {'prepare': prepare, 'worker': worker, 'summarize': summarize}[args.mode](args)
