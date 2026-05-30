#!/usr/bin/env python3
"""Compute BERTScore for completed dfm-evals Inspect archives.

This is an offline rescorer: it reads stored `samples/*.json` from Inspect
`.eval` zip archives and does not rerun model generation.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_TASKS = (
    "wmt24pp-en-da",
    "generative-talemaader",
    "gec-dala",
    "multi-wiki-qa",
)
TASK_RE = re.compile(
    r"_(wmt24pp-en-da|generative-talemaader|gec-dala|multi-wiki-qa)_"
)
EPOCH_RE = re.compile(r"/epoch_(\d+)/")


@dataclass(frozen=True)
class ArchiveInfo:
    family: str
    epoch: int
    task: str
    path: Path
    sample_count: int
    mtime: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-root", type=Path, default=Path("logs/dfm_evals"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/dfm_evals/bertscore_xlm_roberta_large/stored_metrics.json"),
    )
    parser.add_argument("--model-type", default="xlm-roberta-large")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    parser.add_argument("--limit-samples", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")

    selected = select_archives(args.log_root, set(args.tasks))
    if not selected:
        raise RuntimeError(f"No matching Inspect archives found under {args.log_root}")

    from bert_score import BERTScorer

    device = resolve_device(args.device)
    scorer = BERTScorer(
        model_type=args.model_type,
        device=device,
        rescale_with_baseline=False,
    )

    results: list[dict[str, Any]] = []
    for info in selected:
        candidates, references = load_pairs(info.path, args.limit_samples)
        if not candidates:
            print(f"Skipping {info.path}: no prediction/reference pairs")
            continue

        precision, recall, f1 = score_pairs(
            scorer=scorer,
            candidates=candidates,
            references=references,
            batch_size=args.batch_size,
        )
        row = {
            "family": info.family,
            "epoch": info.epoch,
            "task": info.task,
            "archive": str(info.path),
            "model_type": args.model_type,
            "device": device,
            "n": len(candidates),
            "bertscore_precision_mean": statistics.fmean(precision),
            "bertscore_recall_mean": statistics.fmean(recall),
            "bertscore_f1_mean": statistics.fmean(f1),
        }
        print(
            f"{row['family']} epoch {row['epoch']} {row['task']}: "
            f"n={row['n']} f1={row['bertscore_f1_mean']:.6f}"
        )
        results.append(row)

    payload = {
        "model_type": args.model_type,
        "device": device,
        "tasks": list(args.tasks),
        "results": sorted(results, key=lambda r: (r["family"], r["epoch"], r["task"])),
        "rerun_needed_for_bertscore": rerun_matrix(results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {args.output}")


def select_archives(log_root: Path, tasks: set[str]) -> list[ArchiveInfo]:
    candidates: dict[tuple[str, int, str], list[ArchiveInfo]] = defaultdict(list)
    for path in sorted(log_root.rglob("*.eval")):
        info = inspect_archive(path, tasks)
        if info is not None:
            candidates[(info.family, info.epoch, info.task)].append(info)

    selected: list[ArchiveInfo] = []
    for group in candidates.values():
        selected.append(
            max(group, key=lambda item: (item.sample_count, item.mtime, str(item.path)))
        )
    return sorted(selected, key=lambda item: (item.family, item.epoch, item.task))


def inspect_archive(path: Path, tasks: set[str]) -> ArchiveInfo | None:
    task_match = TASK_RE.search(path.name)
    if task_match is None:
        return None
    task = task_match.group(1)
    if task not in tasks:
        return None

    normalized = path.as_posix()
    epoch_match = EPOCH_RE.search(f"/{normalized}")
    if epoch_match is None:
        return None

    if "original_plus_mixed_danish_instruction_rich" in normalized:
        family = "original_plus_mixed_danish_instruction_rich"
    elif "original_sapient_L" in normalized:
        family = "original_sapient"
    else:
        return None

    try:
        sample_count = count_samples(path)
    except zipfile.BadZipFile:
        return None
    if sample_count <= 0:
        return None

    return ArchiveInfo(
        family=family,
        epoch=int(epoch_match.group(1)),
        task=task,
        path=path,
        sample_count=sample_count,
        mtime=path.stat().st_mtime,
    )


def count_samples(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        required = {"header.json", "summaries.json", "reductions.json"}
        if not required.issubset(set(archive.namelist())):
            return 0
        return sum(
            1
            for name in archive.namelist()
            if name.startswith("samples/") and name.endswith(".json")
        )


def load_pairs(path: Path, limit_samples: int | None) -> tuple[list[str], list[list[str]]]:
    candidates: list[str] = []
    references: list[list[str]] = []
    with zipfile.ZipFile(path) as archive:
        sample_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("samples/") and name.endswith(".json")
        )
        if limit_samples is not None:
            sample_names = sample_names[:limit_samples]
        for name in sample_names:
            sample = json.loads(archive.read(name))
            prediction = _completion(sample).strip()
            target = sample.get("target")
            refs = _target_strings(target)
            if prediction and refs:
                candidates.append(prediction)
                references.append(refs)
    return candidates, references


def score_pairs(
    *,
    scorer: Any,
    candidates: list[str],
    references: list[list[str]],
    batch_size: int,
) -> tuple[list[float], list[float], list[float]]:
    all_precision: list[float] = []
    all_recall: list[float] = []
    all_f1: list[float] = []

    for start in range(0, len(candidates), batch_size):
        batch_candidates: list[str] = []
        batch_references: list[str] = []
        owner: list[int] = []
        for local_index, (candidate, refs) in enumerate(
            zip(
                candidates[start : start + batch_size],
                references[start : start + batch_size],
                strict=True,
            )
        ):
            for ref in refs:
                batch_candidates.append(candidate)
                batch_references.append(ref)
                owner.append(local_index)

        p_tensor, r_tensor, f_tensor = scorer.score(batch_candidates, batch_references)
        per_sample: dict[int, tuple[float, float, float]] = {}
        for index, precision, recall, f1 in zip(
            owner, p_tensor.tolist(), r_tensor.tolist(), f_tensor.tolist(), strict=True
        ):
            current = per_sample.get(index)
            if current is None or f1 > current[2]:
                per_sample[index] = (float(precision), float(recall), float(f1))

        for index in range(len(candidates[start : start + batch_size])):
            precision, recall, f1 = per_sample[index]
            all_precision.append(precision)
            all_recall.append(recall)
            all_f1.append(f1)

    return all_precision, all_recall, all_f1


def rerun_matrix(results: list[dict[str, Any]]) -> dict[str, list[str]]:
    have = {
        (str(row["family"]), int(row["epoch"]))
        for row in results
    }
    expected = {
        "original_sapient": [1, 2, 3, 4],
        "original_plus_mixed_danish_instruction_rich": [1, 2, 3],
    }
    rerun_tasks = ("govreport", "nordjyllandnews")
    matrix: dict[str, list[str]] = {}
    for family, epochs in expected.items():
        for epoch in epochs:
            if (family, epoch) not in have:
                continue
            matrix[f"{family}/epoch_{epoch}"] = list(rerun_tasks)
    return matrix


def _completion(sample: dict[str, Any]) -> str:
    output = sample.get("output")
    if isinstance(output, dict):
        completion = output.get("completion")
        if isinstance(completion, str):
            return completion
    return ""


def _target_strings(target: Any) -> list[str]:
    if isinstance(target, str):
        return [target.strip()] if target.strip() else []
    if isinstance(target, list):
        return [item.strip() for item in target if isinstance(item, str) and item.strip()]
    return []


def resolve_device(device: str) -> str:
    normalized = device.strip().lower()
    if normalized != "auto":
        return normalized
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


if __name__ == "__main__":
    main()
