#!/usr/bin/env python3
"""Translate, audit, and materialize Danish Model Charter SFT/DPO rows."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/downloads/datasets/dfm10_synthetic_values_model_charter"
WORK = ROOT / "data/dfm10_model_charter_da_work"
OUTPUT = ROOT / "data/converted_sources/dfm10_synthetic_values_model_charter_da"
PREFERENCE = ROOT / "data/dfm10_preference_pairs/synthetic_values_model_charter_da.jsonl"
PACKAGE = ROOT / "exports_dfm10/dfm10-synthetic-values-model-charter-da"
SPACE = re.compile(r"\s+")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    temporary.replace(path)
    return count


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def latest(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if row.get("request_id"):
            result[str(row["request_id"])] = row
    return result


def normalize(value: Any) -> str:
    return SPACE.sub(" ", str(value or "")).strip()


def extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def completion(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    retries: int,
) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }).encode()
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return str(json.load(response)["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed: {error}")


def run_parallel(
    rows: list[dict[str, Any]],
    function: Callable[[dict[str, Any]], dict[str, Any]],
    output: Path,
    concurrency: int,
    label: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(concurrency) as pool:
        iterator = iter(rows)
        pending: set[Any] = set()

        def fill() -> None:
            while len(pending) < concurrency:
                try:
                    pending.add(pool.submit(function, next(iterator)))
                except StopIteration:
                    return

        fill()
        completed = 0
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                pending.remove(future)
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 25 == 0:
                    print(f"{label} {completed}/{len(rows)}", flush=True)
            fill()
    print(f"{label} {completed}/{len(rows)}", flush=True)


def prepare(args: argparse.Namespace) -> None:
    sft: dict[str, dict[str, Any]] = {}
    dpo: dict[str, dict[str, Any]] = {}
    for split in ("train", "test"):
        for row in iter_jsonl(args.source / f"sft_{split}.jsonl"):
            row["source_split"] = split
            sft[str(row["scenario_id"])] = row
        for row in iter_jsonl(args.source / f"dpo_{split}.jsonl"):
            row["source_split"] = split
            dpo[str(row["scenario_id"])] = row
    if set(sft) != set(dpo):
        raise ValueError("SFT and DPO scenario sets differ")
    rows: list[dict[str, Any]] = []
    for scenario_id in sorted(sft):
        a, b = sft[scenario_id], dpo[scenario_id]
        if a["prompt"] != b["prompt"] or a["response"] != b["chosen"]:
            raise ValueError(f"unaligned scenario {scenario_id}")
        rows.append({
            "request_id": scenario_id,
            "scenario_id": scenario_id,
            "source_split": a["source_split"],
            "sft_source_id": a["id"],
            "dpo_source_id": b["id"],
            "value_unit_id": a["value_unit_id"],
            "prompt_en": a["prompt"],
            "chosen_en": a["response"],
            "rejected_en": b["rejected"],
            "rejection_rationale_en": b.get("rejection_rationale", ""),
        })
    requests = args.work / "requests"
    requests.mkdir(parents=True, exist_ok=True)
    for shard in range(args.shards):
        atomic_jsonl(
            requests / f"part-{shard:02d}-of-{args.shards:02d}.jsonl",
            (row for row in rows if int(hashlib.sha256(row["request_id"].encode()).hexdigest()[:16], 16) % args.shards == shard),
        )
    atomic_json(args.work / "requests.summary.json", {"rows": len(rows), "shards": args.shards})
    print(json.dumps({"rows": len(rows), "shards": args.shards}))


def translation_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    payload = {key: row[key] for key in (
        "request_id", "prompt_en", "chosen_en", "rejected_en", "rejection_rationale_en"
    )}
    return [
        {"role": "system", "content": (
            "Translate and culturally adapt this complete English preference-training tuple into natural modern Danish. "
            "Preserve meaning, detail, safety boundaries, uncertainty, and the exact distinction between the preferred "
            "and rejected answers. Do not improve the rejected answer or weaken the preferred answer. Translate the "
            "rationale faithfully. Return only one JSON object and no commentary."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + (
            '\nReturn exactly {"request_id":"...","prompt_da":"...","chosen_da":"...",'
            '"rejected_da":"...","rejection_rationale_da":"..."}.'
        )},
    ]


def translate(args: argparse.Namespace) -> None:
    accepted = {key for key, row in latest(args.audit_output).items() if row.get("accepted") is True}
    rows = [row for row in iter_jsonl(args.input) if row["request_id"] not in accepted]

    def one(row: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = completion(args.base_url, args.model, translation_messages(row), args.max_tokens, args.timeout, args.retries)
            value = extract_json(raw)
            errors = []
            if value.get("request_id") != row["request_id"]:
                errors.append("wrong_request_id")
            for source, target in (("prompt_en", "prompt_da"), ("chosen_en", "chosen_da"), ("rejected_en", "rejected_da")):
                value[target] = normalize(value.get(target))
                if len(value[target]) < max(8, int(len(row[source]) * 0.3)):
                    errors.append(f"short_{target}")
                if len(value[target]) > max(300, int(len(row[source]) * 2.2)):
                    errors.append(f"long_{target}")
            value["rejection_rationale_da"] = normalize(value.get("rejection_rationale_da"))
            if normalize(row["rejection_rationale_en"]) and not value["rejection_rationale_da"]:
                errors.append("missing_rejection_rationale_da")
            return {**value, "request_id": row["request_id"], "translation_ok": not errors, "errors": errors, "teacher_model": args.model}
        except Exception as exc:
            return {"request_id": row["request_id"], "translation_ok": False, "errors": [type(exc).__name__], "raw": raw[-1000:]}

    run_parallel(rows, one, args.output, args.concurrency, "translate")


def audit_messages(source: dict[str, Any], translated: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": (
            "Independently audit an English-to-Danish preference tuple. Check Danish naturalness, semantic fidelity of "
            "all four translated fields, preservation of safety/value behavior, and preservation of which answer is "
            "preferred. Accept only if every score is at least 4/5 and preference_preserved is true. Return JSON only."
        )},
        {"role": "user", "content": json.dumps({"source": source, "translation": translated}, ensure_ascii=False) + (
            '\nReturn {"request_id":"...","language_quality":1,"prompt_fidelity":1,"chosen_fidelity":1,'
            '"rejected_fidelity":1,"rationale_fidelity":1,"preference_preserved":true,"accepted":false,"issues":[]}.'
        )},
    ]


def audit(args: argparse.Namespace) -> None:
    accepted = {key for key, row in latest(args.output).items() if row.get("accepted") is True}
    translations = latest(args.input)
    rows = [row for row in iter_jsonl(args.requests) if row["request_id"] not in accepted]

    def one(row: dict[str, Any]) -> dict[str, Any]:
        translated = translations.get(row["request_id"], {})
        if not translated.get("translation_ok"):
            return {"request_id": row["request_id"], "accepted": False, "issues": ["translation_not_ok"]}
        raw = ""
        try:
            raw = completion(args.base_url, args.model, audit_messages(row, translated), args.max_tokens, args.timeout, args.retries)
            value = extract_json(raw)
            scores = [int(value.get(key, 0)) for key in (
                "language_quality", "prompt_fidelity", "chosen_fidelity", "rejected_fidelity", "rationale_fidelity"
            )]
            accepted_value = (
                value.get("request_id") == row["request_id"]
                and min(scores) >= args.min_score
                and value.get("preference_preserved") is True
                and value.get("accepted") is True
            )
            return {**value, "request_id": row["request_id"], "accepted": accepted_value, "judge_model": args.model}
        except Exception as exc:
            return {"request_id": row["request_id"], "accepted": False, "issues": [type(exc).__name__], "raw": raw[-1000:]}

    run_parallel(rows, one, args.output, args.concurrency, "audit")


def build(args: argparse.Namespace) -> None:
    requests: dict[str, dict[str, Any]] = {}
    translations: dict[str, dict[str, Any]] = {}
    audits: dict[str, dict[str, Any]] = {}
    for path in sorted((args.work / "requests").glob("*.jsonl")):
        requests.update({row["request_id"]: row for row in iter_jsonl(path)})
    for path in sorted((args.work / "translations").glob("*.jsonl")):
        translations.update(latest(path))
    for path in sorted((args.work / "audits").glob("*.jsonl")):
        audits.update(latest(path))
    accepted_ids = sorted(key for key in requests if audits.get(key, {}).get("accepted") is True)
    if len(accepted_ids) < args.min_accepted:
        raise RuntimeError(f"accepted {len(accepted_ids)} < required {args.min_accepted}")

    sft_rows: list[dict[str, Any]] = []
    preference_rows: list[dict[str, Any]] = []
    package_rows: list[dict[str, Any]] = []
    for key in accepted_ids:
        source, translated, judged = requests[key], translations[key], audits[key]
        metadata = {name: source[name] for name in (
            "scenario_id", "source_split", "sft_source_id", "dpo_source_id", "value_unit_id"
        )}
        sft_rows.append({
            "condition": "direct", "instruction": translated["prompt_da"], "response": translated["chosen_da"],
            "rejected": translated["rejected_da"], "rejection_rationale": translated["rejection_rationale_da"],
            "prompt_en": source["prompt_en"], "chosen_en": source["chosen_en"], "rejected_en": source["rejected_en"],
            "rejection_rationale_en": source["rejection_rationale_en"], "translation_audit": judged, **metadata
        })
        preference = {
            "source": "danish-foundation-models/synthetic-values-model-charter",
            "prompt": translated["prompt_da"], "chosen": translated["chosen_da"],
            "rejected": translated["rejected_da"], "rejection_rationale": translated["rejection_rationale_da"],
            **metadata,
        }
        preference_rows.append(preference)
        package_rows.append({
            **preference,
            "messages": [{"role": "user", "content": translated["prompt_da"]}, {"role": "assistant", "content": translated["chosen_da"]}],
            "prompt_en": source["prompt_en"], "chosen_en": source["chosen_en"],
            "rejected_en": source["rejected_en"], "rejection_rationale_en": source["rejection_rationale_en"],
            "translation_audit": judged,
        })

    source_path = args.output / "data/model_charter_values_da.jsonl"
    atomic_jsonl(source_path, sft_rows)
    atomic_jsonl(args.preference_output, preference_rows)
    data_path = args.package / "data/train-00000.jsonl.gz"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = data_path.with_suffix(data_path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        for row in package_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(data_path)
    args.package.mkdir(parents=True, exist_ok=True)
    (args.package / "README.md").write_text(
        "---\nlicense: other\nlanguage:\n- da\ntask_categories:\n- text-generation\npretty_name: Danish Synthetic Values Model Charter\n---\n\n"
        "# Danish Synthetic Values Model Charter\n\nGemma 4 31B Danish adaptations of the accepted SFT and DPO tuples from "
        "`danish-foundation-models/synthetic-values-model-charter`. English originals, stable scenario/value IDs, "
        "preference pairs, and independent translation-audit results are retained.\n"
    )
    manifest = {
        "name": args.package.name,
        "rows": len(accepted_ids),
        "source_rows": len(requests),
        "rejected_rows": len(requests) - len(accepted_ids),
        "source": "danish-foundation-models/synthetic-values-model-charter",
        "sampling_repeat": 10,
        "sft_output": str(source_path),
        "preference_output": str(args.preference_output),
    }
    atomic_json(args.output / "manifest.json", manifest)
    atomic_json(args.package / "metadata/manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source", type=Path, default=SOURCE)
    result.add_argument("--work", type=Path, default=WORK)
    sub = result.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--shards", type=int, default=8)
    p.set_defaults(func=prepare)
    for name, function in (("translate", translate), ("audit", audit)):
        p = sub.add_parser(name)
        p.add_argument("--input", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--base-url", required=True)
        p.add_argument("--model", required=True)
        p.add_argument("--concurrency", type=int, default=64)
        p.add_argument("--max-tokens", type=int, default=4096 if name == "translate" else 768)
        p.add_argument("--timeout", type=float, default=900)
        p.add_argument("--retries", type=int, default=3)
        if name == "translate":
            p.add_argument("--audit-output", type=Path, required=True)
        else:
            p.add_argument("--requests", type=Path, required=True)
            p.add_argument("--min-score", type=int, default=4)
        p.set_defaults(func=function)
    p = sub.add_parser("build")
    p.add_argument("--output", type=Path, default=OUTPUT)
    p.add_argument("--preference-output", type=Path, default=PREFERENCE)
    p.add_argument("--package", type=Path, default=PACKAGE)
    p.add_argument("--min-accepted", type=int, default=1200)
    p.set_defaults(func=build)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
