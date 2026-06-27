#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

EPOCH="${EPOCH:-1}"
CKPT_PATH="${CKPT_PATH:-checkpoints/dfm4/XL-ddp}"
CKPT_TAG="${CKPT_TAG:-epoch_${EPOCH}}"
CKPT_TAG="${CKPT_TAG#fsdp2_}"
CKPT_TAG="${CKPT_TAG#unsharded_}"
CKPT_TAG="${CKPT_TAG%.pt}"
EVAL_EPOCH="${EVAL_EPOCH:-${EPOCH}}"
EVAL_STEP="${EVAL_STEP:-}"
GPU="${GPU:-0}"
LOG_ROOT="${EUROEVAL_LOG_ROOT:-${LOG_ROOT:-logs/euroeval/${CKPT_TAG}}}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi
VLLM_PYTHON="${VLLM_PYTHON:-${PYTHON_BIN}}"
if [[ "${VLLM_PYTHON}" != "python" && ! -x "${VLLM_PYTHON}" ]]; then
  VLLM_PYTHON="${PYTHON_BIN}"
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-9700}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-dfm4-XL-ddp}"
MODEL_NAME="${EUROEVAL_MODEL_NAME:-${MODEL_PREFIX}-euroeval-${CKPT_TAG}}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
EUROEVAL_BATCH_SIZE="${EUROEVAL_BATCH_SIZE:-4}"
EUROEVAL_BATCH_TIMEOUT_MS="${EUROEVAL_BATCH_TIMEOUT_MS:-25}"
EUROEVAL_LANGUAGES="${EUROEVAL_LANGUAGES:-da,en}"
EUROEVAL_DATASETS="${EUROEVAL_DATASETS:-}"
EUROEVAL_TASKS="${EUROEVAL_TASKS:-}"
EUROEVAL_FEW_SHOT="${EUROEVAL_FEW_SHOT:-}"
EUROEVAL_NUM_ITERATIONS="${EUROEVAL_NUM_ITERATIONS:-}"
EUROEVAL_GENERATIVE_TYPE="${EUROEVAL_GENERATIVE_TYPE:-}"
EUROEVAL_CACHE_DIR="${EUROEVAL_CACHE_DIR:-}"
EUROEVAL_BIN="${EUROEVAL_BIN:-euroeval}"
EUROEVAL_EXTRA_ARGS="${EUROEVAL_EXTRA_ARGS:-}"
OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}"
NO_EMA="${NO_EMA:-0}"
HRM_SERVER_BACKEND="${HRM_SERVER_BACKEND:-simple}"
HRM_HF_EXPORT_DIR="${HRM_HF_EXPORT_DIR:-}"
HRM_VLLM_NATIVE_PROXY="${HRM_VLLM_NATIVE_PROXY:-0}"
HRM_VLLM_TARGET_PORT="${HRM_VLLM_TARGET_PORT:-$((PORT + 1000))}"
VLLM_DTYPE="${VLLM_DTYPE:-bfloat16}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.85}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
WANDB_SYNC="${WANDB_SYNC:-0}"
WANDB_PROJECT="${WANDB_PROJECT:-}"
WANDB_RUN_ID="${WANDB_RUN_ID:-}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-}"
EUROEVAL_PREFIX="${EUROEVAL_PREFIX:-euroeval}"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'USAGE'
Run EuroEval against an HRM checkpoint through scripts/hrm_openai_server.py
or, when HRM_SERVER_BACKEND=vllm, through an exported HRM-Text vLLM model.

Default scope is Danish and English EuroEval only:
  EUROEVAL_LANGUAGES=da,en

