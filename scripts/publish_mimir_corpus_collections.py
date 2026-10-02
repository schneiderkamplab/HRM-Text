#!/usr/bin/env python3
"""Publish reviewed Mimir corpus collection manifests without uploading data."""
import argparse
import json
from pathlib import Path

from huggingface_hub import HfApi


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    api = HfApi()
    for entry in manifest["collections"]:
        ids = sorted(set(entry["datasets"]))
        print(entry["title"], len(ids), flush=True)
        if not args.publish:
            continue
        collection = api.create_collection(
            entry["title"], namespace="schneiderkamplab",
            description=entry["description"][:150], private=False, exists_ok=True,
        )
        entry["url"] = collection.url
        entry["slug"] = collection.slug
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        present = {item.item_id for item in collection.items}
        for repo in ids:
            if repo not in present:
                api.add_collection_item(collection.slug, repo, "dataset", exists_ok=True)
                print("added", repo, flush=True)
        actual = {item.item_id for item in api.get_collection(collection.slug).items}
        if actual != set(ids):
            raise RuntimeError(f"Membership mismatch: missing={set(ids)-actual}, extra={actual-set(ids)}")
        entry["verified_count"] = len(actual)
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
        print(collection.url, flush=True)


if __name__ == "__main__":
    main()
