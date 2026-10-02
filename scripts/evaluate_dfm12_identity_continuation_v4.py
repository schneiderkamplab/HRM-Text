#!/usr/bin/env python3
"""Eight-GPU whole-conversation identity comparison; external launch only.

CPU --preflight-only never probes GPUs or imports inference. Two checkpoint
phases each use eight independent spawn workers and a dynamic conversation
queue. Exit 0 is operational completion, NEVER semantic acceptance.
"""
import argparse
import copy
import gc
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import atomic, digest, file_hash, load, write_json
from scripts import evaluate_dfm12_identity_continuation_v3 as v3

historical = v3.historical
V3_SHA = 'fe8e8d6b6fe1a7758f900b25c61263a918988ff79c856df6d1d9684886f3b4e1'
V3_DATA = ROOT / 'data/dfm12/identity-repair-da-en-20260926-v3'
V3_DATA_SHA = 'af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1'
GPUS = tuple(range(8))


def verify_helpers():
    for path, sha in ((v3.__file__, V3_SHA),
                      (historical.__file__, v3.HISTORICAL_SCRIPT_SHA),
                      (ROOT / 'scripts/smoke_dfm12_identity.py', v3.REGRESSION_SCRIPT_SHA)):
        if file_hash(path) != sha:
            raise ValueError('Frozen helper changed: ' + str(path))


def correction_provenance(spec, requests, schema):
    """Reconstruct the v4 builder's complete native records, independently."""
    result = {}
    families = spec['heldout']
    if len(families) != 25 or len({c['id'] for c in families}) != 25:
        raise ValueError('Expected 25 uniquely named fresh correction families')
    for family in families:
        if len(family['questions']) != 2:
            raise ValueError('Expected two question variants per family')
        for question in family['questions']:
            turns = [(question, family['answer'])]
            if 'followup' in family:
                turns.append((family['followup']['question'], family['followup']['answer']))
            for lang in ('da', 'en'):
                messages = []
                for prompt, key in turns:
                    messages.extend([dict(role='user', content=prompt[lang]),
                                     dict(role='assistant', content=requests[key]['brief'][lang])])
                identifier = digest(dict(schema=schema, language=lang, messages=messages))
                row = dict(id=identifier, language=lang, messages=messages, task='identity',
                           parent_pair_id=None, direction='native')
                if identifier in result:
                    raise ValueError('Duplicate reconstructed heldout')
                result[identifier] = dict(id=identifier, language=lang, family=family['id'],
                                         record_sha256=digest(row), turn_references=[
                                             dict(requests=[key], mode='brief') for _, key in turns])
    return result


def sealed_source(manifest, relative, fallback):
    """V4 external source pins must match the immutable v3 snapshot we read."""
    expected_path = str((ROOT / relative).resolve())
    entries = [p for p in manifest['pins'] if p['path'] == expected_path]
    if len(entries) != 1 or entries[0]['sha256'] != file_hash(fallback):
        raise ValueError('Missing/mismatched inherited source pin: ' + relative)
    return Path(fallback)


