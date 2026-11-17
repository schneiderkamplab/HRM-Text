"""Queue independent dense 2/2 MoE and MoS source-biased XL pilots."""
import argparse
import json
import math
from pathlib import Path
import time

import prepare_hrm_v2_xl as prepare
import schedule_mimir2_3820k as schedule
from eval_scheduler.model import Action, Job, JobStatus
from run_expert_pilot import check_sidecar

KINDS = ("moe", "mos")
AFTER = "hrm-engram-moe-budget-XL-from-3800000-terminal"
SUCCESSOR = "xl-dfm15-train-3900000"
RECEIPT = prepare.ROOT / "data/category_preparation/dfm15-epoch0-source-domains-published-20261020/receipt.json"
SIDECAR = prepare.DATA / "epoch_0/category_id.npy"
BIAS = [[0, 0], [math.log(2), -math.log(2)], [-math.log(2), math.log(2)]]


def name(kind):
    if kind not in KINDS:
        raise ValueError(kind)
    return f"hrm-biased-{kind}2of2-XL-from-3800000"


def command(kind):
    run = name(kind)
    replacements = {
        "arch/net@arch": "hrm_v2", "checkpoint_path": str(prepare.ROOT / "checkpoints/hrm_v2" / run),
        "run_name": run, "wandb_run_id": run, "wandb_resume": "never",
    }
    args = [f'{a.split("=", 1)[0]}={replacements[a.split("=", 1)[0]]}'
            if "=" in a and a.split("=", 1)[0] in replacements else a
            for a in prepare.command("control")]
    args += [
        "+data.routing_categories=true", "+data.homogeneous_categories=false",
        "arch.upcycle_from_dense=true", "arch.gates_enabled=false",
        "arch.gate_initialize_from_v1=false", "arch.ngram_orders=[]",
        "arch.residual_branches=1", "arch.h_memory_branches=1", "arch.l_memory_branches=1",
        "arch.expert_freeze_base=false", "arch.specialist_training=false",
        f"arch.{kind}_num_experts=2", f"arch.{kind}_top_k=2", f"arch.{kind}_sparse=false",
        f"arch.{kind}_metadata_bias=" + json.dumps(BIAS, separators=(",", ":")),
        "arch.routing_bias_decay_start=3810000", "arch.routing_bias_decay_end=3820000",
    ]
    args += ["arch.moe_levels=both", "arch.mos_num_experts=1"] if kind == "moe" else [
        "arch.moe_num_experts=1", "arch.mos_state_mode=shared"]
    return args


def preflight(kind):
    import torch
    import yaml
    import torch.distributed.checkpoint as dcp
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    from models.lm_head import LMHead
    from models.baselines.hrm_v2 import HierarchicalReasoningModel
    from models.expert_mixtures import dense_source_key, is_new_v2_key
    with initialize_config_dir(config_dir=str(prepare.ROOT / "config"), version_base=None):
        cfg = compose(config_name="cfg_pretrain", overrides=command(kind)[3:])
        parsed = PretrainConfig(**OmegaConf.to_container(cfg, resolve=True))
    metadata = yaml.safe_load((prepare.SOURCE / "train_metadata.yaml").read_text())
    combined = parsed.arch.model_dump() | metadata | parsed.data.model_dump()
    with torch.device("meta"):
        model = LMHead(HierarchicalReasoningModel(combined), combined)
    stored = dcp.FileSystemReader(prepare.SOURCE / "fsdp2_step_3800000").read_metadata()
    source = {k.removeprefix("model."): tuple(v.size)
              for k, v in stored.state_dict_metadata.items() if k.startswith("model.")}
    used = set()
    for key, value in model.state_dict().items():
        original = dense_source_key(key)
        if original in source:
            assert tuple(value.shape) == source[original], key
            used.add(original)
        else:
            assert is_new_v2_key(key), key
    assert used == set(source)
    assert parsed.data.routing_categories and not parsed.data.homogeneous_categories
    assert parsed.global_batch_size == 262144
    assert not Path(parsed.checkpoint_path).exists()
    return dict(kind=kind, total_parameters=sum(p.numel() for p in model.parameters()),
                checkpoint_mapping_valid=True, unchanged_sampler=True)


def build(jobs, sidecar_hash):
    by_id = {j.job_id: j for j in jobs}
    assert AFTER in by_id
    assert by_id[SUCCESSOR].status == JobStatus.PENDING
    assert all(name(kind) not in by_id for kind in KINDS)
    added = []
    dependency = AFTER
    for kind in KINDS:
        run = name(kind)
        output = prepare.ROOT / "checkpoints/hrm_v2" / run
        wrapped = ["OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1", str(prepare.ENV / "python"),
                   str(prepare.ROOT / "scripts/run_expert_pilot.py"),
                   "--qualification-root", str(prepare.ROOT / "logs/expert-pilot-qualification" / run),
                   "--sidecar", str(SIDECAR), "--sidecar-sha256", sidecar_hash,
                   "--", *command(kind)]
        pilot = Job(run, Action.TRAIN_UNTIL_STEP, "training", run,
                    deps=(dependency,), deps_mode="terminal", gpu_policy="all", gpu_count=8,
                    max_retries=0, log_dir=str(prepare.ROOT / "logs/training/hrm_v2" / run),
                    metadata=dict(command=wrapped, workdir=str(prepare.ROOT),
                                  stop_after_step=3820000, ckpt_path=str(output), ckpt_tag="step_3820000",
                                  checkpoint_carry_ranks=8, resume_ckpt_path=str(prepare.SOURCE),
                                  resume_from_tag="step_3800000", min_gpu_free_mib=178000,
                                  routing_sidecar_sha256=sidecar_hash))
        terminal = Job(run + "-terminal", Action.TERMINAL_BARRIER, "control",
                       "Continue after pilot even when qualification/training fails",
                       deps=(run,), deps_mode="terminal")
        added.extend([pilot, terminal])
        dependency = terminal.job_id
    updated = []
    for job in jobs:
        if job.job_id == SUCCESSOR:
            updated.extend(added)
            job = job.with_updates(deps=(*job.deps, dependency))
        updated.append(job)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["status"] == "verified" and receipt["published"]
    assert receipt["uncovered_rows"] == 0 and receipt["epoch"] == 0
    check_sidecar(SIDECAR, receipt["category_sha256"])
    state = json.loads((prepare.SOURCE / "checkpoint_state_step_3800000.json").read_text())
    assert state["carry_policy"] == "none"
    assert prepare.complete(prepare.SOURCE, "step_3800000")
    for kind in KINDS:
        print(json.dumps(preflight(kind)), flush=True)
    store = schedule.SQLiteJobStore(schedule.plan_database(schedule.base.PLAN / "plan.tsv"))
    if store.get_admin_lock():
        raise RuntimeError("Existing plan edit lock")
    if args.install:
        store.set_admin_lock(True)
    try:
        updated = build(store.load_jobs(), receipt["category_sha256"])
        if args.install:
            store.backup(schedule.base.PLAN / f"before-biased-experts-{int(time.time())}.sqlite")
            store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(schedule.base.PLAN / "plan.tsv")
            store.backup(schedule.base.PLAN / "state.backup.sqlite")
        print(json.dumps(dict(installed=args.install, pilots=[name(k) for k in KINDS],
                              after=AFTER, before=SUCCESSOR), indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == "__main__":
    main()
