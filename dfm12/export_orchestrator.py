"""One repeatable CPU accepted-export/publication pass; no audit mutation/retry."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

from .io import file_hash, load, lock, write_json

ROOTS = (
    "full-audit-20260924-v1", "full-audit-sv-20260924-v1",
    "full-audit-pl-is-20260925-v1", "scoped-inclusion-audits-20260925-v1/scandi",
    "scoped-inclusion-audits-20260925-v1/norquad-fleurs",
)
DEFAULT_CONTRACT = Path("data/dfm12/export-orchestration-ready-20260925.json")
DEFAULT_STATE = Path("data/dfm12/export-orchestration-20260925")


def cpu_env():
    return dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")


def contract(path):
    value = load(path)
    if value.get("status") != "helpers_ready" or value.get("version") != 1:
        raise ValueError("Parent/helper readiness contract required before launch")
    if value.get("output") != "exports_dfm12" or value.get("namespace") != "schneiderkamplab":
        raise ValueError("Unexpected export root or publication namespace")
    expected = {str((Path("data/dfm12") / r).resolve()) for r in ROOTS}
    if set(map(lambda p: str(Path(p).resolve()), value["audit_roots"])) != expected:
        raise ValueError("All five owning audit roots must be explicit")
    for key in ("export_command", "identity_command"):
        command = value[key]
        if (not isinstance(command, list) or len(command) < 3 or command[0] != "-m"
                or not command[1].startswith("dfm12.") or not all(isinstance(x, str) for x in command)):
            raise ValueError("Helper commands must be explicit Python module argument lists")
        wanted_output = "exports_dfm12" if key == "export_command" else value.get("identity_output")
        if "--output" not in command or command[command.index("--output") + 1] != wanted_output:
            raise ValueError("Unexpected helper output")
    identity_output = Path(value["identity_output"]).resolve()
    if (value["identity_command"][1] != "dfm12.export_identity"
            or not (identity_output.is_relative_to(DEFAULT_STATE.resolve())
                    or (identity_output.parent == Path("data/dfm12").resolve() and identity_output.name.startswith("identity-export-")))):
        raise ValueError("Identity helper must use its isolated orchestration staging root")
    if value["export_command"][1] != "dfm12.export_finished":
        raise ValueError("Unexpected source export helper")
    command = value["export_command"]
    runs = {str(Path(command[i + 1]).resolve()) for i, arg in enumerate(command) if arg == "--run"}
    if runs != expected or "--incremental" not in command:
        raise ValueError("Source export must be incremental and retain all five owners")
    if not value.get("helper_evidence"):
        raise ValueError("Helper readiness evidence required")
    for item in value["helper_evidence"]:
        if file_hash(item["path"]) != item["sha256"]:
            raise ValueError("Helper readiness evidence changed")
    return value


def audit_state(roots):
    """Observe sources/jobs using read-only connections; failed is terminal."""
    result = {}
    for root in map(Path, roots):
        plan = load(root / "sources.json")
        db = sqlite3.connect((root / "jobs.sqlite").resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
        try:
            db.execute("BEGIN")
            states = {r[0]: {"complete": bool(r[1]), "input_rows": r[2], "queued": r[3],
                              "quarantined": r[4], "jobs": {}}
                      for r in db.execute("SELECT component,complete,input_rows,queued,quarantined FROM sources")}
            # The production status index avoids rescanning millions of terminal
            # rows on each pass. Freeze/export remains the authoritative check.
            for component, status, count in db.execute("SELECT component,status,count(*) FROM jobs WHERE status IN ('pending','running','parked') GROUP BY component,status"):
                states[component]["jobs"][status] = count
            db.rollback()
        finally:
            db.close()
        for source in plan["sources"]:
            name = source["component"]
            if name in result:
                raise ValueError("Duplicate component ownership")
            state = states.get(name, {"complete": False, "jobs": {}})
            state["terminal"] = state["complete"] and not (set(state["jobs"]) - {"done", "failed"})
            result[name] = dict(state, audit_root=str(root.resolve()), jobs_observation="active_statuses_only")
    return result


def inventory(output):
    manifest = load(output / "manifest.json")
    receipts_path = output / "metadata/upload-receipts.json"
    receipts = load(receipts_path) if receipts_path.exists() else {}
    packages = {}
    for package in manifest["packages"]:
        name = package["name"]
        if Path(name).name != name or not name.startswith("dfm12-") or name in packages:
            raise ValueError("Unsafe or duplicate package name")
        checksum = file_hash(output / name / "metadata/manifest.json")
        saved = receipts.get("schneiderkamplab/" + name)
        if saved and saved["manifest_sha256"] != checksum:
            raise ValueError("Published package changed: " + name)
        packages[name] = {"manifest_sha256": checksum, "component": package["component"],
                          "rows": package["rows"], "upload": saved}
    return packages


def preserve(before, after):
    for name, prior in before.items():
        now = after.get(name)
        if not now or any(now[k] != prior[k] for k in ("manifest_sha256", "component", "rows")):
            raise ValueError("Previously exported package changed: " + name)
        if (prior.get("upload") or {}).get("status") == "verified" and now["upload"] != prior["upload"]:
            raise ValueError("Previously verified publication receipt changed: " + name)


def run_helper(command, log):
    with log.open("xb") as handle:
        result = subprocess.run([sys.executable, *command], env=cpu_env(), stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Helper exited {result.returncode}; inspect {log}; no automatic retry")


def merge_identity(staged, output):
    """Adopt only validated helper packages; root audit snapshots stay local."""
    from .export_validator import validate
    from .export_identity import verify_identity_source
    report = load(staged / "manifest.json")
    if report.get("completed") is not True or len(report["packages"]) != 9:
        raise ValueError("Incomplete identity helper export")
    companion = report["identity_source_manifest"]
    verify_identity_source(staged, companion, report["packages"])
    with lock(output / ".export.lock"):
        current = load(output / "manifest.json")
        known = {p["name"]: p for p in current["packages"]}
        for package in report["packages"]:
            name = package["name"]
            if Path(name).name != name or not name.startswith("dfm12-identity-xl-full-bp-"):
                raise ValueError("Unexpected identity package name")
            source, destination = staged / name, output / name
            result = validate(source)
            if result["rows"] != package["rows"]:
                raise ValueError("Identity summary count mismatch")
            if not destination.exists():
                build = output / (".identity-adopting-" + name)
                if build.exists():
                    # An interrupted copy is never silently deleted or reused.
                    raise FileExistsError("Interrupted identity copy requires inspection: " + str(build))
                shutil.copytree(source, build)
                validate(build)
                build.rename(destination)
            if file_hash(source / "metadata/manifest.json") != file_hash(destination / "metadata/manifest.json"):
                raise ValueError("Identity destination differs from isolated helper")
            validate(destination)
            if name in known:
                if known[name] != package:
                    raise ValueError("Existing identity inventory differs")
            else:
                current["packages"].append(package)
                known[name] = package
        companion_path = output / companion["file"]
        if companion_path.exists():
            if file_hash(companion_path) != companion["sha256"]:
                raise ValueError("Existing identity companion changed")
        else:
            companion_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staged / companion["file"], companion_path)
        current["identity_source_manifest"] = companion
        current["identity_exports"] = [{"manifest": str((staged / "manifest.json").resolve()),
                                        "sha256": file_hash(staged / "manifest.json")}]
        verify_identity_source(output, companion, current["packages"])
        for key in ("rows", "data_bytes", "package_bytes"):
            current[key] = sum(p[key] for p in current["packages"])
        write_json(output / "manifest.json", current)
        (output / "README.md").write_text("# DFM12 Accepted Exports\n\n"
            "Publication status: metadata/upload-receipts.json. Root metadata is LOCAL ONLY and must never be uploaded.\n"
            "Only each nonempty validated dfm12-* package is public. No final sampling performed.\n\n"
            "| Package | Training rows | Compressed training bytes | Package bytes |\n| --- | ---: | ---: | ---: |\n" +
            "\n".join(f"| [{p['name']}]({p['name']}/README.md) | {p['rows']} | {p['data_bytes']} | {p['package_bytes']} |"
                        for p in current["packages"]) + "\n")
        return {"packages": len(report["packages"]), "rows": report["rows"], "manifest": str(staged / "manifest.json")}


@contextmanager
def wait_lock(path, timeout=43200, interval=5):
    """A final pass queues behind an active first pass instead of being dropped."""
    if timeout < 0:
        raise ValueError("Negative lock timeout")
    deadline = time.monotonic() + timeout
    while True:
        guard = lock(path)
        try:
            guard.__enter__()
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError("Export orchestrator lock wait expired; no work was retried")
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
    try:
        yield
    finally:
        guard.__exit__(None, None, None)


def once(contract_path=DEFAULT_CONTRACT, state=DEFAULT_STATE, lock_wait_seconds=43200):
    cfg = contract(contract_path)
    state.mkdir(parents=True, exist_ok=True)
    with wait_lock(state / ".orchestrator.lock", lock_wait_seconds):
        cfg = contract(contract_path)
        run = state / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{time.time_ns()}")
        run.mkdir()
        output = Path(cfg["output"])
        receipt = {"status": "running", "pid": os.getpid(), "started": time.time(),
                   "contract_sha256": file_hash(contract_path), "namespace": cfg["namespace"],
                   "output": str(output), "audit_mutations": False, "audit_retries": False,
                   "gpu_or_process_mutations": False, "phases": []}
        def save():
            write_json(run / "receipt.json", receipt)
            write_json(state / "latest.json", {"receipt": str((run / "receipt.json").resolve()), "status": receipt["status"]})
        save()
        try:
            from huggingface_hub import get_token, HfApi
            if not get_token():
                raise ValueError("Cached Hugging Face authentication missing")
            HfApi().whoami()  # Never log the response or credentials.
            receipt["cached_hf_auth_valid"] = True
            with lock(output / ".export.lock"):
                before = inventory(output)
            baseline_path = state / "preserved-baseline.json"
            if baseline_path.exists():
                preserve(load(baseline_path), before)
            else:
                if sum(bool(p["upload"] and p["upload"]["status"] == "verified") for p in before.values()) < 58:
                    raise ValueError("Expected at least 58 previously verified packages")
                write_json(baseline_path, before)
            receipt["before"] = {"packages": len(before), "rows": sum(p["rows"] for p in before.values()),
                                  "verified": sum(bool(p["upload"] and p["upload"]["status"] == "verified") for p in before.values())}
            initial = audit_state(cfg["audit_roots"])
            receipt["audit_before"] = initial
            exported = {p["component"] for p in before.values()}
            needed = [name for name, s in initial.items() if s["terminal"] and name not in exported]
            for phase, command in (("export", cfg["export_command"]), ("identity", cfg["identity_command"])):
                if phase == "export" and not needed:
                    receipt["phases"].append({"phase": phase, "status": "no_new_finished_sources"})
                    continue
                contract(contract_path)
                if phase != "identity" or not (Path(cfg["identity_output"]) / "manifest.json").exists():
                    run_helper(command, run / (phase + ".log"))
                if phase == "identity":
                    receipt["identity"] = merge_identity(Path(cfg["identity_output"]), output)
                with lock(output / ".export.lock"):
                    preserve(before, inventory(output))
                receipt["phases"].append({"phase": phase, "status": "complete", "log": str(run / (phase + ".log"))})
                save()
            run_helper(["-m", "dfm12.upload_exports", "--output", str(output), "--namespace", cfg["namespace"]], run / "upload.log")
            receipt["phases"].append({"phase": "upload", "status": "complete", "log": str(run / "upload.log")})
            with lock(output / ".export.lock"):
                after = inventory(output)
                preserve(before, after)
            if any(p["rows"] > 0 and (not p["upload"] or p["upload"]["status"] != "verified") for p in after.values()):
                raise ValueError("Nonempty exported package lacks verified publication")
            final = audit_state(cfg["audit_roots"])
            exported = {p["component"] for p in after.values()}
            receipt.update(status="complete_finished_pass", completed=time.time(), audit_after=final,
                after={"packages": len(after), "rows": sum(p["rows"] for p in after.values()),
                       "verified": sum(bool(p["upload"] and p["upload"]["status"] == "verified") for p in after.values())},
                newly_exported=sorted(set(after) - set(before)),
                newly_verified=sorted(name for name,p in after.items() if p["upload"] and p["upload"]["status"]=="verified"
                    and (name not in before or not before[name]["upload"] or before[name]["upload"]["status"]!="verified")),
                audit_remaining=[name for name,s in final.items() if not s["terminal"]],
                finished_not_exported=[name for name,s in final.items() if s["terminal"] and name not in exported])
            save()
            return receipt
        except Exception as exc:
            receipt.update(status="failed_no_automatic_retry", error_type=type(exc).__name__, completed=time.time())
            save()
            raise


def launch(contract_path=DEFAULT_CONTRACT, state=DEFAULT_STATE, lock_wait_seconds=43200):
    contract(contract_path)
    state.mkdir(parents=True, exist_ok=True)
    with lock(state / ".launch.lock"):
        path = state / "launch.json"
        log = state / f"background-{time.time_ns()}.log"
        command = [sys.executable, "-u", "-m", "dfm12.export_orchestrator", "once",
                   "--contract", str(contract_path), "--state", str(state),
                   "--lock-wait-seconds", str(lock_wait_seconds)]
        with log.open("xb") as handle:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=handle,
                                       stderr=subprocess.STDOUT, env=cpu_env(), start_new_session=True)
        record = {"pid": process.pid, "argv": command, "log": str(log), "start_new_session": True,
                  "started": time.time(), "contract_sha256": file_hash(contract_path)}
        record["proc_start_ticks"] = (Path("/proc") / str(process.pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
        write_json(path, record)
        write_json(state / ("launch-" + str(process.pid) + ".json"), record)
        return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("once", "launch"))
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--lock-wait-seconds", type=float, default=43200)
    args = parser.parse_args()
    result = launch(args.contract, args.state, args.lock_wait_seconds) if args.action == "launch" else once(args.contract, args.state, args.lock_wait_seconds)
    print(json.dumps(result, indent=2))
