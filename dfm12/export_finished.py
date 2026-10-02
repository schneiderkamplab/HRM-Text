"""Explicit local-only accepted exports from frozen, finished audit components."""
import argparse
from collections import Counter
import copy
import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import time

from .audit_gates import CrossScreen
from .audit_readiness import student_views, validate_record
from .audit_full import validate_sources
from .io import digest, file_hash, load, lock, write_json
from .jobs import validate_audit
from .export_validator import validate as validate_package
from .export_licenses import enrich

LANGUAGES = {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl"}


def read_database(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=30)


def freeze(run, output, exclude=(), authorization=None, crossscreen=None, dala_authorization=None):
    """Finished terminal rows are immutable to the auditor; copy in short reads."""
    plan_hash = file_hash(run / "sources.json")
    plan = load(run / "sources.json")
    if dala_authorization is not None:
        validate_sources(plan["sources"], authorization, run, crossscreen, dala_authorization=dala_authorization)
    else:
        validate_sources(plan["sources"], authorization, run, crossscreen)
    validate_inclusion_scope(plan["sources"], run, crossscreen)
    live = read_database(run / "jobs.sqlite")
    started = time.time()
    live.execute("BEGIN")
    active = {row[0] for row in live.execute("SELECT component FROM jobs WHERE status IN ('pending','running','parked')")}
    eligible = {row[0]: {"sha256": row[1], "cursor": row[2], "input_rows": row[3], "queued": row[4], "quarantined": row[5]}
                for row in live.execute("SELECT component,sha256,cursor,input_rows,queued,quarantined FROM sources WHERE complete=1")
                if row[0] not in active and row[0] not in exclude}
    cap = live.execute("SELECT coalesce(max(rowid),0) FROM jobs").fetchone()[0]
    quarantine_cap = live.execute("SELECT coalesce(max(rowid),0) FROM quarantine").fetchone()[0]
    live.execute("COMMIT")
    transaction_seconds = time.time() - started
    sources = [source for source in plan["sources"] if source["component"] in eligible]
    for source in sources:
        state = eligible[source["component"]]
        if state["sha256"] != source["sha256"] or state["cursor"] + 1 != state["input_rows"]:
            raise ValueError("Source snapshot/cursor mismatch")
    if len(sources) != len(eligible):
        raise ValueError("Unpinned source found")
    frozen = sqlite3.connect(output / "snapshot.sqlite")
    frozen.executescript("""
    CREATE TABLE jobs(id TEXT PRIMARY KEY,component TEXT,record TEXT,status TEXT,attempts INTEGER,owner TEXT,result TEXT,error TEXT);
    CREATE INDEX components ON jobs(component);
    CREATE TABLE quarantine(id TEXT PRIMARY KEY,component TEXT,record TEXT,reasons TEXT);
    CREATE INDEX quarantine_components ON quarantine(component);
    """)
    counts = Counter()
    for table, columns, maximum in (("jobs", "id,component,record,status,attempts,owner,result,error", cap),
                                     ("quarantine", "id,component,record,reasons", quarantine_cap)):
        cursor = 0
        while cursor < maximum:
            keys = live.execute(f"SELECT rowid,component FROM {table} WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT 256",
                                 (cursor, maximum)).fetchall()
            if not keys:
                break
            selected = [key for key, component in keys if component in eligible]
            batch = live.execute(f"SELECT rowid,{columns} FROM {table} WHERE rowid IN ({','.join('?' for _ in selected)}) ORDER BY rowid",
                                 selected).fetchall() if selected else []
            for row in batch:
                if row[2] not in eligible:
                    continue
                if table == "jobs" and row[4] not in ("done", "failed"):
                    raise ValueError("Finished source has nonterminal work")
                frozen.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in row[1:])})", row[1:])
                counts[(table, row[2])] += 1
            frozen.commit()
            cursor = keys[-1][0]
    live.close()
    frozen.close()
    for source in sources:
        component = source["component"]
        if counts[("jobs", component)] != eligible[component]["queued"] or counts[("quarantine", component)] != eligible[component]["quarantined"]:
            raise ValueError("Frozen source count mismatch")
    if file_hash(run / "sources.json") != plan_hash:
        raise ValueError("Audit source manifest changed during freeze")
    receipt = {"eligibility_time": started, "eligibility_transaction_seconds": transaction_seconds,
               "rowid_cap": cap, "sources": sources, "source_states": eligible,
               "snapshot_sha256": file_hash(output / "snapshot.sqlite"), "finished": time.time(),
               "source_manifest_sha256": plan_hash, "audit_root": str(run.resolve()),
               "policy": "complete_sources_terminal_immutable_rows_only_no_live_write"}
    write_json(output / "snapshot.json", receipt)
    return receipt


