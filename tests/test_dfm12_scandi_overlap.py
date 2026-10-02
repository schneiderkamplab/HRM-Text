import json

import pytest

from dfm12.scandi_overlap import comparable, group_result, normalized, text_hash, views
from dfm12.scandi_overlap_finalize import action_for, source_keys


def chat():
    return [{"role": "user", "content": "Question"}, {"role": "assistant", "content": "Answer"}]


def test_reverse_is_a_separate_complete_view():
    original = chat() * 2
    result = views({"messages": original, "reverse_messages": chat()}, "new")
    assert [v[0] for v in result] == ["messages", "reverse_messages"]
    assert result[0][1] == original


def test_upstream_pair_adapter_is_heldout_only():
    row = {"input": "Q", "output": "A"}
    assert views(row, "new") == []
    assert views(row, "heldout")[0][1][1]["content"] == "A"


@pytest.mark.parametrize("messages", [None, [], [None], [{"role": "user", "content": None}],
    [{"role": "assistant", "content": "x", "tool_calls": [{"name": "f"}]}]])
def test_unsupported_chat_schema(messages):
    assert not comparable(messages)


def test_text_hash_ignores_whitespace_not_case():
    assert normalized(" a\n b ") == "a b"
    assert text_hash(" a\n b ") == text_hash("a b")
    assert text_hash("a b") != text_hash("A b")


@pytest.mark.parametrize("scope,action", [
    ("heldout", "exclude_exact_heldout_chat"),
    ("inherited", "quarantine_inherited_duplicate_for_owner_resolution"),
    ("new_alternative", "quarantine_cross_component_duplicate_for_owner_resolution"),
])
def test_collision_actions(scope, action):
    components = {0: {"name": "a", "scope": "new"}, 1: {"name": "b", "scope": scope}}
    result = group_result([(0, 2, 10), (1, 1, 20)], components)
    assert result["action"] == action
    assert result["components"][0]["representative_observation"] == 10
    assert result["components"][0]["occurrences"] == 2


def test_within_component_duplicates_and_irrelevant_groups():
    components = {0: {"name": "new", "scope": "new"}, 1: {"name": "old", "scope": "inherited"}}
    assert group_result([(0, 1, 1)], components) is None
    assert group_result([(1, 2, 1)], components) is None
    assert group_result([(0, 2, 1)], components)["action"] == "deduplicate_within_component_before_acceptance"


def test_heldout_precedence_over_training_duplicates():
    components = {i: {"name": str(i), "scope": scope} for i, scope in
                  enumerate(("new", "inherited", "heldout"))}
    assert group_result([(0, 1, 1), (1, 1, 2), (2, 1, 3)], components)["action"] == "exclude_exact_heldout_chat"


def test_omitted_source_does_not_disqualify_independent_provenance():
    group = {"components": [{"scope": "new", "occurrences": 1}, {"scope": "omitted", "occurrences": 2}]}
    assert action_for(group) == "review_overlap_with_omitted_source_only"
    group["components"].append({"scope": "heldout", "occurrences": 1})
    assert action_for(group) == "exclude_exact_heldout_chat"


def test_omitted_only_is_not_an_active_training_gate():
    assert action_for({"components": [{"scope": "omitted", "occurrences": 4}]}) == "omitted_or_reference_only"


def test_source_window_is_distinct_from_document_reference():
    row = {"audit_context": {"original": "Text " * 50},
           "provenance": {"repo": "r", "revision": "v", "file": "f", "source_id": "s"}}
    keys = dict(source_keys(row))
    assert set(keys) == {"exact_source_window", "same_pinned_document_reference"}
    row["audit_context"]["original"] = "Other text " * 50
    other = dict(source_keys(row))
    assert keys["exact_source_window"] != other["exact_source_window"]
    assert keys["same_pinned_document_reference"] == other["same_pinned_document_reference"]
    row["provenance"]["revision"] = "different"
    assert dict(source_keys(row))["same_pinned_document_reference"] != keys["same_pinned_document_reference"]


