"""Verify a prepared identity mixture and record supervised-response shares."""
import argparse
import json
from pathlib import Path

import numpy as np

from . import build_identity_adaptation as adaptation
from .io import file_hash, load, write_json


def response_summary(lengths, labels, stop):
    if len(lengths) != len(labels) or not 0 < stop <= len(labels):
        raise ValueError("invalid response boundary")
    if set(np.unique(labels)) != {0, 1, 2} or np.any(lengths < 1):
        raise ValueError("invalid source labels/response lengths")
    result = {}
    for name, end in (("prepared", len(labels)), ("at_stop", stop)):
        totals = {str(label): int(lengths[:end][labels[:end] == label].sum()) for label in (0, 1, 2)}
        result[name] = {"rows": end, "response_tokens_by_label": totals,
                        "identity_response_fraction": (totals["1"] + totals["2"]) / sum(totals.values())}
    return result


def verify_and_write(output):
    output = Path(output).resolve()
    destination = output / "identity-lineage.json"
    if destination.exists():
        raise FileExistsError(destination)
    receipt = load(output / "build-receipt.json")
    manifest_path = Path(receipt["identity_manifest"])
    manifest = adaptation.verify_identity_manifest(manifest_path)
    if file_hash(manifest_path) != receipt["identity_manifest_sha256"]:
        raise ValueError("identity source drift")
    for relative, expected in receipt["output_files"].items():
        path = (output / relative).resolve()
        if not path.is_relative_to(output) or file_hash(path) != expected:
            raise ValueError("mixture output drift")
    for path, expected in receipt["tokenized_source_files"].items():
        if file_hash(path) != expected:
            raise ValueError("tokenized source drift")
    if file_hash(Path(adaptation.__file__)) != receipt["builder_sha256"]:
        raise ValueError("adaptation builder drift")
    alias = output / f"epoch_{receipt['data_epoch_index']}"
    if alias.resolve() != (output / "epoch_0").resolve():
        raise ValueError("incorrect epoch alias")
    arrays = adaptation.indices(alias)
    labels = np.load(output / "source-labels.npy", mmap_mode="r")
    packing = adaptation.packing_report(arrays, labels, receipt["steps"], receipt["global_batch"],
                                        receipt["packing"]["gas"], receipt["packing"]["world_size"])
    if packing != receipt["packing"]:
        raise ValueError("packing reconstruction mismatch")
    repetitions = {}
    for language, source in zip(("da", "en"), receipt["sources"][1:]):
        a = adaptation.indices(Path(source["path"]))
        expected = manifest["languages"][language]["counts"]["merged"]
        if (len(a["resp_len"]) != expected["assistant_targets"]
                or int(a["resp_len"].sum()) != expected["response_tokens"]
                or int(a["inst_len"].sum() + a["resp_len"].sum()) != expected["rendered_tokens"]):
            raise ValueError("tokenized source accounting mismatch")
        selected = np.load(output / f"identity-{language}-source-rows.npy")
        counts = np.bincount(selected, minlength=len(a["resp_len"]))
        repetitions[language] = {"min": int(counts.min()), "max": int(counts.max()),
                                 "unique_targets": int(np.count_nonzero(counts)), "sampled_targets": len(selected)}
    result = {"schema": "dfm12-identity-mixture-verification-v1",
              "identity_manifest": str(manifest_path), "identity_manifest_sha256": file_hash(manifest_path),
              "build_receipt_sha256": file_hash(output / "build-receipt.json"),
              "metadata_sha256": file_hash(output / "metadata.json"),
              "verifier_sha256": file_hash(Path(__file__)), "packing_reverified": packing,
              "response_supervision": response_summary(arrays["resp_len"], labels, packing["row_end_at_stop"]),
              "identity_repetitions": repetitions, "training_launched": False,
              "heldout_and_development_excluded": True}
    write_json(destination, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(verify_and_write(**vars(parser.parse_args())), indent=2))
