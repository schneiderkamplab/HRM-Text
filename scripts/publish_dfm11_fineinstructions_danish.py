#!/usr/bin/env python3
"""Publish and verify Danish FineInstructions datasets and helper models."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, get_token


ROOT = Path(__file__).resolve().parents[1]
ORG = "schneiderkamplab"
DATASETS = {
    "dfm11-fineinstructions-da": ROOT / "exports_dfm11/dfm11-fineinstructions-da",
    "dfm11-danish-query-templatizer-training": ROOT
    / "exports_dfm11/dfm11-danish-query-templatizer-training",
    "dfm11-danish-template-instantiator-training": ROOT
    / "exports_dfm11/dfm11-danish-template-instantiator-training",
}
MODELS = {
    "dfm11-danish-query-templatizer-qwen3.5-2b": ROOT
    / "data/fineinstructions/dfm11-danish-distillation/models/danish-query-templatizer-qwen3.5-2b-v2/final",
    "dfm11-danish-template-instantiator-qwen3.5-4b": ROOT
    / "data/fineinstructions/dfm11-danish-distillation/models/danish-template-instantiator-qwen3.5-4b-v2-fsdp1-ac-native-bf16-bs2/final",
}
DEFAULT_RECEIPT = ROOT / "logs/fineinstructions/dfm11-danish-500k/publication-receipt.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    return parser.parse_args()


def local_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and ".cache" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def publish_one(
    api: HfApi, name: str, root: Path, repo_type: str, workers: int
) -> dict[str, object]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    repo_id = f"{ORG}/{name}"
    api.create_repo(repo_id=repo_id, repo_type=repo_type, exist_ok=True)
    api.upload_large_folder(
        repo_id=repo_id,
        repo_type=repo_type,
        folder_path=str(root),
        num_workers=max(1, workers),
        ignore_patterns=[".cache/**", "__pycache__/**", "*.pyc"],
        print_report_every=60,
    )
    expected = local_files(root)
    remote = set(api.list_repo_files(repo_id=repo_id, repo_type=repo_type))
    missing = sorted(expected - remote)
    if missing:
        raise RuntimeError(f"{repo_id}: missing remote files: {missing[:10]}")
    info = api.repo_info(repo_id=repo_id, repo_type=repo_type)
    return {
        "repo_id": repo_id,
        "repo_type": repo_type,
        "revision": info.sha,
        "local_files": len(expected),
        "remote_files": len(remote),
        "verified": True,
    }


def main() -> None:
    args = parse_args()
    token = os.environ.get("HF_TOKEN") or get_token()
    if not token:
        raise SystemExit("No Hugging Face token found in HF_TOKEN or the local token cache")
    api = HfApi(token=token)
    published: dict[str, dict[str, object]] = {}
    for name, root in DATASETS.items():
        print(f"Publishing dataset {ORG}/{name}", flush=True)
        published[name] = publish_one(api, name, root, "dataset", args.workers)
    for name, root in MODELS.items():
        print(f"Publishing model {ORG}/{name}", flush=True)
        published[name] = publish_one(api, name, root, "model", args.workers)
    receipt = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": published,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.receipt.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
