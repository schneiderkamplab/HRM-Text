from copy import deepcopy

from dfm12.screening_application import heldout_matches, semantic_key
from dfm12.scandi_overlap import text_hash
from dfm12.records import chat_fingerprint


def record():
    return {"id": "a", "messages": [{"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "next"},
            {"role": "assistant", "content": "last"}], "language": "nb",
            "task": "instruction", "provenance": {"repo": "one"}}


def test_only_attribution_differences_deduplicate():
    a, b = record(), record()
    b.update(id="b", provenance={"repo": "two"}, rendered_tokens=100, audit_context={"original": "doc"})
    assert semantic_key(a) == semantic_key(b)


def test_targets_tools_language_and_unknown_fields_are_significant():
    a = record()
    for key, value in [("target_message_index", 1), ("tools", []),
                       ("language", "nn"), ("unknown_render_option", True)]:
        b = dict(a, **{key: value})
        assert semantic_key(a) != semantic_key(b)
    b = deepcopy(a)
    b["messages"][1]["tool_calls"] = [{"id": "x"}]
    assert semantic_key(a) != semantic_key(b)


def test_full_multiturn_and_reverse_preserved():
    a = record()
    b = deepcopy(a)
    b["messages"][3]["content"] = "other"
    assert semantic_key(a) != semantic_key(b)
    assert semantic_key(a) != semantic_key(dict(a, reverse_messages=a["messages"]))


def test_whitespace_is_not_semantic_equality():
    a, b = record(), record()
    b["messages"][0]["content"] += " "
    assert semantic_key(a) != semantic_key(b)


def test_heldout_matches_whole_field_or_whole_chat_not_shared_document():
    row = record()
    text = "heldout " * 30
    row["audit_context"] = {"original": text}
    refs = [{"ordinal": 48}]
    assert heldout_matches(row, {text_hash(text): refs}, {})
    assert not heldout_matches(row, {text_hash(text + "extra"): refs}, {})
    assert heldout_matches(row, {}, {chat_fingerprint(row["messages"]): refs})


def test_short_field_is_not_heldout_exclusion():
    assert not heldout_matches(record(), {text_hash("answer"): [{}]}, {})


def test_materialization_and_independent_replay(tmp_path, monkeypatch):
    import json
    import sqlite3
    from types import SimpleNamespace
    from dfm12 import screening_application as app
    from dfm12.io import file_hash, write_json, rows
    from dfm12.screening_application_verify import verify

    def jsonl(name, records):
        path = tmp_path / name
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        return path

    first = record()
    duplicate = dict(first, id="duplicate", provenance={"repo": "second"})
    distinct = dict(first, id="distinct-target", target_message_index=1)
    held = dict(first, id="held", messages=[{"role": "user", "content": "heldout " * 30},
                                            {"role": "assistant", "content": "response"}])
    source = jsonl("source.jsonl", [first, duplicate, distinct, held])
    heldout = jsonl("held.jsonl", [held])
    jsonl("flagged-chat-rows.jsonl", [{"file_id": 0, "ordinal": n} for n in range(3)])
    jsonl("heldout-quarantine.jsonl", [{"file_id": 0}])
    write_json(tmp_path / "coverage.json", {"files": [
        {"file_id": 0, "path": str(source), "sha256": file_hash(source), "component": "example", "scope": "new"},
        {"file_id": 1, "path": str(heldout), "sha256": file_hash(heldout), "component": "held", "scope": "heldout"}],
        "components": {"0": {"name": "inherited", "scope": "inherited"}}, "missing_coverage": ["fixture"]})
    inherited = deepcopy(first)
    inherited["id"] = "new-inherited-match"
    inherited["messages"][0]["content"] = "inherited prompt"
    fresh = deepcopy(first)
    fresh["id"] = "fresh"
    fresh["messages"][0]["content"] = "fresh prompt"
    addition = jsonl("addition.jsonl", [inherited, fresh])
    integration = tmp_path / "integration.json"
    write_json(integration, {"status": "complete_unaudited", "components": [
        {"component": "new-integration", "path": str(addition), "sha256": file_hash(addition),
         "family": "instruction"}]})
    with sqlite3.connect(tmp_path / "observations.sqlite") as db:
        db.execute("CREATE TABLE observations(hash BLOB,component INTEGER,file INTEGER,ordinal INTEGER,source_id TEXT)")
        db.execute("INSERT INTO observations VALUES (?,0,9,12,'old')",
                   (bytes.fromhex(chat_fingerprint(inherited["messages"])),))
    monkeypatch.setattr(app, "CrossScreen", lambda _: SimpleNamespace(evidence={}, heldout_ids={"held"}))
    output = tmp_path / "output"
    before = source.read_bytes()
    result = app.run(tmp_path, [integration], output)
    assert result["counts"]["heldout_match"] == 1
    assert result["counts"]["exact_semantic_duplicate"] == 1
    assert result["counts"]["inherited_chat_match_quarantine"] == 1
    assert source.read_bytes() == before
    kept = list(rows(output / "candidates/example/candidates.jsonl"))
    assert kept == [first, distinct]
    assert list(rows(output / "candidates/new-integration/candidates.jsonl")) == [fresh]
    from dfm12.audit_readiness import discover
    discovered, _ = discover(tmp_path / "empty-base", [output / "integration.json"])
    assert {s["component"] for s in discovered} == {"example", "new-integration"}
    assert all(s["sha256"] == file_hash(s["path"]) for s in discovered)
    assert verify(output)["counts"]["semantic_duplicate_decisions_replayed"] == 1
    with (output / "candidates/example/candidates.jsonl").open("a") as handle:
        handle.write(json.dumps(held) + "\n")
    import pytest
    with pytest.raises(ValueError, match="Output changed"):
        verify(output)
