#!/usr/bin/env python3
"""Log DFM5 headline section averages to W&B from local merged eval artifacts."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DANISH_KEYS = [
    "dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1",
    "dfm_eval/danish-citizen-tests/knowledge/accuracy",
    "dfm_eval/gec_dala/exact_match/mean",
    "dfm_eval/generative-talemaader/model_graded_fact/accuracy",
    "dfm_eval/ifeval-da/instruction_following/final_acc",
    "dfm_eval/multi_wiki_qa/exact_match/mean",
    "dfm_eval/nordjyllandnews/bertscore_f1/mean",
    "dfm_eval/piqa/piqa_scorer/accuracy",
    "dfm_eval/wmt24pp-en-da/chrf3pp/mean",
    "euroeval/da/sentiment-classification/angry-tweets/macro_f1",
    "euroeval/da/linguistic-acceptability/scala-da/macro_f1",
    "euroeval/da/named-entity-recognition/dansk/micro_f1",
    "euroeval/da/reading-comprehension/multi-wiki-qa-da/f1",
    "euroeval/da/summarization/nordjylland-news/chr_f3pp",
    "euroeval/da/knowledge/danske-talemaader/accuracy",
    "euroeval/da/knowledge/danish-citizen-tests/accuracy",
    "euroeval/da/common-sense-reasoning/hellaswag-da/accuracy",
    "euroeval/da/instruction-following/ifeval-da/instruction_accuracy",
]

ENGLISH_KEYS = [
    "eval/ARC/acc",
    "eval/BoolQ/acc",
    "eval/DROP/f1",
    "eval/HellaSwag/acc",
    "eval/MMLU/acc",
    "eval/Winogrande/acc",
    "dfm_eval/govreport/bertscore_f1/mean",
    "euroeval/en/sentiment-classification/sst5/macro_f1",
    "euroeval/en/linguistic-acceptability/scala-en/macro_f1",
    "euroeval/en/named-entity-recognition/conll-en/micro_f1",
    "euroeval/en/reading-comprehension/squad/f1",
    "euroeval/en/summarization/cnn-dailymail/chr_f3pp",
    "euroeval/en/knowledge/life-in-the-uk/accuracy",
    "euroeval/en/common-sense-reasoning/hellaswag/accuracy",
    "euroeval/en/instruction-following/ifeval/instruction_accuracy",
]

MATH_CODE_KEYS = [
    "eval/GSM8k/acc",
    "eval/MATH/acc",
    "dfm_eval/humaneval/verify_sanitized/accuracy",
    "euroeval/en/tool-calling/bfcl-v2/tool_calling_accuracy",
]

SECTION_KEYS = {
    "danish": DANISH_KEYS,
    "english": ENGLISH_KEYS,
    "math_code": MATH_CODE_KEYS,
}


@dataclass(frozen=True)
class EvalItem:
    step: int
    epoch: float
    standard_root: Path
    dfm_root: Path
    euroeval_root: Path | None = None


def parse_item(raw: str) -> EvalItem:
    parts = raw.split(":")
    if len(parts) not in (4, 5):
        raise argparse.ArgumentTypeError(
            "--item must be step:epoch:standard_root:dfm_root[:euroeval_root]"
        )
    step, epoch, standard_root, dfm_root, *rest = parts
    euroeval_root = Path(rest[0]) if rest else None
    return EvalItem(int(step), float(epoch), Path(standard_root), Path(dfm_root), euroeval_root)


def load_metrics(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    metrics = data.get("metrics", data)
    return {k: float(v) for k, v in metrics.items() if isinstance(v, int | float)}


def gather_metrics(item: EvalItem) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for path in item.standard_root.glob("standard_shards/*/merged_metrics.json"):
        metrics.update(load_metrics(path))
    for path in item.dfm_root.glob("*/merged_metrics.json"):
        metrics.update(load_metrics(path))
    metrics.update(load_metrics(item.dfm_root / "merged_ifeval_da_metrics.json"))
    if item.euroeval_root is not None:
        for path in item.euroeval_root.glob("**/merged_metrics.json"):
            metrics.update(load_metrics(path))
    return metrics


def normalize_0_1(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    if value < 0:
        return 0.0
    if value <= 1:
        return value
    if value <= 100:
        return value / 100.0
    return None


def section_average(metrics: dict[str, float], keys: list[str]) -> tuple[float | None, int]:
    values = []
    for key in keys:
        if key not in metrics:
            continue
        value = normalize_0_1(metrics[key])
        if value is not None:
            values.append(value)
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def build_row(item: EvalItem, metric_prefix: str = "headline_avg") -> dict[str, Any]:
    metrics = gather_metrics(item)
    row: dict[str, Any] = {
        f"{metric_prefix}/epoch": item.epoch,
        f"{metric_prefix}/train_step": item.step,
    }
    section_values = []
    for section, keys in SECTION_KEYS.items():
        avg, count = section_average(metrics, keys)
        row[f"{metric_prefix}/{section}/count"] = count
        if avg is not None:
            row[f"{metric_prefix}/{section}"] = avg
            section_values.append(avg)
    if section_values:
        row[f"{metric_prefix}/overall"] = sum(section_values) / len(section_values)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--run-id", default="2tv9u438")
    parser.add_argument("--run-name", default="dfm5-XXS")
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument(
        "--metric-prefix",
        default="avg",
        help="Metric namespace for averages, e.g. avg or headline_avg.",
    )
    parser.add_argument(
        "--item",
        action="append",
        type=parse_item,
        required=True,
        help="step:epoch:standard_root:dfm_root",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metric_prefix = args.metric_prefix.rstrip("/")
    rows = [build_row(item, metric_prefix=metric_prefix) for item in args.item]
    print(json.dumps(rows, indent=2, sort_keys=True))
    if args.dry_run:
        return

    import wandb

    run = wandb.init(
        entity=args.entity,
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume="allow",
    )
    wandb.define_metric(f"{metric_prefix}/epoch")
    wandb.define_metric(f"{metric_prefix}/*", step_metric=f"{metric_prefix}/epoch")
    for row in rows:
        wandb.log(row, commit=True)
    run.finish()


if __name__ == "__main__":
    main()
