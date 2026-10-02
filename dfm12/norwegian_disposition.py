"""Append-only final disposition of the pinned Norwegian variant omissions."""
import argparse
from collections import Counter
import os
from pathlib import Path

from .io import digest, file_hash, load, lock, rows, write_json
from .norwegian import REVISION, REPO, cpu_environment, verify_files, verify_upstream


def omission_reason(name, labels):
    if name == "reasoning-norwegian":
        return "unsupported_nb_nn_variant"
    if name == "nb-samtale-pairs":
        if set(labels) == {"nob", "nno"}:
            return "mixed_nb_nn_speaker_orthography"
        if labels not in (["nob"], ["nno"]):
            raise ValueError("unexpected_samtale_labels")
        return None
    if name == "magpie-qwen3-bokmaal" and labels == ["nob"]:
        return None
    raise ValueError("unexpected_constituent_or_labels")


def build(root):
    review_path = root / "license-review-20260924/review-receipt.json"
    review = load(review_path)
    evidence = load(root / "evidence-receipt.json")
    if evidence["source"]["revision"] != REVISION or evidence["source"]["repo"] != REPO:
        raise ValueError("source_pin_mismatch")
    verify_files(root, evidence)
    verify_files(root, {"files": review["reused_files"]})
    verify_files(review_path.parent, review)
    original = root / "preparation-receipt.json"
    if file_hash(original) != review["supersedes"]["sha256"]:
        raise ValueError("original_receipt_changed")
    upstream = {r["id"]: r for r in rows(root / "evidence/upstream/nb-samtale-pairs/conversations.jsonl")}
    omissions, counts, inputs, ids = [], Counter(), Counter(), set()
    for name in ("magpie-qwen3-bokmaal", "nb-samtale-pairs", "reasoning-norwegian"):
        path = f"downloads/data/{name}/{name}.parquet"
        for ordinal, row in enumerate(rows(root / path)):
            key = (name, row["id"])
            if key in ids or row["source"] != name:
                raise ValueError("duplicate_id_or_source_mismatch")
            ids.add(key)
            inputs[name] += 1
            if name == "nb-samtale-pairs":
                verify_upstream(row, name, upstream)
            reason = omission_reason(name, row["language"])
            if reason:
                counts[reason] += 1
                omissions.append({"source": name, "source_id": row["id"],
                                  "path": path, "ordinal_zero_based": ordinal,
                                  "row_sha256": digest(row), "observed_labels": row["language"],
                                  "decision": "omit", "reason": reason,
                                  "assigned_variant": None, "license_blocker": False})
    if dict(inputs) != {"magpie-qwen3-bokmaal": 1822, "nb-samtale-pairs": 4735, "reasoning-norwegian": 4496}:
        raise ValueError("input_counts_changed")
    if dict(counts) != {"mixed_nb_nn_speaker_orthography": 1245, "unsupported_nb_nn_variant": 4496}:
        raise ValueError("omission_counts_changed")
    if review["total_staged"] != 5307 or review["total_tokens"] != 2675108:
        raise ValueError("staging_counts_changed")
    if sum(inputs.values()) != review["total_staged"] + len(omissions) + 5:
        raise ValueError("row_accounting_mismatch")
    return {
        "schema_version": 1, "status": "complete_final_held_subset_disposition",
        "source_repo": REPO, "source_revision": REVISION,
        "accepted": False, "audit_status": "unaudited", "license_blocker": False,
        "policy": "Omit unsupported or mixed variants for this preparation; no inferred NB/NN assignment.",
        "supersedes": {"path": str(review_path), "sha256": file_hash(review_path),
                       "scope": "Reasoning variant hold becomes explicit omission; existing outputs unchanged."},
        "evidence_receipt_sha256": file_hash(root / "evidence-receipt.json"),
        "implementation_sha256": file_hash(Path(__file__)),
        "inputs": dict(inputs), "omission_counts": dict(counts), "omitted_rows": len(omissions),
        "preserved_staged_rows": 5307, "preserved_tokens": 2675108,
        "other_rejections": {"rendered_context_does_not_fit": 5},
        "newly_staged": 0, "remaining_held_rows": 0,
        "excluded_sources": ["NorQuAD", "FLEURS"],
        "benchmark_clearance": False, "quality_audit_complete": False,
        "verified_existing_output_files": len(review["reused_files"]),
        "preserved_outputs": review["reused_files"], "omissions": omissions,
    }


def run(root, validate=False):
    cpu_environment()
    target = root / "final-variant-disposition.json"
    with lock(root / ".run.lock"):
        if target.exists() and not validate:
            raise FileExistsError(target)
        result = build(root)
        if validate:
            if load(target) != result:
                raise ValueError("disposition_validation_mismatch")
        else:
            write_json(target, result)
    return {"validated": True, "pid": os.getpid(), "omitted_rows": result["omitted_rows"],
            "preserved_staged_rows": result["preserved_staged_rows"], "workers": 1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    print(run(args.root, args.validate))
