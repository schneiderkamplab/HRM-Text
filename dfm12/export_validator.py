#!/usr/bin/env python3
"""Standalone, stdlib-only validator for local accepted DFM12 packages."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def authorized_generic_no(record):
    """Portable copy of the two pinned Norwegian exceptions, not a no allowlist."""
    p = record.get("provenance", {})
    messages = record.get("messages", [])
    if not isinstance(p, dict) or not messages or record.get("language") != "no":
        return False
    if (p.get("repo") == "V4ldeLund/scandi-translated-instruct"
            and p.get("revision") == "5da16f97d23330fd029fec4462140433f65295d7"
            and p.get("admission_policy") == "user_include_whole_pinned_scandi_20260925_v1"
            and p.get("authorization_sha256") == "30903877aae3353cb0fa0c98b4153bc1a6e55973ceb5b241f59bde4e36049201"
            and p.get("file") in {f"data/train-{i:05d}-of-00004.parquet" for i in range(4)}
            and type(p.get("ordinal")) is int and p["ordinal"] >= 0
            and p.get("source_metadata", {}).get("source") == "muri-it-language-split"
            and p.get("source_metadata", {}).get("language") == ""
            and record.get("norwegian_standard") == "unknown"
            and record.get("message_languages") == ["no"] * len(messages)):
        matches = p.get("muri_lineage", [])
        message_hash = hashlib.sha256(canonical(messages).encode()).hexdigest()
        return bool(matches) and all(isinstance(m, dict)
            and m.get("revision") == "4987fc82a54145caf778efec6a682863591be1f2"
            and m.get("language") == "nor" and m.get("split") in {"train", "test", "validation"}
            and m.get("file") == f"nor/{m['split']}-00000-of-00001.parquet"
            and type(m.get("ordinal")) is int and m["ordinal"] >= 0
            and m.get("match_method") == "exact_original_messages"
            and m.get("messages_sha256") == message_hash for m in matches)
    if (p.get("repo") != "danish-foundation-models/norwegian-dyna-instruct"
            or p.get("revision") != "b7ea572dd64aa5d052e0086b57ad90da162db7d6"
            or p.get("variant_policy") != "user_include_unknown_and_mixed_norwegian_20260924"):
        return False
    if p.get("constituent") == "reasoning-norwegian":
        return record.get("norwegian_standard") == "unknown" and record.get("message_languages") == ["no"] * len(messages)
    if p.get("constituent") == "nb-samtale-pairs":
        labels, speakers = record.get("message_languages"), record.get("speaker_variants", [])
        return (record.get("norwegian_standard") == "mixed" and labels in (["nb", "nn"], ["nn", "nb"])
                and len(messages) == len(speakers) == 2 and [s.get("language") for s in speakers] == labels
                and all(s.get("orthography") == {"nb": "bm", "nn": "nn"}[s["language"]] for s in speakers))
    return False


EUROPEAN_LANGUAGES = {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl", "de", "fr", "es", "it", "cs", "pt_pt", "fi", "et", "ca", "el", "ro", "uk"}


def validate_language(record, european=False):
    allowed = {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl"}
    if european:
        allowed = EUROPEAN_LANGUAGES
    if record.get("language") not in allowed and not authorized_generic_no(record):
        raise ValueError("Unapproved language or missing pinned generic Norwegian proof")
    if "reverse_messages" in record and record.get("reverse_language") not in allowed:
        raise ValueError("Unapproved reverse language")


def training_rows(record):
    """Independent reconstruction for validation, not a preparation adapter."""
    paired = "reverse_messages" in record
    for direction in (["forward", "reverse"] if paired else ["native"]):
        reverse = direction == "reverse"
        result = {"id": record["id"] + (":" + direction if paired else ""),
                  "messages": [{"role": m["role"], "content": m["content"]}
                               for m in record["reverse_messages" if reverse else "messages"]],
                  "language": record["reverse_language" if reverse else "language"],
                  "task": record["task"], "parent_pair_id": record.get("source_record_id", record["id"]) if paired else None,
                  "direction": direction}
        if not reverse and "target_message_index" in record:
            result["target_message_index"] = record["target_message_index"]
        yield result


def validate(root):
    root = Path(root)
    manifest = json.loads((root / "metadata/manifest.json").read_text())
    if manifest["upload_performed"] is not False or manifest["authorization"]["scope"] != "local_accepted_only_export":
        raise ValueError("Missing local-only authorization")
    for item in manifest["data_files"] + manifest["metadata_files"]:
        path = (root / item["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or sha256(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError("File integrity/path mismatch: " + item["file"])
    metadata_hashes = {item["file"]: item["sha256"] for item in manifest["metadata_files"]}
    total = 0
    with tempfile.TemporaryDirectory() as directory:
        db = sqlite3.connect(str(Path(directory) / "validation.sqlite"))
        db.execute("CREATE TABLE expected(id TEXT PRIMARY KEY, value TEXT, seen INTEGER DEFAULT 0)")
        with gzip.open(root / manifest["audit_file"], "rt", encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
                if item["disposition"] != "accepted":
                    raise ValueError("Excluded record in package audit sidecar")
                result = item["audit"]
                if item["status"] != "done" or result.get("keep") is not True or item["gate_reasons"]:
                    raise ValueError("Nonaccepted record in acceptance mapping")
                if any(type(result.get(k)) is not int or not 4 <= result[k] <= 5
                       for k in ("language_quality", "coherence", "usefulness")):
                    raise ValueError("Invalid kept scores")
                validate_language(item["record"], manifest.get("export_schema") == "dfm12-european-v1")
                for evidence in item["export_provenance"].get("license_resolution", {}).get("evidence", []):
                    if metadata_hashes.get(evidence["file"]) != evidence["sha256"]:
                        raise ValueError("Portable license evidence not pinned in package")
                attribution = item["export_provenance"].get("attribution")
                if isinstance(attribution, str) and attribution.startswith("metadata/") and not (root / attribution).is_file():
                    raise ValueError("Missing portable attribution")
                for row in training_rows(item["record"]):
                    db.execute("INSERT INTO expected(id,value) VALUES (?,?)", (row["id"], canonical(row)))
        db.commit()
        for name in (manifest["unresolved_file"], manifest["exclusions_file"]):
            with gzip.open(root / name, "rt", encoding="utf-8") as handle:
                for line in handle:
                    item = json.loads(line)
                    if set(item) - {"id", "status", "attempts", "error", "disposition", "gate_reasons", "audit"}:
                        raise ValueError("Excluded full text/provenance in package")
        for shard in manifest["data_files"]:
            count = 0
            with gzip.open(root / shard["file"], "rt", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    if any(key in row for key in ("audit_context", "provenance", "audit", "original", "reference")):
                        raise ValueError("Auditor metadata in training data")
                    expected = db.execute("SELECT value,seen FROM expected WHERE id=?", (row["id"],)).fetchone()
                    if expected is None or expected[1] or canonical(row) != expected[0]:
                        raise ValueError("Missing, duplicated or altered student view")
                    db.execute("UPDATE expected SET seen=1 WHERE id=?", (row["id"],))
                    count += 1
            if count != shard["rows"]:
                raise ValueError("Shard count mismatch")
            total += count
        if db.execute("SELECT count(*) FROM expected WHERE seen=0").fetchone()[0] or total != manifest["counts"]["training_rows"]:
            raise ValueError("Missing direction/view or row count mismatch")
        if not total and manifest.get("upload_ready") is not False:
            raise ValueError("Empty package cannot be upload ready")
        db.close()
    return {"valid": True, "component": manifest["component"], "rows": total}


if __name__ == "__main__":
    print(json.dumps(validate(Path(__file__).resolve().parent)))
