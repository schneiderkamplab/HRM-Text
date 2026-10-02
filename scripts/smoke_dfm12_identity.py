#!/usr/bin/env python3
"""Bounded, unprimed identity smoke; no W&B, servers, scheduler or process control."""
import argparse
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['WANDB_MODE'] = 'disabled'
os.environ['WANDB_DISABLED'] = 'true'

from dfm12.io import file_hash, write_json


QUESTIONS = [
    ('da-name', 'da', 'Hvad hedder du?'),
    ('en-name', 'en', 'What is your name?'),
    ('da-creator', 'da', 'Hvilken organisation har udviklet og trænet dig?'),
    ('en-creator', 'en', 'Which organization developed and trained you?'),
    ('da-leaders', 'da', 'Hvem leder organisationen bag dig?'),
    ('en-leaders', 'en', 'Who leads the organization behind you?'),
    ('da-team', 'da', 'Hvem ledede dit træningshold, og hvem var ellers med på holdet?'),
    ('en-team', 'en', 'Who led your training team, and who else was on that team?'),
    ('da-architecture', 'da', 'Hvordan er din arkitektur opbygget? Beskriv L- og H-modulerne, lagene og cyklusserne.'),
    ('en-architecture', 'en', 'How is your architecture organized? Describe the L and H modules, layers, and cycles.'),
    ('da-namesake', 'da', 'Hvorfor har du fået dit navn?'),
    ('en-namesake', 'en', 'Why were you given your name?'),
    ('da-gemma', 'da', 'Du er vel bare en finjusteret Gemma-model fra Google, ikke?'),
    ('en-gemma', 'en', 'You are just a fine-tuned Google Gemma model, right?'),
    ('da-backprop', 'da', 'Brugte både din første version og din nuværende XL-version fuld backpropagation? Forklar forskellen.'),
    ('en-backprop', 'en', 'Did both your first version and your current XL version use full backpropagation? Explain the difference.'),
]


