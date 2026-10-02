"""Refreshable CPU-only review snapshots; no teacher calls or implicit acceptance."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from .catalog import config
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import Queue, audit_payload, validate_audit
from .pilot import require_pilot
from .records import validate_messages
from .norwegian_inclusive import authorized_language as authorized_norwegian_language
from .scandi_admission import authorized_language as authorized_scandi_language
from .audit_gates import CrossScreen, pinned_screen

VERSION = 1
ORIGINAL = ("dala-en", "dala-nl", "ultrachat-nl", "dolci-nl", "dolci-pl", "dolci-sv")
TRANSFORMS = ("dynaword-nl", "dynaword-no", "dynaword-sv", "dynaword-is", "dynaword-fo", "dynaword-pl")
PENDING = {
    "reordering-integration": "Await reconciled native paragraphs and explicitly labelled synthetic blocks; do not sum alternative runs.",
    "additional-dala": "Await complete split/provenance manifests from the other-thread additions.",
    "norwegian-variant-holds": "Await variant disposition; do not promote ambiguous held constituents.",
    "cross-source-screening": "Await full available inherited/held-out review; preparation is not decontamination.",
    "identity": "Existing identity generation pilot is separate; no identity generation or audit executed here.",
    "pllumic-syn": "Explicitly deferred by owner; non-blocking, no access retry.",
    "scandi-instruct": "No cleared rows; excluded pending constituent/variant/held-out review or explicit disposition.",
    "danish-increments": "Pinned comparison found zero new eligible rows; no audit jobs to stage.",
}


def version_key(path):
    return tuple(int(v) for v in re.findall(r"\d+", str(path)))


def source_entry(component, path, receipt_path, sha256=None, family="instruction", evidence=()):
    receipt = load(receipt_path)
    return {"component": component, "family": family, "path": str(Path(path).resolve()),
            "sha256": sha256 or receipt.get("sha256") or receipt.get("candidates_sha256"),
            "receipt": str(Path(receipt_path).resolve()), "receipt_sha256": file_hash(receipt_path),
            "preparation_counts": receipt.get("counts", {}),
            "evidence": [{"path": str(Path(p).resolve()), "sha256": file_hash(p)} for p in evidence]}


def discover(root, integration_paths=()):
    """Only explicit completed routes; never glob raw downloads or alternative repairs."""
    root = Path(root)
    sources, pending = [], dict(PENDING)
    cpu = load(root / "cpu-preparation.json") if (root / "cpu-preparation.json").exists() else {}
    for name in ORIGINAL + TRANSFORMS:
        receipt = root / "candidates" / name / "receipt.json"
        if not receipt.exists() or (name in ORIGINAL and cpu.get(name, {}).get("tokenization") != "complete"):
            pending[name] = "Preparation incomplete or missing completion receipt"
            continue
        sources.append(source_entry(name, receipt.parent / "candidates.jsonl", receipt,
                                    family="transformation" if name in TRANSFORMS else "instruction"))
    for receipt in sorted((root / "candidates").glob("opus-*/receipt.json")):
        if not load(receipt).get("sha256"):
            pending[receipt.parent.name] = "Missing candidate checksum"
            continue
        sources.append(source_entry(receipt.parent.name, receipt.parent / "candidates.jsonl", receipt, family="translation"))
    expected_pairs = {"-".join(sorted((a, b))) for i, a in enumerate(("da", "nl", "nb", "nn", "sv", "is", "fo", "pl"))
                      for b in ("da", "nl", "nb", "nn", "sv", "is", "fo", "pl")[i + 1:]}
    expected_pairs.update("en-" + lang for lang in ("nl", "nb", "nn", "sv", "pl"))
    present = {s["component"][5:] for s in sources if s["family"] == "translation"}
    for pair in sorted(expected_pairs - present):
        if pair == "fo-nl" and "fo-nl-english-anchor" in present:
            continue
        pending["opus-" + pair] = "No completed direct-pair candidate receipt"
    for name in ("dyna-instruct-is", "dyna-instruct-fo"):
        eligible = []
        for receipt in sorted(root.glob(f"island-instruct-unaudited-v*/{name}/receipt.json"), key=version_key):
            if (receipt.parent / "tokenized_unaudited" / "completion.json").exists():
                eligible.append(receipt)
        if eligible:
            receipt = eligible[-1]
            sources.append(source_entry(name, receipt.parent / "candidates.jsonl", receipt,
                                        evidence=[receipt.parent / "tokenized_unaudited" / "completion.json"]))
        else:
            pending[name] = "No completed island candidate/tokenization receipt"
    for name, relative in (("pllum-align", "staging-20260924-v1"),
                           ("pllumic", "pllumic-access-20260924/staging-main-v1")):
        receipt = root / "polish_unaudited" / relative / "receipt.json"
        if receipt.exists() and load(receipt).get("state") == "complete_unaudited":
            sources.append(source_entry(name, receipt.parent / "candidates.jsonl", receipt))
        else:
            pending[name] = "No completed Polish staging receipt"
    norwegian = [p for p in sorted(root.glob("norwegian-*/preparation-receipt.json"), key=version_key)
                 if load(p).get("status") == "complete_unaudited_staging"]
    if norwegian:
        receipt = norwegian[-1]
        for entry in load(receipt)["files"]:
            if entry["path"].startswith("staging_unaudited/") and entry["path"].endswith(".jsonl"):
                constituent = Path(entry["path"]).parts[1]
                sources.append(source_entry("norwegian-" + constituent, receipt.parent / entry["path"],
                                            receipt, entry["sha256"]))
    else:
        pending["norwegian"] = "No completed Norwegian preparation receipt"
    for path in integration_paths:
        manifest = load(path)
        if manifest.get("status") != "complete_unaudited" or manifest.get("version") != 1:
            pending[str(path)] = "Integration not complete_unaudited version 1; no partial sources consumed"
            continue
        additions = []
        for entry in manifest.get("components", []):
            candidate = source_entry(entry["component"], entry["path"], entry["receipt"],
                                     family=entry["family"], evidence=[path, *entry.get("evidence", [])])
            if candidate["sha256"] != entry["sha256"] or not candidate["sha256"]:
                raise ValueError("Integration checksum must match its completed candidate receipt")
            if file_hash(candidate["path"]) != candidate["sha256"]:
                raise ValueError("Integration candidate checksum mismatch")
            additions.append(candidate)
        if not additions:
            pending[str(path)] = "Empty integration manifest"
            continue
        replaced = set(manifest.get("supersedes", []))
        sources = [s for s in sources if s["component"] not in replaced] + additions
        for name in manifest.get("resolves", []):
            pending.pop(name, None)
    keys = [s["component"] for s in sources]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate component keys; use explicit supersedes in integration manifest")
    return sorted(sources, key=lambda s: s["component"]), pending


def stratum(row):
    language, task = row["language"], row["task"]
    provenance = row["provenance"]
    constituent = provenance.get("constituent") or provenance.get("corpus")
    if not constituent:
        parts = Path(provenance.get("file", "unknown")).parts
        constituent = parts[-2] if len(parts) > 1 else parts[-1]
    tokens = row.get("rendered_tokens", 0)
    length = "short" if tokens < 256 else "medium" if tokens < 1024 else "long"
    turns = "multi" if sum(m.get("role") == "assistant" for m in row["messages"]) > 1 else "single"
    label = row["messages"][-1].get("content", "").strip() if task == "acceptability" else ""
    return (language, row.get("reverse_language", ""), task, str(constituent), length, turns, label)


def select_samples(heaps, limit):
    """Round robin over language/task groups, then constituent/length/turn strata."""
    groups = defaultdict(list)
    for key, heap in sorted(heaps.items()):
        groups[(key[0], key[1], key[2])].append(sorted(heap, key=lambda x: -x[0]))
    ordered = {}
    for key, buckets in groups.items():
        ordered[key] = [bucket[rank][2] for rank in range(max(map(len, buckets)))
                        for bucket in buckets if rank < len(bucket)]
    selected = []
    for rank in range(max((len(v) for v in ordered.values()), default=0)):
        for key in sorted(ordered):
            if rank < len(ordered[key]):
                selected.append(ordered[key][rank])
                if len(selected) == limit:
                    return selected
    return selected


def inspect_source(args):
    source, limit, seed, cache_dir, languages = args
    path = Path(source["path"])
    before = path.stat()
    if not source["sha256"] or file_hash(path) != source["sha256"]:
        raise ValueError("Candidate checksum mismatch: " + str(path))
    if file_hash(source["receipt"]) != source["receipt_sha256"]:
        raise ValueError("Receipt changed during discovery")
    cache = Path(cache_dir) / (digest([VERSION, file_hash(__file__), source, limit, seed]) + ".json")
    if cache.exists():
        return load(cache)
    heaps, counts, strata = {}, Counter(rows_scanned=0), Counter()
    language_tasks = Counter()
    for ordinal, row in enumerate(rows(path)):
        counts["rows_scanned"] += 1
        if ((row.get("language") not in languages and not authorized_norwegian_language(row) and not authorized_scandi_language(row))
                or ("reverse_language" in row and row["reverse_language"] not in languages)
                or row.get("provenance", {}).get("split") in ("test", "validation", "dev")
                or row.get("accepted") is True):
            raise ValueError("Unexpected language, held-out split or accepted row in " + str(path))
        key = stratum(row)
        strata[key] += 1
        language_tasks[(key[0], key[1], key[2])] += 1
        # Bounded per-stratum bottom-k samples span the whole file, not its prefix.
        rank = int(hashlib.sha256(f"{seed}:{source['component']}:{ordinal}:{row['id']}".encode()).hexdigest()[:16], 16)
        heap = heaps.setdefault(key, [])
        if len(heap) < limit or rank < -heap[0][0]:
            item = (-rank, ordinal, {"row": row, "ordinal": ordinal, "stratum": list(key)})
            if len(heap) < limit:
                heapq.heappush(heap, item)
            else:
                heapq.heapreplace(heap, item)
    if (before.st_size, before.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError("Candidate changed while sampling")
    selected = select_samples(heaps, limit)
    for item in selected:
        validate_record(item["row"], languages)
    covered = {tuple(item["stratum"]) for item in selected}
    result = {"source": source, "counts": dict(counts), "selected": selected,
              "language_tasks": [{"language": k[0], "reverse_language": k[1], "task": k[2], "rows": v}
                                 for k, v in sorted(language_tasks.items())],
              "strata": [{"key": list(k), "rows": v, "represented": k in covered} for k, v in sorted(strata.items())],
              "unrepresented_strata": len(set(strata) - covered)}
    write_json(cache, result)
    return result


def validate_record(record, languages):
    validate_messages(record["messages"])
    if (record.get("language") not in languages and not authorized_norwegian_language(record) and not authorized_scandi_language(record)) or not isinstance(record.get("provenance"), dict):
        raise ValueError("Missing language or provenance")
    target = record.get("target_message_index")
    if target is not None and (type(target) is not int or not 0 <= target < len(record["messages"])
                               or record["messages"][target]["role"] != "assistant"):
        raise ValueError("Invalid assistant target index")
    if "reverse_messages" in record:
        validate_messages(record["reverse_messages"])
        if record.get("reverse_language") not in languages:
            raise ValueError("Missing reverse language")
    if record["task"] in ("denoising", "prefix-continuation", "span-filling", "paragraph-reordering", "block-reordering", "text-block-reordering"):
        if not record.get("audit_context"):
            raise ValueError("Transformation has no reference audit context")


def student_views(record):
    """Only model-visible fields; annotations and references never enter student text."""
    first = {"id": record["id"], "messages": [{"role": m["role"], "content": m["content"]} for m in record["messages"]]}
    if "target_message_index" in record:
        first["target_message_index"] = record["target_message_index"]
    if "reverse_messages" in record:
        first["id"] += ":forward"
    yield first
    if "reverse_messages" in record:
        yield {"id": record["id"] + ":reverse",
               "messages": [{"role": m["role"], "content": m["content"]} for m in record["reverse_messages"]]}


def refresh(root, output, workers=4, limit=100, integration_paths=(), crossscreen_path=None):
    if not 1 <= limit <= 100 or not 1 <= workers <= 16:
        raise ValueError("Review cap is 1..100 per component; CPU workers 1..16")
    cfg = config()
    output = Path(output).resolve()
    with lock(output / ".refresh.lock"):
        integrations = sorted(set(map(Path, integration_paths)) | set((output / "integrations").glob("*.json")))
        sources, pending = discover(root, integrations)
        screen = CrossScreen(crossscreen_path) if crossscreen_path else None
        settings = {"version": VERSION, "model": cfg["model"], "languages": cfg["languages"], "seed": cfg["seed"],
                    "limit_per_component": limit, "sources": sources, "pending": pending,
                    "crossscreen": screen.descriptor() if screen else None,
                    "implementation_sha256": file_hash(__file__)}
        snapshot_id = digest(settings)
        snapshots = output / "snapshots"
        snapshots.mkdir(exist_ok=True)
        destination = snapshots / snapshot_id
        cache = output / "cache"
        cache.mkdir(exist_ok=True)
        arguments = [(s, limit, cfg["seed"], str(cache), list(cfg["languages"])) for s in sources]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(inspect_source, arguments))
        # Re-check receipts after worker reads, including unchanged cached inputs.
        for source in sources:
            if file_hash(source["receipt"]) != source["receipt_sha256"]:
                raise ValueError("Preparation receipt changed; refresh again after completion")
        if destination.exists():
            prior = load(destination / "manifest.json")
            if (file_hash(destination / "review_only" / "audit_records.jsonl") != prior["review_records_sha256"]
                    or file_hash(destination / "review_only" / "student_views.jsonl") != prior["student_views_sha256"]):
                raise ValueError("Existing immutable snapshot is corrupt")
            write_json(output / "latest.json", {"snapshot": str(destination), "snapshot_id": snapshot_id})
            return prior
        with tempfile.TemporaryDirectory(dir=snapshots) as temporary:
            build = Path(temporary) / "snapshot"
            review = build / "review_only"
            review.mkdir(parents=True)
            queue = Queue(build / "staged_jobs.sqlite")
            overview, total, students, excluded = [], 0, 0, []
            try:
                with (review / "audit_records.jsonl").open("w") as metadata, (review / "student_views.jsonl").open("w") as student:
                    for result in results:
                        source = result["source"]
                        kept = 0
                        for item in result["selected"]:
                            row = dict(item["row"])
                            row["source_record_id"] = row["id"]
                            row["id"] = digest([source["component"], source["sha256"], item["ordinal"], row["id"]])
                            row["component"] = source["component"]
                            row["audit_status"] = "pending"
                            row["accepted"] = False
                            row["readiness"] = {"source_sha256": source["sha256"], "ordinal": item["ordinal"],
                                                "stratum": item["stratum"], "scope": "review_sample_not_corpus_acceptance"}
                            if screen:
                                reasons = screen.reasons(row)
                                if reasons:
                                    excluded.append({"id": row["id"], "source_record_id": row["source_record_id"],
                                                     "component": row["component"], "reasons": reasons})
                                    continue
                                row["readiness"]["crossscreen_covered"] = screen.covered(source)
                            payload = audit_payload(row, cfg["model"])
                            job = queue.add("audit-staged", payload)
                            metadata.write(json.dumps({"audit_job": job, "record": row}, ensure_ascii=False) + "\n")
                            for view in student_views(row):
                                student.write(json.dumps(view, ensure_ascii=False) + "\n")
                                students += 1
                            total += 1
                            kept += 1
                        overview.append({k: v for k, v in result.items() if k != "selected"} |
                                        {"review_records": kept, "pre_gate_review_records": len(result["selected"]),
                                         "crossscreen_covered": screen.covered(source) if screen else False})
                        print("REVIEW", source["component"], result["counts"]["rows_scanned"], kept, flush=True)
            finally:
                queue.close()
            try:
                require_pilot(Path(root), cfg)
                pilot = "approved_but_no_jobs_activated"
            except ValueError:
                pilot = "required_before_activation"
            manifest = settings | {"snapshot_id": snapshot_id, "snapshot": str(destination), "created_at": datetime.now(timezone.utc).isoformat(),
                "review_exclusions": excluded,
                "components": overview, "review_records": total, "student_views": students, "pilot_gate": pilot,
                "queue_stage": "audit-staged", "accepted": False, "final_sampling": False,
                "runnable_audit_jobs": 0, "full_corpus_audit": "not_enqueued; source manifests only",
                "review_records_sha256": file_hash(review / "audit_records.jsonl"),
                "student_views_sha256": file_hash(review / "student_views.jsonl")}
            write_json(build / "manifest.json", manifest)
            report = ["# DFM12 Audit Readiness", "", f"Snapshot: {snapshot_id}",
                      f"Components: {len(sources)}; staged review records: {total}; student views: {students}.",
                      f"Pilot: {pilot}. No GPU work, accepted exports or final sampling.", "",
                      "| Component | Candidate rows | Review rows | Unrepresented strata |", "| --- | ---: | ---: | ---: |"]
            report.extend(f"| {r['source']['component']} | {r['counts']['rows_scanned']} | {r['review_records']} | {r['unrepresented_strata']} |" for r in overview)
            report += ["", "## Pending Integration", ""] + [f"- {k}: {v}" for k, v in pending.items()]
            report += ["", "Review coverage is not corpus acceptance. Refresh after integration receipts change.",
                       "Use this module's gated export: generic DFM12 export currently drops target_message_index."]
            (build / "REPORT.md").write_text("\n".join(report) + "\n")
            build.rename(destination)
        write_json(output / "latest.json", {"snapshot": str(destination), "snapshot_id": snapshot_id})
        return manifest


def verify_snapshot(snapshot):
    latest = snapshot.parent.parent / "latest.json"
    if latest.exists() and Path(load(latest)["snapshot"]).resolve() != snapshot.resolve():
        raise ValueError("Superseded readiness snapshot; use the latest refresh")
    manifest = load(snapshot / "manifest.json")
    if manifest.get("crossscreen"):
        pinned_screen(manifest["crossscreen"])
    for name, key in (("audit_records.jsonl", "review_records_sha256"), ("student_views.jsonl", "student_views_sha256")):
        if file_hash(snapshot / "review_only" / name) != manifest[key]:
            raise ValueError("Review snapshot changed")
    for source in manifest["sources"]:
        if file_hash(source["path"]) != source["sha256"] or file_hash(source["receipt"]) != source["receipt_sha256"]:
            raise ValueError("Source snapshot is stale; refresh before activation/export")
        for evidence in source["evidence"]:
            if file_hash(evidence["path"]) != evidence["sha256"]:
                raise ValueError("Integration/completion evidence changed")
    return manifest


def activate(snapshot, pilot_root):
    cfg = config()
    require_pilot(pilot_root, cfg)
    with lock(snapshot / ".activation.lock"):
        manifest = verify_snapshot(snapshot)
        if manifest["model"] != cfg["model"]:
            raise ValueError("Review model differs from current pilot model")
        queue = Queue(snapshot / "approved" / "jobs.sqlite")
        try:
            for item in rows(snapshot / "review_only" / "audit_records.jsonl"):
                queue.add("audit", audit_payload(item["record"], cfg["model"]))
            status = queue.status()
        finally:
            queue.close()
        write_json(snapshot / "approved" / "activation.json", {"snapshot_id": manifest["snapshot_id"],
                   "pilot_approval_sha256": file_hash(pilot_root / "pilot-approval.json"),
                   "status": status, "scope": "review_samples_only", "gpu_execution": False})
        return status


def export_accepted(snapshot, pilot_root, output):
    """Optional explicit accepted review subset; never promote unaudited remainder."""
    cfg = config()
    require_pilot(pilot_root, cfg)
    manifest = verify_snapshot(snapshot)
    screen = pinned_screen(manifest.get("crossscreen"))
    activation = load(snapshot / "approved" / "activation.json")
    if activation["snapshot_id"] != manifest["snapshot_id"] or manifest["model"] != cfg["model"]:
        raise ValueError("Mismatched activated review snapshot")
    if output.exists():
        raise FileExistsError(output)
    expected = {digest(["audit", audit_payload(item["record"], cfg["model"])]): item["record"]
                for item in rows(snapshot / "review_only" / "audit_records.jsonl")}
    database = snapshot / "approved" / "jobs.sqlite"
    db = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    accepted = []
    try:
        for key, encoded, decision in db.execute("SELECT id,payload,result FROM jobs WHERE stage='audit' AND status='done'"):
            payload, result = json.loads(encoded), json.loads(decision)
            if key not in expected or payload != audit_payload(expected[key], cfg["model"]):
                raise ValueError("Audit payload does not match immutable review record")
            validate_audit(result)
            if result["keep"]:
                validate_record(expected[key], cfg["languages"])
                source = next(s for s in manifest["sources"] if s["component"] == expected[key]["component"])
                if not screen.covered(source) or screen.reasons(expected[key]):
                    raise ValueError("Unresolved cross-screen coverage or row gate blocks accepted export")
                accepted.append((key, expected[key], result))
    finally:
        db.close()
    if not accepted:
        raise ValueError("No explicitly accepted completed audits")
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock(output.parent / ("." + output.name + ".lock")), tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        build = Path(temporary) / "accepted"
        (build / "data").mkdir(parents=True)
        (build / "metadata").mkdir()
        with (build / "data" / "conversations.jsonl").open("w") as student, (build / "metadata" / "audits.jsonl").open("w") as meta:
            for job, record, decision in accepted:
                for view in student_views(record):
                    student.write(json.dumps(view, ensure_ascii=False) + "\n")
                    meta.write(json.dumps({"id": view["id"], "audit_job": job, "audit": decision,
                                           "record": record}, ensure_ascii=False) + "\n")
        write_json(build / "metadata" / "manifest.json", {"scope": "accepted_audited_review_subset_only",
                   "accepted_audit_records": len(accepted), "snapshot_id": manifest["snapshot_id"],
                   "crossscreen": screen.descriptor(),
                   "final_sampling": False, "tokenization": "must_rebuild_from_this_accepted_subset"})
        build.rename(output)
    return {"accepted_audit_records": len(accepted), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    refresh_parser = commands.add_parser("refresh")
    refresh_parser.add_argument("--root", type=Path, default=Path("data/dfm12"))
    refresh_parser.add_argument("--output", type=Path, default=Path("data/dfm12/audit_readiness"))
    refresh_parser.add_argument("--workers", type=int, default=4)
    refresh_parser.add_argument("--limit", type=int, default=100)
    refresh_parser.add_argument("--integration-manifest", type=Path, action="append", default=[])
    refresh_parser.add_argument("--crossscreen-manifest", type=Path)
    for command in ("activate", "export-accepted"):
        sub = commands.add_parser(command)
        sub.add_argument("--snapshot", type=Path, required=True)
        sub.add_argument("--pilot-root", type=Path, default=Path("data/dfm12"))
        if command == "export-accepted":
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1")
    if args.command == "refresh":
        result = refresh(args.root, args.output, args.workers, args.limit, args.integration_manifest, args.crossscreen_manifest)
        print(json.dumps({k: result[k] for k in ("snapshot", "review_records", "student_views", "pilot_gate")}, indent=2))
    elif args.command == "activate":
        print(activate(args.snapshot, args.pilot_root))
    else:
        print(export_accepted(args.snapshot, args.pilot_root, args.output))


if __name__ == "__main__":
    main()
