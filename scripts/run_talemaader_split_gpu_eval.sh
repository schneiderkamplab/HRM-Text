#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CKPT_PATH="${CKPT_PATH:-checkpoints/dfm4/XL-ddp}"
CKPT_TAG="${CKPT_TAG:-step_250000}"
EVAL_EPOCH="${EVAL_EPOCH:-0.6826013116866806}"
LOG_ROOT="${LOG_ROOT:-logs/dfm_evals/talemaader_split_gpu_${CKPT_TAG}}"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
DFM_SINGLE_TASKS_CONFIG="${DFM_SINGLE_TASKS_CONFIG:-${REPO_ROOT}/config/dfm_evals_hrm_single_tasks.yaml}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
MODEL_GPU="${MODEL_GPU:-7}"
JUDGE_GPU="${JUDGE_GPU:-4}"
HOST="${HOST:-127.0.0.1}"
MODEL_PORT="${MODEL_PORT:-9721}"
JUDGE_PORT="${JUDGE_PORT:-9722}"
MODEL_NAME="${MODEL_NAME:-hrm-dfm4-talemaader-${CKPT_TAG}}"
JUDGE_MODEL="${JUDGE_MODEL:-unsloth/gemma-4-E4B-it}"
JUDGE_SERVED_NAME="${JUDGE_SERVED_NAME:-gemma-4-e4b-judge}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
BATCH_SIZE="${BATCH_SIZE:-1}"
BATCH_TIMEOUT_MS="${BATCH_TIMEOUT_MS:-10}"
SHARD_INDEX="${SHARD_INDEX:-0}"
NUM_SHARDS="${NUM_SHARDS:-8}"
NO_EMA="${NO_EMA:-1}"
PREFIX="${PREFIX:-lite_dfm_eval_noema}"
WANDB_SYNC="${WANDB_SYNC:-0}"
WANDB_PROJECT="${WANDB_PROJECT:-Original Plus Mixed Danish Instruction Rich L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-4chqwd3w}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-dfm4-XL-ddp}"
WAIT_FOR_MODEL_GPU_FREE_MB="${WAIT_FOR_MODEL_GPU_FREE_MB:-20000}"
WAIT_FOR_JUDGE_GPU_FREE_MB="${WAIT_FOR_JUDGE_GPU_FREE_MB:-16000}"
EXISTING_JUDGE_BASE_URL="${EXISTING_JUDGE_BASE_URL:-}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

RUN_DIR="${LOG_ROOT}/generative_talemaader/shard_${SHARD_INDEX}_of_${NUM_SHARDS}/${CKPT_TAG}"
INSPECT_DIR="${RUN_DIR}/inspect"
EEE_DIR="${RUN_DIR}/eee"
JUDGE_DIR="${LOG_ROOT}/judge_gpu${JUDGE_GPU}"
MERGED="${LOG_ROOT}/generative_talemaader/merged_metrics.json"
mkdir -p "${INSPECT_DIR}" "${EEE_DIR}" "${JUDGE_DIR}" "$(dirname "${MERGED}")"

log() {
  printf "%s\t%s\n" "$(date --iso-8601=seconds)" "$*" | tee -a "${LOG_ROOT}/status.tsv"
}

wait_for_server() {
  local url="$1" expected_model="${2:-}"
  for _ in $(seq 1 240); do
    if "${PYTHON_BIN}" - "${url}" "${expected_model}" <<'PY'
import json
import sys
import urllib.request

url, expected_model = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
        if expected_model:
            data = json.loads(response.read())
            if data.get("model") != expected_model:
                raise SystemExit(1)
        raise SystemExit(0)
except Exception:
    raise SystemExit(1)
PY
    then
      return 0
    fi
    sleep 2
  done
  return 1
}

gpu_free_mb() {
  nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits \
    | awk -F, -v gpu="$1" '$1 == gpu {gsub(/ /, "", $2); print $2}'
}

while [[ "$(gpu_free_mb "${MODEL_GPU}")" -lt "${WAIT_FOR_MODEL_GPU_FREE_MB}" ]]; do
  log "WAIT_MODEL_GPU_FREE gpu_${MODEL_GPU} free_$(gpu_free_mb "${MODEL_GPU}")MB threshold_${WAIT_FOR_MODEL_GPU_FREE_MB}MB"
  sleep 30
done

if [[ -z "${EXISTING_JUDGE_BASE_URL}" ]]; then
  while [[ "$(gpu_free_mb "${JUDGE_GPU}")" -lt "${WAIT_FOR_JUDGE_GPU_FREE_MB}" ]]; do
    log "WAIT_JUDGE_GPU_FREE gpu_${JUDGE_GPU} free_$(gpu_free_mb "${JUDGE_GPU}")MB threshold_${WAIT_FOR_JUDGE_GPU_FREE_MB}MB"
    sleep 30
  done
fi

