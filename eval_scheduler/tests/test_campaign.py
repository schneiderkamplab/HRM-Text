from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from eval_scheduler import monitor, plan, runtime
from eval_scheduler.model import Action, Job, JobStatus


def job(
    job_id: str,
    *,
    action: Action = Action.EVAL_STANDARD,
    status: JobStatus = JobStatus.PENDING,
    deps: tuple[str, ...] = (),
    deps_mode: str = "success",
) -> Job:
    return Job(
        job_id=job_id,
        action=action,
        family="test",
        name=job_id,
        status=status,
        deps=deps,
        deps_mode=deps_mode,
    )


def plan_config(tmp_path: Path, model_dir: Path) -> plan.PlanConfig:
    return plan.PlanConfig(
        plan_dir=tmp_path / "plan",
        ckpt_path=str(tmp_path / "checkpoint"),
        ckpt_tag="step_100",
        eval_epoch=1.0,
        log_root=str(tmp_path / "standard"),
        dfm_log_root=str(tmp_path / "dfm"),
        euroeval_log_root=str(tmp_path / "euroeval"),
        wandb_project="test",
        wandb_run_id="test-run",
        wandb_run_name="test run",
        model_prefix="test-model",
        include_checkpoint_wait=False,
        include_hf_export=False,
        hrm_hf_export_dir=str(model_dir),
    )


def test_export_hf_passes_explicit_tokenizer_override(tmp_path: Path, monkeypatch) -> None:
    captured: list[str] = []

    def fake_run_command(argv, **_kwargs):
        captured.extend(argv)
        return 7

    monkeypatch.setattr(runtime, "run_command", fake_run_command)
    export_job = Job(
        job_id="export",
        action=Action.EXPORT_HF,
        family="export",
        name="step_100",
        log_dir=str(tmp_path),
        metadata={
            "ckpt_path": str(tmp_path / "checkpoint"),
            "ckpt_tag": "step_100",
            "hf_export_dir": str(tmp_path / "export"),
            "export_tokenizer_path": str(tmp_path / "tokenizer"),
            "python_bin": "python",
        },
    )

    assert runtime.run_export_hf(export_job, gpu=0) == 7
    assert captured[-2:] == ["--tokenizer_path", str(tmp_path / "tokenizer")]


def test_prepare_hf_variant_copies_export_and_overrides_config(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "model.safetensors").write_bytes(b"weights")
    (source / "config.json").write_text(
        json.dumps({"H_cycles": 2, "L_cycles": 3, "L_bp_cycles": [3, 3]})
    )
    (source / "tokenizer.json").write_text("{}")
    variant_job = Job(
        job_id="variant",
        action=Action.PREPARE_HF_VARIANT,
        family="export",
        name="step_100_lcycles4",
        log_dir=str(tmp_path / "logs"),
        metadata={
            "source_hf_export_dir": str(source),
            "hf_export_dir": str(target),
            "config_overrides": {"L_cycles": 4, "L_bp_cycles": [2, 4]},
        },
    )

    assert runtime.run_prepare_hf_variant(variant_job) == 0
    assert (target / "model.safetensors").read_bytes() == b"weights"
    assert (target / "tokenizer.json").is_file()
    config = json.loads((target / "config.json").read_text())
    assert config["H_cycles"] == 2
    assert config["L_cycles"] == 4
    assert config["L_bp_cycles"] == [2, 4]
    assert runtime.run_prepare_hf_variant(variant_job) == 0


def test_long_context_jobs_are_omitted_for_4k_exports(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"max_position_embeddings": 4096}))

    jobs = plan.make_plan(plan_config(tmp_path, model_dir))

    assert not [job for job in jobs if job.family == "long_context"]


def test_long_context_jobs_are_included_for_8k_exports(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"max_position_embeddings": 8192}))

    jobs = plan.make_plan(plan_config(tmp_path, model_dir))

    assert [job for job in jobs if job.family == "long_context"]


def test_terminal_barrier_accepts_failed_and_unreachable_eval_jobs() -> None:
    jobs = [
        job("export", action=Action.EXPORT_HF, status=JobStatus.FAILED),
        job("eval-failed", status=JobStatus.FAILED, deps=("export",)),
        job("eval-blocked", deps=("export",)),
        job(
            "barrier",
            action=Action.TERMINAL_BARRIER,
            deps=("eval-failed", "eval-blocked"),
            deps_mode="terminal",
        ),
    ]

    assert runtime.dependencies_satisfied(jobs[-1], jobs)


