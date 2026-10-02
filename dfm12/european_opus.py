"""Reuse corpus-version reviews across the additional European language mesh."""
import argparse
from pathlib import Path
import time

from . import opus
from .european_expansion import ROOT
from .io import load, lock, write_json
from .opus_decisions import APPROVED, MINED, LOW_PRIORITY
from .prepare import Renderer


def review(root):
    baseline = load("data/dfm12/opus/inventory.json")
    evidence = {}
    for item in baseline["pairs"].values():
        for entry in item["corpora"]:
            key = (entry["corpus"], entry["version"])
            if key in APPROVED and entry.get("status") == "approved" and entry.get("license") == APPROVED[key]:
                evidence[key] = entry
    with lock(root / "opus/.inventory.lock"):
        inventory = load(root / "opus/inventory.json")
        decisions = []
        for pair, item in inventory["pairs"].items():
            for entry in item["corpora"]:
                key = (entry["corpus"], entry["version"])
                if entry["corpus"] in MINED | LOW_PRIORITY:
                    entry.update(status="excluded_quality", review_reason="Existing DFM12 web-mined/fragmentary corpus exclusions")
                elif key in evidence:
                    old = evidence[key]
                    entry.update(status="approved", license=old["license"], license_evidence=old["license_evidence"],
                        quality_review="Reuse named institutional corpus-version review; independent alignment/language audit required")
                decisions.append(dict(pair=pair, corpus=entry["corpus"], version=entry["version"],
                                      status=entry.get("status"), license=entry.get("license")))
        write_json(root / "opus/inventory.json", inventory)
        write_json(root / "opus/review-decisions.json", decisions)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    cfg = load(args.root / "config.json")
    # Discovery is resumable. Wait for its single writer rather than racing it.
    while True:
        try:
            opus.discover(args.root, cfg)
            break
        except BlockingIOError:
            time.sleep(30)
    review(args.root)
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
    with lock(args.root / ".cpu-translations.lock"):
        inventory = load(args.root / "opus/inventory.json")
        for pair, item in inventory["pairs"].items():
            if not any(e.get("status") == "approved" for e in item["corpora"]):
                write_json(args.root / "opus/progress" / (pair + ".json"), dict(state="no_approved_direct_supply", discovery_error=item.get("error")))
                continue
            try:
                path = args.root / "candidates" / ("opus-" + pair) / "receipt.json"
                if path.exists():
                    from .io import file_hash
                    result = load(path)
                    if file_hash(path.parent / "candidates.jsonl") != result["sha256"]:
                        raise ValueError("Candidate checksum mismatch")
                else:
                    result = opus.prepare_pair(args.root, pair, cfg, renderer)
                write_json(args.root / "opus/progress" / (pair + ".json"), dict(state="candidates_ready", counts=result["counts"], audit="pending"))
                print(pair, result["counts"], flush=True)
            except Exception as exc:
                write_json(args.root / "opus/progress" / (pair + ".json"), dict(state="blocked", error=f"{type(exc).__name__}: {exc}"))
                print(pair, repr(exc), flush=True)


if __name__ == "__main__":
    main()
