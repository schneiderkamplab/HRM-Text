import sqlite3

import pytest

from dfm12 import audit_completion_release as release
from dfm12.io import file_hash, write_json


def queue(tmp_path, complete=1, status="done"):
    write_json(tmp_path / "sources.json", {"sources": [{"component": "one", "sha256": "hash"}]})
    with sqlite3.connect(tmp_path / "jobs.sqlite") as db:
        db.execute("CREATE TABLE sources(component,sha256,complete,input_rows,queued,quarantined)")
        db.execute("INSERT INTO sources VALUES ('one','hash',?,1,1,0)", (complete,))
        db.execute("CREATE TABLE jobs(status)")
        db.execute("INSERT INTO jobs VALUES (?)", (status,))
    return {"root": str(tmp_path), "manifest_sha256": file_hash(tmp_path / "sources.json"), "sources": {"one": "hash"}}


@pytest.mark.parametrize("status,ready", [("done", True), ("failed", True), ("pending", False), ("running", False), ("parked", False), ("unknown", False)])
def test_terminal_gate(tmp_path, status, ready):
    assert release.queue_state(queue(tmp_path, status=status))["ready"] is ready


def test_source_must_complete_and_match(tmp_path):
    entry = queue(tmp_path, complete=0)
    assert not release.queue_state(entry)["ready"]
    entry["sources"]["missing"] = "hash"
    assert not release.queue_state(entry)["ready"]
    (tmp_path / "sources.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest changed"):
        release.queue_state(entry)


def test_descendants_exclude_unrelated():
    table = {1: {"ppid": 0}, 2: {"ppid": 1}, 3: {"ppid": 2}, 4: {"ppid": 0}}
    assert release.descendants(table, [1]) == {1, 2, 3}


def test_pid_reuse_refused_before_signal(monkeypatch):
    expected = {"pid": 1, "starttime": 10, "argv": ["audit"], "exe": "/python"}
    monkeypatch.setattr(release, "process", lambda pid: dict(expected, starttime=11, state="S"))
    monkeypatch.setattr(release, "open_pidfd", lambda pid: pytest.fail("must not open reused PID"))
    with pytest.raises(ValueError, match="identity changed"):
        release.signal_exact(expected, 15)


def test_cmd_change_refused():
    expected = {"pid": 1, "starttime": 10, "argv": ["audit"], "exe": "/python"}
    assert not release.same_process(expected, dict(expected, argv=["unrelated"]))


def test_hooks_independent_one_shot(tmp_path, monkeypatch):
    script = tmp_path / "script.py"
    script.write_text("pass\n")
    for name, scope in [("training", "verified_training_resume_only"), ("finalization", "finished_dataset_export_upload_only")]:
        write_json(tmp_path / (name + "-ready.json"), {"ready": True, "user_authorized": True, "scope": scope,
                   "argv": ["python", str(script)], "cwd": str(tmp_path), "pins": {str(script): file_hash(script)}})
    calls = []
    class Child:
        pid = 42
        def poll(self):
            return None
    monkeypatch.setattr(release.subprocess, "Popen", lambda *args, **kwargs: calls.append(args) or Child())
    children = {}
    assert release.hook(tmp_path, "training", children) == "running"
    assert release.hook(tmp_path, "finalization", children) == "running"
    assert len(calls) == 2
    assert release.hook(tmp_path, "training", {}) == "already_started_no_retry"
    assert len(calls) == 2


def test_marker_missing_does_not_launch(tmp_path):
    assert release.hook(tmp_path, "training", {}) == "waiting_parent_ready_marker"


def test_zombie_not_signaled(monkeypatch):
    monkeypatch.setattr(release, "process", lambda pid: {"state": "Z"})
    monkeypatch.setattr(release, "open_pidfd", lambda pid: pytest.fail("zombie should not be signaled"))
    assert release.signal_exact({"pid": 123}, 15) == "already_gone"


def test_libc_pidfd_self_zero_signal():
    import os
    fd = release.open_pidfd(os.getpid())
    try:
        release.send_pidfd(fd, 0)
    finally:
        os.close(fd)
