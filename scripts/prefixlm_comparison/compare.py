"""Run the pinned native engines and compare their logits to Transformers."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

__all__ = []


def _sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load(path, entry):
    return np.fromfile(path / entry["file"], dtype=np.float32).reshape(entry["shape"])


def _metrics(expected, actual):
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError("Invalid logit shape or non-finite logits")
    delta = actual.astype(np.float64) - expected
    return {
        "max_abs": float(np.abs(delta).max()),
        "rmse": float(np.sqrt(np.mean(delta ** 2))),
        "relative_l2": float(np.linalg.norm(delta) / max(np.linalg.norm(expected), 1e-30)),
        "top1_agreement": float(np.mean(actual.argmax(-1) == expected.argmax(-1))),
    }


def _compare(oracle_path, result_path, tolerance, suite="tiny"):
    oracle = json.loads((oracle_path / "result.json").read_text())
    actual = json.loads((result_path / "result.json").read_text())
    by_id = {case["id"]: case for case in actual["cases"]}
    checks = []
    for case in oracle["cases"]:
        other = by_id[case["id"]]
        if len(other["steps"]) != len(case["steps"]):
            raise ValueError("Step count mismatch")
        for index, (ref, got) in enumerate(zip(case["steps"], other["steps"], strict=True)):
            check = {"case": case["id"], "step": index, "return_code": got["return_code"]}
            if ref.get("expect_reject", False):
                check["kind"] = "reject_without_mutation"
                check["pass"] = got["return_code"] == -1 and got["kv_before"] == got["kv_after"]
            elif got["return_code"] != 0:
                check.update(kind="logit_parity", **{"pass": False})
            else:
                metrics = _metrics(_load(oracle_path, ref), _load(result_path, got))
                check.update(kind="logit_parity", **metrics)
                check["pass"] = metrics["max_abs"] <= tolerance
            checks.append(check)

    def rows(case, step):
        return _load(result_path, by_id[case]["steps"][step])

    relations = {}
    pairs = [
        ("answer_future_leakage", rows("answer_chunk", 1)[:2], rows("answer_changed", 1)[:2]),
        ("answer_chunk_vs_single", rows("answer_chunk", 1),
         np.concatenate([rows("answer_single", i) for i in range(1, 4)])),
        ("new_turn_vs_fresh", rows("turn_reset", 2), rows("turn_fresh", 0)),
        ("sequence_isolation", rows("isolated_sequence", 2), rows("answer_chunk", 1)),
    ] if suite == "tiny" else [
        (f"{language}_chunk_vs_single", rows(f"{language}-chunk", 1),
         np.concatenate([rows(f"{language}-single", i) for i in range(1, 5)]))
        for language in ["danish", "english", "multiturn"]
    ]
    for name, lhs, rhs in pairs:
        metrics = _metrics(lhs, rhs)
        relations[name] = {**metrics, "pass": metrics["max_abs"] <= tolerance}
    # A changed future prefix token should change an earlier prefix representation.
    if suite == "tiny":
        prefix_effect = float(np.abs(rows("prefix", 0)[0] - rows("prefix_changed", 0)[0]).max())
        relations["prefix_future_visibility"] = {"max_abs_change": prefix_effect, "pass": prefix_effect > 1e-4}
    timings = {}
    for case in actual["cases"]:
        steps = case["steps"]
        if suite == "real" and case["id"].endswith("-single"):
            total_ms = sum(step["ms"] for step in steps[1:])
            timings[case["id"]] = {
                "prefill_ms": steps[0]["ms"],
                "answer_tokens_per_second": 1000 * sum(step["n_tokens"] for step in steps[1:]) / total_ms,
            }
    return {
        "checks": checks, "relations": relations,
        "passed": sum(c["pass"] for c in checks), "total": len(checks),
        "all_pass": all(c["pass"] for c in checks) and all(c["pass"] for c in relations.values()),
        "tolerance_max_abs": tolerance,
        "process_peak_rss_bytes": actual["process_peak_rss_bytes"],
        "model_load_ms": actual["model_load_ms"],
        "timings": timings,
    }


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", default=["baseline", "existing", "replacement"])
    parser.add_argument("--device", choices=["cpu", "metal"], default="cpu")
    parser.add_argument("--flash", choices=["on", "off"], default="off")
    parser.add_argument("--suite", choices=["tiny", "real"], default="tiny")
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    root = args.workspace.resolve()
    label = args.device + ("-flash" if args.flash == "on" else "")
    if args.suite == "real":
        label = "real-" + label
    summary = {"device": args.device, "flash": args.flash, "variants": {}}
    fixture = root / ("real" if args.suite == "real" else "fixture")
    cases = fixture / "cases.json"
    model = fixture / ("mimir-f32.gguf" if args.suite == "real" else "hrm-true.gguf")
    summary["cases_sha256"] = _sha256(cases)
    summary["model_sha256"] = _sha256(model)
    for variant in args.variants:
        result = root / "results" / f"{variant}-{label}"
        effective = "existing" if variant == "proposal-original" else variant
        variant_model = fixture / "hrm-original.gguf" if variant == "proposal-original" else model
        if variant == "proposal-original" and args.suite != "tiny":
            raise ValueError("Exact original checkout currently supported only for the tiny fixture")
        if not args.analyze_only:
            runner = root / "build" / variant / "bin/prefixlm-runner"
            command = [str(runner), str(variant_model), str(cases), str(result), effective, args.device, args.flash]
            with (root / f"run-{variant}-{label}.log").open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        summary["variants"][variant] = _compare(fixture / "oracle", result, args.tolerance, args.suite)
        summary["variants"][variant]["model_sha256"] = (
            summary["model_sha256"] if variant_model == model else _sha256(variant_model))
        got = summary["variants"][variant]
        if args.suite == "tiny" and variant != "proposal-original":
            controls = {}
            for flag in ["false", "absent"]:
                control_dir = root / "results" / f"{variant}-{label}-metadata-{flag}"
                if not args.analyze_only:
                    command = [str(runner), str(fixture / f"hrm-{flag}.gguf"),
                               str(fixture / "metadata-cases.json"), str(control_dir), effective,
                               args.device, args.flash]
                    with (root / f"run-{variant}-{label}-metadata-{flag}.log").open("w") as log:
                        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
                control = json.loads((control_dir / "result.json").read_text())
                entry = control["cases"][0]["steps"][0]
                reference = np.fromfile(fixture / "oracle/causal_control-0.f32", dtype=np.float32)
                actual = _load(control_dir, entry)
                metrics = _metrics(reference.reshape(actual.shape), actual)
                controls[flag] = {**metrics, "capability": control["prefix_capability"],
                                  "pass": not control["prefix_capability"] and metrics["max_abs"] <= args.tolerance}
            got["metadata_controls"] = controls
            got["all_pass"] &= all(c["pass"] for c in controls.values())
        print(f"{variant}: {got['passed']}/{got['total']} reference/admission checks; "
              f"all_pass={got['all_pass']}", flush=True)
    if "existing" in args.variants and "proposal-original" in args.variants:
        maximum = 0.0
        left = root / "results" / f"existing-{label}"
        right = root / "results" / f"proposal-original-{label}"
        entries = json.loads((left / "result.json").read_text())
        for case in entries["cases"]:
            for step in case["steps"]:
                if "file" in step:
                    maximum = max(maximum, _metrics(_load(left, step), _load(right, step))["max_abs"])
        summary["original_vs_adapted_max_abs"] = maximum
        if maximum > args.tolerance:
            raise ValueError("Adapted proposal differs from original; comparison is confounded")
    (root / f"summary-{label}.json").write_text(json.dumps(summary, indent=2) + "\n")
    replacement = summary["variants"].get("replacement")
    if replacement and not replacement["all_pass"]:
        raise SystemExit("Replacement failed correctness checks; inspect summary before benchmarking")


if __name__ == "__main__":
    _main()