judge_pid=""
model_pid=""
cleanup() {
  if [[ -n "${model_pid}" ]] && kill -0 "${model_pid}" 2>/dev/null; then
    kill "${model_pid}" 2>/dev/null || true
    wait "${model_pid}" 2>/dev/null || true
  fi
  if [[ -n "${judge_pid}" ]] && kill -0 "${judge_pid}" 2>/dev/null; then
    kill "${judge_pid}" 2>/dev/null || true
    wait "${judge_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

judge_base_url="http://${HOST}:${JUDGE_PORT}/v1"
if [[ -n "${EXISTING_JUDGE_BASE_URL}" ]]; then
  judge_base_url="${EXISTING_JUDGE_BASE_URL}"
  log "USE_EXISTING_JUDGE ${judge_base_url}"
else
  log "START_JUDGE gpu_${JUDGE_GPU}"
  CUDA_VISIBLE_DEVICES="${JUDGE_GPU}" "${PYTHON_BIN}" scripts/transformers_openai_server.py \
    "${JUDGE_MODEL}" \
    --served-model-name "${JUDGE_SERVED_NAME}" \
    --host "${HOST}" \
    --port "${JUDGE_PORT}" \
    > "${JUDGE_DIR}/server.log" 2>&1 &
  judge_pid="$!"
  wait_for_server "http://${HOST}:${JUDGE_PORT}/health"
fi

server_ema_args=()
if [[ "${NO_EMA}" == "1" ]]; then
  server_ema_args=(--no-ema)
fi

log "START_MODEL gpu_${MODEL_GPU} no_ema_${NO_EMA}"
CUDA_VISIBLE_DEVICES="${MODEL_GPU}" "${PYTHON_BIN}" scripts/hrm_openai_server.py \
  --ckpt-path "${CKPT_PATH}" \
  --ckpt-tag "${CKPT_TAG}" \
  --host "${HOST}" \
  --port "${MODEL_PORT}" \
  --model-name "${MODEL_NAME}" \
  --max-context "${MAX_CONTEXT}" \
  --batch-size "${BATCH_SIZE}" \
  --batch-timeout-ms "${BATCH_TIMEOUT_MS}" \
  --condition direct \
  "${server_ema_args[@]}" \
  > "${RUN_DIR}/server.log" 2>&1 &
model_pid="$!"
wait_for_server "http://${HOST}:${MODEL_PORT}/health" "${MODEL_NAME}"

log "START_EVAL shard_${SHARD_INDEX}_of_${NUM_SHARDS}"
OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}" \
OPENAI_BASE_URL="http://${HOST}:${MODEL_PORT}/v1" \
DFM_EVALS_MODEL_INFO_OVERRIDES="{\"openai/${MODEL_NAME}\":{\"context_length\":${MAX_CONTEXT},\"output_tokens\":512,\"display_name\":\"${MODEL_NAME}\",\"organization\":\"local\"}}" \
uv run --project "${DFM_EVALS_DIR}" evals suite hrm_danish_generative_talemaader \
  --file "${DFM_SINGLE_TASKS_CONFIG}" \
  --target-model "openai/${MODEL_NAME}" \
  --target-base-url "http://${HOST}:${MODEL_PORT}/v1" \
  --judge-model "openai/${JUDGE_SERVED_NAME}" \
  --judge-base-url "${judge_base_url}" \
  --mode set \
  -- \
  -T "num_shards=${NUM_SHARDS}" \
  -T "shard_index=${SHARD_INDEX}" \
  --log-dir "${INSPECT_DIR}" \
  --log-dir-allow-dirty \
  --max-connections "${BATCH_SIZE}" \
  > "${RUN_DIR}/dfm-evals.log" 2>&1

uv run --project "${DFM_EVALS_DIR}" evals eee inspect \
  --log-path "${INSPECT_DIR}" \
  --output-dir "${EEE_DIR}" \
  --source-organization-name "schneiderkamplab" \
  --evaluator-relationship "first_party" \
  --inference-base-url "http://${HOST}:${MODEL_PORT}/v1" \
  --inference-provider-name "hrm-openai-shim" \
  > "${RUN_DIR}/eee-export.log" 2>&1

wandb_args=()
if [[ "${WANDB_SYNC}" == "1" ]]; then
  wandb_args=(--log-wandb --project "${WANDB_PROJECT}" --run-id "${WANDB_RUN_ID}" --run-name "${WANDB_RUN_NAME}")
fi

log "MERGE_SYNC"
"${PYTHON_BIN}" scripts/merge_dfm_eval_shards.py \
  "${INSPECT_DIR}"/*.eval \
  --task generative_talemaader \
  --epoch "${EVAL_EPOCH}" \
  --output "${MERGED}" \
  --prefix "${PREFIX}" \
  "${wandb_args[@]}" \
  > "${LOG_ROOT}/generative_talemaader/merge_and_wandb_sync.log" 2>&1
log "DONE"
