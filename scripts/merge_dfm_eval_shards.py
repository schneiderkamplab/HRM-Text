#!/usr/bin/env python3
"""Merge sharded dfm-evals Inspect logs and optionally log aggregate metrics."""

from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.dala_semantic import semantic_pairs
except ModuleNotFoundError:
    from dala_semantic import semantic_pairs


def semantic_dala_metrics(samples, language):
    pairs = semantic_pairs(samples, language)
    n = len(pairs)
    if not n:
        raise ValueError('Empty acceptability results')
    return {
        'semantic_v1/macro_f1': macro_f1(pairs, ['correct', 'incorrect']),
        'semantic_v1/mcc': mcc(pairs, ['correct', 'incorrect']),
        'semantic_v1/accuracy': sum(t == p for t, p in pairs) / n,
        'semantic_v1/invalid_rate': sum(p is None for _, p in pairs) / n,
        'semantic_v1/n': float(n),
    }


def epoch_label(epoch: float) -> str:
    return str(int(epoch)) if epoch.is_integer() else str(epoch).replace(".", "p")


def iter_sample_records(paths: list[Path]):
    """Yield sample records from .eval zip files, disambiguating IDs across shards."""
    for shard_idx, path in enumerate(paths):
        if not zipfile.is_zipfile(path):
            continue
        with zipfile.ZipFile(path) as zf:
            for name in sorted(n for n in zf.namelist() if n.startswith("samples/") and n.endswith(".json")):
                record = json.loads(zf.read(name))
                raw_id = str(record.get("id") or f"{path.stem}:{name}")
                record["id"] = f"s{shard_idx}:{raw_id}"
                yield record


def stderr(values: list[float]) -> float:
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    return math.sqrt(variance) / math.sqrt(n)


def mean_stderr(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    return sum(values) / len(values), stderr(values)


def numeric_metrics(
    samples: list[dict[str, Any]],
    scorer_name: str,
    *,
    scalar_metric: str = "mean",
    flatten_dict: bool = True,
) -> dict[str, float]:
    values_by_metric: dict[str, list[float]] = {}
    for sample in samples:
        score = sample.get("scores", {}).get(scorer_name)
        if not isinstance(score, dict):
            continue
        value = score.get("value")
        if isinstance(value, int | float) and math.isfinite(float(value)):
            values_by_metric.setdefault(scalar_metric, []).append(float(value))
        elif isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, int | float) and math.isfinite(float(item)):
                    values_by_metric.setdefault(str(key), []).append(float(item))

    metrics: dict[str, float] = {}
    for key, values in values_by_metric.items():
        mean, se = mean_stderr(values)
        if flatten_dict:
            metrics[f"{key}/mean"] = mean
            metrics[f"{key}/stderr"] = se
        else:
            metrics[f"{scorer_name}/{key}"] = mean
            metrics[f"{scorer_name}/{key}_stderr"] = se
    return metrics


def accuracy_from_values(samples: list[dict[str, Any]], scorer_name: str, *, partial_credit: bool = False) -> dict[str, float]:
    values: list[float] = []
    for sample in samples:
        score = sample.get("scores", {}).get(scorer_name)
        if not isinstance(score, dict):
            continue
        value = score.get("value")
        if value == "C":
            values.append(1.0)
        elif value == "P" and partial_credit:
            values.append(0.5)
        elif value in {"I", "P", ""}:
            values.append(0.0)
    mean, se = mean_stderr(values)
    return {
        f"{scorer_name}/accuracy": mean,
        f"{scorer_name}/accuracy_stderr": se,
        f"{scorer_name}/n": float(len(values)),
    }


def pairs_from_metadata(samples: list[dict[str, Any]], scorer_name: str, *, invalid_as_none: bool = False):
    pairs = []
    for sample in samples:
        score = sample.get("scores", {}).get(scorer_name)
        if not isinstance(score, dict):
            continue
        metadata = score.get("metadata") or {}
        target = metadata.get("target")
        prediction = metadata.get("prediction")
        if target is None:
            continue
        if invalid_as_none and prediction in {None, "", "__invalid__"}:
            prediction = None
        pairs.append((str(target), None if prediction is None else str(prediction)))
    return pairs


