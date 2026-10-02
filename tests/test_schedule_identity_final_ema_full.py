"""Temporary-only regression fixtures for final EMA archive path repair."""
import json
from pathlib import Path

import pytest

from scripts import schedule_identity_final_ema_full as helper
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts.backfill_external_eval_to_wandb import collect_euroeval
from scripts.merge_standard_eval_shards import compute_merged


def make_job(root, action, *, name='task', shard=0, status=JobStatus.DONE, suffix=''):
    identity = f'{action.value}-{name}-{shard}{suffix}'
    return Job(identity, action, 'fixture', name, shard=shard, shards=2,
        status=status, attempt=2, log_dir=str(root/'relocated'/identity),
        metadata=dict(log_root=str(root/'standard'), dfm_log_root=str(root/'dfm'),
            euroeval_log_root=str(root/'euro'), ckpt_tag=helper.TAG,
            shards=2, eval_epoch=10.050795912217435, wandb_project='DFM5',
            wandb_run_id='dfm12-xl-identity-da-en-1000'))


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.mark.parametrize('action,relative', [
    (Action.EVAL_STANDARD, 'standard/standard_shards/task'),
    (Action.MERGE_STANDARD, 'standard/standard_shards/task'),
    (Action.EVAL_DFM, 'dfm/task/shard_1_of_2/step_2897261'),
    (Action.MERGE_DFM, 'dfm/task'),
    (Action.EVAL_DFM_IFEVAL, 'dfm/ifeval_shard_1/step_2897261'),
    (Action.MERGE_IFEVAL, 'dfm'),
    (Action.EVAL_EUROEVAL, 'euro/step_2897261/task'),
    (Action.EVAL_EUROEVAL_BATCHED_IFEVAL, 'euro/step_2897261/task'),
])
def test_canonical_log_layout(tmp_path, action, relative):
    job = make_job(tmp_path, action, shard=1)
    before = job.to_row()
    assert helper.canonical_log_dir(job) == tmp_path/relative
    assert job.to_row() == before


@pytest.mark.parametrize('action', [a for a in Action if a not in {
    Action.EVAL_STANDARD, Action.MERGE_STANDARD, Action.EVAL_DFM, Action.MERGE_DFM,
    Action.EVAL_DFM_IFEVAL, Action.MERGE_IFEVAL, Action.EVAL_EUROEVAL,
    Action.EVAL_EUROEVAL_BATCHED_IFEVAL}])
def test_other_actions_keep_log_directory(tmp_path, action):
    job = make_job(tmp_path, action)
    assert helper.canonical_log_dir(job) == Path(job.log_dir)


@pytest.fixture
def relocated_plan(tmp_path, monkeypatch):
    plan = tmp_path/'plan'
    plan.mkdir()
    monkeypatch.setattr(helper, 'PLAN', plan)
    jobs, originals = [], {}
    for action, name in ((Action.EVAL_STANDARD,'ARC'), (Action.EVAL_DFM,'piqa'),
                         (Action.EVAL_DFM_IFEVAL,'ifeval-da')):
        for shard in range(2):
            job = make_job(tmp_path,action,name=name,shard=shard)
            jobs.append(job)
            if action == Action.EVAL_STANDARD:
                path = put(Path(job.log_dir)/f'ARC_shard_{shard}_of_2.log',
                           f'--- ARC ---\nn: 2\nacc: {shard}\n')
            else:
                path = put(Path(job.log_dir)/'inspect'/f'result-{shard}.eval', f'archive-{shard}')
            originals[path] = path.read_bytes()
    for action, name in ((Action.EVAL_EUROEVAL,'scala-da'),
                         (Action.EVAL_EUROEVAL_BATCHED_IFEVAL,'ifeval-da')):
        job = make_job(tmp_path,action,name=name)
        jobs.append(job)
        path = put(Path(job.log_dir)/'merged_metrics.json',
                   json.dumps({'metrics':{f'euroeval/{name}/score':75.0}}))
        originals[path] = path.read_bytes()
        path = put(Path(job.log_dir)/'raw'/'responses.jsonl', '{"fixture":true}\n')
        originals[path] = path.read_bytes()
    for action,name in ((Action.MERGE_STANDARD,'ARC'), (Action.MERGE_DFM,'piqa'),
                        (Action.MERGE_IFEVAL,'ifeval-da'), (Action.AVERAGE,'headline')):
        jobs.append(make_job(tmp_path,action,name=name,status=JobStatus.FAILED))
    jobs += [make_job(tmp_path,Action.EVAL_EUROEVAL,name='valeu-da',status=JobStatus.SKIPPED),
             make_job(tmp_path,Action.MERGE_DFM,name='excluded',status=JobStatus.SKIPPED),
             make_job(tmp_path,Action.REPORT,name='report',status=JobStatus.SKIPPED)]
    write_plan(plan/'plan.tsv',jobs)
    return plan, jobs, originals