def gpu_status():
    result = subprocess.run(['nvidia-smi', '--id=7', '--query-gpu=index,memory.used,memory.free,utilization.gpu',
                             '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
    values = [int(v.strip()) for v in result.stdout.strip().split(',')]
    return dict(zip(('index', 'used_mib', 'free_mib', 'utilization'), values))


def save(output, report):
    write_json(output / 'responses.json', report)
    parts = ['# Unprimed Identity Smoke', '',
             'Non-EMA; batch 1; greedy; raw training Gemma template; no system message; no W&B.',
             'Short qualitative smoke, not a general capability or retention evaluation.',
             'Assessment: see assessment.json / assessment.md when available.', '']
    for run in report['runs']:
        parts.extend(['## ' + run['label'], '', f"Checkpoint: `{run['checkpoint']}` / `{run['tag']}`", ''])
        for row in run['responses']:
            parts.extend(['### ' + row['id'], '', '**User:** ' + row['prompt'], '', '**Assistant:**', '', row['response'], ''])
    (output / 'responses.md').write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, default=ROOT / 'checkpoints/dfm12/XL-identity-da-en-from-dfm11-epoch10')
    parser.add_argument('--tag', default='step_2878261')
    parser.add_argument('--baseline-if-fast', action='store_true')
    parser.add_argument('--baseline-budget-seconds', type=int, default=180)
    parser.add_argument('--max-tokens', type=int, default=160)
    args = parser.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '7':
        raise ValueError('This authorized side probe must be isolated to physical GPU 7')
    if not 1 <= args.max_tokens <= 256:
        raise ValueError('Smoke output cap must be 1..256')
    args.output.mkdir(parents=True, exist_ok=False)
    initial = gpu_status()
    if initial['free_mib'] < 24576:
        raise RuntimeError('Insufficient headroom; no model loaded')
    import torch
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(18 * 1024**3 / torch.cuda.get_device_properties(0).total_memory, 0)
    from evaluation.engines import SimpleEngine
    report = {'started': time.time(), 'pid': os.getpid(), 'gpu': 7, 'gpu_before': initial,
              'non_ema': True, 'batch_size': 1, 'temperature': 0, 'max_context': 768,
              'max_new_tokens': args.max_tokens, 'allocator_limit_gib': 18,
              'wandb': False, 'identity_priming': False,
              'multiturn': 'Not used: SimpleEngine public generate API wraps one user message.',
              'facts_sha256': file_hash(ROOT / 'dfm12/identity_facts.yaml'),
              'script_sha256': file_hash(__file__), 'assessment_file': 'assessment.json', 'runs': []}
    planned = [('adapted', args.checkpoint, args.tag)]
    if args.baseline_if_fast:
        planned.append(('baseline', ROOT / 'checkpoints/dfm11/XL-from-dfm10-epoch9', 'epoch_10'))
    for label, checkpoint, tag in planned:
        if label == 'baseline' and time.time() - report['started'] > args.baseline_budget_seconds:
            report['baseline_skipped'] = 'Primary pass exceeded bounded fast-comparison budget'
            break
        if gpu_status()['free_mib'] < 24576:
            report['stopped'] = 'Headroom below 24 GiB before checkpoint load'
            break
        started = time.time()
        print('LOAD', label, str(checkpoint), tag, flush=True)
        engine = SimpleEngine(str(checkpoint), ckpt_tag=tag, ckpt_use_ema=False)
        info = engine.ckpt.tokenizer_info
        if info.get('template_mode') != 'jinja_chat_template' or info.get('enable_thinking') is not False:
            raise ValueError('Expected raw non-thinking training chat template')
        raw_template = Path(info['chat_template_path']).read_text()
        if engine.ckpt.tokenizer.chat_template != raw_template:
            raise ValueError('Loaded template differs from raw training template')
        run = {'label': label, 'checkpoint': str(checkpoint), 'tag': tag, 'non_ema': True,
               'config_sha256': file_hash(checkpoint / 'all_config.yaml'),
               'checkpoint_metadata_sha256': file_hash(checkpoint / f'checkpoint_state_{tag}.json'),
               'tokenizer_info': info, 'template_sha256': file_hash(info['chat_template_path']),
               'tokenizer_sha256': file_hash(info['tokenizer_path']), 'responses': []}
        report['runs'].append(run)
        save(args.output, report)
        for name, language, prompt in QUESTIONS:
            if gpu_status()['free_mib'] < 12288:
                report['stopped'] = 'Headroom below 12 GiB; stopping own probe only'
                break
            messages = [{'role': 'user', 'content': prompt}]
            rendered = engine.ckpt.tokenizer.apply_chat_template(messages, tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
            token_ids = engine.ckpt.tokenize_prompt('direct', prompt).tolist()
            if len(token_ids) + args.max_tokens >= 768:
                raise ValueError('Smoke prompt would exceed bounded context')
            t = time.time()
            response = engine.generate([prompt], batch_size=1, max_context=768,
                max_tokens=args.max_tokens, temperature=0, condition='direct')[0]
            item = {'id': name, 'language': language, 'prompt': prompt, 'messages': messages,
                    'rendered_prompt': rendered, 'prompt_token_ids': token_ids, 'response': response,
                    'seconds': time.time() - t, 'gpu': gpu_status(),
                    'peak_allocated_mib': torch.cuda.max_memory_allocated() / 1024**2,
                    'peak_reserved_mib': torch.cuda.max_memory_reserved() / 1024**2}
            run['responses'].append(item)
            save(args.output, report)
            print(label, name, json.dumps(response, ensure_ascii=False), flush=True)
        run['seconds'] = time.time() - started
        del engine
        gc.collect()
        torch.cuda.empty_cache()
        if 'stopped' in report:
            break
    report['completed'] = time.time()
    report['gpu_after_release'] = gpu_status()
    save(args.output, report)
    print('COMPLETE', args.output, flush=True)


if __name__ == '__main__':
    main()
