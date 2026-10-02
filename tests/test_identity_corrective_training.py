from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import yaml

from dfm12 import build_identity_corrective as builder
from dfm12.io import write_json
from scripts import identity_corrective_supervisor as runner


def spec(tmp_path):
    return dict(source=str(runner.SOURCE), state=str(tmp_path), mixture=str(tmp_path / "data"),
                output=str(tmp_path / "checkpoints"), release_receipt=str(tmp_path / "release.json"))


def test_user_five_percent_budget():
    assert builder.IDENTITY_BUDGET == builder.STEPS * builder.GBS * .05 == 131072000
    assert runner.END == builder.START + 10000


@pytest.mark.parametrize("mode", ["none", "full"])
@pytest.mark.parametrize("smoke", [True, False])
def test_training_preserves_optimizer_ema_and_batch(tmp_path, mode, smoke):
    config = runner.training_config(spec(tmp_path), mode, smoke)
    original = yaml.safe_load((runner.SOURCE / "all_config.yaml").read_text())
    for field in ("arch", "beta1", "beta2", "weight_decay", "ema", "reset_ema_on_resume", "upcast_optimizer_state_on_resume"):
        assert config[field] == original[field]
    assert config["ema"] == .9999 and not config["reset_ema_on_resume"]
    assert config["global_batch_size"] == 262144 and config["gradient_accumulation_steps"] == 8
    assert config["lr"] == 1e-5 and config["lr_auto"] and config["lr_min_ratio"] == 1
    assert config["lr_warmup_steps"] == 0 and config["lr_decay_start_step"] is None
    assert config["epochs"] == 16 and config["resume_checkpoint_tag"] == "step_2887261"
    assert config["training_total_steps"] == 2897261
    assert config["stop_after_step"] == (2887264 if smoke else 2897261)
    assert config["wandb_run_id"] == (None if smoke else "dfm12-xl-identity-da-en-1000")


def test_actual_config_accepts_production_model(tmp_path):
    from pretrain import PretrainConfig
    config = PretrainConfig(**runner.training_config(spec(tmp_path), "none", True))
    assert config.ema == .9999


def test_gpu_gate_no_release(tmp_path):
    assert not runner.released(spec(tmp_path))


def test_gpu_gate_requires_all_explicit_flags(tmp_path, monkeypatch):
    s = spec(tmp_path)
    receipt = dict(campaign="identity-corrective10000", retry_finished=True,
                   owned_servers_released=True, gpu_launch_released=True, owned_processes=[{"pid": 123}])
    write_json(s["release_receipt"], receipt)
    monkeypatch.setattr(runner, "same_process", lambda _: True)
    assert not runner.released(s)
    monkeypatch.setattr(runner, "same_process", lambda _: False)
    assert runner.released(s)
    receipt["retry_finished"] = False
    write_json(s["release_receipt"], receipt)
    assert not runner.released(s)


def test_headroom_and_combined_gpu_guard():
    snapshot = [dict(total=100, used=45, owned_used=0) for _ in range(8)]
    assert runner.has_headroom(snapshot)
    snapshot[0]["used"] = 55
    assert not runner.has_headroom(snapshot)
    assert not runner.over_limit(snapshot)
    snapshot[0]["owned_used"] = 48
    assert runner.over_limit(snapshot)


def test_separate_thread_owned_memory_counts_but_foreign_does_not():
    snapshot = [dict(total=100, used=90, owned_used=43, other_thread_owned=10) for _ in range(8)]
    assert runner.over_limit(snapshot)
    assert not runner.has_headroom([dict(g, used=10) for g in snapshot])
    assert not runner.over_limit([dict(g, other_thread_owned=0) for g in snapshot])


def test_smoke_requires_three_update_checkpoint(tmp_path, monkeypatch):
    config = runner.training_config(spec(tmp_path), "none", True)
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(runner, "complete", lambda *_: False)
    with pytest.raises(RuntimeError, match="three-update"):
        runner.verify_smoke_checkpoint(path)