def views(record):
    paired = "reverse_messages" in record
    for index, row in enumerate(student_views(record)):
        row.update(language=record["reverse_language" if index else "language"], task=record["task"],
                   parent_pair_id=record.get("source_record_id", record["id"]) if paired else None,
                   direction=("reverse" if index else "forward") if paired else "native")
        yield row


def disposition(record, status, raw_result, screen, source):
    if status != "done":
        return "audit_unresolved", None, []
    try:
        result = json.loads(raw_result)
        validate_audit(result)
    except (ValueError, TypeError, AttributeError):
        return "audit_unresolved", None, ["invalid_audit_result"]
    if not result["keep"]:
        return "audit_rejected", result, []
    reasons = screen.reasons(record)
    if source.get("authoritative_filtered"):
        reasons = [r for r in reasons if r not in ("unresolved_duplicate_chat", "unresolved_shared_source_review")]
    try:
        validate_record(record, LANGUAGES)
    except (ValueError, KeyError, TypeError) as exc:
        reasons.append("invalid_record:" + str(exc))
    return ("gate_excluded" if reasons else "accepted"), result, reasons


def descriptor(root, path, **extra):
    return {"file": str(path.relative_to(root)), "sha256": file_hash(path), "bytes": path.stat().st_size, **extra}


def bundle_file(root, path, cache):
    path = Path(path).resolve()
    key = str(path)
    if key not in cache:
        checksum = file_hash(path)
        destination = root / "metadata/evidence" / (checksum + path.suffix)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(path, destination)
        cache[key] = str(destination.relative_to(root))
    return cache[key]


def portable_provenance(root, provenance, cache):
    value = copy.deepcopy(provenance)
    def walk(item):
        if isinstance(item, dict):
            for key, child in list(item.items()):
                if key == "attribution" and isinstance(child, str) and child.startswith("/"):
                    item[key] = bundle_file(root, child, cache)
                else:
                    walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return value


