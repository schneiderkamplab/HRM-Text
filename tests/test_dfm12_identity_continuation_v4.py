import copy
import gzip
import json
import os
from pathlib import Path
import queue

import pytest
import yaml

from dfm12.io import digest, file_hash, load, write_json
from scripts import evaluate_dfm12_identity_continuation_v4 as evaluation


def case(i):
    return dict(id=f'case-{i}', suite='heldout', language='da' if i % 2 == 0 else 'en', family='fixture',
                users=[f'Question {i}', f'Follow-up {i}'],
                expected_targets=['GOLD NEVER PRIMED', 'SECOND GOLD'], requests=[['scratch'], ['team']])


def generation(messages, stop='eos'):
    return dict(response='Generated answer ' + str(len(messages)), rendered_prompt=repr(messages),
                prompt_token_ids=[1, 2], generated_token_ids=[3] * (512 if stop == 'length' else 2),
                generated_token_count=512 if stop == 'length' else 2,
                finish_reason=stop, truncated=stop == 'length', seconds=0.01)


def conversation(c, stop='eos'):
    return evaluation.historical.run_conversation(c, lambda messages: generation(messages, stop))


def report_fixture(count=16):
    report = dict(cases=[case(i) for i in range(count)], contract_sha256='contract', max_new_tokens=512,
                  status='running', dataset_policy={}, max_context=4096,
                  runs=[dict(label=label, checkpoint='/fixture/' + label, tag=tag,
                             checkpoint_pins={'state': 'sha'}, status='planned', conversations=[])
                        for label, tag in [('previous', 'step_2880261'), ('continued', 'step_2881261')]])
    return report


def write_shard(directory, report, run, index, gpu, stop='eos'):
    path = directory / f'gpu-{gpu}' / f'case-{index:03d}.json'
    envelope = dict(contract_sha256=report['contract_sha256'], checkpoint=run['checkpoint'],
                    checkpoint_pins=run['checkpoint_pins'], label=run['label'], tag=run['tag'], gpu=gpu,
                    case_index=index, conversation=conversation(report['cases'][index], stop))
    write_json(path, envelope)
    return path


def cpu_worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, directory, deadline):
    """Spawn-safe fake inference; exercises the actual process/queue/merge path."""
    directory = Path(directory)
    completed = []
    index = initial
    while index is not None:
        write_shard(directory, report, run, index, gpu)
        completed.append(index)
        try:
            index = tasks.get(timeout=0.2)
        except queue.Empty:
            index = None
    write_json(directory / f'gpu-{gpu}' / 'worker.json', dict(
        gpu=gpu, status='complete', label=run['label'], tag=run['tag'],
        contract_sha256=report['contract_sha256'], completed_cases=completed,
        ema=report.get('ema', False), ema_verification={'verified': True, 'fixture': True}
        if report.get('ema', False) else None))


def failed_cpu_worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, directory, deadline):
    cancelled.set()
    write_json(Path(directory) / f'gpu-{gpu}' / 'worker.json', dict(
        gpu=gpu, status='failed', label=run['label'], tag=run['tag'],
        contract_sha256=report['contract_sha256'], completed_cases=[]))


def budget_cpu_worker(gpu, initial, tasks, cancelled, load_slots, report, run, manifest, directory, deadline):
    cancelled.set()
    write_json(Path(directory) / f'gpu-{gpu}' / 'worker.json', dict(
        gpu=gpu, status='budget_exhausted', label=run['label'], tag=run['tag'],
        contract_sha256=report['contract_sha256'], completed_cases=[]))


def test_eight_spawn_workers_dynamic_queue_exact_coverage_cpu(tmp_path, monkeypatch):
    report = report_fixture()
    monkeypatch.setattr(evaluation, 'worker', cpu_worker)
    monkeypatch.setattr(evaluation.v3, 'save', lambda *args: None)
    for run in report['runs']:
        assert evaluation.run_phase(report, run, {}, tmp_path, 20) == 0
        assert {s['gpu'] for s in run['workers']} == set(range(8))
        assert all(s['completed_cases'] for s in run['workers'])
        assert [c['id'] for c in run['conversations']] == [c['id'] for c in report['cases']]
    assert evaluation.v3.finish_report(report) == 0


