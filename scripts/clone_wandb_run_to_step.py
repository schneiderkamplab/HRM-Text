"""Snapshot and clone numeric run history through an inclusive global-step cutoff.

Never copies the source summary: it may contain results after the cutoff.
The new run must not already exist. Source artifacts remain on the source run.
"""
import argparse
import json
import math
from pathlib import Path

import wandb


def clean_history_row(raw, max_step):
    step = raw.get("_step")
    if not isinstance(step, int) or not 0 <= step <= max_step:
        return None
    payload = {k: v for k, v in raw.items() if not k.startswith("_")
               and isinstance(v, (int, float)) and math.isfinite(v)}
    if not payload:
        return None
    if any(k.startswith("train/") for k in payload):
        payload.setdefault("train/step", step)
    return {"_step": step, **payload}


def metric_axis(key):
    prefix = key.split("/", 1)[0]
    if prefix == "train" or key == "bp_steps":
        return "train/step"
    if prefix.startswith(("eval", "dfm_eval", "euroeval", "lite_", "avg", "headline_avg", "suite_avg")):
        return f"{prefix}/epoch"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="entity/project/run")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--max-step", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config-json", type=Path, required=True)
    args = parser.parse_args()
    api = wandb.Api(timeout=120)
    source = api.run(args.source)
    entity, project, _ = args.source.split("/")
    try:
        api.run(f"{entity}/{project}/{args.target_id}")
    except wandb.errors.CommError as exc:
        if "could not find run" not in str(exc).lower():
            raise
    else:
        raise RuntimeError("Refusing to append a clone to an existing destination")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    config = dict(source.config)
    config.update(json.loads(args.config_json.read_text()))
    config.update(project_name=project, run_name=args.target_name,
                  wandb_run_id=args.target_id, wandb_resume="allow",
                  history_clone_source=args.source, history_clone_cutoff=args.max_step)
    (args.output_dir / "config.json").write_text(json.dumps(config, indent=2))
    count = 0
    counts = {}
    last = -1
    with (args.output_dir / "history.jsonl").open("w") as handle:
        for raw in source.scan_history(max_step=args.max_step + 1, page_size=5000):
            row = clean_history_row(raw, args.max_step)
            if row is None:
                continue
            if row["_step"] <= last:
                raise RuntimeError("Source history must be strictly ordered by step")
            last = row["_step"]
            handle.write(json.dumps(row) + "\n")
            count += 1
            for key in row:
                if key != "_step":
                    counts[key] = counts.get(key, 0) + 1
            if count % 10000 == 0:
                print(f"downloaded={count} step={last}", flush=True)
    if last != args.max_step or counts.get("train/loss", 0) == 0:
        raise RuntimeError(f"Expected training history ending at {args.max_step}, found {last}")
    print(f"snapshot complete rows={count} last_step={last} metrics={len(counts)}", flush=True)
    run = wandb.init(entity=entity, project=project, id=args.target_id,
                     name=args.target_name, resume="never", config=config,
                     tags=list(source.tags) + ["history-clone", "restart-520k"],
                     settings=wandb.Settings(init_timeout=300))
    axes = {axis for key in counts if (axis := metric_axis(key))}
    for axis in sorted(axes):
        run.define_metric(axis)
    for key in counts:
        if key not in axes:
            axis = metric_axis(key)
            run.define_metric(key, **({"step_metric": axis} if axis else {}))
    with (args.output_dir / "history.jsonl").open() as handle:
        for i, line in enumerate(handle, 1):
            row = json.loads(line)
            step = row.pop("_step")
            run.log(row, step=step)
            if i % 10000 == 0:
                print(f"replayed={i}/{count} step={step}", flush=True)
    run.finish()
    report = dict(source=args.source, target=f"{entity}/{project}/{args.target_id}",
                  rows=count, max_step=last, metric_counts=counts)
    (args.output_dir / "complete.json").write_text(json.dumps(report, indent=2))
    print(f"clone synced: {report['target']} rows={count} max_step={last}", flush=True)


if __name__ == "__main__":
    main()
