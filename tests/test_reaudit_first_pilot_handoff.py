import sqlite3
import pytest
from scripts.reaudit_first_pilot_handoff import require_drained
from scripts import reaudit_first_pilot_handoff as handoff
from dfm12.io import load, write_json


@pytest.mark.parametrize('running,active', [(1, 0), (0, 1), (1, 1)])
def test_rejects_undrained(tmp_path, running, active):
    with sqlite3.connect(tmp_path / 'jobs.sqlite') as db:
        db.executescript('CREATE TABLE jobs(status TEXT); CREATE TABLE groups(active INTEGER);')
        db.execute('INSERT INTO jobs VALUES(?)', ('running' if running else 'accepted',))
        db.execute('INSERT INTO groups VALUES(?)', (active,))
    with pytest.raises(RuntimeError, match='not drained'):
        require_drained(tmp_path)


def test_accepts_drained(tmp_path):
    with sqlite3.connect(tmp_path / 'jobs.sqlite') as db:
        db.executescript("CREATE TABLE jobs(status TEXT); CREATE TABLE groups(active INTEGER);"
                         "INSERT INTO jobs VALUES('accepted'); INSERT INTO groups VALUES(0);")
    require_drained(tmp_path)


@pytest.mark.parametrize('failure', [None, 'audit', 'import'])
def test_handoff_resumes_even_after_reaudit_failure(tmp_path, monkeypatch, failure):
    quarter, audit = tmp_path / 'quarter', tmp_path / 'audit'
    quarter.mkdir()
    audit.mkdir()
    with sqlite3.connect(quarter / 'jobs.sqlite') as db:
        db.executescript('CREATE TABLE jobs(status TEXT); CREATE TABLE groups(active INTEGER);'
                         'INSERT INTO groups VALUES(0);')
    monkeypatch.setattr(handoff, 'ROOT', tmp_path)
    monkeypatch.setattr(handoff, 'verify', lambda root: None)
    monkeypatch.setattr(handoff.os, 'chdir', lambda root: None)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        stage = 'import' if 'dfm12.multilingual_quarter_import' in command else 'audit'
        if stage == failure:
            raise RuntimeError(stage + ' failed')

    class Process:
        pid = 123456

        def poll(self):
            return None

    def popen(command, **kwargs):
        commands.append(command)
        write_json(quarter / 'progress.json', dict(pid=Process.pid, phase='running'))
        return Process()

    monkeypatch.setattr(handoff.subprocess, 'run', run)
    monkeypatch.setattr(handoff.subprocess, 'Popen', popen)
    assert handoff.handoff(quarter, audit) == (1 if failure else 0)
    receipt = load(audit / 'handoff-finished.json')
    assert receipt['resume_confirmed']
    assert receipt['imported'] == (failure is None)
    assert len(commands) == (2 if failure == 'audit' else 3)
    assert 'dfm12.multilingual_quarter' in commands[-1]
    with pytest.raises(RuntimeError, match='already finished'):
        handoff.handoff(quarter, audit)
