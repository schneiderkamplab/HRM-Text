import pytest

from dfm12.audit_gates import CrossScreen
from dfm12.io import file_hash, write_json
from dfm12.scoped_inclusion_audit import SCOPE, validate_screen
from test_dfm12_audit_gates import screen


def scoped(tmp_path):
    base, messages = screen(tmp_path)
    output = tmp_path / "isolated"
    output.mkdir()
    source_manifest = output / "sources.json"
    write_json(source_manifest, {"sources": []})
    path = output / "scoped-screen.json"
    write_json(path, {"scope": SCOPE, "family": "norquad-fleurs", "user_authorized": True,
                     "accepted_exports_allowed": False, "audit_root": str(output),
                     "base_crossscreen": {"path": str(base.path), "sha256": file_hash(base.path)},
                     "sources": {"scandi-nb": {"path": "/pinned/source", "sha256": "pinned"}},
                     "pins": {str(source_manifest): file_hash(source_manifest)}})
    record = {"component": "scandi-nb", "source_record_id": "leak",
              "audit_source": {"path": "/pinned/source", "sha256": "pinned"},
              "messages": [{"role": "assistant", "content": "private heldout text"}]}
    return CrossScreen(path), base, record, messages


def test_only_scoped_heldout_gate_overridden(tmp_path):
    gate, base, record, _ = scoped(tmp_path)
    assert not gate.reasons(record)
    assert set(base.reasons(record)) == {"heldout_quarantine_id", "heldout_quarantine_text"}
    assert gate.descriptor()["accepted_exports_allowed"] is False
    assert gate.descriptor()["benchmarks_clear"] is False


def test_duplicate_and_tool_gates_stay(tmp_path):
    gate, _, record, messages = scoped(tmp_path)
    assert "unresolved_duplicate_chat" in gate.reasons(dict(record, messages=messages))
    tool = [{"role": "assistant", "content": "<function_calls>old format</function_calls>"}]
    assert "legacy_xml_tool_flattening_requires_quarantine" in gate.reasons(dict(record, messages=tool))


@pytest.mark.parametrize("change", [{"component": "other"}, {"audit_source": {"path": "/pinned/source", "sha256": "changed"}}, {"audit_source": {}}])
def test_scope_cannot_spread(tmp_path, change):
    gate, _, record, _ = scoped(tmp_path)
    with pytest.raises(ValueError, match="outside pinned"):
        gate.reasons(dict(record, **change))


def test_changed_evidence_refused(tmp_path):
    gate, _, _, _ = scoped(tmp_path)
    (gate.path.parent / "sources.json").write_text("{}")
    with pytest.raises(ValueError, match="evidence changed"):
        validate_screen(gate.path)


def test_scandi_heldout_override_requires_message_bound_lineage(tmp_path):
    from copy import deepcopy
    from dfm12.scandi import FILES
    from dfm12.scandi_admission import adapt
    from test_dfm12_scandi_admission import fixture
    gate, _, record, _ = scoped(tmp_path)
    gate.scoped["family"] = "scandi"
    assert "heldout_quarantine_id" in gate.reasons(record)
    row, match = fixture()
    authorized = dict(adapt(row, FILES[0], 0, [match]), component=record["component"],
                      source_record_id="leak", audit_source=record["audit_source"])
    assert "heldout_quarantine_id" not in gate.reasons(authorized)
    changed = deepcopy(authorized)
    changed["messages"][0]["content"] += " modified"
    assert "heldout_quarantine_id" in gate.reasons(changed)


def test_readiness_generic_no_is_scoped():
    from copy import deepcopy
    from dfm12.audit_readiness import validate_record
    from dfm12.scandi import FILES
    from dfm12.scandi_admission import adapt
    from test_dfm12_scandi_admission import fixture
    row, match = fixture()
    record = adapt(row, FILES[0], 0, [match])
    validate_record(record, {"nb", "nn"})
    changed = deepcopy(record)
    changed["provenance"]["revision"] = "other"
    with pytest.raises(ValueError, match="language"):
        validate_record(changed, {"nb", "nn"})


def test_completed_scandi_handoff(tmp_path, monkeypatch):
    from dfm12 import scoped_inclusion_audit as runner
    from dfm12.io import load
    from dfm12.scandi import FILES
    from dfm12.scandi_admission import adapt, POLICY, AUTHORIZATION_SHA256
    from test_dfm12_scandi_admission import fixture
    base, _ = screen(tmp_path)
    monkeypatch.setattr(runner, "BASE", base.path)
    parent = tmp_path / "parent"
    parent.mkdir()
    write_json(parent / "operational-approval.json", {"scope": "automated_audit_only", "accepted_exports_allowed": False})
    monkeypatch.setattr(runner, "PARENT", parent)
    integration = tmp_path / "integration"
    integration.mkdir()
    row, match = fixture()
    record = dict(adapt(row, FILES[0], 0, [match]), rendered_tokens=15)
    path = integration / "candidates.jsonl"
    import json
    path.write_text(json.dumps(record) + "\n")
    receipt = integration / "receipt.json"
    write_json(receipt, {"sha256": file_hash(path), "status": "complete_unaudited", "accepted": False,
                         "counts": {"candidates": 1}, "policy": POLICY})
    for name in ("overlap-coverage.json", "overlap-resolutions.jsonl", "exclusions.jsonl"):
        (integration / name).write_text("{}\n")
    write_json(integration / "integration.json", {"version": 1, "status": "complete_unaudited", "policy": POLICY,
               "authorization_sha256": AUTHORIZATION_SHA256,
               "components": [{"component": "scandi-included-no", "path": str(path), "receipt": str(receipt),
                               "sha256": file_hash(path), "family": "instruction", "authoritative_filtered": True}]})
    output = tmp_path / "audit"
    assert runner.prepare("scandi", integration / "integration.json", output)["scandi-included-no"]["candidates"] == 1
    assert load(output / "sources.json")["sources"][0]["authoritative_filtered"]
    assert not CrossScreen(output / "scoped-screen.json").descriptor()["accepted_exports_allowed"]
