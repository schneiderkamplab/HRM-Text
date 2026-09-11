"""Summarize matched actual-update probes without accessing W&B."""
import argparse
import json
from pathlib import Path


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(root):
    branches = {}
    for name in ("update_control", "update_baseline", "update_regularized"):
        path = root / name
        steps = read_rows(path / "steps.jsonl")
        updates = read_rows(path / "steps.jsonl.updates.jsonl")
        if len(steps) != 10 or steps[-1]["step"] != 453010:
            raise ValueError(f"Incomplete branch: {name}")
        branches[name] = dict(steps=steps, updates=updates)
    control = {row["parameter"]: row for row in branches["update_control"]["updates"][-1]["parameters"]}
    baseline = {row["parameter"]: row for row in branches["update_baseline"]["updates"][-1]["parameters"]}
    differences = {key: max(abs(control[name][key] - baseline[name][key]) for name in control)
                   for key in ("weight_rms_after", "update_rms", "update_to_weight")}
    lines = ["# Actual Parameter-Update Calibration", "",
             "453000 -> 453010; actual AdamATan2 updates, including weight decay.", "",
             "## Measurement Control", "",
             "Final-step maximum absolute statistic differences (control vs frequent probes):", "",
             "```json", json.dumps(differences, indent=2), "```", "",
             "These statistic comparisons supplement CPU bitwise parity tests; they are not full checkpoint bitwise comparisons.", "",
             "## Largest Update/Weight Ratios", "",
             "| Branch | Step | Parameter | Update RMS | Update/weight |",
             "|---|---:|---|---:|---:|"]
    for name in ("update_baseline", "update_regularized"):
        records = [(row["update_to_weight"], batch["step"], row)
                   for batch in branches[name]["updates"] for row in batch["parameters"]]
        for _, step, row in sorted(records, key=lambda item: item[0], reverse=True)[:12]:
            lines.append(f"| {name} | {step} | {row['parameter']} | {row['update_rms']:.6g} | {row['update_to_weight']:.6g} |")
    (root / "update_comparison.json").write_text(json.dumps(dict(control_max_absolute_differences=differences), indent=2))
    (root / "update_comparison.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    summarize(parser.parse_args().root)
