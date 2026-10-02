#!/usr/bin/env python3
"""Explicitly pinned fresh identity holdout, 2879261 versus 2880261, non-EMA.

No GPU work with --preflight-only. Actual execution requires an externally
coordinated GPU-7-free interlude. Never launches training or a full suite.
The historical v2-r2 holdout is development data and is NOT evaluated here.
Exit 0 means complete execution, including length stops, NOT identity approval.
Exit 3 means incomplete time-budget coverage; other errors fail nonzero.
"""
import argparse
from collections import Counter
import gc
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts import evaluate_dfm12_identity_continuation as historical

HISTORICAL_SCRIPT_SHA = 'a0270f1073927320e00d9799d6e3e99a965307d79555445258a3144823e6af35'
REGRESSION_SCRIPT_SHA = '931f7fa7deb16938b2e83dbc1c9a402bc9b99e898bb8ffea60707752dc2026c4'
BASELINE = ROOT / 'checkpoints/dfm12/XL-identity-expanded-from-step2878261'
DEVELOPMENT_ROOT = historical.DEFAULT_DATA
DEVELOPMENT_SHA = historical.MANIFEST_SHA
COMPLETED = {'complete', 'complete_with_length_stops'}
REVIEW_REQUEST_ALIASES = {'team': 'team_lead', 'roster': 'members', 'role_contrast': 'roles',
                          'no_titles': 'roles', 'gradient': 'full_bp', 'history': 'bp_contrast'}


