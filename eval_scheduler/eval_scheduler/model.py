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
    TRAIN_UNTIL_STEP = "train_until_step"
    TERMINAL_BARRIER = "terminal_barrier"
    TEARDOWN_EVAL = "teardown_eval"
    WAIT_CHECKPOINT = "wait_checkpoint"
    EXPORT_HF = "export_hf"
    PREPARE_HF_VARIANT = "prepare_hf_variant"
    EVAL_STANDARD = "eval_standard"
    EVAL_DFM = "eval_dfm"
    EVAL_DFM_IFEVAL = "eval_dfm_ifeval"
    EVAL_EUROEVAL = "eval_euroeval"
    EVAL_EUROEVAL_BATCHED_IFEVAL = "eval_euroeval_batched_ifeval"
    MERGE_STANDARD = "merge_standard"
    MERGE_DFM = "merge_dfm"
    MERGE_IFEVAL = "merge_ifeval"
    AVERAGE = "average"
    AVERAGE_LONG_CONTEXT = "average_long_context"
    RELOG_PROJECT_AVERAGES = "relog_project_averages"
    REPORT = "report"


class ExecutionScope(StrEnum):
    CONTROL = "control"
    GPU = "gpu"
    NODE = "node"
    CLUSTER = "cluster"


class Capability(StrEnum):
    CONTROL = "control"
    EVAL = "eval"
    EXPORT = "export"
    TEARDOWN = "teardown"
    TRAIN = "train"


ACTION_PROFILES: dict[Action, tuple[ExecutionScope, Capability, int]] = {
    Action.TRAIN_UNTIL_STEP: (ExecutionScope.CLUSTER, Capability.TRAIN, 0),
    Action.TERMINAL_BARRIER: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.TEARDOWN_EVAL: (ExecutionScope.NODE, Capability.TEARDOWN, 0),
    Action.WAIT_CHECKPOINT: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.EXPORT_HF: (ExecutionScope.GPU, Capability.EXPORT, 1),
    Action.PREPARE_HF_VARIANT: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.EVAL_STANDARD: (ExecutionScope.GPU, Capability.EVAL, 1),
    Action.EVAL_DFM: (ExecutionScope.GPU, Capability.EVAL, 1),
    Action.EVAL_DFM_IFEVAL: (ExecutionScope.GPU, Capability.EVAL, 1),
    Action.EVAL_EUROEVAL: (ExecutionScope.GPU, Capability.EVAL, 1),
    Action.EVAL_EUROEVAL_BATCHED_IFEVAL: (ExecutionScope.GPU, Capability.EVAL, 1),
    Action.MERGE_STANDARD: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.MERGE_DFM: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.MERGE_IFEVAL: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.AVERAGE: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.AVERAGE_LONG_CONTEXT: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.RELOG_PROJECT_AVERAGES: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
    Action.REPORT: (ExecutionScope.CONTROL, Capability.CONTROL, 0),
}


FIELDNAMES = [
    "job_id",
    "action",
    "family",
    "name",
    "shard",
    "shards",
    "deps",
    "deps_mode",
    "initial_batch",
    "max_retries",
    "gpu_policy",
    "execution_scope",
    "required_capability",
    "gpu_count",
    "node_selector",
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
    deps_mode: str = "success"
    initial_batch: int | None = None
    max_retries: int = 3
    gpu_policy: str = "any"
    execution_scope: str = ""
    required_capability: str = ""
    gpu_count: int | None = None
    node_selector: str = ""
    status: JobStatus = JobStatus.PENDING
    attempt: int = 0
    log_dir: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_gpu(self) -> bool:
        return self.action in {
            Action.TRAIN_UNTIL_STEP,
            Action.EXPORT_HF,
            Action.EVAL_STANDARD,
            Action.EVAL_DFM,
            Action.EVAL_DFM_IFEVAL,
            Action.EVAL_EUROEVAL,
            Action.EVAL_EUROEVAL_BATCHED_IFEVAL,
        }

    @property
    def requires_all_gpus(self) -> bool:
        return self.action == Action.TRAIN_UNTIL_STEP or self.gpu_policy == "all"

    @property
    def resolved_execution_scope(self) -> ExecutionScope:
        if self.execution_scope:
            return ExecutionScope(self.execution_scope)
        return ACTION_PROFILES[self.action][0]

    @property
    def resolved_capability(self) -> Capability:
        if self.required_capability:
            capability = Capability(self.required_capability)
            expected = ACTION_PROFILES[self.action][1]
            if capability != expected:
                raise ValueError(
                    f"{self.job_id}: capability {capability.value!r} cannot override "
                    f"the {self.action.value!r} action profile {expected.value!r}"
                )
            return capability
        return ACTION_PROFILES[self.action][1]

    @property
    def resolved_gpu_count(self) -> int:
        if self.gpu_count is not None:
            if self.gpu_count < 0:
                raise ValueError(f"{self.job_id}: gpu_count must be non-negative")
            return self.gpu_count
        return ACTION_PROFILES[self.action][2]

    def retry_batch(self) -> int | None:
        if self.initial_batch is None:
            return None
        if self.metadata.get("fixed_retry_batch"):
            return self.initial_batch
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
            "deps_mode": self.deps_mode,
            "initial_batch": "" if self.initial_batch is None else str(self.initial_batch),
            "max_retries": str(self.max_retries),
            "gpu_policy": self.gpu_policy,
            "execution_scope": self.execution_scope,
            "required_capability": self.required_capability,
            "gpu_count": "" if self.gpu_count is None else str(self.gpu_count),
            "node_selector": self.node_selector,
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
            deps_mode=row.get("deps_mode") or "success",
            initial_batch=int(row["initial_batch"]) if row.get("initial_batch") else None,
            max_retries=int(row.get("max_retries") or 3),
            gpu_policy=row.get("gpu_policy") or "any",
            execution_scope=row.get("execution_scope") or "",
            required_capability=row.get("required_capability") or "",
            gpu_count=int(row["gpu_count"]) if row.get("gpu_count") else None,
            node_selector=row.get("node_selector") or "",
            status=JobStatus(row.get("status") or JobStatus.PENDING.value),
            attempt=int(row.get("attempt") or 0),
            log_dir=row.get("log_dir") or "",
            metadata=json.loads(metadata),
        )

    def to_wire(self) -> dict[str, Any]:
        return self.to_row()

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> Job:
        return cls.from_row({key: str(item) for key, item in value.items()})


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
