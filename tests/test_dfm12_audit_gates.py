import json

import pytest

from dfm12.audit_gates import CrossScreen, pinned_screen
from dfm12.io import file_hash, write_json
from dfm12.records import chat_fingerprint
from dfm12.scandi_overlap import text_hash


def screen(tmp_path):
    messages = [{"role": "user", "content": "A question"}, {"role": "assistant", "content": "An answer"}]
    data = {"heldout-quarantine.jsonl": [{"source_id": "leak", "matching_fields": [
        {"text_sha256": text_hash("private heldout text") }]}],
        "flagged-chat-rows.jsonl": [{"chat_sha256": chat_fingerprint(messages)}],
        "source-overlap-groups.jsonl": [{"components": [{"component": "a", "source_id": "shared"}]}]}
    hashes = {}
    for name, records in data.items():
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in records))
        hashes[name] = file_hash(tmp_path / name)
    write_json(tmp_path / "coverage.json", {"files": [{"path": str(tmp_path / "source"),
               "sha256": "hash", "state": "scanned_stable"}]})
    write_json(tmp_path / "audit-manifest.json", {"snapshot_stable_at_finalization": True,
               "coverage_sha256": file_hash(tmp_path / "coverage.json"), "outputs": hashes})
    return CrossScreen(tmp_path / "audit-manifest.json"), messages


def test_known_leak_survives_component_and_id_changes(tmp_path):
    gate, _ = screen(tmp_path)
    assert "heldout_quarantine_id" in gate.reasons({"source_record_id": "leak"})
    record = {"component": "new-component", "id": "new-id", "messages": [
        {"role": "assistant", "content": " private   heldout text "}]}
    assert "heldout_quarantine_text" in gate.reasons(record)
    assert "heldout_quarantine_reference" in gate.reasons({"audit_context": {"original": "private heldout text"}})


def test_duplicates_include_reverse_and_never_choose_winner(tmp_path):
    gate, messages = screen(tmp_path)
    for field in ("messages", "reverse_messages"):
        assert "unresolved_duplicate_chat" in gate.reasons({field: messages})


def test_source_review_and_legacy_paragraph_gates(tmp_path):
    gate, _ = screen(tmp_path)
    assert gate.reasons({"component": "a", "source_record_id": "shared"})
    assert gate.reasons({"component": "dynaword-nl", "task": "paragraph-reordering"})
    assert not gate.reasons({"component": "dynaword-nl", "task": "denoising"})


def test_coverage_is_exact_file_and_hash(tmp_path):
    gate, _ = screen(tmp_path)
    assert gate.covered({"path": str(tmp_path / "source"), "sha256": "hash"})
    assert not gate.covered({"path": str(tmp_path / "new-source"), "sha256": "hash"})
    assert not gate.covered({"path": str(tmp_path / "source"), "sha256": "changed"})


def test_missing_or_tampered_gate_fails_closed(tmp_path):
    gate, _ = screen(tmp_path)
    descriptor = gate.descriptor()
    assert pinned_screen(descriptor).descriptor() == descriptor
    with pytest.raises(ValueError, match="required"):
        pinned_screen(None)
    (tmp_path / "heldout-quarantine.jsonl").write_text("")
    with pytest.raises(ValueError, match="checksum"):
        pinned_screen(descriptor)
