import threading

from eval_scheduler.model import Action, JobStatus
from test_database_runner import setup, job


def test_training_not_blocked_by_running_publication(tmp_path):
    publishing = threading.Event()
    trained = threading.Event()

    def execute(current, *args):
        if current.job_id == 'publish':
            publishing.set()
            assert trained.wait(3), 'CPU publication blocked training'
        elif current.job_id == 'eval':
            assert publishing.wait(3)
        elif current.job_id == 'train':
            trained.set()
        return 0

    jobs = [job('publish'), job('eval', Action.EVAL_DFM),
            job('teardown', Action.TEARDOWN_EVAL, deps=('eval',)),
            job('train', Action.TRAIN_UNTIL_STEP, deps=('eval',))]
    runner, store, _ = setup(tmp_path, jobs, execute)
    assert runner.run() == 'done'
    assert all(j.status == JobStatus.DONE for j in store.load_jobs())


def test_explicit_user_hold_is_distinct_from_scheduler_hold(tmp_path):
    from eval_scheduler.cooperative_training import user_held
    active = tmp_path / 'active'
    active.mkdir()
    assert not user_held(tmp_path, active)
    (tmp_path / 'hold').write_text('Explicit user hold: wait for my resume command')
    assert user_held(tmp_path, active)
    (tmp_path / 'hold').write_text('scheduler owns evaluation interval\n')
    assert not user_held(tmp_path, active)
    (active / 'hold').write_text('manual pause')
    assert user_held(tmp_path, active)


def test_disk_handoff_requires_offload_and_never_stops_resumed_trainer(tmp_path):
    import json
    import pytest
    from eval_scheduler.cooperative_training import disk_handoff
    active=tmp_path/'active';active.mkdir()
    (tmp_path/'active.json').write_text(json.dumps({'control_dir':str(active)}))
    state=tmp_path/'checkpoint.json';state.write_text(json.dumps({'step':150000,'checkpoint_kind':'regular'}))
    ready={'job_id':'test','generation':1,'step':150000,'checkpoint':str(state),'ranks':[]}
    (active/'suspend_ready.json').write_text(json.dumps(ready))
    generation=active/'generation_000001';generation.mkdir()
    settings={'control_root':str(tmp_path),'step':150000}
    with pytest.raises(FileNotFoundError):disk_handoff(settings)
    assert not (tmp_path/'stop.request').exists()
    (generation/'offloaded.json').write_text(json.dumps(ready))
    (active/'resumed.json').write_text(json.dumps(ready))
    with pytest.raises(RuntimeError,match='already resumed'):disk_handoff(settings)
    assert not (tmp_path/'stop.request').exists()


def test_disk_handoff_stops_only_verified_suspended_predecessor(tmp_path,monkeypatch):
    import json
    import training_suspend.protocol as protocol
    from eval_scheduler.cooperative_training import disk_handoff
    active=tmp_path/'active';active.mkdir()
    (tmp_path/'active.json').write_text(json.dumps({'control_dir':str(active)}))
    (tmp_path/'launcher.json').write_text(json.dumps({'identity':{'pid':99999999}}))
    state=tmp_path/'checkpoint.json';state.write_text(json.dumps({'step':150000,'checkpoint_kind':'regular'}))
    ready={'job_id':'test','generation':1,'step':150000,'checkpoint':str(state),'ranks':[]}
    (active/'suspend_ready.json').write_text(json.dumps(ready))
    generation=active/'generation_000001';generation.mkdir()
    (generation/'offloaded.json').write_text(json.dumps(ready))
    def gone(identity):raise ProcessLookupError()
    monkeypatch.setattr(protocol,'validate_process',gone)
    disk_handoff({'control_root':str(tmp_path),'step':150000})
    assert (tmp_path/'stop.request').exists()
    assert (tmp_path/'hold').exists()
