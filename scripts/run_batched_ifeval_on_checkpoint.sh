#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

GPU="${GPU:-0}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-26000}"
VLLM_PORT="${VLLM_PORT:-$((PORT + 1000))}"
MODEL_NAME="${EUROEVAL_MODEL_NAME:-${MODEL_PREFIX:-hrm}-euroeval-${CKPT_TAG:-checkpoint}}"
TASK="${EUROEVAL_DATASETS:-${EUROEVAL_TASK:-ifeval}}"
LOG_ROOT="${EUROEVAL_LOG_ROOT:-logs/euroeval/${CKPT_TAG:-checkpoint}/${TASK}}"
HRM_HF_EXPORT_DIR="${HRM_HF_EXPORT_DIR:?HRM_HF_EXPORT_DIR is required}"
CONCURRENCY="${EUROEVAL_BATCH_SIZE:-32}"
MAX_TOKENS="${EUROEVAL_MAX_TOKENS:-2048}"
EVAL_EPOCH="${EVAL_EPOCH:-}"
EVAL_STEP="${EVAL_STEP:-}"
VLLM_DTYPE="${VLLM_DTYPE:-bfloat16}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.22}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}"
WANDB_SYNC="${WANDB_SYNC:-0}"
WANDB_PROJECT="${WANDB_PROJECT:-}"
WANDB_RUN_ID="${WANDB_RUN_ID:-}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-}"
EUROEVAL_PREFIX="${EUROEVAL_PREFIX:-euroeval}"

mkdir -p "${LOG_ROOT}"
LOG_ROOT="$(cd "${LOG_ROOT}" && pwd)"

wait_for_vllm() {
  local base_url="$1"
  local expected="$2"
  for _ in $(seq 1 240); do
    if "${PYTHON_BIN}" - "$base_url" "$expected" <<'PY'
import json
import sys
import urllib.request

base_url, expected = sys.argv[1].rstrip("/"), sys.argv[2]
try:
    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
    with urllib.request.urlopen(f"{base_url}/v1/models", timeout=2) as response:
        data = json.loads(response.read())
    if expected not in {item.get("id") for item in data.get("data", [])}:
        raise SystemExit(1)
except Exception:
    raise SystemExit(1)
raise SystemExit(0)
PY
    then
      return 0
    fi
    sleep 2
  done
  return 1
}

wait_for_proxy() {
  local url="$1"
  for _ in $(seq 1 120); do
    if "${PYTHON_BIN}" - "$url" <<'PY'
import sys
import urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        raise SystemExit(0 if response.status == 200 else 1)
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

vllm_pid=""
proxy_pid=""
cleanup() {
  for pid in "${proxy_pid}" "${vllm_pid}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

CUDA_VISIBLE_DEVICES="${GPU}" \
PYTHON_BIN="${PYTHON_BIN}" \
VLLM_DTYPE="${VLLM_DTYPE}" \
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION}" \
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS}" \
scripts/hrm_vllm_openai_server.sh \
  --model "${HRM_HF_EXPORT_DIR}" \
  --served-model-name "${MODEL_NAME}" \
  --host "${HOST}" \
  --port "${VLLM_PORT}" \
  --max-model-len 4096 \
  > "${LOG_ROOT}/vllm.log" 2>&1 &
vllm_pid="$!"
wait_for_vllm "http://${HOST}:${VLLM_PORT}" "${MODEL_NAME}"

"${PYTHON_BIN}" scripts/native_compatible_openai_proxy.py \
  --host "${HOST}" \
  --port "${PORT}" \
  --target-base-url "http://${HOST}:${VLLM_PORT}/v1" \
  --model-name "${MODEL_NAME}" \
  --target-model-name "${MODEL_NAME}" \
  --api-key "${OPENAI_API_KEY}" \
  --log-jsonl "${LOG_ROOT}/proxy_payloads.jsonl" \
  > "${LOG_ROOT}/server.log" 2>&1 &
proxy_pid="$!"
wait_for_proxy "http://${HOST}:${PORT}/health"

epoch_args=()
if [[ -n "${EVAL_EPOCH}" ]]; then
  epoch_args=(--epoch "${EVAL_EPOCH}")
fi

"${PYTHON_BIN}" scripts/run_ifeval_batched_openai.py \
  --dataset "${TASK}" \
  --api-base "http://${HOST}:${PORT}/v1" \
  --api-key "${OPENAI_API_KEY}" \
  --model "${MODEL_NAME}" \
  --output-dir "${LOG_ROOT}" \
  --concurrency "${CONCURRENCY}" \
  --max-tokens "${MAX_TOKENS}" \
  --resume \
  "${epoch_args[@]}" \
  > "${LOG_ROOT}/batched_ifeval.log" 2>&1

wandb_args=()
if [[ "${WANDB_SYNC}" == "1" ]]; then
  wandb_args=(--log-wandb --project "${WANDB_PROJECT}" --run-id "${WANDB_RUN_ID}" --run-name "${WANDB_RUN_NAME}")
fi

if [[ -n "${EVAL_EPOCH}" ]]; then
  step_args=()
  if [[ -n "${EVAL_STEP}" ]]; then
    step_args=(--step "${EVAL_STEP}")
  fi
  "${PYTHON_BIN}" scripts/log_euroeval_to_wandb.py \
    --results "${LOG_ROOT}/euroeval_benchmark_results.jsonl" \
    --epoch "${EVAL_EPOCH}" \
    "${step_args[@]}" \
    --output "${LOG_ROOT}/wandb_metrics.json" \
    --prefix "${EUROEVAL_PREFIX}" \
    "${wandb_args[@]}" \
    > "${LOG_ROOT}/merge_and_wandb_sync.log" 2>&1
fi
