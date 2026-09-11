"""Summarize local replay metrics; never contact W&B."""
import argparse
import json
from pathlib import Path
import statistics
import time


def summarize(rows):
    result = {}
    for name in sorted({key for row in rows for key in row if key.startswith("train/")}):
        values = [row[name] for row in rows if name in row]
        result[name] = dict(mean=statistics.mean(values), median=statistics.median(values),
                            maximum=max(values), count=len(values))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--reference-root", type=Path, help="Compare this regularized branch to an existing baseline and regularized branch")
    args = parser.parse_args()
    root = args.root
    locations = {"baseline": root / "baseline", "regularized": root / "regularized"}
    if args.reference_root:
        locations = {"baseline": args.reference_root / "baseline",
                     "previous_regularized": args.reference_root / "regularized",
                     "new_regularized": root / "regularized"}
    deadline = time.monotonic() + 14 * 3600
    while args.wait and not all((path / "metrics.json").exists() for path in locations.values()):
        state = json.loads((root / "state.json").read_text())
        if state["phase"] == "production_resumed" or time.monotonic() > deadline:
            raise RuntimeError("Replay did not produce both branch metric files; inspect supervisor log")
        time.sleep(30)
    results = {}
    for name, path in locations.items():
        metrics = json.loads((path / "metrics.json").read_text())
        rows = metrics["metric_history"]
        results[name] = {
            "source_directory": str(path.resolve()),
            "median_step_seconds": metrics["median_step_seconds"],
            "all": summarize(rows),
            "historical_burst_window": summarize([row for row in rows if 453400 <= row["step"] <= 453500]),
            "final_200_steps": summarize([row for row in rows if row["step"] > 453800]),
        }
        command = json.loads((path / "command.json").read_text())
        results[name]["coefficient"] = float(next(arg.split("=", 1)[1] for arg in command
            if arg.lstrip("+").startswith("arch.mlp_relative_energy_weight=")))
        telemetry = path / "steps.jsonl"
        if telemetry.exists():
            steps = [json.loads(line) for line in telemetry.read_text().splitlines()]
            results[name]["training_only_median_seconds"] = statistics.median(row["training_seconds"] for row in steps)
            results[name]["total_probe_seconds"] = sum(row["probe_seconds"] for row in steps)
    (root / "comparison.json").write_text(json.dumps(results, indent=2))
    lines = ["# Shared-Prefix MLP Regularizer Replay", "",
        "Common prefix: 451000 to 453000. Branches: 453000 to 454000.",
        "Production remained unchanged. Coefficients below are read from each captured command.", "",
        "With steps.jsonl enabled, metrics cover every optimizer step; otherwise they follow the log interval.",
        "Historical burst reproduction is not guaranteed. This is a short causal probe, not a quality evaluation.", ""]
    for name, result in results.items():
        lines += [f"{name}: coefficient {result['coefficient']:g}.", ""]
        if "training_only_median_seconds" in result:
            lines += [f"{name}: training-only median {result['training_only_median_seconds']:.3f}s; "
                      f"total probe overhead {result['total_probe_seconds']:.1f}s.", ""]
    for window in ("all", "historical_burst_window", "final_200_steps"):
        lines += [f"## {window}", "", "| Metric | " + " | ".join(f"{name} mean / max" for name in locations) + " |",
                  "|---|" + "---:|" * len(locations)]
        for key in sorted({key for result in results.values() for key in result[window]}):
            cells = []
            for name in locations:
                value = results[name][window].get(key)
                cells.append(f"{value['mean']:.6g} / {value['maximum']:.6g}" if value else "n/a")
            lines.append(f"| {key} | {' | '.join(cells)} |")
        lines.append("")
    (root / "comparison.md").write_text("\n".join(lines))
    print(root / "comparison.md")


if __name__ == "__main__":
    main()
