#!/usr/bin/env python3
"""Incrementally export completed Inspect eval logs and log them to W&B."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect-dir", type=Path, required=True)
    parser.add_argument("--sync-root", type=Path, required=True)
    parser.add_argument("--dfm-evals-dir", type=Path, required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--prefix", default="dfm_eval")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--source-organization-name", default="schneiderkamplab")
    parser.add_argument("--evaluator-relationship", default="first_party")
    parser.add_argument("--inference-provider-name", default="hrm-openai-shim")
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def is_complete_eval(path: Path) -> bool:
    try:
        with ZipFile(path) as zip_file:
            names = set(zip_file.namelist())
    except (BadZipFile, FileNotFoundError):
        return False

    return {"header.json", "summaries.json", "reductions.json"} <= names


def run_command(command: list[str], cwd: Path) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def sync_one(args: argparse.Namespace, eval_log: Path, marker: Path) -> None:
    safe_stem = eval_log.stem.replace("/", "_")
    item_root = args.sync_root / safe_stem
    logs_dir = item_root / "eval_logs"
    eee_dir = item_root / "eee"
    logs_dir.mkdir(parents=True, exist_ok=True)

    link = logs_dir / eval_log.name
    if not link.exists():
        link.symlink_to(eval_log.resolve())

    run_command(
        [
            "uv",
            "run",
            "--project",
            str(args.dfm_evals_dir),
            "evals",
            "eee",
            "inspect",
            "--log-path",
            str(logs_dir),
            "--output-dir",
            str(eee_dir),
            "--source-organization-name",
            args.source_organization_name,
            "--evaluator-relationship",
            args.evaluator_relationship,
            "--inference-base-url",
            args.base_url,
            "--inference-provider-name",
            args.inference_provider_name,
        ],
        cwd=args.repo_root,
    )

    run_command(
        [
            sys.executable,
            "scripts/log_dfm_evals_to_wandb.py",
            "--eee-dir",
            str(eee_dir),
            "--epoch",
            str(args.epoch),
            "--project",
            args.project,
            "--run-id",
            args.run_id,
            "--run-name",
            args.run_name,
            "--prefix",
            args.prefix,
        ],
        cwd=args.repo_root,
    )

    marker.write_text(f"{eval_log.resolve()}\n", encoding="utf-8")
    print(f"Synced completed eval log: {eval_log.name}", flush=True)


def sync_pass(args: argparse.Namespace) -> int:
    marker_dir = args.sync_root / ".synced"
    marker_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    for eval_log in sorted(args.inspect_dir.glob("*.eval")):
        marker = marker_dir / f"{eval_log.name}.done"
        if marker.exists() or not is_complete_eval(eval_log):
            continue

        sync_one(args, eval_log, marker)
        synced += 1

    return synced


def main() -> None:
    args = parse_args()
    args.sync_root.mkdir(parents=True, exist_ok=True)

    if args.once:
        synced = sync_pass(args)
        print(f"Synced {synced} completed eval log(s).", flush=True)
        return

    while True:
        try:
            sync_pass(args)
        except Exception as exc:  # noqa: BLE001
            print(f"Incremental dfm-evals sync failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
