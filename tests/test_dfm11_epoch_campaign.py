import importlib.util
import json
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "campaign", Path(__file__).resolve().parents[1] / "scripts/schedule_dfm11_epoch3.py")
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan


def test_finalize_early_end_skips_future_and_releases_final(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(campaign, "checkpoint_ready",
                        lambda j: (j.metadata["ckpt_tag"] == "epoch_3", ""))
    train = Job("dfm11-e3-train-650000", Action.TRAIN_UNTIL_STEP, "training", "x",
                status=JobStatus.RUNNING, metadata={"ckpt_tag": "step_650000"})
    missing = Job("dfm11-e3-missing", Action.WAIT_CHECKPOINT, "checkpoint", "x",
                  metadata={"dfm11_boundary": 650000})
    future = missing.with_updates(job_id="dfm11-e3-future", metadata={"dfm11_boundary": 700000})
    final = missing.with_updates(job_id="dfm11-e3-epoch_3-wait-600289", metadata={}, deps=("old",))
    write_plan(tmp_path / "plan.tsv", [train, missing, future, final])
    campaign.finalize(tmp_path, 650000)
    result = read_plan(tmp_path / "plan.tsv")
    assert result[0] == train
    assert result[1].status == result[2].status == JobStatus.SKIPPED
    assert result[3].status == JobStatus.PENDING
    assert result[3].deps == (train.job_id,)


def test_finalize_fraction_from_dataset_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(campaign, "checkpoint_ready",
                        lambda j: (j.metadata["ckpt_tag"] == "step_650000", ""))
    cp = tmp_path / campaign.CKPT
    cp.mkdir(parents=True)
    (cp / "checkpoint_state_step_650000.json").write_text(json.dumps({"global_row_cursor_in_epoch": 25}))
    data = tmp_path / "data/sampled_dfm11/epoch_2"
    data.mkdir(parents=True)
    np.save(data / "inst_start.npy", np.zeros(100))
    train = Job("dfm11-e3-train-650000", Action.TRAIN_UNTIL_STEP, "training", "x",
                status=JobStatus.RUNNING, metadata={"ckpt_tag": "step_650000"})
    evaluation = Job("dfm11-e3-eval", Action.EVAL_STANDARD, "standard", "x",
                     metadata={"dfm11_boundary": 650000, "eval_epoch": 2.0})
    write_plan(tmp_path / "plan.tsv", [train, evaluation])
    campaign.finalize(tmp_path, 650000)
    assert read_plan(tmp_path / "plan.tsv")[1].metadata["eval_epoch"] == 2.25