def test_smoke_checkpoint_receipt_and_original_resume(tmp_path, monkeypatch):
    import json
    config = runner.training_config(spec(tmp_path), "none", True)
    path = tmp_path / "smoke.yaml"
    path.write_text(yaml.safe_dump(config))
    root = Path(config["checkpoint_path"])
    (root / "fsdp2_step_2887264").mkdir(parents=True)
    (root / "fsdp2_step_2887264/.metadata").write_bytes(b"fixture")
    state = dict(step=2887264, epoch=16, batch_in_epoch=24, gradient_accumulation_steps=8,
                 global_batch_size=262144, global_row_cursor_in_epoch=10, data_path=config["data"]["path"])
    write_json(root / "checkpoint_state_step_2887264.json", state)
    Path(config["experiment_metrics_output"]).write_text("\n".join(json.dumps(dict(step=step, epoch=16, **{"train/lr": 1e-5, "train/loss": 2.0}))
                                                                  for step in range(2887262, 2887265)))
    path.with_suffix(".log").write_text("\n".join(f"[resume_trace rank={rank}] optim_step_end step={step}"
                                               for rank in range(8) for step in range(2887262, 2887265)))
    monkeypatch.setattr(runner, "complete", lambda *_: True)
    receipt = runner.verify_smoke_checkpoint(path)
    assert receipt["optimizer_updates"] == 3
    assert receipt["actual_training_resume_tag"] == "step_2887261"
    assert not receipt["smoke_weights_reused"]
    assert runner.training_config(spec(tmp_path), "none", False)["resume_checkpoint_tag"] == "step_2887261"
    state["batch_in_epoch"] = 0
    write_json(root / "checkpoint_state_step_2887264.json", state)
    with pytest.raises(RuntimeError, match="three GAS8"):
        runner.verify_smoke_checkpoint(path)


def test_smoke_disk_reserve_retains_both_attempts(tmp_path, monkeypatch):
    from types import SimpleNamespace
    s = spec(tmp_path)
    source = tmp_path / "source/fsdp2_step_2887261"
    source.mkdir(parents=True)
    (source / "payload").write_bytes(b"x" * 100)
    s["source"] = str(source.parent)
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda _: SimpleNamespace(free=300))
    result = runner.disk_preflight(s, True)
    assert result["required_free_bytes"] == 250
    assert result["reserved_checkpoint_count"] == 2
    monkeypatch.setattr(runner.shutil, "disk_usage", lambda _: SimpleNamespace(free=249))
    with pytest.raises(RuntimeError, match="disk"):
        runner.disk_preflight(s, True)


def test_fallback_only_confirmed_cuda_oom(tmp_path):
    path = tmp_path / "smoke.log"
    path.write_text("torch.OutOfMemoryError: CUDA out of memory. Tried to allocate")
    assert runner.cuda_oom_log(path)
    for error in ("NCCL connection timed out", "FileNotFoundError: checkpoint missing", "TimeoutError", "normal exit"):
        path.write_text(error)
        assert not runner.cuda_oom_log(path)
    assert not isinstance(TimeoutError(), runner.MemoryCandidateFailure)
    assert not isinstance(RuntimeError(), runner.MemoryCandidateFailure)


