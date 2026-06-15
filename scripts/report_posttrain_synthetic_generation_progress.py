#!/usr/bin/env python3
"""Report progress for sharded post-training synthetic generation."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-root", type=Path, default=Path("data/synthetic_request_shards_posttrain_transform_refine"))
    parser.add_argument("--generated-root", type=Path, default=Path("data/generated_posttrain_transform_refine"))
    parser.add_argument("--log-root", type=Path, default=Path("logs/posttrain_transform_refine_generation"))
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=30.0)
    return parser.parse_args()


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def progress_once(args: argparse.Namespace) -> str:
    pending = sorted((args.shard_root / "pending").glob("*.jsonl"))
    running = sorted((args.shard_root / "running").glob("*.jsonl.gpu*"))
    done = sorted((args.shard_root / "done").glob("*.jsonl"))
    failed = sorted((args.shard_root / "failed").glob("*.jsonl"))
    generated = sorted(args.generated_root.glob("*.jsonl"))

    total_shards = len(pending) + len(running) + len(done) + len(failed)
    total_requests = 0
    manifest = args.shard_root / "manifest.json"
    if manifest.exists():
        try:
            total_requests = int(json.loads(manifest.read_text()).get("total_rows") or 0)
        except Exception:
            total_requests = 0
    done_requests = sum(count_lines(path) for path in generated)

    lines = [
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} shards done={len(done)}/{total_shards} running={len(running)} pending={len(pending)} failed={len(failed)} generated_rows={done_requests}/{total_requests or '?'}",
    ]

    worker_dir = args.log_root / "workers"
    for log in sorted(worker_dir.glob("gpu*.log")):
        text = log.read_text(errors="replace")[-20_000:]
        starts = re.findall(r"START .* shard=(\S+)", text)
        dones = re.findall(r"DONE .* shard=(\S+)", text)
        fails = re.findall(r"FAIL .* shard=(\S+)", text)
        active = starts[-1] if len(starts) > len(dones) + len(fails) else "-"
        lines.append(f"{log.stem}: active={active} done={len(dones)} failed={len(fails)}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.watch:
        while True:
            print(progress_once(args), flush=True)
            time.sleep(args.interval)
    else:
        print(progress_once(args))


if __name__ == "__main__":
    main()
