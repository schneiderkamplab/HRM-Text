import gzip
import hashlib
import json

import pytest

from dfm12.candidate_token_snapshot import scan
from dfm12.export_token_accounting import count_package
from dfm12.io import file_hash


def test_pair_tokens_count_once(tmp_path):
    path = tmp_path / "source.jsonl"
    path.write_text(json.dumps({"rendered_tokens": 101, "reverse_messages": []}) + "\n")
    row = scan({"path": str(path), "sha256": file_hash(path), "component": "opus-en-nl"})
    assert row["records"] == 1
    assert row["training_rows"] == 2
    assert row["rendered_tokens"] == 101


def test_source_hash_mismatch(tmp_path):
    path = tmp_path / "source.jsonl"
    path.write_text('{"rendered_tokens": 22}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        scan({"path": str(path), "sha256": hashlib.sha256(b"wrong").hexdigest(), "component": "test"})


def test_missing_tokens_not_zero_coverage(tmp_path):
    path = tmp_path / "source.jsonl"
    path.write_text('{}\n')
    row = scan({"path": str(path), "sha256": file_hash(path), "component": "test"})
    assert row["missing_token_records"] == 1
    assert "rendered_tokens" not in row


@pytest.mark.parametrize("accepted", [True, False])
def test_export_disposition_and_counts(tmp_path, accepted):
    path = tmp_path / "audits.jsonl.gz"
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    with gzip.open(path, "wt") as handle:
        handle.write(json.dumps({"disposition": "accepted" if accepted else "rejected", "status": "done",
                                 "audit": {"keep": accepted}, "record": {"rendered_tokens": 43}}) + "\n")
    item = {"audit_path": str(path), "audit_sha256": file_hash(path), "audit_bytes": path.stat().st_size,
            "manifest_path": str(manifest), "manifest_sha256": file_hash(manifest),
            "counts": {"accepted": 1, "training_rows": 1}, "package": "test", "component": "test",
            "family": "instruction", "category": "other_instruction"}
    if accepted:
        assert count_package(item)["preserved_rendered_tokens"] == 43
    else:
        with pytest.raises(ValueError, match="Nonaccepted"):
            count_package(item)
