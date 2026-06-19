#!/usr/bin/env python3
"""Prepare export-synth datasets as direct export-upload dataset folders."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_GROUP_COUNTS = {"high40": 40, "repeat30": 30}
HF_REPO_ID_MAX_LENGTH = 96
HF_LICENSE = "apache-2.0"
GENERATION_MODEL_ID = "google/gemma-4-31B-it"
JUDGE_MODEL_ID = "google/gemma-4-31B-it"
SERVED_MODEL_ALIAS = "posttrain-gemma-teacher"


RECREATE_SCRIPT = """#!/usr/bin/env python3
\"\"\"Recreate or validate this exported synthetic chat dataset.\"\"\"

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

TASK_NAME = {task_name!r}
SYNTH_SOURCE_SLUG = {synth_source_slug!r}
GROUP = {group!r}
GENERATION_MODEL_ID = {generation_model_id!r}
JUDGE_MODEL_ID = {judge_model_id!r}
SERVED_MODEL_ALIAS = {served_model_alias!r}


def export_row(row):
    instruction = str(row.get("instruction") or "").strip()
    response = str(row.get("response") or "").strip()
    legacy_notes_key = "anonym" + "ization_notes"
    return {{
        "messages": [
            {{"role": "user", "content": instruction}},
            {{"role": "assistant", "content": response}},
        ],
        "condition": row.get("condition"),
        "source": {{
            "campaign": "sapient-excluded-synthetic-anonymous",
            "group": GROUP,
            "task_name": TASK_NAME,
            "synth_source_slug": SYNTH_SOURCE_SLUG,
            "source_path": row.get("source_path"),
            "source_row_id": row.get("source_row_id"),
        }},
        "synthetic_audit": {{
            "keep": row.get("keep"),
            "attempt": row.get("attempt"),
            "anonymous_generation_notes": row.get("anonymous_generation_notes", row.get(legacy_notes_key)),
            "judge": row.get("judge"),
            "heuristic": row.get("heuristic"),
        }},
    }}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rebuild(source_dir, output_dir):
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    data_dir = output_dir / "data"
    meta_dir = output_dir / "metadata"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / "train.jsonl.gz"
    rows = 0
    shards = sorted((source_dir / "data").glob("train.shard*.jsonl.gz"))
    if not shards:
        raise SystemExit(f"No accepted shards found under {{source_dir / 'data'}}")
    with gzip.open(target, "wt", encoding="utf-8", compresslevel=6) as dst:
        for shard in shards:
            with gzip.open(shard, "rt", encoding="utf-8") as src:
                for line in src:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row.get("keep") is not True:
                        continue
                    out = export_row(row)
                    if not out["messages"][0]["content"] or not out["messages"][1]["content"]:
                        continue
                    rows += 1
                    dst.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + "\\n")
    combine_summaries(source_dir, meta_dir / "summary.json")
    print(json.dumps({{"rows": rows, "sha256": sha256(target)}}, sort_keys=True))


def combine_summaries(source_dir, output_path):
    numeric = {{}}
    source_paths = set()
    tasks = set()
    shard_count = 0
    for path in sorted(source_dir.glob("summary.shard*.json")):
        shard_count += 1
        with path.open("r", encoding="utf-8") as f:
            item = json.load(f)
        for key, value in item.items():
            if isinstance(value, int):
                numeric[key] = numeric.get(key, 0) + value
        if item.get("source_path"):
            source_paths.add(item["source_path"])
        if item.get("task"):
            tasks.add(item["task"])
    output = {{
        "task": TASK_NAME,
        "source_paths": sorted(source_paths),
        "shards": shard_count,
        "generation_model": GENERATION_MODEL_ID,
        "judge_model": JUDGE_MODEL_ID,
        "served_model_alias": SERVED_MODEL_ALIAS,
        **numeric,
    }}
    if tasks and tasks != {{TASK_NAME}}:
        output["tasks_seen"] = sorted(tasks)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\\n")


