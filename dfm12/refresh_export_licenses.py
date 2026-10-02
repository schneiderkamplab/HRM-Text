"""Locally refresh export licensing; preserve student data and original audits."""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import shutil
import time

from .export_finished import bundle_file, descriptor
from .export_licenses import enrich
from .export_validator import validate
from .io import atomic, file_hash, load, lock, write_json


def refresh(root):
    with lock(root / ".export.lock"):
        inventory = load(root / "manifest.json")
        backup = root / "metadata" / ("license-refresh-" + time.strftime("%Y%m%dT%H%M%S", time.gmtime()))
        backup.mkdir()
        write_json(backup / "inventory-before.json", inventory)
        report = []
        for package in inventory["packages"]:
            original = root / package["name"]
            manifest = load(original / "metadata/manifest.json")
            if not any(k.startswith("unknown") for k in manifest["licenses_per_accepted_record"]):
                continue
            for item in manifest["data_files"] + manifest["metadata_files"]:
                if file_hash(original / item["file"]) != item["sha256"]:
                    raise ValueError("Existing package changed: " + package["name"])
            stage = root / (".license-" + package["name"])
            # Hardlink only as a staging optimization; all changed files are replaced.
            shutil.copytree(original, stage, copy_function=os.link)
            audit = stage / manifest["audit_file"]
            replacement = audit.with_suffix(".new.gz")
            counts, statuses, cache = Counter(), Counter(), {}
            with gzip.open(audit, "rt", encoding="utf-8") as source, gzip.open(replacement, "wt", encoding="utf-8", compresslevel=1) as out:
                for line in source:
                    item = json.loads(line)
                    item["export_provenance"] = enrich(item["export_provenance"], lambda p: bundle_file(stage, p, cache))
                    provenance = item["export_provenance"]
                    counts[provenance.get("license", "unknown; see source evidence")] += 1
                    statuses[provenance.get("license_resolution", {}).get("status", "unresolved")] += 1
                    out.write(json.dumps(item, ensure_ascii=False) + "\n")
            replacement.replace(audit)
            resolution = {"counts": dict(counts), "statuses": dict(statuses),
                          "scope": "Source license claims, not legal certification or a new license grant",
                          "student_data_unchanged": True, "raw_audit_records_unchanged": True,
                          "evidence": [{"file": name, "sha256": file_hash(stage / name)} for name in sorted(cache.values())]}
            write_json(stage / "metadata/license-resolution.json", resolution)
            manifest["licenses_per_accepted_record"] = dict(counts)
            manifest["license_resolution_statuses"] = dict(statuses)
            manifest["metadata_files"] = [descriptor(stage, p) for p in sorted((stage / "metadata").rglob("*"))
                                          if p.is_file() and p.name != "manifest.json"]
            write_json(stage / "metadata/manifest.json", manifest)
            text = (original / "README.md").read_text()
            before, rest = text.split("License labels among accepted records:\n\n", 1)
            _, after = rest.split("\n\n## Validation", 1)
            labels = "\n".join(f"- {k}: {v:,}" for k, v in sorted(counts.items()))
            note = ("\n\nResolved from pinned constituent evidence, not the collection-level license. "
                    "See `metadata/license-resolution.json` and per-record `export_provenance.license_resolution`. "
                    "Original audit records are unchanged. Preserve attribution and share-alike notices. "
                    "Unspecified generated-instruction licenses remain explicitly unspecified; source-use approval is not a license grant.")
            with atomic(stage / "README.md") as out:
                out.write(before + "License labels among accepted records:\n\n" + labels + note + "\n\n## Validation" + after)
            verified = validate(stage)
            if manifest["data_files"] != load(original / "metadata/manifest.json")["data_files"]:
                raise ValueError("Student descriptors changed")
            original.rename(backup / package["name"])
            stage.rename(original)
            package["validation"] = verified
            package["package_bytes"] = sum(p.stat().st_size for p in original.rglob("*") if p.is_file())
            report.append({"package": package["name"], **resolution})
            inventory["package_bytes"] = sum(p["package_bytes"] for p in inventory["packages"])
            write_json(root / "manifest.json", inventory)
            write_json(backup / "report.json", report)
            print(json.dumps(report[-1]), flush=True)
        readme = (root / "README.md").read_text()
        for p in inventory["packages"]:
            lines = readme.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("| [" + p["name"] + "]"):
                    lines[i] = f"| [{p['name']}]({p['name']}/README.md) | {p['rows']:,} | {p['data_bytes']:,} | {p['package_bytes']:,} | {p['status']} |"
            readme = "\n".join(lines) + "\n"
        with atomic(root / "README.md") as out:
            out.write(readme)
        print("Updated", len(report), "packages; backup", backup, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, default=Path("exports_dfm12"))
    refresh(parser.parse_args().output)
