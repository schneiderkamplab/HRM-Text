"""Correction-led identity v4, with an exact inherited-turn ledger and CPU receipts."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile

import yaml

from . import identity_extension as base
from . import identity_expansion as helpers
from . import identity_repair_expansion as previous_builder
from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint, validate_messages

ROOT = base.ROOT
SPEC = ROOT / "dfm12/identity_correction.yaml"
REVIEW = ROOT / "data/dfm12/identity-v4-readonly-review-20260926-v1"
PREVIOUS = ROOT / "data/dfm12/identity-repair-da-en-20260926-v3"
PREVIOUS_SHA = "af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1"
ASSESSMENT = ROOT / "data/dfm12/identity-evaluation-third1000-20260926/reviewer-assessment.md"
SCHEMA = "dfm12-curated-identity-correction-v4"


def read_spec(path=SPEC):
    spec = yaml.safe_load(Path(path).read_text())
    if (spec["version"] != 4 or spec["profile"] != "xl-full-bp"
            or spec["facts_sha256"] != base.FACTS_SHA or file_hash(base.FACTS) != base.FACTS_SHA):
        raise ValueError("facts/profile/version mismatch")
    if file_hash(REVIEW / "candidate-ledger.jsonl") != spec["review_ledger_sha256"]:
        raise ValueError("review ledger drift")
    candidates = {r["key"]: r for r in rows(REVIEW / "candidate-ledger.jsonl")}
    for group in spec["review_resolutions"]:
        if set(group) != {"keys", "replacement"} or set(group["replacement"]) != {
                candidates[k]["language"] for k in group["keys"]}:
            raise ValueError("invalid review resolution/language map")
        for key in group["keys"]:
            candidate = candidates[key]
            replacement = group["replacement"][candidate["language"]]
            spec["corrections"].append({"id": candidate["record_id"], "index": candidate["message_index_0based"],
                                        "expect": candidate["assistant_text"], "replacement": replacement,
                                        "category": candidate["disposition"]})
    seen = set()
    for edit in spec["corrections"]:
        if set(edit) != {"id", "index", "category", "expect", "replacement"}:
            raise ValueError("invalid correction fields")
        key = edit["id"], edit["index"]
        if key in seen or not isinstance(key[1], int) or key[1] < 0:
            raise ValueError("duplicate/invalid correction")
        seen.add(key)
        if not all(isinstance(edit[k], str) and edit[k].strip() for k in ("expect", "replacement", "category")):
            raise ValueError("empty correction")
    required = {(r["record_id"], r["message_index_0based"]) for r in candidates.values()
                if r["disposition"] in {"confirmed_contradiction", "unsupported_roster_addition"}}
    if not required <= seen:
        raise ValueError("unresolved confirmed factual defect")
    return spec


def correct(records, spec, provenance=None):
    """Only explicitly enumerated turns may change; the input artifact is sealed."""
    edits = defaultdict(list)
    for edit in spec["corrections"]:
        edits[edit["id"]].append(edit)
    result, ledger, matched = [], [], set()
    for original in records:
        row = deepcopy(original)
        changes = []
        for edit in edits.get(row["id"], []):
            index = edit["index"]
            before = row["messages"][index]
            if edit["expect"] not in before["content"] or before["content"] == edit["replacement"]:
                raise ValueError("correction precondition failed: " + row["id"])
            after = dict(before, content=edit["replacement"])
            row["messages"][index] = after
            changes.append({"message_index": index, "role": before["role"], "category": edit["category"],
                            "before": before["content"], "after": after["content"],
                            "before_sha256": digest(before), "after_sha256": digest(after)})
            matched.add((edit["id"], index))
        p = (provenance or {}).get(original["id"], {})
        if (p.get("kind") in {"agent_authored_compositional", "agent_authored_failure_informed"}
                and p.get("opening_topic") in spec["context_binding"]["topics"]
                and "mimir" not in row["messages"][0]["content"].casefold()):
            before = row["messages"][0]
            after = dict(before, content=spec["context_binding"][row["language"]] + "\n\n" + before["content"])
            row["messages"][0] = after
            changes.append({"message_index": 0, "role": "user", "category": "explicit_model_and_historical_scope",
                            "before": before["content"], "after": after["content"],
                            "before_sha256": digest(before), "after_sha256": digest(after)})
        if changes:
            row["id"] = digest({"schema": SCHEMA, "supersedes": original["id"], "messages": row["messages"]})
            ledger.append({"original_id": original["id"], "corrected_id": row["id"],
                           "language": row["language"], "original_record_sha256": digest(original),
                           "corrected_record_sha256": digest(row), "changes": changes,
                           "human_reviewed": False, "gpu_audited": False})
        validate_messages(row["messages"])
        result.append(row)
    return result, ledger, matched


def deduplicate(records):
    retained, seen, exclusions = [], {}, []
    for row in records:
        fingerprint = chat_fingerprint(row["messages"])
        if fingerprint in seen:
            exclusions.append({"id": row["id"], "kept_id": seen[fingerprint], "record_sha256": digest(row),
                               "reason": "exact full conversation duplicate after explicit correction"})
        else:
            seen[fingerprint] = row["id"]
            retained.append(row)
    return retained, exclusions


def heldout(spec, answer_spec=None):
    answer_spec = answer_spec or previous_builder.read_spec()
    result = {lang: [] for lang in base.LANGUAGES}
    for case in spec["heldout"]:
        if set(case) - {"followup"} != {"id", "answer", "questions"} or len(case["questions"]) != 2:
            raise ValueError("invalid heldout family")
        for variant, question in enumerate(case["questions"]):
            if set(question) != {"da", "en"}:
                raise ValueError("heldout language map must be exactly da/en")
            answer = (spec.get("answers", {}).get(case["answer"])
                      or answer_spec["requests"][case["answer"]]["brief"])
            if set(answer) != {"da", "en"}:
                raise ValueError("answer language map must be exactly da/en")
            for lang in base.LANGUAGES:
                messages = [{"role": "user", "content": question[lang]},
                            {"role": "assistant", "content": answer[lang]}]
                if "followup" in case:
                    follow = case["followup"]
                    if set(follow) != {"answer", "question"} or set(follow["question"]) != {"da", "en"}:
                        raise ValueError("invalid followup")
                    follow_answer = (spec.get("answers", {}).get(follow["answer"])
                                     or answer_spec["requests"][follow["answer"]]["brief"])
                    messages += [{"role": "user", "content": follow["question"][lang]},
                                 {"role": "assistant", "content": follow_answer[lang]}]
                validate_messages(messages)
                row = {"id": digest({"schema": SCHEMA, "language": lang, "messages": messages}),
                       "language": lang, "messages": messages, "task": "identity",
                       "parent_pair_id": None, "direction": "native"}
                result[lang].append(row)
    if len({case["id"] for case in spec["heldout"]}) != 25:
        raise ValueError("expected 25 fresh heldout families")
    return result


def source_data(previous):
    manifest = load(previous / "manifest.json")
    train, development = {}, {}
    for lang in base.LANGUAGES:
        train[lang] = list(rows(previous / manifest["languages"][lang]["input"]))
        development[lang] = list(rows(previous / f"development/{lang}/previous-heldout.jsonl.gz"))
        development[lang] += list(rows(previous / f"heldout/{lang}/test.jsonl.gz"))
    provenance = {r["id"]: r for r in rows(previous / "metadata/provenance.jsonl.gz")}
    return train, development, provenance


def questions(records):
    return {base.question_key(m["content"]) for r in records for m in r["messages"] if m["role"] == "user"}


def validate_splits(train, development, test, original):
    for lang in base.LANGUAGES:
        if len(test[lang]) != 50 or len(questions(test[lang])) < 50:
            raise ValueError("heldout must have 50 cases and at least 50 unique questions per language")
        if questions(test[lang]) & questions(train[lang] + original[lang] + development[lang]):
            raise ValueError("fresh heldout prompt overlaps inherited data")
        # Earlier artifacts may contain pre-existing overlap; no correction may introduce it.
        introduced = questions(train[lang]) - questions(original[lang])
        if introduced & questions(development[lang]):
            raise ValueError("corrected training copied development prompt")
        for group in (train[lang], test[lang]):
            if len({chat_fingerprint(r["messages"]) for r in group}) != len(group):
                raise ValueError("duplicate full conversation")


def measure(records, renderer):
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    results = []
    for row in records:
        count = renderer(row["messages"])
        response_lengths = [len(tokenize_example(renderer.tokenizer, renderer.template, example, False)[1])
                            for example in examples_from_messages(row["messages"], [])]
        results.append(dict(count, id=row["id"], response_tokens=sum(response_lengths),
                            response_lengths=response_lengths))
    return results


def aggregate(measurements):
    return {"conversations": len(measurements),
            **{key: sum(r[key] for r in measurements) for key in
               ("assistant_targets", "rendered_tokens", "response_tokens")},
            "max_rendered_length": max((r["max_rendered_length"] for r in measurements), default=0)}


def readable(records):
    return "\n".join(["# Identity v4 source view", "Agent-authored corrections; not human-reviewed or GPU-audited."]
                     + [f"\n## {r['id']}\n" + "\n\n".join(f"{m['role']}: {m['content']}" for m in r["messages"])
                        for r in records]) + "\n"


def build(output, previous=PREVIOUS, spec=SPEC, metadata=ROOT / "data/sampled_dfm11/metadata.json"):
    output, previous, spec = Path(output).resolve(), Path(previous).resolve(), Path(spec).resolve()
    if output.exists():
        raise FileExistsError(output)
    if previous_builder.verify(previous)["manifest_sha256"] != PREVIOUS_SHA:
        raise ValueError("unexpected prior artifact")
    config = read_spec(spec)
    original, development, old_provenance = source_data(previous)
    train, ledger, matched, exclusions = {}, [], set(), []
    for lang in base.LANGUAGES:
        corrected, changes, found = correct(original[lang], config, old_provenance)
        train[lang], dropped = deduplicate(corrected)
        exclusions.extend(dict(r, language=lang) for r in dropped)
        ledger.extend(changes)
        matched |= found
    if len(matched) != len(config["corrections"]):
        raise ValueError("correction source ID missing")
    test = heldout(config)
    validate_splits(train, development, test, original)
    renderer = base.NativeRenderer(metadata)
    for field, key in (("tokenizer_path", "tokenizer_sha256"), ("chat_template_path", "template_sha256")):
        if file_hash(renderer.info[field]) != config["runtime_binding"][key]:
            raise ValueError("current-profile runtime binding mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".identity-correction-", dir=output.parent))
    try:
        (temp / "metadata").mkdir()
        (temp / "review").mkdir()
        shutil.copyfile(spec, temp / "metadata/identity_correction.yaml")
        shutil.copyfile(ASSESSMENT, temp / "metadata/development-assessment.md")
        manifest = {"schema": SCHEMA, "profile": "xl-full-bp", "previous": str(previous),
                    "previous_manifest_sha256": PREVIOUS_SHA, "human_reviewed": False,
                    "gpu_audited": False, "native_gold": False, "training_launched": False,
                    "strategy": config["strategy"], "new_training_conversations": 0,
                    "runtime_binding": config["runtime_binding"],
                    "tokenizer": base.descriptor(renderer.info["tokenizer_path"]),
                    "template": base.descriptor(renderer.info["chat_template_path"]),
                    "heldout_scope": "50 fresh diagnostic questions per language, shared facts/answer bank; not native gold",
                    "prior_heldout_status": "v2 and v3 heldout are development only, not copied into training",
                    "physical_repeat": 1, "max_seq_len": 4096, "enable_thinking": False,
                    "pins": [base.descriptor(p) for p in (Path(__file__), spec, Path(base.__file__),
                             Path(helpers.__file__), Path(previous_builder.__file__), previous_builder.SPEC,
                             base.FACTS, ASSESSMENT, metadata, previous / "manifest.json",
                             REVIEW / "candidate-ledger.jsonl", REVIEW / "runtime-and-facts.json",
                             renderer.info["tokenizer_path"], renderer.info["chat_template_path"])],
                    "languages": {}, "files": []}
        all_provenance, measurements = [], []
        changed = {r["corrected_id"]: r for r in ledger}
        for lang in base.LANGUAGES:
            measures = {key: measure(group, renderer) for key, group in
                        {"original_v3": original[lang], "merged": train[lang],
                         "heldout": test[lang], "development": development[lang]}.items()}
            path = f"inputs/dfm12-identity-xl-full-bp-{lang}/train-00000.jsonl.gz"
            base.write_rows(temp / path, train[lang])
            base.write_rows(temp / f"heldout/{lang}/test.jsonl.gz", test[lang])
            base.write_rows(temp / f"development/{lang}/previous-heldout.jsonl.gz", development[lang])
            for split, group in (("train", train[lang]), ("heldout", test[lang])):
                (temp / f"review/{lang}-{split}.md").write_text(readable(group))
            source_totals = defaultdict(Counter)
            originals = {r["id"]: (r, m) for r, m in zip(original[lang], measures["original_v3"])}
            for row, new_m in zip(train[lang], measures["merged"]):
                original_id = changed[row["id"]]["original_id"] if row["id"] in changed else row["id"]
                old_row, old_m = originals[original_id]
                p = old_provenance[old_row["id"]]
                origin = "v3" if p.get("kind") == "agent_authored_failure_informed" else (
                    "v2" if p.get("kind") == "agent_authored_compositional" else "accepted_original")
                source_totals[origin].update(before_response_tokens=old_m["response_tokens"],
                                             after_response_tokens=new_m["response_tokens"])
                all_provenance.append({"id": row["id"], "language": lang, "split": "train",
                                       "origin": origin, "inherited_id": old_row["id"],
                                       "inherited_provenance": p, "record_sha256": digest(row),
                                       "corrected": row["id"] in changed,
                                       "human_reviewed": False if row["id"] in changed else p.get("human_reviewed", False),
                                       "gpu_audited": False if row["id"] in changed else p.get("gpu_audited", False)})
            for split in measures:
                measurements.extend(dict(m, language=lang, split=split) for m in measures[split])
            manifest["languages"][lang] = {"input": path, "counts": {k: aggregate(v) for k, v in measures.items()},
                                           "response_tokens_by_origin": dict(source_totals),
                                           "corrected_conversations": sum(r["id"] in changed for r in train[lang]),
                                           "unique_user_questions": len(questions(train[lang])),
                                           "turn_histogram": dict(Counter(len(r["messages"]) // 2 for r in train[lang]))}
        base.write_rows(temp / "metadata/correction-ledger.jsonl.gz", ledger)
        base.write_rows(temp / "metadata/deduplication-ledger.jsonl.gz", exclusions)
        edit_keys = {(r["original_id"], c["message_index"]) for r in ledger for c in r["changes"]}
        dispositions = [dict(r, v4_action="corrected" if (r["record_id"], r["message_index_0based"]) in edit_keys
                            else "retained_after_contextual_review") for r in rows(REVIEW / "candidate-ledger.jsonl")]
        base.write_rows(temp / "metadata/candidate-dispositions.jsonl.gz", dispositions)
        base.write_rows(temp / "metadata/provenance.jsonl.gz", all_provenance)
        base.write_rows(temp / "metadata/response-measurements.jsonl.gz", measurements)
        (temp / "review/corrections.md").write_text("# Exact inherited-turn corrections\n\n" + "\n".join(
            f"## {r['original_id']} -> {r['corrected_id']}\n" + "\n".join(
                f"### Turn index {c['message_index']}: {c['category']}\n\nBefore: {c['before']}\n\nAfter: {c['after']}\n"
                for c in r["changes"]) for r in ledger))
        manifest["corrections"] = {"conversations": len(ledger), "explicit_assistant_turns": len(matched),
                                   "turns": sum(len(r["changes"]) for r in ledger), "deduplicated_conversations": len(exclusions),
                                   "categories": dict(Counter(c["category"] for r in ledger for c in r["changes"]))}
        for path in sorted(temp.rglob("*")):
            if path.is_file():
                item = base.descriptor(path)
                item["path"] = str(path.relative_to(temp))
                manifest["files"].append(item)
        write_json(temp / "manifest.json", manifest)
        write_json(temp / "seal.json", {"schema": SCHEMA, "manifest_sha256": file_hash(temp / "manifest.json")})
        verify(temp)
        temp.rename(output)
    except BaseException:
        shutil.rmtree(temp)
        raise
    return {"output": str(output), "manifest_sha256": file_hash(output / "manifest.json"),
            "corrections": manifest["corrections"], "languages": manifest["languages"]}


def verify(root):
    root = Path(root).resolve()
    manifest = load(root / "manifest.json")
    if manifest["schema"] != SCHEMA or load(root / "seal.json")["manifest_sha256"] != file_hash(root / "manifest.json"):
        raise ValueError("manifest seal mismatch")
    owned = {"manifest.json", "seal.json"}
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or item["path"] in owned:
            raise ValueError("unsafe/duplicate artifact path")
        owned.add(item["path"])
        if file_hash(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("artifact hash mismatch")
    if {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} != owned:
        raise ValueError("unlisted artifact file")
    for pin in manifest["pins"]:
        if file_hash(pin["path"]) != pin["sha256"]:
            raise ValueError("source pin drift: " + pin["path"])
    previous = Path(manifest["previous"])
    if previous_builder.verify(previous)["manifest_sha256"] != PREVIOUS_SHA:
        raise ValueError("previous source drift")
    config = read_spec(root / "metadata/identity_correction.yaml")
    original, development, provenance = source_data(previous)
    test, train, ledger, matched, exclusions = heldout(config), {}, [], set(), []
    for lang in base.LANGUAGES:
        corrected, changes, found = correct(original[lang], config, provenance)
        train[lang], dropped = deduplicate(corrected)
        exclusions.extend(dict(r, language=lang) for r in dropped)
        ledger.extend(changes)
        matched |= found
        for path, expected in ((manifest["languages"][lang]["input"], train[lang]),
                               (f"heldout/{lang}/test.jsonl.gz", test[lang]),
                               (f"development/{lang}/previous-heldout.jsonl.gz", development[lang])):
            if list(rows(root / path)) != expected:
                raise ValueError("reconstruction mismatch: " + path)
    if len(matched) != len(config["corrections"]) or list(rows(root / "metadata/correction-ledger.jsonl.gz")) != ledger:
        raise ValueError("correction ledger mismatch")
    if list(rows(root / "metadata/deduplication-ledger.jsonl.gz")) != exclusions:
        raise ValueError("deduplication ledger mismatch")
    validate_splits(train, development, test, original)
    return {"valid": True, "manifest_sha256": file_hash(root / "manifest.json")}


def mixture(root, tokenized, output, replay=ROOT / "data/sampled_dfm11"):
    from . import build_identity_adaptation as adaptation
    import numpy as np
    root, tokenized, output = Path(root), Path(tokenized), Path(output)
    verified = verify(root)
    completion = load(tokenized / "completion.json")
    if completion["files"] != 2 or completion["skipped_rows_this_run"] != 0:
        raise ValueError("unexpected tokenization inputs/skips")
    expected = {f"dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz" for lang in base.LANGUAGES}
    if {p.name for p in tokenized.iterdir() if p.is_dir()} != expected:
        raise ValueError("unexpected tokenized directory")
    receipt = adaptation.build(Path(replay), tokenized, output, steps=1000, seed=20260929,
                               start_step=2880261, start_checkpoint="step_2880261", data_epoch=13,
                               global_batch=262144, gas=2, world_size=8,
                               identity_manifest=root / "manifest.json")
    arrays = adaptation.indices(output / "epoch_0")
    labels = np.load(output / "source-labels.npy", mmap_mode="r")
    supervised = {str(int(label)): int(arrays["resp_len"][labels == label].sum()) for label in np.unique(labels)}
    total = sum(supervised.values())
    stop = receipt["packing"]["row_end_at_stop"]
    supervised_stop = {str(int(label)): int(arrays["resp_len"][:stop][labels[:stop] == label].sum())
                       for label in np.unique(labels)}
    companion = {"schema": "dfm12-identity-v4-mixture-lineage-v1", "identity_manifest": str((root / "manifest.json").resolve()),
                 "identity_manifest_sha256": verified["manifest_sha256"],
                 "build_receipt_sha256": file_hash(output / "build-receipt.json"),
                 "metadata_sha256": file_hash(output / "metadata.json"),
                 "tokenization_completion": base.descriptor(tokenized / "completion.json"),
                 "response_tokens_by_source_label": supervised,
                 "identity_response_fraction": sum(v for k, v in supervised.items() if k != "0") / total,
                 "response_tokens_by_source_label_at_stop": supervised_stop,
                 "identity_response_fraction_at_stop": sum(v for k, v in supervised_stop.items() if k != "0") / sum(supervised_stop.values()),
                 "heldout_and_development_excluded": True, "training_launched": False}
    write_json(output / "identity-lineage.json", companion)
    return {"output": str(output), "lineage": companion, "packing": receipt["packing"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--previous", type=Path, default=PREVIOUS)
    p.add_argument("--spec", type=Path, default=SPEC)
    p.add_argument("--metadata", type=Path, default=ROOT / "data/sampled_dfm11/metadata.json")
    sub.add_parser("verify").add_argument("--root", type=Path, required=True)
    p = sub.add_parser("mixture")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--tokenized", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--replay", type=Path, default=ROOT / "data/sampled_dfm11")
    args = vars(parser.parse_args())
    print(json.dumps({"build": build, "verify": verify, "mixture": mixture}[args.pop("command")](**args), indent=2))


if __name__ == "__main__":
    main()
