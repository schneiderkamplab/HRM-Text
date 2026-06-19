#!/usr/bin/env python3
"""Run EuroEval IFEval with batched OpenAI-compatible API calls.

This bypasses EuroEval's single-sample generation loop for IFEval while keeping
the same cached dataset rows and instruction-accuracy constraint functions.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from datasets import Dataset
from tqdm.auto import tqdm


_real_find_spec = importlib.util.find_spec


def _find_spec_without_flash_attn(name: str, *args, **kwargs):
    if name == "flash_attn" or name.startswith("flash_attn."):
        return None
    return _real_find_spec(name, *args, **kwargs)


importlib.util.find_spec = _find_spec_without_flash_attn

from euroeval.metrics.ifeval.constraints import ALL_CONSTRAINTS  # noqa: E402


DATASETS = {
    "ifeval": {
        "language": "en",
        "source": "EuroEval/ifeval-en",
        "metric": "euroeval/en/instruction-following/ifeval/instruction_accuracy",
        "default_arrow": "logs/euroeval/dfm5_L_step550000_full_native_followup_20260617/step_550000/ifeval/cache/EuroEval___ifeval-en/default/0.0.0/78c19e06929b759b1f467cfec4ebcfbe8cee7e9b/ifeval-en-test.arrow",
    },
    "ifeval-da": {
        "language": "da",
        "source": "EuroEval/ifeval-da",
        "metric": "euroeval/da/instruction-following/ifeval-da/instruction_accuracy",
        "default_arrow": "logs/euroeval/dfm5_L_step550000_full_native_followup_20260617/step_550000/ifeval-da/cache/EuroEval___ifeval-da/default/0.0.0/70e8a7e9484f25c35170a42ac63ff63efdbbb870/ifeval-da-test.arrow",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASETS), required=True)
    parser.add_argument("--arrow", type=Path, default=None, help="Cached EuroEval Arrow test split.")
    parser.add_argument("--api-base", required=True, help="OpenAI-compatible base URL, e.g. http://127.0.0.1:17001/v1.")
    parser.add_argument("--api-key", default="inspectai")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--epoch", type=float, default=None)
    parser.add_argument("--num-iterations", type=int, default=10)
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--resume", action="store_true", help="Reuse existing predictions.jsonl rows.")
    return parser.parse_args()


def clean_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def iter_constraint_specs(reference: dict[str, Any]):
    instruction_ids = list(reference.get("instruction_id_list") or [])
    kwargs_list = list(reference.get("kwargs") or [])
    if len(kwargs_list) < len(instruction_ids):
        kwargs_list.extend({} for _ in range(len(instruction_ids) - len(kwargs_list)))
    for instruction_id, kwargs in zip(instruction_ids, kwargs_list):
        yield instruction_id, kwargs or {}


def score_response(response: str, reference: dict[str, Any]) -> list[bool]:
    results: list[bool] = []
    for instruction_id, kwargs in iter_constraint_specs(reference):
        if instruction_id not in ALL_CONSTRAINTS:
            continue
        constraint = ALL_CONSTRAINTS[instruction_id]
        results.append(bool(constraint(str(response), **clean_kwargs(dict(kwargs)))))
    return results


def make_bootstrap_iterations(dataset: Dataset, *, num_iterations: int, seed: int) -> list[list[int]]:
    rng = np.random.default_rng(seed)
    return [
        [int(idx) for idx in rng.integers(0, len(dataset), size=(len(dataset),))]
        for _ in range(num_iterations)
    ]


def unique_indices_for_generation(dataset: Dataset, iterations: list[list[int]]) -> list[int]:
    seen_texts: set[str] = set()
    unique_indices: list[int] = []
    for iteration in iterations:
        for idx in iteration:
            text = dataset[idx]["text"]
            if text in seen_texts:
                continue
            seen_texts.add(text)
            unique_indices.append(idx)
    return unique_indices


def aggregate_iteration_scores(iteration_scores: list[float], confidence_level: float = 0.95) -> dict[str, float]:
    if not iteration_scores:
        return {
            "value": 0.0,
            "confidence_level": confidence_level,
            "lower": 0.0,
            "upper": 0.0,
            "num_samples": 0.0,
        }
    mean = float(np.mean(iteration_scores))
    radius = float(1.96 * (np.std(iteration_scores, ddof=1) / math.sqrt(len(iteration_scores)))) if len(iteration_scores) > 1 else float("nan")
    return {
        "value": 100.0 * mean,
        "confidence_level": confidence_level,
        "lower": 100.0 * (mean - radius),
        "upper": 100.0 * (mean + radius),
        "num_samples": float(len(iteration_scores)),
    }


def load_existing(path: Path) -> dict[int, dict[str, Any]]:
    existing: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return existing
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if "idx" in row and row.get("response") is not None:
                existing[int(row["idx"])] = row
    return existing


async def generate_one(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    api_key: str,
    model: str,
    idx: int,
    prompt: str,
    max_tokens: int,
    temperature: float,
    semaphore: asyncio.Semaphore,
) -> tuple[int, str | None, str | None, float]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    started = time.monotonic()
    async with semaphore:
        try:
            response = await client.post(f"{api_base.rstrip('/')}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"].get("content") or ""
            return idx, content, None, time.monotonic() - started
        except Exception as exc:
            return idx, None, repr(exc), time.monotonic() - started


async def generate_all(
    args: argparse.Namespace,
    dataset: Dataset,
    existing: dict[int, dict[str, Any]],
    generation_indices: list[int],
) -> dict[int, dict[str, Any]]:
    predictions_path = args.output_dir / "predictions.jsonl"
    semaphore = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(max_connections=args.concurrency + 8, max_keepalive_connections=args.concurrency + 8)
    timeout = httpx.Timeout(args.timeout)

    pending = [(idx, dataset[idx]["text"]) for idx in generation_indices if idx not in existing]
    rows: dict[int, dict[str, Any]] = dict(existing)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = [
            asyncio.create_task(
                generate_one(
                    client,
                    api_base=args.api_base,
                    api_key=args.api_key,
                    model=args.model,
                    idx=idx,
                    prompt=prompt,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    semaphore=semaphore,
                )
            )
            for idx, prompt in pending
        ]
        with predictions_path.open("a") as out:
            for future in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc=f"{args.dataset} requests"):
                idx, response, error, elapsed = await future
                row = {
                    "idx": idx,
                    "dataset": args.dataset,
                    "prompt": dataset[idx]["text"],
                    "response": response,
                    "error": error,
                    "elapsed_seconds": elapsed,
                    "target_text": dataset[idx]["target_text"],
                }
                rows[idx] = row
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
    return rows


def write_outputs(
    args: argparse.Namespace,
    dataset: Dataset,
    rows_by_index: dict[int, dict[str, Any]],
    iterations: list[list[int]],
) -> None:
    cfg = DATASETS[args.dataset]
    response_by_text = {
        dataset[idx]["text"]: rows_by_index[idx]
        for idx in rows_by_index
    }
    iteration_scores: list[float] = []
    total_instructions = 0
    failed_indices: set[int] = set()
    scored_rows = []
    for idx, row in sorted(rows_by_index.items()):
        results = score_response(row.get("response") or "", row["target_text"]) if not row.get("error") else [
            False
            for instruction_id, _kwargs in iter_constraint_specs(row["target_text"])
            if instruction_id in ALL_CONSTRAINTS
        ]
        if row.get("error") or row.get("response") is None:
            failed_indices.add(idx)
        scored_rows.append({**row, "instruction_results": results})

    for iteration in iterations:
        instruction_results: list[bool] = []
        for idx in iteration:
            cached_row = response_by_text[dataset[idx]["text"]]
            if cached_row.get("error") or cached_row.get("response") is None:
                failed_indices.add(idx)
                results = [
                    False
                    for instruction_id, _kwargs in iter_constraint_specs(dataset[idx]["target_text"])
                    if instruction_id in ALL_CONSTRAINTS
                ]
            else:
                results = score_response(cached_row["response"], dataset[idx]["target_text"])
            instruction_results.extend(results)
        total_instructions += len(instruction_results)
        iteration_scores.append(sum(instruction_results) / len(instruction_results) if instruction_results else 0.0)

    summary = aggregate_iteration_scores(iteration_scores)
    metric_key = cfg["metric"]
    metrics = {
        metric_key: summary["value"],
        f"{metric_key}/confidence_level": summary["confidence_level"],
        f"{metric_key}/lower": summary["lower"],
        f"{metric_key}/num_samples": summary["num_samples"],
        f"{metric_key}/upper": summary["upper"],
        "failed_instances": len(failed_indices),
        "num_generated_examples": len(rows_by_index),
        "num_bootstrap_examples": sum(len(iteration) for iteration in iterations),
        "num_instructions": total_instructions,
        "iteration_scores": iteration_scores,
    }
    if args.epoch is not None:
        metrics["euroeval/epoch"] = args.epoch

    (args.output_dir / "scored_predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in scored_rows)
    )
    (args.output_dir / "merged_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    result = {
        "dataset": args.dataset,
        "source": cfg["source"],
        "language": cfg["language"],
        "task": "instruction-following",
        "metric": "instruction_accuracy",
        "score": summary["value"],
        "confidence_level": summary["confidence_level"],
        "lower": summary["lower"],
        "upper": summary["upper"],
        "num_samples": summary["num_samples"],
        "num_generated_examples": len(rows_by_index),
        "num_bootstrap_examples": sum(len(iteration) for iteration in iterations),
        "num_instructions": total_instructions,
        "failed_instances": len(failed_indices),
    }
    (args.output_dir / "euroeval_benchmark_results.jsonl").write_text(json.dumps(result, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    arrow = args.arrow or Path(DATASETS[args.dataset]["default_arrow"])
    dataset = Dataset.from_file(str(arrow))
    iterations = make_bootstrap_iterations(dataset, num_iterations=args.num_iterations, seed=args.seed)
    generation_indices = unique_indices_for_generation(dataset, iterations)
    print(
        f"Loaded {len(dataset)} raw rows; {len(generation_indices)} unique prompts "
        f"across {args.num_iterations} bootstrap iterations."
    )
    existing = load_existing(args.output_dir / "predictions.jsonl") if args.resume else {}
    rows = asyncio.run(generate_all(args, dataset, existing, generation_indices))
    write_outputs(args, dataset, rows, iterations)
    print((args.output_dir / "merged_metrics.json").read_text())


if __name__ == "__main__":
    main()
