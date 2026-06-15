#!/usr/bin/env python3
"""Rebalance export dataset audits around a per-dataset token target.

This is intentionally a conservative process-level controller. The current
8-GPU audit runner owns all vLLM servers via one parent shell, so killing a
single audit worker is not safe. A rebalance round stops the current tmux
session, then relaunches only unfinished datasets as stable hash shards that
skip already-audited row ids.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "export"

DATASETS = [
    "common-pile-denoising",
    "common-pile-paragraph-reordering",
    "common-pile-prefix-continuation",
    "common-pile-span-filling",
    "danish-dynaword-denoising",
    "danish-dynaword-paragraph-reordering",
    "danish-dynaword-prefix-continuation",
    "danish-dynaword-span-filling",
]

DEFAULT_TARGET_TOKENS = 100_000_000

TARGET_TOKENS_BY_DATASET = {
    "common-pile-paragraph-reordering": 50_000_000,
    "danish-dynaword-paragraph-reordering": 50_000_000,
}

AVG_TOKENS = {
    "common-pile-denoising": 398.1,
    "common-pile-paragraph-reordering": 818.3,
    "common-pile-prefix-continuation": 207.5,
    "common-pile-span-filling": 397.8,
    "danish-dynaword-denoising": 1898.4,
    "danish-dynaword-paragraph-reordering": 916.5,
    "danish-dynaword-prefix-continuation": 954.3,
    "danish-dynaword-span-filling": 1845.7,
}

MODEL_PATH = ROOT / "data/models/google/gemma-4-31B-it-fresh-20260604"
FALLBACK_MODEL_PATH = Path("/work/dfm/brainsurgery/models/google/gemma-4-31B-it")
SERVED_MODEL = "posttrain-gemma-teacher"


@dataclass
class Counts:
    keep: int = 0
    drop: int = 0

    @property
    def audited(self) -> int:
        return self.keep + self.drop


def run(cmd: list[str], *, check: bool = False, **kwargs):
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, **kwargs)


def latest_log_root() -> Path | None:
    roots = sorted((ROOT / "logs").glob("export_dataset_audits_*"), key=lambda p: p.stat().st_mtime)
    return roots[-1] if roots else None


def audit_files(dataset: str) -> list[Path]:
    base = EXPORT / dataset
    files = []
    for path in sorted(base.glob("audit*/audit.jsonl")):
        if path.is_file():
            files.append(path)
    return files


def count_audits(dataset: str) -> Counts:
    counts = Counts()
    for path in audit_files(dataset):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("keep") is True:
                    counts.keep += 1
                else:
                    counts.drop += 1
    return counts


def target_tokens_for(dataset: str, default_target_tokens: float) -> float:
    return TARGET_TOKENS_BY_DATASET.get(dataset, default_target_tokens)


def status(default_target_tokens: float) -> dict[str, dict[str, float]]:
    out = {}
    for dataset in DATASETS:
        counts = count_audits(dataset)
        tokens = counts.keep * AVG_TOKENS[dataset]
        target_tokens = target_tokens_for(dataset, default_target_tokens)
        out[dataset] = {
            "accepted_rows": counts.keep,
            "dropped_rows": counts.drop,
            "audited_rows": counts.audited,
            "estimated_tokens": tokens,
            "target_tokens": target_tokens,
            "complete": tokens >= target_tokens,
            "reject_rate": (counts.drop / counts.audited) if counts.audited else 0.0,
        }
    return out


def print_status(default_target_tokens: float) -> None:
    stats = status(default_target_tokens)
    total = 0.0
    for dataset, row in stats.items():
        total += row["estimated_tokens"]
        print(
            f"{dataset:42s} "
            f"{row['estimated_tokens'] / 1e6:8.1f}M/{row['target_tokens'] / 1e6:.1f}M "
            f"accepted={int(row['accepted_rows']):8d} "
            f"drop={int(row['dropped_rows']):7d} "
            f"reject={row['reject_rate'] * 100:5.1f}% "
            f"{'done' if row['complete'] else 'open'}"
        )
    print("-" * 112)
    print(f"total_estimated_tokens={total / 1e6:.1f}M")


def kill_current_session(session: str, log_root: Path | None) -> None:
    run(["tmux", "kill-session", "-t", session], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if log_root is not None:
        for pid_file in (log_root / "pids").glob("*.pid"):
            try:
                pid = int(pid_file.read_text().strip())
            except Exception:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    time.sleep(5)


def allocate_shards(open_datasets: list[str], gpus: list[int]) -> dict[str, list[int]]:
    """Allocate GPUs to open datasets, weighted by remaining target tokens."""
    assignment = {d: [] for d in open_datasets}
    if not open_datasets:
        return assignment
    stats = status(float("inf"))
    weights = {}
    for d in open_datasets:
        # Paragraph reordering is slow and high-rejection; give it extra weight.
        task_weight = 2.0 if d.endswith("paragraph-reordering") else 1.0
        weights[d] = max(1.0, task_weight * (1.0 + stats[d]["dropped_rows"] / max(1.0, stats[d]["accepted_rows"])))
    ordered = sorted(open_datasets, key=lambda d: weights[d], reverse=True)
    for idx, gpu in enumerate(gpus):
        d = ordered[idx % len(ordered)]
        assignment[d].append(gpu)
    return assignment


def parse_allocation_override(allocation: str, open_datasets: list[str], *, allow_partial: bool = False) -> dict[str, list[int]]:
    open_set = set(open_datasets)
    assignment = {d: [] for d in open_datasets}
    seen_gpus = set()
    for item in allocation.split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid allocation item {item!r}; expected dataset:gpu,gpu")
        dataset, gpu_text = item.split(":", 1)
        dataset = dataset.strip()
        if dataset not in open_set:
            raise ValueError(f"Allocation dataset {dataset!r} is not currently open")
        gpus = [int(x) for x in gpu_text.split(",") if x.strip()]
        if not gpus:
            raise ValueError(f"Allocation dataset {dataset!r} has no GPUs")
        for gpu in gpus:
            if gpu in seen_gpus:
                raise ValueError(f"GPU {gpu} is assigned more than once")
            seen_gpus.add(gpu)
        assignment[dataset] = gpus
    missing = [d for d, gpus in assignment.items() if not gpus]
    if missing and not allow_partial:
        raise ValueError(f"Allocation is missing open datasets: {', '.join(missing)}")
    if allow_partial:
        assignment = {d: gpus for d, gpus in assignment.items() if gpus}
    return assignment


def start_server(gpu: int, port: int, log_root: Path, args: argparse.Namespace) -> subprocess.Popen:
    model = str(MODEL_PATH if MODEL_PATH.exists() else FALLBACK_MODEL_PATH)
    server_log = (log_root / "servers" / f"gpu{gpu}.log").open("w", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "CUDA_VISIBLE_DEVICES": str(gpu),
            "VLLM_DEEP_GEMM_WARMUP": "skip",
            "TORCHINDUCTOR_CACHE_DIR": str(log_root / "cache" / f"gpu{gpu}" / "torchinductor"),
            "TRITON_CACHE_DIR": str(log_root / "cache" / f"gpu{gpu}" / "triton"),
        }
    )
    cmd = [
        args.vllm_python,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model,
        "--served-model-name",
        SERVED_MODEL,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--tensor-parallel-size",
        "1",
        "--max-model-len",
        str(args.max_model_len),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--max-num-seqs",
        str(args.max_num_seqs),
    ]
    if args.enforce_eager:
        cmd.append("--enforce-eager")
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=server_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (log_root / "pids" / f"vllm_gpu{gpu}.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc


def wait_server(port: int, timeout: int = 900) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/v1/models"
    while time.time() < deadline:
        proc = run(["curl", "-fsS", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for vLLM server on port {port}")


def start_audit_worker(
    dataset: str,
    gpu: int,
    port: int,
    shard_index: int,
    num_shards: int,
    log_root: Path,
    args: argparse.Namespace,
) -> subprocess.Popen:
    dataset_dir = EXPORT / dataset
    audit_root = dataset_dir / f"audit_rebalance_{log_root.name}_shard{shard_index:02d}of{num_shards:02d}"
    skip_args = []
    for path in audit_files(dataset):
        skip_args.extend(["--skip-audit", str(path)])
    cmd = [
        args.client_python,
        "recreate_dataset.py",
        "audit",
        "--base-url",
        f"http://127.0.0.1:{port}/v1",
        "--model",
        SERVED_MODEL,
        "--sample-rate",
        "1.0",
        "--concurrency",
        str(args.concurrency),
        "--audit-root",
        str(audit_root),
        "--num-shards",
        str(num_shards),
        "--shard-index",
        str(shard_index),
        "--force",
        *skip_args,
    ]
    log = (log_root / "audits" / f"{dataset}_gpu{gpu}_shard{shard_index:02d}.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=dataset_dir,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    (log_root / "pids" / f"audit_{dataset}_gpu{gpu}_shard{shard_index:02d}.pid").write_text(f"{proc.pid}\n", encoding="utf-8")
    return proc


def rebalance(args: argparse.Namespace) -> None:
    stats = status(args.target_tokens)
    open_datasets = [d for d in DATASETS if not stats[d]["complete"]]
    if not open_datasets:
        print("All datasets have reached target.")
        return

    old_root = latest_log_root()
    if args.stop_current:
        print(f"Stopping current session {args.session} and log root {old_root}")
        kill_current_session(args.session, old_root)

    timestamp = time.strftime("%Y%m%dT%H%M%S")
    log_root = ROOT / "logs" / f"export_dataset_audits_rebalance_{timestamp}"
    (log_root / "servers").mkdir(parents=True, exist_ok=True)
    (log_root / "audits").mkdir(parents=True, exist_ok=True)
    (log_root / "pids").mkdir(parents=True, exist_ok=True)
    (log_root / "cache").mkdir(parents=True, exist_ok=True)

    gpus = [int(x) for x in args.gpus.split(",") if x.strip()]
    if args.allocation:
        allocation = parse_allocation_override(args.allocation, open_datasets, allow_partial=args.allow_partial_allocation)
    else:
        allocation = allocate_shards(open_datasets, gpus)
    print("Allocation:")
    print(json.dumps(allocation, indent=2, sort_keys=True))

    port = args.port_base
    workers = []
    for dataset, dataset_gpus in allocation.items():
        if not dataset_gpus:
            continue
        num_shards = len(dataset_gpus)
        for shard_index, gpu in enumerate(dataset_gpus):
            start_server(gpu, port, log_root, args)
            wait_server(port)
            workers.append(start_audit_worker(dataset, gpu, port, shard_index, num_shards, log_root, args))
            port += 1

    manifest = {
        "default_target_tokens": args.target_tokens,
        "target_tokens_by_dataset": TARGET_TOKENS_BY_DATASET,
        "open_datasets": open_datasets,
        "allocation": allocation,
        "allocation_override": args.allocation,
        "log_root": str(log_root),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (log_root / "rebalance_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Rebalance launched: {log_root}")


def watch(args: argparse.Namespace) -> None:
    initial_complete = {d for d, row in status(args.target_tokens).items() if row["complete"]}
    while True:
        stats = status(args.target_tokens)
        complete = [d for d, row in stats.items() if row["complete"]]
        open_datasets = [d for d, row in stats.items() if not row["complete"]]
        newly_complete = sorted(set(complete) - initial_complete)
        print(
            json.dumps(
                {
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "complete": complete,
                    "newly_complete": newly_complete,
                    "open": open_datasets,
                    "default_target_tokens": args.target_tokens,
                    "target_tokens_by_dataset": TARGET_TOKENS_BY_DATASET,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if newly_complete and open_datasets:
            args.stop_current = True
            rebalance(args)
            return
        if not open_datasets:
            print("All datasets have reached target.", flush=True)
            return
        time.sleep(args.interval_seconds)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["status", "rebalance", "watch"])
    ap.add_argument("--target-tokens", type=float, default=DEFAULT_TARGET_TOKENS)
    ap.add_argument("--session", default="export_audits_8gpu")
    ap.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    ap.add_argument("--allocation", default=None, help="Manual allocation as 'dataset:gpu,gpu;dataset:gpu'.")
    ap.add_argument("--allow-partial-allocation", action="store_true", help="Allow --allocation to omit open datasets.")
    ap.add_argument("--port-base", type=int, default=8400)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--vllm-python", default="python")
    ap.add_argument("--client-python", default="python")
    ap.add_argument("--max-model-len", type=int, default=8192)
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    ap.add_argument("--max-num-seqs", type=int, default=64)
    ap.add_argument("--enforce-eager", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--stop-current", action="store_true")
    ap.add_argument("--interval-seconds", type=int, default=300)
    args = ap.parse_args()

    if args.command == "status":
        print_status(args.target_tokens)
    elif args.command == "rebalance":
        rebalance(args)
    elif args.command == "watch":
        watch(args)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
