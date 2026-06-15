#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

EVAL_EPOCH="1.9112836727227056"

run_lite_eval() {
  local ema_label="$1"
  local no_ema="$2"
  local eval_prefix="$3"
  local dfm_eval_prefix="$4"

  echo "[700K ${ema_label}] starting at $(date --iso-8601=seconds)"
  env \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    CKPT_TAGS=step_700000 \
    EVAL_EPOCHS="${EVAL_EPOCH}" \
    CKPT_PATH=checkpoints/dfm4/XL-ddp \
    GPUS=0,1,2,3,4,5,6,7 \
    JUDGE_GPU=0 \
    LITE_EVAL=1 \
    LITE_SHARD_INDEX=0 \
    QUEUE_ORDER=heavy_first \
    MAX_RETRIES=5 \
    NO_EMA="${no_ema}" \
    WANDB_SYNC=1 \
    WANDB_PROJECT="Original Plus Mixed Danish Instruction Rich L" \
    WANDB_RUN_ID=dfm4xlddpclean \
    WANDB_RUN_NAME="dfm4-XL-ddp clean lite history" \
    EVAL_PREFIX="${eval_prefix}" \
    DFM_EVAL_PREFIX="${dfm_eval_prefix}" \
    MODEL_PREFIX="hrm-dfm4-XL-ddp-${ema_label}" \
    STANDARD_BATCH_SIZE=128 \
    DFM_BATCH_SIZE=32 \
    IFEVAL_BATCH_SIZE=32 \
    STANDARD_BATCH_SIZE_MATH=64 \
    STANDARD_BATCH_SIZE_GSM8K=64 \
    STANDARD_BATCH_SIZE_DROP=32 \
    DFM_BATCH_SIZE_GOVREPORT=16 \
    DFM_BATCH_SIZE_NORDJYLLANDNEWS=32 \
    DFM_BATCH_SIZE_WMT24PP_EN_DA=32 \
    DFM_BATCH_SIZE_HUMANEVAL=16 \
    DFM_BATCH_SIZE_GENERATIVE_TALEMAADER=16 \
    LOG_ROOT_BASE="logs/eval/dfm4_XL_ddp_${ema_label}_lite_700k_20260609" \
    DFM_LOG_ROOT_BASE="logs/dfm_evals/dfm4_XL_ddp_${ema_label}_lite_700k_20260609" \
    bash scripts/schedule_multiple_checkpoint_evals.sh
  echo "[700K ${ema_label}] finished at $(date --iso-8601=seconds)"
}

run_lite_eval "noema" 1 "lite_eval_noema" "lite_dfm_eval_noema"
run_lite_eval "ema" 0 "lite_eval_ema" "lite_dfm_eval_ema"

echo "[700K] no-EMA and EMA lite evals finished at $(date --iso-8601=seconds)"
