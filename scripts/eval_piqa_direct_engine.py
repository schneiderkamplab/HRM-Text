#!/usr/bin/env python3
"""Evaluate PIQA-da through SimpleEngine or direct VLLMEngine, without chat serving."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.engines import SimpleEngine, VLLMEngine


DEFAULT_DATASET_PATH = REPO_ROOT / "dfm-evals/dfm_evals/tasks/piqa/piqa-dan.json"
PROMPT_TEMPLATE_DA = """Du får et spørgsmål om fysisk hverdagsfornuft og to svarmuligheder.
Vælg den bedste løsning.

Spørgsmål:
{prompt}

Mulighed A:
{solution0}

Mulighed B:
{solution1}

Svar kun med A eller B."""
RE_ANY_CHOICE = re.compile(r"\b([AaBb])\b")


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for row in rows:
        label = int(row["label"])
        solution0 = str(row["solution0"]).strip()
        solution1 = str(row["solution1"]).strip()
        cases.append(
            {
                "id": str(row.get("id", len(cases))),
                "prompt": PROMPT_TEMPLATE_DA.format(
                    prompt=str(row["prompt"]).strip(),
                    solution0=solution0,
                    solution1=solution1,
                ),
                "target": "A" if label == 0 else "B",
                "solution0": solution0,
                "solution1": solution1,
            }
        )
    return cases


def normalize_for_match(text: str) -> str:
    return " ".join(text.lower().split())


def extract_letter_choice(text: str) -> str | None:
    if not text:
        return None
    choices = [match.group(1).upper() for match in RE_ANY_CHOICE.finditer(text)]
    if len(set(choices)) == 1:
        return choices[0]
    return None


def extract_choice(text: str, solution0: str, solution1: str) -> str | None:
    choice = extract_letter_choice(text)
    if choice is not None:
        return choice

    normalized = normalize_for_match(text)
    sol0 = normalize_for_match(solution0)
    sol1 = normalize_for_match(solution1)
    has_0 = sol0 != "" and sol0 in normalized
    has_1 = sol1 != "" and sol1 in normalized
    if has_0 and not has_1:
        return "A"
    if has_1 and not has_0:
        return "B"
    return None


def score_cases(cases: list[dict[str, Any]], outputs: list[str]) -> dict[str, Any]:
    records = []
    correct = 0
    invalid = 0
    pred_counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for case, output in zip(cases, outputs, strict=True):
        prediction = extract_choice(output, case["solution0"], case["solution1"])
        target = case["target"]
        is_correct = prediction == target
        correct += int(is_correct)
        if prediction is None:
            invalid += 1
        pred_key = prediction if prediction is not None else "<invalid>"
        pred_counts[pred_key] = pred_counts.get(pred_key, 0) + 1
        target_counts[target] = target_counts.get(target, 0) + 1
        records.append(
            {
                "id": case["id"],
                "target": target,
                "prediction": prediction,
                "correct": is_correct,
                "completion": output,
            }
        )

    total = len(cases)
    accuracy = correct / total if total else 0.0
    stderr = math.sqrt(accuracy * (1.0 - accuracy) / total) if total else 0.0
    return {
        "n": total,
        "accuracy": accuracy,
        "stderr": stderr,
        "invalid_rate": invalid / total if total else 0.0,
        "target_counts": target_counts,
        "pred_counts": pred_counts,
        "records": records,
    }


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
        attention_backend=args.attention_backend,
        trust_remote_code=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("simple", "vllm"), required=True)
    parser.add_argument("--ckpt-path", required=True)
    parser.add_argument("--ckpt-tag")
    parser.add_argument("--ckpt-epoch", type=int)
    parser.add_argument("--ckpt-use-ema", type=parse_bool, default=True)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-context", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--condition", default="direct")
    parser.add_argument("--prompt-mode", default="hrm")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.25)
    parser.add_argument("--enforce-eager", type=parse_bool, default=True)
    parser.add_argument("--attention-backend")
    args = parser.parse_args()

    if args.ckpt_tag and args.ckpt_epoch is not None:
        parser.error("Specify only one of --ckpt-tag and --ckpt-epoch")

    cases = load_cases(args.dataset_path)
    started = time.monotonic()
    engine = build_engine(args)
    load_done = time.monotonic()
    outputs = engine.generate(
        [case["prompt"] for case in cases],
        batch_size=args.batch_size,
        max_context=args.max_context,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        condition=args.condition,
    )
    done = time.monotonic()
    result = score_cases(cases, outputs)
    result["engine"] = args.engine
    result["ckpt_path"] = args.ckpt_path
    result["ckpt_tag"] = args.ckpt_tag
    result["ckpt_epoch"] = args.ckpt_epoch
    result["timing"] = {
        "load_seconds": load_done - started,
        "generation_seconds": done - load_done,
        "total_seconds": done - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: result[k] for k in ("engine", "n", "accuracy", "stderr", "invalid_rate", "target_counts", "pred_counts", "timing")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
