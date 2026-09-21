import importlib.util
import json
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "xl_campaign", Path(__file__).resolve().parents[1] / "scripts/schedule_dfm11_xl_epoch10.py")
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan


def test_insert_preserves_running_and_gates_xxl(tmp_path):
    active = Job("campaign-dfm10-finish-epoch2", Action.TRAIN_UNTIL_STEP,
                 "training", "active", status=JobStatus.RUNNING)
    wait = Job("wait-600289", Action.WAIT_CHECKPOINT, "checkpoint", "epoch_2")
    barrier = Job("barrier", Action.TERMINAL_BARRIER, "campaign", "barrier",
                  deps=(wait.job_id,), deps_mode="terminal")
    release = Job(campaign.RELEASE, Action.TEARDOWN_EVAL, "campaign", "release", deps=(barrier.job_id,))
    follow = active.with_updates(job_id=campaign.FOLLOW, status=JobStatus.PENDING, deps=(release.job_id,))
    result = campaign.build([active, wait, barrier, release, follow], tmp_path)
    assert result[:4] == [active, wait, barrier, release]
    assert result[-1].deps == (campaign.FINAL_RELEASE,)
    first = next(j for j in result if j.job_id == campaign.PREFIX + "train-2500000")
    assert first.deps == (release.job_id,)
    assert first.metadata["resume_from_tag"] == "epoch_9"
    assert first.metadata["resume_ckpt_path"] == campaign.SOURCE
    for j in result:
        if j.job_id.startswith(campaign.PREFIX) and j.action == Action.TERMINAL_BARRIER:
            assert j.deps_mode == "terminal"


def test_finalize_early_end(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(campaign, "checkpoint_ready", lambda j: (j.metadata["ckpt_tag"] == "epoch_10", ""))
    train = Job(campaign.PREFIX + "train-2900000", Action.TRAIN_UNTIL_STEP,
                "training", "x", status=JobStatus.RUNNING, metadata={"ckpt_tag": "step_2900000"})
    missing = Job(campaign.PREFIX + "missing", Action.WAIT_CHECKPOINT, "checkpoint", "x",
                  metadata={"xl_boundary": 2900000})
    final = missing.with_updates(job_id=campaign.FINAL_WAIT, metadata={}, deps=("old",))
    write_plan(tmp_path / "plan.tsv", [train, missing, final])
    campaign.finalize(tmp_path, 2900000)
    result = read_plan(tmp_path / "plan.tsv")
    assert result[0] == train
    assert result[1].status == JobStatus.SKIPPED
    assert result[2].deps == (train.job_id,)


def test_fractional_epoch(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(campaign, "checkpoint_ready", lambda j: (j.metadata["ckpt_tag"] == "step_2500000", ""))
    cp = tmp_path / campaign.CKPT
    cp.mkdir(parents=True)
    (cp / "checkpoint_state_step_2500000.json").write_text(json.dumps({"global_row_cursor_in_epoch": 25}))
    data = tmp_path / "data/sampled_dfm11/epoch_9"
    data.mkdir(parents=True)
    np.save(data / "inst_start.npy", np.zeros(100))
    train = Job(campaign.PREFIX + "train-2500000", Action.TRAIN_UNTIL_STEP,
                "training", "x", status=JobStatus.RUNNING, metadata={"ckpt_tag": "step_2500000"})
    evaluation = Job(campaign.PREFIX + "eval", Action.EVAL_STANDARD, "standard", "x",
                     metadata={"xl_boundary": 2500000, "eval_epoch": 9.0})
    write_plan(tmp_path / "plan.tsv", [train, evaluation])
    campaign.finalize(tmp_path, 2500000)
    assert read_plan(tmp_path / "plan.tsv")[1].metadata["eval_epoch"] == 9.25
