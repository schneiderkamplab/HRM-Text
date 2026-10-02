"""Isolated DA/EN identity extension; no public export or training side effects."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import shutil
import tempfile

import yaml

from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint, validate_messages

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "dfm12/identity_extension.yaml"
FACTS = ROOT / "dfm12/identity_facts.yaml"
FACTS_SHA = "d81c94652a494d84e9937299964baad5519f150e96bea056ce197d5c95488a71"
SCHEMA = "dfm12-curated-identity-extension-v1"
LANGUAGES = ("da", "en")


def question_key(text):
    return re.sub(r"\W+", " ", text.casefold()).strip()


def compile_spec(spec_path=SPEC, facts_path=FACTS):
    """Compile native conversations and isolated provenance, with grouped splits."""
    spec = yaml.safe_load(Path(spec_path).read_text())
    facts = yaml.safe_load(Path(facts_path).read_text())
    if (spec["version"] != 1 or spec["profile"] != "xl-full-bp"
            or spec["facts_sha256"] != FACTS_SHA or file_hash(facts_path) != FACTS_SHA):
        raise ValueError("unapproved facts/profile/version")
    answers = spec["answers"]
    valid_refs = set(facts["facts"]) | {"profile"}
    for answer in answers.values():
        if not answer["facts"] or not set(answer["facts"]) <= valid_refs:
            raise ValueError("invalid fact references")
        for lang in LANGUAGES:
            if not isinstance(answer[lang], str) or not answer[lang].strip():
                raise ValueError("missing native answer")
    for lang, negative in (("da", "Nej,"), ("en", "No,")):
        if not answers["role_correction"][lang].startswith(negative):
            raise ValueError("false premise needs explicit correction")
        if "Kristoffer" in answers["team"][lang] or "Kristoffer" in answers["team_lead"][lang]:
            raise ValueError("organization/team leadership conflated")
        for name in ("Peter Schneider-Kamp", "Jacob Nielsen", "Lukas Galke Poech",
                     "Gianluca Barmina", "Annemette Brok Pirchert", "Kenneth Enevoldsen"):
            if name not in answers["team"][lang]:
                raise ValueError("missing team name")
        architecture = answers["architecture"][lang]
        if architecture.count("16") != 2 or not all(n in architecture for n in ("2", "3", "6", "8")):
            raise ValueError("incomplete XL architecture")
        if len(re.findall(r"[.!?](?:\s|$)", answers["namesake_short"][lang])) > 2:
            raise ValueError("brief namesake answer too long")
    result = []
    groups, questions, fingerprints = set(), set(), set()
    for case in spec["cases"]:
        if case["id"] in groups or case["split"] not in {"train", "heldout"}:
            raise ValueError("duplicate group or invalid split")
        groups.add(case["id"])
        if case["topic"] not in {"namesake", "architecture", "leadership", "intent_contrast"}:
            raise ValueError("unknown topic")
        if not 1 <= len(case["turns"]) <= 3:
            raise ValueError("invalid turn count")
        for lang in LANGUAGES:
            messages, refs = [], []
            for turn in case["turns"]:
                prompt = turn[lang]
                key = (lang, question_key(prompt))
                if key in questions:
                    raise ValueError("duplicate curated question, including across splits")
                questions.add(key)
                answer = answers[turn["answer"]]
                refs.append({"answer": turn["answer"], "facts": answer["facts"]})
                messages.extend([{"role": "user", "content": prompt},
                                 {"role": "assistant", "content": answer[lang]}])
            validate_messages(messages)
            fingerprint = chat_fingerprint(messages)
            if fingerprint in fingerprints:
                raise ValueError("duplicate curated conversation")
            fingerprints.add(fingerprint)
            provenance = {"kind": "agent_authored_curated", "group": case["id"],
                          "split": case["split"], "topic": case["topic"],
                          "profile": spec["profile"], "facts_sha256": FACTS_SHA,
                          "spec_sha256": file_hash(spec_path), "turn_references": refs,
                          "human_reviewed": False, "gpu_audited": False,
                          "native_gold": False}
            row = {"id": digest({"messages": messages, "language": lang,
                                 "provenance": provenance}),
                   "messages": messages, "language": lang, "task": "identity",
                   "parent_pair_id": None, "direction": "native"}
            result.append((row, provenance))
    return result


class NativeRenderer:
    def __init__(self, metadata):
        import jinja2
        from tokenizers import Tokenizer
        self.info = load(metadata)["tokenizer_info"]
        if self.info.get("enable_thinking") is not False:
            raise ValueError("expected raw non-thinking training template")
        self.tokenizer = Tokenizer.from_file(self.info["tokenizer_path"])
        self.template = jinja2.Environment().from_string(
            Path(self.info["chat_template_path"]).read_text())

    def __call__(self, messages):
        from scripts.tokenize_chat_template import examples_from_messages, render, tokenize_example
        lengths = []
        for example in examples_from_messages(messages, []):
            full = render(self.template, example.prompt_messages + [example.assistant_message],
                          [], False, False)
            length = len(self.tokenizer.encode(full, add_special_tokens=False).ids)
            encoded = tokenize_example(self.tokenizer, self.template, example, False)
            if not encoded or sum(map(len, encoded)) != length or length > 4096:
                raise ValueError("invalid or oversized actual native render")
            lengths.append(length)
        if not lengths:
            raise ValueError("no assistant targets")
        return {"assistant_targets": len(lengths), "rendered_tokens": sum(lengths),
                "max_rendered_length": max(lengths)}


def descriptor(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": file_hash(path), "bytes": path.stat().st_size}


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    # No gzip timestamp or filename: identical inputs produce identical artifacts.
    with path.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as out:
        for value in values:
            out.write((json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode())


def check_overlap(original, additions):
    fingerprints = {chat_fingerprint(row["messages"]) for row in original}
    questions = {question_key(m["content"]) for row in original
                 for m in row["messages"] if m["role"] == "user"}
    overlap = []
    for row, provenance in additions:
        if chat_fingerprint(row["messages"]) in fingerprints:
            raise ValueError("curated conversation duplicates original")
        for message in row["messages"]:
            if message["role"] == "user" and question_key(message["content"]) in questions:
                if provenance["split"] == "heldout":
                    raise ValueError("heldout question overlaps original training")
                overlap.append({"id": row["id"], "question": message["content"]})
    return overlap


def build(output, exports=ROOT / "exports_dfm12", spec=SPEC, facts=FACTS,
          metadata=ROOT / "data/sampled_dfm11/metadata.json"):
    """Materialize merged native DA/EN inputs. Never alter accepted originals."""
    from .export_validator import validate
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    compiled = compile_spec(spec, facts)
    renderer = NativeRenderer(metadata)
    original, sources, overlaps = {}, {}, {}
    for lang in LANGUAGES:
        package = Path(exports) / f"dfm12-identity-xl-full-bp-{lang}"
        validate(package)
        manifest_path = package / "metadata/manifest.json"
        manifest = load(manifest_path)
        if (manifest["source"]["profile"] != "xl-full-bp"
                or manifest["source"]["facts_sha256"] != FACTS_SHA):
            raise ValueError("original facts/profile mismatch")
        files = [package / item["file"] for item in manifest["data_files"]]
        original[lang] = [row for path in files for row in rows(path)]
        if any(row["language"] != lang for row in original[lang]):
            raise ValueError("original language mismatch")
        sources[lang] = {"manifest": descriptor(manifest_path),
                         "files": [descriptor(p) for p in files],
                         "metadata_files": [descriptor(package / f["file"])
                                            for f in manifest["metadata_files"]]}
        overlaps[lang] = check_overlap(original[lang], [(r, p) for r, p in compiled
                                                       if r["language"] == lang])
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".identity-extension-", dir=output.parent))
    try:
        (temp / "metadata").mkdir()
        shutil.copyfile(spec, temp / "metadata/identity_extension.yaml")
        shutil.copyfile(facts, temp / "metadata/identity_facts.yaml")
        manifest = {"schema": SCHEMA, "status": "local_curated_cpu_validated",
                    "human_reviewed": False, "gpu_audited": False, "native_gold": False,
                    "profile": "xl-full-bp", "sources": sources,
                    "builder": descriptor(Path(__file__)),
                    "spec": descriptor(spec), "facts": descriptor(facts),
                    "tokenizer_metadata": descriptor(metadata),
                    "tokenizer": descriptor(renderer.info["tokenizer_path"]),
                    "template": descriptor(renderer.info["chat_template_path"]),
                    "enable_thinking": False, "max_seq_len": 4096,
                    "physical_repeat": 1, "other_languages": "untouched; not copied",
                    "heldout_scope": "grouped question paraphrases, not unseen facts or answers",
                    "training_question_overlap_with_original": overlaps,
                    "languages": {}, "files": []}
        provenance_rows = []
        for lang in LANGUAGES:
            additions = [(r, p) for r, p in compiled if r["language"] == lang]
            train = [r for r, p in additions if p["split"] == "train"]
            heldout = [r for r, p in additions if p["split"] == "heldout"]
            merged = original[lang] + train
            if len({r["id"] for r in merged + heldout}) != len(merged + heldout):
                raise ValueError("duplicate record id")
            input_path = f"inputs/dfm12-identity-xl-full-bp-{lang}/train-00000.jsonl.gz"
            groups = {"original": original[lang], "new_train": train,
                      "merged": merged, "heldout": heldout}
            stats = {}
            render_cache = {}
            for name, records in groups.items():
                counts = Counter()
                maximum = 0
                for row in records:
                    validate_messages(row["messages"])
                    if row["id"] not in render_cache:
                        render_cache[row["id"]] = renderer(row["messages"])
                    result = render_cache[row["id"]]
                    counts.update({k: result[k] for k in ("assistant_targets", "rendered_tokens")})
                    maximum = max(maximum, result["max_rendered_length"])
                stats[name] = dict(counts, conversations=len(records), max_rendered_length=maximum)
            write_rows(temp / input_path, merged)
            write_rows(temp / f"curated/{lang}/train.jsonl.gz", train)
            write_rows(temp / f"heldout/{lang}/test.jsonl.gz", heldout)
            manifest["languages"][lang] = {"input": input_path, "counts": stats}
            for ordinal, row in enumerate(original[lang]):
                provenance_rows.append({"id": row["id"], "language": lang, "split": "train",
                                        "kind": "unchanged_accepted_original", "ordinal": ordinal,
                                        "source_manifest_sha256": sources[lang]["manifest"]["sha256"]})
            provenance_rows.extend(dict(p, id=r["id"], language=lang,
                                        render=render_cache[r["id"]]) for r, p in additions)
        write_rows(temp / "metadata/provenance.jsonl.gz", provenance_rows)
        for path in sorted(temp.rglob("*")):
            if path.is_file():
                item = descriptor(path)
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
            "languages": manifest["languages"]}


def verify(root):
    """Check the sealed artifact and pinned source files; no writes."""
    root = Path(root).resolve()
    manifest = load(root / "manifest.json")
    if (manifest["schema"] != SCHEMA
            or load(root / "seal.json")["manifest_sha256"] != file_hash(root / "manifest.json")):
        raise ValueError("manifest seal mismatch")
    owned = {"manifest.json", "seal.json"}
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or item["path"] in owned:
            raise ValueError("invalid owned path")
        owned.add(item["path"])
        if file_hash(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("artifact hash mismatch")
    if {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} != owned:
        raise ValueError("unlisted artifact file")
    pins = [manifest[k] for k in ("builder", "spec", "facts", "tokenizer_metadata", "tokenizer", "template")]
    for source in manifest["sources"].values():
        pins.extend([source["manifest"], *source["files"], *source["metadata_files"]])
    for pin in pins:
        if file_hash(pin["path"]) != pin["sha256"]:
            raise ValueError("source pin drift: " + pin["path"])
    return {"valid": True, "manifest_sha256": file_hash(root / "manifest.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--exports", type=Path, default=ROOT / "exports_dfm12")
    build_parser.add_argument("--spec", type=Path, default=SPEC)
    build_parser.add_argument("--facts", type=Path, default=FACTS)
    build_parser.add_argument("--metadata", type=Path, default=ROOT / "data/sampled_dfm11/metadata.json")
    sub.add_parser("verify").add_argument("--root", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps(build(**args) if command == "build" else verify(**args), indent=2))


if __name__ == "__main__":
    main()
