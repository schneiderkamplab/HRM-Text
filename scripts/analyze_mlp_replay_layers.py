"""CPU-only extraction of matched replay layer statistics; no W&B writes."""
import argparse
import json
from pathlib import Path
import statistics


def describe(values):
    return {"median": statistics.median(values), "minimum": min(values), "maximum": max(values)}


def analyze(path):
    rows = [json.loads(line) for line in path.open()]
    metrics = rows[0]["metrics"]
    result = {
        "steps": [row["step"] for row in rows],
        "summaries": {key: describe([row["summary"][key] for row in rows]) for key in rows[0]["summary"]},
        "selected_layers": {}, "highest_median_derived": {},
        "timeline": [{"step": row["step"], **row["summary"]} for row in rows],
        "parameter_rms_change_percent": {}, "optimizer_rms_endpoints": {},
        "nonfinite_fraction_max": max(value for row in rows for key, value in row["metrics"].items()
                                       if key.endswith("nonfinite_fraction")),
    }
    for base in ("L/cycle_003/layer_000", "L/cycle_004/layer_000",
                 "L/cycle_003/layer_005", "H/cycle_001/layer_000"):
        keys = [key for key in metrics if base in key and
                (key.endswith("/rms") or key.endswith("residual_ratio") or key.endswith("gradient_gain") or
                 key.endswith("gate_near_one/mean") or key.endswith("gate_near_zero/mean"))]
        result["selected_layers"][base] = {key: describe([row["metrics"][key] for row in rows]) for key in keys}
    for suffix in ("mlp_residual_ratio", "attn_residual_ratio", "gradient_gain"):
        keys = [key for key in metrics if key.startswith(("derived/H/", "derived/L/")) and key.endswith(suffix)]
        result["highest_median_derived"][suffix] = sorted(
            [{"key": key, **describe([row["metrics"][key] for row in rows])} for key in keys],
            key=lambda item: item["median"], reverse=True)[:10]
    for key, start in metrics.items():
        if key.startswith("parameter/") and key.endswith("value/rms") and start > 0:
            result["parameter_rms_change_percent"][key] = 100 * (rows[-1]["metrics"][key] / start - 1)
        if key.startswith("optimizer/") and key.endswith(("exp_avg/rms", "exp_avg_sq/rms")):
            result["optimizer_rms_endpoints"][key] = {"first": start, "last": rows[-1]["metrics"][key]}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    report = {name: analyze(args.root / name / "layers.jsonl") for name in ("baseline", "regularized")}
    path = args.root / "layer_analysis.json"
    path.write_text(json.dumps(report, indent=2))
    print(path)


if __name__ == "__main__":
    main()