def build_package(snapshot, source, screen, authorization, root):
    component = source["component"]
    if not component or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in component):
        raise ValueError("Unsafe component name")
    destination = root / ("dfm12-" + component)
    build = root / (".building-dfm12-" + component)
    if destination.exists() or build.exists():
        raise FileExistsError("Refusing to overwrite export")
    (build / "data").mkdir(parents=True)
    (build / "metadata").mkdir()
    evidence_cache = {}
    evidence = []
    for path, expected in [(source["receipt"], source["receipt_sha256"])] + [
            (item["path"], item["sha256"]) for item in source.get("evidence", [])] + list(screen.evidence.items()) + [
            (item["path"], item["sha256"]) for item in authorization.get("scoped_evidence", [])]:
        if file_hash(path) != expected:
            raise ValueError("Pinned source/screen evidence changed")
        evidence.append({"original_path": str(path), "file": bundle_file(build, path, evidence_cache), "sha256": expected})
    db = read_database(snapshot / "snapshot.sqlite")
    counts, languages, licenses = Counter(), Counter(), Counter()
    data_files, shard, shard_count = [], None, 0
    audit_path = build / "metadata/audits.jsonl.gz"
    unresolved_path = build / "metadata/audit_unresolved.jsonl.gz"
    exclusions_path = build / "metadata/exclusions.jsonl.gz"
    def close_shard():
        if shard is not None:
            shard.close()
            data_files.append(descriptor(build, shard_path, rows=shard_count))
    with gzip.open(audit_path, "wt", encoding="utf-8", compresslevel=1) as audits, gzip.open(unresolved_path, "wt", encoding="utf-8", compresslevel=1) as unresolved, gzip.open(exclusions_path, "wt", encoding="utf-8", compresslevel=1) as exclusions:
        for key, encoded, status, attempts, owner, raw_result, error in db.execute(
                "SELECT id,record,status,attempts,owner,result,error FROM jobs WHERE component=? ORDER BY rowid", (component,)):
            record = json.loads(encoded)
            if (record["id"] != key or record.get("audit_source", {}).get("sha256") != source["sha256"]
                    or record.get("component", component) != component):
                raise ValueError("Audit source identity mismatch")
            decision, result, reasons = disposition(record, status, raw_result, screen, source)
            counts[decision] += 1
            if decision == "accepted":
                portable = portable_provenance(build, record["provenance"], evidence_cache)
                portable = enrich(portable, lambda p: bundle_file(build, p, evidence_cache))
                item = {"id": key, "status": status, "record": record, "record_raw_json": encoded,
                        "audit": result, "result_raw_json": raw_result, "attempts": attempts, "owner": owner,
                        "error": error, "disposition": decision, "gate_reasons": reasons,
                        "export_provenance": portable, "student_ids": []}
                licenses[str(portable.get("license", "unknown; see source evidence"))] += 1
                for row in views(record):
                    if shard is None or shard_count >= 50000:
                        close_shard()
                        shard_path = build / "data" / f"train-{len(data_files):05d}.jsonl.gz"
                        shard = gzip.open(shard_path, "wt", encoding="utf-8", compresslevel=1)
                        shard_count = 0
                    shard.write(json.dumps(row, ensure_ascii=False) + "\n")
                    shard_count += 1
                    counts["training_rows"] += 1
                    languages[row["language"]] += 1
                    item["student_ids"].append(row["id"])
                audits.write(json.dumps(item, ensure_ascii=False) + "\n")
            else:
                item = {"id": key, "status": status, "attempts": attempts, "error": error,
                        "disposition": decision, "gate_reasons": reasons, "audit": result}
                line = json.dumps(item, ensure_ascii=False) + "\n"
                exclusions.write(line)
                if decision == "audit_unresolved":
                    unresolved.write(line)
        for key, encoded, reasons in db.execute("SELECT id,record,reasons FROM quarantine WHERE component=?", (component,)):
            counts["preaudit_quarantine"] += 1
            exclusions.write(json.dumps({"id": key, "status": "quarantine",
                                        "disposition": "preaudit_quarantine", "gate_reasons": json.loads(reasons)}, ensure_ascii=False) + "\n")
    close_shard()
    db.close()
    shutil.copyfile(Path(__file__).with_name("export_validator.py"), build / "validate_dataset.py")
    manifest = {"component": component, "name": destination.name, "counts": dict(counts),
                "data_files": data_files, "metadata_files": [descriptor(build, path) for path in sorted((build / "metadata").rglob("*")) if path.is_file()],
                "audit_file": "metadata/audits.jsonl.gz", "unresolved_file": "metadata/audit_unresolved.jsonl.gz",
                "exclusions_file": "metadata/exclusions.jsonl.gz",
                "source": source, "evidence": evidence, "licenses_per_accepted_record": dict(licenses),
                "languages": dict(languages), "authorization": authorization,
                "snapshot_sha256": load(snapshot / "snapshot.json")["snapshot_sha256"],
                "upload_performed": False, "hf_repo_id": None,
                "admission_status": "local_user_authorized_accepted_only_automated_audit" if data_files else "empty_no_upload",
                "hf_ready": bool(data_files),
                "upload_ready": bool(data_files),
                "student_schema": "native_messages_only_plus_ids_language_task_target_index; full evidence in metadata"}
    manifest["counts"].setdefault("training_rows", 0)
    write_json(build / "metadata/manifest.json", manifest)
    header = "---\nconfigs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train-*.jsonl.gz\ntask_categories:\n- text-generation\n---\n\n" if data_files else "EMPTY ACCEPTED SUBSET: metadata only, not HF-ready; no upload.\n\n"
    (build / "README.md").write_text(header + "# " + destination.name +
        "\n\nLocal-only accepted subset; no upload performed or Hub repository assigned.\n"
        "Only completed kept decisions with all three scores at least 4 are included, after deterministic gates.\n"
        "Automated review is not native-speaker certification. Exclusion metadata contains only IDs/status/errors/scores/reasons, never excluded conversations.\n"
        "Full native messages and explicit assistant target indices are preserved. OPUS pairs produce both directions,\n"
        "linked by parent_pair_id; both directions share the same pair audit.\n"
        "Training input must use only messages and optional target_message_index. Accepted references, stored audit decisions,\n"
        "original provenance and portable attribution are under metadata, never concatenated into training messages.\n"
        "Full excluded records remain only in the separate, local non-upload snapshot, not this package.\n\n"
        "## Licensing and Attribution\n\nNo blanket license is asserted. Preserve the exact per-record source license, URL, title, history\n"
        "and attribution in metadata/audits.jsonl.gz (export_provenance). Local attribution files are bundled in\n"
        "metadata/evidence and referenced by relative paths. Original raw records remain unchanged for traceability.\n"
        "License labels among accepted records:\n\n" + "\n".join("- " + key + ": " + str(value) for key, value in sorted(licenses.items())) +
        "\n\n## Validation\n\nRun `python validate_dataset.py` using Python 3.9+; only the standard library is required.\n")
    validation = validate_package(build)
    build.rename(destination)
    return {"name": destination.name, "component": component, "rows": counts["training_rows"],
            "accepted_records": counts["accepted"], "counts": dict(counts),
            "data_bytes": sum(item["bytes"] for item in data_files),
            "package_bytes": sum(path.stat().st_size for path in destination.rglob("*") if path.is_file()),
            "status": manifest["admission_status"], "validation": validation}


