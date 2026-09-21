"""Run session correctness suites serially and retain reproducible provenance."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

__all__ = []


def _sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("logs/mimir-runtime/build"))
    parser.add_argument("--comparison", type=Path, default=Path("logs/prefixlm-comparison"))
    parser.add_argument("--long-fixture", type=Path, default=Path("logs/mimir-runtime/long-fixture"))
    parser.add_argument("--output", type=Path, default=Path("logs/mimir-runtime/matrix"))
    parser.add_argument("--metal", action="store_true")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--full-context", action="store_true", help="Also stress real Mimir at 4096 tokens")
    args = parser.parse_args()
    runner = (args.build / "bin/mimir-session-tests").resolve()
    root = Path(__file__).resolve().parents[3]
    args.output.mkdir(parents=True, exist_ok=True)
    sources = sorted(path for path in (root / "native/mimir").rglob("*")
                     if path.suffix in {".cpp", ".h", ".py"} or path.name == "CMakeLists.txt")
    report = {
        "platform": platform.platform(), "machine": platform.machine(),
        "runner_sha256": _sha256(runner),
        "library_sha256": {path.name: _sha256(path) for path in sorted((args.build / "bin").glob("lib*")) if path.is_file()},
        "llama_revision": subprocess.check_output(["git", "-C", str(root / "llama.cpp"), "rev-parse", "HEAD"], text=True).strip(),
        "llama_diff_sha256": hashlib.sha256(subprocess.check_output(["git", "-C", str(root / "llama.cpp"), "diff"])).hexdigest(),
        "source_sha256": {str(path.relative_to(root)): _sha256(path) for path in sources},
        "runs": [],
    }
    modes = [("cpu", "off"), ("cpu", "off-f16")]
    if args.metal:
        modes += [("metal", "off"), ("metal", "off-f16"), ("metal", "on")]
    jobs = []
    fixture = args.comparison / "fixture"
    for device, flash in modes:
        for flag in ["true", "false", "absent"]:
            jobs.append((f"tiny-{flag}", fixture / f"hrm-{flag}.gguf", fixture, device, flash))
        jobs.append(("long", fixture / "hrm-true.gguf", args.long_fixture, device, flash))
    if args.real:
        if not args.metal:
            parser.error("--real currently requires --metal; use the executable directly for real CPU runs")
        for flash in ["off", "off-f16", "on"]:
            jobs.append(("real", args.comparison / "real/mimir-f32.gguf", args.comparison / "real", "metal", flash))
    if args.full_context and not args.real:
        parser.error("--full-context requires --real")
    hashes = {}
    for name, model, cases, device, flash in jobs:
        label = f"{name}-{device}-{flash}"
        output = args.output / label
        output.mkdir(exist_ok=True)
        command = [str(runner), str(model.resolve()), str(cases.resolve()), device, flash, str(output.resolve())]
        if args.full_context and name == "real":
            command.append("full-context")
        result_path = output / "result.json"
        result_path.unlink(missing_ok=True)
        with (output / "run.log").open("w") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        result = json.loads(result_path.read_text()) if result_path.exists() else {"pass": False, "checks": []}
        key = str(model.resolve())
        if key not in hashes:
            hashes[key] = _sha256(model)
        report["runs"].append({"name": label, "command": command, "model_sha256": hashes[key],
                               "cases_sha256": _sha256(cases / "cases.json"), "exit_code": completed.returncode,
                               **result})
        (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{label}: {len(result['checks'])} checks, pass={result['pass']}", flush=True)
        if completed.returncode or not result["pass"]:
            raise SystemExit(f"Failed {label}; inspect {output / 'run.log'}")


if __name__ == "__main__":
    _main()