def test_failed_workers_do_not_mark_complete(tmp_path, monkeypatch):
    report = report_fixture()
    monkeypatch.setattr(evaluation, 'worker', failed_cpu_worker)
    monkeypatch.setattr(evaluation.v3, 'save', lambda *args: None)
    assert evaluation.run_phase(report, report['runs'][0], {}, tmp_path, 20) == 1
    assert report['status'] == 'failed'


def test_budget_workers_keep_incomplete_exit_three(tmp_path, monkeypatch):
    report = report_fixture()
    monkeypatch.setattr(evaluation, 'worker', budget_cpu_worker)
    monkeypatch.setattr(evaluation.v3, 'save', lambda *args: None)
    assert evaluation.run_phase(report, report['runs'][0], {}, tmp_path, 20) == 3
    assert report['status'] == 'incomplete_budget'


def test_cpu_watcher_and_torchrun_environment_is_overridden(monkeypatch):
    for key in ('CUDA_VISIBLE_DEVICES', 'RANK', 'LOCAL_RANK', 'WORLD_SIZE', 'LOCAL_WORLD_SIZE',
                'MASTER_ADDR', 'MASTER_PORT', 'TORCHELASTIC_RUN_ID', 'PMI_RANK', 'PMIX_RANK',
                'OMPI_COMM_WORLD_RANK'):
        monkeypatch.setenv(key, '' if key == 'CUDA_VISIBLE_DEVICES' else 'inherited')
    # Restore all variables touched by the helper after this test.
    for key in ('CUDA_DEVICE_ORDER', 'WANDB_MODE', 'WANDB_DISABLED', 'TOKENIZERS_PARALLELISM',
                'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        monkeypatch.setenv(key, 'fixture')
    evaluation.worker_environment(3)
    assert os.environ['CUDA_VISIBLE_DEVICES'] == '3'
    assert os.environ['CUDA_DEVICE_ORDER'] == 'PCI_BUS_ID'
    assert not any(key in os.environ for key in ('RANK', 'WORLD_SIZE', 'LOCAL_RANK', 'MASTER_ADDR',
                                               'TORCHELASTIC_RUN_ID', 'PMI_RANK', 'PMIX_RANK'))


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'tag', 'checkpoint', 'pins', 'contract',
                                     'case_id', 'target', 'gold_history', 'cross_case_history',
                                     'empty', 'bad_stop', 'missing_tokens', 'extra_turn', 'context_overflow'])
def test_merge_rejects_corrupt_or_incomplete_shards(tmp_path, mutation):
    report = report_fixture(2)
    run = report['runs'][0]
    path = write_shard(tmp_path, report, run, 0, 0)
    write_shard(tmp_path, report, run, 1, 1)
    shard = load(path)
    c = shard['conversation']
    if mutation == 'duplicate':
        write_shard(tmp_path, report, run, 0, 2)
    elif mutation == 'missing':
        path.unlink()
    elif mutation == 'tag':
        shard['tag'] = 'step_2881261'
    elif mutation == 'checkpoint':
        shard['checkpoint'] = '/other'
    elif mutation == 'pins':
        shard['checkpoint_pins'] = {'state': 'wrong'}
    elif mutation == 'contract':
        shard['contract_sha256'] = 'wrong'
    elif mutation == 'case_id':
        c['id'] = 'unknown'
    elif mutation == 'target':
        c['turns'][0]['expected_target'] = 'other'
    elif mutation == 'gold_history':
        c['turns'][1]['prompt_messages'][1]['content'] = report['cases'][0]['expected_targets'][0]
    elif mutation == 'cross_case_history':
        c['turns'][1]['prompt_messages'][0]['content'] = 'another case'
    elif mutation == 'empty':
        c['turns'][0]['response'] = ''
    elif mutation == 'bad_stop':
        c['turns'][0]['finish_reason'] = 'interrupted'
    elif mutation == 'missing_tokens':
        del c['turns'][0]['prompt_token_ids']
    elif mutation == 'extra_turn':
        c['turns'].append(copy.deepcopy(c['turns'][0]))
    elif mutation == 'context_overflow':
        c['turns'][0]['prompt_token_ids'] = [1] * 4096
    if mutation not in ('missing', 'duplicate'):
        write_json(path, shard)
    with pytest.raises((ValueError, evaluation.v3.InvalidGeneration)):
        evaluation.merge_shards(report, run, tmp_path, final=True)


