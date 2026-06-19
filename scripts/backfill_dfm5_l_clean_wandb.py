#!/usr/bin/env python3
"""Create a clean DFM5-L W&B run with replacement 650K eval metrics.

The destination run is a fresh run in the same project. It streams history from
the original DFM5-L run and preserves all rows except that eval-like metrics at
step 650000 are removed and replaced by eval-like metrics streamed from the
clean vLLM 650K+700K W&B run.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable


EVAL_PREFIXES = ("eval/", "dfm_eval/", "euroeval/", "avg/", "headline_avg/")
SYSTEM_KEYS = {"_runtime", "_timestamp", "_step"}


def finite_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def keep_replacement_key(key: str) -> bool:
    if not key.startswith(EVAL_PREFIXES):
        return False
    if "/epoch_" in key:
        return False
    if key.endswith("/last_epoch"):
        return False
    return True


def load_metrics(path: Path) -> dict[str, float | int]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    metrics = data.get("metrics", data)
    if not isinstance(metrics, dict):
        return {}
    out: dict[str, float | int] = {}
    for key, value in metrics.items():
        parsed = finite_number(value)
        if parsed is not None:
            out[str(key)] = parsed
    return out


def collect_standard(root: Path) -> dict[str, float | int]:
    metrics: dict[str, float | int] = {}
    for path in sorted((root / "standard_shards").glob("*/merged_metrics.json")):
        metrics.update(load_metrics(path))
    return metrics


def collect_dfm(root: Path) -> dict[str, float | int]:
    metrics: dict[str, float | int] = {}
    for path in sorted(root.glob("*/merged_metrics.json")):
        metrics.update(load_metrics(path))
    metrics.update(load_metrics(root / "merged_ifeval_da_metrics.json"))
    return metrics


def collect_euroeval(root: Path) -> dict[str, float | int]:
    metrics: dict[str, float | int] = {}
    for path in sorted(root.glob("*/merged_metrics.json")):
        metrics.update(load_metrics(path))
    return metrics


def row_targets_step(row: dict[str, Any], step: int) -> bool:
    if row.get("_step") == step:
        return True
    return any(
        row.get(key) == step
        for key in (
            "eval/train_step",
            "dfm_eval/train_step",
            "euroeval/train_step",
            "avg/train_step",
            "headline_avg/train_step",
        )
    )


def replacement_eval_row_from_wandb_summary(run: Any, *, step: int, epoch: float) -> dict[str, Any]:
    row: dict[str, Any] = {}
    summary = dict(run.summary)
    for key, value in summary.items():
        if not keep_replacement_key(str(key)):
            continue
        parsed = finite_number(value)
        if parsed is not None:
            row[key] = parsed
    if not row:
        raise RuntimeError(f"No eval-like replacement summary metrics found in {run.id}")
    for prefix in ("eval", "dfm_eval", "euroeval", "avg"):
        train_step_key = f"{prefix}/train_step"
        epoch_key = f"{prefix}/epoch"
        if any(key.startswith(f"{prefix}/") for key in row):
            row.setdefault(train_step_key, step)
            row.setdefault(epoch_key, epoch)
    return row


def clean_history_row(row: dict[str, Any], *, replacement_step: int) -> tuple[int | None, dict[str, Any]]:
    step_value = row.get("_step")
    if not isinstance(step_value, int):
        return None, {}
    targets_replacement = row_targets_step(row, replacement_step)
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if key in SYSTEM_KEYS or key.startswith("_"):
            continue
        if targets_replacement and key.startswith(EVAL_PREFIXES):
            continue
        parsed = finite_number(value)
        if parsed is not None:
            cleaned[key] = parsed
    return step_value, cleaned


def iter_source_rows(run: Any, *, page_size: int) -> Iterable[dict[str, Any]]:
    yield from run.scan_history(page_size=page_size)


def define_metrics(wandb: Any) -> None:
    for prefix in ("eval", "dfm_eval", "euroeval", "avg", "headline_avg"):
        epoch_key = f"{prefix}/epoch"
        train_step_key = f"{prefix}/train_step"
        wandb.define_metric(epoch_key)
        wandb.define_metric(train_step_key)
        wandb.define_metric(f"{prefix}/*", step_metric=train_step_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--source-run-id", default="oti1lisg")
    parser.add_argument("--replacement-run-id", default="dfm5-l-vllm-clean-650k-700k-20260618")
    parser.add_argument("--dest-run-id", default="dfm5-l-clean")
    parser.add_argument("--dest-run-name", default="dfm5-L clean")
    parser.add_argument("--replacement-step", type=int, default=650000)
    parser.add_argument("--replacement-epoch", type=float, default=3.5891500036842338)
    parser.add_argument(
        "--standard-root",
        type=Path,
        default=Path("logs/eval/dfm5_L_clean_vllm_650k_700k_20260618/step_650000"),
    )
    parser.add_argument(
        "--dfm-root",
        type=Path,
        default=Path("logs/dfm_evals/dfm5_L_clean_vllm_650k_700k_20260618/step_650000"),
    )
    parser.add_argument(
        "--euroeval-root",
        type=Path,
        default=Path("logs/euroeval/dfm5_L_clean_vllm_650k_700k_20260618/step_650000"),
    )
    parser.add_argument("--audit-jsonl", type=Path, default=Path("logs/backfill_dfm5_l_clean_rows.jsonl"))
    parser.add_argument("--use-existing-audit", action="store_true")
    parser.add_argument("--sanitize-existing-audit", action="store_true")
    parser.add_argument("--wandb-mode", choices=("online", "offline"), default="online")
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import wandb

    api = wandb.Api()
    source = api.run(f"{args.entity}/{args.project}/{args.source_run_id}")
    replacement_source = api.run(f"{args.entity}/{args.project}/{args.replacement_run_id}")

    if args.use_existing_audit or args.sanitize_existing_audit:
        audit_rows_by_step: dict[int, dict[str, Any]] = {}
        replacement = replacement_eval_row_from_wandb_summary(
            replacement_source,
            step=args.replacement_step,
            epoch=args.replacement_epoch,
        )
        for line in args.audit_jsonl.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            step = int(record["step"])
            raw_row = {"_step": step, **dict(record["row"])}
            _clean_step, cleaned = clean_history_row(raw_row, replacement_step=args.replacement_step)
            if cleaned:
                audit_rows_by_step.setdefault(step, {}).update(cleaned)
        audit_rows_by_step.setdefault(args.replacement_step, {}).update(replacement)
        audit_rows = sorted(audit_rows_by_step.items(), key=lambda item: item[0])
        if args.sanitize_existing_audit:
            args.audit_jsonl.parent.mkdir(parents=True, exist_ok=True)
            with args.audit_jsonl.open("w", encoding="utf-8") as f:
                for step, row in audit_rows:
                    f.write(json.dumps({"step": step, "row": row}, sort_keys=True) + "\n")
        counts = {
            "source_rows_seen": "from_existing_audit",
            "source_rows_logged": "from_existing_audit",
            "source_rows_at_replacement_step": "from_existing_audit",
            "replacement_keys": len(replacement),
            "unique_steps_logged": len(audit_rows),
        }
    else:
        replacement = replacement_eval_row_from_wandb_summary(
            replacement_source,
            step=args.replacement_step,
            epoch=args.replacement_epoch,
        )

        counts = {
            "source_rows_seen": 0,
            "source_rows_logged": 0,
            "source_rows_at_replacement_step": 0,
            "replacement_keys": len(replacement),
        }
        audit_rows_by_step: dict[int, dict[str, Any]] = {}

        for raw in iter_source_rows(source, page_size=args.page_size):
            counts["source_rows_seen"] += 1
            step, cleaned = clean_history_row(raw, replacement_step=args.replacement_step)
            if step is None:
                continue
            if step == args.replacement_step:
                counts["source_rows_at_replacement_step"] += 1
            if not cleaned:
                continue
            audit_rows_by_step.setdefault(step, {}).update(cleaned)
            counts["source_rows_logged"] += 1

        audit_rows_by_step.setdefault(args.replacement_step, {}).update(replacement)
        audit_rows = sorted(audit_rows_by_step.items(), key=lambda item: item[0])
        counts["unique_steps_logged"] = len(audit_rows)

        args.audit_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.audit_jsonl.open("w", encoding="utf-8") as f:
            for step, row in audit_rows:
                f.write(json.dumps({"step": step, "row": row}, sort_keys=True) + "\n")

    summary = {
        **counts,
        "dest": f"{args.entity}/{args.project}/{args.dest_run_id}",
        "dest_name": args.dest_run_name,
        "source_name": source.name,
        "replacement_source_name": replacement_source.name,
        "audit_jsonl": str(args.audit_jsonl),
        "replacement_sample_keys": sorted(replacement)[:20],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return

    run = wandb.init(
        entity=args.entity,
        project=args.project,
        id=args.dest_run_id,
        name=args.dest_run_name,
        resume="never",
        config=dict(source.config),
        tags=[*source.tags, "clean-backfill", "650k-vllm-clean"],
        mode=args.wandb_mode,
        settings=wandb.Settings(init_timeout=300),
    )
    assert run is not None
    define_metrics(wandb)
    for step, row in audit_rows:
        wandb.log(row, step=step, commit=True)

    run.summary["clean_backfill/source_run_id"] = args.source_run_id
    run.summary["clean_backfill/replacement_run_id"] = args.replacement_run_id
    run.summary["clean_backfill/replacement_step"] = args.replacement_step
    run.summary["clean_backfill/replacement_epoch"] = args.replacement_epoch
    run.summary["clean_backfill/audit_jsonl"] = str(args.audit_jsonl)
    for key, value in replacement.items():
        run.summary[key] = value
    wandb.finish()


if __name__ == "__main__":
    main()
