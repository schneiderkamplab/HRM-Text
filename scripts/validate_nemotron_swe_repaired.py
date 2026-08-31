#!/usr/bin/env python3
"""Validate structural invariants of repaired Nemotron SWE JSONL windows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from tqdm import tqdm

try:
    from scripts.repair_nemotron_swe_sources import (
        AGENTLESS_SYSTEM_PROMPT,
        PHASE_HEADING_RE,
        SYSTEM_PROMPT,
        normalized_call,
    )
except ModuleNotFoundError:
    from repair_nemotron_swe_sources import (
        AGENTLESS_SYSTEM_PROMPT,
        PHASE_HEADING_RE,
        SYSTEM_PROMPT,
        normalized_call,
    )


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/converted_sources/nemotron_swe_repaired"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/nemotron_swe_repair/validation_summary.json"),
    )
    return parser.parse_args()


def validate_row(row: dict, counts: Counter[str]) -> None:
    messages = row.get("messages")
    tools = row.get("tools")
    if not isinstance(messages, list) or len(messages) < 3:
        counts["invalid_messages"] += 1
        return
    if row.get("target_message_index") != len(messages) - 1:
        counts["wrong_target_index"] += 1
    if messages[0].get("role") != "system" or messages[1].get("role") != "user":
        counts["wrong_prefix_roles"] += 1
    kind = row.get("target_kind")
    if kind != "agentless":
        if messages[0].get("content") != SYSTEM_PROMPT:
            counts["wrong_system_prompt"] += 1
        if "Issue to resolve:" not in str(messages[1].get("content") or ""):
            counts["unclean_user_prompt"] += 1
        if not isinstance(tools, list) or {tool.get("function", {}).get("name") for tool in tools} != {
            "execute_bash",
            "str_replace_editor",
        }:
            counts["wrong_tools"] += 1
    elif messages[0].get("content") != AGENTLESS_SYSTEM_PROMPT:
        counts["wrong_agentless_system_prompt"] += 1

    target = messages[-1]
    if target.get("role") != "assistant":
        counts["target_not_assistant"] += 1
    if kind != "agentless" and PHASE_HEADING_RE.search(str(target.get("content") or "")):
        counts["phase_heading"] += 1
    target_call = normalized_call(target)
    if kind == "tool":
        if target_call is None or target_call[0] not in {"execute_bash", "str_replace_editor"}:
            counts["invalid_tool_target"] += 1
    elif kind == "finish":
        if target_call is not None or not str(target.get("content") or "").strip():
            counts["invalid_finish_target"] += 1
    elif kind == "agentless":
        if (
            target_call is not None
            or not str(target.get("content") or "").strip()
            or tools
            or set(target) != {"role", "content"}
        ):
            counts["invalid_agentless_target"] += 1
    else:
        counts["unknown_target_kind"] += 1

    history = messages[2:-1]
    if len(history) % 2:
        counts["odd_history"] += 1
        return
    for index in range(0, len(history), 2):
        assistant, tool = history[index : index + 2]
        call = normalized_call(assistant)
        if assistant.get("role") != "assistant" or call is None or call[0] not in {
            "execute_bash",
            "str_replace_editor",
        }:
            counts["invalid_history_assistant"] += 1
            continue
        if tool.get("role") != "tool" or str(tool.get("tool_call_id")) != str(call[2].get("id")):
            counts["invalid_history_tool"] += 1


def main() -> None:
    args = arguments()
    files = sorted(args.input_dir.glob("swe/*.jsonl")) + sorted(args.input_dir.glob("agentless/*.jsonl"))
    counts: Counter[str] = Counter()
    for path in tqdm(files, desc="Validating repaired Nemotron SWE"):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                counts["rows"] += 1
                validate_row(json.loads(line), counts)
    failure_keys = [key for key in counts if key != "rows"]
    summary = {
        "input_dir": str(args.input_dir),
        "files": len(files),
        "rows": counts["rows"],
        "failures": {key: counts[key] for key in sorted(failure_keys) if counts[key]},
    }
    summary["valid"] = len(files) == 33 and not summary["failures"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps(summary, indent=2))
    if not summary["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
