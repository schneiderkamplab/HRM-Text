import gzip
import json
import sqlite3

import pytest

from dfm12.audit_full import Database
from dfm12.audit_gates import CrossScreen, FILES
from dfm12.export_finished import build_package, disposition, freeze, views, source_plans, validate_previous
from dfm12.export_validator import validate
from dfm12.io import file_hash, write_json


def gate(tmp_path):
    for name in FILES:
        (tmp_path / name).write_text("")
    write_json(tmp_path / "coverage.json", {"files": []})
    path = tmp_path / "audit-manifest.json"
    write_json(path, {"snapshot_stable_at_finalization": True, "coverage_sha256": file_hash(tmp_path / "coverage.json"),
                      "outputs": {name: file_hash(tmp_path / name) for name in FILES}})
    return CrossScreen(path)


def row(key="one"):
    return {"id": key, "language": "pl", "task": "instruction", "source_record_id": "original-" + key,
            "provenance": {"license": "source-specific", "url": "https://example.org/source"},
            "messages": [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}],
            "audit_source": {"sha256": "sourcehash", "ordinal": 0}}


def decision(keep=True, score=4):
    return json.dumps({"keep": keep, "reason": "Reviewed", "language_quality": score, "coherence": score, "usefulness": score})


def test_only_valid_kept_terminal_rows(tmp_path):
    screen = gate(tmp_path)
    source = {}
    assert disposition(row(), "done", decision(), screen, source)[0] == "accepted"
    for status in ("pending", "running", "failed"):
        assert disposition(row(), status, decision(), screen, source)[0] == "audit_unresolved"
    assert disposition(row(), "done", decision(False), screen, source)[0] == "audit_rejected"
    for value in (decision(score=3), "{}", "null", "bad json"):
        assert disposition(row(), "done", value, screen, source)[0] == "audit_unresolved"
    bad = row()
    bad["messages"][1]["content"] = "<functions>legacy</functions>"
    assert disposition(bad, "done", decision(), screen, source)[0] == "gate_excluded"


def test_filtered_duplicate_resolution_never_bypasses_heldout():
    class Screen:
        def reasons(self, record):
            return ["unresolved_duplicate_chat", "unresolved_shared_source_review", "heldout_quarantine_text"]
    status, _, reasons = disposition(row(), "done", decision(), Screen(), {"authoritative_filtered": True})
    assert status == "gate_excluded"
    assert reasons == ["heldout_quarantine_text"]


def test_student_views_preserve_turns_target_and_original_pair_id():
    record = row()
    record["messages"] *= 2
    record["target_message_index"] = 1
    record["audit_context"] = {"reference": "never student text"}
    assert list(views(record))[0]["messages"] == record["messages"]
    assert list(views(record))[0]["target_message_index"] == 1
    record.update(reverse_messages=row()["messages"], reverse_language="nl")
    forward, reverse = views(record)
    assert forward["parent_pair_id"] == reverse["parent_pair_id"] == "original-one"
    assert forward["language"] == "pl" and reverse["language"] == "nl"
    assert forward["direction"] == "forward" and reverse["direction"] == "reverse"
    assert "audit_context" not in forward and "provenance" not in reverse


def test_multiple_roots_keep_old_source_pins_and_integrity(tmp_path):
    runs = [tmp_path / "main", tmp_path / "swedish"]
    sources = [{"component": "existing", "sha256": "old-pin"},
               {"component": "dala-sv-correction", "sha256": "sv-pin"}]
    for run, source in zip(runs, sources):
        write_json(run / "sources.json", {"sources": [source]})
    output = tmp_path / "exports"
    package = {"name": "dfm12-existing", "component": "existing"}
    data = output / package["name"] / "data.json"
    write_json(data, {"row": 1})
    write_json(output / package["name"] / "metadata/manifest.json", {
        "source": sources[0], "data_files": [{"file": "data.json", "bytes": data.stat().st_size,
                                             "sha256": file_hash(data)}], "metadata_files": []})
    plan = source_plans(runs)
    validate_previous(output, [package], plan)
    with pytest.raises(ValueError, match="owning --run omitted"):
        validate_previous(output, [package], source_plans(runs[1:]))
    with pytest.raises(ValueError, match="Duplicate component"):
        source_plans(runs + runs[:1])
    plan["existing"] = dict(sources[0], sha256="changed")
    with pytest.raises(ValueError, match="source changed"):
        validate_previous(output, [package], plan)
    data.write_text("tampered")
    with pytest.raises(ValueError, match="integrity"):
        validate_previous(output, [package], source_plans(runs))


def test_swedish_freeze_requires_explicit_scoped_authorization(tmp_path, monkeypatch):
    import dfm12.export_finished as exporter
    run = tmp_path / "swedish"
    write_json(run / "sources.json", {"sources": [{"component": "dala-sv-correction"}]})
    with pytest.raises(ValueError, match="excluded"):
        freeze(run, tmp_path / "snapshot")
    def check(sources, authorization, output, crossscreen):
        assert authorization == tmp_path / "auth.json"
        assert output == run and crossscreen == tmp_path / "screen.json"
        raise ValueError("scoped validator reached")
    monkeypatch.setattr(exporter, "validate_sources", check)
    with pytest.raises(ValueError, match="scoped validator reached"):
        freeze(run, tmp_path / "snapshot", authorization=tmp_path / "auth.json",
               crossscreen=tmp_path / "screen.json")


