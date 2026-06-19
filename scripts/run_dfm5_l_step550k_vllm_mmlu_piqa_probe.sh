#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

CKPT_PATH="${CKPT_PATH:-checkpoints/dfm5/L}"
CKPT_TAG="${CKPT_TAG:-step_550000}"
EVAL_EPOCH="${EVAL_EPOCH:-3.0369730800405055}"
EXPORT_DIR="${EXPORT_DIR:-exports/dfm5_L_step550000_ema_hf}"

RUN_TAG="${RUN_TAG:-dfm5_L_step550000_vllm_mmlu_piqa_20260618}"
LOG_ROOT="${LOG_ROOT:-logs/eval/${RUN_TAG}}"
DFM_LOG_ROOT="${DFM_LOG_ROOT:-logs/dfm_evals/${RUN_TAG}}"
EUROEVAL_LOG_ROOT="${EUROEVAL_LOG_ROOT:-logs/euroeval/${RUN_TAG}}"
JOB_FILE="${JOB_FILE:-${LOG_ROOT}/jobs.tsv}"
STATUS_FILE="${STATUS_FILE:-${LOG_ROOT}/status.tsv}"

GPUS="${GPUS:-6}"
EXPORT_GPU="${EXPORT_GPU:-${GPUS%%,*}}"
MIN_FREE_MIB="${MIN_FREE_MIB:-50000}"
WAIT_GPU_SECONDS="${WAIT_GPU_SECONDS:-120}"

WANDB_PROJECT="${WANDB_PROJECT:-DFM5}"
WANDB_RUN_ID="${WANDB_RUN_ID:-dfm5-l-step550k-vllm-probe-20260618}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-dfm5-L step550k vLLM MMLU+PIQA probe}"
WANDB_SYNC="${WANDB_SYNC:-1}"

STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE:-8}"
DFM_BATCH_SIZE="${DFM_BATCH_SIZE:-16}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.25}"
VLLM_DTYPE="${VLLM_DTYPE:-bfloat16}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---enforce-eager}"
STANDARD_VLLM_GPU_MEMORY_UTILIZATION="${STANDARD_VLLM_GPU_MEMORY_UTILIZATION:-${VLLM_GPU_MEMORY_UTILIZATION}}"
STANDARD_VLLM_DTYPE="${STANDARD_VLLM_DTYPE:-${VLLM_DTYPE}}"
STANDARD_VLLM_MAX_MODEL_LEN="${STANDARD_VLLM_MAX_MODEL_LEN:-4096}"

gpu_free_mib() {
  nvidia-smi -i "$1" --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' '
}

wait_for_gpu_memory() {
  local gpu="$1" free_mib
  while true; do
    free_mib="$(gpu_free_mib "${gpu}" || echo 0)"
    if [[ "${free_mib}" =~ ^[0-9]+$ ]] && (( free_mib >= MIN_FREE_MIB )); then
      echo "[probe] gpu ${gpu} free ${free_mib} MiB >= ${MIN_FREE_MIB} MiB"
      return 0
    fi
    echo "[probe] waiting for gpu ${gpu}: free ${free_mib} MiB < ${MIN_FREE_MIB} MiB"
    sleep "${WAIT_GPU_SECONDS}"
  done
}

wait_for_gpu_memory "${EXPORT_GPU}"

if [[ ! -s "${EXPORT_DIR}/model.safetensors" ]]; then
  echo "[probe] exporting ${CKPT_PATH} ${CKPT_TAG} EMA to ${EXPORT_DIR}"
  CUDA_VISIBLE_DEVICES="${EXPORT_GPU}" "${PYTHON_BIN}" conversion/convert_to_hf.py \
    --ckpt_path "${CKPT_PATH}" \
    --ckpt_tag "${CKPT_TAG}" \
    --ckpt_use_ema true \
    --out_dir "${EXPORT_DIR}"
else
  echo "[probe] using existing export ${EXPORT_DIR}"
fi

mkdir -p "${LOG_ROOT}" "${DFM_LOG_ROOT}" "${EUROEVAL_LOG_ROOT}"
cat > "${JOB_FILE}" <<'JOBS'
standard	MMLU	0	4
standard	MMLU	1	4
standard	MMLU	2	4
standard	MMLU	3	4
dfm	piqa	0	1
JOBS
: > "${STATUS_FILE}"

echo "[probe] job file: ${JOB_FILE}"
cat "${JOB_FILE}"

GPUS="${GPUS}" \
CKPT_PATH="${CKPT_PATH}" \
CKPT_TAG="${CKPT_TAG}" \
EVAL_EPOCH="${EVAL_EPOCH}" \
LOG_ROOT="${LOG_ROOT}" \
DFM_LOG_ROOT="${DFM_LOG_ROOT}" \
EUROEVAL_LOG_ROOT="${EUROEVAL_LOG_ROOT}" \
JOB_FILE_OVERRIDE="${JOB_FILE}" \
STATUS_FILE_OVERRIDE="${STATUS_FILE}" \
RESUME_EXISTING_QUEUE=1 \
SKIP_FINAL_MERGE=1 \
RUN_EUROEVAL=0 \
MAX_RETRIES=2 \
STARTUP_STAGGER_SECONDS=0 \
STANDARD_BATCH_SIZE="${STANDARD_BATCH_SIZE}" \
DFM_BATCH_SIZE="${DFM_BATCH_SIZE}" \
STANDARD_ENGINE_BACKEND=vllm \
STANDARD_HF_EXPORT_DIR="${EXPORT_DIR}" \
STANDARD_VLLM_CONFIG=evaluation/config/hrm_vllm_benchmarking.yaml \
STANDARD_VLLM_DTYPE="${STANDARD_VLLM_DTYPE}" \
STANDARD_VLLM_GPU_MEMORY_UTILIZATION="${STANDARD_VLLM_GPU_MEMORY_UTILIZATION}" \
STANDARD_VLLM_MAX_MODEL_LEN="${STANDARD_VLLM_MAX_MODEL_LEN}" \
HRM_SERVER_BACKEND=vllm \
HRM_HF_EXPORT_DIR="${EXPORT_DIR}" \
VLLM_DTYPE="${VLLM_DTYPE}" \
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION}" \
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS}" \
WANDB_PROJECT="${WANDB_PROJECT}" \
WANDB_RUN_ID="${WANDB_RUN_ID}" \
WANDB_RUN_NAME="${WANDB_RUN_NAME}" \
WANDB_SYNC="${WANDB_SYNC}" \
MODEL_PREFIX=hrm-dfm5-L-step550k-vllm-probe \
EVAL_PREFIX=vllm_eval \
DFM_EVAL_PREFIX=vllm_dfm_eval \
PYTHON_BIN="${PYTHON_BIN}" \
scripts/schedule_checkpoint_evals.sh
