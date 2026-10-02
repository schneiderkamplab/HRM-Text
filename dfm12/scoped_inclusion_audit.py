"""Detached watcher for explicitly requested Scandi/NorQuAD/FLEURS audits only."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from .io import file_hash, load, lock, rows, write_json

SCOPE = "user_scoped_inclusion_audit_only"
BASE = Path("data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json").resolve()
PARENT = Path("data/dfm12/full-audit-20260924-v1").resolve()
ENDPOINTS = [f"http://127.0.0.1:{port}/v1" for port in range(8400, 8408)]
NORWEGIAN_COMPONENTS = {"norquad-wikipedia", "fleurs-alpaca-en-no"}
SCANDI_COMPONENTS = {"scandi-included-" + lang for lang in ("da", "nb", "nn", "sv", "no")}


def validate_provenance(family, component, record):
    provenance = record.get("provenance", {})
    if family == "norquad-fleurs":
        from .norwegian import REPO, REVISION
        expected_policy = "user_full_norquad_train_and_fleurs_eval_origin_inclusion_20260925"
        if (component not in NORWEGIAN_COMPONENTS or provenance.get("repo") != REPO
                or provenance.get("revision") != REVISION
                or provenance.get("constituent") != component
                or provenance.get("inclusion_policy") != expected_policy
                or provenance.get("benchmark_lineage", {}).get("explicit_user_inclusion") is not True
                or provenance.get("benchmark_lineage", {}).get("benchmarks_clear") is not False):
            raise ValueError("NorQuAD/FLEURS pinned source/lineage mismatch")
    else:
        from .scandi import REPO, REVISION
        from .scandi_admission import authorized_record
        if (component not in SCANDI_COMPONENTS or provenance.get("repo") != REPO
                or provenance.get("revision") != REVISION or not authorized_record(record)):
            raise ValueError("Scandi pinned repository mismatch")


def validate_screen(path):
    auth = load(path)
    if (auth.get("scope") != SCOPE or auth.get("user_authorized") is not True
            or auth.get("accepted_exports_allowed") is not False
            or auth.get("family") not in {"scandi", "norquad-fleurs"}
            or not auth.get("sources") or not auth.get("pins")
            or Path(auth["audit_root"]).resolve() != Path(path).resolve().parent):
        raise ValueError("Invalid source-scoped inclusion authorization")
    if auth["base_crossscreen"]["sha256"] != file_hash(auth["base_crossscreen"]["path"]):
        raise ValueError("Base cross-screen changed")
    if load(auth["base_crossscreen"]["path"]).get("scope") == SCOPE:
        raise ValueError("Nested scoped screens are not allowed")
    for filename, expected in auth["pins"].items():
        if file_hash(filename) != expected:
            raise ValueError("Scoped completed integration evidence changed: " + filename)
    return auth


def prepare(family, integration_path, output):
    from .audit_readiness import source_entry, validate_record
    integration_path, output = Path(integration_path).resolve(), Path(output).resolve()
    integration = load(integration_path)
    if integration.get("status") != "complete_unaudited" or integration.get("version") != 1:
        raise ValueError("Waiting for version 1 complete_unaudited integration")
    if not integration.get("components"):
        raise ValueError("No completed components")
    sources, counts, evidence = [], {}, {integration_path}
    for entry in integration["components"]:
        name = entry["component"]
        if not (name in SCANDI_COMPONENTS if family == "scandi" else name in NORWEGIAN_COMPONENTS):
            raise ValueError("Component outside named user scope: " + name)
        paths = [integration_path]
        for item in entry.get("evidence", []):
            if isinstance(item, dict):
                if file_hash(item["path"]) != item["sha256"]:
                    raise ValueError("Integration evidence checksum mismatch")
                paths.append(item["path"])
            else:
                paths.append(item)
        source = source_entry(name, entry["path"], entry["receipt"], entry["sha256"], entry["family"],
                              paths)
        if entry.get("receipt_sha256", source["receipt_sha256"]) != source["receipt_sha256"]:
            raise ValueError("Integration receipt checksum mismatch")
        if file_hash(source["path"]) != source["sha256"]:
            raise ValueError("Completed candidate checksum mismatch")
        receipt = load(source["receipt"])
        if receipt.get("accepted") is not False or receipt.get("status") != "complete_unaudited":
            raise ValueError("Expected unaudited candidates")
        count = Counter()
        for record in rows(source["path"]):
            validate_provenance(family, name, record)
            validate_record(record, {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl"})
            if record.get("accepted") is True:
                raise ValueError("Candidate already accepted")
            count["candidates"] += 1
            count["rendered_tokens"] += record.get("rendered_tokens", 0)
            if record.get("provenance", {}).get("split") in {"dev", "test", "validation"}:
                count["heldout_split_annotation_retained"] += 1
        if not count["candidates"]:
            raise ValueError("Empty component cannot establish audit execution")
        if receipt.get("counts", {}).get("candidates") != count["candidates"]:
            raise ValueError("Completed receipt candidate count mismatch")
        counts[name] = dict(count)
        if family == "scandi":
            from .scandi_admission import POLICY, AUTHORIZATION_SHA256
            if (integration.get("policy") != POLICY or integration.get("authorization_sha256") != AUTHORIZATION_SHA256
                    or receipt.get("policy") != POLICY or entry.get("authoritative_filtered") is not True):
                raise ValueError("Scandi scoped dedup completion policy mismatch")
            for filename in ("overlap-coverage.json", "overlap-resolutions.jsonl", "exclusions.jsonl"):
                proof = integration_path.parent / filename
                evidence.add(proof)
                source["evidence"].append({"path": str(proof), "sha256": file_hash(proof)})
            source["authoritative_filtered"] = True
        sources.append(source)
        evidence.add(Path(source["receipt"]))
        evidence.update(Path(e["path"]) for e in source["evidence"])
    if len({s["component"] for s in sources}) != len(sources):
        raise ValueError("Duplicate integration component")
    if family == "norquad-fleurs" and {s["component"] for s in sources} != NORWEGIAN_COMPONENTS:
        raise ValueError("Both requested Norwegian constituents must be completed")
    output.mkdir(parents=True, exist_ok=True)
    if (output / "sources.json").exists():
        if load(output / "sources.json")["sources"] != sources:
            raise ValueError("Cannot change existing scoped source snapshot")
    else:
        write_json(output / "sources.json", {"sources": sources, "accepted_exports_allowed": False})
    # Reuse actual prior operational findings without asserting review of these new rows.
    approval = load(PARENT / "operational-approval.json")
    approval["additional_source_authorization"] = {
        "scope": SCOPE, "family": family, "user_authorized": True,
        "new_source_human_review_complete": False,
        "basis": "User explicitly requested inclusion and queued automated audits of Scandi, NorQuAD and FLEURS; no acceptance authorization."}
    write_json(output / "operational-approval.json", approval)
    evidence.update((output / "sources.json", output / "operational-approval.json"))
    auth = {"scope": SCOPE, "family": family, "user_authorized": True,
            "accepted_exports_allowed": False, "audit_root": str(output),
            "known_heldout_override": "Only listed source hashes for automated audit; retain annotations; no benchmark-clean or human-review claim.",
            "base_crossscreen": {"path": str(BASE), "sha256": file_hash(BASE)},
            "sources": {s["component"]: {"path": s["path"], "sha256": s["sha256"]} for s in sources},
            "pins": {str(p): file_hash(p) for p in sorted(evidence)}, "counts": counts}
    write_json(output / "scoped-screen.json", auth)
    validate_screen(output / "scoped-screen.json")
    return counts


def launch(output):
    command = [sys.executable, "-u", "-m", "dfm12.audit_full", "--source-manifest", str(output / "sources.json"),
               "--operational-approval", str(output / "operational-approval.json"), "--crossscreen", str(output / "scoped-screen.json"),
               "--output", str(output), "--concurrency", "128", "--preparation-workers", "2", "--endpoints", *ENDPOINTS]
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1")
    with (output / "client.log").open("ab") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=environment)
    write_json(output / "launch.json", {"pid": process.pid, "command": command, "time": time.time(), "accepted_exports_allowed": False})
    return process


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / ".watcher.lock"), ThreadPoolExecutor(max_workers=2) as preparation:
        children = {}
        preparing = {}
        while True:
            request = load(root / "registration.json")
            status = {"pid": os.getpid(), "checked_at": time.time(), "accepted_exports_allowed": False, "families": {}}
            for family in ("scandi", "norquad-fleurs"):
                target = request["families"][family]
                output = root / family
                item = {"state": "registered_waiting_completed_integration", "integration": target.get("integration")}
                if family in children:
                    process = children[family]
                    item.update(state="audit_running" if process.poll() is None else "audit_client_exited", pid=process.pid, exit_code=process.poll())
                    if (output / "jobs.sqlite").exists():
                        with sqlite3.connect((output / "jobs.sqlite").as_uri() + "?mode=ro", uri=True, timeout=5) as db:
                            item["jobs"] = db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall()
                            item["components"] = db.execute("SELECT component,status,count(*) FROM jobs GROUP BY component,status").fetchall()
                            item["sources"] = db.execute("SELECT component,input_rows,queued,quarantined,complete FROM sources").fetchall()
                    if process.poll() == 0:
                        item["state"] = "completed_automated_audit"
                elif family in preparing:
                    item["state"] = "validating_completed_integration"
                    if preparing[family].done():
                        try:
                            item["counts"] = preparing.pop(family).result()
                            children[family] = launch(output)
                            item.update(state="audit_launched", pid=children[family].pid)
                        except Exception as exc:
                            item.update(state="waiting_or_validation_blocked", error=f"{type(exc).__name__}: {exc}")
                elif target.get("integration") and Path(target["integration"]).exists():
                    try:
                        preparing[family] = preparation.submit(prepare, family, target["integration"], output)
                        item["state"] = "validating_completed_integration"
                    except Exception as exc:
                        item.update(state="waiting_or_validation_blocked", error=f"{type(exc).__name__}: {exc}")
                status["families"][family] = item
            write_json(root / "status.json", status)
            if all(item["state"] == "completed_automated_audit" for item in status["families"].values()):
                write_json(root / "completion.json", status)
                return
            time.sleep(15)


if __name__ == "__main__":
    main()
