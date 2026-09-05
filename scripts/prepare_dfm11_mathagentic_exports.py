#!/usr/bin/env python3
"""Build upload-ready DFM11 Mathagentic dataset packages."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
MATHAGENTIC = ROOT / "mathagentic"
DEFAULT_OUTPUT = ROOT / "exports_dfm11"
UPLOAD_RECEIPTS = ROOT / "logs/dfm11_mathagentic_upload_receipts.jsonl"


@dataclass(frozen=True)
class PackageSpec:
    name: str
    source_dir: Path
    source_glob: str
    upstream: tuple[str, ...]
    license: str
    description: str
    selection: str
    admission_status: str
    intended_hf_id: str
    dfm11_row_cap: int | None
    dfm11_repeat: int


SPECS = (
    PackageSpec(
        name="dfm11-mathagentic-tinygsm-python",
        source_dir=MATHAGENTIC / "data/converted/tinygsm",
        source_glob="tinygsm-*.jsonl",
        upstream=("TinyGSM/TinyGSM",),
        license="mit",
        description=(
            "English arithmetic word problems converted into native Python tool-call "
            "trajectories with precomputed tool responses and boxed final answers."
        ),
        selection=(
            "Deterministic 1-in-20 source sample; restricted-Python validation and "
            "execution; independent Gemma 4 26B A4B semantic audit; accepted verdicts only."
        ),
        admission_status="semantic_verified",
        intended_hf_id="schneiderkamplab/dfm11-mathagentic-tinygsm-python",
        dfm11_row_cap=50_000,
        dfm11_repeat=1,
    ),
    PackageSpec(
        name="dfm11-mathagentic-gsm8k-prolog",
        source_dir=MATHAGENTIC / "data/converted/gsm8k-prolog",
        source_glob="gsm8k-prolog-*.jsonl",
        upstream=("niklasm222/gsm8k-prolog-prover", "openai/gsm8k"),
        license="other",
        description=(
            "GSM8K training questions converted into native SWI-Prolog tool-call "
            "trajectories with precomputed tool responses and boxed final answers."
        ),
        selection=(
            "All rows pass SWI-Prolog sandbox validation and execution and agree with "
            "reviewed GSM8K answers; 12 malformed programs and 14 bad gold labels use "
            "tracked, manually reviewed corrections."
        ),
        admission_status="execution_and_gold_verified",
        intended_hf_id="schneiderkamplab/dfm11-mathagentic-gsm8k-prolog",
        dfm11_row_cap=None,
        dfm11_repeat=2,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rows-per-shard", type=int, default=100_000)
    parser.add_argument("--dataset", action="append", choices=[spec.name for spec in SPECS])
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonl_rows(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_number}: expected an object")
                yield row


def accepted_verdicts(path: Path) -> tuple[set[str], dict[str, Any]]:
    accepted: set[str] = set()
    seen: set[str] = set()
    reasons: Counter[str] = Counter()
    models: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            source_id = str(row.get("source_id") or "")
            if not source_id or source_id in seen:
                raise ValueError(f"{path}:{line_number}: missing or duplicate source_id")
            seen.add(source_id)
            if row.get("accepted") is True:
                accepted.add(source_id)
            else:
                reasons[str(row.get("reason_code") or "unknown")] += 1
            if row.get("audit_model"):
                models.add(str(row["audit_model"]))
    return accepted, {
        "audited_rows": len(seen),
        "accepted_rows": len(accepted),
        "rejected_rows": len(seen) - len(accepted),
        "acceptance_rate": len(accepted) / len(seen),
        "rejection_reasons": dict(sorted(reasons.items())),
        "audit_models": sorted(models),
        "verdict_sha256": sha256(path),
    }


def verified_publications() -> set[str]:
    if not UPLOAD_RECEIPTS.is_file():
        return set()
    verified: set[str] = set()
    with UPLOAD_RECEIPTS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("validation", {}).get("valid") is True and row.get("repo_id"):
                verified.add(str(row["repo_id"]))
    return verified


class GzipShardWriter:
    def __init__(self, data_dir: Path, rows_per_shard: int) -> None:
        self.data_dir = data_dir
        self.rows_per_shard = rows_per_shard
        self.index = 0
        self.rows_in_shard = 0
        self.rows = 0
        self.paths: list[Path] = []
        self.raw: io.BufferedWriter | None = None
        self.compressed: gzip.GzipFile | None = None
        self.text: io.TextIOWrapper | None = None

    def _open(self) -> None:
        path = self.data_dir / f"train-{self.index:05d}.jsonl.gz"
        self.raw = path.open("wb")
        self.compressed = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, compresslevel=6, mtime=0)
        self.text = io.TextIOWrapper(self.compressed, encoding="utf-8", newline="\n")
        self.paths.append(path)
        self.rows_in_shard = 0
        self.index += 1

    def write(self, row: dict[str, Any]) -> None:
        if self.text is None or self.rows_in_shard >= self.rows_per_shard:
            self.close_current()
            self._open()
        assert self.text is not None
        self.text.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        self.rows_in_shard += 1
        self.rows += 1

    def close_current(self) -> None:
        if self.text is not None:
            self.text.flush()
            self.text.close()
        self.text = None
        self.compressed = None
        self.raw = None

    def close(self) -> None:
        self.close_current()


def validate_row(row: dict[str, Any], expected_status: str) -> None:
    if row.get("admission_status") != expected_status:
        raise ValueError(f"unexpected admission status for {row.get('source_id')}")
    messages = row.get("messages")
    tools = row.get("tools")
    if not isinstance(messages, list) or len(messages) != 4 or not isinstance(tools, list) or len(tools) != 1:
        raise ValueError(f"invalid trajectory shape for {row.get('source_id')}")
    if [message.get("role") for message in messages] != ["user", "assistant", "tool", "assistant"]:
        raise ValueError(f"invalid role sequence for {row.get('source_id')}")
    calls = messages[1].get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError(f"invalid tool call for {row.get('source_id')}")
    if calls[0].get("id") != messages[2].get("tool_call_id"):
        raise ValueError(f"tool call/result mismatch for {row.get('source_id')}")
    if not str(messages[3].get("content") or "").startswith("\\boxed{"):
        raise ValueError(f"missing boxed terminal answer for {row.get('source_id')}")


def package_rows(spec: PackageSpec, accepted: set[str] | None) -> tuple[Iterator[dict[str, Any]], int]:
    paths = sorted(spec.source_dir.glob(spec.source_glob))
    if not paths:
        raise FileNotFoundError(f"no source shards for {spec.name}")

    def rows() -> Iterator[dict[str, Any]]:
        matched: set[str] = set()
        for row in jsonl_rows(paths):
            source_id = str(row.get("source_id") or "")
            if accepted is not None and source_id not in accepted:
                continue
            if source_id in matched:
                raise ValueError(f"duplicate source_id: {source_id}")
            matched.add(source_id)
            row["admission_status"] = spec.admission_status
            validate_row(row, spec.admission_status)
            yield row
        if accepted is not None and matched != accepted:
            missing = accepted - matched
            raise ValueError(f"{len(missing)} accepted verdict IDs have no converted row")

    return rows(), len(paths)


VALIDATOR = '''#!/usr/bin/env python3
import gzip, hashlib, json
from pathlib import Path

root = Path(__file__).parent
manifest = json.loads((root / "metadata/manifest.json").read_text())
rows = 0
seen = set()
for item in manifest["data_files"]:
    path = root / item["file"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item["sha256"]:
        raise ValueError(f"checksum mismatch: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            sid = row.get("source_id")
            if not sid or sid in seen:
                raise ValueError(f"missing or duplicate source_id: {sid}")
            seen.add(sid)
            messages = row.get("messages")
            if [message.get("role") for message in messages] != ["user", "assistant", "tool", "assistant"]:
                raise ValueError(f"invalid roles: {sid}")
            call = messages[1]["tool_calls"][0]
            if call["id"] != messages[2].get("tool_call_id"):
                raise ValueError(f"call/result mismatch: {sid}")
            if not str(messages[3].get("content") or "").startswith("\\\\boxed{"):
                raise ValueError(f"missing boxed answer: {sid}")
            rows += 1
if rows != manifest["rows"]:
    raise ValueError(f"row count mismatch: {rows} != {manifest['rows']}")
print(json.dumps({"rows": rows, "valid": True}, sort_keys=True))
'''


def dataset_card(spec: PackageSpec, rows: int, shards: int, audit: dict[str, Any] | None) -> str:
    audit_text = ""
    if audit is not None:
        audit_text = (
            f"\nThe semantic audit covered {audit['audited_rows']:,} candidates and accepted "
            f"{audit['accepted_rows']:,} ({audit['acceptance_rate']:.2%}). Rejected rows are not packaged.\n"
        )
    upstream = "\n".join(f"- `{item}`" for item in spec.upstream)
    license_note = (
        "The upstream TinyGSM dataset declares the MIT license. Preserve its attribution."
        if spec.license == "mit"
        else (
            "The GSM8K source declares MIT. The gsm8k-prolog-prover dataset card does not "
            "declare a machine-readable license. Manual project release approval was recorded "
            "on 2026-09-03; preserve the upstream citation and do not represent this derivative "
            "as MIT-licensed. This package does not broaden upstream rights."
        )
    )
    sampling = (
        f"deterministically cap to {spec.dfm11_row_cap:,} distinct rows per epoch"
        if spec.dfm11_row_cap is not None
        else "use every packaged row per epoch"
    )
    return f'''---
license: {spec.license}
language:
- en
task_categories:
- text-generation
tags:
- instruction-tuning
- tool-calling
- math
- dfm11
pretty_name: {spec.name}
---

# {spec.name}

{spec.description}

## Contents

- Rows: {rows:,}
- Shards: {shards:,}
- Format: deterministic gzip JSON Lines in `data/train-*.jsonl.gz`
- Schema: `tools`, four-message native tool trajectory, execution metadata,
  stable source ID, source revision, and admission status
- Intended repository: `{spec.intended_hf_id}`

Each row contains a user problem, an assistant tool call, a precomputed tool
response, and a terminal assistant response containing exactly one boxed final
answer. It is directly consumable by Mathagentic/HRM-Text's Gemma 4 native
tool-call rendering path; no executor is used during training.

## Upstream datasets

{upstream}

## Selection and verification

{spec.selection}
{audit_text}
The package contains source trajectories, not tokenized arrays or sampled epoch
indices. Packaging does not itself admit the dataset into a DFM11 data mix.
The approved DFM11 sampling policy is to {sampling}, with repeat
`{spec.dfm11_repeat}`. This policy does not remove rows from the published
source package.

## License and citation review

{license_note}

## Validate

```bash
python validate_dataset.py
```
'''


def build_package(spec: PackageSpec, output_root: Path, rows_per_shard: int, force: bool) -> dict[str, Any]:
    destination = output_root / spec.name
    if destination.exists() and not force:
        raise FileExistsError(f"{destination} exists; pass --force to rebuild")
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{spec.name}.", dir=output_root))
    try:
        data_dir = temporary / "data"
        metadata_dir = temporary / "metadata"
        data_dir.mkdir()
        metadata_dir.mkdir()
        audit = None
        accepted = None
        if spec.name.endswith("tinygsm-python"):
            verdict_path = MATHAGENTIC / "data/audits/tinygsm/verdicts.jsonl"
            accepted, audit = accepted_verdicts(verdict_path)
            if audit["audited_rows"] != 500_000:
                raise ValueError(f"TinyGSM audit is incomplete: {audit['audited_rows']}/500000")

        rows, source_shards = package_rows(spec, accepted)
        writer = GzipShardWriter(data_dir, rows_per_shard)
        for row in rows:
            writer.write(row)
        writer.close()
        if writer.rows == 0:
            raise ValueError(f"{spec.name}: no rows packaged")
        data_files = [
            {
                "file": path.relative_to(temporary).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in writer.paths
        ]
        source_manifest = json.loads((spec.source_dir / "manifest.json").read_text())
        published = spec.intended_hf_id in verified_publications()
        manifest = {
            "name": spec.name,
            "intended_hf_id": spec.intended_hf_id,
            "format": "mathagentic-native-tool-sft-v1; deterministic gzip JSON Lines",
            "rows": writer.rows,
            "shards": len(writer.paths),
            "data_files": data_files,
            "source_shards": source_shards,
            "source_revision": source_manifest["source_revision"],
            "upstream": list(spec.upstream),
            "license": spec.license,
            "selection": spec.selection,
            "admission_status": spec.admission_status,
            "dfm11_sampling": {
                "row_cap_per_epoch": spec.dfm11_row_cap,
                "repeat": spec.dfm11_repeat,
            },
            "semantic_audit": audit,
            "upload_performed": published,
            "publication_receipt_verified": published,
        }
        (metadata_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        )
        (temporary / "README.md").write_text(
            dataset_card(spec, writer.rows, len(writer.paths), audit), encoding="utf-8"
        )
        (temporary / "validate_dataset.py").write_text(VALIDATOR, encoding="utf-8")
        (temporary / "validate_dataset.py").chmod(0o755)
        if destination.exists():
            shutil.rmtree(destination)
        temporary.rename(destination)
        return manifest
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def write_inventory(output_root: Path, manifests: list[dict[str, Any]]) -> None:
    inventory = {
        "name": "dfm11-mathagentic-export-staging",
        "packages": manifests,
        "package_count": len(manifests),
        "rows": sum(item["rows"] for item in manifests),
        "bytes": sum(file["bytes"] for item in manifests for file in item["data_files"]),
        "upload_performed": bool(manifests) and all(item["upload_performed"] for item in manifests),
    }
    (output_root / "manifest.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    (output_root / "README.md").write_text(
        "# DFM11 Mathagentic export staging\n\n"
        "Upload-ready, locally validated packages. Preparation does not upload.\n\n"
        + "\n".join(
            f"- `{item['name']}`: {item['rows']:,} rows in {item['shards']} shards"
            for item in manifests
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    if args.rows_per_shard < 1:
        raise SystemExit("--rows-per-shard must be positive")
    selected = [spec for spec in SPECS if not args.dataset or spec.name in args.dataset]
    manifests = [
        build_package(spec, args.output_root.resolve(), args.rows_per_shard, args.force)
        for spec in selected
    ]
    existing = {
        path.parent.parent.name: json.loads(path.read_text())
        for path in args.output_root.resolve().glob("*/metadata/manifest.json")
    }
    existing.update({item["name"]: item for item in manifests})
    write_inventory(args.output_root.resolve(), [existing[name] for name in sorted(existing)])
    for item in manifests:
        print(f"READY {item['name']}: {item['rows']:,} rows, {item['shards']} shards")


if __name__ == "__main__":
    main()
