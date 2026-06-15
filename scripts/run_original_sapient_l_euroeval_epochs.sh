#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CKPT_PATH="${CKPT_PATH:-checkpoints/original_sapient/L}"
LOG_ROOT="${LOG_ROOT:-logs/euroeval/original_sapient_L}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-original-sapient-L}"
WANDB_PROJECT="${WANDB_PROJECT:-Original Plus Mixed Danish Instruction Rich L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-origLclean}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-original-sapient-L-clean-history}"
EUROEVAL_BIN="${EUROEVAL_BIN:-${REPO_ROOT}/scripts/euroeval_api_no_flash_attn_guard.py}"
EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES:-da,en}"
EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE:-4}"
EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS:-25}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
HOST="${HOST:-127.0.0.1}"
BASE_PORT="${BASE_PORT:-9740}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"

epochs=(1 2 3 4)
gpus=(4 5 6 7)

mkdir -p "${LOG_ROOT}/launcher"

pids=()
for index in "${!epochs[@]}"; do
  epoch="${epochs[$index]}"
  gpu="${gpus[$index]}"
  port=$((BASE_PORT + index + 1))
  run_dir="${LOG_ROOT}/epoch_${epoch}"
  mkdir -p "${run_dir}"

  (
    CKPT_PATH="${CKPT_PATH}" \
    CKPT_TAG="epoch_${epoch}" \
    EVAL_EPOCH="${epoch}" \
    GPU="${gpu}" \
    PORT="${port}" \
    HOST="${HOST}" \
    MODEL_PREFIX="${MODEL_PREFIX}" \
    MAX_CONTEXT="${MAX_CONTEXT}" \
    EUROEVAL_LOG_ROOT="${run_dir}" \
    EUROEVAL_BIN="${EUROEVAL_BIN}" \
    EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES}" \
    EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE}" \
    EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS}" \
    WANDB_SYNC=1 \
    WANDB_PROJECT="${WANDB_PROJECT}" \
    WANDB_RUN_ID="${WANDB_RUN_ID}" \
    WANDB_RUN_NAME="${WANDB_RUN_NAME}" \
    PYTHON_BIN="${PYTHON_BIN}" \
    scripts/run_euroeval_on_checkpoint.sh
  ) > "${LOG_ROOT}/launcher/epoch_${epoch}_gpu_${gpu}.log" 2>&1 &
  pids+=("$!")
  printf "%s\tSTART epoch_%s gpu_%s port_%s pid_%s\n" "$(date --iso-8601=seconds)" "${epoch}" "${gpu}" "${port}" "${pids[-1]}" | tee -a "${LOG_ROOT}/launcher/status.log"
  sleep 5
done

status=0
for index in "${!pids[@]}"; do
  epoch="${epochs[$index]}"
  gpu="${gpus[$index]}"
  pid="${pids[$index]}"
  if wait "${pid}"; then
    printf "%s\tEND epoch_%s gpu_%s status_0\n" "$(date --iso-8601=seconds)" "${epoch}" "${gpu}" | tee -a "${LOG_ROOT}/launcher/status.log"
  else
    child_status="$?"
    printf "%s\tEND epoch_%s gpu_%s status_%s\n" "$(date --iso-8601=seconds)" "${epoch}" "${gpu}" "${child_status}" | tee -a "${LOG_ROOT}/launcher/status.log"
    status=1
  fi
done

exit "${status}"
