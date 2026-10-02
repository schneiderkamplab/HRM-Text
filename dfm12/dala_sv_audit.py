"""Explicit, pinned authorization for a separate completed Swedish-only audit."""
import argparse
from pathlib import Path

from .audit_gates import CrossScreen
from .audit_readiness import source_entry
from .dala_integrate import verify_inputs
from .io import file_hash, load, write_json

COMPONENTS = {"dala-sv-acceptability", "dala-sv-correction"}


def validate_client_limits(auth, concurrency, workers, endpoints):
    if (not 1 <= concurrency <= min(1024, auth["max_client_concurrency_per_endpoint"]) or
            not 1 <= workers <= min(1, auth["max_preparation_workers"]) or
            endpoints != auth["endpoints"]):
        raise ValueError("Swedish client must use pinned endpoints and authorized concurrency with one preparation worker")


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": file_hash(path)}


def validate_authorization(sources, authorization, output, crossscreen):
    auth = load(authorization)
    output = Path(output).resolve()
    if (auth.get("scope") != "completed_swedish_automated_audit_only" or
            auth.get("user_authorized") is not True or auth.get("accepted_exports_allowed") is not False or
            output != Path(auth["audit_root"]) or
            output == Path(auth["parent_audit_root"]) or output.is_relative_to(Path(auth["parent_audit_root"])) or
            {s["component"] for s in sources} != COMPONENTS or len(sources) != 2):
        raise ValueError("Completed Swedish-only isolated authorization required")
    for receipt in auth["pins"]:
        if file_hash(receipt["path"]) != receipt["sha256"]:
            raise ValueError("Swedish authorization evidence changed: " + receipt["path"])
    if sources != load(output / "sources.json")["sources"]:
        raise ValueError("Swedish source descriptor mismatch")
    if CrossScreen(crossscreen).descriptor() != auth["existing_crossscreen"]:
        raise ValueError("Existing cross-screen changed")
    root = Path(auth["integration_root"])
    integration = load(root / "integration.json")
    proof = load(root / "verification.json")
    inputs = load(root / "inputs.json")
    screening = load(root / "screening.json")
    if (integration["status"] != "complete_unaudited" or integration["integrated_languages"] != ["sv"] or
            proof["status"] != "verified_unaudited" or
            proof["integration_sha256"] != file_hash(root / "integration.json") or
            inputs["scope"] != ["sv"] or screening["status"] != "complete_local_screen"):
        raise ValueError("Swedish completed import proof missing")
    exclusions = inputs["late_exclusions_receipt"]
    if file_hash(exclusions["path"]) != exclusions["sha256"]:
        raise ValueError("Late exclusions changed; Swedish must be screened again")
    seed = load(root / "previous-screen.json")
    if file_hash(seed["seed"]) != seed["seed_sha256"]:
        raise ValueError("Previous held-out/train screening seed changed")
    verify_inputs(inputs)
    for source, component in zip(sorted(sources, key=lambda s: s["component"]),
                                 sorted(integration["components"], key=lambda s: s["component"])):
        if source["path"] != component["path"] or source["sha256"] != component["sha256"]:
            raise ValueError("Source is not the completed Swedish import")
        receipt = load(source["receipt"])
        if receipt["language"] != "sv" or receipt["status"] != "complete_unaudited":
            raise ValueError("Swedish component receipt mismatch")
        if file_hash(source["path"]) != source["sha256"]:
            raise ValueError("Swedish candidates changed")
    return auth


def prepare(root, output, parent, crossscreen):
    root, output, parent = (Path(p).resolve() for p in (root, output, parent))
    if output.exists() and (output / "sources.json").exists():
        raise ValueError("Audit source manifest already pinned; do not overwrite")
    integration = load(root / "integration.json")
    sources = [source_entry(e["component"], e["path"], e["receipt"], e["sha256"], e["family"], e["evidence"])
               for e in integration["components"]]
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "sources.json", {"sources": sources, "accepted_exports_allowed": False,
               "local_swedish_screen": str(root / "screening.json"),
               "coverage_note": "Earlier crossscreen does not cover SV; additional pinned local SV screen required. Inherited coverage remains incomplete."})
    write_json(output / "operational-approval.json", load(parent / "operational-approval.json"))
    paths = {root / name for name in ("integration.json", "verification.json", "inputs.json", "screening.json", "previous-screen.json", "tokenizer.json")}
    paths.update((output / "sources.json", output / "operational-approval.json"))
    for source in sources:
        paths.add(Path(source["receipt"]))
        paths.update(Path(e["path"]) for e in source["evidence"])
    auth = {"scope": "completed_swedish_automated_audit_only", "user_authorized": True,
            "authorization_basis": "2026-09-24 user explicitly requested completed Swedish isolated import and bounded audit on existing endpoints",
            "accepted_exports_allowed": False, "audit_root": str(output), "parent_audit_root": str(parent),
            "integration_root": str(root), "pins": [pin(p) for p in sorted(paths)],
            "existing_crossscreen": CrossScreen(crossscreen).descriptor(),
            "max_client_concurrency_per_endpoint": 1, "max_preparation_workers": 1,
            "endpoints": load(parent / "configuration.json")["endpoints"],
            "producer_finalized": False, "full_inherited_dedup_complete": False}
    path = output / "completed-swedish-authorization.json"
    write_json(path, auth)
    validate_authorization(sources, path, output, crossscreen)
    write_json(output / "owner-handoff.json", {"owner": "Tesla/main audit owner", "status": "isolated_swedish_ready",
               "parent_audit_root": str(parent), "parent_files_modified": False,
               "exports_modified": False, "server_restart": False,
               "source_manifest": str(output / "sources.json"), "integration_manifest": str(root / "integration.json"),
               "authorization": str(path), "client_concurrency_per_endpoint": 1,
               "endpoints": load(parent / "configuration.json")["endpoints"]})
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/dala-sv-20260924-v1"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/full-audit-sv-20260924-v1"))
    parser.add_argument("--parent", type=Path, default=Path("data/dfm12/full-audit-20260924-v1"))
    parser.add_argument("--crossscreen", type=Path, default=Path("data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json"))
    args = parser.parse_args()
    print(prepare(args.root, args.output, args.parent, args.crossscreen))