def test_length_stops_complete_without_approval_and_generated_history(tmp_path):
    report = report_fixture(2)
    for run in report['runs']:
        phase = tmp_path / run['label']
        for i in range(2):
            write_shard(phase, report, run, i, i, stop='length')
        evaluation.merge_shards(report, run, phase, final=True)
        run['status'] = 'complete'
        c = run['conversations'][0]
        assert c['turns'][1]['prompt_messages'][1]['content'] == c['turns'][0]['response']
        assert c['turns'][1]['prompt_messages'][1]['content'] != c['turns'][0]['expected_target']
    assert evaluation.v3.finish_report(report) == 0
    assert report['status'] == 'complete_with_length_stops'
    evaluation.save(tmp_path, report)
    saved = load(tmp_path / 'responses.json')
    assert saved['identity_positive'] is None and saved['full_suite_approved'] is None
    assert saved['review_required'] is True


@pytest.mark.parametrize('turns', [0, 1, 2])
def test_reporting_all_eight_empty_partial_or_complete_workers(tmp_path, turns):
    report = report_fixture(8)
    run = report['runs'][0]
    phase = tmp_path / 'shards'
    for i in range(8):
        path = write_shard(phase, report, run, i, i)
        shard = load(path)
        c = shard['conversation']
        c['turns'] = c['turns'][:turns]
        c['generated_history'] = c['generated_history'][:2 * turns]
        c['status'] = 'complete' if turns == 2 else 'incomplete'
        write_json(path, shard)
    evaluation.merge_shards(report, run, phase)
    before = copy.deepcopy(run['conversations'])
    evaluation.save(tmp_path, report)
    raw, summary = load(tmp_path / 'responses.json'), load(tmp_path / 'summary.json')
    assert raw['runs'][0]['conversations'] == before == run['conversations']
    assert summary['empty_in_progress_conversations']['previous'] == (8 if turns == 0 else 0)
    assert not raw['operational_success'] and raw['full_suite_approved'] is None
    assert ('Conversation status: incomplete' if turns < 2 else 'Conversation status: complete') in (tmp_path / 'responses.md').read_text()
    if turns < 2:
        with pytest.raises(ValueError):
            evaluation.merge_shards(report, run, phase, final=True)
    report['status'] = 'failed'
    evaluation.save(tmp_path, report)
    assert load(tmp_path / 'responses.json')['status'] == 'failed'


def test_reporting_mixed_empty_and_partial_groups_matches_legacy_stats(tmp_path):
    report = report_fixture(8)
    run = report['runs'][0]
    for i, c in enumerate(report['cases']):
        result = conversation(c)
        if i % 2 == 0:
            result.update(turns=[], generated_history=[], status='incomplete')
        run['conversations'].append(result)
    evaluation.save(tmp_path, report)
    expected = evaluation.historical.summarize(dict(report, runs=[dict(r, conversations=[
        c for c in r['conversations'] if c['turns']]) for r in report['runs']]))
    assert load(tmp_path / 'summary.json')['runs'] == expected['runs']
    assert len(load(tmp_path / 'responses.json')['runs'][0]['conversations']) == 8


def test_task_order_keeps_conversations_whole():
    cases = [case(i) for i in range(10)]
    cases[5]['users'].append('third turn')
    assert evaluation.task_order(cases)[0] == 5
    assert sorted(evaluation.task_order(cases)) == list(range(10))


def test_partial_shards_remain_incomplete(tmp_path):
    report = report_fixture(2)
    run = report['runs'][0]
    write_shard(tmp_path, report, run, 0, 0)
    evaluation.merge_shards(report, run, tmp_path)
    assert len(run['conversations']) == 1
    with pytest.raises(ValueError, match='Incomplete'):
        evaluation.merge_shards(report, run, tmp_path, final=True)


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt') as handle:
        for value in values:
            handle.write(json.dumps(value) + '\n')


