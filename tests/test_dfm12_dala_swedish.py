import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

from dfm12.audit_full import validate_sources
from dfm12.dala_integrate import conversations, screen, text_hash
from dfm12.dala_sv_audit import prepare, validate_authorization, validate_client_limits


@pytest.mark.parametrize("limit", [128, 256])
def test_explicitly_authorized_higher_concurrency(limit):
    auth = {"max_client_concurrency_per_endpoint": limit, "max_preparation_workers": 1,
            "endpoints": ["one", "two"]}
    validate_client_limits(auth, limit, 1, ["one", "two"])
    with pytest.raises(ValueError):
        validate_client_limits(auth, limit + 1, 1, ["one", "two"])
from dfm12.io import file_hash, load, write_json
from tests.test_dfm12_dala_integrate import pair, manifest


def test_swedish_standard_and_train_only():
    views = list(conversations(pair("sv"), manifest("sv")["prompts"], "pin"))
    assert len(views) == 4
    assert {v["language"] for v in views} == {"sv"}
    assert [v["messages"][-1]["content"] for v in views] == ["yes", "no", "Good words", "Good words"]
    with pytest.raises(ValueError):
        list(conversations(pair("sv", split="test"), manifest("sv")["prompts"], "pin"))
    with pytest.raises(ValueError):
        list(conversations(pair("sv"), manifest("nb")["prompts"], "pin"))


def test_swedish_screen_prior_train_prior_heldout_new_heldout_and_late(tmp_path):
    seed = tmp_path / "seed.sqlite"
    db = sqlite3.connect(seed)
    for table in ("seen", "held", "held_docs"):
        db.execute(f"CREATE TABLE {table}(hash TEXT PRIMARY KEY)")
    db.execute("INSERT INTO seen VALUES (?)", (text_hash("Good previous train"),))
    db.execute("INSERT INTO seen VALUES (?)", (text_hash("Good prior train only"),))
    db.execute("INSERT INTO held VALUES (?)", (text_hash("Good previous held"),))
    db.execute("INSERT INTO held_docs VALUES (?)", ("prior-held-doc",))
    db.commit()
    db.close()
    original_seed = file_hash(seed)
    train = [pair("sv", identifier=str(i), text=t) for i, t in enumerate([
        "Good previous train", "Good previous held", "Good new held", "Good late",
        "Good retained", "Good previous document", "Good prior train only"])]
    train[-2]["document_sha256"] = "prior-held-doc"
    held = [pair("sv", "test", "h1", "Good new held"), pair("sv", "test", "h2", "Good previous train")]
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "documents.jsonl").write_text("".join(json.dumps(p) + "\n" for p in train + held))
    for split, values in (("train", train), ("validation", []), ("test", held)):
        (raw / split).mkdir()
        (raw / split / "pairs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in values))
    m = manifest("sv")
    m["splits"] = {"train": {"pairs": 7}, "validation": {"pairs": 0}, "test": {"pairs": 2}}
    inputs = {"scope": ["sv"], "sources": {"sv": {"raw": str(raw), "selected": str(raw),
              "raw_manifest": m, "selected_manifest": m}},
              "late_exclusions": {"sv": [{"original_sha256": hashlib.sha256(b"Good late").hexdigest()}]}}
    out = tmp_path / "out"
    out.mkdir()
    result = screen(inputs, out, seed)
    counts = result["counts"]["sv"]
    assert counts["screened_pairs"] == 1
    assert counts["heldout_text_pairs"] == 3
    assert counts["heldout_document_pairs"] == 1
    assert counts["late_excluded_pairs"] == 1
    assert counts["normalized_duplicate_pairs"] == 1
    assert counts["new_heldout_text_matching_previous_train"] == 1
    assert file_hash(seed) == original_seed


@pytest.mark.parametrize("language", ["sv", "pl", "is"])
def test_default_audit_still_rejects(language):
    with pytest.raises(ValueError, match="excluded"):
        validate_sources([{"component": f"dala-{language}-correction"}])


def test_bounded_client():
    auth = {"max_client_concurrency_per_endpoint": 1, "max_preparation_workers": 1, "endpoints": ["one"]}
    validate_client_limits(auth, 1, 1, ["one"])
    for c, w, endpoints in [(2, 1, ["one"]), (1, 2, ["one"]), (1, 1, ["other"])]:
        with pytest.raises(ValueError):
            validate_client_limits(auth, c, w, endpoints)


def test_authorization_pins_scope_evidence_and_separate_root(tmp_path):
    root, out, parent = [tmp_path / p for p in ("import", "audit", "parent")]
    root.mkdir()
    parent.mkdir()
    write_json(parent / "operational-approval.json", {"fixture": True})
    write_json(parent / "configuration.json", {"endpoints": ["one"]})
    exclusions = root / "late.json"
    write_json(exclusions, {"sv": []})
    seed = root / "seed.sqlite"
    seed.write_bytes(b"fixture")
    write_json(root / "previous-screen.json", {"seed": str(seed), "seed_sha256": file_hash(seed)})
    write_json(root / "inputs.json", {"scope": ["sv"], "late_exclusions_receipt": {"path": str(exclusions), "sha256": file_hash(exclusions)}})
    write_json(root / "screening.json", {"status": "complete_local_screen"})
    write_json(root / "tokenizer.json", {})
    entries = []
    for task in ("acceptability", "correction"):
        path, receipt = root / (task + ".jsonl"), root / (task + "-receipt.json")
        path.write_text("fixture\n")
        write_json(receipt, {"sha256": file_hash(path), "language": "sv", "status": "complete_unaudited"})
        entries.append({"component": "dala-sv-" + task, "path": str(path), "receipt": str(receipt),
                        "sha256": file_hash(path), "family": "instruction", "evidence": []})
    write_json(root / "integration.json", {"status": "complete_unaudited", "integrated_languages": ["sv"], "components": entries})
    write_json(root / "verification.json", {"status": "verified_unaudited", "integration_sha256": file_hash(root / "integration.json")})
    with patch("dfm12.dala_sv_audit.CrossScreen") as cross, patch("dfm12.dala_sv_audit.verify_inputs") as verify:
        cross.return_value.descriptor.return_value = {"fixture": "pinned"}
        authorization = prepare(root, out, parent, tmp_path / "cross")
        sources = load(out / "sources.json")["sources"]
        validate_sources(sources, authorization, out, tmp_path / "cross")
        assert verify.called
        with pytest.raises(ValueError):
            validate_authorization(sources, authorization, parent, tmp_path / "cross")
        with pytest.raises(ValueError):
            validate_authorization(sources + [{"component": "dala-pl-correction"}], authorization, out, tmp_path / "cross")
        write_json(exclusions, {"sv": ["new late exclusion"]})
        with pytest.raises(ValueError, match="Late exclusions changed"):
            validate_authorization(sources, authorization, out, tmp_path / "cross")
        write_json(exclusions, {"sv": []})
        write_json(root / "screening.json", {"status": "changed"})
        with pytest.raises(ValueError, match="evidence changed"):
            validate_authorization(sources, authorization, out, tmp_path / "cross")
