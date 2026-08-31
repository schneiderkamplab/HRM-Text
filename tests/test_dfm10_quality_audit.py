from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import dfm10_quality_audit as audit


def test_authoritative_inventory_has_184_unique_sources() -> None:
    specs = audit.source_specs(audit.DEFAULT_INVENTORY_DOC)
    assert len(specs) == 184
    assert len({spec.source_id for spec in specs}) == 184


def test_merge_rejects_incomplete_partitions(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    sample = {
        "sample_id": "abc",
        "source_id": "source",
        "sample_ordinal": 0,
    }
    samples.write_text(json.dumps(sample) + "\n")
    partitions = tmp_path / "parts"
    partitions.mkdir()
    (partitions / "partition_0.jsonl").write_text(json.dumps(sample) + "\n")
    args = SimpleNamespace(
        samples=samples,
        partition_root=partitions,
        partitions=2,
        output=tmp_path / "merged.jsonl",
    )

    with pytest.raises(FileNotFoundError):
        audit.merge(args)


def test_merge_atomically_orders_complete_results(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    rows = [
        {"sample_id": "a", "source_id": "z", "sample_ordinal": 0, "judgment": {"usable_for_training": True}},
        {"sample_id": "b", "source_id": "a", "sample_ordinal": 0, "judgment": {"usable_for_training": False}},
    ]
    samples.write_text("".join(json.dumps(row) + "\n" for row in rows))
    partitions = tmp_path / "parts"
    partitions.mkdir()
    buckets = {0: [], 1: []}
    for row in rows:
        buckets[audit.stable_partition(row["sample_id"], 2)].append(row)
    for partition, bucket in buckets.items():
        (partitions / f"partition_{partition}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in bucket)
        )
    output = tmp_path / "merged.jsonl"
    audit.merge(SimpleNamespace(samples=samples, partition_root=partitions, partitions=2, output=output))

    merged = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["source_id"] for row in merged] == ["a", "z"]


def test_merge_orders_samples_without_optional_ordinal(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    rows = [
        {"sample_id": "source:2", "source_id": "source", "judgment": {"usable_for_training": True}},
        {"sample_id": "source:1", "source_id": "source", "judgment": {"usable_for_training": True}},
    ]
    samples.write_text("".join(json.dumps(row) + "\n" for row in rows))
    partitions = tmp_path / "parts"
    partitions.mkdir()
    buckets = {0: [], 1: []}
    for row in rows:
        buckets[audit.stable_partition(row["sample_id"], 2)].append(row)
    for partition, bucket in buckets.items():
        (partitions / f"partition_{partition}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in bucket)
        )
    output = tmp_path / "merged.jsonl"
    audit.merge(SimpleNamespace(samples=samples, partition_root=partitions, partitions=2, output=output))

    merged = [json.loads(line) for line in output.read_text().splitlines()]
    assert [row["sample_id"] for row in merged] == ["source:1", "source:2"]


def test_resume_discards_retryable_judge_errors(tmp_path: Path) -> None:
    path = tmp_path / "partition.jsonl"
    good = {"sample_id": "good", "judgment": {"usable_for_training": True}}
    failed = {"sample_id": "retry", "judge_error": "timeout"}
    path.write_text(json.dumps(good) + "\n" + json.dumps(failed) + "\n")

    rows, completed = audit.load_resumable(path)

    assert rows == [good]
    assert completed == {"good"}
    assert [json.loads(line) for line in path.read_text().splitlines()] == [good]


def test_raw_package_samples_include_shard_path_in_identity(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    row = {
        "messages": [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ]
    }
    for shard in ("train-00000.jsonl", "train-00001.jsonl"):
        (data / shard).write_text(json.dumps(row) + "\n")
    source = audit.SourceSpec(
        source_id="package",
        generation="dfm10",
        patterns=(),
        form="chat",
        raw_root=str(tmp_path),
    )

    samples, available = audit.reservoir_raw_samples(source, count=2, seed=0)

    assert available == 2
    assert {sample["task_name"] for sample in samples} == {
        "data/train-00000.jsonl",
        "data/train-00001.jsonl",
    }