def validate(dataset_dir):
    dataset_dir = Path(dataset_dir)
    rows = 0
    bad = 0
    path = dataset_dir / "data" / "train.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows += 1
            try:
                row = json.loads(line)
                messages = row["messages"]
                if len(messages) != 2 or messages[0].get("role") != "user" or messages[1].get("role") != "assistant":
                    bad += 1
                if not messages[0].get("content") or not messages[1].get("content"):
                    bad += 1
            except Exception:
                bad += 1
    print(json.dumps({{"rows": rows, "bad_rows": bad, "sha256": sha256(path)}}, sort_keys=True))
    if bad:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-synth", help="Path to the already synthesized source folder to package")
    parser.add_argument("--output", default=".", help="Output dataset folder, default: current directory")
    parser.add_argument("--validate", action="store_true", help="Validate exported data file")
    args = parser.parse_args()
    if args.from_synth:
        rebuild(args.from_synth, args.output)
    if args.validate or not args.from_synth:
        validate(args.output)


if __name__ == "__main__":
    main()
"""


def count_jsonl_gz_rows(data_dir: Path) -> int:
    rows = 0
    for path in sorted(data_dir.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            rows += sum(1 for line in f if line.strip())
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_no_symlinks(path: Path) -> None:
    links = [p for p in path.rglob("*") if p.is_symlink()]
    if links:
        formatted = "\n".join(str(p) for p in links[:20])
        raise SystemExit(f"Refusing to package symlinks under {path}:\n{formatted}")


def combine_summary_files(dataset_dir: Path) -> dict:
    summary_dir = dataset_dir / "metadata" / "summaries"
    paths = sorted(summary_dir.glob("summary.shard*.json"))
    numeric: dict[str, int] = {}
    source_paths: set[str] = set()
    tasks: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            item = json.load(f)
        for key, value in item.items():
            if isinstance(value, int):
                numeric[key] = numeric.get(key, 0) + value
        if item.get("source_path"):
            source_paths.add(item["source_path"])
        if item.get("task"):
            tasks.add(item["task"])
    if summary_dir.exists():
        shutil.rmtree(summary_dir)
    summary = {
        "shards": len(paths),
        "source_paths": sorted(source_paths),
        **numeric,
    }
    if len(tasks) == 1:
        summary["task"] = next(iter(tasks))
    elif tasks:
        summary["tasks"] = sorted(tasks)
    summary["generation_model"] = GENERATION_MODEL_ID
    summary["judge_model"] = JUDGE_MODEL_ID
    summary["served_model_alias"] = SERVED_MODEL_ALIAS
    output_path = dataset_dir / "metadata" / "summary.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return {
        "file": "metadata/summary.json",
        "bytes": output_path.stat().st_size,
        "sha256": sha256(output_path),
    }


def copy_dataset(source: Path, target: Path, force: bool) -> None:
    if target.exists():
        if not force:
            raise SystemExit(f"{target} already exists; rerun with --force to replace it")
        shutil.rmtree(target)
    shutil.copytree(source, target, symlinks=False)


def make_repo_name(group: str, dataset_id: str) -> str:
    del group
    name = f"sapient-synth-{dataset_id}"
    replacements = {
        "amazon-and-yelp-summarization-dataset-summarization": "amazon-yelp-summarization",
        "paper-reviews-accept-or-reject-classification": "paper-reviews-accept-reject",
        "paper-reviews-reviewer-perspective-classification": "paper-reviews-reviewer-perspective",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    if len(name) <= HF_REPO_ID_MAX_LENGTH:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{name[: HF_REPO_ID_MAX_LENGTH - 9].rstrip('-.')}-{digest}"


def join_data_shards(dataset_dir: Path) -> dict:
    data_dir = dataset_dir / "data"
    shard_paths = sorted(data_dir.glob("train-*.jsonl.gz"))
    if shard_paths == [data_dir / "train.jsonl.gz"]:
        shard_paths = []
    if not shard_paths:
        target = data_dir / "train.jsonl.gz"
        return {"file": "data/train.jsonl.gz", "rows": count_jsonl_gz_rows(data_dir), "bytes": target.stat().st_size, "sha256": sha256(target)}

    target = data_dir / "train.jsonl.gz"
    temp = data_dir / "train.jsonl.gz.tmp"
    rows = 0
    with gzip.open(temp, "wt", encoding="utf-8", compresslevel=6) as dst:
        for shard in shard_paths:
            with gzip.open(shard, "rt", encoding="utf-8") as src:
                for line in src:
                    if not line.strip():
                        continue
                    rows += 1
                    row = json.loads(line)
                    if isinstance(row.get("source"), dict):
                        row["source"]["campaign"] = "sapient-excluded-synthetic-anonymous"
                    audit = row.get("synthetic_audit")
                    legacy_notes_key = "anonym" + "ization_notes"
                    if isinstance(audit, dict) and legacy_notes_key in audit:
                        audit["anonymous_generation_notes"] = audit.pop(legacy_notes_key)
                    dst.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temp.replace(target)
    for shard in shard_paths:
        shard.unlink()
    return {
        "file": "data/train.jsonl.gz",
        "rows": rows,
        "bytes": target.stat().st_size,
        "sha256": sha256(target),
    }


def update_metadata(dataset_dir: Path, joined_file: dict, summary_file: dict, license_id: str) -> dict:
    path = dataset_dir / "metadata" / "manifest.json"
    with path.open("r", encoding="utf-8") as f:
        source_metadata = json.load(f)
    metadata = {
        "dataset_id": source_metadata["dataset_id"],
        "task_name": source_metadata["task_name"],
        "source_paths": source_metadata.get("source_paths", []),
        "accepted_rows": joined_file["rows"],
        "data_file": joined_file,
        "summary_file": summary_file,
        "license": license_id,
        "generation_model": GENERATION_MODEL_ID,
        "judge_model": JUDGE_MODEL_ID,
        "served_model_alias": SERVED_MODEL_ALIAS,
        "synth_source_dir": source_metadata["synth_source_dir"],
        "synth_source_slug": source_metadata["synth_source_slug"],
        "group": source_metadata["group"],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return metadata


def write_readme(dataset_dir: Path, metadata: dict, repo_name: str) -> None:
    title = repo_name
    readme = f"""---
