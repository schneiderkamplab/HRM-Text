#!/usr/bin/env python3
"""Filter export datasets using every audit JSONL under audit* roots."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "export"
DATASETS = [
    "common-pile-denoising",
    "common-pile-paragraph-reordering",
    "common-pile-prefix-continuation",
    "common-pile-span-filling",
    "danish-dynaword-denoising",
    "danish-dynaword-paragraph-reordering",
    "danish-dynaword-prefix-continuation",
    "danish-dynaword-span-filling",
]


def main() -> None:
    for dataset in DATASETS:
        folder = EXPORT / dataset
        audits = sorted(p for p in folder.glob("audit*/audit.jsonl") if p.is_file() and p.stat().st_size)
        if not audits:
            print(f"{dataset}: no audit files, skipped")
            continue
        cmd = [
            "python",
            "recreate_dataset.py",
            "filter",
            "--output-root",
            "audited",
            "--force",
        ]
        for audit in audits:
            cmd.extend(["--audit", str(audit.relative_to(folder))])
        print(f"{dataset}: filtering with {len(audits)} audit file(s)")
        subprocess.run(cmd, cwd=folder, check=True)


if __name__ == "__main__":
    main()
