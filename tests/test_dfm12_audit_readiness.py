import copy
import json
from pathlib import Path
import sqlite3

import pytest

from dfm12 import audit_readiness as ar
from dfm12.io import digest, file_hash, load, write_json
from dfm12.jobs import Queue, audit_payload


def row(i=0, language="pl", task="instruction"):
    return {"id": str(i), "messages": [{"role": "user", "content": f"Question {i}"},
            {"role": "assistant", "content": f"Answer {i}"}], "language": language,
            "task": task, "rendered_tokens": 120,
            "provenance": {"repo": "test/source", "revision": "pinned", "file": "data/source/train.jsonl", "split": "train"}}


def source(tmp_path, records, component="test"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "candidates.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    receipt = tmp_path / "receipt.json"
    write_json(receipt, {"sha256": file_hash(path), "counts": {"candidates": len(records)}})
    return ar.source_entry(component, path, receipt)


def approve(root):
    cfg = ar.config()
    write_json(root / "pilot-approval.json", {"approved": True, "model": cfg["model"],
               "languages": list(cfg["languages"]), "evidence": "Fixture explicit multilingual human pilot review"})


def snapshot(tmp_path, records):
    root, output = tmp_path / "root", tmp_path / "snapshot"
    src = source(root / "input", records)
    gates = root / "gates"
    gates.mkdir()
    write_json(gates / "coverage.json", {"files": [dict(src, state="scanned_stable")]})
    outputs = {}
    for name in ("heldout-quarantine.jsonl", "flagged-chat-rows.jsonl", "source-overlap-groups.jsonl"):
        (gates / name).write_text("")
        outputs[name] = file_hash(gates / name)
    write_json(gates / "audit-manifest.json", {"snapshot_stable_at_finalization": True,
               "coverage_sha256": file_hash(gates / "coverage.json"), "outputs": outputs})
    review = output / "review_only"
    review.mkdir(parents=True)
    staged = Queue(output / "staged_jobs.sqlite")
    metadata, student = [], []
    for r in records:
        r = dict(r, component="test", accepted=False)
        key = staged.add("audit-staged", audit_payload(r, ar.config()["model"]))
        metadata.append({"record": r, "audit_job": key})
        student.extend(ar.student_views(r))
    staged.close()
    for name, data in (("audit_records", metadata), ("student_views", student)):
        (review / (name + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in data))
    write_json(output / "manifest.json", {"snapshot_id": "test", "model": ar.config()["model"], "sources": [src],
               "crossscreen": ar.CrossScreen(gates / "audit-manifest.json").descriptor(),
               "review_records_sha256": file_hash(review / "audit_records.jsonl"),
               "student_views_sha256": file_hash(review / "student_views.jsonl")})
    return root, output


def test_full_file_deterministic_stratification_and_cache(tmp_path):
    records = [row(i, "nb" if i % 2 else "nn", "correction" if i % 3 else "instruction") for i in range(500)]
    for r in records:
        r["rendered_tokens"] = int(r["id"]) * 8
    src = source(tmp_path / "input", records)
    args = (src, 40, 20260924, str(tmp_path / "cache"), ["nb", "nn"])
    result = ar.inspect_source(args)
    assert result == ar.inspect_source(args)
    assert result["counts"]["rows_scanned"] == 500
    assert len(result["selected"]) == 40
    assert max(r["ordinal"] for r in result["selected"]) > 400
    assert {r["row"]["language"] for r in result["selected"]} == {"nb", "nn"}
    assert {r["row"]["task"] for r in result["selected"]} == {"instruction", "correction"}
    assert result["unrepresented_strata"] == 0


def test_input_checksum_change_invalidates_cache(tmp_path):
    src = source(tmp_path / "input", [row()])
    args = (src, 10, 1, str(tmp_path / "cache"), ["pl"])
    ar.inspect_source(args)
    with Path(src["path"]).open("a") as f:
        f.write(json.dumps(row(1)) + "\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        ar.inspect_source(args)


@pytest.mark.parametrize("patch", [{"language": "no"}, {"accepted": True}, {"provenance": {"split": "test"}}])
def test_heldout_and_ambiguous_rows_fail_closed(tmp_path, patch):
    r = row(); r.update(patch)
    src = source(tmp_path / "input", [r])
    with pytest.raises(ValueError):
        ar.inspect_source((src, 10, 1, str(tmp_path / "cache"), ["pl"]))


def test_student_metadata_separation_and_target_preservation():
    r = row(); r.update(target_message_index=1, audit_context={"secret_reference": "DO NOT TRAIN"})
    r["provenance"]["english_anchor"] = "DO NOT TRAIN"
    r["messages"][0]["audit_context"] = "DO NOT TRAIN"
    views = list(ar.student_views(r))
    assert set(views[0]) == {"id", "messages", "target_message_index"}
    assert "DO NOT TRAIN" not in json.dumps(views)
    assert views[0]["target_message_index"] == 1


def test_superseded_snapshot_cannot_activate(tmp_path):
    root, snap = snapshot(tmp_path / "workspace", [row()])
    approve(root)
    write_json(snap.parent.parent / "latest.json", {"snapshot": str(tmp_path / "new-snapshot")})
    with pytest.raises(ValueError, match="Superseded"):
        ar.activate(snap, root)


def test_translation_joint_audit_two_student_views():
    r = row(task="translation")
    r.update(reverse_messages=copy.deepcopy(r["messages"]), reverse_language="fo", pair="fo-pl",
             audit_context={"english_anchor": "untrusted source anchor"})
    views = list(ar.student_views(r))
    assert len(views) == 2 and views[0]["id"] != views[1]["id"]
    assert all(set(v) == {"id", "messages"} for v in views)
    payload = audit_payload(r, "test")
    assert "reverse_messages" in json.loads(payload["request"]["messages"][-1]["content"])


def test_activation_and_exports_blocked_without_pilot(tmp_path):
    root, snap = snapshot(tmp_path, [row()])
    with pytest.raises(ValueError, match="Pilot review required"):
        ar.activate(snap, root)
    with pytest.raises(ValueError, match="Pilot review required"):
        ar.export_accepted(snap, root, tmp_path / "accepted")
    assert not (snap / "approved").exists()
    q = Queue(snap / "staged_jobs.sqlite")
    try:
        assert q.claim("audit", "worker") is None
        assert q.status() == [{"stage": "audit-staged", "status": "pending", "count": 1}]
    finally:
        q.close()


@pytest.mark.parametrize("gate", ["uncovered", "duplicate", "heldout", "missing"])
def test_model_keep_cannot_bypass_crossscreen(tmp_path, gate):
    from dfm12.records import chat_fingerprint
    root, snap = snapshot(tmp_path, [row()])
    manifest = load(snap / "manifest.json")
    gates = root / "gates"
    cross = load(gates / "audit-manifest.json")
    if gate == "missing":
        manifest.pop("crossscreen")
    else:
        if gate == "uncovered":
            write_json(gates / "coverage.json", {"files": []})
            cross["coverage_sha256"] = file_hash(gates / "coverage.json")
        else:
            name, item = (("flagged-chat-rows.jsonl", {"chat_sha256": chat_fingerprint(row()["messages"])})
                          if gate == "duplicate" else
                          ("heldout-quarantine.jsonl", {"source_id": "0", "matching_fields": []}))
            (gates / name).write_text(json.dumps(item) + "\n")
            cross["outputs"][name] = file_hash(gates / name)
        write_json(gates / "audit-manifest.json", cross)
        manifest["crossscreen"] = ar.CrossScreen(gates / "audit-manifest.json").descriptor()
    write_json(snap / "manifest.json", manifest)
    approve(root)
    ar.activate(snap, root)
    q = Queue(snap / "approved/jobs.sqlite")
    job = q.claim("audit", "test")
    q.finish(job[0], "test", 1, result={"keep": True, "language_quality": 5, "coherence": 5,
             "usefulness": 5, "reason": "Model keep cannot override data gates"})
    q.close()
    with pytest.raises(ValueError, match="[Cc]ross-screen"):
        ar.export_accepted(snap, root, tmp_path / "accepted")
    assert not (tmp_path / "accepted").exists()


def test_pilot_model_language_evidence_gate(tmp_path):
    root, snap = snapshot(tmp_path, [row()])
    approve(root)
    approval = load(root / "pilot-approval.json")
    approval["languages"].remove("fo")
    write_json(root / "pilot-approval.json", approval)
    with pytest.raises(ValueError, match="all nine languages"):
        ar.activate(snap, root)


def test_only_explicit_done_keep_exported_and_no_corpus_promotion(tmp_path):
    chosen = row(); chosen["target_message_index"] = 1
    root, snap = snapshot(tmp_path, [chosen, row(1), row(2)])
    approve(root)
    assert ar.activate(snap, root)[0]["count"] == 3
    assert ar.activate(snap, root)[0]["count"] == 3
    with pytest.raises(ValueError, match="No explicitly accepted"):
        ar.export_accepted(snap, root, tmp_path / "empty")
    q = Queue(snap / "approved/jobs.sqlite")
    try:
        first = q.claim("audit", "test")
        q.finish(first[0], "test", 1, result={"keep": True, "language_quality": 5, "coherence": 5, "usefulness": 5, "reason": "Reviewed"})
        second = q.claim("audit", "test")
        q.finish(second[0], "test", 1, result={"keep": False, "language_quality": 2, "coherence": 3, "usefulness": 3, "reason": "Reject"})
    finally:
        q.close()
    out = tmp_path / "accepted"
    result = ar.export_accepted(snap, root, out)
    assert result["accepted_audit_records"] == 1
    student = [json.loads(line) for line in (out / "data/conversations.jsonl").read_text().splitlines()]
    assert len(student) == 1 and student[0]["target_message_index"] == 1
    assert "provenance" not in student[0] and "audit_context" not in student[0]
    assert load(out / "metadata/manifest.json")["tokenization"].startswith("must_rebuild")
    with pytest.raises(FileExistsError):
        ar.export_accepted(snap, root, out)


def test_bad_audit_scores_and_tampered_records_never_export(tmp_path):
    root, snap = snapshot(tmp_path, [row()]); approve(root); ar.activate(snap, root)
    q = Queue(snap / "approved/jobs.sqlite")
    job = q.claim("audit", "test")
    q.finish(job[0], "test", 1, result={"keep": True, "language_quality": 2, "coherence": 5, "usefulness": 5, "reason": "Invalid"})
    q.close()
    with pytest.raises(ValueError, match="contradicts scores"):
        ar.export_accepted(snap, root, tmp_path / "accepted")
    (snap / "review_only/audit_records.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="snapshot changed"):
        ar.activate(snap, root)


def test_transformation_reference_required():
    with pytest.raises(ValueError, match="reference"):
        ar.validate_record(row(task="paragraph-reordering"), ["pl"])


def test_completed_integration_replaces_not_adds_original(tmp_path):
    root = tmp_path / "root"
    original = source(root / "candidates/dynaword-pl", [row()], "dynaword-pl")
    new = source(tmp_path / "integrated", [row(1)], "integrated-pl")
    integration = tmp_path / "integration.json"
    write_json(integration, {"version": 1, "status": "complete_unaudited", "resolves": ["reordering-integration"],
        "supersedes": ["dynaword-pl"], "components": [{k: new[k] for k in ("component", "path", "receipt", "sha256", "family")}]})
    sources, pending = ar.discover(root, [integration])
    assert [s["component"] for s in sources] == ["integrated-pl"]
    assert "reordering-integration" not in pending
    assert "additional-dala" in pending
    integration_data = load(integration); integration_data["status"] = "running"
    write_json(integration, integration_data)
    sources, pending = ar.discover(root, [integration])
    assert [s["component"] for s in sources] == [original["component"]]
    assert str(integration) in pending


def test_refresh_builds_staged_queue_and_reuses_immutable_snapshot(tmp_path):
    root = tmp_path / "root"
    source(root / "candidates/dynaword-pl", [row(i) for i in range(15)], "dynaword-pl")
    output = tmp_path / "readiness"
    result = ar.refresh(root, output, workers=1, limit=10)
    assert result["review_records"] == 10 and result["runnable_audit_jobs"] == 0
    assert not result["accepted"] and result["pilot_gate"] == "required_before_activation"
    assert ar.refresh(root, output, workers=1, limit=10)["snapshot_id"] == result["snapshot_id"]
    q = Queue(Path(result["snapshot"]) / "staged_jobs.sqlite")
    assert q.claim("audit", "test") is None
    assert q.status()[0]["count"] == 10
    q.close()
