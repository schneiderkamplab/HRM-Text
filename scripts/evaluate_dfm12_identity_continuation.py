#!/usr/bin/env python3
"""Unprimed, non-EMA identity comparison; no W&B, servers or process control.

Harvey: launch only in the GPU-7-free interlude. Use --checkpoint for the new
root and --previous-checkpoint if the earlier checkpoint stays in its old root.
--preflight-only is CPU-only and does not load models or require either tag.
Outputs: responses.json, responses.md, summary.json and summary.md. The heldout
is a prompt-wording holdout with shared facts/targets, not unseen knowledge or
human-reviewed gold. Reference targets NEVER enter generation histories.
"""
import argparse
from collections import Counter, defaultdict
import gc
import gzip
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts.smoke_dfm12_identity import QUESTIONS

DEFAULT_CHECKPOINT = ROOT / 'checkpoints/dfm12/XL-identity-da-en-from-dfm11-epoch10'
DEFAULT_DATA = ROOT / 'data/dfm12/identity-expansion-da-en-20260926-v2-r2'
MANIFEST_SHA = '28cb1b97c542a25af19128c7b91bc37b24d87a6144dd62e220d10af3705125a4'
REGRESSION_REQUESTS = dict(name='name', creator='creator', leaders='org_leads',
                           team='members', architecture='architecture', namesake='namesake',
                           gemma='gemma_weights', backprop='bp_contrast')
LIMITATIONS = ('Lexical/anchor diagnostics only: mentions do not establish correct attribution, '
              'negation, role assignment, architecture relationships, fluency or absence of hallucinations. '
              'Targets are agent-authored and not independent human gold. This is a prompt-wording '
              'holdout with shared facts and targets, not unseen-knowledge generalization.')


class EvaluationBudgetExceeded(TimeoutError):
    pass


def budget_expired(signum, frame):
    raise EvaluationBudgetExceeded('Per-checkpoint wall-time budget expired; incomplete, not a pass')


def gzip_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_cases(root, manifest_sha=MANIFEST_SHA):
    manifest_path = root / 'manifest.json'
    if file_hash(manifest_path) != manifest_sha:
        raise ValueError('Heldout manifest pin mismatch')
    manifest = load(manifest_path)
    files = {item['path']: item for item in manifest['files']}
    needed = ['heldout/da/test.jsonl.gz', 'heldout/en/test.jsonl.gz',
              'metadata/provenance.jsonl.gz', 'metadata/identity_expansion.yaml', 'metadata/identity_facts.yaml']
    for relative in needed:
        if file_hash(root / relative) != files[relative]['sha256']:
            raise ValueError('Heldout/source checksum mismatch: ' + relative)
    spec = yaml.safe_load((root / 'metadata/identity_expansion.yaml').read_text())
    provenance = {r['id']: r for r in gzip_rows(root / 'metadata/provenance.jsonl.gz') if r['split'] == 'heldout'}
    cases = []
    for name, lang, question in QUESTIONS:
        request = REGRESSION_REQUESTS[name.split('-', 1)[1]]
        target = spec['requests'][request]['detailed'][lang]
        cases.append({'id': name, 'suite': 'regression', 'language': lang,
                      'users': [question], 'expected_targets': [target], 'requests': [[request]]})
    for lang in ('da', 'en'):
        records = list(gzip_rows(root / 'heldout' / lang / 'test.jsonl.gz'))
        if len(records) != 50:
            raise ValueError('Expected exactly 50 heldout conversations per language')
        for row in records:
            messages = row['messages']
            if (row['language'] != lang or not messages or len(messages) % 2
                    or any(m['role'] != ('user' if i % 2 == 0 else 'assistant')
                           or not isinstance(m['content'], str) or not m['content'].strip()
                           for i, m in enumerate(messages))):
                raise ValueError('Heldout must contain native alternating user/assistant turns, no system priming')
            p = provenance[row['id']]
            if p['record_sha256'] != digest(row):
                raise ValueError('Heldout record/provenance mismatch')
            cases.append({'id': row['id'], 'suite': 'heldout', 'language': lang,
                          'users': [m['content'] for m in messages[::2]],
                          'expected_targets': [m['content'] for m in messages[1::2]],
                          'requests': [t['requests'] for t in p['turn_references']],
                          'family': p['family'], 'source_record_sha256': p['record_sha256']})
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate evaluation IDs')
    # Interleave languages so a time-limited pass does not evaluate Danish only.
    heldout = {lang: [c for c in cases if c['suite'] == 'heldout' and c['language'] == lang]
               for lang in ('da', 'en')}
    cases = [c for c in cases if c['suite'] == 'regression'] + [
        c for pair in zip(heldout['da'], heldout['en']) for c in pair]
    return cases, manifest


