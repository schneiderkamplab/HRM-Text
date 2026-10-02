"""Pinned completed-DaLA authorization, separate from legacy Swedish and main audits."""
import argparse
from pathlib import Path

from .audit_gates import CrossScreen
from .audit_readiness import source_entry
from .dala_integrate import STANDARDS, TASKS, verify_inputs
from .io import file_hash, load, write_json


def isolated_output(output, protected):
    output = Path(output).resolve()
    if any(output.is_relative_to(Path(p).resolve()) or Path(p).resolve().is_relative_to(output) for p in protected):
        raise ValueError("Completed DaLA audit must use a separate, nonoverlapping root")


def validate_client_limits(auth, concurrency, workers, endpoints):
    if (not 1 <= concurrency <= min(128, auth["max_client_concurrency_per_endpoint"]) or
            not 1 <= workers <= min(2, auth["max_preparation_workers"]) or
            endpoints != auth["endpoints"]):
        raise ValueError("Completed DaLA client exceeds pinned endpoints/concurrency/preparation limits")


def validate_authorization(sources, authorization, output, crossscreen):
    auth = load(authorization)
    output = Path(output).resolve()
    languages = auth.get("languages", [])
    if (auth.get("scope") != "completed_dala_automated_audit_only" or
            auth.get("user_authorized") is not True or auth.get("accepted_exports_allowed") is not False or
            output != Path(auth["audit_root"]).resolve() or
            Path(authorization).resolve() != output / "completed-dala-authorization.json" or
            not languages or len(set(languages)) != len(languages) or not set(languages) <= set(STANDARDS)):
        raise ValueError("Explicit completed DaLA language/root authorization required")
    isolated_output(output, auth["protected_roots"])
    expected = {f"dala-{lang}-{task}" for lang in languages for task in TASKS}
    if len(sources) != len(expected) or {s["component"] for s in sources} != expected:
        raise ValueError("Source components differ from explicitly authorized languages")
    for path, expected_sha in auth["pins"].items():
        if file_hash(path) != expected_sha:
            raise ValueError("Completed DaLA authorization evidence changed: " + path)
    if sources != load(output / "sources.json")["sources"]:
        raise ValueError("Completed DaLA source descriptor mismatch")
    if CrossScreen(crossscreen).descriptor() != auth["existing_crossscreen"]:
        raise ValueError("Existing cross-screen evidence changed")
    root = Path(auth["integration_root"])
    integration, proof, inputs, screening = [load(root / name) for name in
                                            ("integration.json", "verification.json", "inputs.json", "screening.json")]
    if (integration["status"] != "complete_unaudited" or integration["integrated_languages"] != languages or
            integration.get("producer_finalized") is not True or proof["status"] != "verified_unaudited" or
            proof.get("producer_finalized") is not True or
            proof["integration_sha256"] != file_hash(root / "integration.json") or
            inputs["scope"] != languages or inputs.get("producer_finalized") is not True or
            inputs["producer_status"] != "candidate_datasets_complete_require_linguistic_review" or
            screening["status"] != "complete_local_screen" or
            len(integration["components"]) != len(expected) or
            {e["component"] for e in integration["components"]} != expected):
        raise ValueError("Completed producer/import/verification proof missing")
    exclusions = inputs["late_exclusions_receipt"]
    if file_hash(exclusions["path"]) != exclusions["sha256"]:
        raise ValueError("Late exclusions changed; screen again")
    previous = load(root / "previous-screen.json")
    if file_hash(previous["seed"]) != previous["seed_sha256"]:
        raise ValueError("Previous held-out/train seed changed")
    for path, sha in previous["inputs"].items():
        if file_hash(path) != sha:
            raise ValueError("Previous integration evidence changed")
    verify_inputs(inputs)
    for source, entry in zip(sorted(sources, key=lambda e: e["component"]),
                             sorted(integration["components"], key=lambda e: e["component"])):
        canonical = source_entry(entry["component"], entry["path"], entry["receipt"], entry["sha256"],
                                 entry["family"], entry["evidence"])
        if source != canonical or file_hash(source["path"]) != source["sha256"]:
            raise ValueError("Source differs from pinned completed component")
        receipt = load(source["receipt"])
        if (receipt["language"] not in languages or receipt["task"] not in TASKS or
                source["component"] != f"dala-{receipt['language']}-{receipt['task']}" or
                receipt["status"] != "complete_unaudited" or receipt.get("accepted") is not False or
                receipt["counts"]["candidates"] != proof["counts"][source["component"]]):
            raise ValueError("Completed DaLA component receipt mismatch")
    return auth