Common overrides:
  CKPT_PATH=checkpoints/dfm4/XL-ddp
  CKPT_TAG=step_700000
  EVAL_EPOCH=1.91
  GPU=0
  EUROEVAL_LOG_ROOT=logs/euroeval/dfm4_XL_ddp/step_700000
  EUROEVAL_DATASETS=dataset-a,dataset-b # optional; default is all matching da/en
  EUROEVAL_TASKS=task-a,task-b          # optional; mutually exclusive with datasets
  EUROEVAL_FEW_SHOT=0                   # optional override; unset uses EuroEval default
  EUROEVAL_NUM_ITERATIONS=1             # optional override; unset uses EuroEval default
  EUROEVAL_GENERATIVE_TYPE=instruction_tuned # optional override; unset uses EuroEval default
  EUROEVAL_BIN='uv run --no-project --with euroeval euroeval'
  HRM_SERVER_BACKEND=vllm HRM_HF_EXPORT_DIR=exports/original_sapient_L_epoch4_ema_hf
  HRM_VLLM_NATIVE_PROXY=1 # optional: strip structured-output extras for native parity
  WANDB_SYNC=1 WANDB_PROJECT=... WANDB_RUN_ID=...
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ -n "${EUROEVAL_DATASETS}" && -n "${EUROEVAL_TASKS}" ]]; then
  echo "EUROEVAL_DATASETS and EUROEVAL_TASKS are mutually exclusive." >&2
  exit 2
fi
if [[ "${HRM_SERVER_BACKEND}" != "simple" && "${HRM_SERVER_BACKEND}" != "vllm" ]]; then
  echo "Unsupported HRM_SERVER_BACKEND=${HRM_SERVER_BACKEND}; expected simple or vllm." >&2
  exit 2
fi
if [[ "${HRM_SERVER_BACKEND}" == "vllm" && -z "${HRM_HF_EXPORT_DIR}" ]]; then
  echo "HRM_HF_EXPORT_DIR is required when HRM_SERVER_BACKEND=vllm." >&2
  exit 2
fi

mkdir -p "${LOG_ROOT}"
LOG_ROOT="$(cd "${LOG_ROOT}" && pwd)"
EUROEVAL_CACHE_DIR="${EUROEVAL_CACHE_DIR:-${LOG_ROOT}/cache}"
BASE_URL="http://${HOST}:${PORT}/v1"
RESULTS_FILE="${LOG_ROOT}/euroeval_benchmark_results.jsonl"
METRICS_FILE="${LOG_ROOT}/merged_metrics.json"
SERVER_LOG="${LOG_ROOT}/server.log"
EUROEVAL_LOG="${LOG_ROOT}/euroeval.log"

server_ema_args=()
if [[ "${NO_EMA}" == "1" ]]; then
  server_ema_args=(--no-ema)
fi