def test_resolve_dfm_shard_archive_prefers_matching_checkpoint(tmp_path: Path) -> None:
    wanted = tmp_path / "step_100" / "inspect" / "wanted.eval"
    stale = tmp_path / "step_50" / "inspect" / "stale.eval"
    wanted.parent.mkdir(parents=True)
    stale.parent.mkdir(parents=True)
    wanted.touch()
    stale.touch()

    assert runtime.resolve_dfm_shard_archive(tmp_path, ckpt_tag="step_100", step="100") == wanted.resolve()


def test_resolve_dfm_shard_archive_rejects_ambiguous_legacy_outputs(tmp_path: Path) -> None:
    for name in ("first", "second"):
        path = tmp_path / name / "inspect" / f"{name}.eval"
        path.parent.mkdir(parents=True)
        path.touch()

    try:
        runtime.resolve_dfm_shard_archive(tmp_path, ckpt_tag="epoch_8", step="2150000")
    except runtime.SchedulerError as exc:
        assert "Ambiguous stale" in str(exc)
    else:
        raise AssertionError("ambiguous archives were accepted")


def test_terminal_barrier_waits_for_runnable_retry() -> None:
    jobs = [
        job("export", action=Action.EXPORT_HF, status=JobStatus.DONE),
        job("eval-retry", deps=("export",)),
        job(
            "barrier",
            action=Action.TERMINAL_BARRIER,
            deps=("eval-retry",),
            deps_mode="terminal",
        ),
    ]

    assert not runtime.dependencies_satisfied(jobs[-1], jobs)


def test_success_dependency_still_blocks_merge_after_eval_failure() -> None:
    jobs = [
        job("eval", status=JobStatus.FAILED),
        job("merge", action=Action.MERGE_STANDARD, deps=("eval",)),
    ]

    assert not runtime.dependencies_satisfied(jobs[-1], jobs)


def test_all_gpu_training_allocation_is_atomic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        runtime,
        "gpu_snapshot",
        lambda _gpu: ("179000", "1000", "180000"),
    )
    runner = runtime.Runner(tmp_path, [0, 1, 2])
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="step_100",
        gpu_policy="all",
        metadata={"min_gpu_free_mib": 178000},
    )
    partial = [0, 1]
    assert runner.select_gpus(training, partial) is None
    assert partial == [0, 1]

    complete = [0, 1, 2]
    assert runner.select_gpus(training, complete) == (0, 1, 2)
    assert complete == []


def test_training_can_resume_from_a_different_checkpoint_root(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_shard = source / "fsdp2_step_50"
    source_shard.mkdir(parents=True)
    (source_shard / ".metadata").touch()
    (source / "checkpoint_state_step_50.json").write_text(
        json.dumps({"step": 50, "checkpoint_kind": "regular", "carry_policy": "none"})
    )
    captured: dict[str, object] = {}

    class Completed:
        pid = 123

        def wait(self):
            return 7

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="step_100",
        log_dir=str(tmp_path / "logs"),
        metadata={
            "command": "python pretrain.py checkpoint_path=target",
            "ckpt_path": str(target),
            "ckpt_tag": "step_100",
            "resume_ckpt_path": str(source),
            "resume_from_tag": "step_50",
            "stop_after_step": 100,
        },
    )

    assert runtime.run_training_until_step(training, (0, 1)) == 7
    argv = captured["argv"]
    assert f"resume_checkpoint_path={source}" in argv
    assert "resume_checkpoint_tag=step_50" in argv


def test_training_checkpoint_requires_regular_sidecar(tmp_path: Path) -> None:
    tag = "step_100"
    checkpoint = tmp_path / "checkpoints"
    shard = checkpoint / f"fsdp2_{tag}"
    shard.mkdir(parents=True)
    (shard / ".metadata").touch()
    for rank in range(2):
        (checkpoint / f"carry_{tag}.{rank}.pt").touch()
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name=tag,
        metadata={
            "ckpt_path": str(checkpoint),
            "ckpt_tag": tag,
            "checkpoint_carry_ranks": 2,
        },
    )

    ready, reason = runtime.training_checkpoint_ready(training, 100)
    assert not ready
    assert "sidecar" in reason

    (checkpoint / f"checkpoint_state_{tag}.json").write_text(
        json.dumps({"step": 100, "checkpoint_kind": "regular"})
    )
    assert runtime.training_checkpoint_ready(training, 100) == (True, "ready")


