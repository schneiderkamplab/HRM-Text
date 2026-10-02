import json
from types import SimpleNamespace

import pytest

from scripts import after_identity_multilingual_trial as m


@pytest.mark.parametrize('trial_fails', [False, True])
def test_trial_failure_also_resumes_scheduler(tmp_path, monkeypatch, trial_fails):
    plan = tmp_path / 'plan'
    plan.mkdir()
    trial = tmp_path / 'trial'
    trial.mkdir()
    (trial / 'cpu-preflight-passed.json').write_text('{}')
    monkeypatch.setattr(m, 'PLAN', plan)
    monkeypatch.setattr(m, 'STATE', tmp_path / 'state')
    monkeypatch.setattr(m, 'TRIAL', trial)
    reads = iter([
        [SimpleNamespace(job_id=m.XL_JOB, status=m.JobStatus.RUNNING)],
        [SimpleNamespace(job_id=m.XL_JOB, status=m.JobStatus.DONE),
         SimpleNamespace(job_id=m.XXL_JOB, status=m.JobStatus.PENDING)],
    ])
    monkeypatch.setattr(m, 'read_plan', lambda _: next(reads))
    running = iter([[123], [], []])
    monkeypatch.setattr(m, 'runners', lambda: next(running))
    monkeypatch.setattr(m, 'gpu_free', lambda: True)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if 'stop' in argv:
            (plan / 'stop.request').write_text('our stop')
        elif 'clear-stop' in argv:
            (plan / 'stop.request').unlink()
        elif 'dfm12.multilingual_run' in argv and trial_fails:
            raise RuntimeError('calibration failed')

    monkeypatch.setattr(m.subprocess, 'run', run)
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=999))
    m.main()
    receipt = json.loads((m.STATE / 'post-identity-trial/finished.json').read_text())
    assert receipt['success'] is not trial_fails
    assert receipt['runner_pid'] == 999
    assert any('clear-stop' in c for c in calls)
    assert not (plan / 'stop.request').exists()


def test_finished_identity_does_not_interrupt_xxl(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'STATE', tmp_path)
    monkeypatch.setattr(m, 'read_plan', lambda _: [
        SimpleNamespace(job_id=m.XL_JOB, status=m.JobStatus.DONE)])
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: pytest.fail('must not stop scheduler'))
    with pytest.raises(RuntimeError, match='already terminal'):
        m.main()


def test_existing_stop_is_not_cleared(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'STATE', tmp_path / 'state')
    monkeypatch.setattr(m, 'PLAN', tmp_path)
    (tmp_path / 'stop.request').write_text('user stop')
    monkeypatch.setattr(m, 'read_plan', lambda _: [
        SimpleNamespace(job_id=m.XL_JOB, status=m.JobStatus.RUNNING)])
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: pytest.fail('must not override stop'))
    with pytest.raises(RuntimeError, match='ownership'):
        m.main()
    assert (tmp_path / 'stop.request').read_text() == 'user stop'
