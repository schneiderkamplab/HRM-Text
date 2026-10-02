"""Bounded review execution, deliberately separate from approved audit queues."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time
import urllib.request

from .io import digest, file_hash, write_json
from .jobs import Queue, audit_payload, run_clients
from .norwegian_inclusive import authorized_language

MODEL = "google/gemma-4-26B-A4B-it"
TOKENIZER_DIR = Path("/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52")
LANGUAGES = ("en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl")
NORWEGIAN = """ For explicitly unknown-standard Norwegian or mixed Bokmal/Nynorsk
records, do not infer that all text must be Bokmal. Do not reject merely because
the standard is unknown or mixed. Evaluate the actual task: punctuation repairs
must preserve words and meaning; dialogue pairs must preserve speaker labels and
each speaker's wording/standard. Reject unjustified normalization or translation.
This exception does not excuse violating an explicitly requested standard."""


def select(records, per_language=20):
    if not 1 <= per_language <= 20:
        raise ValueError("Pilot limit is 1..20 per language")
    selected, used = [], set()
    for language in LANGUAGES:
        eligible = [(i, row) for i, row in enumerate(records)
                    if language in (row.get("language"), row.get("reverse_language"))]
        # Alternate task/component strata rather than taking a file prefix.
        groups = {}
        for i, row in eligible:
            key = (row.get("task", ""), row.get("component", ""))
            groups.setdefault(key, []).append((i, row))
        count = 0
        while count < per_language:
            progress = False
            for group in groups.values():
                while group and group[0][0] in used:
                    group.pop(0)
                if group and count < per_language:
                    i, row = group.pop(0)
                    used.add(i)
                    selected.append((language, row))
                    count += 1
                    progress = True
            if not progress:
                raise ValueError(f"Insufficient distinct pilot records for {language}")
    return selected


def payload(language, record):
    result = audit_payload(record, MODEL)
    result["request"]["max_tokens"] = 512
    result["pilot_language"] = language
    result["request"]["messages"][0]["content"] += NORWEGIAN
    properties = {"keep": {"type": "boolean"}, "reason": {"type": "string"}}
    properties.update({k: {"type": "integer", "minimum": 1, "maximum": 5}
                       for k in ("language_quality", "coherence", "usefulness")})
    result["request"]["response_format"] = {"type": "json_schema", "json_schema": {
        "name": "audit", "strict": True, "schema": {"type": "object",
        "properties": properties, "required": list(properties), "additionalProperties": False}}}
    return result


def norwegian_supplement(records):
    selected = []
    for standard in ("unknown", "mixed"):
        eligible = [r for r in records if r.get("norwegian_standard") == standard
                    and authorized_language(r)]
        if len(eligible) < 20:
            raise ValueError(f"Insufficient authorized Norwegian {standard} records")
        selected.extend(("no-" + standard, r) for r in eligible[:20])
    return selected


def reordering_supplement(records):
    selected = []
    for language in ("nb", "nn", "nl", "sv"):
        for task in ("paragraph-reordering", "text-block-reordering"):
            component = f"reordering-integrated-{language}-{task}"
            eligible = [r for r in records if r.get("component") == component
                        and r.get("language") == language and r.get("task") == task]
            if len(eligible) < 10:
                raise ValueError("Insufficient eligible reordering review: " + component)
            selected.extend((language, r) for r in eligible[:10])
    return selected


def context_eligible(records, tokenizer_dir=TOKENIZER_DIR):
    import jinja2
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(tokenizer_dir / "tokenizer.json"))
    environment = jinja2.Environment()
    def fail(message):
        raise ValueError(message)
    environment.globals["raise_exception"] = fail
    template = environment.from_string((tokenizer_dir / "chat_template.jinja").read_text())
    kept, lengths = [], []
    for record in records:
        request = payload(record["language"], record)["request"]
        rendered = template.render(messages=request["messages"], add_generation_prompt=True,
                                   enable_thinking=False, bos_token="<bos>", eos_token="<eos>")
        count = len(tokenizer.encode(rendered, add_special_tokens=False).ids)
        fits = count + request["max_tokens"] <= 8192
        lengths.append({"id": record["id"], "prompt_tokens": count, "fits": fits})
        if fits:
            kept.append(record)
    return kept, {"records": lengths, "output_reserve": 512, "max_model_len": 8192,
                  "tokenizer_sha256": file_hash(tokenizer_dir / "tokenizer.json"),
                  "template_sha256": file_hash(tokenizer_dir / "chat_template.jinja")}


def heartbeat(path, phase, **details):
    write_json(path, {"pid": os.getpid(), "checked_at": time.time(),
                      "phase": phase, **details})


def wait_for_endpoints(endpoints, heartbeat_path, timeout=0, interval=30):
    """Readiness failures never claim jobs; zero timeout means wait indefinitely."""
    started = time.monotonic()
    while True:
        pending = {}
        for endpoint in endpoints:
            try:
                with urllib.request.urlopen(endpoint + "/models", timeout=3) as response:
                    models = json.load(response)
                if MODEL not in {m["id"] for m in models["data"]}:
                    raise ValueError("Unexpected served model")
            except Exception as exc:
                pending[endpoint] = type(exc).__name__
        heartbeat(heartbeat_path, "waiting_for_endpoints" if pending else "ready",
                  pending=pending, elapsed_seconds=time.monotonic() - started,
                  timeout_seconds=timeout)
        if not pending:
            print("READY " + ", ".join(endpoints), flush=True)
            return
        print("WAIT " + json.dumps(pending), flush=True)
        if timeout and time.monotonic() - started >= timeout:
            raise TimeoutError("Configured endpoint readiness timeout reached; jobs remain unclaimed")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoints", nargs="+", required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--norwegian-supplement", action="store_true")
    modes.add_argument("--reordering-supplement", action="store_true")
    parser.add_argument("--after", type=Path, help="Wait for another bounded pilot's summary")
    parser.add_argument("--readiness-timeout", type=float, default=0,
                        help="Seconds; default 0 waits indefinitely without consuming attempts")
    args = parser.parse_args()
    if args.readiness_timeout < 0:
        parser.error("readiness timeout must be nonnegative")
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.snapshot / "review_only/audit_records.jsonl"
    records = [json.loads(line)["record"] for line in source.open()]
    manifest = json.loads((args.snapshot / "manifest.json").read_text())
    if manifest["model"] != MODEL or file_hash(source) != manifest["review_records_sha256"]:
        raise ValueError("Review checksum or model mismatch")
    if args.reordering_supplement:
        eligible, report = context_eligible([r for r in records if r.get("component", "").startswith("reordering-integrated-")])
        chosen = reordering_supplement(eligible)
        report["selected_ids"] = [r["id"] for _, r in chosen]
        write_json(args.output / "context-preflight.json", report)
    else:
        chosen = norwegian_supplement(records) if args.norwegian_supplement else select(records)
    receipt = {"mode": "pilot-only-not-approved", "model": MODEL,
               "snapshot": str(args.snapshot.resolve()), "review_sha256": file_hash(source),
               "counts": dict(Counter(lang for lang, _ in chosen)),
               "endpoints": args.endpoints, "concurrency_per_endpoint": 32}
    receipt_path = args.output / "execution.json"
    if receipt_path.exists() and json.loads(receipt_path.read_text()) != receipt:
        raise ValueError("Existing run differs; use a new isolated output")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    queue = Queue(args.output / "jobs.sqlite")
    planned = [payload(lang, record) for lang, record in chosen]
    existing = {key for key, in queue.db.execute("SELECT id FROM jobs")}
    expected = {digest(["pilot-audit", p]) for p in planned}
    if existing and existing != expected:
        raise ValueError("Existing pilot selection differs; never expand a running pilot")
    for item in planned:
        queue.add("pilot-audit", item)
    print(json.dumps(receipt), flush=True)
    if args.after:
        print("WAIT for prior pilot summary " + str(args.after), flush=True)
        while not args.after.exists():
            heartbeat(args.output / "heartbeat.json", "waiting_for_prior_pilot", after=str(args.after))
            time.sleep(30)
    wait_for_endpoints(args.endpoints, args.output / "heartbeat.json", args.readiness_timeout)
    print("RUNNING bounded pilot", flush=True)
    heartbeat(args.output / "heartbeat.json", "running")
    run_clients(args.output / "jobs.sqlite", "pilot-audit", args.endpoints, 32)
    completed = list(queue.completed("pilot-audit"))
    summary = {"status": queue.status(), "completed_by_language": dict(Counter(
        p["pilot_language"] for _, p, _ in completed)),
        "decisions": dict(Counter("keep" if r["keep"] else "reject" for _, _, r in completed)),
        "human_approved": False, "accepted_training_exports": 0}
    write_json(args.output / "summary.json", summary)
    heartbeat(args.output / "heartbeat.json", "finished", status=summary["status"])
    print(json.dumps(summary), flush=True)
    queue.close()


if __name__ == "__main__":
    main()