def test_completed_pl_is_forwarded_without_relaxing_default(tmp_path, monkeypatch):
    import dfm12.export_finished as exporter
    run = tmp_path / "pl-is"
    write_json(run / "sources.json", {"sources": [{"component": "dala-pl-correction"}]})
    with pytest.raises(ValueError, match="excluded"):
        freeze(run, tmp_path / "snapshot")
    def check(sources, authorization, output, crossscreen, dala_authorization=None):
        assert authorization is None and output == run
        assert dala_authorization == tmp_path / "completed.json"
        raise ValueError("completed DaLA validator reached")
    monkeypatch.setattr(exporter, "validate_sources", check)
    with pytest.raises(ValueError, match="completed DaLA validator reached"):
        freeze(run, tmp_path / "snapshot", dala_authorization=tmp_path / "completed.json")


def inclusion_root(tmp_path, base, family="norquad-fleurs"):
    from dfm12.scoped_inclusion_audit import SCANDI_COMPONENTS, NORWEGIAN_COMPONENTS
    run = (tmp_path / family).resolve()
    names = SCANDI_COMPONENTS if family == "scandi" else NORWEGIAN_COMPONENTS
    sources = [{"component": name, "path": "/pinned/" + name, "sha256": name} for name in sorted(names)]
    write_json(run / "sources.json", {"sources": sources})
    auth = {"scope": "user_scoped_inclusion_audit_only", "family": family, "user_authorized": True,
            "accepted_exports_allowed": False, "audit_root": str(run),
            "base_crossscreen": {"path": str(base.path), "sha256": file_hash(base.path)},
            "sources": {s["component"]: {"path": s["path"], "sha256": s["sha256"]} for s in sources},
            "pins": {str(run / "sources.json"): file_hash(run / "sources.json")}}
    path = run / "scoped-screen.json"
    write_json(path, auth)
    return run, path, sources


@pytest.mark.parametrize("family", ["scandi", "norquad-fleurs"])
def test_scoped_export_requires_exact_owning_screen(tmp_path, family):
    from dfm12.export_finished import export_contexts
    base = gate(tmp_path)
    run, path, sources = inclusion_root(tmp_path, base, family)
    with pytest.raises(ValueError, match="Invalid source-scoped"):
        export_contexts([run], base.path)
    contexts = export_contexts([run], base.path, inclusion=[path])
    assert contexts[run]["screen"].scoped["family"] == family
    assert contexts[run]["screen"].descriptor()["accepted_exports_allowed"] is False
    assert str(run / "sources.json") in contexts[run]["pins"]
    with pytest.raises(ValueError, match="omitted or multiply"):
        export_contexts([run], base.path, inclusion=[path, path])
    with pytest.raises(ValueError, match="omitted or multiply"):
        export_contexts([], base.path, inclusion=[path])
    with pytest.raises(ValueError, match="Default crossscreen"):
        export_contexts([run], path, inclusion=[path])
    source_plan = {"sources": sources[:-1]}
    write_json(run / "sources.json", source_plan)
    with pytest.raises(ValueError, match="evidence changed"):
        export_contexts([run], base.path, inclusion=[path])


def test_generic_no_portable_validator_matches_scandi_helper():
    from copy import deepcopy
    from dfm12.export_validator import authorized_generic_no, validate_language
    from dfm12.scandi_admission import adapt, authorized_language
    from dfm12.scandi import FILES
    from test_dfm12_scandi_admission import fixture
    source, match = fixture()
    record = adapt(source, FILES[0], 0, [match])
    assert authorized_generic_no(record) and authorized_language(record)
    validate_language(record)
    for field in ("repo", "revision", "admission_policy", "authorization_sha256"):
        changed = deepcopy(record)
        changed["provenance"][field] = "wrong"
        assert not authorized_generic_no(changed)
        with pytest.raises(ValueError, match="Unapproved language"):
            validate_language(changed)
    changed = deepcopy(record)
    changed["messages"][0]["content"] += "changed"
    assert not authorized_generic_no(changed)
    with pytest.raises(ValueError, match="reverse language"):
        validate_language(dict(record, reverse_messages=record["messages"], reverse_language="no"))


