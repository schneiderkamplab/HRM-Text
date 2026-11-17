"""Preview a five-step XL FSDP compiled save/resume qualification; --run opts in.

Requires all eight GPUs idle immediately before each launch. Never schedules,
stops other processes, or writes to production checkpoints. W&B disabled.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

from prepare_hrm_v2_xl import ROOT, SOURCE, command
from stop_training_at_complete_checkpoint import complete


def commands(output, buckets=65536, gas=2, warmup_steps=2000):
    base = command("v2", 3800003)
    changes = {
        "arch.gates_enabled": "false",
        "arch.gate_initialize_from_v1": "false",
        "checkpoint_path": str(output),
        "memory_log_interval": "1",
        "ephemeral_checkpoint_step_interval": "null",
        "run_name": "engram-xl-qualification",
        "wandb_run_id": "null",
        "wandb_resume": "null",
        "gradient_accumulation_steps": str(gas),
    }
    base = [f'{arg.split("=", 1)[0]}={changes[arg.split("=", 1)[0]]}'
            if "=" in arg and arg.split("=", 1)[0] in changes else arg for arg in base]
    base += ["arch.upcycle_from_dense=true", "arch.ngram_orders=[2,3]",
             "arch.ngram_heads=4", "arch.ngram_contextual_gate=true",
             f"arch.ngram_buckets={buckets}", "arch.ngram_warmup_start_step=3800000",
             f"arch.ngram_warmup_steps={warmup_steps}"]
    resume = dict(resume_checkpoint_path=str(output), resume_checkpoint_tag="step_3800003",
                  stop_after_step="3800005", training_total_steps="3800005",
                  **{"arch.upcycle_from_dense": "false"})
    second = [f'{arg.split("=", 1)[0]}={resume[arg.split("=", 1)[0]]}'
              if "=" in arg and arg.split("=", 1)[0] in resume else arg for arg in base]
    return base, second


def validate_configuration(argv):
    import torch
    import torch.distributed.checkpoint as dcp
    import yaml
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    from models.baselines.hrm_v2 import HierarchicalReasoningModel
    from models.lm_head import LMHead
    from models.expert_mixtures import is_new_v2_key

    with initialize_config_dir(config_dir=str(ROOT / "config"), version_base=None):
        parsed = PretrainConfig(**OmegaConf.to_container(
            compose(config_name="cfg_pretrain", overrides=argv[3:]), resolve=True))
    metadata = yaml.safe_load((SOURCE / "train_metadata.yaml").read_text())
    native = parsed.arch.model_dump() | metadata | parsed.data.model_dump()
    with torch.device("meta"):
        model = LMHead(HierarchicalReasoningModel(native), native)
    source = dcp.FileSystemReader(SOURCE / "fsdp2_step_3800000").read_metadata()
    source_shapes = {key.removeprefix("model."): tuple(value.size)
                     for key, value in source.state_dict_metadata.items()
                     if key.startswith("model.")}
    inherited = {key: tuple(value.shape) for key, value in model.state_dict().items()
                 if not is_new_v2_key(key)}
    if source_shapes != inherited:
        raise RuntimeError("Candidate backbone differs from source checkpoint metadata")
    return dict(stop_after_step=parsed.stop_after_step,
                compile_train_batch=parsed.compile_train_batch,
                configuration_valid=True,
                inherited_checkpoint_shapes_valid=True,
                ngram_parameters=sum(p.numel() for p in model.model.ngram.parameters()))


def assert_idle():
    processes = subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], text=True).strip()
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
         "--format=csv,noheader,nounits"], text=True).strip().splitlines()
    if processes or len(rows) != 8:
        raise RuntimeError("XL smoke requires eight unoccupied GPUs; no launch")
    for row in rows:
        _, memory, utilization = map(int, row.split(","))
        if memory > 100 or utilization != 0:
            raise RuntimeError("GPU is not idle; no launch")


def gpu_memory():
    rows = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=index,memory.total,memory.used",
         "--format=csv,noheader,nounits"], text=True).strip().splitlines()
    values = [tuple(map(int, row.split(","))) for row in rows]
    if len(values) != 8:
        raise RuntimeError("Expected memory telemetry for all eight GPUs")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--buckets", type=int, default=65536)
    parser.add_argument("--gas", type=int, choices=(2, 4, 8), default=2)
    parser.add_argument("--warmup-steps", type=int, default=2000)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "logs/engram-preparation-20261020/xl-smoke")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("Use a new output directory; never overwrite a smoke")
    argv = commands(output / "checkpoints", args.buckets, args.gas, args.warmup_steps)
    for phase in argv:
        validate_configuration(phase)
    if not args.run:
        for phase in argv:
            print("WANDB_MODE=disabled " + shlex.join(phase))
        return
    if not complete(SOURCE, "step_3800000"):
        raise RuntimeError("Candidate source checkpoint is incomplete")
    run_phases(argv, output, gas=args.gas, buckets=args.buckets)


def run_phases(argv, output, *, gas, buckets=None):
    """Run isolated native save/resume phases with identical memory telemetry."""
    assert_idle()
    output.mkdir(parents=True)
    env = dict(os.environ, WANDB_MODE="disabled", WANDB_DISABLED="true",
               CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1",
               PATH="/home/ucloud/miniforge3/envs/hrm/bin:" + os.environ["PATH"])
    durations = []
    minimum_free = {}
    for index, phase in enumerate(argv):
        assert_idle()
        start = time.monotonic()
        with (output / f"phase-{index}.log").open("w") as log:
            process = subprocess.Popen(phase, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT)
            try:
                while True:
                    for gpu, total, used in gpu_memory():
                        minimum_free[gpu] = min(minimum_free.get(gpu, total), total - used)
                    try:
                        code = process.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                # torchrun owns its workers and propagates termination to them.
                process.terminate()
                process.wait()
                raise
            if code:
                raise subprocess.CalledProcessError(code, phase)
        durations.append(time.monotonic() - start)
        tag = "step_3800003" if index == 0 else "step_3800005"
        if not complete(output / "checkpoints", tag):
            raise RuntimeError(f"Incomplete smoke checkpoint: {tag}")
    (output / "result.json").write_text(json.dumps(
        dict(phase_wall_seconds=durations, steps=[3, 2],
             gas=gas, buckets=buckets,
             min_free_mib_by_gpu=minimum_free,
             note="Wall time includes compile/load/save; use per-step memory/time in phase logs. "
                  "Memory sampled each second; this is not a guarantee of future peak memory. "
                  "Five steps do not establish long-run stability."), indent=2))


if __name__ == "__main__":
    main()
