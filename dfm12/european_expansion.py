"""Incremental CPU staging for the owner-approved second DFM12 language wave.

This does not alter the frozen first-wave catalog, training inputs, or sampling.
Candidates require the existing independent audit before accepted-only export.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
import traceback

from . import catalog, opus, prepare
from .io import digest, file_hash, load, lock, write_json

ROOT = Path("data/dfm12/european-expansion-20260926")
NEW = dict(de="German", fr="French", es="Spanish", it="Italian", cs="Czech",
           pt_pt="European Portuguese (pt-PT)", fi="Finnish", et="Estonian",
           ca="Catalan", el="Greek", ro="Romanian", uk="Ukrainian")


def configuration():
    previous = catalog.config()
    cfg = {k: previous[k] for k in ("seed", "model", "max_seq_len", "tasks",
            "transform_fraction", "english_translation_fraction", "other_translation_fraction")}
    cfg.update(languages=dict(previous["languages"], **NEW), new_languages=list(NEW),
               english_pairs=list(NEW), opus_codes={"pt_pt": "pt"}, sources={})
    cfg["opus_pairs"] = [list(p) for p in combinations(sorted(cfg["languages"]), 2)
                         if set(p) & set(NEW)]
    def add(name, repo, patterns, **kwargs):
        cfg["sources"][name] = dict(repo=repo, patterns=patterns, kind="instruction", **kwargs)
    for lang in ("nl", "pl", "de", "fr", "es", "it", "cs", "el", "ro", "uk"):
        add("eu-instruct-" + lang, "openeurollm/EU-Instruct-Synthetic",
            [f"{lang}/train.parquet"], language=lang)
    for lang in ("de", "fr", "es", "it", "cs", "fi", "el", "ro", "uk"):
        add("dolci-translated-" + lang, "openeurollm/Dolci-Instruct-SFT-translated",
            [f"{lang}/shard*.parquet"], language=lang)
    add("aya-human-train", "CohereLabs/aya_dataset", ["data/train-*.parquet"],
        languages=[l for l in cfg["languages"] if l != "pt_pt"], language_field="language_code",
        adapter="input_target", input_field="inputs", target_field="targets")
    add("dolly-nl-train", "BramVanroy/dolly-15k-dutch", ["data/train_sft-*.parquet"], language="nl")
    add("smoltalk2-chat-en", "HuggingFaceTB/smoltalk2",
        ["SFT/smoltalk_smollm3_everyday_conversations_no_think-*.parquet",
         "SFT/smoltalk_smollm3_systemchats_30k_no_think-*.parquet"], language="en")
    add("euroblocks", "utter-project/EuroBlocks-SFT-2512", ["data/train-*.parquet"],
        languages=[l for l in cfg["languages"] if l not in {"nb", "nn", "pt_pt"}],
        language_aliases={v: k for k, v in cfg["languages"].items()})
    add("poro2-fi", "LumiOpen/poro2-instruction-collection", ["train.jsonl"],
        language="fi", language_field="lang")
    add("magpie-et", "tartuNLP/magpie-gemma-3-12b-it-100k-et", ["data/train-*.parquet"],
        language="et", adapter="input_target", input_field="instruction", target_field="response")
    add("alia-ca-es", "BSC-LT/ALIA-2606-SFT", ["data/train-*.parquet"], languages=["ca", "es"])
    add("amalia-persona", "amalia-llm/persona_general", ["persona_instruct_2shot.jsonl"], language="pt_pt")
    add("amalia-if", "amalia-llm/persona_instruction_following",
        ["if_output_pt_100k_verified_quality5.jsonl"], language="pt_pt")
    add("amalia-wikipedia", "amalia-llm/wikipedia_conversations",
        ["wikipedia_conversations_fix.jsonl"], language="pt_pt", adapter="conversation",
        conversation_field="conversation", role_field="from", content_field="value")
    add("amalia-summarize", "amalia-llm/smol_summarize_pt", ["smol_summarize_pt.jsonl"],
        language="pt_pt", adapter="conversation", conversation_field="conversations")
    add("trustllm-prompts", "AnnikaSimonsen/TrustLLM-reformulation-prompts",
        ["data/train-*.parquet"], languages=list(cfg["languages"]))
    cfg["sources"]["trustllm-prompts"]["kind"] = "prompts"
    for lang in NEW:
        if lang == "pt_pt":
            cfg["sources"]["text-pt_pt"] = dict(repo="amalia-llm/CorEGe-PT",
                patterns=["CorEGe-PT.parquet"], kind="documents", language=lang,
                document_equals={"pt.pt.auto": True},
                review="Require document-level rights and pt-PT confidence screening before transformations")
        else:
            cfg["sources"]["text-" + lang] = dict(repo="wikimedia/wikipedia",
                patterns=[f"20231101.{lang}/train-*.parquet"], kind="documents", language=lang)
    return cfg


def initialize(root):
    cfg = configuration()
    with lock(root / ".initialize.lock"):
        config_path = root / "config.json"
        if config_path.exists() and digest(load(config_path)) != digest(cfg):
            old = load(config_path)
            if ({k: v for k, v in old.items() if k != "sources"} !=
                {k: v for k, v in cfg.items() if k != "sources"} or
                any(cfg["sources"].get(k) != v for k, v in old["sources"].items())):
                raise ValueError("Existing frozen source/policy changed; refusing implicit replacement")
            # Only append new source registrations; never repin an existing source.
            extra = {k: v for k, v in cfg["sources"].items() if k not in old["sources"]}
            addition_root = root / "catalog-additions" / digest(extra)
            addition = catalog.resolve(addition_root, dict(cfg, sources=extra))
            with lock(root / ".catalog.lock"):
                prior = load(root / "sources.lock.json")
                write_json(root / "catalog-history" / (digest(old) + ".json"), prior)
                prior["sources"].update(addition["sources"])
                prior["config_hash"] = digest(cfg)
                write_json(root / "sources.lock.json", prior)
        write_json(config_path, cfg)
        catalog.resolve(root, cfg)
        baseline = load("data/dfm12/baselines.json")
        write_json(root / "baselines.json", baseline)
        write_json(root / "policy.json", dict(instructions_repeat=1,
            english_pair_token_cap=661329827, other_pair_token_cap=165332456,
            translation_basis="Per-epoch EN-DA both directions: 2645319308.5 tokens",
            final_sampling=False, dala="Owned by separate thread",
            audit_required=True, benchmark_and_inherited_dedup_required=True))
    return cfg


def process_source(root, name):
    root = Path(root)
    cfg = load(root / "config.json")
    destination = root / "progress" / (name + ".json")
    try:
        with lock(root / "workers" / (name + ".lock")):
            write_json(destination, dict(state="downloading", source=name))
            source = catalog.download(root, name)
            if source["kind"] == "prompts":
                from .trustllm import enqueue
                count = enqueue(root, cfg)
                result = dict(state="generation_queued", jobs=count)
            else:
                renderer = prepare.Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
                receipt_path = root / "candidates" / name / "receipt.json"
                candidate_path = receipt_path.parent / "candidates.jsonl"
                if receipt_path.exists():
                    receipt = load(receipt_path)
                    if receipt["source"] != source or file_hash(candidate_path) != receipt["sha256"]:
                        raise ValueError("Existing candidate receipt does not match pinned inputs")
                elif source["kind"] == "documents":
                    write_json(destination, dict(state="transforming", source=name))
                    receipt = prepare.prepare_transforms(root, name, load(root / "baselines.json"), cfg, renderer)
                else:
                    write_json(destination, dict(state="converting", source=name))
                    receipt = prepare.convert_source(root, name, renderer)
                # Materialize first; queue admission is an explicit separate stage.
                result = dict(state="candidates_ready", counts=receipt["counts"],
                              receipt=str(receipt_path), audit="pending", admitted=False)
            write_json(destination, result)
            return name, result
    except Exception as exc:
        traceback.print_exc()
        result = dict(state="blocked", error=f"{type(exc).__name__}: {exc}")
        write_json(destination, result)
        return name, result


def run(root, workers, only=None):
    initialize(root)
    inventory = load(root / "sources.lock.json")["sources"]
    names = only or list(inventory)
    if not set(names) <= set(inventory):
        raise ValueError("Unknown source name")
    with lock(root / ".cpu-campaign.lock"), ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(process_source, str(root), name) for name in names]
        for future in as_completed(futures):
            print(future.result(), flush=True)


def manifest(root):
    cfg = load(root / "config.json")
    components = []
    for path in sorted((root / "candidates").glob("*/receipt.json")):
        receipt = load(path)
        name = path.parent.name
        family = "translation" if name.startswith("opus-") else "transformation" if name.startswith("text-") else "instruction"
        components.append(dict(component=name, family=family, path=str((path.parent / "candidates.jsonl").resolve()),
            receipt=str(path.resolve()), sha256=receipt["sha256"], receipt_sha256=file_hash(path),
            counts=receipt["counts"], accepted=False))
    result = dict(version=1, status="complete_unaudited", components=components,
                  languages=cfg["languages"], accepted=False, benchmarks_clear=False,
                  full_inherited_coverage=False, final_sampling=False,
                  scope="Completed candidate components only; not completion of the expansion campaign")
    destination = root / "audit-manifests" / (digest(result) + ".json")
    write_json(destination, result)
    print(destination, flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["initialize", "cpu", "opus-discover", "opus-prepare", "queue-audits", "manifest", "status"])
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--source", action="append")
    args = p.parse_args()
    if not 1 <= args.workers <= 16:
        p.error("workers must be 1..16")
    if args.action == "initialize":
        initialize(args.root)
    elif args.action == "cpu":
        run(args.root, args.workers, args.source)
    elif args.action == "manifest":
        manifest(args.root)
    elif args.action == "status":
        import json
        progress = {p.stem: load(p) for p in (args.root / "progress").glob("*.json")}
        translation = {p.stem: load(p) for p in (args.root / "opus/progress").glob("*.json")}
        print(json.dumps(dict(sources=progress, opus_states=dict(Counter(v["state"] for v in translation.values())),
                              complete=False, note="Candidate preparation is not audit acceptance"), indent=2))
    elif args.action == "opus-discover":
        opus.discover(args.root, load(args.root / "config.json"))
    elif args.action == "opus-prepare":
        cfg = load(args.root / "config.json")
        renderer = prepare.Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
        with lock(args.root / ".cpu-translations.lock"):
            for pair in load(args.root / "opus" / "inventory.json")["pairs"]:
                try:
                    path = args.root / "candidates" / ("opus-" + pair) / "receipt.json"
                    if not path.exists():
                        opus.prepare_pair(args.root, pair, cfg, renderer)
                except ValueError as exc:
                    print(pair, exc, flush=True)
    else:
        if args.source:
            p.error("Audit preparation screens the complete ordered source set; --source is only for CPU conversion")
        from .european_screen import run as screen
        screen(args.root)


if __name__ == "__main__":
    main()
