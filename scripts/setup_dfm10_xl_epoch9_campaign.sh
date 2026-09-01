#!/usr/bin/env bash
set -euo pipefail

ROOT=/work/dfm/HRM-Text
PLAN="$ROOT/logs/scheduler/dfm10_XL_epoch9_20260831"
BASE_LOG=dfm10_XL_epoch9
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
TORCHRUN=/home/ucloud/miniforge3/envs/hrm/bin/torchrun
CKPT=checkpoints/dfm10/XL-from-dfm9-epoch8
START_STEP=2127489
END_STEP=2482084
STEPS_PER_EPOCH=354595
WANDB_RUN_ID=dfm8-xl-from-dfm6-dfm7-epoch5-clean-full
WANDB_RUN_NAME="DFM8-XL clean full from DFM6-DFM7 epoch5"

cd "$ROOT"
export PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"

TRAIN_CMD="OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 $TORCHRUN --nproc_per_node=8 pretrain.py data=dfm10 arch/size@arch=XL lr=3e-4 lr_min_ratio=1 lr_warmup_steps=2000 weight_decay=0.1 beta1=0.9 beta2=0.95 ema=0.9999 global_batch_size=262144 gradient_accumulation_steps=2 epochs=9 training_total_steps=$END_STEP distributed_strategy=fsdp fsdp_params_precision=fp32 fsdp_shard_degree=null fsdp_reshard_after_forward=false fsdp_accumulation_sync_mode=no_sync checkpoint_format=sharded fwd_bwd_dtype=bfloat16 activation_checkpointing=none accelerator_type=sm100 compile_train_batch=true checkpoint_interval=1 checkpoint_step_interval=10000 ephemeral_checkpoint_step_interval=500 checkpoint_path=$CKPT resume_checkpoint_path=$CKPT resume_checkpoint_tag=epoch_8 reset_ema_on_resume=false upcast_optimizer_state_on_resume=false project_name=DFM5 run_name='$WANDB_RUN_NAME' wandb_run_id=$WANDB_RUN_ID wandb_resume=allow"

if [[ -e "$PLAN" ]]; then
  echo "Refusing to overwrite existing plan: $PLAN" >&2
  exit 1
fi

eval_epoch() {
  "$PY" - "$1" "$START_STEP" "$STEPS_PER_EPOCH" <<'PY'
import sys
step, start, length = map(int, sys.argv[1:])
print(8.0 + (step - start) / length)
PY
}

create_eval() {
  local step="$1"
  local mode="$2"
  local epoch
  epoch="$(eval_epoch "$step")"
  local export_dir="$ROOT/exports/dfm10_XL_step${step}_ema_hf"
  local args=(
    "$PY" -m eval_scheduler plan create
    --plan-dir "$PLAN"
    --ckpt-path "$CKPT"
    --ckpt-tag "step_${step}"
    --eval-epoch "$epoch"
    --log-root "logs/eval/${BASE_LOG}/step_${step}"
    --dfm-log-root "logs/dfm_evals/${BASE_LOG}/step_${step}"
    --euroeval-log-root "logs/euroeval/${BASE_LOG}/step_${step}"
    --wandb-project DFM5
    --wandb-run-id "$WANDB_RUN_ID"
    --wandb-run-name "$WANDB_RUN_NAME"
    --model-prefix hrm-dfm10-XL-vllm-native-proxy
    --run-euroeval
    --queue-order euroeval-first
    --dfm-ifeval-shards 32
    --max-retries 5
    --standard-batch 128
    --dfm-batch 64
    --ifeval-batch 64
    --euroeval-batch 64
    --python-bin "$PY"
    --standard-config evaluation/config/dfm6_vllm_benchmarking.yaml
    --port-base 57000
    --checkpoint-wait-seconds 60
    --standard-engine-backend vllm
    --standard-hf-export-dir "$export_dir"
    --hrm-server-backend vllm
    --hrm-hf-export-dir "$export_dir"
    --hrm-vllm-native-proxy
    --hrm-vllm-gemma-bfcl-tools
    --hrm-vllm-gemma-bfcl-tool-mode parser
    --vllm-python "$PY"
    --vllm-dtype bfloat16
    --vllm-max-model-len 4096
    --vllm-gpu-memory-utilization 0.9
    --min-gpu-free-mib 178000
    --vllm-attention-backend FLASH_ATTN
    --vllm-extra-args "--enforce-eager --attention-backend FLASH_ATTN --chat-template $ROOT/evaluation/chat_templates/gemma4_native_chat.jinja"
    --euroeval-max-concurrent-calls 64
    --judge-model openai/gemma-4-e4b-judge
    --judge-server-model unsloth/gemma-4-E4B-it
    --judge-server-dtype bfloat16
    --judge-server-attn-implementation sdpa
    --judge-server-max-new-tokens 64
    --judged-max-connections 32
    --judged-batch 32
    --judged-vllm-gpu-memory-utilization 0.65
    --judged-min-gpu-free-mib 178000
    --govreport-max-report-chars 9000
  )
  if [[ "$mode" == append ]]; then
    args+=(--append)
  else
    args+=(--force)
  fi
  "${args[@]}"
}

add_release() {
  local step="$1"
  "$PY" -m eval_scheduler plan add-eval-release \
    --plan-dir "$PLAN" \
    --checkpoint-tag "step_${step}" \
    --barrier-job-id "campaign-barrier-${step}" \
    --teardown-job-id "campaign-teardown-${step}"
}

add_training() {
  local source="$1"
  local target="$2"
  local resume_tag="$3"
  local deps="$4"
  local completion_tag="${5:-}"
  local args=(
    "$PY" -m eval_scheduler plan add-training
    --plan-dir "$PLAN"
    --job-id "campaign-train-${target}"
    --stop-after-step "$target"
    --command "$TRAIN_CMD"
    --checkpoint-path "$CKPT"
    --log-dir "logs/training/dfm10_XL_epoch9/${source}_to_${target}"
    --resume-from-tag "$resume_tag"
    --workdir "$ROOT"
    --checkpoint-carry-ranks 8
    --min-gpu-free-mib 178000
  )
  [[ -n "$deps" ]] && args+=(--deps "$deps")
  [[ -n "$completion_tag" ]] && args+=(--completion-checkpoint-tag "$completion_tag")
  "${args[@]}"
}

checkpoints=(2150000 2200000 2250000 2300000 2350000 2400000 2450000 "$END_STEP")

for index in "${!checkpoints[@]}"; do
  step="${checkpoints[$index]}"
  if (( index == 0 )); then
    create_eval "$step" fresh
    add_release "$step"
    add_training epoch_8 "$step" epoch_8 ""
  else
    previous="${checkpoints[$((index - 1))]}"
    create_eval "$step" append
    add_release "$step"
    if [[ "$step" == "$END_STEP" ]]; then
      add_training "$previous" "$step" "step_${previous}" "campaign-teardown-${previous}" epoch_9
    else
      add_training "$previous" "$step" "step_${previous}" "campaign-teardown-${previous}"
    fi
  fi
done

"$PY" -m eval_scheduler stop --plan-dir "$PLAN"
"$PY" -m eval_scheduler status --plan-dir "$PLAN"
