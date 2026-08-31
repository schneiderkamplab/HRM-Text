#!/usr/bin/env python3
"""Prepare, generate, audit, and build DFM10 persona and legal chats."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import jinja2
import pyarrow.parquet as pq
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dfm10_tidsskrift_grounded_model import (
    DEFAULT_TEMPLATE,
    DEFAULT_TOKENIZER,
    extract_json,
    has_long_copy,
    iter_jsonl,
    latest_rows,
    request_completion,
    run_parallel,
)

DEFAULT_PERSONAS = ROOT / "data/downloads/datasets/dfm10_danish_personas_seed/data/train-00000-of-00001.parquet"
DEFAULT_DOMS = ROOT / "data/downloads/datasets/dfm10_domsdatabasen/data/train-00000-of-00001.parquet"
DEFAULT_WORK = ROOT / "data/dfm10_persona_doms_chats"
DEFAULT_PERSONA_OUTPUT = ROOT / "data/dfm10_danish_persona_chats_source/danish_persona_chats__accepted.jsonl"
DEFAULT_DOMS_OUTPUT = ROOT / "data/dfm10_domsdatabasen_grounded_chats_source/domsdatabasen_grounded_chats__accepted.jsonl"

PERSONA_FOCUSES = (
    "praktisk hjælp i hverdagen med opfølgende præciseringer",
    "instruktionsfølgning med form-, længde- eller stilkrav",
    "videnssøgning, forklaring og kritiske opfølgende spørgsmål",
    "afklaring, revision og forbedring af et tidligere svar",
    "planlægning eller formulering af en tekst til en realistisk situation",
)
PERSONA_ACCEPTED_QUOTAS = {3: 2_000, 4: 4_000, 5: 8_000, 6: 4_000, 7: 1_850}
# Keep the completed 25,000-request campaign stable. The final seven-turn
# acceptance floor was explicitly revised after independent audit.
PERSONA_CANDIDATE_QUOTAS = {3: 2_500, 4: 5_000, 5: 10_000, 6: 5_000, 7: 2_500}
LEGAL_FOCUSES = (
    "kort neutral sagsoversigt og gradvis uddybning",
    "adskil parternes påstande fra rettens faktiske og retlige vurdering",
    "procesforløb, afgørelsesspørgsmål, begrundelse og resultat",
    "tidslinje, evidenshenvisning og kontrol af en mulig fejlslutning",
)


def stable_hex(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def atomic_shards(rows: list[dict[str, Any]], output: Path, shards: int) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(shards)]
    for row in rows:
        buckets[int(row["request_id"][:16], 16) % shards].append(row)
    for index, bucket in enumerate(buckets):
        destination = output / f"part-{index:05d}-of-{shards:05d}.jsonl"
        temporary = destination.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in sorted(bucket, key=lambda value: value["request_id"]):
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        temporary.replace(destination)
    return {
        "rows": len(rows),
        "shards": shards,
        "minimum_shard_rows": min(map(len, buckets)),
        "maximum_shard_rows": max(map(len, buckets)),
    }


def persona_requests(path: Path) -> list[dict[str, Any]]:
    rows = pq.read_table(path).to_pylist()
    requests: list[dict[str, Any]] = []
    for row in rows:
        seed_id = str(row["uuid"])
        seed = {
            "age": row.get("age"),
            "gender": row.get("sex"),
            "occupation": row.get("occupation"),
            "education_level": row.get("education_level"),
            "interests": row.get("hobbies_and_interests"),
            "persona_description": row.get("persona"),
        }
        for focus_index, focus in enumerate(PERSONA_FOCUSES):
            request_id = stable_hex("dfm10-persona-chats-v1", seed_id, str(focus_index))
            requests.append(
                {
                    "request_id": request_id,
                    "campaign": "persona",
                    "source": "oliverkinch/danish-personas",
                    "source_id": seed_id,
                    "language": "da",
                    "focus": focus,
                    "persona_seed": seed,
                }
            )
    # Assign candidate proportions with audit headroom. The build retains every
    # accepted row, while these quotas remain minimum coverage gates by length.
    ordered = sorted(requests, key=lambda row: stable_hex("turn-quota", row["request_id"]))
    candidate_quotas = PERSONA_CANDIDATE_QUOTAS
    offset = 0
    for turns, count in candidate_quotas.items():
        for row in ordered[offset : offset + count]:
            row["target_turns"] = turns
        offset += count
    if offset != len(ordered) or any("target_turns" not in row for row in ordered):
        raise ValueError("persona candidate turn quotas do not cover all requests")
    return requests


def normalized_paragraphs(text: str) -> list[str]:
    text = text.replace("\u00ad", "")
    paragraphs = []
    for block in re.split(r"\n\s*\n+", text):
        value = re.sub(r"\s+", " ", block).strip()
        if len(value) >= 40 and not value.isdigit():
            paragraphs.append(value)
    return paragraphs


def evidence_excerpt(text: str, variant: int, max_chars: int = 7_000) -> str:
    paragraphs = normalized_paragraphs(text)
    if not paragraphs:
        return ""
    headings = re.compile(
        r"(?:sagens baggrund|parternes påstande|forklaringer|rettens begrundelse|"
        r"begrundelse og resultat|thi kendes for ret|afgørelse)",
        re.I,
    )
    important = [index for index, paragraph in enumerate(paragraphs) if headings.search(paragraph)]
    if variant == 0:
        indices = list(range(min(4, len(paragraphs))))
        for index in important:
            indices.extend(range(index, min(index + 4, len(paragraphs))))
        indices.extend(range(max(0, len(paragraphs) - 5), len(paragraphs)))
    else:
        pivot = important[-1] if important else max(0, len(paragraphs) * 2 // 3)
        indices = list(range(max(0, pivot - 3), min(len(paragraphs), pivot + 8)))
    selected: list[str] = []
    used = 0
    for index in dict.fromkeys(indices):
        paragraph = paragraphs[index]
        if used + len(paragraph) + 2 > max_chars:
            continue
        selected.append(paragraph)
        used += len(paragraph) + 2
    return "\n\n".join(selected)


def doms_requests(path: Path, target: int = 4_500) -> list[dict[str, Any]]:
    columns = [
        "case_id",
        "Overskrift",
        "Afgørelsesstatus",
        "Faggruppe",
        "Ret",
        "Sagstype",
        "Instans",
        "Sagsemner",
        "text_anonymized",
    ]
    rows = pq.read_table(path, columns=columns).to_pylist()
    requests: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text_anonymized") or "").strip()
        if not text:
            continue
        case_id = str(row["case_id"])
        variants = 2 if len(text) > 14_000 else 1
        for variant in range(variants):
            excerpt = evidence_excerpt(text, variant)
            if len(excerpt) < 500:
                continue
            request_id = stable_hex("dfm10-doms-grounded-v1", case_id, str(variant))
            requests.append(
                {
                    "request_id": request_id,
                    "campaign": "doms",
                    "source": "alexandrainst/domsdatabasen",
                    "source_id": case_id,
                    "language": "da",
                    "focus": LEGAL_FOCUSES[int(request_id[:8], 16) % len(LEGAL_FOCUSES)],
                    "target_turns": 4 + (int(request_id[8:16], 16) % 2),
                    "source_text": excerpt,
                    "chunk_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                    "case_metadata": {
                        "heading": row.get("Overskrift"),
                        "decision_status": row.get("Afgørelsesstatus"),
                        "case_family": row.get("Faggruppe"),
                        "court": row.get("Ret"),
                        "case_type": row.get("Sagstype"),
                        "instance": row.get("Instans"),
                        "subjects": row.get("Sagsemner"),
                    },
                    "variant": variant,
                }
            )
    if len(requests) < target:
        raise ValueError(f"only {len(requests)} legal candidates; require {target}")
    return sorted(requests, key=lambda row: stable_hex("legal-selection", row["request_id"]))[:target]


def cmd_prepare(args: argparse.Namespace) -> None:
    persona = persona_requests(args.personas)
    doms = doms_requests(args.doms, args.doms_candidates)
    summary = {
        "version": "dfm10-persona-doms-chats-v1",
        "persona": atomic_shards(persona, args.work / "persona/requests/shards", args.persona_shards),
        "doms": atomic_shards(doms, args.work / "doms/requests/shards", args.doms_shards),
        "persona_minimum_accepted_by_turns": PERSONA_ACCEPTED_QUOTAS,
        "doms_minimum_accepted": args.doms_minimum,
    }
    args.work.mkdir(parents=True, exist_ok=True)
    (args.work / "requests.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    turns = int(request["target_turns"])
    if request["campaign"] == "persona":
        system = (
            "Skab en naturlig dansk samtale mellem en bruger og en hjælpsom, præcis assistent. "
            "Personaprofilen er kun en inspirationskilde til realistiske behov og interesser: "
            "assistenten må ikke udgive sig for at være personen, og samtalen må ikke afsløre navn, "
            "adresse, postnummer eller opfinde følsomme personoplysninger. Følg fokus og lav præcis "
            f"{turns} bruger/assistent-udvekslinger. Senere spørgsmål skal følge naturligt af tidligere "
            "svar. Varier svarlængde efter behov og overhold alle konkrete brugerkrav. Returnér kun JSON."
        )
        payload = {
            "persona_seed": request["persona_seed"],
            "conversation_focus": request["focus"],
            "required_turns": turns,
            "json_shape": {"turns": [{"user": "spørgsmål", "assistant": "svar"}]},
        }
    else:
        system = (
            "Skab en naturlig dansk, dokumentbaseret samtale om en pseudonymiseret retsafgørelse. "
            "Brug kun det leverede uddrag. Skeln konsekvent mellem parternes påstande, forklaringer, "
            "rettens vurdering og resultat. Sig tydeligt når uddraget ikke giver grundlag for et svar. "
            "Bevar anonymisering, giv ikke personlig juridisk rådgivning, forudsig ikke andre sager, og "
            "opfind ingen fakta. Lav præcis " + str(turns) + " naturligt sammenhængende udvekslinger. "
            "Angiv for hvert svar en kort støttepassage fra uddraget. Returnér kun JSON."
        )
        payload = {
            "case_metadata": request["case_metadata"],
            "conversation_focus": request["focus"],
            "required_turns": turns,
            "judgment_excerpt": request["source_text"],
            "json_shape": {
                "turns": [
                    {"user": "spørgsmål", "assistant": "kildebaseret svar", "support": "kort støttepassage"}
                ]
            },
        }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def render_generated(value: dict[str, Any], request: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    turns = value.get("turns")
    expected = int(request["target_turns"])
    if not isinstance(turns, list) or len(turns) != expected:
        raise ValueError(f"expected exactly {expected} turns")
    messages: list[dict[str, str]] = []
    support: list[str] = []
    if request["campaign"] == "doms":
        messages.append(
            {
                "role": "system",
                "content": "Besvar spørgsmål ud fra dette pseudonymiserede uddrag:\n\n" + request["source_text"],
            }
        )
    seen: set[str] = set()
    for turn in turns:
        if not isinstance(turn, dict):
            raise ValueError("turn is not an object")
        user = str(turn.get("user") or "").strip()
        assistant = str(turn.get("assistant") or "").strip()
        normalized = re.sub(r"\W+", " ", user.casefold()).strip()
        if not 8 <= len(user) <= 600 or not 10 <= len(assistant) <= 4_000:
            raise ValueError("invalid user or assistant length")
        if not normalized or normalized in seen:
            raise ValueError("duplicate user question")
        if request["campaign"] == "doms":
            evidence = str(turn.get("support") or "").strip()
            if len(evidence) < 12:
                raise ValueError("missing legal support")
            if has_long_copy(assistant, request["source_text"]):
                raise ValueError("assistant copies an overly long source span")
            support.append(evidence)
        messages.extend(({"role": "user", "content": user}, {"role": "assistant", "content": assistant}))
        seen.add(normalized)
    return messages, support


def rendered_tokens(messages: list[dict[str, str]], tokenizer: Tokenizer, template: jinja2.Template) -> int:
    rendered = template.render(
        messages=messages,
        add_generation_prompt=False,
        enable_thinking=False,
        bos_token="<bos>",
        eos_token="<eos>",
    )
    return len(tokenizer.encode(rendered, add_special_tokens=False).ids)


def cmd_generate(args: argparse.Namespace) -> None:
    complete = latest_rows(args.output, "generation_ok")
    pending = [row for row in iter_jsonl(args.input) if row["request_id"] not in complete]
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    print(f"generation pending={len(pending)}", flush=True)

    def one(request: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = request_completion(
                base_url=args.base_url,
                model=args.model,
                messages=generation_messages(request),
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            messages, support = render_generated(extract_json(raw), request)
            count = rendered_tokens(messages, tokenizer, template)
            if count > args.max_training_tokens:
                raise ValueError(f"rendered chat has {count} tokens")
            return {
                "request_id": request["request_id"],
                "generation_ok": True,
                "campaign": request["campaign"],
                "messages": messages,
                "support": support,
                "exchange_count": int(request["target_turns"]),
                "training_tokens": count,
                "teacher_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "generation_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    if request["campaign"] == "persona":
        system = (
            "Du er en streng kvalitetskontrollør af dansk assistentdialog. Vurder naturlighed, "
            "instruktionsfølgning, korrekthed, relevans for den syntetiske brugerprofil og privatliv. "
            "Afvis persona-efterligning, afsløring eller opfindelse af følsomme oplysninger, mekaniske "
            "spørgelister, gentagelser og svage svar. Returnér kun JSON."
        )
        context = {"persona_seed": request["persona_seed"], "focus": request["focus"]}
        score_keys = ["naturalness", "instruction_following", "response_quality", "persona_relevance", "privacy_safety"]
    else:
        system = (
            "Du er en streng kvalitetskontrollør af dansk dokumentbaseret juridisk dialog. Kontroller "
            "hvert svar mod det pseudonymiserede uddrag. Afvis sammenblanding af påstande og rettens "
            "konklusion, ikke-underbyggede oplysninger, juridisk rådgivning, identitetslæk, dårlig dansk "
            "eller unaturlig dialog. Returnér kun JSON."
        )
        context = {"judgment_excerpt": request["source_text"], "case_metadata": request["case_metadata"]}
        score_keys = ["source_support", "role_distinction", "legal_accuracy", "naturalness", "privacy_safety"]
    schema = {
        "keep": True,
        **{key: 5 for key in score_keys},
        "assistant_turns": [{"turn_index": 0, "acceptable": True, "complaint": ""}],
        "primary_failure": "none",
        "complaint": "",
    }
    payload = {
        **context,
        "conversation": generated["messages"],
        "hidden_support": generated.get("support"),
        "required_json_shape": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_audit(value: dict[str, Any], generated: dict[str, Any], minimum_score: int) -> dict[str, Any]:
    score_keys = (
        ("naturalness", "instruction_following", "response_quality", "persona_relevance", "privacy_safety")
        if generated["campaign"] == "persona"
        else ("source_support", "role_distinction", "legal_accuracy", "naturalness", "privacy_safety")
    )
    scores = [value.get(key) for key in score_keys]
    turns = value.get("assistant_turns")
    expected = set(range(int(generated["exchange_count"])))
    covered = {
        row.get("turn_index")
        for row in turns or []
        if isinstance(row, dict) and row.get("acceptable") is True
    }
    keep = (
        value.get("keep") is True
        and covered == expected
        and all(isinstance(score, int) and minimum_score <= score <= 5 for score in scores)
        and str(value.get("primary_failure") or "").strip().casefold() in {"", "none", "null"}
    )
    return {**value, "keep": keep}


def cmd_audit(args: argparse.Namespace) -> None:
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generated = latest_rows(args.input, "generation_ok")
    complete = latest_rows(args.output, "audit_ok")
    pending = [(requests[key], row) for key, row in generated.items() if key in requests and key not in complete]
    print(f"audit pending={len(pending)}", flush=True)

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        raw = ""
        try:
            raw = request_completion(
                base_url=args.base_url,
                model=args.model,
                messages=audit_messages(request, generated_row),
                temperature=0.0,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            decision = validate_audit(extract_json(raw), generated_row, args.minimum_score)
            return {
                "request_id": request["request_id"],
                "audit_ok": True,
                "keep": decision["keep"],
                "decision": decision,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "audit_ok": False,
                "keep": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "audited")


def cmd_verify(args: argparse.Namespace) -> None:
    requested = {row["request_id"] for row in iter_jsonl(args.requests)}
    generated = set(latest_rows(args.generated, "generation_ok"))
    audited = set(latest_rows(args.audited, "audit_ok"))
    fraction = len(requested & generated & audited) / len(requested) if requested else 1.0
    print(json.dumps({"requested": len(requested), "generated": len(requested & generated), "audited": len(requested & audited), "completion_fraction": fraction}))
    if fraction < args.minimum_completion_fraction:
        raise SystemExit(1)


def all_accepted(work: Path, campaign: str, shards: int) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for index in range(shards):
        name = f"part-{index:05d}-of-{shards:05d}.jsonl"
        requests = {row["request_id"]: row for row in iter_jsonl(work / campaign / "requests/shards" / name)}
        generated = latest_rows(work / campaign / "generated" / name, "generation_ok")
        audited = latest_rows(work / campaign / "audits" / name, "audit_ok")
        for request_id, audit in audited.items():
            if audit.get("keep") is True and request_id in requests and request_id in generated:
                accepted.append({"request": requests[request_id], "generated": generated[request_id], "audit": audit})
    return accepted


def atomic_jsonl(rows: Iterable[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(output)


def cmd_build(args: argparse.Namespace) -> None:
    accepted = all_accepted(args.work, args.campaign, args.shards)
    if args.campaign == "persona":
        counts: Counter[int] = Counter()
        for item in accepted:
            counts[int(item["generated"]["exchange_count"])] += 1
        for turns, quota in PERSONA_ACCEPTED_QUOTAS.items():
            if counts[turns] < quota:
                raise SystemExit(f"only {counts[turns]} accepted {turns}-turn persona chats; require {quota}")
        output = args.persona_output
    else:
        if len(accepted) < args.doms_minimum:
            raise SystemExit(f"only {len(accepted)} accepted legal chats; require {args.doms_minimum}")
        output = args.doms_output
    selected = sorted(accepted, key=lambda item: stable_hex("accepted", item["request"]["request_id"]))
    rows = []
    turns = 0
    tokens = 0
    for item in selected:
        request, generated, audit = item["request"], item["generated"], item["audit"]
        turns += int(generated["exchange_count"])
        tokens += int(generated["training_tokens"])
        rows.append(
            {
                "messages": generated["messages"],
                "source": request["source"],
                "source_id": request["source_id"],
                "row_id": f"{args.campaign}:{request['request_id']}",
                "language": "da",
                "task": "persona_seeded_chat" if args.campaign == "persona" else "grounded_legal_chat",
                "exchange_count": generated["exchange_count"],
                "training_tokens": generated["training_tokens"],
                "teacher_model": generated["teacher_model"],
                "judge_model": audit["judge_model"],
                "quality_audit": audit["decision"],
                "provenance": {
                    "focus": request["focus"],
                    "chunk_sha256": request.get("chunk_sha256"),
                    "case_metadata": request.get("case_metadata"),
                    "variant": request.get("variant"),
                },
            }
        )
    atomic_jsonl(rows, output)
    summary = {
        "campaign": args.campaign,
        "rows": len(rows),
        "assistant_turns": turns,
        "rendered_training_tokens": tokens,
        "accepted_rows_retained": "all",
        "rows_by_exchange_count": dict(sorted(Counter(row["exchange_count"] for row in rows).items())),
        "output": str(output),
    }
    output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def add_api(command: argparse.ArgumentParser) -> None:
    command.add_argument("--base-url", required=True)
    command.add_argument("--model", required=True)
    command.add_argument("--concurrency", type=int, default=64)
    command.add_argument("--max-tokens", type=int, default=4096)
    command.add_argument("--timeout", type=float, default=600)
    command.add_argument("--retries", type=int, default=3)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--personas", type=Path, default=DEFAULT_PERSONAS)
    prepare.add_argument("--doms", type=Path, default=DEFAULT_DOMS)
    prepare.add_argument("--work", type=Path, default=DEFAULT_WORK)
    prepare.add_argument("--persona-shards", type=int, default=64)
    prepare.add_argument("--doms-shards", type=int, default=32)
    prepare.add_argument("--doms-candidates", type=int, default=4_500)
    prepare.add_argument("--doms-minimum", type=int, default=3_000)
    prepare.set_defaults(func=cmd_prepare)
    generate = commands.add_parser("generate")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--temperature", type=float, default=0.7)
    generate.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    generate.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    generate.add_argument("--max-training-tokens", type=int, default=4096)
    add_api(generate)
    generate.set_defaults(func=cmd_generate)
    audit = commands.add_parser("audit")
    audit.add_argument("--requests", type=Path, required=True)
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--minimum-score", type=int, default=4)
    add_api(audit)
    audit.set_defaults(func=cmd_audit)
    verify = commands.add_parser("verify-shard")
    verify.add_argument("--requests", type=Path, required=True)
    verify.add_argument("--generated", type=Path, required=True)
    verify.add_argument("--audited", type=Path, required=True)
    verify.add_argument("--minimum-completion-fraction", type=float, default=0.98)
    verify.set_defaults(func=cmd_verify)
    build = commands.add_parser("build")
    build.add_argument("--work", type=Path, default=DEFAULT_WORK)
    build.add_argument("--campaign", choices=("persona", "doms"), required=True)
    build.add_argument("--shards", type=int, required=True)
    build.add_argument("--persona-output", type=Path, default=DEFAULT_PERSONA_OUTPUT)
    build.add_argument("--doms-output", type=Path, default=DEFAULT_DOMS_OUTPUT)
    build.add_argument("--doms-minimum", type=int, default=3_000)
    build.set_defaults(func=cmd_build)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
