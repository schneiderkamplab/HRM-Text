#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

import wandb
from wandb.proto import wandb_internal_pb2
from wandb.sdk.internal.datastore import DataStore


PROJECT = "Original Plus Mixed Danish Instruction Rich L"
SOURCE_RUN_ID = "dfm4xlddpclean"
TARGET_RUN_ID = "dfm4xlddpcleanfixed"
TARGET_RUN_NAME = "dfm4-XL-ddp clean corrected history"

STANDARD_TASKS = ("GSM8k", "DROP", "MMLU", "ARC", "HellaSwag", "Winogrande", "BoolQ", "MATH")
DFM_TASKS = (
    "danish_citizen_tests",
    "dala",
    "gec_dala",
    "wmt24pp_en_da",
    "multi_wiki_qa",
    "piqa",
    "generative_talemaader",
    "govreport",
    "nordjyllandnews",
    "humaneval",
)
LITE_PREFIXES = (
    "lite_eval_noema/",
    "lite_dfm_eval_noema/",
    "lite_eval_ema/",
    "lite_dfm_eval_ema/",
)


def iter_records(path: Path) -> Iterable[wandb_internal_pb2.Record]:
    ds = DataStore()
    ds.open_for_scan(str(path))
    while True:
        data = ds.scan_data()
        if data is None:
            break
        record = wandb_internal_pb2.Record()
        record.ParseFromString(data)
        yield record


def item_key(item) -> str:
    if len(item.nested_key) > 1:
        return ".".join(item.nested_key)
    if len(item.nested_key) == 1:
        return item.nested_key[0]
    return item.key


def item_value(item) -> Any:
    try:
        return json.loads(item.value_json)
    except json.JSONDecodeError:
        return item.value_json


def history_row(record: wandb_internal_pb2.Record) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for item in record.history.item:
        row[item_key(item)] = item_value(item)
    if record.history.HasField("step"):
        row.setdefault("_step", int(record.history.step.num))
    return row


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if key == "_wandb" or value is None:
            continue
        if isinstance(value, float) and not math.isfinite(value):
            continue
        clean[key] = value
    return clean


def discover_wandb_files(root: Path, run_id: str) -> list[Path]:
    return sorted(root.glob(f"run-*-{run_id}/run-{run_id}.wandb"))


def is_plain_full_eval_key(key: str) -> bool:
    return key.startswith("eval/") or key.startswith("dfm_eval/")


def is_lite_eval_key(key: str) -> bool:
    return key.startswith(LITE_PREFIXES)


def should_drop_row(row: dict[str, Any], *, drop_lite: bool = False) -> bool:
    if int(row.get("_step", -1)) == 900000:
        return True
    return any(is_plain_full_eval_key(key) or (drop_lite and is_lite_eval_key(key)) for key in row)


