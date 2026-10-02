"""CPU-only 95/5 replay from the parent's final packed corrective SFT."""
import argparse
from pathlib import Path
import json

import numpy as np

from . import build_identity_adaptation as shared
from .io import file_hash, load, write_json

START = 2887261
STEPS = 10000
GBS = 262144
IDENTITY_BUDGET = 131072000


def validate_final(ready_path):
    ready = load(ready_path)
    if ready.get("final_review_complete") is not True or ready.get("reviewed_stochastic_turns") != 560:
        raise ValueError("Require parent's complete 560-turn final-data receipt, not an earlier subset")
    root = Path(ready["packed_root"]).resolve()
    if file_hash(root / "manifest.json") != ready["packed_manifest_sha256"]:
        raise ValueError("Final packed manifest drift")
    manifest = load(root / "manifest.json")
    if manifest.get("final_only_loss") is not True or manifest.get("repeat") != 1:
        raise ValueError("Require final-answer-only parent packer output")
    source = Path(manifest["source"])
    if file_hash(source / "manifest.json") != manifest["source_manifest_sha256"]:
        raise ValueError("Reviewed source manifest drift")
    source_manifest = load(source / "manifest.json")
    if (source_manifest.get("source_mode") != "EMA_ONLY"
            or source_manifest.get("review_complete") is not True
            or source_manifest.get("prior_assistant_loss") is not False):
        raise ValueError("Invalid reviewed source/masking")
    for split in ("train", "validation"):
        for relative, sha in manifest["splits"][split]["files"].items():
            path = (root / split / relative).resolve()
            if not path.is_relative_to(root / split) or file_hash(path) != sha:
                raise ValueError("Packed file drift")
    # Verify every packed training span against the exact final-only source labels.
    from scripts.pack_identity_preference_sft import validate_row
    source_path = source / "chosen-sft-tokenized/train.jsonl"
    if file_hash(source_path) != source_manifest["files"]["chosen-sft-tokenized/train.jsonl"]:
        raise ValueError("Source train token drift")
    records = [json.loads(line) for line in source_path.read_text().splitlines() if line.strip()]
    arrays = shared.indices(root / "train/epoch_0")
    tokens = np.load(root / "train/tokens.npy", mmap_mode="r")
    metadata = load(root / "train/metadata.json")
    if len(records) != len(arrays["inst_len"]):
        raise ValueError("Packed row count mismatch")
    for i, row in enumerate(records):
        boundary = validate_row(row, "train", metadata["tokenizer_info"]["vocab_size"], metadata["max_seq_len"] - 1)
        inst, resp = (tokens[int(arrays[k + "_start"][i]):int(arrays[k + "_start"][i] + arrays[k + "_len"][i])].tolist()
                      for k in ("inst", "resp"))
        if inst + resp != row["input_ids"] or len(inst) != boundary:
            raise ValueError("Packed final-only span mismatch")
    return root, manifest


def build(ready, output, base=Path("data/sampled_dfm11"), gas=8, seed=20261001):
    ready, output, base = Path(ready).resolve(), Path(output).resolve(), Path(base).resolve()
    packed, manifest = validate_final(ready)
    if output.exists():
        raise FileExistsError(output)
    if gas not in (8, 16):
        raise ValueError("Corrective memory candidates use GAS 8 or 16")
    metadata = load(base / "metadata.json")
    shared.check_tokenizer(metadata["tokenizer_info"], load(packed / "train/metadata.json")["tokenizer_info"])
    rng = np.random.default_rng(seed)
    sources = []
    for name, root, budget, repeat in (("DFM11", base, STEPS * GBS - IDENTITY_BUDGET, False),
                                        ("identity-corrective", packed / "train", IDENTITY_BUDGET, True)):
        arrays = shared.indices(root / "epoch_0")
        info = load(root / "metadata.json")
        selected, total = shared.select_rows(arrays, budget, rng, repeat,
                                             info["total_length"] / len(arrays["inst_len"]))
        lengths = arrays["inst_len"][selected] + arrays["resp_len"][selected]
        if np.any(lengths > metadata["max_seq_len"]) or np.any(lengths < 2):
            raise ValueError("Invalid sequence length; no clipping allowed")
        sources.append(dict(name=name, path=str(root), arrays=arrays, selected=selected,
                            rendered_tokens=total, tokens=np.load(root / "tokens.npy", mmap_mode="r")))
    output.mkdir(parents=True)
    for source in sources:
        np.save(output / (source["name"] + "-source-rows.npy"), source["selected"])
    arrays, labels, stored = shared.compact_copy(sources, output, rng)
    packing = shared.packing_report(arrays, labels, STEPS, GBS, gas, 8)
    epoch = output / "epoch_0"
    epoch.mkdir()
    for key, values in arrays.items():
        np.save(epoch / (key + ".npy"), values)
    np.save(output / "source-labels.npy", labels)
    (output / "epoch_15").symlink_to("epoch_0", target_is_directory=True)
    total = sum(s["rendered_tokens"] for s in sources)
    metadata["total_length"] = total
    write_json(output / "metadata.json", metadata)
    responses = {}
    for scope, end in (("prepared", len(labels)), ("at_stop", packing["row_end_at_stop"])):
        counts = {s["name"]: int(arrays["resp_len"][:end][labels[:end] == i].sum()) for i, s in enumerate(sources)}
        responses[scope] = dict(response_tokens=counts, identity_response_fraction=counts["identity-corrective"] / sum(counts.values()))
    repetitions = np.bincount(sources[1]["selected"], minlength=len(sources[1]["arrays"]["inst_len"]))
    receipt = dict(schema="dfm12-corrective-mixture-v1", steps=STEPS, global_batch=GBS, gas=gas, world_size=8,
                   seed=seed, identity_budget=IDENTITY_BUDGET, rendered_tokens=total,
                   identity_fraction=sources[1]["rendered_tokens"] / total, stored_tokens=stored,
                   packing=packing, response_supervision=responses,
                   identity_repetitions=dict(min=int(repetitions.min()), max=int(repetitions.max())),
                   sources=[dict(name=s["name"], path=s["path"], sampled_rows=len(s["selected"]),
                                 unique_rows=len(s["unique"]), rendered_tokens=s["rendered_tokens"],
                                 unique_response_tokens=int(s["arrays"]["resp_len"][s["unique"]].sum())) for s in sources],
                   **shared.continuation_contract(START, STEPS, f"step_{START}", 15),
                   parent_ready_path=str(ready), parent_ready_sha256=file_hash(ready),
                   packed_manifest=str(packed / "manifest.json"), packed_manifest_sha256=file_hash(packed / "manifest.json"),
                   builder_sha256=file_hash(Path(__file__)), helper_sha256=file_hash(Path(shared.__file__)),
                   data_config=dict(path=str(output), target_only=True), training_launched=False,
                   heldout_and_validation_excluded=True)
    receipt["output_files"] = {str(p.relative_to(output)): file_hash(p) for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "build-receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path("data/sampled_dfm11"))
    parser.add_argument("--gas", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261001)
    print(json.dumps(build(**vars(parser.parse_args())), indent=2))
