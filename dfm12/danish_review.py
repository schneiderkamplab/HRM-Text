"""Capture pinned constituent provenance and conservative overlap decisions."""
import argparse
from pathlib import Path

from .io import atomic, file_hash, load, write_json


def main():
    import requests
    from huggingface_hub import get_token
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/danish-increments"))
    args = parser.parse_args()
    source = load("data/dfm12/sources.lock.json")["sources"]["dyna-instruct-da-increments"]
    session = requests.Session()
    token = get_token()
    if token:
        session.headers["Authorization"] = "Bearer " + token
    paths = ["README.md"]
    for relative in source["files"]:
        paths.extend(str(Path(relative).parent / name) for name in ("datasheet.md", "create.py"))
    evidence = {}
    for relative in paths:
        url = f"https://huggingface.co/datasets/{source['repo']}/resolve/{source['revision']}/{relative}"
        response = session.get(url, timeout=60)
        entry = {"url": url, "http_status": response.status_code}
        if response.ok:
            path = args.root / "review-evidence" / relative
            with atomic(path) as handle:
                handle.write(response.text)
            entry["sha256"] = file_hash(path)
        evidence[relative] = entry
        print(relative, response.status_code, flush=True)
    write_json(args.root / "review-evidence.json", {
        "revision": source["revision"], "documents": evidence,
        "license_policy": "All DynaInstruct licenses owner-authorized on 2026-09-24; preserve notices",
        "decisions": {
            "when2call": "Exclude benchmark-derived llm_judge/mcq material; card names BFCL tool schemas",
            "ifbench-train": "Inherited train source, not automatically an eval split; require prompt-level held-out check before any future increment",
            "agentic-code-sft-mix-v1": "Inherited English NVIDIA mixture; any future additions need SWE repository/issue overlap and native tool-format review",
            "apertus-sft-mixture": "Inherited multilingual mixture; no blanket Danish label or blanket held-out clearance",
            "all": "No additions admitted: identical pinned inherited reservoirs. Not a full held-out decontamination claim",
        }})


if __name__ == "__main__":
    main()