def seal(root, manifest):
    manifest['files'] = [dict(path=str(p.relative_to(root)), bytes=p.stat().st_size, sha256=file_hash(p))
                         for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    write_json(root / 'manifest.json', manifest)
    return file_hash(root / 'manifest.json')


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    root = tmp_path / 'fresh'
    old = tmp_path / 'old'
    old.mkdir()
    (old / 'metadata').mkdir()
    (old / 'metadata/identity_facts.yaml').write_text('facts: fixture\n')
    (root / 'metadata').mkdir(parents=True)
    (root / 'metadata/identity_facts.yaml').write_text('facts: fixture\n')
    spec = {'requests': {'scratch': {'brief': {'da': 'Fra bunden.', 'en': 'From scratch.'}}}}
    (root / 'metadata/spec.yaml').write_text(yaml.safe_dump(spec))
    manifest = dict(profile='xl-full-bp', enable_thinking=False, languages={})
    for key in ('tokenizer', 'template'):
        path = tmp_path / key
        path.write_text('fixture')
        manifest[key] = dict(path=str(path), sha256=file_hash(path))
    provenance = []
    for lang in ('da', 'en'):
        data = []
        for i in range(50):
            row = dict(id=f'fresh-{lang}-{i}', language=lang, messages=[
                dict(role='user', content=f'Fresh {lang} {i}'),
                dict(role='assistant', content=spec['requests']['scratch']['brief'][lang])])
            data.append(row)
            provenance.append(dict(id=row['id'], split='heldout', language=lang, family='fixture',
                                   record_sha256=digest(row), turn_references=[dict(requests=['scratch'], mode='brief')]))
        rows(root / f'heldout/{lang}/test.jsonl.gz', data)
        relative = f'inputs/{lang}/train.jsonl.gz'
        rows(root / relative, [dict(id=f'train-{lang}', messages=[dict(role='user', content='training ' + lang)])])
        rows(old / relative, [dict(id=f'old-train-{lang}', messages=[dict(role='user', content='old training ' + lang)])])
        manifest['languages'][lang] = dict(input=relative)
    rows(root / 'metadata/provenance.jsonl.gz', provenance)
    development = []
    for i in range(100):
        c = case(1000 + i)
        c['users'][0] = 'old v3 question' if i == 0 else f'other old question {i}'
        development.append(c)
    previous = [case(i) for i in range(16)] + development
    for c in previous[:16]:
        c['suite'] = 'regression'
    monkeypatch.setattr(evaluation, 'V3_DATA', old)
    monkeypatch.setattr(evaluation.v3, 'load_cases', lambda *args: (previous, manifest, {}))
    monkeypatch.setattr(evaluation.historical, 'load_cases', lambda *args: ([dict(id='old-v2', users=['old v2 question'])], {}))
    return root, manifest, seal(root, manifest)


def test_fresh_loader_and_cpu_preflight_never_probe_gpu(fresh, tmp_path, monkeypatch):
    root, manifest, sha = fresh
    cases, _, policy = evaluation.load_cases(root, sha, 'metadata/spec.yaml')
    assert len(cases) == 216
    assert all(c['suite'] == 'development_v3' for c in cases[16:116])
    assert all(c['suite'] == 'heldout' for c in cases[116:])
    assert len(cases[16]['users']) == 2
    assert len(policy['development_roots']) == 2
    monkeypatch.setattr(evaluation, 'gpu_status', lambda *args: pytest.fail('CPU preflight probed GPU'))
    monkeypatch.setattr(evaluation, 'run_phase', lambda *args: pytest.fail('CPU preflight launched workers'))
    monkeypatch.setattr(evaluation.historical, 'tokenizer_lengths', lambda *args: {})
    monkeypatch.setattr(evaluation, 'runtime_asset_binding', lambda *args: {'fixture': True})
    output = tmp_path / 'preflight'
    assert evaluation.main(['--preflight-only', '--checkpoint', '/not-yet-created', '--output', str(output),
                            '--heldout-root', str(root), '--heldout-manifest-sha256', sha,
                            '--heldout-spec', 'metadata/spec.yaml']) == 0
    report = load(output / 'responses.json')
    assert report['status'] == 'preflight' and report['gpus'] == list(range(8))
    assert report['runs'][0]['tag'] == 'step_2880261'
    assert report['runs'][1]['tag'] == 'step_2881261'
    assert report['non_ema'] and not report['ema']
    assert report['allocator_limit_gib_per_worker'] == 24


def test_ema_latest_fresh_only_cpu_preflight(fresh, tmp_path, monkeypatch):
    root, _, sha = fresh
    monkeypatch.setattr(evaluation, 'gpu_status', lambda *args: pytest.fail('GPU probe'))
    monkeypatch.setattr(evaluation, 'run_phase', lambda *args: pytest.fail('GPU launch'))
    monkeypatch.setattr(evaluation.historical, 'tokenizer_lengths', lambda *args: {})
    monkeypatch.setattr(evaluation, 'runtime_asset_binding', lambda path, _: {'checkpoint': str(path)})
    inspected = []
    monkeypatch.setattr(evaluation, 'ema_source', lambda path, tag: inspected.append((str(path), tag)))
    output = tmp_path / 'ema-preflight'
    assert evaluation.main(['--preflight-only', '--ema', '--latest-only', '--heldout-only',
                            '--checkpoint', '/latest', '--output', str(output),
                            '--heldout-root', str(root), '--heldout-manifest-sha256', sha,
                            '--heldout-spec', 'metadata/spec.yaml']) == 0
    report = load(output / 'responses.json')
    assert report['ema'] and not report['non_ema'] and report['allocator_limit_gib_per_worker'] == 96
    assert len(report['runs']) == 1 and report['runs'][0]['tag'] == 'step_2881261'
    assert len(report['cases']) == 100 and all(c['suite'] == 'heldout' for c in report['cases'])
    assert report['per_checkpoint_seconds'] == report['max_seconds']
    assert inspected == [('/latest', 'step_2881261')]
    assert report['runtime_asset_binding']['checkpoint'] == '/latest'
    assert 'EMA, greedy' in (output / 'responses.md').read_text()
    assert 'Non-EMA' not in (output / 'responses.md').read_text()
    assert load(output / 'summary.json')['weight_mode'] == 'EMA'


@pytest.fixture
def ema_checkpoint(tmp_path):
    import torch
    import torch.distributed.checkpoint as dcp
    from types import SimpleNamespace
    model = torch.nn.Linear(2, 2).to(torch.bfloat16)
    state = {name: {'param_ema': torch.full(value.shape, 0.375, dtype=torch.float32)}
             for name, value in model.named_parameters()}
    dcp.save({'optim': {'state': state}}, checkpoint_id=tmp_path / 'fsdp2_step_1', no_dist=True)
    (tmp_path / 'all_config.yaml').write_text('ema: 0.9999\n')
    for value in model.parameters():
        value.data.fill_(0.375)
    return SimpleNamespace(model=model), dict(checkpoint=str(tmp_path), tag='step_1')


def test_ema_loader_true_and_all_tensors_verified(ema_checkpoint):
    checkpoint, run = ema_checkpoint
    calls = []
    def loader(*args, **kwargs):
        calls.append((args, kwargs))
        return checkpoint
    loaded, receipt = evaluation.load_for_run(run, True, loader=loader)
    assert loaded is checkpoint and calls == [((run['checkpoint'], None, True), {'ckpt_tag': 'step_1'})]
    assert receipt['verified'] and receipt['tensor_count'] == 2 and receipt['parameter_count'] == 6
    assert receipt['decay'] == 0.9999 and len(receipt['source_ema_tensor_sha256']) == 64
    assert receipt['loaded_inference_tensor_sha256'] != receipt['source_ema_tensor_sha256']


@pytest.mark.parametrize('failure', ['weights', 'coverage', 'disabled', 'missing'])
def test_ema_fails_closed(ema_checkpoint, failure):
    import torch
    import torch.distributed.checkpoint as dcp
    checkpoint, run = ema_checkpoint
    if failure == 'weights':
        checkpoint.model.weight.data.zero_()
    elif failure == 'coverage':
        checkpoint.model.register_parameter('extra', torch.nn.Parameter(torch.ones(1)))
    elif failure == 'disabled':
        (Path(run['checkpoint']) / 'all_config.yaml').write_text('ema: null\n')
    else:
        dcp.save({'model': {'weight': torch.ones(1)}},
                 checkpoint_id=Path(run['checkpoint']) / 'fsdp2_step_2', no_dist=True)
        run['tag'] = 'step_2'
    with pytest.raises(ValueError, match='EMA'):
        evaluation.verify_loaded_ema(checkpoint, run)


def test_nonema_does_not_inspect_ema(monkeypatch):
    monkeypatch.setattr(evaluation, 'ema_source', lambda *a: pytest.fail('Unexpected EMA inspection'))
    calls = []
    def loader(*args, **kwargs):
        calls.append(args)
        return 'checkpoint'
    assert evaluation.load_for_run({'checkpoint': '/fixture', 'tag': 'step_1'}, False, loader) == ('checkpoint', None)
    assert calls == [('/fixture', None, False)]


@pytest.mark.parametrize('ema', [False, True])
def test_latest_only_main_cpu_end_to_end(tmp_path, monkeypatch, ema):
    monkeypatch.setattr(evaluation, 'load_cases', lambda *a: ([case(i) for i in range(16)], {}, {}))
    monkeypatch.setattr(evaluation, 'runtime_asset_binding', lambda *a: {})
    monkeypatch.setattr(evaluation.historical, 'tokenizer_lengths', lambda *a: {})
    monkeypatch.setattr(evaluation, 'checkpoint_pins', lambda *a: {'state': 'sha'})
    monkeypatch.setattr(evaluation, 'gpu_status', lambda *a: {'free_mib': 180 * 1024})
    monkeypatch.setattr(evaluation, 'worker', cpu_worker)
    monkeypatch.setattr(evaluation, 'ema_source', lambda *a: (0.9999, {}))
    output = tmp_path / 'latest'
    assert evaluation.main(['--latest-only', '--heldout-only', '--checkpoint', '/fixture',
                            '--output', str(output), '--heldout-root', '/fixture',
                            '--heldout-manifest-sha256', 'fixture', '--heldout-spec', 'fixture']
                           + (['--ema'] if ema else [])) == 0
    report = load(output / 'responses.json')
    assert report['status'] == 'complete' and len(report['runs']) == 1
    assert len(report['runs'][0]['conversations']) == 16
    assert sum(len(c['turns']) for c in report['runs'][0]['conversations']) == 32
    assert load(output / 'completion.json')['responses_sha256'] == file_hash(output / 'responses.json')
    assert load(output / 'summary.json')['paired_turns'] == 0
    assert report['identity_positive'] is None
    assert report['ema'] is ema
    assert all(w['ema'] is ema for w in report['runs'][0]['workers'])


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'partial', 'wrong_label'])
def test_latest_completion_rejects_bad_coverage(mutation):
    report = report_fixture(2)
    report['latest_only'] = True
    report['runs'] = [report['runs'][1]]
    run = report['runs'][0]
    run.update(status='complete', conversations=[conversation(c) for c in report['cases']])
    if mutation == 'missing':
        run['conversations'].pop()
    elif mutation == 'duplicate':
        run['conversations'][1] = copy.deepcopy(run['conversations'][0])
    elif mutation == 'partial':
        run['conversations'][0]['turns'].pop()
    else:
        run['label'] = 'previous'
    with pytest.raises(ValueError):
        evaluation.finish_report(report)


