#!/usr/bin/env python3
"""Evaluate a prefix of MMLU through SimpleEngine or VLLMEngine and save generations."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.benchmarks import MMLU
from evaluation.engines import SimpleEngine, VLLMEngine


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def build_engine(args: argparse.Namespace):
    if args.engine == "simple":
        return SimpleEngine(
            ckpt_path=args.ckpt_path,
            ckpt_tag=args.ckpt_tag,
            ckpt_epoch=args.ckpt_epoch,
            ckpt_use_ema=args.ckpt_use_ema,
        )
    return VLLMEngine(
        ckpt_path=args.ckpt_path,
        prompt_mode=args.prompt_mode,
        dtype=args.dtype,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        enforce_eager=args.enforce_eager,
        trust_remote_code=False,
    )


def score(generations: list[str], ground_truths: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    correct = 0.0
    invalid = 0
    pred_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    for idx, (generation, gt) in enumerate(zip(generations, ground_truths, strict=True)):
        pred = generation.strip().upper()
        gold = gt["gold"]
        target_counts[gold] += 1
        if pred not in gt["valid_set"]:
            invalid += 1
            pred_counts["<invalid>"] += 1
            item_correct = 1.0 / len(gt["valid_set"])
        else:
            pred_counts[pred] += 1
            item_correct = 1.0 if pred == gold else 0.0
        correct += item_correct
        rows.append(
            {
                "index": idx,
                "generation": generation,
                "prediction": pred if pred in gt["valid_set"] else None,
                "gold": gold,
                "subject": gt.get("subject"),
                "correct": item_correct,
            }
        )
    total = len(generations)
    acc = correct / total if total else 0.0
    return {
        "n": total,
        "acc": acc,
        "stderr": math.sqrt(acc * (1.0 - acc) / total) if total else 0.0,
        "invalid": invalid / total if total else 0.0,
        "pred_counts": dict(pred_counts),
        "target_counts": dict(target_counts),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("simple", "vllm"), required=True)
    parser.add_argument("--ckpt-path", required=True)
    parser.add_argument("--ckpt-tag")
    parser.add_argument("--ckpt-epoch", type=int)
    parser.add_argument("--ckpt-use-ema", type=parse_bool, default=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-context", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--condition", default="direct")
    parser.add_argument("--prompt-mode", default="hrm_tokens")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.05)
    parser.add_argument("--enforce-eager", type=parse_bool, default=True)
    args = parser.parse_args()

    if args.ckpt_tag and args.ckpt_epoch is not None:
        parser.error("Specify only one of --ckpt-tag and --ckpt-epoch")

    benchmark = MMLU(special_shots={"high_school_european_history": 3})
    prompts = benchmark.prompts[: args.max_samples]
    ground_truths = benchmark.ground_truths[: args.max_samples]

    started = time.monotonic()
    engine = build_engine(args)
    load_done = time.monotonic()
    generations = engine.generate(
        prompts,
        batch_size=args.batch_size,
        max_context=args.max_context,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        condition=args.condition,
    )
    done = time.monotonic()
    result = score(generations, ground_truths)
    result["engine"] = args.engine
    result["ckpt_path"] = args.ckpt_path
    result["ckpt_tag"] = args.ckpt_tag
    result["timing"] = {
        "load_seconds": load_done - started,
        "generation_seconds": done - load_done,
        "total_seconds": done - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: result[k] for k in ("engine", "n", "acc", "invalid", "pred_counts", "target_counts", "timing")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
