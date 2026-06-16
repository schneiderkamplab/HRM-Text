#!/usr/bin/env python3
"""Sample GSM8k rows, run an HRM checkpoint, and bucket failure modes."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.benchmarks import GSM8k  # noqa: E402
from evaluation.engines import SimpleEngine  # noqa: E402
from utils.functions import last_boxed_only_string  # noqa: E402


NUMBER_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")


@dataclass(frozen=True)
class Bucket:
    name: str
    description: str


BUCKETS = {
    "correct": Bucket("correct", "Parsed final integer matches the GSM8k target."),
    "invalid_no_final_number": Bucket(
        "invalid_no_final_number",
        "The completion has no scorer-parseable final integer or boxed answer.",
    ),
    "format_extraction_mismatch": Bucket(
        "format_extraction_mismatch",
        "The gold answer appears in the text, but the final parsed answer is missing or different.",
    ),
    "arithmetic_slip": Bucket(
        "arithmetic_slip",
        "The reasoning appears to choose the right quantities/operation family but computes the wrong integer.",
    ),
    "wrong_setup_or_operation": Bucket(
        "wrong_setup_or_operation",
        "The answer uses the wrong quantities, skips a condition, or applies the wrong operation.",
    ),
    "under_reasoned_guess": Bucket(
        "under_reasoned_guess",
        "The response gives a short unsupported number or generic reasoning with no clear derivation.",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt-path", default="checkpoints/dfm5/L")
    parser.add_argument("--ckpt-tag", default="step_200000")
    parser.add_argument("--ckpt-epoch", type=int, default=None)
    parser.add_argument("--no-ema", action="store_true")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-context", type=int, default=3072)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--prompt-style",
        choices=("eval", "show_work"),
        default="eval",
        help="`eval` uses the raw GSM8k question, `show_work` asks for reasoning and a boxed final answer.",
    )
    parser.add_argument("--output", type=Path, default=Path("logs/analysis/gsm8k_smoke_dfm5_L_step200000.json"))
    parser.add_argument("--report", type=Path, default=Path("logs/analysis/gsm8k_smoke_dfm5_L_step200000.md"))
    return parser.parse_args()


def extract_truth(answer: str) -> int:
    return int(answer.split("####")[-1].strip().replace(",", ""))


def extract_answer(text: str) -> int | None:
    boxed = last_boxed_only_string(text)
    if boxed:
        text = boxed
    text = text.replace(",", "").replace("$", "").strip()
    try:
        return int(float(text))
    except (ValueError, OverflowError):
        return None


def all_numbers(text: str) -> list[float]:
    out = []
    for match in NUMBER_RE.finditer(text.replace("$", "")):
        raw = match.group(0).replace(",", "")
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def has_boxed(text: str) -> bool:
    return last_boxed_only_string(text) is not None


def classify_failure(question: str, gold: int, pred: int | None, completion: str) -> str:
    text = completion.strip()
    if pred == gold:
        return "correct"
    if not text:
        return "invalid_no_final_number"

    normalized_text = text.replace(",", "")
    if str(gold) in normalized_text and (pred is None or pred != gold):
        return "format_extraction_mismatch"

    if pred is None:
        return "invalid_no_final_number"

    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 12:
        return "under_reasoned_guess"

    q_numbers = set(all_numbers(question))
    out_numbers = all_numbers(text)
    non_question_numbers = [n for n in out_numbers if n not in q_numbers]

    operation_markers = ("+", "-", "*", "/", " x ", "times", "total", "left", "remaining", "each", "percent", "%")
    has_operation = any(marker in text.lower() for marker in operation_markers)
    if has_operation and len(non_question_numbers) >= 2:
        lower = text.lower()
        if any(marker in lower for marker in ("wrong", "should", "instead", "however")):
            return "wrong_setup_or_operation"
        return "arithmetic_slip"

    return "wrong_setup_or_operation"


def truncate(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"


def markdown_table(rows: list[dict[str, Any]]) -> str:
    counts = Counter(row["bucket"] for row in rows)
    examples: dict[str, dict[str, Any]] = {}
    for row in rows:
        examples.setdefault(row["bucket"], row)

    lines = [
        "# GSM8k 100-row smoke error analysis",
        "",
        "Checkpoint: `dfm5/L step_200000`, EMA weights, `condition=direct`, `temperature=0.0`, `max_tokens=512`.",
        "",
        "| Bucket | Description | Count | Example |",
        "|---|---|---:|---|",
    ]
    for bucket_key in BUCKETS:
        if counts[bucket_key] == 0:
            continue
        bucket = BUCKETS[bucket_key]
        row = examples[bucket_key]
        if bucket_key == "correct":
            example = (
                f"Q: {truncate(row['question'], 120)}<br>"
                f"gold={row['gold']} pred={row['pred']}"
            )
        else:
            example = (
                f"Q: {truncate(row['question'], 95)}<br>"
                f"gold={row['gold']} pred={row['pred']}<br>"
                f"completion: {truncate(row['completion'], 135)}"
            )
        lines.append(f"| `{bucket.name}` | {bucket.description} | {counts[bucket_key]} | {example} |")
    lines.append("")
    lines.append(f"Accuracy in this sample: `{counts['correct']}/{len(rows)}`.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    dataset = load_dataset("gsm8k", "main", split="test")
    rng = random.Random(args.seed)
    indices = rng.sample(range(len(dataset)), args.sample_size)
    prompts = [str(dataset[i]["question"]) for i in indices]
    if args.prompt_style == "show_work":
        prompts_for_model = [
            (
                "Solve the following grade-school math problem. Show the calculation briefly, "
                "then put only the final numeric answer in \\boxed{}.\n\n"
                f"Problem: {prompt}\n\nSolution:"
            )
            for prompt in prompts
        ]
    else:
        prompts_for_model = prompts
    golds = [extract_truth(str(dataset[i]["answer"])) for i in indices]

    ckpt_tag = None if args.ckpt_epoch is not None else args.ckpt_tag
    engine = SimpleEngine(
        ckpt_path=args.ckpt_path,
        ckpt_epoch=args.ckpt_epoch,
        ckpt_tag=ckpt_tag,
        ckpt_use_ema=not args.no_ema,
    )
    completions = engine.generate(
        prompts_for_model,
        batch_size=args.batch_size,
        max_context=args.max_context,
        max_tokens=args.max_tokens,
        temperature=0.0,
        condition="direct",
    )

    scorer = GSM8k()
    rows: list[dict[str, Any]] = []
    for index, question, model_prompt, gold, completion in zip(indices, prompts, prompts_for_model, golds, completions, strict=True):
        pred = scorer._extract_answer(completion)
        bucket = classify_failure(question, gold, pred, completion)
        rows.append(
            {
                "dataset_index": index,
                "question": question,
                "model_prompt": model_prompt,
                "gold": gold,
                "pred": pred,
                "completion": completion,
                "bucket": bucket,
                "has_boxed_answer": has_boxed(completion),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(markdown_table(rows), encoding="utf-8")
    print(args.output)
    print(args.report)
    print(json.dumps(Counter(row["bucket"] for row in rows), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