def test_latest_length_stops_are_complete_not_approved(tmp_path):
    report = report_fixture(1)
    report['latest_only'] = True
    report['runs'] = [report['runs'][1]]
    report['runs'][0].update(status='complete', conversations=[conversation(report['cases'][0], 'length')])
    assert evaluation.finish_report(report) == 0
    evaluation.save(tmp_path, report)
    assert report['status'] == 'complete_with_length_stops' and report['identity_positive'] is None


@pytest.mark.parametrize('question', ['old v2 question', 'old v3 question', 'training da', 'old training da'])
def test_both_old_holdouts_and_training_are_excluded(fresh, question):
    root, manifest, sha = fresh
    path = root / 'heldout/da/test.jsonl.gz'
    records = list(evaluation.historical.gzip_rows(path))
    records[0]['messages'][0]['content'] = question
    rows(path, records)
    with pytest.raises(ValueError, match='overlap'):
        evaluation.load_cases(root, seal(root, manifest), 'metadata/spec.yaml')


def test_corrected_target_requires_matching_frozen_binding(fresh):
    root, manifest, sha = fresh
    path = root / 'heldout/da/test.jsonl.gz'
    records = list(evaluation.historical.gzip_rows(path))
    records[0]['messages'][1]['content'] = 'Wrong invented leader'
    rows(path, records)
    pp = root / 'metadata/provenance.jsonl.gz'
    refs = list(evaluation.historical.gzip_rows(pp))
    refs[0]['record_sha256'] = digest(records[0])
    rows(pp, refs)
    with pytest.raises(ValueError, match='frozen request'):
        evaluation.load_cases(root, seal(root, manifest), 'metadata/spec.yaml')