def normalize(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', text))


def heuristic(response, expected, requests=()):
    """Reference-selected name/number mentions, never a semantic pass/fail."""
    response_n, expected_n = normalize(response), normalize(expected)
    names = ['Mimir', 'Danish Foundation Models', 'Kristoffer Nielbo', 'Peter Schneider-Kamp',
             'Jacob Nielsen', 'Lukas Galke Poech', 'Gianluca Barmina', 'Annemette Brok Pirchert',
             'Kenneth Enevoldsen', 'Gemma']
    candidates = [(name, normalize(name)) for name in names]
    candidates += [(number, number) for number in sorted(set(re.findall(r'\b\d+\b', expected_n)))]
    contains = lambda text, key: f' {key} ' in f' {text} '
    anchors = [name for name, key in candidates if contains(expected_n, key)]
    hits = [name for name in anchors if contains(response_n, normalize(name))]
    a, b = Counter(response_n.split()), Counter(expected_n.split())
    overlap = sum((a & b).values())
    f1 = 2 * overlap / (sum(a.values()) + sum(b.values())) if a or b else 1.0
    flags = []
    if set(anchors) - set(hits):
        flags.append('expected_name_or_numeric_anchor_missing_review_paraphrase_and_facts')
    if set(requests) & {'team_lead', 'members', 'roles', 'kristoffer'} and 'kristoffer' in response_n:
        flags.append('organizational_vs_training_team_role_review_required')
    if set(requests) & {'historical_bp', 'bp_contrast', 'full_bp'}:
        if re.search(r'\b(?:both|begge|always|altid)\b', response_n) and re.search(r'\b(?:full|fuld)\b', response_n):
            flags.append('possible_historical_full_backprop_conflation_check_negation')
    if re.search(r'\b(?:google|openai|anthropic|chatgpt)\b', response_n):
        flags.append('external_provider_or_model_mention_check_denial_vs_wrong_attribution')
    return {'expected_anchors': anchors, 'matched_anchors': hits,
            'anchor_recall': len(hits) / len(anchors) if anchors else None,
            'reference_token_f1': f1, 'empty': not response.strip(),
            'review_flags': flags, 'semantic_correctness': 'not_assessed'}


def render_prompt(tokenizer, messages, max_context, max_new_tokens):
    if not messages or messages[-1]['role'] != 'user' or any(m['role'] == 'system' for m in messages):
        raise ValueError('Only unprimed generated history ending in a user turn is allowed')
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                             enable_thinking=False)
    ids = tokenizer.encode(rendered, add_special_tokens=False)
    if len(ids) + max_new_tokens >= max_context:
        raise ValueError('Full generated history plus output budget exceeds context; no truncation allowed')
    return rendered, ids


class TokenizedCheckpoint:
    """Adapt the existing inference loop to exact multi-turn prompt token IDs."""
    def __init__(self, checkpoint, prompt_ids):
        self.model = checkpoint.model
        self.carry = checkpoint.carry
        self.checkpoint = checkpoint
        self.prompt_ids = prompt_ids
        self.generated_ids = None
        self.eos_id = None

    def tokenize_prompt(self, condition, prompt):
        import numpy as np
        return np.asarray(self.prompt_ids, dtype=np.int64)

    def stop_token_id(self):
        return self.checkpoint.stop_token_id()

    def decode_generation(self, tokens, eos_id):
        self.generated_ids = tokens.tolist()
        self.eos_id = eos_id
        return self.checkpoint.decode_generation(tokens, eos_id)


def generate_turn(checkpoint, messages, max_context, max_new_tokens):
    from simple_inference_engine import inference_generate
    rendered, ids = render_prompt(checkpoint.tokenizer, messages, max_context, max_new_tokens)
    adapter = TokenizedCheckpoint(checkpoint, ids)
    start = time.monotonic()
    outputs = list(inference_generate(adapter, iter([(0, ('raw', ''))]),
                                     max_context, max_new_tokens, 1, 0.0))
    if len(outputs) != 1 or outputs[0][0] != 0 or adapter.generated_ids is None:
        raise RuntimeError('Inference did not produce exactly one tracked output')
    generated = adapter.generated_ids
    eos = bool(generated and generated[-1] == adapter.eos_id)
    if not eos and len(generated) != max_new_tokens:
        raise RuntimeError('Unexpected non-EOS generation termination')
    return {'response': outputs[0][1], 'rendered_prompt': rendered, 'prompt_token_ids': ids,
            'generated_token_ids': generated, 'generated_token_count': len(generated),
            'finish_reason': 'eos' if eos else 'length', 'truncated': not eos,
            'seconds': time.monotonic() - start}