def test_identity_inventory_preserves_exact_descriptors_not_blanket_skip(tmp_path, monkeypatch):
    import dfm12.export_identity as identity
    source = {"kind": "generated_identity", "sha256": "original"}
    component = "identity-xl-full-bp-en"
    name = "dfm12-" + component
    write_json(tmp_path / name / "metadata/manifest.json", {"source": source, "data_files": [], "metadata_files": []})
    prior = [{"name": name, "component": component}]
    companion = {"file": "metadata/identity-source-manifest.json"}
    write_json(tmp_path / companion["file"], {"source": source})
    def verify(root, descriptor, packages):
        assert root == tmp_path and descriptor == companion and packages == prior
        return {component: prior[0]}
    monkeypatch.setattr(identity, "verify_identity_source", verify)
    validate_previous(tmp_path, prior, {}, companion)
    with pytest.raises(ValueError, match="owning --run omitted"):
        validate_previous(tmp_path, prior, {})
    with pytest.raises(ValueError, match="Duplicate identity"):
        validate_previous(tmp_path, prior, {component: source}, companion)
    write_json(tmp_path / name / "metadata/manifest.json", {"source": dict(source, sha256="changed"), "data_files": [], "metadata_files": []})
    with pytest.raises(ValueError, match="source changed"):
        validate_previous(tmp_path, prior, {}, companion)


def test_freeze_excludes_unfinished_and_active_sources(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    db = Database(run / "jobs.sqlite")
    sources = []
    for component in ("finished", "active", "preparing"):
        source = {"component": component, "sha256": "sourcehash"}
        sources.append(source)
        db.register(source)
        db.put(source, [(0, row(component), [])])
        if component != "preparing":
            db.complete_source(component)
    db.db.execute("UPDATE jobs SET status='done',result=? WHERE component='finished'", (decision(),))
    db.db.execute("UPDATE jobs SET status='done',result=? WHERE component='preparing'", (decision(),))
    db.close()
    write_json(run / "sources.json", {"sources": sources})
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    result = freeze(run, snapshot)
    assert [s["component"] for s in result["sources"]] == ["finished"]
    copied = sqlite3.connect(snapshot / "snapshot.sqlite")
    assert copied.execute("SELECT component FROM jobs").fetchall() == [("finished",)]
    copied.close()
    incremental = tmp_path / "incremental"
    incremental.mkdir()
    assert freeze(run, incremental, {"finished"})["sources"] == []
    copied = sqlite3.connect(incremental / "snapshot.sqlite")
    assert copied.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    copied.close()


@pytest.mark.parametrize("kept", [True, False])
def test_portable_package_validator_and_empty_policy(tmp_path, kept):
    screen = gate(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    source = {"component": "fixture", "sha256": "sourcehash", "receipt": str(tmp_path / "receipt.json")}
    write_json(source["receipt"], {"accepted": False})
    source["receipt_sha256"] = file_hash(source["receipt"])
    record = row()
    record.update(reverse_messages=row()["messages"], reverse_language="nl")
    attribution = tmp_path / "attribution.json"
    write_json(attribution, {"LICENSE": "source-specific text", "README": "attribution"})
    record["provenance"]["attribution"] = str(attribution)
    record["provenance"].update(title="Original title", history_url="https://example.org/history")
    db = Database(snapshot / "snapshot.sqlite")
    db.register(source)
    db.put(source, [(0, record, [])])
    db.db.execute("UPDATE jobs SET status='done',result=?", (decision(kept),))
    db.close()
    write_json(snapshot / "snapshot.json", {"snapshot_sha256": file_hash(snapshot / "snapshot.sqlite")})
    output = tmp_path / "exports"
    output.mkdir()
    result = build_package(snapshot, source, screen, {"scope": "local_accepted_only_export"}, output)
    package = output / result["name"]
    assert result["rows"] == (2 if kept else 0)
    assert validate(package)["valid"]
    manifest = json.loads((package / "metadata/manifest.json").read_text())
    assert manifest["hf_ready"] is kept
    if not kept:
        assert manifest["admission_status"] == "empty_no_upload"
        assert manifest["upload_ready"] is False
        assert not list((package / "data").iterdir())
    with gzip.open(package / "metadata/audits.jsonl.gz", "rt") as handle:
        audits = [json.loads(line) for line in handle]
    if kept:
        audit = audits[0]
        assert (package / audit["export_provenance"]["attribution"]).exists()
        assert audit["export_provenance"]["title"] == "Original title"
        assert audit["record"]["provenance"]["attribution"] == str(attribution)
    else:
        assert audits == []
        with gzip.open(package / "metadata/exclusions.jsonl.gz", "rt") as handle:
            excluded = json.loads(next(handle))
        assert "record" not in excluded and "record_raw_json" not in excluded
    assert manifest["hf_repo_id"] is None and manifest["upload_performed"] is False
    if kept:
        shard = package / manifest["data_files"][0]["file"]
        shard.write_bytes(b"tampered")
        with pytest.raises(ValueError, match="integrity"):
            validate(package)
def test_authorization_pins_support_swedish_descriptor_list():
    from dfm12.export_finished import authorization_pins
    expected = {"/source/a.json": "abc", "/source/b.json": "def"}
    assert authorization_pins({"pins": expected}) == expected
    assert authorization_pins({"pins": [
        {"path": path, "sha256": checksum} for path, checksum in expected.items()
    ]}) == expected