def test_checkpoint_ready_accepts_completed_no_carry_checkpoint(tmp_path: Path) -> None:
    tag = "step_100"
    checkpoint = tmp_path / "checkpoints"
    shard = checkpoint / f"fsdp2_{tag}"
    shard.mkdir(parents=True)
    (shard / ".metadata").touch()
    job = Job(
        job_id="wait",
        action=Action.WAIT_CHECKPOINT,
        family="checkpoint",
        name=tag,
        metadata={"ckpt_path": str(checkpoint), "ckpt_tag": tag},
    )

    assert runtime.checkpoint_ready(job)[0] is False
    (checkpoint / f"checkpoint_state_{tag}.json").write_text(
        json.dumps({"step": 100, "world_size": 64, "carry_policy": "none"})
    )
    assert runtime.checkpoint_ready(job) == (True, "ready")


def test_checkpoint_ready_uses_sidecar_world_size_for_carry(tmp_path: Path) -> None:
    tag = "step_100"
    checkpoint = tmp_path / "checkpoints"
    shard = checkpoint / f"fsdp2_{tag}"
    shard.mkdir(parents=True)
    (shard / ".metadata").touch()
    (checkpoint / f"checkpoint_state_{tag}.json").write_text(
        json.dumps({"step": 100, "world_size": 2, "carry_policy": "per_rank"})
    )
    job = Job(
        job_id="wait",
        action=Action.WAIT_CHECKPOINT,
        family="checkpoint",
        name=tag,
        metadata={"ckpt_path": str(checkpoint), "ckpt_tag": tag},
    )

    for rank in range(2):
        (checkpoint / f"carry_{tag}.{rank}.pt").touch()
    assert runtime.checkpoint_ready(job) == (True, "ready")


def test_training_command_replaces_stop_target(monkeypatch, tmp_path: Path) -> None:
    process = MagicMock()
    process.wait.return_value = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    monkeypatch.setattr(
        runtime,
        "training_checkpoint_ready",
        MagicMock(side_effect=[(False, "missing"), (True, "ready")]),
    )
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="step_100",
        log_dir=str(tmp_path / "logs"),
        metadata={
            "command": "OMP_NUM_THREADS=1 torchrun --nproc_per_node=2 pretrain.py stop_after_step=50",
            "stop_after_step": 100,
            "ckpt_path": str(tmp_path / "checkpoints"),
            "ckpt_tag": "step_100",
            "workdir": str(tmp_path),
        },
    )

    assert runtime.run_training_until_step(training, (3, 5)) == 0
    argv = popen.call_args.args[0]
    assert "stop_after_step=50" not in argv
    assert argv[-1] == "stop_after_step=100"
    assert popen.call_args.kwargs["env"]["OMP_NUM_THREADS"] == "1"
    assert popen.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"] == "3,5"


def test_training_accepts_natural_epoch_completion(monkeypatch, tmp_path: Path) -> None:
    process = MagicMock()
    process.wait.return_value = 0
    monkeypatch.setattr(runtime.subprocess, "Popen", MagicMock(return_value=process))
    monkeypatch.setattr(
        runtime,
        "training_checkpoint_ready",
        MagicMock(side_effect=[(False, "missing step"), (False, "missing step")]),
    )
    monkeypatch.setattr(
        runtime,
        "checkpoint_ready",
        MagicMock(side_effect=[(False, "missing epoch"), (True, "ready")]),
    )
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="epoch_1",
        log_dir=str(tmp_path / "logs"),
        metadata={
            "command": "torchrun pretrain.py",
            "stop_after_step": 110,
            "ckpt_path": str(tmp_path / "checkpoints"),
            "ckpt_tag": "step_110",
            "completion_checkpoint_tag": "epoch_1",
            "workdir": str(tmp_path),
        },
    )

    assert runtime.run_training_until_step(training, (0, 1)) == 0
    log = (tmp_path / "logs" / "train_until_step_110.log").read_text()
    assert "checkpoint_state_epoch_1.json" in log


def test_training_skips_when_natural_epoch_checkpoint_already_exists(
    monkeypatch, tmp_path: Path
) -> None:
    popen = MagicMock()
    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    monkeypatch.setattr(runtime, "checkpoint_ready", MagicMock(return_value=(True, "ready")))
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="epoch_1",
        metadata={
            "command": "torchrun pretrain.py",
            "stop_after_step": 110,
            "ckpt_path": str(tmp_path / "checkpoints"),
            "ckpt_tag": "step_110",
            "completion_checkpoint_tag": "epoch_1",
        },
    )

    assert runtime.run_training_until_step(training, (0, 1)) == 0
    popen.assert_not_called()


def test_replace_hydra_overrides_handles_added_and_plain_keys() -> None:
    argv = [
        "torchrun",
        "pretrain.py",
        "+stop_after_step=50",
        "resume_checkpoint_tag=step_25",
        "data=dfm8",
    ]

    assert runtime.replace_hydra_overrides(
        argv,
        {
            "stop_after_step": "100",
            "resume_checkpoint_tag": "step_50",
        },
    ) == [
        "torchrun",
        "pretrain.py",
        "data=dfm8",
        "stop_after_step=100",
        "resume_checkpoint_tag=step_50",
    ]


