from pathlib import Path

from scripts import schedule_identity_final_ema_full as helper
from eval_scheduler.model import Action, Job, JobStatus


def test_serial_cpu_writers_preserve_gpu_and_dependencies():
    gpu = Job('gpu', Action.EVAL_STANDARD, 'standard', 'MATH', status=JobStatus.DONE)
    first = Job('a', Action.MERGE_STANDARD, 'standard', 'MATH', deps=('gpu',))
    second = Job('b', Action.MERGE_DFM, 'dfm', 'task', deps=('gpu',))
    avg = Job('avg', Action.AVERAGE, 'all', 'avg', deps=('a', 'b'))
    jobs = helper.serial_cpu_jobs([gpu, avg, first, second])
    mapped = {j.job_id: j for j in jobs}
    assert mapped['gpu'] is gpu
    assert mapped['a'].deps == ('gpu',)
    assert mapped['b'].deps == ('gpu', 'a')
    assert mapped['avg'].deps == ('a', 'b')
    assert all(mapped[k].status == JobStatus.PENDING for k in ('a', 'b', 'avg'))


def test_canonical_shard_paths():
    meta = dict(log_root='/std', dfm_log_root='/dfm', euroeval_log_root='/euro', ckpt_tag='step_1')
    job = Job('x', Action.EVAL_STANDARD, 'std', 'MATH', shard=2, shards=4, metadata=meta)
    assert helper.canonical_log_dir(job) == Path('/std/standard_shards/MATH')
    assert helper.canonical_log_dir(job.with_updates(action=Action.EVAL_DFM)) == Path('/dfm/MATH/shard_2_of_4/step_1')
    assert helper.canonical_log_dir(job.with_updates(action=Action.EVAL_DFM_IFEVAL)) == Path('/dfm/ifeval_shard_2/step_1')
    assert helper.canonical_log_dir(job.with_updates(action=Action.EVAL_EUROEVAL)) == Path('/euro/step_1/MATH')


def test_euroeval_replay_materializes_globbable_directory(tmp_path, monkeypatch):
    source = tmp_path / 'raw'
    source.mkdir()
    (source / 'merged_metrics.json').write_text('{"euroeval/test": 42}')
    dest = tmp_path / 'euro/step_1/test'
    dest.parent.mkdir(parents=True)
    dest.symlink_to(source, target_is_directory=True)
    job = Job('x', Action.EVAL_EUROEVAL, 'euro', 'test', status=JobStatus.DONE,
              log_dir=str(dest), metadata=dict(euroeval_log_root=str(tmp_path / 'euro'), ckpt_tag='step_1'))
    helper.write_plan(tmp_path / 'plan.tsv', [job])
    monkeypatch.setattr(helper, 'PLAN', tmp_path)
    helper.prepare_serial_replay()
    assert not dest.is_symlink()
    assert (source / 'merged_metrics.json').is_file()
    from scripts.backfill_external_eval_to_wandb import collect_euroeval
    assert collect_euroeval(tmp_path / 'euro') == {'euroeval/test': 42}