def run_conversation(case, generate, result=None, on_update=lambda: None):
    if result is None:
        result = {'id': case['id'], 'suite': case['suite'], 'language': case['language'],
                  'family': case.get('family'), 'turns': [], 'generated_history': [], 'status': 'incomplete'}
    history, turns = result['generated_history'], result['turns']
    for i, user in enumerate(case['users']):
        history.append({'role': 'user', 'content': user})
        prompt_messages = [dict(m) for m in history]
        generated = generate(prompt_messages)
        expected = case['expected_targets'][i]
        turns.append(dict(generated, turn=i + 1, prompt_messages=prompt_messages, user=user,
                          expected_target=expected, requests=case['requests'][i],
                          heuristics=heuristic(generated['response'], expected, case['requests'][i])))
        history.append({'role': 'assistant', 'content': generated['response']})
        on_update()
    result['status'] = 'complete'
    return result


def summarize(report):
    output = {'limitations': LIMITATIONS, 'runs': {}, 'identity_positive': None,
              'full_suite_gate': 'Explicit parent review required; never automatically approved by this script',
              'report_status': report['status'], 'paired_comparison': []}
    for run in report['runs']:
        groups = defaultdict(list)
        for c in run['conversations']:
            groups[c['suite'] + '/' + c['language']].extend(c['turns'])
        summary = {}
        for key, turns in sorted(groups.items()):
            recalls = [t['heuristics']['anchor_recall'] for t in turns if t['heuristics']['anchor_recall'] is not None]
            summary[key] = {'turns': len(turns), 'length_stops': sum(t['truncated'] for t in turns),
                            'empty_responses': sum(t['heuristics']['empty'] for t in turns),
                            'anchor_scored_turns': len(recalls),
                            'mean_anchor_recall': sum(recalls) / len(recalls) if recalls else None,
                            'mean_reference_token_f1': sum(t['heuristics']['reference_token_f1'] for t in turns) / len(turns)}
        output['runs'][run['label']] = summary
    if len(report['runs']) == 2:
        indices = [{(c['id'], t['turn']): t for c in r['conversations'] for t in c['turns']}
                   for r in report['runs']]
        for key in sorted(indices[0].keys() & indices[1].keys()):
            a, b = [index[key] for index in indices]
            output['paired_comparison'].append({'id': key[0], 'turn': key[1],
                'previous_flags': a['heuristics']['review_flags'], 'continued_flags': b['heuristics']['review_flags'],
                'previous_finish': a['finish_reason'], 'continued_finish': b['finish_reason'],
                'previous_anchor_recall': a['heuristics']['anchor_recall'],
                'continued_anchor_recall': b['heuristics']['anchor_recall'],
                'note': 'Later prompts contain checkpoint-specific generated histories; human review required'})
    output['expected_turns_per_checkpoint'] = sum(len(c['users']) for c in report['cases'])
    output['paired_turns'] = len(output['paired_comparison'])
    return output


def save(output, report):
    write_json(output / 'responses.json', report)
    summary = summarize(report)
    write_json(output / 'summary.json', summary)
    text = ['# Identity Continuation Comparison', '', LIMITATIONS, '',
            'Non-EMA, greedy, batch one. No facts/system priming. Earlier assistant turns are generated, not gold.',
            'All reference targets are reporting/scoring only. JSON also records exact rendered prompts and token IDs.', '']
    # Group by case so previous/continued dialogues can be compared directly.
    for case in report['cases']:
        text += [f"## {case['suite']} / {case['language']} / {case['id']}", '']
        for run in report['runs']:
            conversation = next((c for c in run['conversations'] if c['id'] == case['id']), None)
            text += [f"### {run['label']}: {run['tag']}", '', f"Checkpoint: `{run['checkpoint']}`", '']
            if conversation is None:
                text += ['Not yet evaluated.', '']
            else:
                text += ['Conversation status: ' + conversation['status'], '']
            completed_turns = conversation['turns'] if conversation else []
            for turn in completed_turns:
                text += [f"#### Turn {turn['turn']}", '', '**User**', '', turn['user'], '',
                         '**Generated assistant**', '', turn['response'], '', '**Expected target (not supplied)**', '',
                         turn['expected_target'], '', f"Finish: {turn['finish_reason']}; tokens: {turn['generated_token_count']}",
                         '', 'Limited heuristic: ' + json.dumps(turn['heuristics'], ensure_ascii=False), '']
            for i in range(len(completed_turns), len(case['users'])):
                text += [f'#### Turn {i + 1} (not generated)', '', '**User**', '', case['users'][i], '',
                         '**Expected target (not supplied)**', '', case['expected_targets'][i], '']
    with atomic(output / 'responses.md') as handle:
        handle.write('\n'.join(text))
    with atomic(output / 'summary.md') as handle:
        handle.write('# Limited Identity Diagnostics\n\n' + LIMITATIONS + '\n\n```json\n'
                     + json.dumps(summary, indent=2, ensure_ascii=False) + '\n```\n')


