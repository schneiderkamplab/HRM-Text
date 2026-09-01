import importlib.util
from pathlib import Path
import sys

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_dfm11_fineinstructions_nemotron",
    ROOT / "scripts/prepare_dfm11_fineinstructions_nemotron.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
ShardPair = MODULE.ShardPair
ShardedWriter = MODULE.ShardedWriter
approval_is_valid = MODULE.approval_is_valid
obvious_pii_reason = MODULE.obvious_pii_reason
ordered_pairs = MODULE.ordered_pairs


def test_ordered_pairs_is_deterministic_and_seeded() -> None:
    pairs = [ShardPair(i, f"train-{i}", f"judge-{i}", 1, 1) for i in range(20)]
    first = [item.index for item in ordered_pairs(pairs, 17)]
    assert first == [item.index for item in ordered_pairs(reversed(pairs), 17)]
    assert first != [item.index for item in ordered_pairs(pairs, 18)]


def test_obvious_pii_gate() -> None:
    assert obvious_pii_reason("Write to person@example.org", "Done") == "email"
    assert obvious_pii_reason("Connect to 192.168.1.10", "Done") == "ipv4"
    assert obvious_pii_reason("Call +45 12 34 56 78", "Done") == "phone_like"
    assert obvious_pii_reason("Explain photosynthesis", "Plants use light.") is None


def test_approval_receipt_is_fail_closed(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.yaml"
    assert not approval_is_valid(receipt)
    receipt.write_text(
        "license_approved: true\n"
        "pii_audit_passed: true\n"
        "source_copy_audit_passed: true\n"
        "benchmark_decontamination_passed: true\n"
        "task_quality_audit_passed: true\n",
        encoding="utf-8",
    )
    assert approval_is_valid(receipt)


def test_sharded_writer_emits_native_messages(tmp_path: Path) -> None:
    writer = ShardedWriter(tmp_path, rows_per_shard=1)
    writer.add(
        {
            "messages": [
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": "Answer"},
            ],
            "source_repo": "example/source",
            "source_revision": "abc",
            "source_shard": "data/train.parquet",
            "source_row_index": 3,
            "warc_record_id": "record",
            "template_id": 4,
            "upstream_judge_score": 5,
            "synthetic_token_count": 7,
        }
    )
    assert writer.total == 1
    row = pq.read_table(tmp_path / "part-00000.parquet").to_pylist()[0]
    assert row["messages"][-1] == {"role": "assistant", "content": "Answer"}
