"""Deterministic local DA/EN identity expansion; preserves the sealed v1 builder."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile

import yaml

from . import identity_extension as base
from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint, validate_messages

ROOT = base.ROOT
SPEC = ROOT / "dfm12/identity_expansion.yaml"
SCHEMA = "dfm12-curated-identity-expansion-v2"
EXPECTED = {"train": 500, "heldout": 50}
FAMILIES = {"train": 50, "heldout": 10}
HISTOGRAM = {"train": {1: 250, 2: 100, 3: 100, 4: 50},
             "heldout": {1: 25, 2: 10, 3: 10, 4: 5}}


def read_spec(path=SPEC, facts=base.FACTS):
    spec = yaml.safe_load(Path(path).read_text())
    registry = yaml.safe_load(Path(facts).read_text())
    if (spec["version"] != 2 or spec["profile"] != "xl-full-bp"
            or spec["facts_sha256"] != base.FACTS_SHA or file_hash(facts) != base.FACTS_SHA):
        raise ValueError("facts/profile/version mismatch")
    refs = set(registry["facts"]) | {"profile"}
    for value in spec["formats"].values():
        if set(value) != set(base.LANGUAGES):
            raise ValueError("format must contain exactly da/en")
    for key, request in spec["requests"].items():
        required = {"topic", "facts", "train", "heldout", "concise", "detailed"}
        if not required <= set(request) or set(request) - required - {"neutral_heldout", "neutral_concise"}:
            raise ValueError("unexpected request fields")
        if not request["facts"] or not set(request["facts"]) <= refs:
            raise ValueError("invalid fact references: " + key)
        if request["topic"] not in spec["topic_pool"]:
            raise ValueError("unknown topic")
        if request.get("neutral_heldout") and "neutral_concise" not in request:
            raise ValueError("missing neutral target")
        for field in ("train", "heldout", "concise", "detailed") + (("neutral_concise",) if "neutral_concise" in request else ()):
            if set(request[field]) != set(base.LANGUAGES):
                raise ValueError("text must contain exactly da/en")
            for lang in base.LANGUAGES:
                if not isinstance(request[field][lang], str) or not request[field][lang].strip():
                    raise ValueError("missing native text")
    for pool in spec["branch_pools"].values():
        if len(set(pool)) != len(pool) or len(pool) < 11 or not set(pool) <= spec["requests"].keys():
            raise ValueError("invalid substantive branch pool")
    for lang, no in (("da", "Nej,"), ("en", "No,")):
        for mode in ("concise", "detailed"):
            for key in ("kristoffer", "literal_being", "infallible", "eight_layers", "reuse",
                        "bp_contrast", "gemma_weights", "gemma_creator", "tools", "memory", "ability"):
                if not spec["requests"][key][mode][lang].startswith(no):
                    raise ValueError("missing explicit premise correction: " + key)
            for key in ("team_lead", "members"):
                if "Kristoffer" in spec["requests"][key][mode][lang]:
                    raise ValueError("team/organization conflation")
            for name in ("Peter Schneider-Kamp", "Jacob Nielsen", "Lukas Galke Poech",
                         "Gianluca Barmina", "Annemette Brok Pirchert", "Kenneth Enevoldsen"):
                if name not in spec["requests"]["members"][mode][lang]:
                    raise ValueError("missing team member")
            text = spec["requests"]["architecture"][mode][lang]
            if text.count("16") != 2 or not all(n in text for n in ("2", "3", "6", "8")):
                raise ValueError("incomplete architecture")
    families = spec["families"]
    if len({f["id"] for f in families}) != len(families):
        raise ValueError("duplicate family")
    if Counter(f["split"] for f in families) != FAMILIES:
        raise ValueError("incorrect family split counts")
    for family in families:
        if set(family) - {"neutral"} != {"id", "split", "turns", "answer", "da", "en"}:
            raise ValueError("unexpected family fields")
        if family["answer"] not in spec["requests"] or family["turns"] not in (1, 2, 3, 4):
            raise ValueError("invalid family plan")
        if family.get("neutral") and "neutral_concise" not in spec["requests"][family["answer"]]:
            raise ValueError("missing neutral opening target")
    return spec


def compile_spec(spec_path=SPEC, facts_path=base.FACTS):
    """Expand 50x10 train and 10x5 held-out bilingual scenario compositions.

    Opening questions and fact answers are reused transparently. Variants change
    the requested branch facts, not arbitrary prefixes. Held-out wording is from
    separate families/banks, while facts and answer strings may be shared.
    """
    spec = read_spec(spec_path, facts_path)
    result = []
    for family_index, family in enumerate(spec["families"]):
        split, opening = family["split"], family["answer"]
        request = spec["requests"][opening]
        pool = spec["branch_pools"][spec["topic_pool"][request["topic"]]]
        pool = [key for key in pool if key != opening]
        offset = family_index % len(pool)
        pool = pool[offset:] + pool[:offset]
        # Held-out families use a separate wording bank and reverse branch order.
        if split == "heldout":
            pool = list(reversed(pool))
        for variant in range(10 if split == "train" else 5):
            branch = [pool[(variant + shift) % len(pool)] for shift in (0, 3, 7)]
            plans = ([[opening]] if family["turns"] == 1 and variant < 2 else
                     [[opening, branch[0]]] if family["turns"] == 1 else
                     [[opening]] + [[key] for key in branch[:family["turns"] - 1]])
            for lang in base.LANGUAGES:
                messages, references = [], []
                for turn, keys in enumerate(plans):
                    mode = "concise" if (variant + turn) % 2 == 0 else "detailed"
                    questions = [family[lang] if turn == 0 and i == 0 else
                                 spec["requests"][key][split][lang] for i, key in enumerate(keys)]
                    format_key = ("heldout_" if split == "heldout" else "") + mode
                    # Keep direct variant zero literally question-only, including the
                    # three requested leadership questions. Variant one asks for detail.
                    question = "\n\n".join(questions if family["turns"] == 1 and variant == 0
                                             else questions + [spec["formats"][format_key][lang]])
                    answer_forms = []
                    for i, key in enumerate(keys):
                        neutral = (family.get("neutral", False) if turn == 0 and i == 0 else
                                   split == "heldout" and spec["requests"][key].get("neutral_heldout", False))
                        answer_forms.append("neutral_concise" if mode == "concise" and neutral else mode)
                    answer = "\n\n".join(spec["requests"][key][form][lang]
                                           for key, form in zip(keys, answer_forms))
                    messages.extend([{"role": "user", "content": question},
                                     {"role": "assistant", "content": answer}])
                    references.append({"requests": keys, "mode": mode,
                                       "answer_forms": answer_forms,
                                       "question_atoms": questions,
                                       "facts": sorted({f for key in keys for f in spec["requests"][key]["facts"]})})
                validate_messages(messages)
                provenance = {"kind": "agent_authored_compositional", "family": family["id"],
                              "variant": variant, "split": split, "profile": "xl-full-bp",
                              "opening_topic": request["topic"], "turn_references": references,
                              "facts_sha256": base.FACTS_SHA, "spec_sha256": file_hash(spec_path),
                              "human_reviewed": False, "gpu_audited": False, "native_gold": False}
                row = {"id": digest({"messages": messages, "language": lang, "provenance": provenance}),
                       "language": lang, "messages": messages, "task": "identity",
                       "parent_pair_id": None, "direction": "native"}
                result.append((row, provenance))
    validate_compiled(result)
    return result


def question_sets(records):
    turns, atoms = set(), set()
    for row, provenance in records:
        turns.update(base.question_key(m["content"]) for m in row["messages"] if m["role"] == "user")
        atoms.update(base.question_key(q) for ref in provenance["turn_references"]
                     for q in ref["question_atoms"])
    return turns, atoms


def validate_compiled(records):
    if len({r["id"] for r, _ in records}) != len(records):
        raise ValueError("duplicate id")
    for lang in base.LANGUAGES:
        selected = [(r, p) for r, p in records if r["language"] == lang]
        fingerprints = [chat_fingerprint(r["messages"]) for r, _ in selected]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("duplicate conversation")
        by_split = {s: [(r, p) for r, p in selected if p["split"] == s] for s in EXPECTED}
        for split, group in by_split.items():
            if len(group) != EXPECTED[split]:
                raise ValueError("incorrect conversation counts")
            if Counter(len(r["messages"]) // 2 for r, _ in group) != HISTOGRAM[split]:
                raise ValueError("incorrect turn histogram")
            if len({p["family"] for _, p in group}) != FAMILIES[split]:
                raise ValueError("incorrect family counts")
            if len({p["opening_topic"] for _, p in group}) < (10 if split == "train" else 5):
                raise ValueError("insufficient topic diversity")
            for family in {p["family"] for _, p in group}:
                plans = {tuple(tuple(ref["requests"]) for ref in p["turn_references"])
                         for _, p in group if p["family"] == family}
                first_row = next(r for r, p in group if p["family"] == family)
                expected_plans = (10 if split == "train" else 5) - (len(first_row["messages"]) == 2)
                if len(plans) != expected_plans:
                    raise ValueError("variants must change factual request plans")
        if {p["family"] for _, p in by_split["train"]} & {p["family"] for _, p in by_split["heldout"]}:
            raise ValueError("family split leakage")
        train_turns, train_atoms = question_sets(by_split["train"])
        test_turns, test_atoms = question_sets(by_split["heldout"])
        if train_turns & test_turns or train_atoms & test_atoms:
            raise ValueError("heldout normalized question overlap")


def diversity(records):
    output = {}
    for lang in base.LANGUAGES:
        output[lang] = {}
        for split in EXPECTED:
            group = [(r, p) for r, p in records if r["language"] == lang and p["split"] == split]
            turns, atoms = question_sets(group)
            frequencies = Counter(base.question_key(m["content"]) for r, _ in group
                                  for m in r["messages"] if m["role"] == "user")
            output[lang][split] = {
                "conversations": len(group), "families": len({p["family"] for _, p in group}),
                "turn_histogram": dict(sorted(Counter(len(r["messages"]) // 2 for r, _ in group).items())),
                "opening_topics": dict(sorted(Counter(p["opening_topic"] for _, p in group).items())),
                "request_counts": dict(sorted(Counter(key for _, p in group for ref in p["turn_references"]
                                                     for key in ref["requests"]).items())),
                "answer_modes": dict(Counter(ref["mode"] for _, p in group for ref in p["turn_references"])),
                "unique_normalized_user_turns": len(turns), "unique_normalized_question_atoms": len(atoms),
                "user_turn_frequency_histogram": dict(sorted(Counter(frequencies.values()).items())),
                "maximum_user_turn_repetitions": max(frequencies.values()),
                "unique_assistant_texts": len({m["content"] for r, _ in group for m in r["messages"]
                                              if m["role"] == "assistant"})}
    return output


def check_original(original, compiled):
    overlaps = base.check_overlap(original, compiled)
    original_questions = {base.question_key(m["content"]) for r in original for m in r["messages"]
                          if m["role"] == "user"}
    _, heldout_atoms = question_sets([(r, p) for r, p in compiled if p["split"] == "heldout"])
    if original_questions & heldout_atoms:
        raise ValueError("heldout question atom overlaps original")
    return overlaps


def stats(records, renderer, cache):
    count = Counter()
    maximum = 0
    for row in records:
        validate_messages(row["messages"])
        if row["id"] not in cache:
            cache[row["id"]] = renderer(row["messages"])
        result = cache[row["id"]]
        count.update({k: result[k] for k in ("assistant_targets", "rendered_tokens")})
        maximum = max(maximum, result["max_rendered_length"])
    return dict(count, conversations=len(records), max_rendered_length=maximum)


def readable(records):
    parts = ["# Agent-authored compositional identity conversations\n",
             "Not human-reviewed, GPU-audited, or native-language gold.\n"]
    for row, p in records:
        parts.append(f"\n## {p['family']} / {p['variant']} / {row['language']} / {p['split']}\n")
        for message in row["messages"]:
            parts.append(f"\n**{message['role']}**\n\n{message['content']}\n")
    return "".join(parts)


def build(output, exports=ROOT / "exports_dfm12", spec=SPEC, facts=base.FACTS,
          metadata=ROOT / "data/sampled_dfm11/metadata.json"):
    from .export_validator import validate
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    compiled = compile_spec(spec, facts)
    renderer = base.NativeRenderer(metadata)
    sources, originals, overlaps = {}, {}, {}
    for lang in base.LANGUAGES:
        package = Path(exports) / f"dfm12-identity-xl-full-bp-{lang}"
        validate(package)
        original_manifest = load(package / "metadata/manifest.json")
        if (original_manifest["source"]["profile"] != "xl-full-bp"
                or original_manifest["source"]["facts_sha256"] != base.FACTS_SHA):
            raise ValueError("original profile/facts mismatch")
        files = [package / item["file"] for item in original_manifest["data_files"]]
        originals[lang] = [r for path in files for r in rows(path)]
        if any(r["language"] != lang for r in originals[lang]):
            raise ValueError("original language mismatch")
        sources[lang] = {"manifest": base.descriptor(package / "metadata/manifest.json"),
                         "files": [base.descriptor(p) for p in files],
                         "metadata_files": [base.descriptor(package / f["file"])
                                            for f in original_manifest["metadata_files"]]}
        overlaps[lang] = check_original(originals[lang], [(r, p) for r, p in compiled if r["language"] == lang])
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".identity-expansion-", dir=output.parent))
    try:
        (temp / "metadata").mkdir()
        (temp / "review").mkdir()
        shutil.copyfile(spec, temp / "metadata/identity_expansion.yaml")
        shutil.copyfile(facts, temp / "metadata/identity_facts.yaml")
        manifest = {"schema": SCHEMA, "status": "local_curated_cpu_validated",
                    "human_reviewed": False, "gpu_audited": False, "native_gold": False,
                    "profile": "xl-full-bp", "sources": sources,
                    "builder": base.descriptor(Path(__file__)), "helper": base.descriptor(Path(base.__file__)),
                    "spec": base.descriptor(spec), "facts": base.descriptor(facts),
                    "tokenizer_metadata": base.descriptor(metadata),
                    "tokenizer": base.descriptor(renderer.info["tokenizer_path"]),
                    "template": base.descriptor(renderer.info["chat_template_path"]),
                    "enable_thinking": False, "max_seq_len": 4096, "physical_repeat": 1,
                    "other_languages": "untouched; not copied",
                    "heldout_scope": "whole prompt families and wording; shared facts/answers; not semantic or native gold",
                    "composition": "opening plus different fact-specific branches; reused opening/answer banks disclosed",
                    "training_question_overlap_with_original": overlaps,
                    "diversity": diversity(compiled), "languages": {}, "files": []}
        provenance = []
        for lang in base.LANGUAGES:
            selected = [(r, p) for r, p in compiled if r["language"] == lang]
            train = [r for r, p in selected if p["split"] == "train"]
            heldout = [r for r, p in selected if p["split"] == "heldout"]
            merged = originals[lang] + train
            if len({r["id"] for r in merged + heldout}) != len(merged + heldout):
                raise ValueError("duplicate record id")
            cache = {}
            counts = {k: stats(v, renderer, cache) for k, v in {
                "original": originals[lang], "new_train": train, "merged": merged, "heldout": heldout}.items()}
            input_path = f"inputs/dfm12-identity-xl-full-bp-{lang}/train-00000.jsonl.gz"
            base.write_rows(temp / input_path, merged)
            base.write_rows(temp / f"curated/{lang}/train.jsonl.gz", train)
            base.write_rows(temp / f"heldout/{lang}/test.jsonl.gz", heldout)
            for split in EXPECTED:
                (temp / f"review/{lang}-{split}.md").write_text(
                    readable([(r, p) for r, p in selected if p["split"] == split]))
            manifest["languages"][lang] = {"input": input_path, "counts": counts}
            provenance.extend({"id": r["id"], "language": lang, "split": "train",
                               "kind": "unchanged_accepted_original", "ordinal": i,
                               "record_sha256": digest(r),
                               "source_manifest_sha256": sources[lang]["manifest"]["sha256"]}
                              for i, r in enumerate(originals[lang]))
            provenance.extend(dict(p, id=r["id"], language=lang, record_sha256=digest(r),
                                   render=cache[r["id"]]) for r, p in selected)
        base.write_rows(temp / "metadata/provenance.jsonl.gz", provenance)
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
            "languages": manifest["languages"], "diversity": manifest["diversity"]}


def verify(root):
    root = Path(root).resolve()
    manifest = load(root / "manifest.json")
    if (manifest["schema"] != SCHEMA
            or load(root / "seal.json")["manifest_sha256"] != file_hash(root / "manifest.json")):
        raise ValueError("manifest seal mismatch")
    owned = {"manifest.json", "seal.json"}
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or item["path"] in owned:
            raise ValueError("unsafe or duplicate artifact path")
        owned.add(item["path"])
        if file_hash(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("artifact hash mismatch")
    if {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} != owned:
        raise ValueError("unlisted artifact file")
    pins = [manifest[k] for k in ("builder", "helper", "spec", "facts", "tokenizer_metadata", "tokenizer", "template")]
    for source in manifest["sources"].values():
        pins.extend([source["manifest"], *source["files"], *source["metadata_files"]])
    for pin in pins:
        if file_hash(pin["path"]) != pin["sha256"]:
            raise ValueError("source pin drift: " + pin["path"])
    compiled = compile_spec(root / "metadata/identity_expansion.yaml", root / "metadata/identity_facts.yaml")
    for lang in base.LANGUAGES:
        train = [r for r, p in compiled if r["language"] == lang and p["split"] == "train"]
        heldout = [r for r, p in compiled if r["language"] == lang and p["split"] == "heldout"]
        original = [r for f in manifest["sources"][lang]["files"] for r in rows(f["path"])]
        if list(rows(root / manifest["languages"][lang]["input"])) != original + train:
            raise ValueError("merged records differ from original plus compiled training")
        if (list(rows(root / f"heldout/{lang}/test.jsonl.gz")) != heldout
                or list(rows(root / f"curated/{lang}/train.jsonl.gz")) != train):
            raise ValueError("split reconstruction mismatch")
    return {"valid": True, "manifest_sha256": file_hash(root / "manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--exports", type=Path, default=ROOT / "exports_dfm12")
    build_parser.add_argument("--spec", type=Path, default=SPEC)
    build_parser.add_argument("--facts", type=Path, default=base.FACTS)
    build_parser.add_argument("--metadata", type=Path, default=ROOT / "data/sampled_dfm11/metadata.json")
    sub.add_parser("verify").add_argument("--root", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(build(**args) if command == "build" else verify(**args), indent=2))


if __name__ == "__main__":
    main()
