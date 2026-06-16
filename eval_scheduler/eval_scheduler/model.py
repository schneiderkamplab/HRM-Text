from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class Action(StrEnum):
    WAIT_CHECKPOINT = "wait_checkpoint"
    EVAL_STANDARD = "eval_standard"
    EVAL_DFM = "eval_dfm"
    EVAL_DFM_IFEVAL = "eval_dfm_ifeval"
    EVAL_EUROEVAL = "eval_euroeval"
    MERGE_STANDARD = "merge_standard"
    MERGE_DFM = "merge_dfm"
    MERGE_IFEVAL = "merge_ifeval"
    AVERAGE = "average"
    REPORT = "report"


FIELDNAMES = [
    "job_id",
    "action",
    "family",
    "name",
    "shard",
    "shards",
    "deps",
    "initial_batch",
    "max_retries",
    "gpu_policy",
    "status",
    "attempt",
    "log_dir",
    "metadata_json",
]


@dataclass(frozen=True)
class Job:
    job_id: str
    action: Action
    family: str
    name: str
    shard: int | None = None
    shards: int | None = None
    deps: tuple[str, ...] = ()
    initial_batch: int | None = None
    max_retries: int = 3
    gpu_policy: str = "any"
    status: JobStatus = JobStatus.PENDING
    attempt: int = 0
    log_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_gpu(self) -> bool:
        return self.action in {
            Action.EVAL_STANDARD,
            Action.EVAL_DFM,
            Action.EVAL_DFM_IFEVAL,
            Action.EVAL_EUROEVAL,
        }

    def retry_batch(self) -> int | None:
        if self.initial_batch is None:
            return None
        batch = self.initial_batch
        for _ in range(max(0, self.attempt)):
            batch = max(1, (batch + 1) // 2)
        return batch

    def with_updates(self, **kwargs: Any) -> Job:
        return replace(self, **kwargs)

    def to_row(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "action": self.action.value,
            "family": self.family,
            "name": self.name,
            "shard": "" if self.shard is None else str(self.shard),
            "shards": "" if self.shards is None else str(self.shards),
            "deps": ",".join(self.deps),
            "initial_batch": "" if self.initial_batch is None else str(self.initial_batch),
            "max_retries": str(self.max_retries),
            "gpu_policy": self.gpu_policy,
            "status": self.status.value,
            "attempt": str(self.attempt),
            "log_dir": self.log_dir,
            "metadata_json": json.dumps(self.metadata, sort_keys=True, separators=(",", ":")),
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Job:
        metadata = row.get("metadata_json") or "{}"
        return cls(
            job_id=row["job_id"],
            action=Action(row["action"]),
            family=row["family"],
            name=row["name"],
            shard=int(row["shard"]) if row.get("shard") else None,
            shards=int(row["shards"]) if row.get("shards") else None,
            deps=tuple(x for x in row.get("deps", "").split(",") if x),
            initial_batch=int(row["initial_batch"]) if row.get("initial_batch") else None,
            max_retries=int(row.get("max_retries") or 3),
            gpu_policy=row.get("gpu_policy") or "any",
            status=JobStatus(row.get("status") or JobStatus.PENDING.value),
            attempt=int(row.get("attempt") or 0),
            log_dir=row.get("log_dir") or "",
            metadata=json.loads(metadata),
        )


def read_plan(path: Path) -> list[Job]:
    if not path.exists():
        return []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [Job.from_row(row) for row in reader]


def write_plan(path: Path, jobs: list[Job]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.to_row())
    tmp.replace(path)


def append_tsv(path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as f:
        f.write("\t".join(fields) + "\n")
