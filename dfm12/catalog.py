"""Pinned, explicit source selection. A review hold cannot silently become approval."""
from fnmatch import fnmatch
from pathlib import Path
import yaml

from .io import digest, load, lock, write_json

DEFAULT_CONFIG = Path(__file__).with_name("config.yaml")


def config(path=DEFAULT_CONFIG):
    return yaml.safe_load(Path(path).read_text())


def resolve(root, cfg):
    from huggingface_hub import HfApi
    api = HfApi()
    destination = root / "sources.lock.json"
    with lock(root / ".catalog.lock"):
        if destination.exists():
            previous = load(destination)
            if previous["config_hash"] != digest(cfg):
                raise ValueError("Configuration changed; use a new work directory or explicitly archive the old lock")
            return previous
        result = {"config_hash": digest(cfg), "sources": {}}
        for name, source in cfg["sources"].items():
            entry = dict(source)
            try:
                info = api.dataset_info(source["repo"], revision=source.get("revision"))
                entry["revision"] = info.sha
                entry["files"] = [f.rfilename for f in info.siblings
                                  if any(fnmatch(f.rfilename, p) for p in source["patterns"])
                                  and Path(f.rfilename).name != "metadata.parquet"]
                if not entry["files"]:
                    raise ValueError("No files match the approved patterns")
                entry["status"] = "review" if source.get("review") else "ready"
            except Exception as exc:
                entry.update(status="blocked", error=f"{type(exc).__name__}: {exc}")
            result["sources"][name] = entry
            print(name, entry["status"], flush=True)
        write_json(destination, result)
        return result


def selected_source(root, name):
    entry = dict(load(root / "sources.lock.json")["sources"][name])
    if entry["status"] == "blocked":
        raise ValueError(entry["error"])
    approval = root / "approvals" / f"{name}.json"
    if entry["status"] == "review":
        if not approval.exists():
            raise ValueError(f"Review required: {approval}: {entry['review']}")
        review = load(approval)
        if review.get("revision") != entry["revision"] or not review.get("evidence"):
            raise ValueError("Approval must name the pinned revision and evidence")
        files = review.get("files", [])
        if not files or not set(files) <= set(entry["files"]):
            raise ValueError("Approval must select explicit files from the locked source")
        entry["files"] = files
        entry["review_receipt"] = review
    return entry


def download(root, name):
    from huggingface_hub import snapshot_download
    entry = selected_source(root, name)
    with lock(root / "downloads" / f".{name}.lock"):
        snapshot_download(repo_id=entry["repo"], repo_type="dataset", revision=entry["revision"],
                          local_dir=root / "downloads" / name, max_workers=4,
                          allow_patterns=entry["files"] + ["README.md", "LICENSE*", "data/*/datasheet.md"])
    return entry
