"""Verify isolated DaLA candidates and token arrays without editing audit readiness."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from .dala_integrate import LANGUAGES, TASKS, conversations
from .io import file_hash, load, rows, write_json


def verify(root, languages=LANGUAGES):
    import jinja2
    import numpy as np
    from tokenizers import Tokenizer
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    root = Path(root).resolve()
    integration = load(root / "integration.json")
    inputs = load(root / "inputs.json")
    if (integration["status"] != "complete_unaudited" or
            integration["producer_finalized"] != inputs.get("producer_finalized", False)):
        raise ValueError("Not a completed local unaudited integration")
    if {e["component"] for e in integration["components"]} != {f"dala-{l}-{t}" for l in languages for t in TASKS}:
        raise ValueError("Unexpected task components for authorized language scope")
    inputs = load(root / "inputs.json")
    exclusion = inputs["late_exclusions_receipt"]
    if file_hash(exclusion["path"]) != exclusion["sha256"]:
        raise ValueError("Producer late exclusions changed; new local screening required")
    assets = load(root / "tokenizer.json")
    info = assets["tokenizer_info"]
    if (file_hash(info["tokenizer_path"]) != assets["tokenizer_sha256"] or
            file_hash(info["chat_template_path"]) != assets["chat_template_sha256"]):
        raise ValueError("Raw tokenizer/template changed")
    tokenizer = Tokenizer.from_file(info["tokenizer_path"])
    template = jinja2.Environment().from_string(Path(info["chat_template_path"]).read_text())
    counts, tokens, replayed = Counter(), Counter(), 0
    hashes = {(lang, task): hashlib.sha256() for lang in languages for task in TASKS}
    for shard in load(root / "screening.json")["shards"]:
        lang, key = shard["language"], Path(shard["path"]).stem
        if file_hash(shard["path"]) != shard["sha256"]:
            raise ValueError("Screened pair shard changed")
        source = inputs["sources"][lang]
        expected = {r["id"]: r for p in rows(shard["path"])
                    for r in conversations(p, source["selected_manifest"]["prompts"], source["selected_receipt"]["sha256"])}
        receipt = load(root / "shard_receipts" / lang / f"{key}.json")
        pair_counts = Counter()
        for task in TASKS:
            component = f"dala-{lang}-{task}"
            path = root / "candidate_shards" / component / f"{key}.jsonl"
            if file_hash(path) != receipt["outputs"][str(path)]:
                raise ValueError("Candidate shard changed")
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                    hashes[lang, task].update(block)
            directory = root / "tokenized_unaudited" / component / key
            arrays = {name: np.load(directory / f"{name}.npy", mmap_mode="r")
                      for name in ("tokens", "inst_start", "inst_len", "resp_start", "resp_len")}
            for name, array in arrays.items():
                if array.dtype != (np.uint32 if name == "tokens" else np.uint64):
                    raise ValueError("Wrong token-array dtype")
                if file_hash(directory / f"{name}.npy") != receipt["outputs"][str(directory / f"{name}.npy")]:
                    raise ValueError("Token array changed")
            n = len(arrays["inst_start"])
            if any(len(arrays[name]) != n for name in ("inst_len", "resp_start", "resp_len")):
                raise ValueError("Mismatched array lengths")
            if (np.any(arrays["inst_start"] + arrays["inst_len"] != arrays["resp_start"]) or
                    np.any(arrays["resp_start"] + arrays["resp_len"] > len(arrays["tokens"]))):
                raise ValueError("Token-array bounds mismatch")
            if n and (arrays["inst_start"][0] != 0 or
                      arrays["resp_start"][-1] + arrays["resp_len"][-1] != len(arrays["tokens"]) or
                      np.any(arrays["inst_start"][1:] != arrays["resp_start"][:-1] + arrays["resp_len"][:-1])):
                raise ValueError("Token storage is not contiguous")
            actual_n = 0
            for i, row in enumerate(rows(path)):
                rendered = row.pop("rendered_tokens")
                if row != expected.pop(row["id"]):
                    raise ValueError("Candidate differs from canonical pair/task view")
                if rendered != int(arrays["inst_len"][i] + arrays["resp_len"][i]) or rendered > 4096:
                    raise ValueError("Rendered token length mismatch")
                if i < 2:
                    example, = examples_from_messages(row["messages"], [])
                    encoded = tokenize_example(tokenizer, template, example, False)
                    for prefix, ids in zip(("inst", "resp"), encoded):
                        a = int(arrays[prefix + "_start"][i])
                        b = a + int(arrays[prefix + "_len"][i])
                        if arrays["tokens"][a:b].tolist() != ids:
                            raise ValueError("Raw Gemma4 token replay mismatch")
                    replayed += 1
                pair_counts[row["provenance"]["pair_id"]] += 1
                actual_n += 1
            if actual_n != n or n != receipt["counts"]["converted_pairs"] * 2:
                raise ValueError("Candidate/token row count mismatch")
            counts[component] += n
            tokens[component] += len(arrays["tokens"])
        if any(n != 4 for n in pair_counts.values()) or len(pair_counts) != receipt["counts"]["converted_pairs"]:
            raise ValueError("Pair views not balanced/complete")
        print("VERIFIED_SHARD", lang, key, flush=True)
    for entry in integration["components"]:
        component = entry["component"]
        receipt = load(entry["receipt"])
        _, lang, task = component.split("-", 2)
        sha = file_hash(entry["path"])
        if sha != entry["sha256"] or sha != receipt["sha256"] or sha != hashes[lang, task].hexdigest():
            raise ValueError("Combined candidates differ from verified shards")
        completion = load(receipt["tokenization"])
        if receipt["counts"]["candidates"] != counts[component] or completion["rows"] != counts[component] or completion["tokens"] != tokens[component]:
            raise ValueError("Completion count mismatch")
    for entry in integration["components"]:
        proof = str(root / "verification.json")
        if proof not in entry["evidence"]:
            entry["evidence"].append(proof)
    write_json(root / "integration.json", integration)
    report = {"status": "verified_unaudited", "integration_sha256": file_hash(root / "integration.json"),
              "counts": dict(counts), "tokens": dict(tokens), "raw_gemma_replayed_rows": replayed,
              "canonical_task_replay": "all candidate rows", "producer_finalized": integration["producer_finalized"],
              "latest_exclusions_unchanged": True}
    write_json(root / "verification.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/dala-nb-nn-fo-20260924-v1"))
    args = parser.parse_args()
    print(verify(args.root))
