"""Read-only identity audit integration; never uploads or changes shared inventories."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

import yaml

from . import export_validator
from .io import digest, file_hash, load, write_json
from .jobs import validate_audit
from .prepare import Renderer
from .records import chat_fingerprint, validate_messages

LANGUAGES = frozenset(("da", "en", "fo", "is", "nb", "nl", "nn", "pl", "sv"))
PROFILE = "xl-full-bp"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def descriptor(root, path, **extra):
    return {"file": str(path.relative_to(root)), "sha256": file_hash(path),
            "bytes": path.stat().st_size, **extra}


def jsonlines(path, items):
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=1) as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def pinned_renderer(run, metadata):
    pin = load(run / "training-template.json")
    info = load(metadata)["tokenizer_info"]
    require(pin["metadata_sha256"] == file_hash(metadata) and info == pin["tokenizer_info"],
            "Current student metadata differs from identity pin")
    require(info.get("enable_thinking") is False and pin["max_context"] == 4096,
            "Identity requires non-thinking 4096 context")
    require(file_hash(info["tokenizer_path"]) == pin["tokenizer_sha256"], "Tokenizer hash mismatch")
    require(file_hash(info["chat_template_path"]) == pin["template_sha256"]
            == file_hash(run / "student-chat-template.jinja"), "Template hash mismatch")
    return Renderer(info, 4096)


def inspect_snapshot(db, registry, renderer):
    """Fail closed on missing joins, provenance drift, incomplete work or duplicate keeps."""
    db.row_factory = sqlite3.Row
    jobs = {r["id"]: dict(r) for r in db.execute("SELECT * FROM jobs")}
    records = {r["job_id"]: dict(r) for r in db.execute("SELECT * FROM identity_records")}
    counts = Counter()
    accepted, exclusions = defaultdict(list), defaultdict(list)
    seen_ids, seen_chats, audited = set(), set(), set()
    for key, job in jobs.items():
        require(job["stage"] in {"generate", "audit-pilot", "audit-bulk"}, "Unexpected identity stage")
        require(job["status"] in ({"done", "failed"} if job["stage"] == "generate" else {"done"}),
                "Incomplete identity work")
        if job["stage"] != "generate":
            continue
        payload = json.loads(job["payload"])
        require(key == digest(["generate", payload]), "Generation source ID/hash mismatch")
        lang = payload["record"]["language"]
        require(lang in LANGUAGES, "Unsupported identity language")
        counts["generation_requests"] += 1
        if job["status"] == "failed":
            require(key not in records, "Failed generation has promoted record")
            counts["failed_generations"] += 1
            continue
        counts["generated"] += 1
        require(key in records, "Missing promoted generation")
    for key, item in records.items():
        require(key in jobs and jobs[key]["stage"] == "generate" and jobs[key]["status"] == "done",
                "Orphan identity record")
        gen = jobs[key]
        payload, result = json.loads(gen["payload"]), json.loads(gen["result"])
        record = json.loads(item["record"])
        lang, provenance = record["language"], record["provenance"]
        context = {"facts": registry["facts"], "profile": registry["profiles"][PROFILE], "sources": registry["sources"]}
        require(record["profile"] == PROFILE and record["task"] == "identity"
                and record["component"] == "identity-" + PROFILE and lang in LANGUAGES,
                "Identity profile/task/language mismatch")
        require(provenance["source"] == "mimir-identity" and provenance["facts_hash"] == digest(registry)
                and record["audit_context"] == context, "Identity fact provenance mismatch")
        require(record["id"] == digest([PROFILE, lang, provenance["slot"], context]), "Identity record ID mismatch")
        expected = dict(payload["record"], messages=result["messages"], component="identity-" + PROFILE,
                        rendered_tokens=record["rendered_tokens"])
        require(record == expected, "Generated conversation/source mismatch")
        validate_messages(record["messages"])
        spec = json.loads(payload["request"]["messages"][1]["content"])
        require(spec["grounding"] == context and spec["variation"] == provenance["slot"], "Generation grounding mismatch")
        require(all(m["role"] in {"user", "assistant"} for m in record["messages"])
                and sum(m["role"] == "user" for m in record["messages"]) == spec["user_turns"], "Identity turn mismatch")
        fingerprint = chat_fingerprint(record["messages"])
        if item["duplicate_of"] is not None:
            previous = records.get(item["duplicate_of"])
            require(item["audit_id"] is None and previous is not None and previous["duplicate_of"] is None
                    and chat_fingerprint(json.loads(previous["record"])["messages"]) == fingerprint,
                    "Invalid duplicate lineage")
            counts["duplicates"] += 1
            continue
        require(record["id"] not in seen_ids and fingerprint not in seen_chats, "Duplicate audited identity")
        seen_ids.add(record["id"])
        seen_chats.add(fingerprint)
        audit_id = item["audit_id"]
        require(audit_id in jobs and audit_id not in audited, "Missing or reused audit")
        audit = jobs[audit_id]
        require(audit["stage"] in {"audit-pilot", "audit-bulk"} and audit["status"] == "done", "Incomplete identity audit")
        audit_payload = json.loads(audit["payload"])
        require(audit_payload["record"] == record, "Audit/source record mismatch")
        original_stage = "audit-pilot" if provenance["slot"] < 20 else "audit-review-pending"
        require(audit_id == digest([original_stage, audit_payload]), "Audit payload hash mismatch")
        decision = json.loads(audit["result"])
        validate_audit(decision)
        audited.add(audit_id)
        counts["audit_done"] += 1
        if not decision["keep"]:
            counts["audit_rejected"] += 1
            exclusions[lang].append({"id": record["id"], "status": "done", "disposition": "audit_rejected",
                                     "gate_reasons": [], "audit": decision})
            continue
        tokens = renderer.count(record["messages"])
        require(type(record["rendered_tokens"]) is int and tokens == record["rendered_tokens"], "Identity render/token drift")
        accepted[lang].append({"id": record["id"], "status": "done", "record": record,
            "record_raw_json": item["record"], "audit": decision, "result_raw_json": audit["result"],
            "disposition": "accepted", "gate_reasons": [], "student_ids": [record["id"]],
            "export_provenance": dict(provenance, generation_job_id=key, audit_job_id=audit_id,
                source_record_sha256=digest(record), source_record_raw_sha256=hashlib.sha256(item["record"].encode()).hexdigest(),
                generation_payload_sha256=digest(payload), generation_result_sha256=digest(result),
                audit_payload_sha256=digest(audit_payload), audit_result_sha256=digest(decision),
                generator_model=payload["request"]["model"], auditor_model=audit_payload["request"]["model"]),
            "attempts": audit["attempts"], "owner": audit["owner"], "error": audit["error"]})
        counts["accepted"] += 1
        counts["rendered_tokens"] += tokens
    require(audited == {k for k, j in jobs.items() if j["stage"].startswith("audit-")}, "Orphan audit jobs")
    return accepted, exclusions, dict(counts)


def write_identity_companion(root, packages, source):
    """Seal owned files; parent must retain this descriptor in its root inventory."""
    root = Path(root)
    path = root / "metadata/identity-source-manifest.json"
    if path.exists():
        raise FileExistsError(path)
    value = {"schema": "dfm12-identity-source-v1", "source": source, "repeat": 10,
             "packages": packages,
             "owned_files": [descriptor(root, path) for package in packages
                             for path in sorted((root / package["name"]).rglob("*")) if path.is_file()]}
    write_json(path, value)
    return descriptor(root, path)


def verify_identity_source(root, companion, packages):
    """Strict preserved-source hook for the parent's incremental validate_previous.

    Pass inventory['identity_source_manifest'] and inventory['packages']; returns
    only the nine explicitly owned identity components. No source-root bypass.
    Parent must copy the companion unchanged and pin its descriptor when merging.
    """
    root = Path(root).resolve()
    require(companion["file"] == "metadata/identity-source-manifest.json", "Unexpected identity companion path")
    path = root / companion["file"]
    require(path.resolve().is_relative_to(root) and descriptor(root, path) == companion, "Identity companion hash mismatch")
    value = load(path)
    require(value["schema"] == "dfm12-identity-source-v1" and value["repeat"] == 10, "Identity companion schema mismatch")
    owned = value["packages"]
    names = {"dfm12-identity-" + PROFILE + "-" + lang for lang in LANGUAGES}
    require(len(owned) == 9 and {p["name"] for p in owned} == names, "Identity companion package scope mismatch")
    selected = [p for p in packages if p["component"].startswith("identity-")]
    require(sorted(selected, key=lambda p: p["name"]) == sorted(owned, key=lambda p: p["name"]),
            "Inventory identity ownership mismatch")
    paths = set()
    for item in value["owned_files"]:
        path = root / item["file"]
        require(Path(item["file"]).parts[0] in names and path.resolve().is_relative_to(root)
                and item["file"] not in paths and descriptor(root, path) == item, "Identity owned-file hash mismatch")
        paths.add(item["file"])
    actual = {str(p.relative_to(root)) for name in names for p in (root / name).rglob("*") if p.is_file()}
    require(paths == actual, "Identity file inventory mismatch")
    for package in owned:
        folder = root / package["name"]
        manifest = load(folder / "metadata/manifest.json")
        require(manifest["source"] == value["source"] and manifest["component"] == package["component"]
                and manifest["name"] == package["name"] and manifest["repeat"] == 10
                and manifest["physical_row_repetition"] == 1
                and manifest["counts"] == package["counts"], "Identity package provenance mismatch")
        require(export_validator.validate(folder)["rows"] == package["rows"] == package["accepted_records"],
                "Identity accepted count mismatch")
    return {p["component"]: p for p in owned}


def export_identity(run, output, *, metadata=Path("data/sampled_dfm11/metadata.json"), repeat=10):
    """Return upload-inventory-compatible packages in a NEW isolated root. No upload.

    Parent may combine returned package summaries after placing the named folders
    under its inventory root. This function never edits that shared manifest.
    """
    run, output, metadata = Path(run).resolve(), Path(output).resolve(), Path(metadata).resolve()
    require(type(repeat) is int and repeat == 10, "User-authorized identity repeat is 10")
    if output.exists():
        raise FileExistsError(output)
    renderer = pinned_renderer(run, metadata)
    registry = yaml.safe_load((run / "identity_facts.yaml").read_text())
    bulk = load(run / "bulk-audit-authorization.json")
    require(bulk["facts_sha256"] == file_hash(run / "identity_facts.yaml")
            == load(run / "enqueue.json")["facts_sha256"], "Fact registry file hash mismatch")
    require(bulk["training_template_pin_sha256"] == file_hash(run / "training-template.json"), "Student pin receipt mismatch")
    require(bulk["review_sha256"] == file_hash(run / "bulk-pilot-review.json"), "Pilot review hash mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".identity-export-", dir=output.parent) as temp:
        root = Path(temp) / "export"
        (root / "metadata").mkdir(parents=True)
        snapshot = root / "metadata/identity-snapshot.sqlite"
        source_hash = file_hash(run / "jobs.sqlite")
        with sqlite3.connect((run / "jobs.sqlite").as_uri() + "?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot) as db:
                source.backup(db)
        with sqlite3.connect(snapshot) as db:
            cohort = [[k, digest(json.loads(p))] for k, p in db.execute("SELECT id,payload FROM jobs WHERE stage='audit-bulk' ORDER BY id")]
            require(cohort == bulk["cohort"] and len(cohort) == bulk["count"], "Bulk cohort hash mismatch")
            pilot = db.execute("SELECT id,payload,result FROM jobs WHERE stage='audit-pilot' ORDER BY id").fetchall()
            require(digest(pilot) == load(run / "bulk-pilot-review.json")["pilot_sha256"], "Pilot cohort hash mismatch")
            accepted, exclusions, counts = inspect_snapshot(db, registry, renderer)
        require(set(accepted) == LANGUAGES, "Missing accepted identity language")
        require(source_hash == file_hash(run / "jobs.sqlite"), "Source database changed during export")
        source = {"kind": "generated_identity", "profile": PROFILE, "sha256": file_hash(snapshot),
                  "original_database_sha256": source_hash, "facts_sha256": bulk["facts_sha256"],
                  "facts_hash": digest(registry), "references": registry["sources"],
                  "bulk_authorization_sha256": file_hash(run / "bulk-audit-authorization.json"),
                  "pilot_review_sha256": bulk["review_sha256"], "training_template_pin_sha256": bulk["training_template_pin_sha256"]}
        authorization = {"scope": "local_accepted_only_export", "date": "2026-09-25",
                         "authority": "Explicit user accepted-only export/upload authorization including identity",
                         "supersedes": "Historical accepted_exports_allowed=false for this completed cohort",
                         "upload_performed": False, "upload_orchestrator": "parent", "public": True,
                         "human_approval": False, "native_speaker_certification": False}
        packages = []
        for lang in sorted(accepted):
            component = "identity-" + PROFILE + "-" + lang
            name = "dfm12-" + component
            folder = root / name
            (folder / "data").mkdir(parents=True)
            (folder / "metadata").mkdir()
            items = sorted(accepted[lang], key=lambda r: r["id"])
            for item in items:
                item["export_provenance"].update(source_snapshot_sha256=source["sha256"],
                    facts_file_sha256=source["facts_sha256"], attribution="metadata/identity_facts.yaml")
            jsonlines(folder / "data/train-00000.jsonl.gz", (row for item in items for row in export_validator.training_rows(item["record"])))
            jsonlines(folder / "metadata/audits.jsonl.gz", items)
            jsonlines(folder / "metadata/exclusions.jsonl.gz", exclusions[lang])
            jsonlines(folder / "metadata/audit_unresolved.jsonl.gz", [])
            # Review findings can contain rejected text: publish their hashes, not that local evidence file.
            for evidence in ("identity_facts.yaml", "training-template.json", "student-chat-template.jinja"):
                shutil.copyfile(run / evidence, folder / "metadata" / evidence)
            write_json(folder / "metadata/source.json", source)
            shutil.copyfile(export_validator.__file__, folder / "validate_dataset.py")
            tokens = sum(item["record"]["rendered_tokens"] for item in items)
            package_counts = {"accepted": len(items), "audit_rejected": len(exclusions[lang]), "training_rows": len(items), "rendered_tokens": tokens}
            manifest = {"component": component, "name": name, "counts": package_counts,
                "data_files": [descriptor(folder, folder / "data/train-00000.jsonl.gz", rows=len(items))],
                "metadata_files": [descriptor(folder, p) for p in sorted((folder / "metadata").iterdir())],
                "audit_file": "metadata/audits.jsonl.gz", "exclusions_file": "metadata/exclusions.jsonl.gz",
                "unresolved_file": "metadata/audit_unresolved.jsonl.gz", "source": source,
                "languages": {lang: len(items)}, "authorization": authorization, "repeat": repeat,
                "effective_tokens_per_epoch": tokens * repeat, "physical_row_repetition": 1,
                "upload_performed": False, "hf_repo_id": None, "public": True,
                "hf_ready": True, "upload_ready": True, "snapshot_sha256": source["sha256"],
                "admission_status": "local_user_authorized_accepted_only_automated_audit",
                "license_policy": "User-authorized generated identity release; factual references retained; no blanket relicensing asserted",
                "final_sampling": False, "student_schema": "native full messages; attribution and audits in metadata only"}
            write_json(folder / "metadata/manifest.json", manifest)
            (folder / "README.md").write_text("---\nlanguage:\n- " + lang + "\ntask_categories:\n- text-generation\nconfigs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train-*.jsonl.gz\n---\n# " + name + "\n\n"
                "Local-only accepted subset; no upload performed or Hub repository assigned.\n\n"
                f"{len(items)} distinct full conversations; repeat {repeat} is training-mixture metadata, not duplicated rows.\n\n"
                "Generated Mimir XL full-backpropagation identity conversations, accepted by automated Gemma audits. "
                "Not human or native-speaker certified. Historical v1 claims remain qualified. "
                "Fact registry, primary-source references, profile and per-record hashes are in metadata/. "
                "Only data/ is training input. User-authorized public release; no blanket relicensing of references is asserted.\n")
            validation = export_validator.validate(folder)
            packages.append({"name": name, "component": component, "rows": len(items), "accepted_records": len(items),
                "counts": package_counts, "data_bytes": sum(p["bytes"] for p in manifest["data_files"]),
                "package_bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()),
                "status": manifest["admission_status"], "validation": validation, "repeat": repeat})
        report = {"packages": packages, "counts": counts, "rows": counts["accepted"], "repeat": repeat,
                  "rendered_tokens": counts["rendered_tokens"], "effective_tokens_per_epoch": counts["rendered_tokens"] * repeat,
                  "data_bytes": sum(p["data_bytes"] for p in packages), "package_bytes": sum(p["package_bytes"] for p in packages),
                  "source": source, "authorization": authorization, "upload_performed": False,
                  "audit_roots": [str(run)], "snapshot": "metadata/identity-snapshot.sqlite",
                  "api": "dfm12.export_identity.export_identity(run, output, metadata=..., repeat=10)",
                  "integration": "Parent places named package folders under its inventory root and merges package summaries; never upload root metadata",
                  "completed": True, "final_sampling": False}
        report["identity_source_manifest"] = write_identity_companion(root, packages, source)
        verify_identity_source(root, report["identity_source_manifest"], packages)
        write_json(root / "manifest.json", report)
        root.rename(output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, default=Path("data/sampled_dfm11/metadata.json"))
    args = parser.parse_args()
    result = export_identity(args.run, args.output, metadata=args.metadata)
    print(json.dumps({k: result[k] for k in ("rows", "counts", "rendered_tokens", "effective_tokens_per_epoch")}, indent=2))