def macro_f1(pairs: list[tuple[str, str | None]], labels: list[str]) -> float:
    if not pairs:
        return 0.0
    scores = []
    for label in labels:
        tp = fp = fn = 0
        for target, prediction in pairs:
            if target == label and prediction == label:
                tp += 1
            elif target != label and prediction == label:
                fp += 1
            elif target == label and prediction != label:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def mcc(pairs: list[tuple[str, str | None]], labels: list[str]) -> float:
    if not pairs or not labels:
        return 0.0
    full_labels = list(labels)
    invalid = "__invalid__"
    if any(prediction is None for _target, prediction in pairs):
        full_labels.append(invalid)
    index = {label: idx for idx, label in enumerate(full_labels)}
    matrix = [[0 for _ in full_labels] for _ in full_labels]
    for target, prediction in pairs:
        pred = prediction if prediction is not None else invalid
        if target not in index:
            continue
        if pred not in index:
            pred = invalid
            if pred not in index:
                index[pred] = len(full_labels)
                full_labels.append(pred)
        matrix[index[target]][index[pred]] += 1

    total = sum(sum(row) for row in matrix)
    if total == 0:
        return 0.0
    correct = sum(matrix[i][i] for i in range(len(matrix)))
    true_totals = [sum(row) for row in matrix]
    pred_totals = [sum(matrix[r][c] for r in range(len(matrix))) for c in range(len(matrix))]
    covariance = correct * total - sum(t * p for t, p in zip(true_totals, pred_totals, strict=True))
    denom_left = total * total - sum(t * t for t in true_totals)
    denom_right = total * total - sum(p * p for p in pred_totals)
    denom = math.sqrt(denom_left * denom_right)
    return covariance / denom if denom else 0.0


def task_metrics(task: str, samples: list[dict[str, Any]]) -> dict[str, float]:
    # Multilingual tasks retain their language-specific output namespace while
    # using the same sample-level aggregation as the Danish benchmark.
    if re.fullmatch(r"dala_[a-z]{2}(?:_[a-z]{2})?", task):
        pairs = pairs_from_metadata(samples, "linguistic-acceptability", invalid_as_none=True)
        return {
            "linguistic-acceptability/dfm_evals_macro_f1": macro_f1(pairs, ["correct", "incorrect"]),
            "linguistic-acceptability/dfm_evals_mcc": mcc(pairs, ["correct", "incorrect"]),
            "linguistic-acceptability/n": float(len(pairs)),
            **semantic_dala_metrics(samples, task.removeprefix('dala_')),
        }
    if re.fullmatch(r"gec_dala_[a-z]{2}(?:_[a-z]{2})?", task):
        return task_metrics("gec_dala", samples)
    if task == "ruler_8k":
        metrics = numeric_metrics(samples, "ruler_scorer", flatten_dict=False)
        variants = sorted(
            {
                str((sample.get("metadata") or {}).get("variant"))
                for sample in samples
                if (sample.get("metadata") or {}).get("variant")
            }
        )
        for variant in variants:
            subset = [
                sample
                for sample in samples
                if str((sample.get("metadata") or {}).get("variant")) == variant
            ]
            variant_metrics = numeric_metrics(subset, "ruler_scorer", flatten_dict=False)
            for key, value in variant_metrics.items():
                metrics[f"variant/{variant}/{key}"] = value
        return metrics
    match task:
        case "andersen_modernization":
            return numeric_metrics(samples, "gleu", flatten_dict=False) | numeric_metrics(
                samples, "chrf3pp", flatten_dict=False
            )
        case "wmt24pp_en_da":
            return numeric_metrics(samples, "chrf3pp", flatten_dict=False)
        case "multi_wiki_qa":
            return numeric_metrics(samples, "multi_wiki_qa_scorer")
        case "gec_dala":
            return numeric_metrics(samples, "gec_dala_scorer")
        case "govreport" | "govreport_long" | "nordjyllandnews":
            return numeric_metrics(samples, "summarization")
        case (
            "ruler_smoke"
            | "ruler_8k"
            | "longbench_en"
            | "longalign_en"
            | "longalign_da"
            | "marathon"
            | "qmsum_cleaned"
            | "danish_summarization_eur_lex"
            | "danish_summarization"
        ):
            return numeric_metrics(samples, "ruler_scorer", flatten_dict=False) | numeric_metrics(
                samples, "long_context_scorer", flatten_dict=False
            )
        case "piqa":
            return accuracy_from_values(samples, "piqa_scorer")
        case "danish_citizen_tests":
            pairs = pairs_from_metadata(samples, "knowledge")
            labels = sorted({target for target, _ in pairs} | {pred for _, pred in pairs if pred})
            metrics = accuracy_from_values(samples, "knowledge")
            metrics["knowledge/dfm_evals/mcc"] = mcc(pairs, labels)
            return metrics
        case "dala":
            pairs = pairs_from_metadata(samples, "linguistic-acceptability", invalid_as_none=True)
            return {
                "linguistic-acceptability/dfm_evals_macro_f1": macro_f1(pairs, ["correct", "incorrect"]),
                "linguistic-acceptability/dfm_evals_mcc": mcc(pairs, ["correct", "incorrect"]),
                "linguistic-acceptability/n": float(len(pairs)),
                **semantic_dala_metrics(samples, 'da'),
            }
        case "generative_talemaader":
            return accuracy_from_values(samples, "model_graded_fact", partial_credit=True)
        case "humaneval":
            # inspect-evals HumanEval uses a verify scorer.
            scorer_names = Counter(
                scorer
                for sample in samples
                for scorer in (sample.get("scores") or {}).keys()
            )
            scorer = "verify" if "verify" in scorer_names else (scorer_names.most_common(1)[0][0] if scorer_names else "verify")
            return accuracy_from_values(samples, scorer)
        case "arc_easy" | "arc_challenge" | "commonsense_qa" | "hellaswag" | "piqa_en" | "winogrande" | "openbookqa" | "socialiqa":
            return accuracy_from_values(samples, "choice")
        case "boolq":
            return accuracy_from_values(samples, "pattern")
        case "squad" | "drop" | "coqa" | "nq_open" | "triviaqa":
            return numeric_metrics(samples, "f1", flatten_dict=False) | numeric_metrics(samples, "exact", flatten_dict=False)
        case "humaneval_plus" | "mbpp" | "mbpp_plus":
            scorer_names = Counter(
                scorer
                for sample in samples
                for scorer in (sample.get("scores") or {}).keys()
            )
            scorer = "verify" if "verify" in scorer_names else (scorer_names.most_common(1)[0][0] if scorer_names else "verify")
            return accuracy_from_values(samples, scorer)
        case "mmlu_pro":
            return accuracy_from_values(samples, "choice")
        case "agieval":
            scorer_names = Counter(
                scorer
                for sample in samples
                for scorer in (sample.get("scores") or {}).keys()
            )
            if "choice" in scorer_names:
                return accuracy_from_values(samples, "choice")
            scorer = scorer_names.most_common(1)[0][0] if scorer_names else "choice"
            return accuracy_from_values(samples, scorer)
        case "bbh":
            return accuracy_from_values(samples, "bbh_scorer")
        case _:
            raise ValueError(f"Unsupported DFM task merge: {task}")