def load_cases(root, sha, spec_relative):
    """Validate fresh bindings, roles and disjointness from BOTH old holdouts."""
    root = Path(root).resolve()
    manifest, files = v3.pinned_manifest(root, sha)
    if manifest.get('profile') != 'xl-full-bp' or manifest.get('enable_thinking') is not False:
        raise ValueError('Expected non-thinking XL full-backprop profile')
    previous, old_manifest, _ = v3.load_cases(
        V3_DATA, V3_DATA_SHA, 'metadata/identity_repair_expansion.yaml')
    oldest, _ = historical.load_cases(v3.DEVELOPMENT_ROOT, v3.DEVELOPMENT_SHA)
    cases = copy.deepcopy(previous)
    for case in cases[16:]:
        case['suite'] = 'development_v3'
    forbidden_ids = {c['id'] for c in previous + oldest}
    forbidden_questions = {historical.normalize(q) for c in previous + oldest for q in c['users']}
    # Corrections can remove/reword training turns; their old wording is not fresh.
    for lang in ('da', 'en'):
        for row in historical.gzip_rows(V3_DATA / old_manifest['languages'][lang]['input']):
            forbidden_ids.add(row['id'])
            forbidden_questions.update(v3.question_keys(row))
    if root in (V3_DATA.resolve(), Path(v3.DEVELOPMENT_ROOT).resolve()) or sha in (V3_DATA_SHA, v3.DEVELOPMENT_SHA):
        raise ValueError('Old heldout is development data, not fresh evaluation')
    correction_schema = manifest.get('schema') == 'dfm12-curated-identity-correction-v4'
    facts = (v3.pinned_file(root, files, 'metadata/identity_facts.yaml')
             if 'metadata/identity_facts.yaml' in files else
             sealed_source(manifest, 'dfm12/identity_facts.yaml', V3_DATA / 'metadata/identity_facts.yaml')
             if correction_schema else v3.pinned_file(root, files, 'metadata/identity_facts.yaml'))
    if file_hash(facts) != file_hash(V3_DATA / 'metadata/identity_facts.yaml'):
        raise ValueError('Facts drift requires separate contract review')
    spec = yaml.safe_load(v3.pinned_file(root, files, spec_relative).read_text())
    requests = spec.get('requests')
    if requests is None:
        if spec.get('version') != 4 or manifest.get('schema') != 'dfm12-curated-identity-correction-v4':
            raise ValueError('Unknown frozen answer-bank schema')
        bank = (v3.pinned_file(root, files, 'metadata/identity_repair_expansion.yaml')
                if 'metadata/identity_repair_expansion.yaml' in files else
                sealed_source(manifest, 'dfm12/identity_repair_expansion.yaml',
                              V3_DATA / 'metadata/identity_repair_expansion.yaml'))
        if file_hash(bank) != file_hash(V3_DATA / 'metadata/identity_repair_expansion.yaml'):
            raise ValueError('Inherited answer bank changed')
        requests = copy.deepcopy(yaml.safe_load(bank.read_text())['requests'])
        for key, answer in spec.get('answers', {}).items():
            if set(answer) != {'da', 'en'}:
                raise ValueError('Expected bilingual v4 answer override')
            requests[key] = {'brief': answer}
        if spec['facts_sha256'] != file_hash(facts):
            raise ValueError('Correction spec facts pin mismatch')
    for key in ('template', 'tokenizer'):
        if (manifest[key]['sha256'] != old_manifest[key]['sha256']
                or file_hash(manifest[key]['path']) != manifest[key]['sha256']):
            raise ValueError('Raw training asset changed: ' + key)
    for lang in ('da', 'en'):
        relative = manifest['languages'][lang]['input']
        if not relative.startswith('inputs/') or not relative.endswith('.jsonl.gz'):
            raise ValueError('Expected explicit native training shard')
        for row in historical.gzip_rows(v3.pinned_file(root, files, relative)):
            forbidden_ids.add(row['id'])
            forbidden_questions.update(v3.question_keys(row))
    provenance = {}
    for row in historical.gzip_rows(v3.pinned_file(root, files, 'metadata/provenance.jsonl.gz')):
        if row['split'] == 'heldout':
            if row['id'] in provenance:
                raise ValueError('Duplicate heldout provenance')
            provenance[row['id']] = row
    if correction_schema:
        reconstructed = correction_provenance(spec, requests, manifest['schema'])
        if provenance and {k: v['record_sha256'] for k, v in provenance.items()} != {
                k: v['record_sha256'] for k, v in reconstructed.items()}:
            raise ValueError('Heldout provenance differs from frozen correction spec')
        provenance = reconstructed
    heldout, seen = {}, set()
    for lang in ('da', 'en'):
        selected = []
        for row in historical.gzip_rows(v3.pinned_file(root, files, f'heldout/{lang}/test.jsonl.gz')):
            messages = row['messages']
            if (row['language'] != lang or not 2 <= len(messages) <= 8 or len(messages) % 2
                    or any(m['role'] != ('user' if i % 2 == 0 else 'assistant')
                           or not isinstance(m['content'], str) or not m['content'].strip()
                           for i, m in enumerate(messages))):
                raise ValueError('Expected 1..4 native alternating pairs without system facts')
            if row['id'] in forbidden_ids or row['id'] in seen or v3.question_keys(row) & forbidden_questions:
                raise ValueError('Duplicate or training/development heldout overlap')
            entry = provenance[row['id']]
            refs = entry['turn_references']
            if (entry['language'] != lang or entry['record_sha256'] != digest(row)
                    or len(refs) != len(messages) // 2):
                raise ValueError('Record/turn provenance mismatch')
            for i, ref in enumerate(refs):
                forms = ref.get('answer_forms')
                if forms is None:
                    if ref.get('mode') not in ('brief', 'contrast'):
                        raise ValueError('Unknown target binding')
                    forms = [ref['mode']] * len(ref['requests'])
                if not ref['requests'] or len(forms) != len(ref['requests']):
                    raise ValueError('Invalid target binding')
                expected = '\n\n'.join(requests[key][form][lang]
                                       for key, form in zip(ref['requests'], forms))
                if expected != messages[2 * i + 1]['content']:
                    raise ValueError('Target differs from frozen request bindings')
            seen.add(row['id'])
            selected.append(dict(id=row['id'], suite='heldout', language=lang,
                                 family=entry['family'], source_record_sha256=digest(row),
                                 users=[m['content'] for m in messages[::2]],
                                 expected_targets=[m['content'] for m in messages[1::2]],
                                 requests=[r['requests'] for r in refs]))
        if len(selected) != 50:
            raise ValueError('Require 50 fresh heldouts per language')
        heldout[lang] = selected
    if seen != set(provenance):
        raise ValueError('Missing/extra heldout provenance')
    for pair in zip(heldout['da'], heldout['en']):
        cases.extend(pair)
    policy = dict(fresh_heldout_root=str(root), fresh_manifest_sha256=sha,
                  frozen_request_spec=spec_relative, fresh_conversations_per_language=50,
                  development_roots=[str(v3.DEVELOPMENT_ROOT), str(V3_DATA)],
                  development_manifest_sha256=[v3.DEVELOPMENT_SHA, V3_DATA_SHA],
                  old_heldout_status='v3_replayed_as_development_only_v2_not_evaluated',
                  v3_development_conversations=100,
                  development_note='Previously observed failures; not independent heldout evidence and may inform correction training',
                  heldout_provenance=('exact_native_records_reconstructed_from_sealed_correction_spec_and_pinned_v3_bank'
                                      if correction_schema else 'manifest_pinned_turn_provenance'),
                  regression_status='fixed_previous_16_development_regressions',
                  split_check='IDs and normalized full turns against current/inherited-v3 training and both old holdouts; not semantic paraphrase leakage detection')
    return cases, manifest, policy


def gpu_status(gpu, allow_occupied=False):
    common = ['nvidia-smi', f'--id={gpu}']
    def query(fields):
        return subprocess.run(common + fields + ['--format=csv,noheader,nounits'],
                              capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    index, free, utilization = map(int, query(['--query-gpu=index,memory.free,utilization.gpu']).split(','))
    pids = {int(line.strip()) for line in query(['--query-compute-apps=pid']).splitlines() if line.strip()}
    if index != gpu or (not allow_occupied and pids - {os.getpid()}):
        raise RuntimeError(f'GPU {gpu} occupied by another compute process; refusing to compete')
    return dict(physical_gpu=index, free_mib=free, utilization=utilization, compute_pids=sorted(pids))


def worker_environment(gpu):
    if gpu not in GPUS:
        raise ValueError('Physical GPU must be 0..7')
    os.environ.update(CUDA_VISIBLE_DEVICES=str(gpu), CUDA_DEVICE_ORDER='PCI_BUS_ID',
                      WANDB_MODE='disabled', WANDB_DISABLED='true',
                      TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    for key in ('RANK', 'LOCAL_RANK', 'WORLD_SIZE', 'LOCAL_WORLD_SIZE', 'GROUP_RANK',
                'ROLE_RANK', 'ROLE_WORLD_SIZE', 'MASTER_ADDR', 'MASTER_PORT'):
        os.environ.pop(key, None)
    for key in list(os.environ):
        if key.startswith(('TORCHELASTIC_', 'PET_', 'PMI_', 'PMIX_', 'OMPI_COMM_WORLD_')):
            os.environ.pop(key, None)


def validate_conversation(case, conversation, max_tokens, final):
    for key in ('id', 'suite', 'language', 'family'):
        if conversation.get(key) != case.get(key):
            raise ValueError('Case identity mismatch')
    turns = conversation['turns']
    if len(turns) > len(case['users']) or (final and len(turns) != len(case['users'])):
        raise ValueError('Missing/extra turn coverage')
    history = []
    for i, turn in enumerate(turns):
        history.append({'role': 'user', 'content': case['users'][i]})
        if (turn['turn'] != i + 1 or turn['user'] != case['users'][i]
                or turn['expected_target'] != case['expected_targets'][i]
                or turn['requests'] != case['requests'][i] or turn['prompt_messages'] != history):
            raise ValueError('Turn binding or generated-history mismatch')
        v3.validate_generation(turn, max_tokens)
        if (not isinstance(turn.get('rendered_prompt'), str) or not turn['rendered_prompt']
                or not isinstance(turn.get('prompt_token_ids'), list) or not turn['prompt_token_ids']
                or any(type(i) is not int or i < 0 for i in turn['prompt_token_ids'])):
            raise ValueError('Missing/invalid raw prompt receipt')
        history.append({'role': 'assistant', 'content': turn['response']})
    permitted = [history]
    if not final and len(turns) < len(case['users']):
        permitted.append(history + [{'role': 'user', 'content': case['users'][len(turns)]}])
    if conversation['generated_history'] not in permitted or (final and conversation['status'] != 'complete'):
        raise ValueError('Final generated history or completion mismatch')


def merge_shards(report, run, phase_dir, final=False):
    """One coordinator reads atomic worker files; duplicate IDs fail closed."""
    found = {}
    for gpu in GPUS:
        directory = phase_dir / f'gpu-{gpu}'
        for path in sorted(directory.glob('case-*.json')):
            shard = load(path)
            index = shard['case_index']
            if type(index) is not int or not 0 <= index < len(report['cases']):
                raise ValueError('Unknown shard case index')
            if (shard['contract_sha256'] != report['contract_sha256'] or shard['gpu'] != gpu
                    or shard['label'] != run['label'] or shard['tag'] != run['tag']
                    or shard['checkpoint'] != run['checkpoint']
                    or shard['checkpoint_pins'] != run['checkpoint_pins']
                    or path.name != f'case-{index:03d}.json'):
                raise ValueError('Shard provenance/checkpoint mismatch')
            if index in found:
                raise ValueError('Duplicate conversation shard')
            conversation = shard['conversation']
            validate_conversation(report['cases'][index], conversation, report['max_new_tokens'], final)
            for turn in conversation['turns']:
                if len(turn['prompt_token_ids']) + report['max_new_tokens'] >= report['max_context']:
                    raise ValueError('Full generated history exceeds context contract')
                turn['heuristics'] = v3.review_heuristic(turn)
            found[index] = conversation
    if final and set(found) != set(range(len(report['cases']))):
        raise ValueError('Incomplete conversation coverage')
    run['conversations'] = [found[i] for i in sorted(found)]


def save(output, report):
    """Keep raw partial evidence; legacy statistics require nonempty groups."""
    report.update(review_required=True, identity_positive=None, full_suite_approved=None,
                  operational_success=report['status'] in v3.COMPLETED)
    snapshot = dict(report, runs=[dict(run, conversations=[c for c in run['conversations'] if c['turns']])
                                 for run in report['runs']])
    summary = historical.summarize(snapshot)
    summary.update(review_required=True, identity_positive=None, full_suite_approved=None,
                   weight_mode='EMA' if report.get('ema', False) else 'non-EMA',
                   operational_success=report['operational_success'], dataset_policy=report['dataset_policy'],
                   empty_in_progress_conversations={run['label']: sum(not c['turns'] for c in run['conversations'])
                                                    for run in report['runs']},
                   exit_policy='0 = operational completion, never model acceptance; 3 = incomplete budget; errors fail')
    write_json(output / 'responses.json', report)
    write_json(output / 'summary.json', summary)
    text = ['# Identity Continuation Comparison', '', historical.LIMITATIONS, '',
            ('EMA' if report.get('ema', False) else 'Non-EMA')
            + ', greedy, batch one per GPU. No system facts or gold assistant histories.',
            'Empty in-progress conversations remain incomplete evidence, not successes.', '']
    for case in report['cases']:
        text += [f"## {case['suite']} / {case['language']} / {case['id']}", '']
        for run in report['runs']:
            c = next((c for c in run['conversations'] if c['id'] == case['id']), None)
            text += [f"### {run['label']}: {run['tag']}", '', f"Checkpoint: `{run['checkpoint']}`", '',
                     'Conversation status: ' + (c['status'] if c else 'not yet evaluated'), '']
            turns = c['turns'] if c else []
            for turn in turns:
                text += [f"#### Turn {turn['turn']}", '', '**User**', '', turn['user'], '',
                         '**Generated assistant**', '', turn['response'], '', '**Expected target (not supplied)**', '',
                         turn['expected_target'], '', f"Finish: {turn['finish_reason']}; tokens: {turn['generated_token_count']}",
                         '', 'Limited heuristic: ' + json.dumps(turn['heuristics'], ensure_ascii=False), '']
            for i in range(len(turns), len(case['users'])):
                text += [f'#### Turn {i + 1} (not generated)', '', '**User**', '', case['users'][i], '',
                         '**Expected target (not supplied)**', '', case['expected_targets'][i], '']
    with atomic(output / 'responses.md') as handle:
        handle.write('\n'.join(text))
    with atomic(output / 'summary.md') as handle:
        handle.write('# Identity Comparison: Parent Review Required\n\n' + historical.LIMITATIONS
                     + '\n\nEmpty claimed conversations are excluded only from statistics, not raw evidence.\n\n```json\n'
                     + json.dumps(summary, ensure_ascii=False, indent=2) + '\n```\n')


def task_order(cases):
    # Long histories first reduces the tail; worker assignment never changes prompts.
    return sorted(range(len(cases)), key=lambda i: (-len(cases[i]['users']), i))


def finish_report(report):
    if not report.get('latest_only', False):
        return v3.finish_report(report)
    if len(report['runs']) != 1 or report['runs'][0]['label'] != 'continued':
        raise ValueError('Latest-only requires exactly one continued checkpoint')
    run = report['runs'][0]
    if run['status'] == 'budget_exhausted':
        report['status'] = 'incomplete_budget'
        return 3
    if (run['status'] != 'complete'
            or [c['id'] for c in run['conversations']] != [c['id'] for c in report['cases']]):
        raise ValueError('Incomplete or mismatched conversation coverage')
    for case, conversation in zip(report['cases'], run['conversations']):
        validate_conversation(case, conversation, report['max_new_tokens'], final=True)
    lengths = any(t['truncated'] for c in run['conversations'] for t in c['turns'])
    report['status'] = 'complete_with_length_stops' if lengths else 'complete'
    return 0


def checkpoint_pins(run):
    from scripts.stop_training_at_complete_checkpoint import complete
    root, tag = Path(run['checkpoint']), run['tag']
    if not complete(root, tag):
        raise ValueError('Checkpoint incomplete: ' + str(root / tag))
    return {relative: file_hash(root / relative) for relative in (
        f'checkpoint_state_{tag}.json', f'fsdp2_{tag}/.metadata', 'all_config.yaml', 'train_metadata.yaml')}


def ema_source(checkpoint, tag):
    """Inspect only CPU DCP metadata; never accept the loader's silent EMA fallback."""
    from torch.distributed.checkpoint import FileSystemReader
    root = Path(checkpoint)
    decay = yaml.safe_load((root / 'all_config.yaml').read_text()).get('ema')
    if not isinstance(decay, (int, float)) or not 0 < decay < 1:
        raise ValueError('EMA requested but checkpoint configuration has no valid EMA')
    metadata = FileSystemReader(root / f'fsdp2_{tag}').read_metadata()
    entries = {}
    for key, route in metadata.planner_data.items():
        if len(route) == 4 and route[:2] == ('optim', 'state') and route[-1] == 'param_ema':
            tensor = metadata.state_dict_metadata[key]
            if route[2] in entries:
                raise ValueError('Duplicate EMA parameter')
            entries[route[2]] = tensor
    if not entries:
        raise ValueError('EMA requested but checkpoint has no EMA tensors')
    return decay, entries


def verify_loaded_ema(checkpoint, run):
    """Read EMA alone on CPU and verify every inference parameter after casting."""
    import torch
    import torch.distributed.checkpoint as dcp
    decay, entries = ema_source(run['checkpoint'], run['tag'])
    parameters = {name: value for name, value in checkpoint.model.named_parameters() if value.requires_grad}
    if set(parameters) != set(entries):
        raise ValueError('EMA parameter coverage mismatch')
    state = {}
    for name, param in parameters.items():
        entry = entries[name]
        if tuple(param.shape) != tuple(entry.size):
            raise ValueError('EMA parameter shape mismatch: ' + name)
        state[name] = {'param_ema': torch.empty(entry.size, dtype=entry.properties.dtype, device='cpu')}
    dcp.load({'optim': {'state': state}},
             checkpoint_id=str(Path(run['checkpoint']) / f"fsdp2_{run['tag']}"), no_dist=True)
    source_hash, loaded_hash = hashlib.sha256(), hashlib.sha256()
    count = 0
    for name in sorted(parameters):
        expected = state[name]['param_ema']
        actual = parameters[name].detach().cpu()
        if not torch.isfinite(expected).all() or not torch.equal(actual, expected.to(actual.dtype)):
            raise ValueError('Loaded parameter does not equal checkpoint EMA: ' + name)
        for hasher, tensor in ((source_hash, expected), (loaded_hash, actual)):
            hasher.update((name + ':' + str(tensor.dtype) + ':' + str(tuple(tensor.shape))).encode())
            hasher.update(tensor.contiguous().view(torch.uint8).numpy().tobytes())
        count += expected.numel()
    return dict(verified=True, decay=decay, tensor_count=len(parameters), parameter_count=count,
                source_ema_tensor_sha256=source_hash.hexdigest(),
                loaded_inference_tensor_sha256=loaded_hash.hexdigest(),
                method='All trainable parameters exactly equal independently loaded CPU EMA after inference dtype cast')


def load_for_run(run, use_ema, loader=None):
    if loader is None:
        from simple_inference_engine import inference_load_checkpoint
        loader = inference_load_checkpoint
    if use_ema:
        ema_source(run['checkpoint'], run['tag'])
    checkpoint = loader(run['checkpoint'], None, use_ema, ckpt_tag=run['tag'])
    verification = verify_loaded_ema(checkpoint, run) if use_ema else None
    return checkpoint, verification


def runtime_asset_binding(checkpoint, manifest):
    """CPU-only evidence from the real baseline; no model/checkpoint tensors loaded."""
    path = Path(checkpoint) / 'train_metadata.yaml'
    metadata = yaml.safe_load(path.read_text())
    info = metadata['tokenizer_info']
    if info.get('template_mode') != 'jinja_chat_template' or info.get('enable_thinking') is not False:
        raise ValueError('Baseline metadata must bind raw non-thinking template')
    assets = {}
    for key, field in (('tokenizer', 'tokenizer_path'), ('template', 'chat_template_path')):
        asset = Path(info[field])
        if not asset.is_absolute():
            if info.get('tokenizer_path_base') != 'repo_root':
                raise ValueError('Unresolved relative runtime tokenizer asset')
            asset = ROOT / asset
        sha = file_hash(asset)
        if sha != manifest[key]['sha256']:
            raise ValueError('Runtime metadata asset does not match manifest: ' + key)
        assets[key] = dict(path=str(asset.resolve()), sha256=sha)
    return dict(train_metadata_path=str(path.resolve()), train_metadata_sha256=file_hash(path),
                vocab_size=metadata['vocab_size'], tokenizer_info=info, assets=assets,
                interpretation='Current XL runtime assets, distinct from historical original HRM-Text BPE claims')


def required_free_mib(report, total_mib=None):
    default = 104 * 1024 if report.get('ema', False) else 32768
    if 'required_free_mib' not in report:
        return default
    cap = report['allocator_limit_gib_per_worker'] * 1024
    reserve = report.get('non_torch_reserve_mib', 0)
    required = report['required_free_mib']
    if (report.get('resource_mode') != 'manual_co_resident' or not report.get('ema')
            or not 0 < cap <= 86 * 1024 or reserve < 4096
            or required < cap + reserve + 8192
            or (total_mib is not None and cap + reserve > total_mib * 0.5)):
        raise ValueError('Unsafe co-resident memory override')
    return required


def worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, phase_dir, deadline):
    worker_environment(gpu)
    directory = Path(phase_dir) / f'gpu-{gpu}'
    directory.mkdir(parents=True, exist_ok=False)
    state = dict(gpu=gpu, pid=os.getpid(), status='starting', label=run['label'], tag=run['tag'],
                 contract_sha256=report['contract_sha256'], completed_cases=[])
    conversation, shard_path, envelope, checkpoint = None, None, None, None
    torch = None
    def gpu_snapshot():
        if report.get('resource_mode') == 'manual_co_resident':
            return gpu_status(gpu, allow_occupied=True)
        return gpu_status(gpu)
    old_handler = signal.signal(signal.SIGALRM, historical.budget_expired)
    def persist():
        if envelope is not None:
            write_json(shard_path, envelope)
        write_json(directory / 'worker.json', state)
    try:
        signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.monotonic()))
        persist()
        verify_helpers()
        if (file_hash(__file__) != report['script_sha256']
                or file_hash(ROOT / 'simple_inference_engine.py') != report['inference_source_sha256']):
            raise ValueError('Evaluator/inference source changed after preflight')
        if checkpoint_pins(run) != run['checkpoint_pins']:
            raise ValueError('Checkpoint changed after parent validation')
        import torch
        torch.set_num_threads(2)
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError('Worker must see exactly one CUDA GPU')
        before = gpu_snapshot()
        required = required_free_mib(report, torch.cuda.get_device_properties(0).total_memory / 1024**2)
        if before['free_mib'] < required:
            raise RuntimeError(f'Need {required} MiB free before load')
        torch.cuda.set_per_process_memory_fraction(report['allocator_limit_gib_per_worker'] * 1024**3
                                                  / torch.cuda.get_device_properties(0).total_memory, 0)
        state.update(status='loading', gpu_before=before)
        persist()
        with load_slots:
            if cancelled.is_set():
                raise RuntimeError('Evaluation phase cancelled')
            if gpu_snapshot()['free_mib'] < required:
                raise RuntimeError('Insufficient real headroom at checkpoint load')
            checkpoint, ema_verification = load_for_run(run, report.get('ema', False))
        info = checkpoint.tokenizer_info
        if info.get('template_mode') != 'jinja_chat_template' or info.get('enable_thinking') is not False:
            raise ValueError('Expected raw non-thinking template')
        for key, field in (('template', 'chat_template_path'), ('tokenizer', 'tokenizer_path')):
            if file_hash(info[field]) != manifest[key]['sha256']:
                raise ValueError('Checkpoint asset mismatch: ' + key)
        if checkpoint.tokenizer.chat_template != Path(info['chat_template_path']).read_text():
            raise ValueError('Loaded template differs from training asset')
        state.update(status='running', tokenizer_info=info, checkpoint_pins=run['checkpoint_pins'],
                     ema=report.get('ema', False), ema_verification=ema_verification)
        index = initial
        while index is not None:
            if cancelled.is_set():
                raise RuntimeError('Evaluation phase cancelled')
            case = report['cases'][index]
            conversation = dict(id=case['id'], suite=case['suite'], language=case['language'],
                                family=case.get('family'), turns=[], generated_history=[], status='incomplete')
            shard_path = directory / f'case-{index:03d}.json'
            if shard_path.exists():
                raise ValueError('Refusing to overwrite a conversation shard')
            envelope = dict(contract_sha256=report['contract_sha256'], checkpoint=run['checkpoint'],
                            checkpoint_pins=run['checkpoint_pins'], label=run['label'], tag=run['tag'],
                            gpu=gpu, case_index=index, conversation=conversation)
            persist()
            def generate(messages):
                if cancelled.is_set():
                    raise RuntimeError('Evaluation phase cancelled')
                if gpu_snapshot()['free_mib'] < 8192:
                    raise RuntimeError('Need 8 GiB free before generation')
                return v3.validate_generation(historical.generate_turn(
                    checkpoint, messages, report['max_context'], report['max_new_tokens']), report['max_new_tokens'])
            historical.run_conversation(case, generate, conversation, persist)
            state['completed_cases'].append(index)
            state['peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 1024**2
            persist()
            try:
                index = tasks.get(timeout=0.2)
            except queue.Empty:
                index = None
        state['status'] = 'complete'
    except historical.EvaluationBudgetExceeded as exc:
        state.update(status='budget_exhausted', error=str(exc))
        cancelled.set()
    except BaseException as exc:
        state.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        if isinstance(exc, v3.InvalidGeneration):
            state['invalid_generation'] = exc.output
        cancelled.set()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        persist()
        checkpoint = None
        gc.collect()
        if torch is not None and torch.cuda.is_initialized():
            torch.cuda.empty_cache()


def run_phase(report, run, manifest, output, seconds):
    phase_dir = output / 'shards' / run['label']
    phase_dir.mkdir(parents=True, exist_ok=False)
    context = mp.get_context('spawn')
    tasks, cancelled = context.Queue(), context.Event()
    load_slots = context.BoundedSemaphore(2)
    order = task_order(report['cases'])
    if len(order) < len(GPUS):
        raise ValueError('Need at least eight conversations')
    for index in order[8:]:
        tasks.put(index)
    deadline = time.monotonic() + seconds
    processes = []
    interrupted = False
    cancel_deadline = None
    try:
        for gpu in GPUS:
            process = context.Process(target=worker, args=(gpu, order[gpu], tasks, cancelled, load_slots,
                                                          report, run, manifest, phase_dir, deadline))
            process.start()
            processes.append(process)
        run['status'] = 'running'
        while any(p.is_alive() for p in processes):
            merge_shards(report, run, phase_dir)
            save(output, report)
            if any(p.exitcode not in (None, 0) for p in processes):
                cancelled.set()
            if cancelled.is_set() and cancel_deadline is None:
                cancel_deadline = time.monotonic() + 15
            if time.monotonic() > deadline + 15:
                interrupted = True
                break
            if cancel_deadline is not None and time.monotonic() > cancel_deadline:
                break
            time.sleep(1)
    finally:
        # Reap ONLY processes created by this evaluator, never external training.
        cancelled.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
        tasks.cancel_join_thread()
        tasks.close()
    states = []
    for gpu in GPUS:
        path = phase_dir / f'gpu-{gpu}' / 'worker.json'
        states.append(load(path) if path.exists() else dict(gpu=gpu, status='missing_worker_receipt'))
    run['workers'] = states
    for gpu, state in zip(GPUS, states):
        if state['status'] != 'missing_worker_receipt' and (
                state['gpu'] != gpu or state['label'] != run['label'] or state['tag'] != run['tag']
                or state['contract_sha256'] != report['contract_sha256']):
            raise ValueError('Worker receipt provenance mismatch')
    failed = any(s['status'] != 'complete' for s in states) or any(p.exitcode != 0 for p in processes)
    if report.get('ema', False) and any(
            s.get('ema') is not True or not (s.get('ema_verification') or {}).get('verified') for s in states):
        failed = True
    budget = interrupted or any(s['status'] == 'budget_exhausted' for s in states)
    merge_shards(report, run, phase_dir, final=not failed and not budget)
    if budget:
        run['status'] = 'budget_exhausted'
        report['status'] = 'incomplete_budget'
        return 3
    if failed:
        run['status'] = 'failed'
        report['status'] = 'failed'
        return 1
    run['status'] = 'complete'
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--previous-checkpoint', type=Path,
                        default=ROOT / 'checkpoints/dfm12/XL-identity-expanded-from-step2879261')
    parser.add_argument('--previous-tag', default='step_2880261')
    parser.add_argument('--tag', default='step_2881261')
    parser.add_argument('--heldout-root', type=Path, required=True)
    parser.add_argument('--heldout-manifest-sha256', required=True)
    parser.add_argument('--heldout-spec', required=True)
    parser.add_argument('--gpus', default='0,1,2,3,4,5,6,7')
    parser.add_argument('--max-new-tokens', type=int, default=512)
    parser.add_argument('--max-context', type=int, default=4096)
    parser.add_argument('--max-seconds', type=int, default=3600)
    parser.add_argument('--preflight-only', action='store_true')
    parser.add_argument('--ema', action='store_true', help='Load and independently verify checkpoint EMA weights')
    parser.add_argument('--latest-only', action='store_true', help='Evaluate only --checkpoint/--tag')
    parser.add_argument('--heldout-only', action='store_true', help='Evaluate only fresh heldout conversations')
    args = parser.parse_args(argv)
    if args.gpus != '0,1,2,3,4,5,6,7':
        parser.error('Exactly eight physical GPUs 0,1,2,3,4,5,6,7 required')
    if (args.max_seconds < 2 or not 1 <= args.max_new_tokens <= 1024
            or not args.max_new_tokens < args.max_context <= 4096):
        parser.error('Invalid runtime/context/output bounds')
    if any(not re.fullmatch(r'(?:ephemeral_)?step_\d+', tag) for tag in (args.tag, args.previous_tag)):
        parser.error('Explicit checkpoint step tags required')
    if not args.latest_only and args.tag == args.previous_tag and args.checkpoint.resolve() == args.previous_checkpoint.resolve():
        parser.error('Comparison requires distinct checkpoints')
    os.chdir(ROOT)
    verify_helpers()
    cases, manifest, policy = load_cases(args.heldout_root, args.heldout_manifest_sha256, args.heldout_spec)
    if args.heldout_only:
        cases = [case for case in cases if case['suite'] == 'heldout']
    phases = [('continued', args.checkpoint, args.tag)] if args.latest_only else [
        ('previous', args.previous_checkpoint, args.previous_tag), ('continued', args.checkpoint, args.tag)]
    if args.ema:
        for _, path, tag in phases:
            ema_source(path, tag)
    report = dict(started=time.time(), status='preflight', evaluation_version=4,
                  script_sha256=file_hash(__file__), v3_helper_sha256=V3_SHA,
                  historical_helper_sha256=v3.HISTORICAL_SCRIPT_SHA,
                  inference_source_sha256=file_hash(ROOT / 'simple_inference_engine.py'),
                  regression_source_sha256=v3.REGRESSION_SCRIPT_SHA,
                  heldout_root=str(args.heldout_root.resolve()), heldout_manifest_sha256=args.heldout_manifest_sha256,
                  dataset_policy=policy, limitations=historical.LIMITATIONS, cases=cases,
                  non_ema=not args.ema, ema=args.ema, latest_only=args.latest_only,
                  heldout_only=args.heldout_only, wandb=False, identity_priming=False, batch_size=1,
                  history_policy='model-generated assistant turns; reset per whole conversation/checkpoint',
                  parallelism=f'eight single-GPU spawn workers; {len(phases)} checkpoint phases; dynamic whole-conversation queue',
                  gpus=list(GPUS), concurrent_checkpoint_loads=2, allocator_limit_gib_per_worker=96 if args.ema else 24,
                  max_seconds=args.max_seconds, per_checkpoint_seconds=args.max_seconds / len(phases),
                  max_context=args.max_context, max_new_tokens=args.max_new_tokens,
                  budget_note='Per-phase deadline includes loading; 15s grace, then terminate/reap owned workers only; no coverage autopass.',
                  target_lengths=historical.tokenizer_lengths(cases, manifest),
                  runtime_asset_binding=runtime_asset_binding(phases[0][1], manifest),
                  runs=[dict(label=label, checkpoint=str(path.resolve()), tag=tag, status='planned', conversations=[])
                        for label, path, tag in phases])
    report['contract_sha256'] = digest(report)
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output, report)
    if args.preflight_only:
        print('CPU preflight:', len(cases), 'conversations;', sum(len(c['users']) for c in cases),
              'turns per checkpoint; no GPU actions', flush=True)
        return 0
    try:
        for gpu in GPUS:
            required = 104 * 1024 if args.ema else 32768
            if gpu_status(gpu)['free_mib'] < required:
                raise RuntimeError(f'GPU {gpu} needs {required} MiB free before evaluation')
        for run in report['runs']:
            run['checkpoint_pins'] = checkpoint_pins(run)
        report['status'] = 'running'
        for run in report['runs']:
            result = run_phase(report, run, manifest, args.output, args.max_seconds / len(phases))
            if result:
                return result
        result = finish_report(report)
        report['completed'] = time.time()
        return result
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save(args.output, report)
        write_json(args.output / 'completion.json', dict(status=report['status'],
                   responses_sha256=file_hash(args.output / 'responses.json'),
                   review_required=True, identity_positive=None, full_suite_approved=None))


if __name__ == '__main__':
    raise SystemExit(main())