def test_repair_restores_standard_dfm_ifeval_reader_paths(relocated_plan):
    from eval_scheduler.runtime import resolve_dfm_shard_archive
    plan, jobs, originals = relocated_plan
    before = (plan/'plan.tsv').read_bytes()
    helper.repair_existing()
    repaired = {j.job_id:j for j in read_plan(plan/'plan.tsv')}
    assert (plan/'plan.before-archive-repair.tsv').read_bytes() == before
    standard = next(j for j in jobs if j.action == Action.MERGE_STANDARD)
    root = helper.canonical_log_dir(standard)
    paths = [root/f'ARC_shard_{i}_of_2.log' for i in range(2)]
    assert compute_merged(paths,'ARC') == {'n':4.0,'acc':0.5}
    for job in jobs:
        changed = repaired[job.job_id]
        assert Path(changed.log_dir) == helper.canonical_log_dir(job)
        assert changed.deps == job.deps
        if job.status == JobStatus.FAILED:
            assert changed.status == JobStatus.PENDING and changed.attempt == 0
            assert changed.metadata['archive_repair_previous_attempt'] == 2
        else:
            assert (changed.status,changed.attempt) == (job.status,job.attempt)
        if job.action == Action.EVAL_DFM:
            shard_root = Path(job.metadata['dfm_log_root'])/job.name/f'shard_{job.shard}_of_2'
            assert resolve_dfm_shard_archive(shard_root,ckpt_tag=helper.TAG,step='2897261') == (
                Path(job.log_dir)/'inspect'/f'result-{job.shard}.eval').resolve()
        if job.action == Action.EVAL_DFM_IFEVAL:
            found = list((Path(job.metadata['dfm_log_root'])/f'ifeval_shard_{job.shard}'/
                          helper.TAG/'inspect').glob('*.eval'))
            assert len(found) == 1
            assert found[0].read_bytes() == originals[Path(job.log_dir)/'inspect'/f'result-{job.shard}.eval']
    assert all(path.read_bytes() == content for path,content in originals.items())
    receipt = json.loads((plan/'archive-repair.json').read_text())
    assert receipt['gpu_reruns'] == 0
    assert set(receipt['reset_job_ids']) == {j.job_id for j in jobs if j.status == JobStatus.FAILED}


def test_serial_replay_exposes_both_euroeval_modes_to_real_collector(relocated_plan):
    plan, jobs, originals = relocated_plan
    helper.repair_existing()
    helper.prepare_serial_replay()
    expected = {'euroeval/scala-da/score':75.0,'euroeval/ifeval-da/score':75.0}
    euro_root = Path(jobs[0].metadata['euroeval_log_root'])
    assert collect_euroeval(euro_root) == expected
    assert collect_euroeval(euro_root/helper.TAG) == expected
    for job in jobs:
        if job.action in {Action.EVAL_EUROEVAL,Action.EVAL_EUROEVAL_BATCHED_IFEVAL} and job.status == JobStatus.DONE:
            dest = helper.canonical_log_dir(job)
            assert dest.is_dir() and not dest.is_symlink()
            assert (dest/'merged_metrics.json').is_file()
            assert (dest/'raw'/'responses.jsonl').read_bytes() == originals[Path(job.log_dir)/'raw'/'responses.jsonl']
    assert all(path.read_bytes() == content for path,content in originals.items())
    first = read_plan(plan/'plan.tsv')
    helper.prepare_serial_replay()
    assert read_plan(plan/'plan.tsv') == first
    assert collect_euroeval(euro_root) == expected


