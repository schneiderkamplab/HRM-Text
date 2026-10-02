"""Read-only registration of another thread's six-language DaLA exports.

No generation, publication, tokenization, or accepted-corpus mutation. The
producer's terminal finalization receipt, not a raw build, gates eligibility.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .io import digest, file_hash, lock, write_json

CONFIG = Path(__file__).with_name("dala_sources.yaml")
TERMINAL = "candidate_datasets_complete_require_linguistic_review"
SPLITS = ("train", "validation", "test")
TASKS = ("acceptability", "correction")


def contained(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes producer directory: {relative}")
    return path


def evidence(path):
    # Parse and fingerprint the same bytes so concurrent atomic updates cannot
    # associate a new checksum with old JSON contents.
    import hashlib
    raw = path.read_bytes()
    return json.loads(raw), {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def summarize_manifest(path, language):
    manifest, receipt = evidence(path)
    if manifest.get("language") != language or str(manifest.get("schema_version")) != "2":
        raise ValueError("Wrong language or unsupported producer manifest schema")
    return manifest, {"manifest": receipt, "quality_status": manifest.get("quality_status"),
        "pairs": manifest.get("verification", {}).get("pairs"),
        "splits": {s: {k: v for k, v in manifest.get("splits", {}).get(s, {}).items()
                       if k in ("pairs", "acceptability_rows", "correction_rows")} for s in SPLITS},
        "source_snapshots": manifest.get("source_snapshots", []),
        "counts_basis": "Producer manifest; not an independent row recount"}


def validate_final(root, output, language, isolation, run):
    expected = root / "la_output" / f"six_language_candidates_{run}" / language
    path = contained(root, output)
    if path != expected.resolve():
        raise ValueError("Final output is not the current isolated production destination")
    manifest, summary = summarize_manifest(path / "manifest.json", language)
    if not manifest.get("cross_dataset_isolation") or not manifest.get("late_agent_review"):
        raise ValueError("Missing cross-dataset isolation or late-review provenance")
    if manifest["verification"].get("document_split_isolation") is not True:
        raise ValueError("Missing document-separated split verification")
    if not manifest.get("source_snapshots"):
        raise ValueError("Missing pinned source provenance")
    entry = isolation.get(language, {})
    if (entry.get("retained_pairs") != summary["pairs"] or
            contained(root, entry.get("output", "")) != path):
        raise ValueError("Isolation receipt disagrees with final output")
    required = {f"{s}/{t}_it.jsonl" for s in SPLITS for t in TASKS}
    required |= {f"{s}/pairs.jsonl" for s in SPLITS}
    required |= {"documents.jsonl", "rules.json"}
    if not required <= set(manifest.get("artifacts", {})):
        raise ValueError("Missing required split/provenance artifact receipts")
    for name, artifact in manifest["artifacts"].items():
        file = contained(path, name)
        if file.stat().st_size != artifact["bytes"] or file_hash(file) != artifact["sha256"]:
            raise ValueError(f"Artifact checksum/size mismatch: {name}")
    if evidence(path / "manifest.json")[1] != summary["manifest"]:
        raise ValueError("Manifest changed during verification; refresh again")
    summary.update(output=str(path), artifact_checksums_verified=True,
                   train_files=[str(path / "train" / f"{task}_it.jsonl") for task in TASKS],
                   excluded_splits=["validation", "test"])
    return summary


def inspect(cfg, producer_root):
    root = producer_root.resolve()
    sources = {name: dict(source, kind="dala-local-task-views", status="pending",
                         audit_status="unaudited", import_enabled=False,
                         blockers=[], train_files=[]) for name, source in cfg["sources"].items()}
    report = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "producer_root": str(root), "registration_config_hash": digest(cfg),
              "policy": {"train_only": True, "human_validation_claim": False,
                         "license_hold": False, "license_authorization": "All DynaWord/Instruct licenses owner-approved",
                         "generation_owned_by": "DaLA producer thread", "final_sampling": False},
              "sources": sources, "evidence": {}}
    try:
        pointer, pointer_receipt = evidence(contained(root, cfg["current_run"]))
        report["evidence"]["current_run"] = pointer_receipt
        run = pointer["run_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run) or any(t in run.lower() for t in ("pilot", "smoke", "audit")):
            raise ValueError("Invalid or diagnostic current run")
        report["run_id"] = run
        final_path = contained(root, pointer["finalization"])
        expected = root / "wiki/artifacts/six-language-expansion" / run / "finalization.json"
        if final_path != expected.resolve():
            raise ValueError("Finalization path does not match current run")
        final, final_receipt = evidence(final_path)
        report["evidence"]["finalization"] = final_receipt
        if final.get("run_id") != run:
            raise ValueError("Finalization run does not match current-run pointer")
        report["producer_status"] = final.get("status")
        for source in sources.values():
            lang = source["language"]
            language_run = final.get("language_runs", {}).get(lang, run)
            if not re.fullmatch(r"[A-Za-z0-9_-]+", language_run):
                raise ValueError("Invalid language run")
            status_path = root / "wiki/artifacts/six-language-expansion" / language_run / f"{lang}-status.json"
            source["build_status_path"] = str(status_path)
            source["expected_final_output"] = str(root / "la_output" / f"six_language_candidates_{run}" / lang)
            if status_path.exists():
                status, status_receipt = evidence(status_path)
                source["build_receipt"] = status_receipt
                source["producer_build_status"] = status.get("status")
                if status.get("language") != lang or status.get("exit_code") != 0:
                    source["blockers"].append("producer_build_failed_or_wrong_language")
                elif status.get("output"):
                    _, summary = summarize_manifest(contained(root, status["output"]) / "manifest.json", lang)
                    source["raw_build_not_importable"] = summary
            else:
                source["blockers"].append("current_build_completion_receipt_missing")
            if final.get("status") != TERMINAL:
                source["blockers"].append("producer_finalization_pending:" + str(final.get("status")))
                source["blockers"].append("cross_dataset_isolation_and_late_exclusions_not_final")
        if final.get("status") == TERMINAL:
            isolation, isolation_receipt = evidence(contained(root, final["cross_dataset_isolation"]))
            report["evidence"]["isolation"] = isolation_receipt
            expected_languages = {s["language"] for s in sources.values()}
            if set(isolation) != expected_languages or set(final.get("outputs", {})) != expected_languages:
                raise ValueError("Finalization does not cover all six standards")
            for source in sources.values():
                lang = source["language"]
                if source["blockers"]:
                    continue
                try:
                    source["final_export"] = validate_final(root, final["outputs"][lang], lang, isolation, run)
                    source["status"] = "ready_for_unaudited_cpu_import"
                    source["train_files"] = source["final_export"]["train_files"]
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    source["blockers"].append(f"final_export_verification_failed:{exc}")
        if evidence(contained(root, cfg["current_run"]))[1] != pointer_receipt or evidence(final_path)[1] != final_receipt:
            raise ValueError("Producer state changed during refresh; rerun")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        for source in sources.values():
            source.update(status="pending", train_files=[])
            source["blockers"].append(f"producer_evidence_unavailable_or_inconsistent:{exc}")
    report["counts"] = {"registered_sources": len(sources),
                        "ready_sources": sum(s["status"] == "ready_for_unaudited_cpu_import" for s in sources.values()),
                        "imported_conversations": 0, "pretokenized_conversations": 0}
    return report


def apply_local_integration(report, path):
    """A verified local three-language screen can supersede the all-six wait."""
    manifest = json.loads(Path(path).read_text())
    proof_path = Path(path).parent / "verification.json"
    proof = json.loads(proof_path.read_text())
    if (manifest.get("version") != 1 or manifest.get("status") != "complete_unaudited" or
            proof.get("status") != "verified_unaudited" or proof.get("integration_sha256") != file_hash(path)):
        raise ValueError("Local integration lacks matching independent verification")
    expected = {f"dala-{lang}-{task}" for lang in ("nb", "nn", "fo") for task in TASKS}
    if {e["component"] for e in manifest["components"]} != expected:
        raise ValueError("Local integration must cover exactly NB/NN/FO task views")
    groups = {}
    for entry in manifest["components"]:
        receipt = json.loads(Path(entry["receipt"]).read_text())
        if receipt["sha256"] != entry["sha256"] or file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("Local integration candidates changed")
        language = receipt["language"]
        if (entry["component"] != f"dala-{language}-{receipt['task']}" or
                receipt["counts"]["candidates"] != proof["counts"][entry["component"]]):
            raise ValueError("Local language/task/count verification mismatch")
        if receipt.get("audit_status") != "unaudited" or receipt.get("accepted") is not False:
            raise ValueError("Unexpected local integration audit state")
        groups.setdefault(language, []).append(entry | {"conversations": receipt["counts"]["candidates"]})
    for language, entries in groups.items():
        source = report["sources"][f"dala-{language}"]
        source["producer_blockers"] = source["blockers"]
        source.update(status="integrated_unaudited", blockers=[], local_components=entries,
                      local_integration=str(Path(path).resolve()), verification=str(proof_path.resolve()),
                      local_screening_scope=manifest["screening_scope"], limitations=manifest["limitations"])
    total = sum(e["conversations"] for entries in groups.values() for e in entries)
    report["counts"].update(integrated_sources=len(groups), imported_conversations=total,
                            pretokenized_conversations=total,
                            ready_sources=sum(s["status"] == "ready_for_unaudited_cpu_import"
                                              for s in report["sources"].values()))
    report["evidence"]["local_integration"] = {"path": str(Path(path).resolve()), "sha256": file_hash(path)}
    return report


def main():
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--producer-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/dala-registration/manifest.json"))
    parser.add_argument("--integration-manifest", type=Path,
                        help="Verified local NB/NN/FO integration; does not unblock PL/SV/IS")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    root = args.producer_root or Path(cfg["producer_root"])
    if args.output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Refusing to write into producer-owned workspace")
    with lock(args.output.with_suffix(".lock")):
        result = inspect(cfg, root)
        integration = args.integration_manifest
        if integration is None and args.output.exists():
            previous = json.loads(args.output.read_text())
            if previous.get("producer_root") == str(root.resolve()):
                registered = previous.get("evidence", {}).get("local_integration", {}).get("path")
                integration = Path(registered) if registered else None
        if integration:
            result = apply_local_integration(result, integration)
        write_json(args.output, result)
    print(json.dumps(result["counts"], indent=2))
    for name, source in result["sources"].items():
        print(name, source["status"], "; ".join(source["blockers"]))


if __name__ == "__main__":
    main()
