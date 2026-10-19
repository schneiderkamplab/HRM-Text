"""Preview/preflight a separate v2 or matched v1 control continuation; never auto-launch."""

import argparse
import json
from pathlib import Path
import shlex
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stop_training_at_complete_checkpoint import complete

ENV = Path("/home/ucloud/miniforge3/envs/hrm/bin")
ARCHIVE = ROOT / "incoming/mimir-xl-20261015"
SOURCE = ARCHIVE / "checkpoints/dfm15/XL-from-dfm14-epoch1"
DATA = ARCHIVE / "data/sampled_dfm15"
START = 3800000


def command(mode="v2", end=3820000):
    if mode not in ("v2", "control") or end <= START:
        raise ValueError("Choose v2/control and an endpoint after 3.8M")
    name = f"hrm-{mode}-XL-from-3800000"
    args = [str(ENV / "torchrun"), "--nproc_per_node=8", "pretrain.py",
            f"arch/net@arch={'hrm_v2' if mode == 'v2' else 'hrm'}", "arch/size@arch=XL",
            "data=dfm15", f"data.path={DATA}",
            "arch.bp_max_steps=8", "arch.bp_warmup_ratio=0",
            "lr=1e-5", "lr_auto=true", "lr_min_ratio=1", "lr_warmup_steps=0",
            "lr_rewarm_steps=0", "lr_piecewise_points=null", "lr_cooldown_checkpoint=null",
            "lr_embeddings=null", "lr_head=null", "lr_h=null", "lr_l=null",
            "beta1=0.9", "beta2=0.95", "weight_decay=0.1", "ema=0.9999",
            "global_batch_size=262144", "gradient_accumulation_steps=2", "epochs=1",
            "seed=0", f"training_total_steps={end}", f"stop_after_step={end}",
            "distributed_strategy=fsdp", "fsdp_params_precision=fp32",
            "fsdp_wrap_policy=transformer_block", "fsdp_shard_degree=null",
            "fsdp_reshard_after_forward=false", "fsdp_accumulation_sync_mode=no_sync",
            "fwd_bwd_dtype=bfloat16", "accelerator_type=sm100",
            "activation_checkpointing=none", "compile_train_batch=true",
            "checkpoint_format=sharded", "checkpoint_interval=1", "checkpoint_step_interval=5000",
            "ephemeral_checkpoint_step_interval=500", "memory_log_interval=100",
            f"checkpoint_path={ROOT / 'checkpoints/hrm_v2' / name}",
            f"resume_checkpoint_path={SOURCE}", "resume_checkpoint_tag=step_3800000",
            "reset_ema_on_resume=false", "upcast_optimizer_state_on_resume=false",
            "project_name=DFM5", f"run_name={name}", f"wandb_run_id={name}", "wandb_resume=never"]
    if mode == "v2":
        args += ["arch.gates_enabled=true", "arch.gate_initialize_from_v1=true", "arch.gate_warmup_start_step=3800000",
                 "arch.gate_warmup_steps=2000", "arch.gate_alpha_max=1.0"]
    else:
        replacements = {
            'run_name': 'DFM8-XL clean full from DFM6-DFM7 epoch5',
            'wandb_run_id': 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',
            'wandb_resume': 'must',
        }
        args = [f'{a.split("=", 1)[0]}={replacements[a.split("=", 1)[0]]}'
                if '=' in a and a.split('=', 1)[0] in replacements else a for a in args]
    return args


def preflight(mode, end):
    import torch
    import numpy as np
    import torch.distributed.checkpoint as dcp
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    from models.lm_head import LMHead
    from models.baselines.hrm_v2 import HierarchicalReasoningModel
    from models.v2_checkpoint import is_gate_key

    args = command(mode, end)
    with initialize_config_dir(config_dir=str(ROOT / "config"), version_base=None):
        cfg = compose(config_name="cfg_pretrain", overrides=args[3:])
        parsed = PretrainConfig(**OmegaConf.to_container(cfg, resolve=True))
    if not complete(SOURCE, "step_3800000"):
        raise RuntimeError("Source 3.8M checkpoint is incomplete")
    state = json.loads((SOURCE / "checkpoint_state_step_3800000.json").read_text())
    expected = dict(step=START, epoch=1, world_size=8, gradient_accumulation_steps=2,
                    local_batch_size=16384, global_batch_size=262144, seed=0, carry_policy="none")
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError(f"Unexpected resume {key}: {state.get(key)!r}")
    for name in ("local-transfer-verified.json", "full-mixture-verified.json",
                 "math-answer-conditioning-verified.json"):
        if not (DATA / name).is_file():
            raise RuntimeError(f"Missing data receipt: {name}")
    counts = [len(np.load(DATA / "epoch_0" / f"{name}.npy", mmap_mode="r"))
              for name in ("inst_start", "inst_len", "resp_start", "resp_len")]
    if len(set(counts)) != 1 or state["global_row_cursor_in_epoch"] >= counts[0]:
        raise RuntimeError("Dataset indices cannot accommodate the preserved source cursor")
    metadata = yaml.safe_load((SOURCE / "train_metadata.yaml").read_text())
    combined = parsed.arch.model_dump() | metadata | parsed.data.model_dump()
    with torch.device("meta"):
        target = LMHead(HierarchicalReasoningModel(combined), combined)
    source = dcp.FileSystemReader(SOURCE / "fsdp2_step_3800000").read_metadata()
    source_shapes = {key.removeprefix("model."): tuple(value.size)
                     for key, value in source.state_dict_metadata.items() if key.startswith("model.")}
    target_shapes = {key: tuple(value.shape) for key, value in target.state_dict().items()
                     if not is_gate_key(key)}
    if source_shapes != target_shapes:
        raise RuntimeError("Source backbone tensor names/shapes do not match the target")
    if Path(parsed.checkpoint_path).exists():
        raise RuntimeError("Experiment output exists; use an explicit checkpoint resume instead of overwriting")
    gate_count = sum(p.numel() for name, p in target.named_parameters() if is_gate_key(name)) if mode == "v2" else 0
    print(f"Preflight passed: step {START}, epoch 1, row cursor {state['global_row_cursor_in_epoch']}; "
          f"{gate_count:,} new gate parameters.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("v2", "control"), default="v2")
    parser.add_argument("--end-step", type=int, default=3820000)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        preflight(args.mode, args.end_step)
    print('cd ' + shlex.quote(str(ROOT)))
    print('PATH=' + shlex.quote(str(ENV)) + ':"$PATH" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 '
          + shlex.join(command(args.mode, args.end_step)))


if __name__ == "__main__":
    main()
