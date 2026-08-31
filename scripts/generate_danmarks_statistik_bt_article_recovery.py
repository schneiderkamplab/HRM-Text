#!/usr/bin/env python3
"""Generate article-grounded Danish instruction pairs for rejected DST rows."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    import scripts.generate_danmarks_statistik_bt_prompts as engine
except ModuleNotFoundError:
    import generate_danmarks_statistik_bt_prompts as engine


SYSTEM = """Du skaber dansk instruktionsdata fra en fuld artikel fra Danmarks Statistik.
Skriv én naturlig, selvstændig brugerprompt og ét direkte, fyldestgørende assistentsvar.
Parret skal fokusere på emnet i den oprindelige passage, men må bruge relevante oplysninger
fra hele artikeluddraget til at gøre svaret komplet. Hver faktuel påstand og hvert tal i svaret
skal være udtrykkeligt understøttet af artikeluddraget. Opfind eller beregn ikke manglende tal.
Prompten må ikke bede om oplysninger, som svaret ikke giver, og svaret må ikke foregive at have
nyere information end artiklen. Undgå omtale af måltekst, artikeluddrag, datasæt og generering.
Afvis rækken, hvis artikeluddraget er utilstrækkeligt, støjfyldt eller ikke gør et nyttigt,
selvstændigt par muligt. Returnér kun JSON."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "dst_article_recovery",
        "schema": {
            "type": "object",
            "properties": {
                "usable": {"type": "boolean"},
                "prompt": {"type": "string", "maxLength": 1200},
                "answer": {"type": "string", "maxLength": 5000},
                "reason": {"type": "string", "maxLength": 400},
            },
            "required": ["usable", "prompt", "answer", "reason"],
            "additionalProperties": False,
        },
    },
}
PROMPT_VERSION = "dst_article_recovery_31b_v1_20260829"


def fail_close_errors(args: argparse.Namespace) -> None:
    converted = 0
    for index in range(args.partitions):
        path = args.partition_root / f"partition_{index}.jsonl"
        rows = list(engine.read_jsonl(path))
        changed = False
        for row in rows:
            if "generation_error" not in row:
                continue
            if row.get("generator_model") != args.expected_model:
                raise ValueError(
                    f"partition {index} error row has generator_model="
                    f"{row.get('generator_model')!r}; expected {args.expected_model!r}"
                )
            error = row.pop("generation_error")
            row.update(
                {
                    "generator_prompt_version": PROMPT_VERSION,
                    "usable": False,
                    "generated_prompt": "",
                    "generated_answer": "",
                    "reason": f"terminal_generator_error_after_retry_budget: {error}",
                    "terminal_generation_rejection": True,
                }
            )
            changed = True
            converted += 1
        if changed:
            temporary = path.with_name(f".{path.name}.tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            temporary.replace(path)
    print(json.dumps({"terminal_generation_rejections": converted}, indent=2))


def parse_content(content: str) -> tuple[dict[str, Any], bool]:
    try:
        return json.loads(content), False
    except json.JSONDecodeError:
        pass
    fields: dict[str, Any] = {}
    usable = re.search(r'"usable"\s*:\s*(true|false)', content)
    if usable is None:
        raise ValueError("truncated response lacks usable")
    fields["usable"] = usable.group(1) == "true"
    for name in ("prompt", "answer", "reason"):
        match = re.search(rf'"{name}"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
        if match is None and (name != "reason" or fields["usable"]):
            raise ValueError(f"truncated response lacks {name}")
        fields[name] = json.loads(match.group(1)) if match else "recovered constrained JSON"
    return fields, True


def request(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "titel": row["title"],
                        "indholdstype": row["content_type"],
                        "oprindelig_prompt_til_diagnose": row["original_prompt"],
                        "oprindelig_kort_passage": row["original_target"],
                        # Keep generation comfortably inside the E4B 8K context.
                        # The independent audit still receives the complete
                        # 20K-character evidence excerpt from the candidate.
                        "fuldt_artikeluddrag_som_eneste_kilde": row["article_excerpt"][:8000],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.25,
        "top_p": 0.95,
        "max_tokens": args.max_tokens,
        "response_format": RESPONSE_FORMAT,
    }
    import time
    import urllib.request

    error: Exception | None = None
    for attempt in range(args.retries + 1):
        try:
            req = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                payload = json.load(response)
            parsed, recovered = parse_content(payload["choices"][0]["message"]["content"])
            result = {
                "sample_id": row["sample_id"],
                "source_row": row["source_row_index"],
                "generator_model": args.model,
                "generator_prompt_version": PROMPT_VERSION,
                "usable": bool(parsed["usable"]),
                "generated_prompt": str(parsed["prompt"]).strip(),
                "generated_answer": str(parsed["answer"]).strip(),
                "reason": str(parsed["reason"]).strip(),
            }
            if recovered:
                result["recovered_from_constrained_json_stall"] = True
            return result
        except Exception as exc:
            error = exc
            if attempt < args.retries:
                time.sleep(min(8.0, 1.5**attempt))
    return {
        "sample_id": row["sample_id"],
        "source_row": row["source_row_index"],
        "generator_model": args.model,
        "generator_prompt_version": PROMPT_VERSION,
        "generation_error": f"{type(error).__name__}: {error}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("--requests", type=Path, required=True)
    generate_parser.add_argument("--output", type=Path, required=True)
    generate_parser.add_argument("--base-url", required=True)
    generate_parser.add_argument("--model", required=True)
    generate_parser.add_argument("--partitions", type=int, default=8)
    generate_parser.add_argument("--partition-index", type=int, required=True)
    generate_parser.add_argument("--concurrency", type=int, default=32)
    generate_parser.add_argument("--retries", type=int, default=3)
    generate_parser.add_argument("--timeout", type=float, default=300)
    generate_parser.add_argument("--max-tokens", type=int, default=2048)
    generate_parser.add_argument("--progress-interval", type=int, default=100)
    generate_parser.add_argument("--resume", action="store_true")
    generate_parser.set_defaults(func=engine.generate)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--requests", type=Path, required=True)
    merge_parser.add_argument("--partition-root", type=Path, required=True)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.add_argument("--expected-model", required=True)
    merge_parser.set_defaults(func=engine.merge)
    fail_close_parser = commands.add_parser("fail-close-errors")
    fail_close_parser.add_argument("--partition-root", type=Path, required=True)
    fail_close_parser.add_argument("--partitions", type=int, default=8)
    fail_close_parser.add_argument("--expected-model", required=True)
    fail_close_parser.set_defaults(func=fail_close_errors)
    args = parser.parse_args()
    engine.request = request
    args.func(args)


if __name__ == "__main__":
    main()