def test_v4_correction_spec_uses_sealed_inherited_bank_and_overrides(fresh):
    root, manifest, sha = fresh
    old_bank = evaluation.V3_DATA / 'metadata/identity_repair_expansion.yaml'
    bank = (root / 'metadata/spec.yaml').read_text()
    old_bank.write_text(bank)
    (root / 'metadata/identity_repair_expansion.yaml').write_text(bank)
    spec = dict(version=4, facts_sha256=file_hash(root / 'metadata/identity_facts.yaml'),
                answers={'scratch': {'da': 'Fra bunden.', 'en': 'From scratch.'}},
                heldout=[dict(id=f'family-{i}', answer='scratch', questions=[
                    {lang: f'Fresh {lang} {2*i+j}' for lang in ('da', 'en')} for j in range(2)])
                         for i in range(25)])
    (root / 'metadata/spec.yaml').write_text(yaml.safe_dump(spec))
    manifest['schema'] = 'dfm12-curated-identity-correction-v4'
    for lang in ('da', 'en'):
        values = list(evaluation.historical.gzip_rows(root / f'heldout/{lang}/test.jsonl.gz'))
        for row in values:
            row['id'] = digest(dict(schema=manifest['schema'], language=lang, messages=row['messages']))
            row.update(task='identity', parent_pair_id=None, direction='native')
        rows(root / f'heldout/{lang}/test.jsonl.gz', values)
    rows(root / 'metadata/provenance.jsonl.gz', [])
    cases, _, _ = evaluation.load_cases(root, seal(root, manifest), 'metadata/spec.yaml')
    assert cases[116]['expected_targets'] == ['Fra bunden.']
    (root / 'metadata/identity_repair_expansion.yaml').write_text(bank + '# changed\n')
    with pytest.raises(ValueError, match='Inherited answer bank changed'):
        evaluation.load_cases(root, seal(root, manifest), 'metadata/spec.yaml')