def wandb_task_name(task: str) -> str:
    return {
        "danish_citizen_tests": "danish-citizen-tests",
        "wmt24pp_en_da": "wmt24pp-en-da",
        "generative_talemaader": "generative-talemaader",
    }.get(task, task)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval", nargs="+", type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--epoch", type=float, required=True)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--run-id")
    parser.add_argument("--run-name")
    parser.add_argument("--prefix", default="dfm_eval")
    parser.add_argument("--log-wandb", action="store_true")
    args = parser.parse_args()

    samples = list(iter_sample_records(args.eval))
    if not samples:
        raise ValueError(f"No DFM eval samples found for task {args.task}: {', '.join(str(path) for path in args.eval)}")
    metrics = task_metrics(args.task, samples)
    task_name = wandb_task_name(args.task)
    logged_metrics = {f"{args.prefix}/{task_name}/{key}": value for key, value in metrics.items()}
    payload = {
        "epoch": args.epoch,
        "num_samples": len(samples),
        "metrics": logged_metrics,
        "inputs": [str(path) for path in args.eval],
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.log_wandb:
        if not (args.project and args.run_id and args.run_name):
            raise ValueError("--project, --run-id, and --run-name are required with --log-wandb.")
        import wandb

        run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume="allow")
        assert run is not None
        epoch_key = f"{args.prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)
        row = {epoch_key: args.epoch, **logged_metrics}
        train_step_key = f"{args.prefix}/train_step"
        if args.step is not None:
            wandb.define_metric(train_step_key)
            row[train_step_key] = args.step
        from log_dfm5_headline_averages import define_present_headline_metrics

        define_present_headline_metrics(wandb, row, epoch_key=epoch_key)
        wandb.log(row, commit=True)
        summary = {epoch_key: args.epoch, f"{args.prefix}/last_epoch": args.epoch}
        if args.step is not None:
            summary[train_step_key] = args.step
            summary[f"{args.prefix}/last_train_step"] = args.step
        label = epoch_label(args.epoch)
        for key, value in logged_metrics.items():
            summary[key] = value
            summary[f"{key}/epoch_{label}"] = value
        run.summary.update(summary)
        wandb.finish()


if __name__ == "__main__":
    main()