def test_source_overlap_records_cross_component_document_references(tmp_path):
    from dfm12.io import file_hash, rows
    from dfm12.scandi_overlap_finalize import source_overlap
    entries = []
    for i, name in enumerate(("dynaword-test", "native-v3:test")):
        path = tmp_path / f"input-{i}.jsonl"
        row = {"id": str(i), "audit_context": {"original": "Shared source window " * 20},
               "provenance": {"repo": "r", "revision": "v", "file": "f", "source_id": "s"}}
        path.write_text(json.dumps(row) + "\n")
        stat = path.stat()
        entries.append({"file_id": i, "path": str(path), "component": name,
                        "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": file_hash(path)})
    result = source_overlap(tmp_path, {"files": entries})
    assert result["cross_component_groups"] == {"exact_source_window": 1, "same_pinned_document_reference": 1}
    groups = list(rows(tmp_path / "source-overlap-groups.jsonl"))
    assert all(len(g["components"]) == 2 for g in groups)
    assert groups[0]["components"][0]["ordinal"] == 0


@pytest.mark.parametrize("change_after_scan", [False, True])
def test_end_to_end_audit_gates_and_snapshot_drift(tmp_path, monkeypatch, change_after_scan):
    import dfm12.scandi_overlap as scan
    import dfm12.scandi_overlap_finalize as final
    from dfm12.io import load, write_json

    held = [{"role": "user", "content": "Long held-out question " * 12},
            {"role": "assistant", "content": "Long held-out answer " * 12}]
    independent = chat()
    entries = []
    for name, scope, records in [
        ("held", "heldout", [{"messages": held}]),
        ("new", "new", [{"id": "held-hit", "messages": held, "reverse_messages": independent}]),
        ("omitted", "omitted", [{"messages": independent}]),
        ("old", "inherited", [{"messages": [{"role": "user", "content": "Legacy"},
                                                {"role": "assistant", "content": "Legacy answer"}]}]),
    ]:
        path = tmp_path / (name + ".jsonl")
        path.write_text("".join(json.dumps(r) + "\n" for r in records))
        stat = path.stat()
        entries.append({"file_id": len(entries), "path": str(path), "component": name,
                        "scope": scope, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    monkeypatch.setattr(scan, "inventory", lambda: (entries, []))
    monkeypatch.setattr(final, "inventory", lambda: (entries, []))
    prior = tmp_path / "prior"
    write_json(prior / "receipt.json", {})
    monkeypatch.setattr(final, "SCANDI", prior)
    monkeypatch.setattr(scan, "disposition", lambda root: write_json(root / "scandi-disposition.json", {"admitted_rows": 0}))
    root = tmp_path / "audit"
    scan.run(root)
    if change_after_scan:
        (tmp_path / "new.jsonl").write_text("{}\n")
    final.finalize(root)
    report = load(root / "audit-manifest.json")
    assert report["snapshot_stable_at_finalization"] is not change_after_scan
    assert report["collision_groups_by_action"]["exclude_exact_heldout_chat"] == 1
    assert report["collision_groups_by_action"]["review_overlap_with_omitted_source_only"] == 1
    assert report["components"]["new"]["distinct_rows_with_heldout_text"] == 1
    assert report["active_heldout_text_quarantine_rows"] == 1
    assert report["flagged_chat_view_occurrences_by_action"]["exclude_exact_heldout_chat"] == 1
    assert report["accepted"] is False
    assert report["components"]["old"]["existing_acceptance_status"] == "unchanged_comparator_only"
    assert "accepted" not in report["components"]["old"]
    if not change_after_scan:
        final.verify(root)
        verification = load(root / "verification.json")
        assert verification["observations_verified"] == 5
        assert len(verification["active_heldout_field_hits_replayed"]) == 2
        assert verification["flagged_chat_views_verified"] == 1
    with pytest.raises(FileExistsError):
        final.finalize(root)
