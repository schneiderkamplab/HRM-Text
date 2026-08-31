#!/usr/bin/env python3
"""Maintain the atomic status list for the ordered DFM10 residual audits."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_stages(config: Path) -> list[dict[str, object]]:
    document = yaml.safe_load(config.read_text(encoding="utf-8"))
    stages = document.get("stages", []) if isinstance(document, dict) else []
    if not stages:
        raise ValueError(f"no stages in {config}")
    return stages


def locked_state(args: argparse.Namespace, mutate) -> dict[str, object]:
    args.run_root.mkdir(parents=True, exist_ok=True)
    lock_path = args.run_root / "state.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = args.run_root / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        updated = mutate(state)
        atomic_write(state_path, updated)
        return updated


def initialize(args: argparse.Namespace) -> None:
    stages = load_stages(args.config)

    def mutate(state: dict[str, object]) -> dict[str, object]:
        old = {item["id"]: item for item in state.get("stages", [])}
        rows = []
        for position, stage in enumerate(stages, start=1):
            stage_id = str(stage["id"])
            previous = old.get(stage_id, {})
            status = previous.get("status", "pending")
            message = previous.get("message", "")
            if status in {"preparing", "running"}:
                status = "pending"
                message = "Recovered stale in-progress state after runner restart."
            rows.append(
                {
                    "position": position,
                    "id": stage_id,
                    "description": str(stage.get("description", "")),
                    "status": status,
                    "message": message,
                    "updated_at": previous.get("updated_at", now()),
                    "samples": previous.get("samples"),
                }
            )
        return {"config": str(args.config), "updated_at": now(), "stages": rows}

    locked_state(args, mutate)


def set_status(args: argparse.Namespace) -> None:
    def mutate(state: dict[str, object]) -> dict[str, object]:
        found = False
        for row in state.get("stages", []):
            if row["id"] != args.stage:
                continue
            found = True
            row["status"] = args.status
            row["message"] = args.message
            row["updated_at"] = now()
            if args.samples is not None:
                row["samples"] = args.samples
        if not found:
            raise ValueError(f"unknown stage {args.stage}")
        state["updated_at"] = now()
        return state

    locked_state(args, mutate)


def show(args: argparse.Namespace) -> None:
    state_path = args.run_root / "state.json"
    if not state_path.exists():
        raise SystemExit(f"missing state: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    print("pos\tstatus\tsamples\tstage\tmessage")
    for row in state["stages"]:
        samples = "" if row.get("samples") is None else str(row["samples"])
        print(f"{row['position']}\t{row['status']}\t{samples}\t{row['id']}\t{row.get('message', '')}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--config", type=Path, required=True)
    init.add_argument("--run-root", type=Path, required=True)
    init.set_defaults(func=initialize)
    update = commands.add_parser("set")
    update.add_argument("--run-root", type=Path, required=True)
    update.add_argument("--stage", required=True)
    update.add_argument("--status", required=True)
    update.add_argument("--message", default="")
    update.add_argument("--samples", type=int)
    update.set_defaults(func=set_status)
    status = commands.add_parser("status")
    status.add_argument("--run-root", type=Path, required=True)
    status.set_defaults(func=show)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
