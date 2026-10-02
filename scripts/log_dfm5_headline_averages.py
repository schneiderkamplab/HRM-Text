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

STRICT_DALA_KEY = "dfm_eval/dala/linguistic-acceptability/dfm_evals_macro_f1"
SEMANTIC_DALA_KEY = "dfm_eval/dala/semantic_v1/macro_f1"
SEMANTIC_PREFIXES = frozenset({"headline_avg_semantic_v1", "suite_avg_semantic_v1"})

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

MC9_KEYS = [
    "dfm_eval/arc_easy/choice/accuracy",
    "dfm_eval/arc_challenge/choice/accuracy",
    "dfm_eval/boolq/pattern/accuracy",
    "dfm_eval/commonsense_qa/choice/accuracy",
    "dfm_eval/hellaswag/choice/accuracy",
    "dfm_eval/piqa_en/choice/accuracy",
    "dfm_eval/winogrande/choice/accuracy",
    "dfm_eval/openbookqa/choice/accuracy",
    "dfm_eval/socialiqa/choice/accuracy",
]

GEN5_KEYS = [
    "dfm_eval/squad/f1/mean",
    "dfm_eval/drop/f1/mean",
    "dfm_eval/coqa/f1/mean",
    "dfm_eval/nq_open/f1/mean",
    "dfm_eval/triviaqa/f1/mean",
]

CODE4_KEYS = [
    "dfm_eval/humaneval/verify_sanitized/accuracy",
    "dfm_eval/humaneval_plus/verify_humaneval_plus/accuracy",
    "dfm_eval/mbpp/verify/accuracy",
    "dfm_eval/mbpp_plus/verify_mbpp_plus/accuracy",
]

MATH2_KEYS = [
    "eval/GSM8k/acc",
    "eval/MATH/acc",
]

FLEXOLMO_EXTRA_KEYS = [
    "dfm_eval/mmlu_pro/choice/accuracy",
    "dfm_eval/agieval/choice/accuracy",
    "dfm_eval/bbh/bbh_scorer/accuracy",
]

SECTION_KEYS = {
    "danish": DANISH_KEYS,
    "english": ENGLISH_KEYS,
    "math_code": MATH_CODE_KEYS,
    "mc9": MC9_KEYS,
    "gen5": GEN5_KEYS,
    "code4": CODE4_KEYS,
    "math2": MATH2_KEYS,
    "flexolmo_extras": FLEXOLMO_EXTRA_KEYS,
}
HEADLINE_METRIC_KEYS = frozenset(
    key for keys in SECTION_KEYS.values() for key in keys
)

SUITE_KEYS = {
    "standard": sorted(
        {
            key
            for keys in SECTION_KEYS.values()
            for key in keys
            if key.startswith("eval/")
        }
    ),
    "dfm": sorted(
        {
            key
            for keys in SECTION_KEYS.values()
            for key in keys
            if key.startswith("dfm_eval/")
        }
    ),
    "euroeval": sorted(
        {
            key
            for keys in SECTION_KEYS.values()
            for key in keys
            if key.startswith("euroeval/")
        }
    ),
}


def define_present_headline_metrics(
    wandb_module: Any,
    row: dict[str, Any],
    *,
    epoch_key: str,
) -> None:
    """Register visible workspace metrics explicitly in W&B's history schema."""
    for key in sorted(HEADLINE_METRIC_KEYS.intersection(row)):
        wandb_module.define_metric(key, step_metric=epoch_key, summary="last")


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


def normalize_metric_0_1(key: str, value: float) -> float | None:
    if not math.isfinite(value):
        return None
    if key.startswith("euroeval/"):
        return max(0.0, value) / 100.0
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
        value = normalize_metric_0_1(key, metrics[key])
        if value is not None:
            values.append(value)
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def build_row(
    item: EvalItem,
    metric_prefix: str = "headline_avg",
    *,
    include_sections: bool = True,
    include_suites: bool = True,
    sections: set[str] | None = None,
    include_overall: bool = True,
    overall_only: bool = False,
    suites: set[str] | None = None,
) -> dict[str, Any]:
    metrics = gather_metrics(item)
    # Exact opt-in namespaces only: never mutate legacy memberships or substitute
    # strict DALA when semantic evidence is absent.
    semantic = metric_prefix in SEMANTIC_PREFIXES
    semantic_missing = semantic and section_average(metrics, [SEMANTIC_DALA_KEY])[1] != 1
    def selected_keys(keys):
        return [SEMANTIC_DALA_KEY if semantic and key == STRICT_DALA_KEY else key for key in keys]

    row: dict[str, Any] = {
        f"{metric_prefix}/epoch": item.epoch,
        f"{metric_prefix}/train_step": item.step,
    }
    section_values = []
    selected_sections = sections or set(SECTION_KEYS)
    if include_sections:
        for section, keys in SECTION_KEYS.items():
            if section not in selected_sections:
                continue
            avg, count = section_average(metrics, selected_keys(keys))
            row[f"{metric_prefix}/{section}/count"] = count
            if semantic_missing and STRICT_DALA_KEY in keys:
                continue
            if avg is not None:
                row[f"{metric_prefix}/{section}"] = avg
                section_values.append(avg)
        if include_overall and not sections and section_values and not semantic_missing:
            row[f"{metric_prefix}/overall"] = sum(section_values) / len(section_values)
    if overall_only:
        all_section_values = []
        for keys in SECTION_KEYS.values():
            avg, _ = section_average(metrics, selected_keys(keys))
            if avg is not None:
                all_section_values.append(avg)
        if all_section_values and not semantic_missing:
            row[f"{metric_prefix}/overall"] = sum(all_section_values) / len(all_section_values)
    selected_suites = suites or set(SUITE_KEYS)
    for suite, keys in SUITE_KEYS.items():
        if not include_suites or suite not in selected_suites:
            continue
        avg, count = section_average(metrics, selected_keys(keys))
        row[f"{metric_prefix}/{suite}/count"] = count
        if semantic_missing and STRICT_DALA_KEY in keys:
            continue
        if avg is not None:
            row[f"{metric_prefix}/{suite}"] = avg
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
        "--average-scope",
        choices=["all", "sections", "suites", "danish", "english", "math_code", "mc9", "gen5", "code4", "math2", "flexolmo_extras", "overall", "standard", "dfm", "euroeval"],
        default="all",
        help="Which averages to compute.",
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
    if args.average_scope == "all":
        build_kwargs = {}
    elif args.average_scope == "sections":
        build_kwargs = {"include_sections": True, "include_suites": False}
    elif args.average_scope == "suites":
        build_kwargs = {"include_sections": False, "include_suites": True}
    elif args.average_scope in SECTION_KEYS:
        build_kwargs = {
            "include_sections": True,
            "include_suites": False,
            "sections": {args.average_scope},
            "include_overall": False,
        }
    elif args.average_scope == "overall":
        build_kwargs = {"include_sections": False, "include_suites": False, "overall_only": True}
    else:
        build_kwargs = {"include_sections": False, "include_suites": True, "suites": {args.average_scope}}
    rows = [build_row(item, metric_prefix=metric_prefix, **build_kwargs) for item in args.item]
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