def gpu_status():
    common = ['nvidia-smi', '--id=7']
    metrics = subprocess.run(common + ['--query-gpu=index,memory.free,utilization.gpu', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, check=True, timeout=30)
    index, free, utilization = map(int, metrics.stdout.strip().split(','))
    processes = subprocess.run(common + ['--query-compute-apps=pid', '--format=csv,noheader,nounits'],
                               capture_output=True, text=True, check=True, timeout=30)
    pids = [int(p.strip()) for p in processes.stdout.splitlines() if p.strip()]
    if index != 7 or set(pids) - {os.getpid()}:
        raise RuntimeError('GPU 7 is not exclusively free for this interlude; refusing to compete')
    return {'physical_gpu': index, 'free_mib': free, 'utilization': utilization, 'compute_pids': pids}


def tokenizer_lengths(cases, manifest):
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(manifest['tokenizer']['path'])
    result = {}
    for language in ('da', 'en'):
        lengths = [len(tokenizer.encode(t, add_special_tokens=False).ids) for c in cases
                   if c['language'] == language and c['suite'] == 'heldout' for t in c['expected_targets']]
        result[language] = {'assistant_targets': len(lengths), 'max_target_tokens': max(lengths),
                            'mean_target_tokens': sum(lengths) / len(lengths)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, default=DEFAULT_CHECKPOINT, help='New checkpoint root')
    parser.add_argument('--previous-checkpoint', type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument('--previous-tag', default='step_2878261')
    parser.add_argument('--tag', default='step_2879261')
    parser.add_argument('--heldout-root', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--heldout-manifest-sha256', default=MANIFEST_SHA)
    parser.add_argument('--max-new-tokens', type=int, default=512)
    parser.add_argument('--max-context', type=int, default=4096)
    parser.add_argument('--max-seconds', type=int, default=1800,
                        help='Total model-evaluation budget, divided equally between checkpoints; partial output is not success')
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    if args.max_seconds < 2 or not 1 <= args.max_new_tokens <= 1024 or not args.max_new_tokens < args.max_context <= 4096:
        parser.error('Require 1..1024 new tokens and a larger context <=4096; no truncation')
    os.chdir(ROOT)
    os.environ.update(WANDB_MODE='disabled', WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false')
    cases, manifest = load_cases(args.heldout_root, args.heldout_manifest_sha256)
    for key in ('tokenizer', 'template'):
        if file_hash(manifest[key]['path']) != manifest[key]['sha256']:
            raise ValueError('Raw training ' + key + ' changed')
    report = {'started': time.time(), 'status': 'preflight', 'script_sha256': file_hash(__file__),
              'inference_source_sha256': file_hash(ROOT / 'simple_inference_engine.py'),
              'regression_source_sha256': file_hash(ROOT / 'scripts/smoke_dfm12_identity.py'),
              'heldout_root': str(args.heldout_root.resolve()), 'heldout_manifest_sha256': args.heldout_manifest_sha256,
              'limitations': LIMITATIONS, 'batch_size': 1, 'non_ema': True, 'wandb': False,
              'identity_priming': False, 'history_policy': 'model-generated assistant turns only; reset per case/checkpoint',
              'max_seconds': args.max_seconds, 'per_checkpoint_seconds': args.max_seconds / 2,
              'budget_note': 'SIGALRM interrupts Python/model decoding; an in-flight CUDA/native call must return first. Cleanup is additional.',
              'max_context': args.max_context, 'max_new_tokens': args.max_new_tokens,
              'target_lengths': tokenizer_lengths(cases, manifest), 'cases': cases, 'runs': []}
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output, report)
    if args.preflight_only:
        print(json.dumps({'conversations': len(cases), 'target_lengths': report['target_lengths'],
                          'model_loaded': False}, indent=2))
        return
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '7':
        raise ValueError('Set CUDA_VISIBLE_DEVICES=7; this evaluation may use physical GPU 7 only')
    planned = [('previous', args.previous_checkpoint, args.previous_tag), ('continued', args.checkpoint, args.tag)]
    from scripts.stop_training_at_complete_checkpoint import complete
    for _, checkpoint, tag in planned:
        if not re.fullmatch(r'(?:ephemeral_)?step_\d+', tag) or not complete(checkpoint, tag):
            raise ValueError('Requested checkpoint is not complete: ' + str(checkpoint / tag))
    import torch
    from simple_inference_engine import inference_load_checkpoint
    torch.set_num_threads(2)
    before = gpu_status()
    if before['free_mib'] < 32768:
        raise RuntimeError('Need at least 32 GiB free before model load')
    torch.cuda.set_per_process_memory_fraction(24 * 1024**3 / torch.cuda.get_device_properties(0).total_memory, 0)
    report.update(status='running', gpu_before=before, allocator_limit_gib=24)
    checkpoint = None
    previous_handler = signal.signal(signal.SIGALRM, budget_expired)
    try:
        for label, path, tag in planned:
            if gpu_status()['free_mib'] < 32768:
                raise RuntimeError('Headroom below 32 GiB before checkpoint load')
            print('LOAD', label, path, tag, flush=True)
            run = {'label': label, 'checkpoint': str(path.resolve()), 'tag': tag,
                   'checkpoint_state_sha256': file_hash(path / f'checkpoint_state_{tag}.json'),
                   'dcp_metadata_sha256': file_hash(path / f'fsdp2_{tag}/.metadata'),
                   'config_sha256': file_hash(path / 'all_config.yaml'), 'status': 'loading',
                   'template_sha256': manifest['template']['sha256'], 'tokenizer_sha256': manifest['tokenizer']['sha256'],
                   'conversations': []}
            report['runs'].append(run)
            signal.setitimer(signal.ITIMER_REAL, args.max_seconds / 2)
            try:
                checkpoint = inference_load_checkpoint(str(path), None, False, ckpt_tag=tag)
                info = checkpoint.tokenizer_info
                if info.get('template_mode') != 'jinja_chat_template' or info.get('enable_thinking') is not False:
                    raise ValueError('Expected raw non-thinking training template')
                for key, field in (('template', 'chat_template_path'), ('tokenizer', 'tokenizer_path')):
                    if file_hash(info[field]) != manifest[key]['sha256']:
                        raise ValueError('Checkpoint ' + key + ' differs from pinned training asset')
                if checkpoint.tokenizer.chat_template != Path(info['chat_template_path']).read_text():
                    raise ValueError('Loaded template differs from raw training template')
                run.update(tokenizer_info=info, status='running')
                torch.cuda.reset_peak_memory_stats()
                def generate(messages):
                    if gpu_status()['free_mib'] < 8192:
                        raise RuntimeError('Headroom below 8 GiB; stopping only this evaluation')
                    return generate_turn(checkpoint, messages, args.max_context, args.max_new_tokens)
                for case in cases:
                    conversation = {'id': case['id'], 'suite': case['suite'], 'language': case['language'],
                                    'family': case.get('family'), 'turns': [], 'generated_history': [], 'status': 'incomplete'}
                    run['conversations'].append(conversation)
                    run_conversation(case, generate, conversation, lambda: save(args.output, report))
                    run['peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 1024**2
                    save(args.output, report)
                    print(label, case['suite'], case['language'], case['id'], flush=True)
                run['status'] = 'complete'
            except EvaluationBudgetExceeded as exc:
                run.update(status='budget_exhausted', error=str(exc))
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                checkpoint = None
                gc.collect()
                torch.cuda.empty_cache()
                save(args.output, report)
        status = 'complete' if all(r['status'] == 'complete' for r in report['runs']) else 'incomplete_budget'
        if status == 'complete' and any(t['truncated'] for r in report['runs'] for c in r['conversations'] for t in c['turns']):
            status = 'complete_with_length_stops'
        report.update(status=status, completed=time.time())
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        checkpoint = None
        gc.collect()
        torch.cuda.empty_cache()
        save(args.output, report)
    if report['status'] != 'complete':
        raise SystemExit(4 if report['status'] == 'complete_with_length_stops' else 3)


if __name__ == '__main__':
    main()
