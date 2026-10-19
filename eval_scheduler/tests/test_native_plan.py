"""Native campaign admission is isolated from shared servers and training."""
import pytest

from eval_scheduler import runtime
from eval_scheduler.model import Action, Job, JobStatus, write_plan
from eval_scheduler.native_plan import validate_native_plan, run_native_plan
from test_database_runner import setup


def prepare(tmp_path):
    child = tmp_path / 'child'
    child.mkdir()
    row = Job('math', Action.EVAL_STANDARD, 'standard', 'MATH')
    write_plan(child/'plan.tsv', [row])
    parent = Job('native', Action.EVAL_NATIVE_PLAN, 'native', 'comparison',
                 gpu_policy='all', max_retries=0, log_dir=str(child),
                 metadata={'native_plan_dir': str(child)})
    return parent, row, child


def test_validation_rejects_recursive_or_shared_subplans(tmp_path):
    parent, row, child = prepare(tmp_path)
    assert validate_native_plan(parent) == child
    with pytest.raises(ValueError, match='parent'):
        validate_native_plan(parent, child)
    for invalid in (parent, row.with_updates(metadata={'hrm_server_backend':'vllm'}),
                    row.with_updates(status=JobStatus.RUNNING)):
        write_plan(child/'plan.tsv', [invalid])
        with pytest.raises(ValueError):
            validate_native_plan(parent)


def test_nonzero_or_incomplete_native_campaign_not_success(tmp_path, monkeypatch):
    parent, row, child = prepare(tmp_path)
    calls = []
    def execute(argv, **kw):
        calls.append(argv)
        return 0
    monkeypatch.setattr(runtime, 'run_command', execute)
    assert run_native_plan(parent, (2, 3)) == 1
    assert calls[0][-1] == '2,3'
    write_plan(child/'plan.tsv', [row.with_updates(status=JobStatus.DONE)])
    assert run_native_plan(parent, (2, 3)) == 0
    monkeypatch.setattr(runtime, 'run_command', lambda *a, **k: 72)
    assert run_native_plan(parent, (2, 3)) == 72


def test_native_failure_does_not_strand_training(tmp_path):
    parent, _, _ = prepare(tmp_path)
    barrier = Job('terminal', Action.TERMINAL_BARRIER, 'control', 'terminal',
                  deps=('native',), deps_mode='terminal')
    train = Job('training', Action.TRAIN_UNTIL_STEP, 'training', 'next', deps=('terminal',))
    calls = []
    def execute(job, gpu, pool, gpus):
        calls.append(job.job_id)
        if job.action in (Action.EVAL_NATIVE_PLAN, Action.TRAIN_UNTIL_STEP):
            assert pool.drained and gpus == (0, 1)
        return 1 if job.job_id == 'native' else 0
    runner, store, _ = setup(tmp_path, [parent, barrier, train], execute)
    assert runner.run() == 'done'
    assert calls == ['native', 'terminal', 'training']
    assert store.load_jobs()[0].status == JobStatus.FAILED
