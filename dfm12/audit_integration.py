"""Read-only registration of reconciled reordering outputs into audit readiness."""
import argparse
from pathlib import Path

from .io import file_hash, load, write_json


def register(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    receipt, verification = load(root / "receipt.json"), load(root / "verification.json")
    if (verification["receipt_sha256"] != file_hash(root / "receipt.json")
            or not verification["input_hashes_unchanged"] or not verification["source_replay"]
            or verification["counts"] != receipt["counts"] or receipt["accepted"] != 0
            or receipt["audit_status"] != "unaudited"):
        raise ValueError("Reordering completion verification mismatch")
    components = []
    for key, sha in sorted(receipt["output_sha256"].items()):
        path = root / "candidates" / (key + ".jsonl")
        if file_hash(path) != sha:
            raise ValueError("Reordering candidate checksum mismatch")
        component = "reordering-integrated-" + key.replace("/", "-")
        wrapper = output / "receipts" / (component + ".json")
        write_json(wrapper, {"sha256": sha, "counts": {"candidates": receipt["counts"][key]},
                            "accepted": False, "audit_status": "unaudited",
                            "receipt": str(root / "receipt.json")})
        components.append({"component": component, "family": "transformation", "path": str(path),
                           "receipt": str(wrapper), "sha256": sha,
                           "evidence": [str(root / name) for name in ("receipt.json", "verification.json")]})
    manifest = {"version": 1, "status": "complete_unaudited", "components": components,
                "supersedes": [], "resolves": ["reordering-integration"],
                "legacy_policy": "Cross-screen gates exclude dynaword-nl paragraph-reordering; retain other tasks"}
    write_json(output / "integration.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--reordering-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = register(args.reordering_root, args.output)
    print(f"Registered {len(result['components'])} unaudited reordering components")
