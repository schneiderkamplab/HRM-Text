import sqlite3
from pathlib import Path
from types import SimpleNamespace

from scripts import monitor_dfm13_wave_campaign as monitor


def test_booster_waits_for_all_baltic_work_and_does_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path('logs/dfm13/wave4').mkdir(parents=True)
    for wave in ('baltic', 'wave4'):
        path = Path(f'data/dfm13/{wave}/audit/jobs.sqlite')
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE jobs(stage TEXT,status TEXT)')
            db.execute("INSERT INTO jobs VALUES('audit','pending')")
    processes, launched = [], []
    monkeypatch.setattr(monitor.psutil, 'process_iter', lambda fields: processes)
    monkeypatch.setattr(monitor.time, 'monotonic', lambda: 1000)
    def launch(args, **kwargs):
        launched.append(args)
        processes.append(SimpleNamespace(info={'cmdline': args}))
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(monitor.subprocess, 'Popen', launch)
    assert monitor.ensure_wave4_booster(0) == 0
    with sqlite3.connect('data/dfm13/baltic/audit/jobs.sqlite') as db:
        db.execute("UPDATE jobs SET status='running'")
    assert monitor.ensure_wave4_booster(0) == 0
    with sqlite3.connect('data/dfm13/baltic/audit/jobs.sqlite') as db:
        db.execute("UPDATE jobs SET status='done'")
    assert monitor.ensure_wave4_booster(0) == 1000
    assert monitor.ensure_wave4_booster(0) == 0
    assert len(launched) == 1
    assert launched[0][launched[0].index('--concurrency') + 1] == '320'