def test_separate_session_child_is_owned():
    import os
    import subprocess
    import sys
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        assert os.getpgid(child.pid) != os.getpgid(os.getpid())
        assert runner.descendant_of(child.pid, os.getpid())
        assert not runner.descendant_of(os.getpid(), child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_nvml_accounts_separate_session_rank_and_foreign(tmp_path, monkeypatch):
    s = spec(tmp_path)
    write_json(s["release_receipt"], dict(owned_processes=[], thread_owned_processes=[dict(pid=50)]))
    monkeypatch.setattr(runner, "same_process", lambda _: True)
    monkeypatch.setattr(runner, "descendant_of", lambda pid, root: (pid, root) in {(11, 10), (51, 50)})
    monkeypatch.setattr(runner, "gpu_snapshot", lambda: [dict(index=0, total=100, used=95,
                       processes=[dict(pid=11, used=43), dict(pid=51, used=10), dict(pid=99, used=42)])])
    result = runner.ownership_snapshot(s, 10)
    assert result[0]["owned_used"] == 43 and result[0]["other_thread_owned"] == 10
    assert runner.over_limit(result)
    assert not result[0]["processes"][2]["owned_training"]


@pytest.mark.parametrize("error", [ProcessLookupError, FileNotFoundError])
def test_worker_exit_between_nvml_and_proc_is_normal(monkeypatch, error):
    def gone(_):
        raise error()
    monkeypatch.setattr(runner, "process_identity", gone)
    workers = {}
    assert not runner.remember_worker(123, workers)
    assert workers == {}


def test_old_partial_subset_rejected_before_reading_paths(tmp_path):
    p = tmp_path / "ready.json"
    write_json(p, dict(final_review_complete=True, reviewed_stochastic_turns=140))
    with pytest.raises(ValueError, match="560"):
        builder.validate_final(p)


def test_stop_does_not_signal_unowned_group(monkeypatch):
    class Process:
        pid = 100
    monkeypatch.setattr(runner, "same_process", lambda _: False)
    monkeypatch.setattr(runner.os, "killpg", lambda *_: pytest.fail("signalled foreign group"))
    runner.stop_owned(Process(), dict(pid=100, pgid=100))


def test_parent_packed_source_verified_and_history_mask_retained(tmp_path):
    from test_pack_identity_preference_sft import fixture
    from scripts.pack_identity_preference_sft import pack
    from dfm12.io import file_hash
    source, metadata = fixture(tmp_path)
    packed = tmp_path / "packed"
    pack(source, packed, metadata)
    ready = tmp_path / "ready.json"
    write_json(ready, dict(final_review_complete=True, reviewed_stochastic_turns=560,
                           packed_root=str(packed), packed_manifest_sha256=file_hash(packed / "manifest.json")))
    root, manifest = builder.validate_final(ready)
    assert root == packed and manifest["final_only_loss"]
    response = np.load(root / "train/epoch_0/resp_len.npy")
    assert response.tolist() == [2]
    np.save(root / "train/epoch_0/resp_len.npy", np.array([3]))
    with pytest.raises(ValueError, match="drift"):
        builder.validate_final(ready)


def test_final_mixture_end_to_end_small_fixture(tmp_path, monkeypatch):
    from test_pack_identity_preference_sft import fixture
    from scripts.pack_identity_preference_sft import pack
    from dfm12.io import file_hash, load
    source, metadata = fixture(tmp_path)
    packed = tmp_path / "packed"
    pack(source, packed, metadata)
    ready = tmp_path / "ready.json"
    write_json(ready, dict(final_review_complete=True, reviewed_stochastic_turns=560,
                           packed_root=str(packed), packed_manifest_sha256=file_hash(packed / "manifest.json")))
    broad = tmp_path / "broad"
    (broad / "epoch_0").mkdir(parents=True)
    np.save(broad / "tokens.npy", np.tile(np.array([1, 2, 3, 4, 5], dtype=np.uint32), 100))
    for key, value in dict(inst_start=np.arange(100) * 5, resp_start=np.arange(100) * 5 + 3,
                           inst_len=np.full(100, 3), resp_len=np.full(100, 2)).items():
        np.save(broad / "epoch_0" / (key + ".npy"), value)
    write_json(broad / "metadata.json", dict(load(metadata), total_length=500))
    monkeypatch.setattr(builder, "STEPS", 1)
    monkeypatch.setattr(builder, "GBS", 256)
    monkeypatch.setattr(builder, "IDENTITY_BUDGET", 13)
    # Tiny fixture checks storage/masking; production packing has its own tests.
    monkeypatch.setattr(builder.shared, "packing_report", lambda arrays, labels, *args: {"row_end_at_stop": len(labels)})
    receipt = builder.build(ready, tmp_path / "mixture", broad)
    assert receipt["sources"][1]["unique_rows"] == 1
    assert receipt["sources"][1]["unique_response_tokens"] == 2
    assert (tmp_path / "mixture/epoch_15").resolve() == (tmp_path / "mixture/epoch_0").resolve()
    assert receipt["heldout_and_validation_excluded"]
