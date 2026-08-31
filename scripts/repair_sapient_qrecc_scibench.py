#!/usr/bin/env python3
"""Build complete, contract-explicit QReCC-II and SciBench supervision."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_variant", pa.string()),
        ("source_row", pa.int64()),
    ]
)
SPACE_RE = re.compile(r"[ \t]+")
OPEN_END_RE = re.compile(
    r"(?s)(?P<body>.*?)(?P<marker>"
    r"(?:Person|Speaker|Anonymous)\s*(?:2|B|Y)\)?\s*[:;]?|"
    r"P2\)?\s*[:;]?|\(?[12ABabxy]\)?[.:;]?|\[[^\]\n]{1,3}\][.:;]?|[-+*]"
    r")\s*$"
)
TAIL_LABELS = re.compile(
    r"(?im)^(?:Question|Input|Problem|Response|Consider this response|Write the conversation|"
    r"Write an example conversation|See the last examples|What might have been said)\s*[:.]"
)
ANSWER_PATTERNS = (
    re.compile(r"(?is)response\s*:\s*(.+?)(?:\s+(?:what came before|previous conversation|the preceding conversation|what was the preceding dialog)|\n|$)"),
    re.compile(r"(?is)response\s+(.+?)(?:\n|$)"),
    re.compile(r"(?is)(?:if this is the response|see this dialog response)[,.:]?\s*(.+?)(?:\s+what came before|\s+what was the preceding dialog|\n|$)"),
    re.compile(r"(?is)(?:read this response and predict the preceding dialog|write the conversation that led to this response)[.?:]?\s*(.+?)(?:\n|$)"),
    re.compile(r"(?is)(?:what might have been said before this|imagine the conversation that came before this response)[? .:]*(.+?)(?:\n|$)"),
    re.compile(r"(?is)what came before[.? :]*(.+?)(?:\n|$)"),
)


def clean(value: Any) -> str:
    text = str(value or "").replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines()).strip()


def current_prompt_block(instruction: str) -> str:
    matches = list(TAIL_LABELS.finditer(instruction))
    return instruction[matches[-1].start() :] if matches else instruction


def extract_supplied_answer(instruction: str) -> str | None:
    block = current_prompt_block(clean(instruction))
    for pattern in ANSWER_PATTERNS:
        match = pattern.search(block)
        if not match:
            continue
        answer = clean(match.group(1))
        answer = re.split(
            r"(?is)\s*(?:\+{3,}|\*{3,}|before this should be|came before|preceding (?:dialog|conversation)|solution)\s*:?",
            answer,
            maxsplit=1,
        )[0].strip(" \n\t\"'")
        if 2 <= len(answer) <= 2000 and not re.search(
            r"(?i)(predict the preceding|what came before|preceding dialog|^dialog:|^conversation:|"
            r"see the last examples|write an example conversation|^question:?$|^what$)",
            answer,
        ):
            return answer
    # Zero-shot templates often place the supplied answer on the first line.
    first = clean(block).splitlines()[0]
    first = re.sub(
        r"(?is)^(?:read this response and predict the preceding dialog|write the conversation that led to this response|"
        r"what might have been said before this|imagine the conversation that came before this response)\s*[? .:]*",
        "",
        first,
    ).strip(" \"'")
    if re.search(
        r"(?i)(predict the preceding|what came before|preceding dialog|^dialog:|^conversation:|"
        r"see the last examples|write an example conversation|^question:?$|^what$)",
        first,
    ):
        return None
    return first if 2 <= len(first) <= 2000 else None


def complete_dialogue(response: str, answer: str) -> str | None:
    response = clean(response)
    match = OPEN_END_RE.fullmatch(response)
    if not match:
        return None
    marker = match.group("marker").rstrip()
    separator = " " if marker.endswith((":", ";", ")", "]")) else " "
    return f"{match.group('body')}{marker}{separator}{answer}".strip()


def dialogue_context(response: str) -> str | None:
    """Remove the empty final-speaker marker while retaining the final question."""
    match = OPEN_END_RE.fullmatch(clean(response))
    if not match:
        return None
    context = match.group("body").rstrip()
    return context if len(context) >= 10 else None


def qrecc_task(context: str, supplied_turn: str) -> tuple[str, str, str] | None:
    """Convert input inversion into either answer or next-question supervision."""
    final_line = context.rstrip().splitlines()[-1].strip()
    if final_line.rstrip(" ;.").endswith("?"):
        if supplied_turn.rstrip(" ;.").endswith("?"):
            return None
        return (
            "answer",
            (
                "Answer the final question using the preceding conversation. Return only the answer to "
                f"that final question.\n\nConversation:\n{context}"
            ),
            supplied_turn,
        )
    if supplied_turn.rstrip(" ;.").endswith("?"):
        return (
            "next_question",
            (
                "Write the next user question that naturally follows this conversation. Return only the question.\n\n"
                f"Conversation:\n{context}"
            ),
            supplied_turn,
        )
    return None


def write_rows(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    columns: dict[str, list[Any]] = {name: [] for name in SCHEMA.names}
    for row in rows:
        for name in SCHEMA.names:
            columns[name].append(row[name])
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, path)
    return len(columns["response"])


def repair_qrecc(input_root: Path, output_root: Path) -> dict[str, Any]:
    variants = {
        "zsopt": input_root / "dialog_zsopt_data__qrecc_ii.parquet",
        "fsopt": input_root / "dialog_fsopt_data__qrecc_ii.parquet",
    }
    totals: Counter[str] = Counter()
    output_root.mkdir(parents=True, exist_ok=True)
    for variant, source in variants.items():
        repaired: list[dict[str, Any]] = []
        for index, row in enumerate(pq.read_table(source).to_pylist()):
            totals["seen"] += 1
            answer = extract_supplied_answer(row["instruction"])
            if answer is None:
                totals[f"{variant}_unparsed_answer"] += 1
                continue
            context = dialogue_context(row["response"])
            if context is None:
                totals[f"{variant}_not_open_dialogue"] += 1
                continue
            task = qrecc_task(context, answer)
            if task is None:
                totals[f"{variant}_contract_mismatch"] += 1
                continue
            mode, instruction, target = task
            repaired.append(
                {
                    "condition": "direct",
                    "instruction": instruction,
                    "response": target,
                    "source_variant": variant,
                    "source_row": index,
                }
            )
            totals[f"{variant}_{mode}"] += 1
        totals[f"{variant}_written"] = write_rows(output_root / f"{variant}.parquet", repaired)
    manifest = {
        "source_id": "sapient/QReCC-II synthetic variants",
        "repair": "convert the open final dialogue turn into grounded conversational QA",
        **dict(totals),
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def repair_scibench(source: Path, output_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    with source.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            row = json.loads(line)
            condition = clean(row.get("condition")).lower()
            instruction = clean(row.get("instruction"))
            response = clean(row.get("response"))
            counts["seen"] += 1
            if condition not in {"direct", "cot"} or not instruction or not response:
                counts["invalid"] += 1
                continue
            # Some inherited rows are mislabeled CoT despite containing only a
            # short final answer. Normalize from the observable target contract.
            if condition == "cot" and len(response) < 100:
                condition = "direct"
                counts["cot_reclassified_as_direct"] += 1
            if condition == "direct":
                instruction += (
                    "\n\nReturn only the concise final answer requested by the problem. "
                    "Do not add a derivation or explanatory prose."
                )
            else:
                instruction += "\n\nSolve the problem and show the derivation."
            rows.append(
                {
                    "condition": condition,
                    "instruction": instruction,
                    "response": response,
                    "source_variant": "scibench",
                    "source_row": index,
                }
            )
            counts[f"written_{condition}"] += 1
    output_root.mkdir(parents=True, exist_ok=True)
    written = write_rows(output_root / "train.parquet", rows)
    manifest = {
        "source_id": "Sapient/Platypus SciBench",
        "repair": "make the direct-versus-reasoning response contract explicit without changing answers",
        "written": written,
        **dict(counts),
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qrecc-input-root",
        type=Path,
        default=Path("data/downloads/datasets/sapient_cleaned/data_clustered/flan"),
    )
    parser.add_argument(
        "--qrecc-output-root",
        type=Path,
        default=Path("data/converted_sources/sapient_qrecc_ii_repaired"),
    )
    parser.add_argument(
        "--scibench-input",
        type=Path,
        default=Path("data/downloads/datasets/sapient_cleaned/data/Platypus/scibench.jsonl"),
    )
    parser.add_argument(
        "--scibench-output-root",
        type=Path,
        default=Path("data/converted_sources/sapient_scibench_repaired"),
    )
    args = parser.parse_args()
    print(json.dumps(repair_qrecc(args.qrecc_input_root, args.qrecc_output_root), indent=2))
    print(json.dumps(repair_scibench(args.scibench_input, args.scibench_output_root), indent=2))


if __name__ == "__main__":
    main()
