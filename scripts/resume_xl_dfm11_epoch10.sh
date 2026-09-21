#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
test -f logs/transfer_xl_dfm11/complete.json
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
exec torchrun --nproc_per_node=8 pretrain.py \
  data=dfm11 arch/size@arch=XL \
  arch.bp_max_steps=8 arch.bp_warmup_ratio=0.2 \
  lr=3e-4 lr_auto=true lr_min_ratio=0.5 \
  lr_decay_start_step=2525000 lr_decay_end_step=2550000 \
  lr_rewarm_steps=0 lr_cooldown_checkpoint=null \
  lr_embeddings=null lr_head=null lr_h=null lr_l=null \
  beta1=0.9 beta2=0.95 weight_decay=0.1 ema=0.9999 \
  global_batch_size=262144 gradient_accumulation_steps=2 epochs=10 \
  training_total_steps=2875816 \
  distributed_strategy=fsdp fsdp_params_precision=fp32 \
  fsdp_wrap_policy=transformer_block fsdp_shard_degree=null \
  fsdp_reshard_after_forward=false fsdp_accumulation_sync_mode=no_sync \
  fwd_bwd_dtype=bfloat16 accelerator_type=sm100 \
  activation_checkpointing=none compile_train_batch=true \
  checkpoint_format=sharded checkpoint_interval=1 \
  checkpoint_step_interval=10000 ephemeral_checkpoint_step_interval=500 \
  checkpoint_path=checkpoints/dfm11/XL-from-dfm10-epoch9 \
  resume_checkpoint_path=checkpoints/dfm10/XL-from-dfm9-epoch8 \
  resume_checkpoint_tag=epoch_9 reset_ema_on_resume=false \
  upcast_optimizer_state_on_resume=false \
  project_name=DFM5 \
  'run_name=DFM8-XL clean full from DFM6-DFM7 epoch5' \
  wandb_run_id=dfm8-xl-from-dfm6-dfm7-epoch5-clean-full wandb_resume=must \
  "$@"