def collect_rows(paths: list[Path], *, drop_lite: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    stats = {
        "files": len(paths),
        "history_records": 0,
        "rows_without_step": 0,
        "dropped_plain_full_eval_or_bad_step_rows": 0,
        "dropped_lite_eval_rows": 0,
        "unreadable_files": 0,
    }
    for path in paths:
        try:
            for record in iter_records(path):
                if record.WhichOneof("record_type") != "history":
                    continue
                stats["history_records"] += 1
                row = clean_row(history_row(record))
                if "_step" not in row:
                    stats["rows_without_step"] += 1
                    continue
                if should_drop_row(row, drop_lite=drop_lite):
                    if any(is_lite_eval_key(key) for key in row):
                        stats["dropped_lite_eval_rows"] += 1
                    stats["dropped_plain_full_eval_or_bad_step_rows"] += 1
                    continue
                rows.append(row)
        except (AssertionError, EOFError, OSError) as exc:
            stats["unreadable_files"] += 1
            print(f"Skipping unreadable W&B datastore {path}: {exc}", flush=True)
    return rows, stats


def coalesce_by_step(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_step: "OrderedDict[int, dict[str, Any]]" = OrderedDict()
    for row in sorted(rows, key=lambda r: (int(r["_step"]), r.get("_timestamp", 0.0), json.dumps(r, sort_keys=True, default=str))):
        step = int(row["_step"])
        target = by_step.setdefault(step, {"_step": step})
        for key, value in row.items():
            if key == "_step":
                continue
            target[key] = value
    return list(by_step.values())


def load_metrics(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{path} does not contain a metrics object")
    return metrics


def load_merged_metrics(path: Path) -> tuple[float | int | None, dict[str, Any]]:
    data = json.loads(path.read_text())
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{path} does not contain a metrics object")
    return data.get("epoch"), metrics


def alias_metrics(metrics: dict[str, Any], old_prefix: str, new_prefix: str) -> dict[str, Any]:
    old = old_prefix + "/"
    return {new_prefix + "/" + key[len(old) :]: value for key, value in metrics.items() if key.startswith(old)}


def full_eval_alias_row(step: int, epoch: float, standard_root: Path, dfm_root: Path) -> dict[str, Any]:
    row: dict[str, Any] = {"_step": step, "eval/epoch": epoch, "dfm_eval/epoch": epoch}
    for task in STANDARD_TASKS:
        row.update(alias_metrics(load_metrics(standard_root / "standard_shards" / task / "merged_metrics.json"), "eval_ema", "eval"))
    for task in DFM_TASKS:
        row.update(alias_metrics(load_metrics(dfm_root / task / "merged_metrics.json"), "dfm_eval_ema", "dfm_eval"))
    row.update(alias_metrics(load_metrics(dfm_root / "merged_ifeval_da_metrics.json"), "dfm_eval_ema", "dfm_eval"))
    for key, value in list(row.items()):
        marker = "dfm_eval/humaneval/verify_sanitized/"
        if key.startswith(marker):
            row["dfm_eval/humaneval/verify/" + key[len(marker) :]] = value
    return row


def checkpoint_tag_steps(checkpoint_path: Path) -> dict[str, int]:
    tags: dict[str, int] = {}
    for path in checkpoint_path.glob("checkpoint_state*.json"):
        data = json.loads(path.read_text())
        tag = data.get("tag")
        step = data.get("step")
        if isinstance(tag, str) and isinstance(step, int):
            tags[tag] = step
    return tags


def classify_lite_artifact(path: Path) -> tuple[str | None, str | None, str | None, Path | None]:
    text = str(path)
    lower = text.lower()
    if "dfm4_xl_ddp" not in lower:
        return None, None, None, None
    if "lite" not in lower:
        return None, None, None, None

    if "noema" in lower:
        variant = "noema"
    elif "ema" in lower:
        variant = "ema"
    else:
        return None, None, None, None

    tag = next((part for part in path.parts if part.startswith("step_") or part.startswith("epoch_")), None)
    if tag is None:
        return None, None, None, None

    if "/logs/eval/" in "/" + text and "/standard_shards/" in text:
        return variant, "standard", tag, path.parents[2]
    if "/logs/dfm_evals/" in "/" + text:
        if path.name == "merged_ifeval_da_metrics.json":
            return variant, "dfm", tag, path.parent
        return variant, "dfm", tag, path.parent.parent
    return None, None, None, None


def discover_lite_roots(log_root: Path) -> dict[tuple[str, str, str], Path]:
    counts: dict[tuple[str, str, str, Path], int] = {}
    mtimes: dict[tuple[str, str, str, Path], float] = {}
    for pattern in ("**/merged_metrics.json", "**/merged_ifeval_da_metrics.json"):
        for path in log_root.glob(pattern):
            variant, suite, tag, root = classify_lite_artifact(path)
            if variant is None or suite is None or tag is None or root is None:
                continue
            key = (variant, suite, tag, root)
            counts[key] = counts.get(key, 0) + 1
            mtimes[key] = max(mtimes.get(key, 0.0), path.stat().st_mtime)

    best: dict[tuple[str, str, str], Path] = {}
    for (variant, suite, tag, root), count in counts.items():
        needed = len(STANDARD_TASKS) if suite == "standard" else len(DFM_TASKS) + 1
        if count < needed:
            continue
        key = (variant, suite, tag)
        current = best.get(key)
        if current is None:
            best[key] = root
            continue
        current_score = (counts[(variant, suite, tag, current)], mtimes[(variant, suite, tag, current)], str(current))
        candidate_score = (count, mtimes[(variant, suite, tag, root)], str(root))
        if candidate_score > current_score:
            best[key] = root
    return best


def lite_repair_row(
    *,
    variant: str,
    tag: str,
    step: int,
    standard_root: Path | None,
    dfm_root: Path | None,
) -> dict[str, Any]:
    standard_prefix = f"lite_eval_{variant}"
    dfm_prefix = f"lite_dfm_eval_{variant}"
    row: dict[str, Any] = {"_step": step}

    if standard_root is not None:
        for task in STANDARD_TASKS:
            epoch, metrics = load_merged_metrics(standard_root / "standard_shards" / task / "merged_metrics.json")
            if epoch is not None:
                row[f"{standard_prefix}/epoch"] = epoch
            row.update(metrics)

    if dfm_root is not None:
        for task in DFM_TASKS:
            epoch, metrics = load_merged_metrics(dfm_root / task / "merged_metrics.json")
            if epoch is not None:
                row[f"{dfm_prefix}/epoch"] = epoch
            row.update(metrics)
        epoch, metrics = load_merged_metrics(dfm_root / "merged_ifeval_da_metrics.json")
        if epoch is not None:
            row[f"{dfm_prefix}/epoch"] = epoch
        row.update(metrics)
    return row


def build_lite_repair_rows(log_root: Path, checkpoint_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    roots = discover_lite_roots(log_root)
    tag_steps = checkpoint_tag_steps(checkpoint_path)
    rows: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []

    tags = sorted({tag for _variant, _suite, tag in roots}, key=lambda tag: tag_steps.get(tag, 10**18))
    for variant in ("noema", "ema"):
        for tag in tags:
            step = tag_steps.get(tag)
            if step is None:
                continue
            standard_root = roots.get((variant, "standard", tag))
            dfm_root = roots.get((variant, "dfm", tag))
            if standard_root is None and dfm_root is None:
                continue
            row = lite_repair_row(
                variant=variant,
                tag=tag,
                step=step,
                standard_root=standard_root,
                dfm_root=dfm_root,
            )
            rows.append(row)
            report.append(
                {
                    "variant": variant,
                    "tag": tag,
                    "step": step,
                    "has_standard": standard_root is not None,
                    "has_dfm": dfm_root is not None,
                    "standard_root": str(standard_root) if standard_root is not None else None,
                    "dfm_root": str(dfm_root) if dfm_root is not None else None,
                }
            )
    return rows, report


def merge_repair_rows(
    rows: list[dict[str, Any]],
    *,
    repair_lite: bool,
    log_root: Path,
    checkpoint_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    repair_rows = [
        full_eval_alias_row(
            367247,
            1.0,
            Path("logs/eval/dfm4_XL_ddp_ema_full_epoch1_20260608/epoch_1"),
            Path("logs/dfm_evals/dfm4_XL_ddp_ema_full_epoch1_20260608/epoch_1"),
        ),
        full_eval_alias_row(
            734484,
            2.0,
            Path("logs/eval/dfm4_XL_ddp_eval_campaign_20260610/full_ema/epoch_2"),
            Path("logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/full_ema/epoch_2"),
        ),
    ]
    lite_report: list[dict[str, Any]] = []
    if repair_lite:
        lite_rows, lite_report = build_lite_repair_rows(log_root, checkpoint_path)
        repair_rows.extend(lite_rows)
    return coalesce_by_step(rows + repair_rows), lite_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wandb-root", type=Path, default=Path("wandb"))
    parser.add_argument("--source-run-id", default=SOURCE_RUN_ID)
    parser.add_argument("--target-project", default=PROJECT)
    parser.add_argument("--target-run-id", default=TARGET_RUN_ID)
    parser.add_argument("--target-run-name", default=TARGET_RUN_NAME)
    parser.add_argument("--log-root", type=Path, default=Path("logs"))
    parser.add_argument("--checkpoint-path", type=Path, default=Path("checkpoints/dfm4/XL-ddp"))
    parser.add_argument("--repair-lite-history", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    paths = discover_wandb_files(args.wandb_root, args.source_run_id)
    if not paths:
        raise FileNotFoundError(f"No local W&B files found for {args.source_run_id}")
    rows, stats = collect_rows(paths, drop_lite=args.repair_lite_history)
    before_coalesce = len(rows)
    rows, lite_report = merge_repair_rows(
        rows,
        repair_lite=args.repair_lite_history,
        log_root=args.log_root,
        checkpoint_path=args.checkpoint_path,
    )

    report = {
        **stats,
        "source_run_id": args.source_run_id,
        "target_run_id": args.target_run_id,
        "target_run_name": args.target_run_name,
        "rows_before_coalesce": before_coalesce,
        "rows_after_coalesce_and_repairs": len(rows),
        "min_step": int(rows[0]["_step"]),
        "max_step": int(rows[-1]["_step"]),
        "contains_step_900000": any(int(row["_step"]) == 900000 for row in rows),
        "train_rows_after_865000": sum(1 for row in rows if int(row["_step"]) >= 865000 and any(key.startswith("train/") for key in row)),
        "lite_repair_rows": lite_report,
        "lite_repair_row_count": len(lite_report),
        "plain_full_eval_rows": [
            {
                "step": int(row["_step"]),
                "eval_epoch": row.get("eval/epoch"),
                "dfm_eval_epoch": row.get("dfm_eval/epoch"),
                "math": row.get("eval/MATH/acc"),
                "nordjyllandnews_chrf3pp": row.get("dfm_eval/nordjyllandnews/chrf3pp/mean"),
            }
            for row in rows
            if "eval/epoch" in row or "dfm_eval/epoch" in row
        ],
        "dry_run": args.dry_run,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.dry_run:
        return

    api = wandb.Api()
    try:
        source = api.run(f"peter-sk-sdu/{args.target_project}/{args.source_run_id}")
        config = dict(source.config)
    except Exception:
        config = {}
    config["_cloned_from_run_id"] = args.source_run_id
    config["_clone_note"] = "Local history replay; artificial step 900000 full-eval aliases removed; full EMA eval aliases relogged at checkpoint steps."
    if args.repair_lite_history:
        config["_clone_note"] += " Lite eval rows were dropped from source history and rebuilt from local merged artifacts at checkpoint steps."

    run = wandb.init(
        project=args.target_project,
        id=args.target_run_id,
        name=args.target_run_name,
        config=config,
        resume="never",
    )
    assert run is not None

    for prefix in ("eval", "dfm_eval", "lite_eval_noema", "lite_dfm_eval_noema", "lite_eval_ema", "lite_dfm_eval_ema"):
        epoch_key = f"{prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)

    for index, row in enumerate(rows, start=1):
        step = int(row["_step"])
        payload = {key: value for key, value in row.items() if key != "_step"}
        if payload:
            wandb.log(payload, step=step, commit=True)
        if index == 1 or index % 5000 == 0 or index == len(rows):
            print(f"replayed {index}/{len(rows)} rows at step {step}", flush=True)

    run.summary.update(
        {
            "clean_history/source_run_id": args.source_run_id,
            "clean_history/replayed_rows": len(rows),
            "clean_history/dropped_plain_full_eval_or_bad_step_rows": stats["dropped_plain_full_eval_or_bad_step_rows"],
            "clean_history/dropped_lite_eval_rows": stats["dropped_lite_eval_rows"],
            "clean_history/lite_repair_row_count": len(lite_report),
            "clean_history/max_step": int(rows[-1]["_step"]),
        }
    )
    wandb.finish()


if __name__ == "__main__":
    main()
