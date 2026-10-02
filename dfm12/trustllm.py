"""Answer native TrustLLM prompts; explicitly mark synthetic language adaptations.

Released prompts have no answer field or stable OpenAssistant message IDs.
Never borrow an English answer for a culturally changed reformulation.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from .catalog import selected_source
from .io import digest, rows, write_json
from .jobs import Queue, audit_payload, run_clients
from .records import validate_messages

LABELS = {"Danish": "da", "Dutch": "nl", "German": "de", "Swedish": "sv",
          "Icelandic": "is", "Faroese": "fo", "Norwegian (Bokmål)": "nb",
          "Norwegian (Nynorsk)": "nn", "Norwegian Bokmål": "nb", "Norwegian Nynorsk": "nn"}


def enqueue(root, cfg, adaptation_target=1000):
    source = selected_source(root, "trustllm-prompts")
    native = []
    for relative in source["files"]:
        for ordinal, row in enumerate(rows(root / "downloads" / "trustllm-prompts" / relative)):
            lang = LABELS.get(row.get("language"))
            prompt = row.get("original_text")
            if lang is None or not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"Unknown TrustLLM schema/language at {relative}:{ordinal}")
            provenance = dict(repo=source["repo"], revision=source["revision"], file=relative,
                              ordinal=ordinal, source_id=row["id"])
            native.append(dict(prompt=prompt, language=lang, provenance=provenance))
    jobs = [(row, row["language"], False) for row in native]
    existing = {row["language"] for row in native}
    # Stable seeds sampled across all released languages, not only the first file/language.
    seeds = sorted(native, key=lambda r: digest([cfg["seed"], r]))[:adaptation_target]
    jobs.extend((row, lang, True) for lang in cfg["languages"] if lang not in existing for row in seeds)
    queue = Queue(root / "trustllm.sqlite")
    counts = Counter()
    try:
        for row, lang, adapted in jobs:
            record = dict(id=digest([row, lang, adapted]), language=lang, task="instruction",
                          component="trustllm-" + lang, provenance=row["provenance"],
                          audit_context=dict(seed_prompt=row["prompt"], seed_language=row["language"],
                              target_language=cfg["languages"][lang], synthetic_prompt=adapted,
                              instruction="Check factual accuracy, answerability, cultural appropriateness, and preservation of the seed's task. Reject unsupported facts or missing source context."))
            instruction = ("Adapt this prompt naturally into " + cfg["languages"][lang] +
                           ", preserving its instructional intent. Then answer it in that language. " if adapted else
                           "Keep the user prompt EXACTLY unchanged and answer it in " + cfg["languages"][lang] + ". ")
            request = dict(model=cfg["model"], temperature=0.4, max_tokens=4096,
                           chat_template_kwargs={"enable_thinking": False},
                           messages=[dict(role="system", content=
                               "Produce a training conversation, not model identity claims. Return JSON with messages: exactly one user and one assistant message, each role/content. Do not invent facts or missing documents. If essential context is missing, ask a concise clarification instead of fabricating an answer. " + instruction),
                               dict(role="user", content=row["prompt"])])
            queue.add("generate", dict(record=record, request=request))
            counts[lang] += 1
    finally:
        queue.close()
    write_json(root / "trustllm-seeds.json", dict(counts=dict(counts), native_counts=dict(Counter(r["language"] for r in native)),
        adaptation_target=adaptation_target, published_answers="Not found in released schema/paper-linked repository",
        status="generation pending; independent audit required"))
    return dict(counts)


def validate_generation(record, result):
    messages = result.get("messages")
    validate_messages(messages)
    if len(messages) != 2 or messages[0]["role"] != "user":
        raise ValueError("Expected exactly one prompt/answer pair")
    context = record["audit_context"]
    if not context["synthetic_prompt"] and messages[0]["content"] != context["seed_prompt"]:
        raise ValueError("Native prompt changed")
    return messages


def transfer_to_audit(root, renderer, model):
    queue = Queue(root / "trustllm.sqlite")
    audits = Queue(root / "jobs.sqlite")
    counts = Counter()
    try:
        for key, payload, result in queue.completed("generate"):
            record = dict(payload["record"])
            try:
                record["messages"] = validate_generation(record, result)
                record["rendered_tokens"] = renderer.count(record["messages"])
            except ValueError as exc:
                counts[str(exc)] += 1
                write_json(root / "trustllm-rejected" / (key + ".json"), dict(reason=str(exc), record=record, result=result))
                continue
            audits.add("audit", audit_payload(record, model))
            counts["audit_queued"] += 1
    finally:
        queue.close()
        audits.close()
    write_json(root / "trustllm-transfer.json", dict(counts))
    return counts


def main():
    from .european_expansion import ROOT
    from .io import load
    from .prepare import Renderer
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["generate", "audit", "transfer"])
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--endpoint", action="append", default=[])
    p.add_argument("--concurrency", type=int, default=64)
    args = p.parse_args()
    if args.stage == "transfer":
        cfg = load(args.root / "config.json")
        renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
        print(transfer_to_audit(args.root, renderer, cfg["model"]))
    else:
        path = args.root / ("trustllm.sqlite" if args.stage == "generate" else "jobs.sqlite")
        run_clients(path, args.stage, args.endpoint, args.concurrency)


if __name__ == "__main__":
    main()