def test_serial_replay_resets_all_nonskipped_cpu_writers_without_gpu_reruns(tmp_path):
    jobs = [make_job(tmp_path,Action.AVERAGE,name='headline'),
            make_job(tmp_path,Action.EVAL_STANDARD,name='ARC'),
            make_job(tmp_path,Action.MERGE_STANDARD,name='ARC').with_updates(deps=('source',)),
            make_job(tmp_path,Action.MERGE_DFM,status=JobStatus.FAILED),
            make_job(tmp_path,Action.MERGE_IFEVAL,status=JobStatus.PENDING),
            make_job(tmp_path,Action.MERGE_DFM,name='excluded',status=JobStatus.SKIPPED),
            make_job(tmp_path,Action.REPORT,status=JobStatus.SKIPPED)]
    original = [j.to_row() for j in jobs]
    updated = helper.serial_cpu_jobs(jobs)
    by_id = {j.job_id:j for j in updated}
    writers = [j for j in jobs if j.action in helper.CPU_ACTIONS and j.status != JobStatus.SKIPPED]
    writers.sort(key=lambda j:j.action == Action.AVERAGE)
    for index, job in enumerate(writers):
        changed = by_id[job.job_id]
        assert changed.status == JobStatus.PENDING and changed.attempt == 0
        assert set(job.deps) <= set(changed.deps)
        if index:
            assert writers[index-1].job_id in changed.deps
        assert len(set(changed.deps)) == len(changed.deps)
    for job in jobs:
        if job not in writers:
            assert by_id[job.job_id] == job
    assert [j.to_row() for j in jobs] == original
    assert helper.serial_cpu_jobs(updated) == updated


@pytest.mark.parametrize('operation', ['repair_existing','prepare_serial_replay'])
@pytest.mark.parametrize('action,status', [
    (Action.MERGE_DFM,JobStatus.RUNNING),
    (Action.EVAL_STANDARD,JobStatus.RUNNING),
    (Action.EVAL_DFM,JobStatus.PENDING),
    (Action.EVAL_EUROEVAL,JobStatus.FAILED),
])
def test_refuse_active_or_unauthorized_work_without_plan_mutation(tmp_path,monkeypatch,operation,action,status):
    monkeypatch.setattr(helper,'PLAN',tmp_path)
    write_plan(tmp_path/'plan.tsv',[make_job(tmp_path,action,status=status)])
    before = (tmp_path/'plan.tsv').read_bytes()
    with pytest.raises(ValueError):
        getattr(helper,operation)()
    assert (tmp_path/'plan.tsv').read_bytes() == before


def test_conflicting_canonical_archive_is_not_overwritten(relocated_plan):
    plan,jobs,originals = relocated_plan
    job = next(j for j in jobs if j.action == Action.EVAL_DFM)
    conflict = put(helper.canonical_log_dir(job)/'unrelated.txt','do not overwrite')
    before = (plan/'plan.tsv').read_bytes()
    with pytest.raises(ValueError,match='Conflicting archive path'):
        helper.repair_existing()
    assert conflict.read_text() == 'do not overwrite'
    assert (plan/'plan.tsv').read_bytes() == before
    assert all(path.read_bytes() == content for path,content in originals.items())


