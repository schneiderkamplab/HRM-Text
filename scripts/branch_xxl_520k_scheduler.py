"""Redirect only future rows after the old run stops and its clone is synced."""
import csv
import io
import json
import os
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval_scheduler"))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import read_plan


def main():
    plan = Path("logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725")
    complete = Path("logs/wandb_clones/xxl_restart520k_20260910/complete.json")
    if not complete.exists() or json.loads(complete.read_text())["max_step"] != 520000:
        raise RuntimeError("Clone must complete before changing the plan")
    if "Training stopped." not in Path("logs/stability/stop_xxl_532000_20260910.log").read_text():
        raise RuntimeError("Old training has not stopped")
    checkpoint = "checkpoints/dfm10/XXL-from-520000-half-lr"
    run_id = "xxl-restart520k-20260910"
    name = "dfm8-XXL restart520K half LR"
    replacements = {
        "checkpoints/dfm10/XXL-from-dfm8-epoch1": checkpoint,
        "dfm10_XXL_epoch2_from_dfm8_epoch1": "dfm10_XXL_restart520k_half_lr",
        "dfm10_XXL_epoch2": "dfm10_XXL_restart520k_half_lr",
        "hrm-dfm10-XXL-epoch2-vllm-native-proxy": "hrm-dfm10-XXL-restart520k-half-lr",
        "40j5y877": run_id,
    }

    def replace(value):
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
            if value == "dfm8-XXL-1epoch":
                value = name
        elif isinstance(value, dict):
            value = {k: replace(v) for k, v in value.items()}
        elif isinstance(value, list):
            value = [replace(v) for v in value]
        return value

    with PlanLock(plan):
        original = (plan / "plan.tsv").read_text()
        lines = original.splitlines(keepends=True)
        changed = []
        for i, line in enumerate(lines[1:], 1):
            fields = next(csv.reader([line], delimiter="\t"))
            meta = json.loads(fields[-1])
            if fields[15] not in ("pending", "failed") or (
                "step_550000" not in (meta.get("ckpt_tag"), meta.get("checkpoint_tag"))
                and "step_600000" not in (meta.get("ckpt_tag"), meta.get("checkpoint_tag"))
                and "epoch_2" not in (meta.get("ckpt_tag"), meta.get("checkpoint_tag"))
                and fields[0] != "campaign-dfm10-finish-epoch2"
            ):
                continue
            meta = replace(meta)
            fields[17] = replace(fields[17])
            if fields[1] == "train_until_step":
                argv = shlex.split(meta["command"])
                overrides = dict(lr="7.5e-5", lr_h="3.75e-5", lr_l="2.5e-5",
                                 checkpoint_path=checkpoint, run_name=name,
                                 wandb_run_id=run_id)
                argv = [a for a in argv if a.lstrip("+").split("=", 1)[0] not in overrides]
                argv.extend(f"{k}={v}" for k, v in overrides.items())
                meta["command"] = shlex.join(argv)
                if fields[0] == "campaign-dfm10-train-550000":
                    meta["resume_from_tag"] = "step_520000"
                    fields[15], fields[16] = "pending", "0"
                    fields[17] = "logs/training/dfm10_XXL_restart520k_half_lr/from_520000_to_550000"
            fields[-1] = json.dumps(meta, separators=(",", ":"))
            out = io.StringIO()
            csv.writer(out, delimiter="\t", lineterminator="\n").writerow(fields)
            lines[i] = out.getvalue()
            changed.append(fields[0])
        if "campaign-dfm10-train-550000" not in changed or len(changed) < 800:
            raise RuntimeError(f"Unexpected future row selection: {len(changed)}")
        backup = plan / "plan.tsv.before_520k_branch_20260910"
        with backup.open("x") as handle:
            handle.write(original)
        tmp = plan / "plan.tsv.branch.tmp"
        tmp.write_text("".join(lines))
        read_plan(tmp)
        os.replace(tmp, plan / "plan.tsv")
    print(f"Redirected {len(changed)} future rows; scheduler remains paused")


if __name__ == "__main__":
    main()