def source_plans(runs):
    """Require explicit, unique root ownership; never infer another audit's pins."""
    result = {}
    for run in runs:
        for source in load(run / "sources.json")["sources"]:
            component = source["component"]
            if component in result:
                raise ValueError("Duplicate component across audit roots: " + component)
            result[component] = source
    return result


def validate_previous(output, previous, source_plan, identity_companion=None):
    identity = {}
    identity_source = None
    if identity_companion is not None:
        from .export_identity import verify_identity_source
        identity = verify_identity_source(output, identity_companion, previous)
        if set(identity) & set(source_plan):
            raise ValueError("Duplicate identity/audit-root source ownership")
        identity_source = load(output / identity_companion["file"])["source"]
    if len({p["component"] for p in previous}) != len(previous):
        raise ValueError("Duplicate previous component packages")
    for package in previous:
        if Path(package["name"]).name != package["name"] or package["name"] != "dfm12-" + package["component"]:
            raise ValueError("Unsafe existing package name")
        folder = output / package["name"]
        metadata = load(folder / "metadata/manifest.json")
        expected = identity_source if package["component"] in identity else source_plan.get(package["component"])
        if metadata["source"] != expected:
            raise ValueError("Existing exported source changed or owning --run omitted; refusing incremental replacement")
        for item in metadata["data_files"] + metadata["metadata_files"]:
            path = (folder / item["file"]).resolve()
            if not path.is_relative_to(folder.resolve()) or path.stat().st_size != item["bytes"] or file_hash(path) != item["sha256"]:
                raise ValueError("Existing package integrity mismatch: " + str(path))


def validate_inclusion_scope(sources, run, crossscreen):
    """Audit-only holds can be superseded operationally, never source/evidence pins."""
    from .scoped_inclusion_audit import SCANDI_COMPONENTS, NORWEGIAN_COMPONENTS, validate_screen
    names = {s["component"] for s in sources}
    scoped_names = SCANDI_COMPONENTS | NORWEGIAN_COMPONENTS
    if not names & scoped_names and (crossscreen is None or load(crossscreen).get("scope") != "user_scoped_inclusion_audit_only"):
        return
    if crossscreen is None:
        raise ValueError("Explicit scoped inclusion screen required")
    auth = validate_screen(crossscreen)
    expected = SCANDI_COMPONENTS if auth["family"] == "scandi" else NORWEGIAN_COMPONENTS
    if (names != expected or len(sources) != len(expected)
            or Path(auth["audit_root"]).resolve() != Path(run).resolve()
            or auth["pins"].get(str((Path(run) / "sources.json").resolve())) != file_hash(Path(run) / "sources.json")
            or {s["component"]: {"path": s["path"], "sha256": s["sha256"]} for s in sources} != auth["sources"]):
        raise ValueError("Scoped inclusion source ownership/pins mismatch")


