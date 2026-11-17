import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval_scheduler"))

import schedule_engram_pilot as pilot
from eval_scheduler.model import Action, Job, JobStatus


def test_plan_order_budget_and_failure_continuity():
    before = Job(pilot.AFTER, Action.TERMINAL_BARRIER, "control", "after")
    successor = Job(pilot.SUCCESSOR, Action.TRAIN_UNTIL_STEP, "training", "ordinary",
                    deps=("existing",))
    jobs = pilot.build([before, successor])
    assert [j.job_id for j in jobs] == [
        pilot.AFTER, pilot.NAME, pilot.NAME + "-terminal", pilot.SUCCESSOR]
    run, barrier = jobs[1:3]
    assert run.deps_mode == barrier.deps_mode == "terminal"
    assert run.max_retries == 0
    assert run.gpu_count == 8
    assert jobs[-1].deps == ("existing", pilot.NAME + "-terminal")
    args = pilot.command()
    assert "gradient_accumulation_steps=2" in args
    assert "--fallback-gas" in run.metadata["command"]
    assert "arch.ngram_buckets=196608" in args
    assert "resume_checkpoint_tag=step_3800000" in args
    assert "stop_after_step=3820000" in args
    assert "wandb_resume=never" in args
    assert 2 * pilot.BUCKETS * 1536 == 603979776


def test_no_modification_of_live_successor():
    import pytest
    with pytest.raises(AssertionError):
        pilot.build([
            Job(pilot.AFTER, Action.TERMINAL_BARRIER, "control", "after"),
            Job(pilot.SUCCESSOR, Action.TRAIN_UNTIL_STEP, "training", "ordinary",
                status=JobStatus.RUNNING),
        ])


def test_gas_selection_memory_and_oom_classification(tmp_path):
    import pytest
    from run_engram_pilot import headroom, is_oom, set_gas
    assert set_gas(["a", "gradient_accumulation_steps=2"], 4) == [
        "a", "gradient_accumulation_steps=4"]
    with pytest.raises(ValueError):
        set_gas(["a"], 4)
    with pytest.raises(RuntimeError):
        headroom({"min_free_mib_by_gpu": {"0": 10000}})
    assert headroom({"min_free_mib_by_gpu": {str(i): 9000+i for i in range(8)}}) == 9000
    log = tmp_path / "phase-0.log"
    log.write_text("NCCL remote failure\n")
    assert not is_oom(tmp_path)
    log.write_text("torch.OutOfMemoryError: CUDA out of memory.\n")
    assert is_oom(tmp_path)


def test_biased_expert_schedule_is_independent_and_terminal():
    import schedule_biased_expert_pilots as experts
    jobs = [
        Job(experts.AFTER, Action.TERMINAL_BARRIER, "control", "after"),
        Job(experts.SUCCESSOR, Action.TRAIN_UNTIL_STEP, "training", "ordinary",
            deps=("original",)),
    ]
    updated = experts.build(jobs, "test-hash")
    assert len(updated) == 6
    moe, moe_terminal, mos, mos_terminal = updated[1:5]
    assert moe.deps == (experts.AFTER,)
    assert mos.deps == (moe_terminal.job_id,)
    assert updated[-1].deps == ("original", mos_terminal.job_id)
    for run in (moe, mos):
        assert run.deps_mode == "terminal"
        assert run.max_retries == 0
        assert run.metadata["resume_from_tag"] == "step_3800000"
        assert run.metadata["routing_sidecar_sha256"] == "test-hash"
        args = run.metadata["command"]
        assert "+data.routing_categories=true" in args
        assert "+data.homogeneous_categories=false" in args
        assert "arch.routing_bias_decay_end=3820000" in args
    assert moe.metadata["ckpt_path"] != mos.metadata["ckpt_path"]


def test_expert_smoke_overrides_do_not_change_pilot_resume():
    from run_expert_pilot import overrides
    args = ["torchrun", "--nproc_per_node=8", "pretrain.py",
            "resume_checkpoint_tag=step_3800000", "stop_after_step=3820000"]
    short = overrides(args, {"stop_after_step": 3800003})
    assert short[-1] == "stop_after_step=3800003"
    assert short[-2] == args[-2]
    assert args[-1] == "stop_after_step=3820000"
