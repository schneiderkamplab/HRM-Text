#!/usr/bin/env python3
"""Bounded local Transformers EMA-export smoke. No W&B or process control."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def worker(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(8 * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, fix_mistral_regex=False)
    model, info = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa', output_loading_info=True)
    if info['missing_keys'] or info['unexpected_keys'] or info.get('mismatched_keys'):
        raise ValueError(info)
    model = model.eval().cuda()
    rows = [json.loads(line) for line in args.prompts.read_text().splitlines()]
    with (args.output / f'worker_{args.worker}.jsonl').open('x') as stream:
        for index, row in enumerate(rows):
            if index % args.workers != args.worker:
                continue
            rendered = tokenizer.apply_chat_template([{'role': 'user', 'content': row['prompt']}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
            encoded = tokenizer(rendered, add_special_tokens=False, return_tensors='pt').to('cuda')
            encoded['token_type_ids'] = torch.ones_like(encoded['input_ids'])
            budget = 768 if row['task'] == 'creative_writing' else 384
            if encoded['input_ids'].shape[1] + budget > 2048:
                raise ValueError('Prompt exceeds bounded context')
            started = time.time()
            with torch.inference_mode():
                output = model.generate(**encoded, max_new_tokens=budget, do_sample=False,
                    pad_token_id=tokenizer.pad_token_id, eos_token_id=model.config.eos_token_id,
                    use_cache=True)
            ids = output[0, encoded['input_ids'].shape[1]:].tolist()
            result = dict(row, index=index, response=tokenizer.decode(ids, skip_special_tokens=True),
                output_ids=ids, rendered_prompt=rendered, prompt_tokens=encoded['input_ids'].shape[1],
                output_tokens=len(ids), finish_reason='length' if len(ids) >= budget else 'stop',
                elapsed_seconds=time.time()-started,
                peak_reserved_gib=torch.cuda.max_memory_reserved()/1024**3)
            stream.write(json.dumps(result, ensure_ascii=False)+'\n')
            stream.flush()
            print(f"{index} {row['language']} {row['task']} tokens={len(ids)} seconds={result['elapsed_seconds']:.1f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--prompts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--worker', type=int)
    parser.add_argument('--label', default='XL 2930K EMA')
    args = parser.parse_args()
    os.environ['WANDB_MODE'] = 'disabled'
    os.environ['WANDB_DISABLED'] = 'true'
    if args.worker is not None:
        worker(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    processes = []
    for gpu in range(args.workers):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
        with (args.output/f'worker_{gpu}.log').open('w') as log:
            proc = subprocess.Popen([sys.executable, __file__, '--model', str(args.model),
                '--prompts', str(args.prompts), '--output', str(args.output),
                '--workers', str(args.workers), '--worker', str(gpu)], env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(proc)
    statuses = [p.wait() for p in processes]
    if any(statuses):
        raise RuntimeError(f'Worker failures: {statuses}; outputs retained')
    rows = [json.loads(line) for path in sorted(args.output.glob('worker_*.jsonl')) for line in path.read_text().splitlines()]
    rows.sort(key=lambda r: r['index'])
    expected = len(args.prompts.read_text().splitlines())
    if [r['index'] for r in rows] != list(range(expected)):
        raise ValueError('Missing or duplicated results')
    (args.output/'responses.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    (args.output/'responses.md').write_text('# ' + args.label + ' multilingual smoke\n\n' + '\n\n'.join(
        f"## {r['language']} / {r['task']}\n\n**Prompt:**\n\n{r['prompt']}\n\n**Response:**\n\n{r['response']}" for r in rows))
    print('COMPLETE', len(rows), args.output, flush=True)


if __name__ == '__main__':
    main()
