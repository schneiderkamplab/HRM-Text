"""Isolated training-tokenizer evaluation, followed by the existing XL resume."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_scheduler"))
sys.path.insert(0, str(ROOT))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete

PLAN = ROOT / "logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725"
OLD = "dfm11-xl-e10-2750000-"
NEW = "dfm11-xl-2750k-training-tokenizer-"
OLD_ROOT = "dfm11_XL_epoch10/step_2750000"
NEW_ROOT = "dfm11_XL_2750k_training_tokenizer/step_2750000"
SOURCE = ROOT / "exports/dfm11_XL_epoch10_step_2750000_ema_hf"
EXPORT = SOURCE.with_name(SOURCE.name + "_training_tokenizer")
RUN = "dfm11-xl-2750k-training-tokenizer-20260921"
NAME = "DFM11 XL 2750K EMA training tokenizer (no regex fix)"
CONTROL = PLAN / "tokenizer-comparison-2750k"
TRAIN = "dfm11-xl-e10-train-2800000"
CKPT = ROOT / "checkpoints/dfm11/XL-from-dfm10-epoch9"
TAG = "ephemeral_step_2785500"


def prepare():
    from tokenizers import Tokenizer
    from transformers import AutoTokenizer

    raw_path = ROOT / "data/dfm11_tokenizer/tokenizer.json"
    assert json.loads(raw_path.read_text()) == json.loads((SOURCE / "tokenizer.json").read_text())
    if not EXPORT.exists():
        temp = EXPORT.with_name(EXPORT.name + ".preparing")
        temp.mkdir()
        for path in SOURCE.iterdir():
            if path.suffix == ".safetensors":
                os.link(path, temp / path.name)
            else:
                shutil.copy2(path, temp / path.name)
        config = json.loads((temp / "tokenizer_config.json").read_text())
        config["fix_mistral_regex"] = False
        (temp / "tokenizer_config.json").write_text(json.dumps(config, indent=2) + "\n")
        temp.rename(EXPORT)
    assert json.loads((EXPORT / "tokenizer_config.json").read_text())["fix_mistral_regex"] is False
    assert (EXPORT / "model.safetensors").samefile(SOURCE / "model.safetensors")
    assert (EXPORT / "tokenizer.json").read_bytes() == (SOURCE / "tokenizer.json").read_bytes()
    raw = Tokenizer.from_file(str(raw_path))
    new = AutoTokenizer.from_pretrained(EXPORT, local_files_only=True)
    old = AutoTokenizer.from_pretrained(SOURCE, local_files_only=True)
    samples = ["Hello, world!\nNext line.", "Dansk: et svar, og en forklaring.",
               "def f(x):\n    return x + 1", "\\boxed{42}", '{"name":"search","arguments":{"q":"test"}}']
    samples += [new.apply_chat_template([{"role": "user", "content": s}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False) for s in samples.copy()]
    for sample in samples:
        assert raw.encode(sample, add_special_tokens=False).ids == new.encode(sample, add_special_tokens=False)
    assert any(old.encode(s, add_special_tokens=False) != new.encode(s, add_special_tokens=False) for s in samples)
    assert json.loads(new.backend_tokenizer.to_str())["pre_tokenizer"] == json.loads(raw.to_str())["pre_tokenizer"]
    CONTROL.mkdir(exist_ok=True)
    (CONTROL / "tokenizer_validation.json").write_text(json.dumps(dict(
        source=str(SOURCE), export=str(EXPORT), raw_training_tokenizer=str(raw_path),
        raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        parity_samples=len(samples), fix_mistral_regex=False, weights_unchanged=True), indent=2) + "\n")


def insert():
    assert (PLAN / "stop.request").exists(), "Stop scheduler before editing"
    assert complete(CKPT, TAG)
    prepare()
    with PlanLock(PLAN):
        path = PLAN / "plan.tsv"
        jobs = read_plan(path)
        assert not any(j.job_id.startswith(NEW) for j in jobs), "Already inserted"
        template = [j for j in jobs if j.job_id.startswith(OLD)]
        assert len(template) == 290
        assert all(j.status in (JobStatus.DONE, JobStatus.SKIPPED) for j in template)
        mapping = {j.job_id: j.job_id.replace(OLD, NEW, 1) for j in template}
        added = []
        for job in template:
            meta = copy.deepcopy(job.metadata)
            for key, value in meta.items():
                if isinstance(value, str):
                    meta[key] = value.replace(OLD_ROOT, NEW_ROOT).replace(str(SOURCE), str(EXPORT))
            meta.update(wandb_run_id=RUN, wandb_run_name=NAME,
                        model_prefix="hrm-dfm11-XL-2750k-training-tokenizer",
                        tokenizer_variant="training_no_mistral_regex", fix_mistral_regex=False)
            meta.pop("xl_boundary", None)
            deps = tuple(mapping.get(d, d) for d in job.deps)
            status = JobStatus.SKIPPED if job.status == JobStatus.SKIPPED else JobStatus.PENDING
            if job.action == Action.REPORT:
                # This action writes an unrelated DFM5-L table. Compare separately.
                status = JobStatus.SKIPPED
                meta["skip_reason"] = "Separate tokenizer comparison report"
            log = job.log_dir.replace(OLD_ROOT, NEW_ROOT)
            if log == str(PLAN.relative_to(ROOT)):
                log = str(CONTROL.relative_to(ROOT))
            added.append(job.with_updates(job_id=mapping[job.job_id], metadata=meta,
                deps=deps, status=status, attempt=0, log_dir=log))
        release = next(j for j in added if j.action == Action.TEARDOWN_EVAL)
        train = next(j for j in jobs if j.job_id == TRAIN)
        assert train.status != JobStatus.RUNNING
        meta = dict(train.metadata, resume_from_tag=TAG, resume_ckpt_path=str(CKPT))
        resumed = train.with_updates(status=JobStatus.PENDING, attempt=0,
            deps=(release.job_id,), metadata=meta,
            log_dir="logs/training/dfm11_XL_epoch10/from_2785500_to_2800000")
        index = jobs.index(train)
        result = jobs[:index] + added + [resumed] + jobs[index + 1:]
        known = {j.job_id for j in result}
        assert len(known) == len(result)
        assert all(set(j.deps) <= known for j in result)
        assert all(j.metadata.get("wandb_run_id") == RUN for j in added)
        for j in added:
            for key in ("hf_export_dir", "standard_hf_export_dir", "hrm_hf_export_dir"):
                if key in j.metadata:
                    assert j.metadata[key] == str(EXPORT)
        shutil.copy2(path, CONTROL / "plan.before.tsv")
        write_plan(path, result)
    print(f"Inserted {len(added)} rows; resume {TAG}; W&B {RUN}", flush=True)


def metrics(root):
    result = {}
    for family in ("eval", "dfm_evals", "euroeval"):
        directory = ROOT / "logs" / family / root
        for path in directory.rglob("*metrics.json"):
            data = json.loads(path.read_text())
            for key, value in data.get("metrics", data).items():
                if key.startswith(("eval/", "dfm_eval/", "euroeval/")) and isinstance(value, (int, float)):
                    if key in result and result[key] != value:
                        raise ValueError(f"Conflicting metric {key}: {path}")
                    result[key] = value
    return result


def compare(wait=False):
    while True:
        with PlanLock(PLAN, exclusive=False):
            rows = [j for j in read_plan(PLAN / "plan.tsv") if j.job_id.startswith(NEW)]
        assert rows
        active = [j for j in rows if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]
        # Missing merges stay pending after failures; do not wait indefinitely.
        if not active or not wait:
            break
        states = {j.job_id: j.status for j in rows}
        gpu_done = all(j.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.SKIPPED)
                       for j in rows if j.action.value.startswith("eval_"))
        if gpu_done and not any(j.status == JobStatus.RUNNING for j in rows):
            runnable = [j for j in active if all(states.get(d, JobStatus.DONE) in
                (JobStatus.DONE, JobStatus.SKIPPED) for d in j.deps)]
            if not runnable:
                break
        time.sleep(60)
    baseline, variant = metrics(OLD_ROOT), metrics(NEW_ROOT)
    shared = sorted(baseline.keys() & variant.keys())
    payload = dict(baseline_run="dfm8-xl-from-dfm6-dfm7-epoch5-clean-full", run=RUN,
        checkpoint_step=2750000, missing_variant=sorted(baseline.keys() - variant.keys()),
        jobs={j.job_id: j.status.value for j in rows},
        metrics={k: dict(regex_fix=baseline[k], training_tokenizer=variant[k],
                        delta=variant[k] - baseline[k]) for k in shared})
    (CONTROL / "comparison.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = ["# XL 2750K Tokenizer Comparison", "", "Same EMA weights and eval settings; only tokenizer regex fix differs.",
             "Deltas use each metric's native units. Missing results are not zero scores.", "",
             "| Metric | Regex fix (main) | Training tokenizer | Delta |", "|---|---:|---:|---:|"]
    for key in shared:
        lines.append(f"| {key} | {baseline[key]:.6g} | {variant[key]:.6g} | {variant[key]-baseline[key]:+.6g} |")
    lines += ["", "Missing variant metrics: " + str(len(payload["missing_variant"]))]
    (CONTROL / "comparison.md").write_text("\n".join(lines) + "\n")
    print(f"Compared {len(shared)} metrics; missing {len(payload['missing_variant'])}; {CONTROL}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "insert", "compare", "watch"])
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.mode == "prepare":
        prepare()
    elif args.mode == "insert":
        insert()
    else:
        compare(wait=args.mode == "watch")
