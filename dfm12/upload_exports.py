"""Publish only explicitly inventoried, validated accepted DFM12 packages."""
import argparse
import io
from pathlib import Path
import time

from huggingface_hub import CommitOperationAdd, HfApi
from huggingface_hub.errors import RepositoryNotFoundError

from .export_validator import validate
from .io import file_hash, load, lock, write_json


def publish(root, namespace):
    api = HfApi()
    api.whoami()
    with lock(root / ".export.lock"):
        inventory = load(root / "manifest.json")
        receipt_path = root / "metadata/upload-receipts.json"
        receipts = load(receipt_path) if receipt_path.exists() else {}
        for package in inventory["packages"]:
            name = package["name"]
            if not name.startswith("dfm12-") or Path(name).name != name:
                raise ValueError("Unsafe package name")
            folder = root / name
            manifest_path = folder / "metadata/manifest.json"
            manifest = load(manifest_path)
            if package["rows"] == 0 and manifest.get("upload_ready") is False:
                validate(folder)
                print("EMPTY NO UPLOAD", name, flush=True)
                continue
            if not manifest["upload_ready"] or not package["rows"]:
                raise ValueError("Package is not upload ready: " + name)
            repo = namespace + "/" + name
            checksum = file_hash(manifest_path)
            saved = receipts.get(repo)
            if saved and saved["status"] == "verified" and saved["manifest_sha256"] == checksum:
                print("ALREADY VERIFIED", repo, flush=True)
                continue
            try:
                info = api.repo_info(repo, repo_type="dataset")
            except RepositoryNotFoundError:
                info = None
            if info is not None and not saved:
                raise ValueError("Refusing to overwrite an existing unowned repository: " + repo)
            if saved and saved["manifest_sha256"] != checksum:
                raise ValueError("Previously uploaded package changed: " + repo)
            result = validate(folder)
            if result["rows"] != package["rows"]:
                raise ValueError("Inventory row count mismatch")
            files = {item["file"] for item in manifest["data_files"] + manifest["metadata_files"]}
            files.update({"metadata/manifest.json", "validate_dataset.py"})
            for name_in_repo in files:
                path = folder / name_in_repo
                if not path.resolve().is_relative_to(folder.resolve()):
                    raise ValueError("Package path escapes folder")
            card = (folder / "README.md").read_text().replace(
                "Local-only accepted subset; no upload performed or Hub repository assigned.",
                "Published accepted-only DFM12 subset. Local audit-snapshot fields describe the pre-publication build, not Hub publication status.")
            card = card.replace("Local accepted-only European expansion export. No upload performed.",
                "Published accepted-only European expansion dataset. Local manifest upload fields describe the pre-publication build; publication receipts record the Hub revision.")
            receipts[repo] = {"status": "publishing", "manifest_sha256": checksum,
                              "rows": package["rows"], "authorized": "explicit user upload request",
                              "public": True, "started": time.time()}
            write_json(receipt_path, receipts)
            api.create_repo(repo, repo_type="dataset", private=False, exist_ok=bool(saved))
            operations = [CommitOperationAdd(path_in_repo=n, path_or_fileobj=str(folder / n)) for n in sorted(files)]
            operations.append(CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=io.BytesIO(card.encode())))
            commit = api.create_commit(repo, repo_type="dataset", operations=operations,
                                       commit_message="Publish validated accepted-only DFM12 dataset with source attribution")
            remote = set(api.list_repo_files(repo, repo_type="dataset", revision=commit.oid))
            expected = files | {"README.md"}
            if not expected <= remote or remote - expected - {".gitattributes"}:
                raise ValueError("Remote file inventory mismatch: " + repo)
            receipts[repo].update(status="verified", revision=commit.oid, commit_url=commit.commit_url,
                                  file_count=len(expected), completed=time.time())
            write_json(receipt_path, receipts)
            print("VERIFIED", repo, package["rows"], commit.oid, flush=True)
        print("Completed", sum(p["rows"] > 0 for p in inventory["packages"]), "nonempty public dataset uploads", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, default=Path("exports_dfm12"))
    parser.add_argument("--namespace", default="schneiderkamplab")
    args = parser.parse_args()
    publish(args.output, args.namespace)