def pinned_manifest(root, sha256):
    root = Path(root).resolve()
    if not re.fullmatch(r'[0-9a-f]{64}', sha256) or file_hash(root / 'manifest.json') != sha256:
        raise ValueError('Explicit manifest SHA-256 mismatch')
    manifest = load(root / 'manifest.json')
    files = {}
    for item in manifest['files']:
        relative = Path(item['path'])
        path = (root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(root) or str(relative) in files:
            raise ValueError('Unsafe or duplicate manifest path')
        files[str(relative)] = item
    return manifest, files


def pinned_file(root, files, relative):
    if relative not in files:
        raise ValueError('Required file not listed in manifest: ' + relative)
    item = files[relative]
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Pinned file escaped artifact root')
    if file_hash(path) != item['sha256'] or path.stat().st_size != item['bytes']:
        raise ValueError('Artifact checksum/size mismatch: ' + relative)
    return path


def question_keys(row):
    return {historical.normalize(m['content']) for m in row['messages'] if m['role'] == 'user'}


def load_cases(root, sha256, spec_relative, development_root=DEVELOPMENT_ROOT, development_sha=DEVELOPMENT_SHA):
    """Keep the old 16 prompts/targets; fresh cases must not reuse development turns."""
    root, development_root = Path(root).resolve(), Path(development_root).resolve()
    if root == development_root or sha256 == development_sha:
        raise ValueError('Old heldout is development data, not a fresh holdout')
    manifest, files = pinned_manifest(root, sha256)
    if manifest.get('profile') != 'xl-full-bp' or manifest.get('enable_thinking') is not False:
        raise ValueError('Expected the XL full-backprop, non-thinking identity profile')
    old_manifest, old_files = pinned_manifest(development_root, development_sha)
    spec = yaml.safe_load(pinned_file(root, files, spec_relative).read_text())
    facts_path = pinned_file(root, files, 'metadata/identity_facts.yaml')
    old_facts = pinned_file(development_root, old_files, 'metadata/identity_facts.yaml')
    if file_hash(facts_path) != file_hash(old_facts):
        raise ValueError('Identity facts changed; requires a separately reviewed evaluator contract')
    old_cases, _ = historical.load_cases(development_root, development_sha)
    cases = old_cases[:16]
    forbidden_ids = {c['id'] for c in old_cases}
    forbidden_questions = {historical.normalize(q) for c in old_cases for q in c['users']}
    # Inspect only the two explicitly listed merged training shards, not corpus trees.
    training_files = []
    for lang in ('da', 'en'):
        relative = manifest['languages'][lang]['input']
        if not relative.startswith('inputs/') or not relative.endswith('.jsonl.gz'):
            raise ValueError('Expected an explicitly listed native training shard')
        training_files.append(relative)
        for row in historical.gzip_rows(pinned_file(root, files, relative)):
            forbidden_ids.add(row['id'])
            forbidden_questions.update(question_keys(row))
    provenance = {}
    for entry in historical.gzip_rows(pinned_file(root, files, 'metadata/provenance.jsonl.gz')):
        if entry['split'] == 'heldout':
            if entry['id'] in provenance:
                raise ValueError('Duplicate heldout provenance ID')
            provenance[entry['id']] = entry
    heldout, seen = {}, set()
    for lang in ('da', 'en'):
        selected = []
        for row in historical.gzip_rows(pinned_file(root, files, f'heldout/{lang}/test.jsonl.gz')):
            messages = row['messages']
            if (row['language'] != lang or not 2 <= len(messages) <= 8 or len(messages) % 2
                    or any(m['role'] != ('user' if i % 2 == 0 else 'assistant')
                           or not isinstance(m['content'], str) or not m['content'].strip()
                           for i, m in enumerate(messages))):
                raise ValueError('Expected 1..4 native user/assistant pairs without system priming')
            if row['id'] in seen or row['id'] in forbidden_ids:
                raise ValueError('Duplicate or development/training heldout ID overlap')
            if question_keys(row) & forbidden_questions:
                raise ValueError('Fresh heldout user wording overlaps training/development')
            seen.add(row['id'])
            entry = provenance[row['id']]
            references = entry['turn_references']
            if (entry['record_sha256'] != digest(row) or entry['language'] != lang
                    or len(references) != len(messages) // 2):
                raise ValueError('Heldout record/turn provenance mismatch')
            for i, ref in enumerate(references):
                forms = ref.get('answer_forms')
                if forms is None:
                    if (manifest.get('schema') != 'dfm12-curated-identity-repair-v3'
                            or ref.get('mode') not in ('brief', 'contrast')):
                        raise ValueError('Unknown heldout target-binding schema')
                    forms = [ref['mode']] * len(ref['requests'])
                if not ref['requests'] or len(ref['requests']) != len(forms):
                    raise ValueError('Invalid heldout target binding')
                expected = '\n\n'.join(spec['requests'][key][form][lang]
                                       for key, form in zip(ref['requests'], forms))
                if expected != messages[2 * i + 1]['content']:
                    raise ValueError('Heldout target differs from frozen request bindings')
            selected.append({'id': row['id'], 'suite': 'heldout', 'language': lang,
                             'family': entry['family'], 'source_record_sha256': digest(row),
                             'users': [m['content'] for m in messages[::2]],
                             'expected_targets': [m['content'] for m in messages[1::2]],
                             'requests': [ref['requests'] for ref in references]})
        if len(selected) != 50:
            raise ValueError('Require exactly 50 fresh heldout conversations per language')
        heldout[lang] = selected
    if seen != set(provenance):
        raise ValueError('Heldout provenance has missing or extra records')
    for pair in zip(heldout['da'], heldout['en']):
        cases.extend(pair)
    for key in ('tokenizer', 'template'):
        if (file_hash(manifest[key]['path']) != manifest[key]['sha256']
                or manifest[key]['sha256'] != old_manifest[key]['sha256']):
            raise ValueError('Raw training tokenizer/template changed')
    policy = {'fresh_heldout_root': str(root), 'fresh_manifest_sha256': sha256,
              'frozen_request_spec': spec_relative, 'fresh_conversations_per_language': 50,
              'development_root': str(development_root), 'development_manifest_sha256': development_sha,
              'old_heldout_status': 'development_only_not_evaluated',
              'regression_status': 'fixed_previous_16_prompts_and_targets_development_regressions',
              'training_files_checked': training_files,
              'split_check': 'No normalized full user-turn or ID overlap with training/old evaluation; not semantic leakage detection'}
    return cases, manifest, policy


class InvalidGeneration(RuntimeError):
    def __init__(self, message, output):
        super().__init__(message)
        self.output = output


def validate_generation(output, max_new_tokens):
    if not isinstance(output, dict) or not isinstance(output.get('response'), str) or not output['response'].strip():
        raise InvalidGeneration('Empty or malformed generated response', output)
    ids, count = output.get('generated_token_ids'), output.get('generated_token_count')
    if (not isinstance(ids, list) or not ids or any(type(i) is not int or i < 0 for i in ids)
            or type(count) is not int or len(ids) != count or not 1 <= count <= max_new_tokens):
        raise InvalidGeneration('Invalid generation token accounting', output)
    stop = output.get('finish_reason')
    if (stop not in ('eos', 'length') or output.get('truncated') is not (stop == 'length')
            or (stop == 'length' and count != max_new_tokens)):
        raise InvalidGeneration('Unexpected generation stop contract', output)
    return output


def review_heuristic(turn):
    requests = [REVIEW_REQUEST_ALIASES.get(key, key) for key in turn['requests']]
    return historical.heuristic(turn['response'], turn['expected_target'], requests)


def finish_report(report):
    expected = [(c['id'], len(c['users'])) for c in report['cases']]
    if len(report['runs']) != 2 or [r['label'] for r in report['runs']] != ['previous', 'continued']:
        raise ValueError('Missing checkpoint comparison')
    if any(r['status'] == 'budget_exhausted' for r in report['runs']):
        report['status'] = 'incomplete_budget'
        return 3
    for run in report['runs']:
        actual = [(c['id'], len(c['turns'])) for c in run['conversations']]
        if (run['status'] != 'complete' or actual != expected
                or any(c['status'] != 'complete' for c in run['conversations'])):
            raise ValueError('Incomplete or mismatched conversation coverage')
        for conversation in run['conversations']:
            for turn in conversation['turns']:
                validate_generation(turn, report['max_new_tokens'])
    lengths = any(t['truncated'] for r in report['runs'] for c in r['conversations'] for t in c['turns'])
    report['status'] = 'complete_with_length_stops' if lengths else 'complete'
    return 0


def save(output, report):
    report.update(review_required=True, identity_positive=None, full_suite_approved=None,
                  operational_success=report['status'] in COMPLETED)
    historical.save(output, report)
    summary = historical.summarize(report)
    summary.update(review_required=True, identity_positive=None, full_suite_approved=None,
                   operational_success=report['status'] in COMPLETED,
                   dataset_policy=report['dataset_policy'],
                   exit_policy='0 = complete execution, including length stops, NEVER model acceptance; 3 = incomplete budget; errors fail')
    write_json(output / 'summary.json', summary)
    with atomic(output / 'summary.md') as handle:
        handle.write('# Identity Comparison: Parent Review Required\n\n'
                     'Old v2-r2 heldouts are development data, not fresh evaluation. '
                     'The fixed 16 regressions are also development evidence. '
                     'Length-limited answers are flagged, never assumed correct. '
                     'Operational exit 0 does not approve identity or the full suite.\n\n'
                     + historical.LIMITATIONS + '\n\n```json\n'
                     + json.dumps(summary, ensure_ascii=False, indent=2) + '\n```\n')


def run_models(args, report, manifest):
    """Only the explicit non-preflight path imports GPU inference dependencies."""
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '7':
        raise ValueError('Set CUDA_VISIBLE_DEVICES=7; physical GPU 7 only')
    from scripts.stop_training_at_complete_checkpoint import complete
    for run in report['runs']:
        if not complete(Path(run['checkpoint']), run['tag']):
            raise ValueError('Requested checkpoint is not complete: ' + run['checkpoint'] + '/' + run['tag'])
    import torch
    from simple_inference_engine import inference_load_checkpoint
    torch.set_num_threads(2)
    before = historical.gpu_status()
    if before['free_mib'] < 32768:
        raise RuntimeError('Need at least 32 GiB free before model load')
    torch.cuda.set_per_process_memory_fraction(24 * 1024**3 / torch.cuda.get_device_properties(0).total_memory, 0)
    report.update(status='running', gpu_before=before, allocator_limit_gib=24)
    checkpoint = None
    old_handler = signal.signal(signal.SIGALRM, historical.budget_expired)
    try:
        for run in report['runs']:
            if historical.gpu_status()['free_mib'] < 32768:
                raise RuntimeError('Headroom below 32 GiB before checkpoint load')
            path, tag = Path(run['checkpoint']), run['tag']
            run.update(status='loading', checkpoint_state_sha256=file_hash(path / f'checkpoint_state_{tag}.json'),
                       dcp_metadata_sha256=file_hash(path / f'fsdp2_{tag}/.metadata'),
                       config_sha256=file_hash(path / 'all_config.yaml'))
            save(args.output, report)
            print('LOAD', run['label'], path, tag, flush=True)
            signal.setitimer(signal.ITIMER_REAL, args.max_seconds / 2)
            try:
                checkpoint = inference_load_checkpoint(str(path), None, False, ckpt_tag=tag)
                info = checkpoint.tokenizer_info
                if info.get('template_mode') != 'jinja_chat_template' or info.get('enable_thinking') is not False:
                    raise ValueError('Expected raw non-thinking training template')
                for key, field in (('template', 'chat_template_path'), ('tokenizer', 'tokenizer_path')):
                    if file_hash(info[field]) != manifest[key]['sha256']:
                        raise ValueError('Checkpoint training asset differs from pinned ' + key)
                if checkpoint.tokenizer.chat_template != Path(info['chat_template_path']).read_text():
                    raise ValueError('Loaded template differs from raw training template')
                run.update(tokenizer_info=info, status='running')
                torch.cuda.reset_peak_memory_stats()

                def generate(messages):
                    if historical.gpu_status()['free_mib'] < 8192:
                        raise RuntimeError('Headroom below 8 GiB; stopping evaluation only')
                    return validate_generation(historical.generate_turn(
                        checkpoint, messages, args.max_context, args.max_new_tokens), args.max_new_tokens)

                for case in report['cases']:
                    conversation = {'id': case['id'], 'suite': case['suite'], 'language': case['language'],
                                    'family': case.get('family'), 'turns': [], 'generated_history': [], 'status': 'incomplete'}
                    run['conversations'].append(conversation)

                    def persist_turn():
                        turn = conversation['turns'][-1]
                        turn['heuristics'] = review_heuristic(turn)
                        save(args.output, report)

                    historical.run_conversation(case, generate, conversation, persist_turn)
                    run['peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 1024**2
                    save(args.output, report)
                    print(run['label'], case['suite'], case['language'], case['id'], flush=True)
                run['status'] = 'complete'
            except historical.EvaluationBudgetExceeded as exc:
                run.update(status='budget_exhausted', error=str(exc))
            except Exception as exc:
                run.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                if isinstance(exc, InvalidGeneration):
                    run['invalid_generation'] = exc.output
                raise
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                checkpoint = None
                gc.collect()
                torch.cuda.empty_cache()
                save(args.output, report)
        return finish_report(report)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        checkpoint = None
        gc.collect()
        torch.cuda.empty_cache()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True, help='New continuation root; no assumed alias')
    parser.add_argument('--previous-checkpoint', type=Path, default=BASELINE)
    parser.add_argument('--previous-tag', default='step_2879261')
    parser.add_argument('--tag', default='step_2880261')
    parser.add_argument('--heldout-root', type=Path, required=True)
    parser.add_argument('--heldout-manifest-sha256', required=True, help='Reviewed external manifest pin, never inferred')
    parser.add_argument('--heldout-spec', required=True, help='Manifest-listed frozen target bank relative path')
    parser.add_argument('--max-new-tokens', type=int, default=512)
    parser.add_argument('--max-context', type=int, default=4096)
    parser.add_argument('--max-seconds', type=int, default=3600)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(argv)
    if (args.max_seconds < 2 or not 1 <= args.max_new_tokens <= 1024
            or not args.max_new_tokens < args.max_context <= 4096):
        parser.error('Require positive bounded model-evaluation budget, 1..1024 new tokens and larger context <=4096')
    for tag in (args.previous_tag, args.tag):
        if not re.fullmatch(r'(?:ephemeral_)?step_\d+', tag):
            parser.error('Explicit step checkpoint tags required')
    os.chdir(ROOT)
    os.environ.update(WANDB_MODE='disabled', WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false')
    if file_hash(historical.__file__) != HISTORICAL_SCRIPT_SHA:
        raise ValueError('Frozen historical evaluation helper changed; review before execution')
    if file_hash(ROOT / 'scripts/smoke_dfm12_identity.py') != REGRESSION_SCRIPT_SHA:
        raise ValueError('Frozen 16 regression prompts changed; review before execution')
    cases, manifest, policy = load_cases(args.heldout_root, args.heldout_manifest_sha256, args.heldout_spec)
    report = {'started': time.time(), 'status': 'preflight', 'evaluation_version': 3,
              'script_sha256': file_hash(__file__), 'historical_helper_sha256': HISTORICAL_SCRIPT_SHA,
              'inference_source_sha256': file_hash(ROOT / 'simple_inference_engine.py'),
              'regression_source_sha256': file_hash(ROOT / 'scripts/smoke_dfm12_identity.py'),
              'heldout_root': str(args.heldout_root.resolve()),
              'heldout_manifest_sha256': args.heldout_manifest_sha256, 'dataset_policy': policy,
              'limitations': historical.LIMITATIONS, 'batch_size': 1, 'non_ema': True, 'wandb': False,
              'identity_priming': False, 'history_policy': 'model-generated assistant turns only; reset per case/checkpoint',
              'max_seconds': args.max_seconds, 'per_checkpoint_seconds': args.max_seconds / 2,
              'budget_note': 'SIGALRM bounds Python decoding; in-flight CUDA/native calls must return first. Cleanup is additional.',
              'max_context': args.max_context, 'max_new_tokens': args.max_new_tokens,
              'target_lengths': historical.tokenizer_lengths(cases, manifest), 'cases': cases,
              'runs': [{'label': label, 'checkpoint': str(path.resolve()), 'tag': tag,
                        'status': 'planned', 'conversations': []} for label, path, tag in (
                            ('previous', args.previous_checkpoint, args.previous_tag),
                            ('continued', args.checkpoint, args.tag))]}
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output, report)
    if args.preflight_only:
        print(json.dumps({'conversations': len(cases), 'turns_per_checkpoint': sum(len(c['users']) for c in cases),
                          'target_lengths': report['target_lengths'], 'dataset_policy': policy,
                          'model_loaded': False, 'review_required': True}, indent=2))
        return 0
    try:
        result = run_models(args, report, manifest)
        report['completed'] = time.time()
        return result
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save(args.output, report)


if __name__ == '__main__':
    raise SystemExit(main())
