import sqlite3
from pathlib import Path

import pytest

from dfm12.export_orchestrator import ROOTS, audit_state, contract, preserve, run_helper, wait_lock, merge_identity
from dfm12.io import file_hash, write_json, lock, load


def ready(tmp_path):
    evidence = tmp_path / "ready.txt"
    evidence.write_text("owner helper ready")
    roots = [str(Path("data/dfm12") / r) for r in ROOTS]
    command = ["-m", "dfm12.export_finished", "--output", "exports_dfm12", "--incremental"]
    for root in roots:
        command += ["--run", root]
    value = {"version": 1, "status": "helpers_ready", "output": "exports_dfm12",
             "namespace": "schneiderkamplab", "audit_roots": roots, "export_command": command,
             "identity_output": "data/dfm12/export-orchestration-20260925/identity-export-v1",
             "identity_command": ["-m", "dfm12.export_identity", "--output", "data/dfm12/export-orchestration-20260925/identity-export-v1"],
             "helper_evidence": [{"path": str(evidence), "sha256": file_hash(evidence)}]}
    path = tmp_path / "contract.json"
    write_json(path, value)
    return path, value


def test_contract_requires_readiness_five_roots_and_pins(tmp_path):
    path, value = ready(tmp_path)
    assert contract(path) == value
    value["status"] = "in_progress"
    write_json(path, value)
    with pytest.raises(ValueError, match="readiness"):
        contract(path)
    value["status"] = "helpers_ready"
    value["audit_roots"].pop()
    write_json(path, value)
    with pytest.raises(ValueError, match="five"):
        contract(path)


def test_contract_does_not_allow_changed_helpers_or_shell(tmp_path):
    path, value = ready(tmp_path)
    Path(value["helper_evidence"][0]["path"]).write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        contract(path)
    value["export_command"] = ["bash", "-c", "anything"]
    write_json(path, value)
    with pytest.raises(ValueError, match="module argument"):
        contract(path)


def test_preserve_verified_and_allow_new_upload(tmp_path):
    before = {"dfm12-old": {"rows": 3, "component": "old", "manifest_sha256": "hash", "upload": None}}
    after = {"dfm12-old": dict(before["dfm12-old"], upload={"status": "verified", "revision": "abc"})}
    preserve(before, after)
    preserve(after, after)
    with pytest.raises(ValueError, match="package changed"):
        preserve(before, {"dfm12-old": dict(after["dfm12-old"], rows=4)})
    with pytest.raises(ValueError, match="receipt changed"):
        preserve(after, {"dfm12-old": dict(after["dfm12-old"], upload={"status": "verified", "revision": "new"})})


def test_readonly_terminal_failed_rows_never_retried(tmp_path):
    db = sqlite3.connect(tmp_path / "jobs.sqlite")
    db.executescript("CREATE TABLE sources(component,complete,input_rows,queued,quarantined); CREATE TABLE jobs(component,status);")
    for name, complete, status in [("done",1,"done"),("failed",1,"failed"),("active",1,"running"),("unfed",0,"done")]:
        db.execute("INSERT INTO sources VALUES(?,?,1,1,0)",(name,complete))
        db.execute("INSERT INTO jobs VALUES(?,?)",(name,status))
    db.commit(); db.close()
    write_json(tmp_path / "sources.json", {"sources": [{"component": n} for n in ("done","failed","active","unfed","missing")]})
    before = file_hash(tmp_path / "jobs.sqlite")
    result = audit_state([tmp_path])
    assert {k for k,v in result.items() if v["terminal"]} == {"done","failed"}
    assert before == file_hash(tmp_path / "jobs.sqlite")


def test_helper_failure_called_once_and_cpu_only(tmp_path, monkeypatch):
    calls = []
    def fake(command, **kw):
        calls.append(command)
        assert kw["env"]["CUDA_VISIBLE_DEVICES"] == ""
        return type("Result", (), {"returncode": 3})()
    monkeypatch.setattr("dfm12.export_orchestrator.subprocess.run", fake)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        run_helper(["-m", "dfm12.export_finished"], tmp_path / "helper.log")
    assert len(calls) == 1


def test_lock_wait_timeout_does_not_lose_or_mutate_active_work(tmp_path):
    path = tmp_path / "run.lock"
    with lock(path):
        with pytest.raises(TimeoutError):
            with wait_lock(path, timeout=0):
                pytest.fail("active lock was bypassed")
    with wait_lock(path, timeout=0):
        pass


def test_waiting_final_pass_acquires_after_first_pass(tmp_path):
    import threading
    path = tmp_path / "run.lock"
    acquired = threading.Event()
    errors = []
    def final():
        try:
            with wait_lock(path, timeout=2, interval=0.01):
                acquired.set()
        except Exception as exc:
            errors.append(exc)
    with lock(path):
        thread = threading.Thread(target=final)
        thread.start()
        assert not acquired.wait(0.05)
    thread.join(timeout=3)
    assert acquired.is_set() and not errors


def test_identity_append_preserves_companion_and_is_repeatable(tmp_path, monkeypatch):
    import dfm12.export_identity as identity
    import dfm12.export_validator as validator
    monkeypatch.setattr(validator, "validate", lambda folder: {"rows": 1, "valid": True})
    verified = []
    monkeypatch.setattr(identity, "verify_identity_source", lambda root, companion, packages: verified.append(str(root)))
    staged, output = tmp_path / "stage", tmp_path / "exports"
    packages = []
    for language in ("da", "en", "fo", "is", "nb", "nl", "nn", "pl", "sv"):
        component = "identity-xl-full-bp-" + language
        name = "dfm12-" + component
        write_json(staged / name / "metadata/manifest.json", {"component": component})
        packages.append({"name": name, "component": component, "rows": 1, "data_bytes": 1, "package_bytes": 1})
    source = staged / "metadata/identity-source-manifest.json"
    write_json(source, {"source": "immutable"})
    descriptor = {"file": "metadata/identity-source-manifest.json", "sha256": file_hash(source), "bytes": source.stat().st_size}
    write_json(staged / "manifest.json", {"completed": True, "packages": packages, "identity_source_manifest": descriptor, "rows": 9})
    (staged / "metadata/private-snapshot.sqlite").write_text("never publish or copy as package")
    old = {"name": "dfm12-old", "component": "old", "rows": 2, "data_bytes": 2, "package_bytes": 2}
    write_json(output / "manifest.json", {"packages": [old], "snapshot": "unchanged"})
    merge_identity(staged, output)
    first = load(output / "manifest.json")
    merge_identity(staged, output)
    assert first == load(output / "manifest.json")
    assert first["identity_source_manifest"] == descriptor
    assert first["packages"][0] == old and first["rows"] == 11
    assert not (output / "metadata/private-snapshot.sqlite").exists()
    assert len(verified) == 4
