#!/usr/bin/env python3
"""Monitor posttrain transform/refine 1M recovery audit progress."""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from pathlib import Path


EXPECTED_ROWS = {
    0: 65000,
    1: 64000,
    2: 62000,
    3: 60000,
    4: 61000,
    5: 61000,
    6: 63000,
    7: 64000,
}


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except FileNotFoundError:
        return 0


def latest_current_file(log_path: Path) -> str:
    if not log_path.exists():
        return ""

    data = log_path.read_bytes()[-40000:].decode("utf-8", "ignore")
    matches = re.findall(
        r"([^\r\n:]+\.jsonl):\s*(\d+)%\|.*?\|\s*(\d+)/(\d+)",
        data,
    )
    if not matches:
        return ""

    name, _pct, done, total = matches[-1]
    return f" current {Path(name).name} {done}/{total}"


def render_once(audit_root: Path, start_epoch: float) -> None:
    rows_total = 0
    expected_total = sum(EXPECTED_ROWS.values())

    print("posttrain transform/refine audit -> 1M recovery")
    print(f"audit root: {audit_root}")
    print()

    for gpu, expected in EXPECTED_ROWS.items():
        gpu_root = audit_root / f"gpu{gpu}"
        rows = sum(count_lines(path) for path in gpu_root.glob("**/*.audit.jsonl"))
        rows_total += rows
        pct = rows / expected * 100 if expected else 0.0
        current = latest_current_file(audit_root / f"gpu{gpu}.log")
        print(f"GPU{gpu}: {rows:6d}/{expected:6d} rows {pct:5.1f}%{current}")

    elapsed = max(1.0, time.time() - start_epoch)
    rate = rows_total / elapsed
    remaining = max(0, expected_total - rows_total)
    eta = remaining / rate if rate > 0 else 0.0

    print()
    print(f"TOTAL: {rows_total}/{expected_total} rows {rows_total / expected_total * 100:.2f}%")
    print(f"elapsed {elapsed / 60:.1f} min | rate {rate:.1f} rows/s | audit ETA {eta / 60:.1f} min")
    print()

    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        )
    except Exception as exc:  # pragma: no cover - monitor fallback
        print(f"nvidia-smi failed: {exc}")
    else:
        print("GPU memory/util:")
        print(output.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=Path("logs/posttrain_transform_refine_generation/audits_to_1m_resume_20260609T083026"),
    )
    parser.add_argument("--start-epoch", type=float, default=1780986626.659544)
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()

    while True:
        print("\033c", end="")
        print(time.strftime("%F %T %Z"))
        render_once(args.audit_root, args.start_epoch)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