def test_split_command_environment_keeps_command_without_shell() -> None:
    environment, argv = runtime.split_command_environment(
        [
            "OMP_NUM_THREADS=1",
            "MKL_NUM_THREADS=2",
            "torchrun",
            "--nproc_per_node=8",
            "pretrain.py",
        ]
    )

    assert environment == {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "2"}
    assert argv == ["torchrun", "--nproc_per_node=8", "pretrain.py"]


def test_monitor_maps_all_gpu_training_event_to_every_gpu(tmp_path: Path) -> None:
    (tmp_path / "status.tsv").write_text(
        "2026-07-28T19:00:00+02:00\t"
        "START train train_until_step training step_100 "
        "shard_-_of_- gpu_0,1,2 attempt_1_of_1 batch_- mem_free_before_180000\n"
    )

    event = monitor.read_running_events(tmp_path)["train"]
    assert event.gpus == (0, 1, 2)


def test_monitor_reports_training_segment_progress_and_rate_eta(tmp_path: Path) -> None:
    log_dir = tmp_path / "training"
    log_dir.mkdir()
    (log_dir / "train_until_step_150000.log").write_text(
        " 38%|███▊      | 101120/268857 [02:12<28:58:27,  1.60it/s]\n"
    )
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="step_150000",
        log_dir=str(log_dir),
        metadata={
            "resume_from_tag": "ephemeral_step_101000",
            "stop_after_step": 150000,
        },
    )

    progress = monitor.job_progress(training)

    assert progress.text == "step 101120/150000"
    assert progress.fraction == 120 / 49000
    assert progress.eta_seconds == 48880 / 1.6
    assert monitor.progress_eta(progress, elapsed=999999) == "8h29m"


def test_monitor_training_eta_supports_seconds_per_iteration(tmp_path: Path) -> None:
    log_dir = tmp_path / "training"
    log_dir.mkdir()
    (log_dir / "train_until_step_200.log").write_text(
        " 10%|█         | 110/1000 [00:20<29:40,  2.00s/it]\n"
    )
    training = Job(
        job_id="train",
        action=Action.TRAIN_UNTIL_STEP,
        family="training",
        name="step_200",
        log_dir=str(log_dir),
        metadata={"resume_from_tag": "step_100", "stop_after_step": 200},
    )

    progress = monitor.job_progress(training)

    assert progress.text == "step 110/200"
    assert progress.fraction == 0.1
    assert progress.eta_seconds == 180


def test_monitor_uses_tqdm_reported_eta(tmp_path: Path) -> None:
    log = tmp_path / "task.log"
    log.write_text(
        "generation:  25%|██▌       | 20/80 [00:33<01:38,  1.68s/it]\n"
    )

    progress = monitor.tqdm_progress(log)

    assert progress.fraction == 0.25
    assert progress.text == "20/80"
    assert progress.eta_seconds == 98


def test_monitor_reads_live_inspect_archive_progress(tmp_path: Path) -> None:
    inspect_dir = tmp_path / "inspect"
    inspect_dir.mkdir()
    archive_path = inspect_dir / "task.eval"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "_journal/start.json",
            json.dumps({"eval": {"dataset": {"samples": 4}}}),
        )
        archive.writestr("samples/10_epoch_1.json", "{}")
        archive.writestr("samples/11_epoch_1.json", "{}")

    evaluation = Job(
        job_id="dfm",
        action=Action.EVAL_DFM,
        family="dfm",
        name="task",
        log_dir=str(tmp_path),
    )

    progress = monitor.job_progress(evaluation)

    assert progress.fraction == 0.5
    assert progress.text == "samples 2/4"


def test_monitor_marks_complete_inspect_generation_as_finalizing(tmp_path: Path) -> None:
    inspect_dir = tmp_path / "inspect"
    inspect_dir.mkdir()
    with zipfile.ZipFile(inspect_dir / "task.eval", "w") as archive:
        archive.writestr(
            "_journal/start.json",
            json.dumps({"eval": {"dataset": {"samples": 1}}}),
        )
        archive.writestr("samples/10_epoch_1.json", "{}")

    evaluation = Job(
        job_id="dfm",
        action=Action.EVAL_DFM_IFEVAL,
        family="dfm_ifeval",
        name="ifeval-da",
        log_dir=str(tmp_path),
    )

    progress = monitor.job_progress(evaluation)

    assert progress.fraction == 0.999
    assert progress.text == "samples 1/1 finalizing"