license: {HF_LICENSE}
language:
- en
tags:
- synthetic
- instruction-tuning
- anonymous
- chat
pretty_name: {title}
---

# {title}

Chat-template-ready synthetic anonymous replacement examples for one Sapient source excluded from the DFM5 data mix.

## Contents

- Format: gzip-compressed JSON Lines under `data/train.jsonl.gz`
- Schema: `{{"messages": [{{"role": "user", "content": "..."}}, {{"role": "assistant", "content": "..."}}]}}`
- Files: `1`
- Rows: `{metadata["accepted_rows"]}`
- Task: synthetic anonymous instruction replacement

## Generation

Rows were generated with [`{GENERATION_MODEL_ID}`](https://huggingface.co/{GENERATION_MODEL_ID}) and accepted only after a [`{JUDGE_MODEL_ID}`](https://huggingface.co/{JUDGE_MODEL_ID}) judge checked task preservation, PII absence, low textual overlap, and usefulness.

Overlap precautions: prompts asked the model to create new synthetic examples that preserve the task type and skill, not to rewrite or copy the provenance row. Candidates were rejected when the judge found substantial wording overlap, unresolved PII, or failure to preserve the task. Only accepted rows are included.

## License

Released as Apache-2.0. The datasets that inspired these recreations may have different licensing conditions. These examples are fully synthetic recreations with no or minimal wording overlap and were judged to be free of PII before inclusion.

## Recreate

```bash
python recreate_dataset.py --validate
python recreate_dataset.py --from-synth /path/to/{metadata["synth_source_dir"]} --output /path/to/output-folder
```
"""
    (dataset_dir / "README.md").write_text(readme, encoding="utf-8")


def write_license(dataset_dir: Path) -> None:
    text = """Apache License
Version 2.0, January 2004
https://www.apache.org/licenses/

This dataset package is released under the Apache License, Version 2.0.

Provenance note: the datasets that inspired these recreations may have different
licensing conditions. The included examples are fully synthetic recreations with
no or minimal wording overlap with the provenance data and were judged to be
free of PII before inclusion.

The full Apache 2.0 license text is available at:
https://www.apache.org/licenses/LICENSE-2.0
"""
    (dataset_dir / "LICENSE.md").write_text(text, encoding="utf-8")


def write_recreate_script(dataset_dir: Path, metadata: dict) -> None:
    script = RECREATE_SCRIPT.format(
        task_name=metadata["task_name"],
        synth_source_slug=metadata["synth_source_slug"],
        group=metadata["group"],
        generation_model_id=GENERATION_MODEL_ID,
        judge_model_id=JUDGE_MODEL_ID,
        served_model_alias=SERVED_MODEL_ALIAS,
    )
    path = dataset_dir / "recreate_dataset.py"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    datasets = manifest.get("datasets") or []
    group_counts = {group: 0 for group in EXPECTED_GROUP_COUNTS}
    for item in datasets:
        group_counts[item["group"]] = group_counts.get(item["group"], 0) + 1
    if group_counts != EXPECTED_GROUP_COUNTS:
        raise SystemExit(f"Unexpected export-synth group counts: {group_counts}")
    return manifest


def prepare(root: Path, output_root: Path, force: bool) -> dict:
    manifest = load_manifest(root / "manifest.json")
    assert_no_symlinks(root)
    output_root.mkdir(parents=True, exist_ok=True)
    if force:
        for old in output_root.glob("sapient-synth-*"):
            if old.is_dir():
                shutil.rmtree(old)
    prepared = []
    for item in manifest["datasets"]:
        group = item["group"]
        dataset_id = item["dataset_id"]
        source = root / item["path"]
        if not source.is_dir():
            raise SystemExit(f"Missing source folder: {source}")
        target_name = make_repo_name(group, dataset_id)
        target = output_root / target_name
        copy_dataset(source, target, force=force)
        assert_no_symlinks(target)
        joined_file = join_data_shards(target)
        summary_file = combine_summary_files(target)
        metadata = update_metadata(target, joined_file, summary_file, HF_LICENSE)
        write_readme(target, metadata, target_name)
        write_license(target)
        write_recreate_script(target, metadata)
        row_count = count_jsonl_gz_rows(target / "data")
        expected_rows = int(item["accepted_rows"])
        if row_count != expected_rows:
            raise SystemExit(
                f"Row-count mismatch for {target}: got {row_count}, expected {expected_rows}"
            )
        prepared.append(
            {
                "repo_name": target_name,
                "group": group,
                "dataset_id": dataset_id,
                "accepted_rows": row_count,
                "source_export_synth_path": item["path"],
                "original_task_name": item["task_name"],
            }
        )
    upload_manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(root),
        "target": str(output_root),
        "dataset_count": len(prepared),
        "accepted_rows": sum(item["accepted_rows"] for item in prepared),
        "datasets": prepared,
    }
    manifest_path = output_root / "sapient-synth-upload-manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(upload_manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return upload_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="export-synth", help="Source export-synth root")
    parser.add_argument("--output-root", default="export-upload", help="Destination upload root")
    parser.add_argument("--force", action="store_true", help="Replace existing synthetic upload folders")
    args = parser.parse_args()
    result = prepare(Path(args.root), Path(args.output_root), force=args.force)
    print(
        json.dumps(
            {
                "dataset_count": result["dataset_count"],
                "accepted_rows": result["accepted_rows"],
                "manifest": str(Path(args.output_root) / "sapient-synth-upload-manifest.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