wait_for_server() {
  local url="$1"
  for _ in $(seq 1 240); do
    if "${PYTHON_BIN}" - "$url" "${MODEL_NAME}" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
        data = json.loads(response.read())
        if data.get("model") != sys.argv[2]:
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

wait_for_vllm_server() {
  local url="$1"
  for _ in $(seq 1 240); do
    if "${PYTHON_BIN}" - "$url" "${MODEL_NAME}" <<'PY'
import json
import sys
import urllib.request

base_url, expected = sys.argv[1].rstrip("/"), sys.argv[2]
try:
    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
    with urllib.request.urlopen(f"{base_url}/v1/models", timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
        data = json.loads(response.read())
    model_ids = {item.get("id") for item in data.get("data", [])}
    if expected not in model_ids:
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

run_euroeval_with_server_monitor() {
  (
    cd "${LOG_ROOT}"
    # shellcheck disable=SC2086
    ${EUROEVAL_BIN} "${euroeval_args[@]}"
  ) > "${EUROEVAL_LOG}" 2>&1 &
  local client_pid="$!"
  local status=0

  while kill -0 "${client_pid}" 2>/dev/null; do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
      echo "Server process ${server_pid} exited while EuroEval client ${client_pid} was still running." >> "${EUROEVAL_LOG}"
      kill "${client_pid}" 2>/dev/null || true
      wait "${client_pid}" 2>/dev/null || true
      return 71
    fi
    if [[ -f "${SERVER_LOG}" ]] && grep -Eiq "OutOfMemoryError|CUDA out of memory|out of memory" "${SERVER_LOG}"; then
      echo "Server process ${server_pid} logged an OOM; terminating EuroEval client ${client_pid} for scheduler retry." >> "${EUROEVAL_LOG}"
      kill "${server_pid}" 2>/dev/null || true
      kill "${client_pid}" 2>/dev/null || true
      wait "${client_pid}" 2>/dev/null || true
      return 72
    fi
    sleep "${SERVER_MONITOR_INTERVAL_SECONDS:-5}"
  done

  set +e
  wait "${client_pid}"
  status=$?
  set -e

  if [[ -f "${SERVER_LOG}" ]] && grep -Eiq "OutOfMemoryError|CUDA out of memory|out of memory" "${SERVER_LOG}"; then
    echo "Server process ${server_pid} logged an OOM after EuroEval client exit; treating job as failed for scheduler retry." >> "${EUROEVAL_LOG}"
    return 72
  fi
  return "${status}"
}

split_csv_args() {
  local option="$1" csv="$2" item
  [[ -z "${csv}" ]] && return 0
  IFS=',' read -r -a values <<< "${csv}"
  for item in "${values[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    [[ -n "${item}" ]] && printf '%s\0%s\0' "${option}" "${item}"
  done
}

euroeval_args=(
  --model "${MODEL_NAME}"
  --api-base "${BASE_URL}"
  --api-key "${OPENAI_API_KEY}"
  --cache-dir "${EUROEVAL_CACHE_DIR}"
  --max-context-length "${MAX_CONTEXT}"
  --force
  --no-progress-bar
  --save-results
)

if [[ -n "${EUROEVAL_GENERATIVE_TYPE}" ]]; then
  euroeval_args+=(--generative-type "${EUROEVAL_GENERATIVE_TYPE}")
fi
if [[ -n "${EUROEVAL_NUM_ITERATIONS}" ]]; then
  euroeval_args+=(--num-iterations "${EUROEVAL_NUM_ITERATIONS}")
fi
if [[ "${EUROEVAL_FEW_SHOT}" == "1" ]]; then
  euroeval_args+=(--few-shot)
elif [[ "${EUROEVAL_FEW_SHOT}" == "0" ]]; then
  euroeval_args+=(--zero-shot)
fi

while IFS= read -r -d '' arg; do euroeval_args+=("${arg}"); done < <(split_csv_args --language "${EUROEVAL_LANGUAGES}")
while IFS= read -r -d '' arg; do euroeval_args+=("${arg}"); done < <(split_csv_args --dataset "${EUROEVAL_DATASETS}")
while IFS= read -r -d '' arg; do euroeval_args+=("${arg}"); done < <(split_csv_args --task "${EUROEVAL_TASKS}")

if [[ -n "${EUROEVAL_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  extra_args=( ${EUROEVAL_EXTRA_ARGS} )
  euroeval_args+=("${extra_args[@]}")
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  if [[ "${HRM_SERVER_BACKEND}" == "vllm" ]]; then
    printf 'CUDA_VISIBLE_DEVICES=%q HRM_HF_EXPORT_DIR=%q scripts/hrm_vllm_openai_server.sh ...\n' "${GPU}" "${HRM_HF_EXPORT_DIR}"
    if [[ "${HRM_VLLM_NATIVE_PROXY}" == "1" ]]; then
      printf '%q scripts/native_compatible_openai_proxy.py --target-base-url %q ...\n' "${PYTHON_BIN}" "http://${HOST}:${HRM_VLLM_TARGET_PORT}/v1"
    fi
  else
    printf 'CUDA_VISIBLE_DEVICES=%q %q scripts/hrm_openai_server.py ...\n' "${GPU}" "${PYTHON_BIN}"
  fi
  printf '(cd %q && %s ' "${LOG_ROOT}" "${EUROEVAL_BIN}"
  printf '%q ' "${euroeval_args[@]}"
  printf ')\n'
  exit 0
fi

server_pid=""
vllm_pid=""
cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  if [[ -n "${vllm_pid}" ]] && kill -0 "${vllm_pid}" 2>/dev/null; then
    kill "${vllm_pid}" 2>/dev/null || true
    wait "${vllm_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${HRM_SERVER_BACKEND}" == "vllm" ]]; then
  vllm_port="${PORT}"
  vllm_log="${SERVER_LOG}"
  if [[ "${HRM_VLLM_NATIVE_PROXY}" == "1" ]]; then
    vllm_port="${HRM_VLLM_TARGET_PORT}"
    vllm_log="${LOG_ROOT}/vllm.log"
  fi
  CUDA_VISIBLE_DEVICES="${GPU}" \
  PYTHON_BIN="${VLLM_PYTHON}" \
  VLLM_DTYPE="${VLLM_DTYPE}" \
  VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION}" \
  VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS}" \
  scripts/hrm_vllm_openai_server.sh \
    --model "${HRM_HF_EXPORT_DIR}" \
    --served-model-name "${MODEL_NAME}" \
    --host "${HOST}" \
    --port "${vllm_port}" \
    --max-model-len "${MAX_CONTEXT}" \
    > "${vllm_log}" 2>&1 &
  vllm_pid="$!"
  if [[ "${HRM_VLLM_NATIVE_PROXY}" == "1" ]]; then
    wait_for_vllm_server "http://${HOST}:${vllm_port}"
    proxy_args=()
    if [[ "${HRM_VLLM_GEMMA_BFCL_TOOLS:-0}" == "1" ]]; then
      if [[ "${HRM_VLLM_GEMMA_BFCL_TOOL_MODE:-parser}" == "text" ]]; then
        proxy_args+=(--gemma-native-bfcl-tools-as-text)
      else
        proxy_args+=(--gemma-native-bfcl-tools)
      fi
    fi
    "${PYTHON_BIN}" scripts/native_compatible_openai_proxy.py \
      --host "${HOST}" \
      --port "${PORT}" \
      --target-base-url "http://${HOST}:${vllm_port}/v1" \
      --model-name "${MODEL_NAME}" \
      --target-model-name "${MODEL_NAME}" \
      --api-key "${OPENAI_API_KEY}" \
      --log-jsonl "${LOG_ROOT}/proxy_payloads.jsonl" \
      "${proxy_args[@]}" \
      > "${SERVER_LOG}" 2>&1 &
  fi
else
  CUDA_VISIBLE_DEVICES="${GPU}" "${PYTHON_BIN}" scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-tag "${CKPT_TAG}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --model-name "${MODEL_NAME}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${EUROEVAL_BATCH_SIZE}" \
    --batch-timeout-ms "${EUROEVAL_BATCH_TIMEOUT_MS}" \
    --condition direct \
    "${server_ema_args[@]}" \
    > "${SERVER_LOG}" 2>&1 &
fi
server_pid="$!"
if [[ "${HRM_SERVER_BACKEND}" == "vllm" && "${HRM_VLLM_NATIVE_PROXY}" != "1" ]]; then
  wait_for_vllm_server "http://${HOST}:${PORT}"
else
  wait_for_server "http://${HOST}:${PORT}/health"
fi

rm -f "${RESULTS_FILE}" "${METRICS_FILE}"
run_euroeval_with_server_monitor

if [[ ! -s "${RESULTS_FILE}" ]]; then
  echo "Missing EuroEval results file: ${RESULTS_FILE}" >&2
  exit 3
fi

wandb_args=()
if [[ "${WANDB_SYNC}" == "1" ]]; then
  wandb_args=(--log-wandb --project "${WANDB_PROJECT}" --run-id "${WANDB_RUN_ID}" --run-name "${WANDB_RUN_NAME}")
fi
step_args=()
if [[ -n "${EVAL_STEP}" ]]; then
  step_args=(--step "${EVAL_STEP}")
fi

"${PYTHON_BIN}" scripts/log_euroeval_to_wandb.py \
  --results "${RESULTS_FILE}" \
  --epoch "${EVAL_EPOCH}" \
  "${step_args[@]}" \
  --output "${METRICS_FILE}" \
  --prefix "${EUROEVAL_PREFIX}" \
  --language da \
  --language en \
  "${wandb_args[@]}" \
  > "${LOG_ROOT}/merge_and_wandb_sync.log" 2>&1