def test_actual_sealed_v4_reconstructed_provenance_and_development():
    root = evaluation.ROOT / 'data/dfm12/identity-corrected-da-en-20260926-v4'
    cases, manifest, policy = evaluation.load_cases(root,
        'b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b',
        'metadata/identity_correction.yaml')
    assert len(cases) == 216
    assert sum(len(c['users']) for c in cases) == 346
    fresh = [c for c in cases if c['suite'] == 'heldout']
    assert len(fresh) == 100 and sum(len(c['users']) > 1 for c in fresh) == 40
    assert cases[107]['suite'] == 'development_v3' and len(cases[107]['users']) == 4
    assert cases[115]['suite'] == 'development_v3' and len(cases[115]['users']) == 4
    assert policy['heldout_provenance'].startswith('exact_native_records')
    broken = yaml.safe_load((root / 'metadata/identity_correction.yaml').read_text())
    broken['heldout'][0]['questions'][0]['en'] += ' changed'
    bank = yaml.safe_load((evaluation.V3_DATA / 'metadata/identity_repair_expansion.yaml').read_text())['requests']
    for key, answer in broken['answers'].items():
        bank[key] = {'brief': answer}
    refs = evaluation.correction_provenance(broken, bank, manifest['schema'])
    assert fresh[1]['id'] not in refs


def test_frozen_helpers_unchanged():
    evaluation.verify_helpers()


def test_runtime_assets_bind_actual_current_xl():
    manifest = load(evaluation.V3_DATA / 'manifest.json')
    bound = evaluation.runtime_asset_binding(
        evaluation.ROOT / 'checkpoints/dfm12/XL-identity-expanded-from-step2879261', manifest)
    assert bound['vocab_size'] == 262144
    assert bound['assets']['tokenizer']['sha256'] == manifest['tokenizer']['sha256']
    broken = copy.deepcopy(manifest)
    broken['tokenizer']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='does not match manifest'):
        evaluation.runtime_asset_binding(Path(bound['train_metadata_path']).parent, broken)
