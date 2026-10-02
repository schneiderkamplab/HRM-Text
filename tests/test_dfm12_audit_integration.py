import pytest

from dfm12.audit_integration import register
from dfm12.io import file_hash, write_json


def test_reordering_registration_has_versioned_contract(tmp_path):
    root = tmp_path / "reordering"
    candidate = root / "candidates/nb/paragraph-reordering.jsonl"
    candidate.parent.mkdir(parents=True)
    candidate.write_text('{}\n')
    write_json(root / "receipt.json", {"counts": {"nb/paragraph-reordering": 1},
               "output_sha256": {"nb/paragraph-reordering": file_hash(candidate)},
               "accepted": 0, "audit_status": "unaudited"})
    write_json(root / "verification.json", {"receipt_sha256": file_hash(root / "receipt.json"),
               "counts": {"nb/paragraph-reordering": 1}, "input_hashes_unchanged": True, "source_replay": True})
    result = register(root, tmp_path / "registration")
    assert result["version"] == 1 and result["status"] == "complete_unaudited"
    assert result["components"][0]["path"] == str(candidate)
    assert len(result["components"][0]["evidence"]) == 2
    candidate.write_text('changed\n')
    with pytest.raises(ValueError, match="checksum"):
        register(root, tmp_path / "bad")
