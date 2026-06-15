#!/usr/bin/env python3
"""Relog HRM evaluation artifacts into clean comparison runs.

The target project uses separate runs for full/lite and EMA/no-EMA variants.
All evaluation metric prefixes are normalized to ``eval/*`` and rows are logged
at the exact training step of the checkpoint.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT = "HRM DFM"

PREFIXES = (
    "eval",
    "eval_ema",
    "eval_noema",
    "dfm_eval",
    "dfm_eval_ema",
    "dfm_eval_noema",
    "lite_eval",
    "lite_eval_ema",
    "lite_eval_noema",
    "lite_eval_noema_real",
    "lite_dfm_eval",
    "lite_dfm_eval_ema",
    "lite_dfm_eval_noema",
    "lite_dfm_eval_noema_real",
)

EPOCH_STEPS: dict[str, dict[str, int]] = {
    "original_sapient_L": {
        "epoch_1": 81478,
        "epoch_2": 162961,
        "epoch_3": 244443,
        "epoch_4": 325928,
    },
    "original_plus_mixed_danish_instruction_rich_L": {
        "epoch_1": 161311,
        "epoch_2": 322628,
        "epoch_3": 483939,
        "epoch_4": 645263,
    },
    "dfm_L": {
        "epoch_1": 164670,
        "epoch_2": 329380,
        "epoch_3": 494080,
        "epoch_4": 658771,
        "step_500000": 500000,
        "step_550000": 550000,
        "step_600000": 600000,
        "step_650000": 650000,
    },
    "dfm4_XL_ddp": {
        "epoch_1": 367247,
        "epoch_2": 734484,
        **{f"step_{step}": step for step in range(50000, 900000, 50000)},
    },
}


@dataclass(frozen=True)
class RootSpec:
    path: Path
    tag: str | None = None


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    run_name: str
    model: str
    suite: str
    weights: str
    roots: tuple[RootSpec, ...]
    raw_original_full: bool = False
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


def root(path: str, tag: str | None = None) -> RootSpec:
    return RootSpec(Path(path), tag)


RUNS: tuple[RunSpec, ...] = (
    RunSpec(
        run_id="original-sapient-L-full-ema",
        run_name="original Sapient L full EMA",
        model="original_sapient_L",
        suite="full",
        weights="ema",
        roots=(root("logs/eval/original_sapient_L"),),
        raw_original_full=True,
        notes="Original standard eval logs parsed from EVALUATION SUMMARY blocks.",
    ),
    RunSpec(
        run_id="original-sapient-L-lite-ema",
        run_name="original Sapient L lite EMA",
        model="original_sapient_L",
        suite="lite",
        weights="ema",
        roots=(
            root("logs/eval/original_sapient_L_lite_all_checkpoints_20260603T213010"),
            root("logs/dfm_evals/original_sapient_L_lite_all_checkpoints_20260603T213010"),
        ),
    ),
    RunSpec(
        run_id="original-sapient-L-lite-noema",
        run_name="original Sapient L lite no-EMA",
        model="original_sapient_L",
        suite="lite",
        weights="noema",
        roots=(
            root("logs/eval/original_sapient_L_cp1_noema_lite_real_20260604T184821"),
            root("logs/dfm_evals/original_sapient_L_cp1_noema_lite_real_20260604T184821"),
            root("logs/eval/original_sapient_L_cp4_noema_lite_real_20260604T181038"),
            root("logs/dfm_evals/original_sapient_L_cp4_noema_lite_real_20260604T181038"),
        ),
    ),
    RunSpec(
        run_id="original-plus-mixed-L-full-ema",
        run_name="original+mixed L full EMA",
        model="original_plus_mixed_danish_instruction_rich_L",
        suite="full",
        weights="ema",
        roots=(
            root("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1", "epoch_1"),
            root("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid", "epoch_2"),
            root("logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all", "epoch_3"),
            root("logs/eval/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all", "epoch_4"),
            root("logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch1_parallel", "epoch_1"),
            root("logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch2_parallel_then_ifeval", "epoch_2"),
            root("logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch3_queued_all", "epoch_3"),
            root("logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_epoch4_queued_all", "epoch_4"),
        ),
        notes="Epochs 1-2 standard logs come from older direct roots; manifest should be checked for coverage.",
    ),
    RunSpec(
        run_id="original-plus-mixed-L-lite-ema",
        run_name="original+mixed L lite EMA",
        model="original_plus_mixed_danish_instruction_rich_L",
        suite="lite",
        weights="ema",
        roots=(
            root("logs/eval/original_plus_mixed_danish_instruction_rich_L_lite_all_checkpoints_20260604T035922"),
            root("logs/dfm_evals/original_plus_mixed_danish_instruction_rich_L_lite_all_checkpoints_20260604T035922"),
        ),
    ),
    RunSpec(
        run_id="dfm-L-full-ema",
        run_name="DFM L full EMA",
        model="dfm_L",
        suite="full",
        weights="ema",
        roots=(
            root("logs/eval/dfm_L_epoch1_queued_all", "epoch_1"),
            root("logs/eval/dfm_L_epoch2_heavy_first_20260531T1102", "epoch_2"),
            root("logs/eval/dfm_L_epoch3_heavy_first_20260531T2227", "epoch_3"),
            root("logs/eval/dfm_L_epoch4_queued_all", "epoch_4"),
            root("logs/dfm_evals/dfm_L_epoch1_queued_all", "epoch_1"),
            root("logs/dfm_evals/dfm_L_epoch2_heavy_first_20260531T1102", "epoch_2"),
            root("logs/dfm_evals/dfm_L_epoch3_heavy_first_20260531T2227", "epoch_3"),
            root("logs/dfm_evals/dfm_L_epoch4_queued_all", "epoch_4"),
        ),
    ),
    RunSpec(
        run_id="dfm-L-lite-ema",
        run_name="DFM L lite EMA",
        model="dfm_L",
        suite="lite",
        weights="ema",
        roots=(
            root("logs/eval/dfm_L_lite_all_checkpoints_20260603T181930"),
            root("logs/dfm_evals/dfm_L_lite_all_checkpoints_20260603T181930"),
        ),
    ),
    RunSpec(
        run_id="dfm4-XL-ddp-full-ema",
        run_name="DFM4 XL-DDP full EMA",
        model="dfm4_XL_ddp",
        suite="full",
        weights="ema",
        roots=(
            root("logs/eval/dfm4_XL_ddp_ema_full_epoch1_20260608"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_full_epoch1_20260608"),
            root("logs/eval/dfm4_XL_ddp_eval_campaign_20260610/full_ema"),
            root("logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/full_ema"),
        ),
    ),
    RunSpec(
        run_id="dfm4-XL-ddp-full-noema",
        run_name="DFM4 XL-DDP full no-EMA",
        model="dfm4_XL_ddp",
        suite="full",
        weights="noema",
        roots=(
            root("logs/eval/dfm4_XL_ddp_noema_full_epoch1_20260608"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_full_epoch1_20260608"),
            root("logs/eval/dfm4_XL_ddp_eval_campaign_20260610/full_noema"),
            root("logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/full_noema"),
        ),
    ),
    RunSpec(
        run_id="dfm4-XL-ddp-lite-ema",
        run_name="DFM4 XL-DDP lite EMA",
        model="dfm4_XL_ddp",
        suite="lite",
        weights="ema",
        roots=(
            root("logs/eval/dfm4_XL_ddp_ema_lite_missing_20260608"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_missing_20260608"),
            root("logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604T064428_200k"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_probe_20260604T064428_200k"),
            root("logs/eval/dfm4_XL_ddp_ema_lite_probe_20260604_250k"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_probe_20260604_250k"),
            root("logs/eval/dfm4_XL_ddp_ema_lite_400k_20260606_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_400k_20260606_tmux"),
            root("logs/eval/dfm4_XL_ddp_ema_lite_650k_20260608_highbs"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_650k_20260608_highbs"),
            root("logs/eval/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs"),
            root("logs/dfm_evals/dfm4_XL_ddp_ema_lite_700k_20260609_lowbs"),
            root("logs/eval/dfm4_XL_ddp_eval_campaign_20260610/lite_ema"),
            root("logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/lite_ema"),
        ),
    ),
    RunSpec(
        run_id="dfm4-XL-ddp-lite-noema",
        run_name="DFM4 XL-DDP lite no-EMA",
        model="dfm4_XL_ddp",
        suite="lite",
        weights="noema",
        roots=(
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_1125"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_1125"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_150k"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_150k"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_250k"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_250k"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_300k"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_300k"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_350k_cp1_20260605_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_350k_cp1_20260605_tmux"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_400k_20260606_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_400k_20260606_tmux"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_450k_20260606_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_450k_20260606_tmux"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_500k_550k_20260607_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_500k_550k_20260607_tmux"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_600k_20260608_tmux"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_600k_20260608_tmux"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_650k_20260608_freegpus"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_650k_20260608_freegpus"),
            root("logs/eval/dfm4_XL_ddp_noema_lite_700k_20260609"),
            root("logs/dfm_evals/dfm4_XL_ddp_noema_lite_700k_20260609"),
            root("logs/eval/dfm4_XL_ddp_eval_campaign_20260610/lite_noema"),
            root("logs/dfm_evals/dfm4_XL_ddp_eval_campaign_20260610/lite_noema"),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-run", action="append", default=[])
    parser.add_argument("--manifest", type=Path, default=Path("logs/wandb_relog_hrm_dfm_manifest.json"))
    parser.add_argument("--resume", default="allow", choices=("allow", "never"))
    return parser.parse_args()


def checkpoint_tag(path: Path, fallback: str | None = None) -> str | None:
    if fallback:
        return fallback
    for part in reversed(path.parts):
        if re.fullmatch(r"epoch_\d+", part) or re.fullmatch(r"step_\d+", part):
            return part
    return None


def epoch_value(model: str, tag: str) -> float | None:
    if tag.startswith("epoch_"):
        return float(tag.removeprefix("epoch_"))

    step = int(tag.removeprefix("step_"))
    boundaries = sorted((v, k) for k, v in EPOCH_STEPS[model].items() if k.startswith("epoch_"))
    prev_step = 0
    prev_epoch = 0
    for boundary_step, boundary_tag in boundaries:
        epoch = int(boundary_tag.removeprefix("epoch_"))
        if step <= boundary_step:
            denom = boundary_step - prev_step
            return prev_epoch + ((step - prev_step) / denom if denom > 0 else 0.0)
        prev_step = boundary_step
        prev_epoch = epoch
    if len(boundaries) >= 2:
        # Best available extrapolation for later intra-epoch checkpoints.
        denom = boundaries[-1][0] - boundaries[-2][0]
        return prev_epoch + ((step - prev_step) / denom if denom > 0 else 0.0)
    return None


def normalize_key(key: str) -> str | None:
    if "/" not in key:
        return None
    prefix, rest = key.split("/", 1)
    if prefix not in PREFIXES:
        return None
    if rest == "epoch":
        return "eval/epoch"
    return f"eval/{rest}"


def maybe_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def load_merged_json(path: Path) -> dict[str, float | int]:
    data = json.loads(path.read_text())
    metrics = data.get("metrics", {})
    out: dict[str, float | int] = {}
    for old_key, value in metrics.items():
        new_key = normalize_key(old_key)
        number = maybe_number(value)
        if new_key and number is not None:
            out[new_key] = number
    return out


def parse_summary_log(path: Path, prefix: str = "eval") -> dict[str, float | int]:
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    if "EVALUATION SUMMARY" not in text:
        return {}
    summary = text.split("EVALUATION SUMMARY", 1)[1]
    parts = re.split(r"\n--- (.*?) ---\n", summary)
    out: dict[str, float | int] = {}
    for idx in range(1, len(parts), 2):
        benchmark = parts[idx].strip().replace(" ", "_").replace("/", "_")
        body = parts[idx + 1]
        for line in body.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            metric = key.rstrip(".").strip().replace(" ", "_").replace("/", "_")
            raw = raw.strip()
            if not re.fullmatch(r"[-+0-9.eE]+", raw):
                continue
            value: float | int = float(raw)
            if metric == "n" or metric.startswith("n_"):
                value = int(value)
            out[f"{prefix}/{benchmark}/{metric}"] = value
    return out


def collect_root_metrics(spec: RunSpec, root_spec: RootSpec) -> dict[str, dict[str, float | int]]:
    root = root_spec.path
    by_tag: dict[str, dict[str, float | int]] = {}
    if not root.exists():
        return by_tag

    if spec.raw_original_full:
        for log_path in sorted(root.glob("epoch_*.log")):
            match = re.fullmatch(r"epoch_(\d+)\.log", log_path.name)
            if not match:
                continue
            tag = f"epoch_{match.group(1)}"
            by_tag.setdefault(tag, {}).update(parse_summary_log(log_path))
        return by_tag

    for json_path in sorted(root.rglob("merged*_metrics.json")):
        tag = checkpoint_tag(json_path, root_spec.tag)
        if tag is None:
            continue
        metrics = load_merged_json(json_path)
        if metrics:
            by_tag.setdefault(tag, {}).update(metrics)

    # Older direct standard eval folders may only have raw summary logs.
    for log_path in sorted(root.glob("*.log")):
        tag = checkpoint_tag(log_path, root_spec.tag)
        if tag is None:
            continue
        metrics = parse_summary_log(log_path)
        if metrics:
            by_tag.setdefault(tag, {}).update(metrics)

    return by_tag


def collect_run(spec: RunSpec) -> dict[str, dict[str, float | int]]:
    by_tag: dict[str, dict[str, float | int]] = {}
    for root_spec in spec.roots:
        root_metrics = collect_root_metrics(spec, root_spec)
        for tag, metrics in root_metrics.items():
            by_tag.setdefault(tag, {}).update(metrics)
    return by_tag


def sorted_tags(model: str, tags: list[str]) -> list[str]:
    steps = EPOCH_STEPS[model]
    return sorted(tags, key=lambda tag: (steps.get(tag, int(tag.removeprefix("step_")) if tag.startswith("step_") else 10**18), tag))


def relog_run(args: argparse.Namespace, spec: RunSpec, rows: dict[str, dict[str, float | int]]) -> dict[str, Any]:
    tags = sorted_tags(spec.model, list(rows))
    summary = {
        "run_id": spec.run_id,
        "run_name": spec.run_name,
        "model": spec.model,
        "suite": spec.suite,
        "weights": spec.weights,
        "num_checkpoints": len(tags),
        "checkpoints": [],
        "notes": spec.notes,
    }
    if args.dry_run:
        for tag in tags:
            summary["checkpoints"].append(
                {
                    "tag": tag,
                    "step": EPOCH_STEPS[spec.model].get(tag),
                    "epoch": epoch_value(spec.model, tag),
                    "num_metrics": len(rows[tag]),
                    "sample_keys": sorted(rows[tag])[:8],
                }
            )
        return summary

    import wandb

    run = wandb.init(
        project=args.project,
        id=spec.run_id,
        name=spec.run_name,
        resume=args.resume,
        tags=("hrm-dfm-relog", f"model:{spec.model}", f"suite:{spec.suite}", f"weights:{spec.weights}", *spec.tags),
        config={
            "source": "local merged evaluation artifacts",
            "model": spec.model,
            "suite": spec.suite,
            "weights": spec.weights,
            "standardized_prefix": "eval",
            "notes": spec.notes,
        },
    )
    assert run is not None
    wandb.define_metric("eval/train_step")
    wandb.define_metric("eval/epoch")
    wandb.define_metric("eval/*", step_metric="eval/train_step")

    for tag in tags:
        step = EPOCH_STEPS[spec.model].get(tag)
        if step is None and tag.startswith("step_"):
            step = int(tag.removeprefix("step_"))
        if step is None:
            raise ValueError(f"No step mapping for {spec.model} {tag}")
        epoch = epoch_value(spec.model, tag)
        row: dict[str, float | int | str] = {
            "eval/train_step": step,
            "eval/checkpoint": tag,
            **rows[tag],
        }
        if epoch is not None:
            row["eval/epoch"] = epoch
        wandb.log(row, step=step)
        label = str(epoch).replace(".", "p") if epoch is not None else tag
        for key, value in rows[tag].items():
            run.summary[f"{key}/{tag}"] = value
            if epoch is not None:
                run.summary[f"{key}/epoch_{label}"] = value
        run.summary["eval/last_train_step"] = step
        if epoch is not None:
            run.summary["eval/last_epoch"] = epoch
        summary["checkpoints"].append(
            {
                "tag": tag,
                "step": step,
                "epoch": epoch,
                "num_metrics": len(rows[tag]),
            }
        )
    wandb.finish()
    return summary


def main() -> None:
    args = parse_args()
    selected = set(args.only_run)
    manifest: dict[str, Any] = {"project": args.project, "dry_run": args.dry_run, "runs": []}
    for spec in RUNS:
        if selected and spec.run_id not in selected:
            continue
        rows = collect_run(spec)
        if not rows:
            manifest["runs"].append({"run_id": spec.run_id, "run_name": spec.run_name, "error": "no metrics found"})
            continue
        manifest["runs"].append(relog_run(args, spec, rows))

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