@pytest.mark.parametrize('count',[0,2])
def test_dfm_missing_or_ambiguous_archives_fail_closed(tmp_path,monkeypatch,count):
    monkeypatch.setattr(helper,'PLAN',tmp_path)
    job = make_job(tmp_path,Action.EVAL_DFM)
    for index in range(count):
        put(Path(job.log_dir)/'inspect'/f'{index}.eval','archive')
    write_plan(tmp_path/'plan.tsv',[job])
    before = (tmp_path/'plan.tsv').read_bytes()
    with pytest.raises(ValueError,match='Require one archive'):
        helper.repair_existing()
    assert (tmp_path/'plan.tsv').read_bytes() == before


def test_cpu_recovery_never_allocates_gpus_or_server_pool(tmp_path,monkeypatch):
    from eval_scheduler import runtime
    monkeypatch.setattr(helper,'PLAN',tmp_path)
    write_plan(tmp_path/'plan.tsv',[make_job(tmp_path,Action.MERGE_DFM,status=JobStatus.PENDING)])
    calls = []
    class FakeRunner:
        def __init__(self,plan,**kwargs):
            calls.append((plan,kwargs))
        def run(self):
            calls.append('run')
    monkeypatch.setattr(runtime,'Runner',FakeRunner)
    helper.run_cpu_recovery()
    assert calls == [(tmp_path,dict(gpus=[],persistent_vllm=False)),'run']


def test_fresh_plan_uses_canonical_paths_and_preserves_every_exclusion(tmp_path,monkeypatch):
    source, plan = tmp_path/'source', tmp_path/'new-plan'
    source.mkdir()
    for key,value in dict(ROOT=tmp_path,SOURCE=source,PLAN=plan,
                          CHECKPOINT=tmp_path/'checkpoint',EXPORT=tmp_path/'export').items():
        monkeypatch.setattr(helper,key,value)
    monkeypatch.setattr(helper,'complete',lambda *_:True)
    monkeypatch.setattr(helper,'validate_tokenizer',lambda:dict(fixture=True))
    actions = [Action.EVAL_STANDARD,Action.MERGE_STANDARD,Action.EVAL_DFM,
               Action.MERGE_DFM,Action.EVAL_DFM_IFEVAL,Action.MERGE_IFEVAL,
               Action.EVAL_EUROEVAL,Action.EVAL_EUROEVAL_BATCHED_IFEVAL,
               Action.AVERAGE,Action.REPORT]
    jobs = []
    for index in range(290):
        job = make_job(source,actions[index % len(actions)],name=f'task-{index}',
                       status=JobStatus.SKIPPED if index % 7 == 0 else JobStatus.DONE)
        meta = dict(job.metadata,ckpt_tag='step_2881261',fix_mistral_regex=False)
        jobs.append(job.with_updates(job_id=f'identity-4000-ema-full-{index}',metadata=meta,
            deps=(f'identity-4000-ema-full-{index-1}',) if index else ()))
    write_plan(source/'plan.tsv',jobs)
    source_bytes = (source/'plan.tsv').read_bytes()
    helper.main()
    prepared = read_plan(plan/'plan.tsv')
    assert len(prepared) == 290
    assert (source/'plan.tsv').read_bytes() == source_bytes
    for old,new in zip(jobs,prepared):
        assert new.status == (JobStatus.SKIPPED if old.status == JobStatus.SKIPPED else JobStatus.PENDING)
        assert new.attempt == 0
        assert new.job_id == old.job_id.replace('identity-4000','identity-20000')
        assert {d.replace('identity-4000','identity-20000') for d in old.deps} <= set(new.deps)
        assert set(new.deps) <= {j.job_id for j in prepared}
        assert Path(new.log_dir) == helper.canonical_log_dir(new)
        assert new.metadata['ckpt_tag'] == 'step_2897261'
        assert new.metadata['no_ema'] is False
        assert new.metadata['fix_mistral_regex'] is False
        assert new.metadata['vllm_gpu_memory_utilization'] <= .5
        assert new.action != Action.TRAIN_UNTIL_STEP
    receipt = json.loads((plan/'preflight.json').read_text())
    assert len(receipt['skipped']) == sum(j.status == JobStatus.SKIPPED for j in jobs)
    assert receipt['no_training'] is True
