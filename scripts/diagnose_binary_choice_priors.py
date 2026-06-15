#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import random
import sys
from pathlib import Path
from typing import Any

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evaluation.benchmarks import BoolQ
from evaluation.engines import SimpleEngine


PIQA_PATH = Path("dfm-evals/dfm_evals/tasks/piqa/piqa-dan.json")
BOOLQ_MARKER = "\nA. Yes\nB. No\nAnswer:"


def boolq_cases(limit: int, seed: int, mode: str) -> list[dict[str, Any]]:
    benchmark = BoolQ()
    indices = list(range(len(benchmark.prompts)))
    random.Random(seed).shuffle(indices)
    indices = indices[:limit]

    rng = random.Random(seed + 1009)
    cases: list[dict[str, Any]] = []
    for index in indices:
        prompt = benchmark.prompts[index]
        gold = benchmark.ground_truths[index]["gold"]
        swapped = mode == "flip" or (mode == "random" and rng.random() < 0.5)
        if swapped:
            prompt = prompt.replace(BOOLQ_MARKER, "\nA. No\nB. Yes\nAnswer:")
            gold = "A" if gold == "B" else "B"
        cases.append({"id": index, "prompt": prompt, "gold": gold, "swapped": swapped})
    return cases


def piqa_cases(seed: int, mode: str) -> list[dict[str, Any]]:
    records = json.loads(PIQA_PATH.read_text())
    rng = random.Random(seed + 2003)
    cases: list[dict[str, Any]] = []
    for row in records:
        solution0 = str(row["solution0"])
        solution1 = str(row["solution1"])
        gold = "A" if row["label"] == 0 else "B"
        swapped = mode == "flip" or (mode == "random" and rng.random() < 0.5)
        if swapped:
            solution0, solution1 = solution1, solution0
            gold = "A" if gold == "B" else "B"
        prompt = (
            "Du får et spørgsmål om fysisk hverdagsfornuft og to svarmuligheder.\n"
            "Vælg den bedste løsning.\n\n"
            f"Spørgsmål:\n{row['prompt']}\n\n"
            f"Mulighed A:\n{solution0}\n\n"
            f"Mulighed B:\n{solution1}\n\n"
            "Svar kun med A eller B."
        )
        cases.append({"id": str(row.get("id")), "prompt": prompt, "gold": gold, "swapped": swapped})
    return cases


def score_outputs(cases: list[dict[str, Any]], outputs: list[str]) -> dict[str, Any]:
    rows = []
    correct = invalid = 0
    pred_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for case, output in zip(cases, outputs, strict=True):
        pred = output.strip().upper()
        if pred not in {"A", "B"}:
            invalid += 1
            pred_key = "<invalid>"
        else:
            pred_key = pred
            correct += int(pred == case["gold"])
        pred_counts[pred_key] = pred_counts.get(pred_key, 0) + 1
        target_counts[case["gold"]] = target_counts.get(case["gold"], 0) + 1
        rows.append(case | {"completion": output, "pred": pred_key, "correct": pred == case["gold"]})
    total = len(cases)
    return {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "invalid_rate": invalid / total if total else 0.0,
        "target_counts": target_counts,
        "pred_counts": pred_counts,
        "rows": rows,
    }


def run_model(
    ckpt_path: str,
    ckpt_tag: str | None,
    use_ema: bool,
    suites: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    engine = SimpleEngine(ckpt_path, ckpt_tag=ckpt_tag, ckpt_use_ema=use_ema)
    results = {}
    for name, cases in suites.items():
        if name.startswith("boolq"):
            max_tokens = 1
            batch_size = 1
        else:
            max_tokens = 8
            batch_size = 8
        outputs = engine.generate(
            [case["prompt"] for case in cases],
            batch_size=batch_size,
            max_context=4096,
            max_tokens=max_tokens,
            temperature=0.0,
            condition="direct",
        )
        results[name] = score_outputs(cases, outputs)
    del engine
    gc.collect()
    torch.cuda.empty_cache()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boolq-limit", type=int, default=256)
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--ckpt-path", default="checkpoints/dfm4/XL-ddp")
    parser.add_argument("--ckpt-tag", default="step_200000")
    parser.add_argument("--models", choices=("ema", "noema", "both"), default="both")
    parser.add_argument("--output", type=Path, default=Path("logs/eval/dfm4_XL_ddp_binary_choice_order_200k.json"))
    args = parser.parse_args()

    suites = {
        "boolq_original": boolq_cases(args.boolq_limit, args.seed, "original"),
        "boolq_flip": boolq_cases(args.boolq_limit, args.seed, "flip"),
        "boolq_random": boolq_cases(args.boolq_limit, args.seed, "random"),
        "piqa_original": piqa_cases(args.seed, "original"),
        "piqa_flip": piqa_cases(args.seed, "flip"),
        "piqa_random": piqa_cases(args.seed, "random"),
    }

    results: dict[str, Any] = {
        "checkpoint": {
            "path": args.ckpt_path,
            "tag": args.ckpt_tag,
            "boolq_limit": args.boolq_limit,
            "seed": args.seed,
        },
    }
    if args.models in ("noema", "both"):
        results["noema"] = run_model(args.ckpt_path, args.ckpt_tag, False, suites)
    if args.models in ("ema", "both"):
        results["ema"] = run_model(args.ckpt_path, args.ckpt_tag, True, suites)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    print(f"wrote {args.output}")
    for model, model_results in results.items():
        if model == "checkpoint":
            continue
        print(f"\n{model}")
        for suite_name, result in model_results.items():
            print(
                suite_name,
                "acc", f"{result['accuracy']:.4f}",
                "invalid", f"{result['invalid_rate']:.4f}",
                "targets", result["target_counts"],
                "preds", result["pred_counts"],
            )


if __name__ == "__main__":
    main()
