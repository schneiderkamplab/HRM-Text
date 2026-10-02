"""Failure-informed v3 identity data and CPU-only continuation preparation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import tempfile

import yaml

from . import identity_extension as base
from . import identity_expansion as prior
from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint, validate_messages

ROOT = base.ROOT
SPEC = ROOT / "dfm12/identity_repair_expansion.yaml"
PREVIOUS = ROOT / "data/dfm12/identity-expansion-da-en-20260926-v2-r2"
ASSESSMENT = ROOT / "data/dfm12/identity-evaluation-second1000-20260926/reviewer-assessment.md"
SCHEMA = "dfm12-curated-identity-repair-v3"
PREVIOUS_SHA = "28cb1b97c542a25af19128c7b91bc37b24d87a6144dd62e220d10af3705125a4"


def read_spec(path=SPEC):
    spec = yaml.safe_load(Path(path).read_text())
    facts = yaml.safe_load(base.FACTS.read_text())
    if (spec["version"] != 3 or spec["profile"] != "xl-full-bp"
            or spec["facts_sha256"] != base.FACTS_SHA or file_hash(base.FACTS) != base.FACTS_SHA):
        raise ValueError("invalid facts/profile/version")
    if set(spec["authorized_context"]) != {"checkpoint_continuation"}:
        raise ValueError("unexpected contextual fact")
    allowed = set(facts["facts"]) | {"profile", "checkpoint_continuation"}
    for value in spec["formats"].values():
        if set(value) != {"da", "en"}:
            raise ValueError("format must be exactly da/en")
    for key, request in spec["requests"].items():
        if set(request) - {"derivation"} != {"topic", "facts", "polarity", "train", "heldout", "brief", "contrast"}:
            raise ValueError("unexpected request keys")
        if not request["facts"] or not set(request["facts"]) <= allowed:
            raise ValueError("invalid fact references")
        if request["topic"] not in spec["topic_pool"] or request["polarity"] not in {"neutral", "negative"}:
            raise ValueError("invalid topic/polarity")
        for field in ("train", "heldout", "brief", "contrast"):
            if set(request[field]) != {"da", "en"}:
                raise ValueError("text must be exactly da/en")
            for lang in base.LANGUAGES:
                text = request[field][lang]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("empty/nontext native field")
                if field in {"brief", "contrast"}:
                    negative = text.startswith("Nej," if lang == "da" else "No,")
                    if negative != (request["polarity"] == "negative"):
                        raise ValueError("answer polarity mismatch: " + key)
                    if not 1 <= len(re.findall(r"[.!?](?:\s|$)", text.replace("pr. ", "pr "))) <= 2:
                        raise ValueError("target exceeds two-sentence bound")
    for pool in spec["pools"].values():
        if len(pool) < 11 or len(set(pool)) != len(pool) or not set(pool) <= spec["requests"].keys():
            raise ValueError("invalid factual branch pool")
    families = spec["families"]
    if len({f["id"] for f in families}) != len(families):
        raise ValueError("duplicate family")
    if Counter(f["split"] for f in families) != prior.FAMILIES:
        raise ValueError("incorrect family counts")
    for family in families:
        if set(family) != {"id", "split", "turns", "answer", "da", "en"}:
            raise ValueError("unexpected family keys")
        if family["answer"] not in spec["requests"] or family["turns"] not in (1, 2, 3, 4):
            raise ValueError("invalid family")
    return spec


def compile_spec(path=SPEC):
    spec = read_spec(path)
    result = []
    for number, family in enumerate(spec["families"]):
        split, opening = family["split"], family["answer"]
        opening_request = spec["requests"][opening]
        pool = spec["pools"][spec["topic_pool"][opening_request["topic"]]]
        pool = [key for key in pool if key != opening]
        offset = number % len(pool)
        pool = pool[offset:] + pool[:offset]
        if split == "heldout":
            pool.reverse()
        for variant in range(10 if split == "train" else 5):
            branches = [pool[(variant + shift) % len(pool)] for shift in (0, 3, 7)]
            plans = ([[opening]] if family["turns"] == 1 and variant < 2 else
                     [[opening, branches[0]]] if family["turns"] == 1 else
                     [[opening]] + [[key] for key in branches[:family["turns"] - 1]])
            for lang in base.LANGUAGES:
                messages, references = [], []
                for turn, keys in enumerate(plans):
                    mode = "brief" if (variant + turn) % 2 == 0 else "contrast"
                    questions = [family[lang] if turn == 0 and i == 0 else spec["requests"][key][split][lang]
                                 for i, key in enumerate(keys)]
                    fmt = spec["formats"][("heldout_" if split == "heldout" else "") + mode][lang]
                    prompt = "\n\n".join(questions if family["turns"] == 1 and variant == 0 else questions + [fmt])
                    target = "\n\n".join(spec["requests"][key][mode][lang] for key in keys)
                    messages.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": target}])
                    references.append({"requests": keys, "question_atoms": questions, "mode": mode,
                                       "facts": sorted({f for key in keys for f in spec["requests"][key]["facts"]}),
                                       "derivations": [spec["requests"][key]["derivation"] for key in keys
                                                       if "derivation" in spec["requests"][key]]})
                validate_messages(messages)
                provenance = {"kind": "agent_authored_failure_informed", "family": family["id"],
                              "variant": variant, "split": split, "opening_topic": opening_request["topic"],
                              "turn_references": references, "profile": "xl-full-bp",
                              "facts_sha256": base.FACTS_SHA, "spec_sha256": file_hash(path),
                              "human_reviewed": False, "gpu_audited": False, "native_gold": False}
                row = {"id": digest({"language": lang, "messages": messages, "provenance": provenance}),
                       "language": lang, "messages": messages, "task": "identity",
                       "parent_pair_id": None, "direction": "native"}
                result.append((row, provenance))
    validate_compiled(result)
    return result


def validate_compiled(compiled):
    if len({r["id"] for r, _ in compiled}) != len(compiled):
        raise ValueError("duplicate record id")
    for lang in base.LANGUAGES:
        selected = [(r, p) for r, p in compiled if r["language"] == lang]
        if len({chat_fingerprint(r["messages"]) for r, _ in selected}) != len(selected):
            raise ValueError("duplicate conversation")
        groups = {s: [(r, p) for r, p in selected if p["split"] == s] for s in prior.EXPECTED}
        for split, group in groups.items():
            if len(group) != prior.EXPECTED[split]:
                raise ValueError("wrong split count")
            if Counter(len(r["messages"]) // 2 for r, _ in group) != prior.HISTOGRAM[split]:
                raise ValueError("wrong turn histogram")
            if len({p["opening_topic"] for _, p in group}) < (8 if split == "train" else 5):
                raise ValueError("insufficient factual topic diversity")
            if len({p["family"] for _, p in group}) != prior.FAMILIES[split]:
                raise ValueError("wrong family count")
            for family in {p["family"] for _, p in group}:
                family_rows = [(r, p) for r, p in group if p["family"] == family]
                plans = {tuple(tuple(ref["requests"]) for ref in p["turn_references"]) for _, p in family_rows}
                if len(plans) != len(family_rows) - (len(family_rows[0][0]["messages"]) == 2):
                    raise ValueError("non-substantive repeated variant")
        train = prior.question_sets(groups["train"])
        heldout = prior.question_sets(groups["heldout"])
        if (train[0] | train[1]) & (heldout[0] | heldout[1]):
            raise ValueError("new split question leakage")


def check_lineage(previous_root, compiled):
    """Old heldout informed tuning, so prohibit prompt copying and relabel as dev."""
    old = load(previous_root / "manifest.json")
    provenance = {r["id"]: r for r in rows(previous_root / "metadata/provenance.jsonl.gz")}
    data = {}
    for lang in base.LANGUAGES:
        inherited = list(rows(previous_root / old["languages"][lang]["input"]))
        development = list(rows(previous_root / f"heldout/{lang}/test.jsonl.gz"))
        old_questions = {base.question_key(m["content"]) for r in inherited + development
                         for m in r["messages"] if m["role"] == "user"}
        old_dev_questions = set()
        for records, is_dev in ((inherited, False), (development, True)):
            for row in records:
                p = provenance[row["id"]]
                atoms = {base.question_key(q) for ref in p.get("turn_references", []) for q in ref["question_atoms"]}
                old_questions.update(atoms)
                if is_dev:
                    old_dev_questions.update(atoms)
                    old_dev_questions.update(base.question_key(m["content"]) for m in row["messages"] if m["role"] == "user")
        selected = [(r, p) for r, p in compiled if r["language"] == lang]
        train = [(r, p) for r, p in selected if p["split"] == "train"]
        test = [(r, p) for r, p in selected if p["split"] == "heldout"]
        train_sets, test_sets = prior.question_sets(train), prior.question_sets(test)
        if (train_sets[0] | train_sets[1]) & old_dev_questions:
            raise ValueError("new training copied prior heldout/development question")
        if (test_sets[0] | test_sets[1]) & old_questions:
            raise ValueError("fresh heldout overlaps prior train/development question")
        fingerprints = {chat_fingerprint(r["messages"]) for r in inherited + development}
        if any(chat_fingerprint(r["messages"]) in fingerprints for r, _ in selected):
            raise ValueError("new conversation duplicates prior data")
        data[lang] = (inherited, development)
    return data, provenance


def build(output, previous=PREVIOUS, spec=SPEC, assessment=ASSESSMENT,
          metadata=ROOT / "data/sampled_dfm11/metadata.json"):
    output, previous = Path(output).resolve(), Path(previous).resolve()
    if output.exists():
        raise FileExistsError(output)
    if prior.verify(previous)["manifest_sha256"] != PREVIOUS_SHA:
        raise ValueError("unexpected prior artifact")
    compiled = compile_spec(spec)
    inherited, old_provenance = check_lineage(previous, compiled)
    old = load(previous / "manifest.json")
    renderer = base.NativeRenderer(metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".identity-repair-", dir=output.parent))
    try:
        (temp / "metadata").mkdir()
        (temp / "review").mkdir()
        shutil.copyfile(spec, temp / "metadata/identity_repair_expansion.yaml")
        shutil.copyfile(base.FACTS, temp / "metadata/identity_facts.yaml")
        shutil.copyfile(assessment, temp / "metadata/development-assessment.md")
        pins = [base.descriptor(p) for p in (Path(__file__), Path(base.__file__), Path(prior.__file__),
                spec, base.FACTS, assessment, metadata, renderer.info["tokenizer_path"],
                renderer.info["chat_template_path"], previous / "manifest.json")]
        manifest = {"schema": SCHEMA, "profile": "xl-full-bp", "status": "local_curated_cpu_validated",
                    "human_reviewed": False, "gpu_audited": False, "native_gold": False,
                    "previous": str(previous), "previous_manifest_sha256": PREVIOUS_SHA, "pins": pins,
                    "tokenizer": base.descriptor(renderer.info["tokenizer_path"]),
                    "template": base.descriptor(renderer.info["chat_template_path"]),
                    "prior_heldout_status": "development_after_failure_informed_tuning; excluded from training",
                    "heldout_scope": "fresh prompt families/wording, shared facts and target bank; not native gold",
                    "composition": "fact-specific branches, brief/contrast targets; repeated natural followups within split",
                    "physical_repeat": 1, "max_seq_len": 4096, "enable_thinking": False,
                    "diversity": prior.diversity(compiled), "languages": {}, "files": []}
        all_provenance = []
        for lang in base.LANGUAGES:
            old_train, development = inherited[lang]
            selected = [(r, p) for r, p in compiled if r["language"] == lang]
            train = [r for r, p in selected if p["split"] == "train"]
            test = [r for r, p in selected if p["split"] == "heldout"]
            merged = old_train + train
            if len({r["id"] for r in merged + test + development}) != len(merged + test + development):
                raise ValueError("duplicate merged/split id")
            cache = {}
            counts = {key: prior.stats(records, renderer, cache) for key, records in
                      {"prior_merged": old_train, "new_train": train, "merged": merged,
                       "heldout": test, "development": development}.items()}
            counts["accepted_original"] = old["languages"][lang]["counts"]["original"]
            counts["previous_additions"] = old["languages"][lang]["counts"]["new_train"]
            path = f"inputs/dfm12-identity-xl-full-bp-{lang}/train-00000.jsonl.gz"
            base.write_rows(temp / path, merged)
            base.write_rows(temp / f"curated/{lang}/train.jsonl.gz", train)
            base.write_rows(temp / f"heldout/{lang}/test.jsonl.gz", test)
            base.write_rows(temp / f"development/{lang}/previous-heldout.jsonl.gz", development)
            for split in prior.EXPECTED:
                (temp / f"review/{lang}-{split}.md").write_text(prior.readable(
                    [(r, p) for r, p in selected if p["split"] == split]))
            manifest["languages"][lang] = {"input": path, "counts": counts}
            all_provenance.extend(dict(old_provenance[r["id"]], split="train", lineage="unchanged_v2_train",
                                       inherited_manifest_sha256=PREVIOUS_SHA) for r in old_train)
            all_provenance.extend(dict(old_provenance[r["id"]], split="development", lineage="v2_heldout_now_development",
                                       inherited_manifest_sha256=PREVIOUS_SHA) for r in development)
            all_provenance.extend(dict(p, id=r["id"], language=lang, record_sha256=digest(r), render=cache[r["id"]])
                                  for r, p in selected)
        base.write_rows(temp / "metadata/provenance.jsonl.gz", all_provenance)
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
    if prior.verify(previous)["manifest_sha256"] != PREVIOUS_SHA:
        raise ValueError("previous source drift")
    compiled = compile_spec(root / "metadata/identity_repair_expansion.yaml")
    inherited, _ = check_lineage(previous, compiled)
    for lang in base.LANGUAGES:
        train = [r for r, p in compiled if r["language"] == lang and p["split"] == "train"]
        test = [r for r, p in compiled if r["language"] == lang and p["split"] == "heldout"]
        old_train, dev = inherited[lang]
        expected = {manifest["languages"][lang]["input"]: old_train + train,
                    f"curated/{lang}/train.jsonl.gz": train, f"heldout/{lang}/test.jsonl.gz": test,
                    f"development/{lang}/previous-heldout.jsonl.gz": dev}
        for name, records in expected.items():
            if list(rows(root / name)) != records:
                raise ValueError("reconstruction/split mismatch: " + name)
    return {"valid": True, "manifest_sha256": file_hash(root / "manifest.json")}


def mixture(root, tokenized, output, replay=ROOT / "data/sampled_dfm11"):
    """Use the unchanged adaptation builder, with a v3-specific lineage companion."""
    from . import build_identity_adaptation as adaptation
    root, tokenized, output = Path(root), Path(tokenized), Path(output)
    if output.exists():
        raise FileExistsError(output)
    verified = verify(root)
    manifest = load(root / "manifest.json")
    completion = load(tokenized / "completion.json")
    if completion["files"] != 2 or completion["skipped_rows_this_run"] != 0:
        raise ValueError("unexpected tokenization inputs/skips")
    expected_dirs = {f"dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz" for lang in base.LANGUAGES}
    if {p.name for p in tokenized.iterdir() if p.is_dir()} != expected_dirs:
        raise ValueError("unexpected tokenized directory")
    for lang in base.LANGUAGES:
        path = tokenized / f"dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz"
        a = adaptation.indices(path)
        count = manifest["languages"][lang]["counts"]["merged"]
        if (len(a["inst_len"]) != count["assistant_targets"]
                or int(a["inst_len"].sum() + a["resp_len"].sum()) != count["rendered_tokens"]):
            raise ValueError("tokenized identity does not match merged v3")
    info = load(tokenized / "tokenizer_info.json")
    for field, pin in (("tokenizer_path", "tokenizer"), ("chat_template_path", "template")):
        if file_hash(info[field]) != manifest[pin]["sha256"]:
            raise ValueError("tokenizer/template mismatch")
    receipt = adaptation.build(Path(replay), tokenized, output, steps=1000, seed=20260928,
                               start_step=2879261, start_checkpoint="step_2879261", data_epoch=12,
                               identity_manifest=root / "manifest.json")
    companion = {"schema": "dfm12-identity-v3-mixture-lineage-v1", "identity_manifest": str((root / "manifest.json").resolve()),
                 "identity_manifest_sha256": verified["manifest_sha256"],
                 "build_receipt_sha256": file_hash(output / "build-receipt.json"),
                 "metadata_sha256": file_hash(output / "metadata.json"),
                 "tokenization_completion": base.descriptor(tokenized / "completion.json"),
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
    p.add_argument("--assessment", type=Path, default=ASSESSMENT)
    p.add_argument("--metadata", type=Path, default=ROOT / "data/sampled_dfm11/metadata.json")
    sub.add_parser("verify").add_argument("--root", type=Path, required=True)
    p = sub.add_parser("mixture")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--tokenized", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--replay", type=Path, default=ROOT / "data/sampled_dfm11")
    args = vars(parser.parse_args())
    command = args.pop("command")
    print(json.dumps({"build": build, "verify": verify, "mixture": mixture}[command](**args), indent=2))


if __name__ == "__main__":
    main()