def prepare(root, output, parent, swedish, crossscreen, languages):
    root, output, parent, swedish = (Path(p).resolve() for p in (root, output, parent, swedish))
    protected = [str(p) for p in (parent, swedish, root, Path("/work/mimir/DaLA"))]
    isolated_output(output, protected)
    if (output / "sources.json").exists():
        raise ValueError("Audit sources already pinned; refusing overwrite")
    integration = load(root / "integration.json")
    if integration["integrated_languages"] != list(languages):
        raise ValueError("Requested language scope does not match import")
    # Two preparation lanes begin one language each, rather than both Polish tasks.
    order = {f"dala-{lang}-{task}": i for i, (task, lang) in
             enumerate((task, lang) for task in TASKS for lang in languages)}
    sources = [source_entry(e["component"], e["path"], e["receipt"], e["sha256"], e["family"], e["evidence"])
               for e in sorted(integration["components"], key=lambda e: order[e["component"]])]
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "sources.json", {"sources": sources, "accepted_exports_allowed": False,
               "local_completed_dala_screen": str(root / "screening.json"),
               "coverage_note": "Local full-raw heldout and previous DaLA screen supplements earlier crossscreen; inherited coverage remains incomplete."})
    write_json(output / "operational-approval.json", load(parent / "operational-approval.json"))
    paths = {root / name for name in ("integration.json", "verification.json", "inputs.json", "screening.json", "previous-screen.json", "tokenizer.json")}
    paths.update((output / "sources.json", output / "operational-approval.json"))
    for source in sources:
        paths.add(Path(source["receipt"]))
        paths.update(Path(e["path"]) for e in source["evidence"])
    auth = {"scope": "completed_dala_automated_audit_only", "languages": list(languages),
            "user_authorized": True, "authorization_basis": "2026-09-25 user authorized completed PL/IS isolated import and automated audit at 128 per existing endpoint, two preparation workers",
            "accepted_exports_allowed": False, "audit_root": str(output), "integration_root": str(root),
            "protected_roots": protected, "pins": {str(p): file_hash(p) for p in sorted(paths)},
            "existing_crossscreen": CrossScreen(crossscreen).descriptor(),
            "max_client_concurrency_per_endpoint": 128, "max_preparation_workers": 2,
            "endpoints": load(parent / "configuration.json")["endpoints"],
            "producer_candidate_finalized": True, "linguistic_review_complete": False,
            "full_inherited_dedup_complete": False}
    path = output / "completed-dala-authorization.json"
    write_json(path, auth)
    validate_authorization(sources, path, output, crossscreen)
    write_json(output / "owner-handoff.json", {"status": "isolated_completed_dala_ready", "languages": list(languages),
               "owners": {"exports_upload": "Poincare", "identity": "Tesla"},
               "audit_cli_flag": "--completed-dala-authorization", "source_and_jobs_schema": "unchanged audit_full schema",
               "authorization_validator": "dfm12.dala_completed_audit.validate_authorization",
               "audit_full_validate_sources_keyword": "dala_authorization",
               "direct_owner_messaging_available": False,
               "parent_files_modified": False, "swedish_files_modified": False, "exports_modified": False,
               "server_restart": False, "source_manifest": str(output / "sources.json"),
               "integration_manifest": str(root / "integration.json"), "authorization": str(path),
               "client_concurrency_per_endpoint": 128, "preparation_workers": 2, "endpoints": auth["endpoints"],
               "immutable_source_hashes": {str(p / "sources.json"): file_hash(p / "sources.json") for p in (parent, swedish)}})
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/dala-pl-is-20260925-v1"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/full-audit-pl-is-20260925-v1"))
    parser.add_argument("--parent", type=Path, default=Path("data/dfm12/full-audit-20260924-v1"))
    parser.add_argument("--swedish", type=Path, default=Path("data/dfm12/full-audit-sv-20260924-v1"))
    parser.add_argument("--crossscreen", type=Path, default=Path("data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json"))
    parser.add_argument("--languages", nargs="+", choices=sorted(STANDARDS), default=["pl", "is"])
    args = parser.parse_args()
    print(prepare(args.root, args.output, args.parent, args.swedish, args.crossscreen, args.languages))