def authorization_pins(auth):
    """Older Swedish receipts store descriptors, newer receipts use a mapping."""
    pins = auth.get("pins", {})
    if isinstance(pins, list):
        result = {}
        for item in pins:
            path, checksum = item["path"], item["sha256"]
            if path in result and result[path] != checksum:
                raise ValueError("Conflicting authorization pin: " + path)
            result[path] = checksum
        return result
    if not isinstance(pins, dict):
        raise ValueError("Invalid authorization pins")
    return dict(pins)


def export_contexts(runs, base_crossscreen, swedish=None, dala=(), inclusion=()):
    """Explicit per-root authorization; no discovery or blanket language exception."""
    base = CrossScreen(base_crossscreen)
    if getattr(base, "scoped", None) is not None:
        raise ValueError("Default crossscreen must be the unscoped original screen")
    contexts = {run: {"screen": base, "crossscreen": base_crossscreen, "swedish": None,
                      "dala": None, "evidence": [], "pins": {}} for run in runs}
    assigned = set()
    for kind, paths in (("swedish", [swedish] if swedish else []), ("dala", dala), ("inclusion", inclusion)):
        for path in paths:
            path = Path(path).resolve()
            auth = load(path)
            owner = Path(auth["audit_root"]).resolve()
            if owner not in contexts or owner in assigned:
                raise ValueError("Authorization root omitted or multiply authorized")
            assigned.add(owner)
            context = contexts[owner]
            context["evidence"].append({"path": str(path), "sha256": file_hash(path)})
            context["pins"].update(authorization_pins(auth))
            if kind == "inclusion":
                validate_inclusion_scope(load(owner / "sources.json")["sources"], owner, path)
                if not {s["component"] for s in load(owner / "sources.json")["sources"]}:
                    raise ValueError("Empty scoped source plan")
                context.update(screen=CrossScreen(path), crossscreen=path)
            else:
                context[kind] = path
    for run, context in contexts.items():
        sources = load(run / "sources.json")["sources"]
        validate_sources(sources, context["swedish"], run, context["crossscreen"], dala_authorization=context["dala"])
        validate_inclusion_scope(sources, run, context["crossscreen"])
    return contexts


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True,
                        help="Repeat for each owning audit root, including prior exports")
    parser.add_argument("--output", type=Path, default=Path("exports_dfm12"))
    parser.add_argument("--crossscreen", type=Path, required=True)
    parser.add_argument("--authorize-local-accepted-export", action="store_true", required=True)
    parser.add_argument("--incremental", action="store_true", help="Append newly finished sources; never replace existing packages")
    parser.add_argument("--completed-swedish-authorization", type=Path,
                        help="Pinned isolated Swedish audit authorization; not a blanket DaLA override")
    parser.add_argument("--completed-dala-authorization", type=Path, action="append", default=[],
                        help="Repeat for explicitly pinned completed DaLA roots, including PL/IS")
    parser.add_argument("--scoped-inclusion-authorization", type=Path, action="append", default=[],
                        help="Repeat with each Scandi/NorQuAD-FLEURS audit root's scoped-screen.json")
    parser.add_argument("--identity-source-manifest", type=Path,
                        help="Optional assertion of the identity companion path already pinned in the root manifest")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with lock(args.output / ".export.lock"):
        existing = load(args.output / "manifest.json") if args.incremental and (args.output / "manifest.json").exists() else None
        previous = existing["packages"] if existing else []
        runs = [p.resolve() for p in args.run]
        identity_companion = existing.get("identity_source_manifest") if existing else None
        if args.identity_source_manifest and (identity_companion is None or
                args.identity_source_manifest.resolve() != (args.output / identity_companion["file"]).resolve()):
            raise ValueError("Identity companion must be explicitly pinned in the existing root inventory")
        source_plan = source_plans(runs)
        validate_previous(args.output, previous, source_plan, identity_companion)
        pins = {str(run / name): file_hash(run / name) for run in runs
                for name in ("sources.json", "operational-approval.json")}
        if identity_companion:
            pins[str((args.output / identity_companion["file"]).resolve())] = identity_companion["sha256"]
        contexts = export_contexts(runs, args.crossscreen, args.completed_swedish_authorization,
                                   args.completed_dala_authorization, args.scoped_inclusion_authorization)
        for context in contexts.values():
            pins.update(context["screen"].evidence)
            pins.update(context["pins"])
            for item in context["evidence"]:
                if file_hash(item["path"]) != item["sha256"]:
                    raise ValueError("Scoped authorization evidence changed")
                pins[item["path"]] = item["sha256"]
        history = list(existing.get("snapshots", [existing["snapshot"]])) if existing else []
        result = {"snapshots": history, "packages": list(previous), "upload_performed": False,
                  "audit_roots": [str(run) for run in runs]}
        if identity_companion:
            result["identity_source_manifest"] = identity_companion
        for index, run in enumerate(runs):
            context = contexts[run]
            screen = context["screen"]
            snapshot = args.output / "metadata" / ("snapshot-" + time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f"-{index}")
            snapshot.mkdir(parents=True, exist_ok=False)
            authorization = {"scope": "local_accepted_only_export", "authorized_by": "explicit_user_instruction",
                         "time": time.time(), "upload_authorized": False,
                         "operation_only_override": "operational accepted_exports_allowed=false does not block this explicitly authorized export",
                         "auditor_approval_mutated": False, "audit_root": str(run),
                         "operational_approval_sha256": pins[str(run / "operational-approval.json")],
                         "source_manifest_sha256": pins[str(run / "sources.json")],
                         "scoped_evidence": context["evidence"],
                         "source_screen": screen.descriptor(), "retry_authorized": False}
            write_json(snapshot / "authorization.json", authorization)
            receipt = freeze(run, snapshot, {p["component"] for p in result["packages"]},
                             context["swedish"], context["crossscreen"], context["dala"])
            print("Frozen", str(run), "eligible components", len(receipt["sources"]), "short transaction seconds", receipt["eligibility_transaction_seconds"], flush=True)
            result.update(snapshot=str(snapshot), authorization=authorization)
            result["snapshots"].append(str(snapshot))
            for source in receipt["sources"]:
                if source != source_plan[source["component"]]:
                    raise ValueError("Source plan changed since preflight")
                package = build_package(snapshot, source, screen, authorization, args.output)
                result["packages"].append(package)
                write_json(args.output / "manifest.json", result)
                print(json.dumps(package), flush=True)
        result["rows"] = sum(p["rows"] for p in result["packages"])
        result["data_bytes"] = sum(p["data_bytes"] for p in result["packages"])
        result["package_bytes"] = sum(p["package_bytes"] for p in result["packages"])
        result["completed"] = time.time()
        write_json(args.output / "manifest.json", result)
        (args.output / "README.md").write_text("# DFM12 Accepted Exports\n\nFrozen eligible components only; publication status is in metadata/upload-receipts.json. See manifest.json and each package README.\n"
            "The root metadata/ directory is LOCAL ONLY, NOT FOR UPLOAD: its frozen snapshot includes full rejected/unresolved/quarantined records.\n"
            "OPUS rows include both directions; package bytes include audit/evidence metadata but exclude the shared frozen snapshot.\n\n"
            "| Package | Training rows | Compressed training bytes | Whole package bytes | Status |\n"
            "| --- | ---: | ---: | ---: | --- |\n" +
            "\n".join(f"| [{p['name']}]({p['name']}/README.md) | {p['rows']:,} | {p['data_bytes']:,} | {p['package_bytes']:,} | {p['status']} |" for p in result["packages"]) + "\n")
        for path, expected in pins.items():
            if file_hash(path) != expected:
                raise ValueError("Pinned approval/source/screen changed during export: " + path)
        print(json.dumps({k: result[k] for k in ("rows", "data_bytes", "package_bytes", "completed")}), flush=True)


if __name__ == "__main__":
    main()
