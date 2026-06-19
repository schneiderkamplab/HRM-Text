#!/usr/bin/env python3
"""Log EuroEval JSONL results to W&B under a separate prefix."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import wandb


DEFAULT_PREFIX = "euroeval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--epoch", type=float, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--language", action="append", default=None)
    parser.add_argument("--log-wandb", action="store_true")
    parser.add_argument("--project", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--resume", default="allow", choices=("allow", "must"))
    return parser.parse_args()


def sanitize(value: str) -> str:
    value = value.strip().replace(" ", "_").replace("/", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("._-") or "unknown"


def maybe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    return None


def iter_records(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc


def flatten_scores(scores: Any, prefix: tuple[str, ...] = ()):
    if isinstance(scores, dict):
        for key, value in scores.items():
            yield from flatten_scores(value, (*prefix, str(key)))
        return
    value = maybe_float(scores)
    if value is not None:
        yield prefix, value


def parse_languages(record: dict[str, Any]) -> list[str]:
    language = record.get("language")
    if language is not None:
        return [str(language)]

    languages = record.get("languages")
    if languages is not None:
        return [str(lang) for lang in languages]

    details = record.get("eval_library", {}).get("additional_details", {})
    raw_languages = details.get("languages")
    if isinstance(raw_languages, str):
        try:
            parsed = json.loads(raw_languages)
        except json.JSONDecodeError:
            parsed = raw_languages
        if isinstance(parsed, list):
            return [str(lang) for lang in parsed]
        return [str(parsed)]
    if isinstance(raw_languages, list):
        return [str(lang) for lang in raw_languages]
    return []


def record_dataset(record: dict[str, Any]) -> str:
    details = record.get("eval_library", {}).get("additional_details", {})
    return str(record.get("dataset") or details.get("dataset") or "unknown")


def record_task(record: dict[str, Any]) -> str:
    details = record.get("eval_library", {}).get("additional_details", {})
    return str(record.get("task") or details.get("task") or "unknown")


def collect_legacy_results_metrics(
    record: dict[str, Any],
    prefix: str,
    lang_key: str,
    dataset: str,
    task: str,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    scores = record.get("results", {})
    for path_parts, value in flatten_scores(scores):
        if not path_parts:
            continue
        if "raw" in path_parts:
            continue
        metric = "/".join(sanitize(part) for part in path_parts)
        key = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{metric}"
        metrics[key] = value
    return metrics


def collect_euroeval_v17_metrics(
    record: dict[str, Any],
    prefix: str,
    lang_key: str,
    dataset: str,
    task: str,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    results = record.get("evaluation_results")
    if not isinstance(results, list):
        return metrics

    for result in results:
        if not isinstance(result, dict):
            continue
        metric_name = sanitize(str(result.get("evaluation_name", "score")))
        if metric_name.startswith("test_"):
            metric_name = metric_name[len("test_") :]

        score_details = result.get("score_details", {})
        if not isinstance(score_details, dict):
            continue

        score = maybe_float(score_details.get("score"))
        if score is not None:
            key = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{metric_name}"
            metrics[key] = score

        uncertainty = score_details.get("uncertainty", {})
        if isinstance(uncertainty, dict):
            ci = uncertainty.get("confidence_interval", {})
            if isinstance(ci, dict):
                for ci_key in ("lower", "upper", "confidence_level"):
                    value = maybe_float(ci.get(ci_key))
                    if value is not None:
                        key = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{metric_name}/{sanitize(ci_key)}"
                        metrics[key] = value
            value = maybe_float(uncertainty.get("num_samples"))
            if value is not None:
                key = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{metric_name}/num_samples"
                metrics[key] = value

        details = score_details.get("details", {})
        if isinstance(details, dict):
            value = maybe_float(details.get("num_failed_instances"))
            if value is not None:
                key = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{metric_name}/num_failed_instances"
                metrics[key] = value

    return metrics


def collect_flat_metric_record(
    record: dict[str, Any],
    prefix: str,
    lang_key: str,
    dataset: str,
    task: str,
) -> dict[str, float]:
    metric_name = record.get("metric")
    score = maybe_float(record.get("score"))
    if metric_name is None or score is None:
        return {}

    base = f"{prefix}/{sanitize(lang_key)}/{task}/{dataset}/{sanitize(str(metric_name))}"
    metrics = {base: score}
    for field in ("confidence_level", "lower", "upper", "num_samples"):
        value = maybe_float(record.get(field))
        if value is not None:
            metrics[f"{base}/{field}"] = value
    return metrics


def collect_metrics(
    results_path: Path,
    prefix: str,
    languages: set[str] | None,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for record in iter_records(results_path):
        record_languages = parse_languages(record)
        if languages is not None and not any(lang in languages for lang in record_languages):
            continue
        lang_key = "_".join(record_languages) if record_languages else "unknown"
        dataset = sanitize(record_dataset(record))
        task = sanitize(record_task(record))
        if task == "unknown" and dataset in {"ifeval", "ifeval-da"}:
            task = "instruction-following"

        metrics.update(collect_legacy_results_metrics(record, prefix, lang_key, dataset, task))
        metrics.update(collect_euroeval_v17_metrics(record, prefix, lang_key, dataset, task))
        metrics.update(collect_flat_metric_record(record, prefix, lang_key, dataset, task))
    return metrics


def main() -> None:
    args = parse_args()
    languages = set(args.language) if args.language else None
    metrics = collect_metrics(args.results, args.prefix, languages)
    if not metrics:
        raise RuntimeError(f"No numeric EuroEval metrics found in {args.results}")

    epoch_key = f"{args.prefix}/epoch"
    row: dict[str, float] = {epoch_key: args.epoch}
    row.update(metrics)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.log_wandb:
        if not args.project or not args.run_id:
            raise RuntimeError("--project and --run-id are required with --log-wandb")
        run = wandb.init(
            project=args.project,
            id=args.run_id,
            name=args.run_name,
            resume=args.resume,
        )
        assert run is not None
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)
        wandb.log(row)
        label = str(int(args.epoch)) if args.epoch.is_integer() else str(args.epoch).replace(".", "p")
        for key, value in metrics.items():
            run.summary[f"{key}/epoch_{label}"] = value
        run.summary[f"{args.prefix}/last_epoch"] = args.epoch
        wandb.finish()

    print(f"Collected {len(metrics)} EuroEval metrics from {args.results}.")


if __name__ == "__main__":
    main()
