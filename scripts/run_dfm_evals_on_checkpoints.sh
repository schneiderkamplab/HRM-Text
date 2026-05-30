#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DFM_EVALS_DIR="${DFM_EVALS_DIR:-${REPO_ROOT}/dfm-evals}"
CKPT_PATH="${CKPT_PATH:-${REPO_ROOT}/checkpoints/original_sapient/L}"
EPOCHS="${EPOCHS:-1 2 3 4}"
GPU="${GPU:-0}"
HOST="${HOST:-127.0.0.1}"
PORT_BASE="${PORT_BASE:-8091}"
MODEL_PREFIX="${MODEL_PREFIX:-hrm-original-sapient-L}"
SUITE_FILE="${SUITE_FILE:-${REPO_ROOT}/config/dfm_evals_hrm.yaml}"
SUITE="${SUITE:-hrm_danish}"
LOG_ROOT="${LOG_ROOT:-${REPO_ROOT}/logs/dfm_evals/original_sapient_L}"
MAX_CONTEXT="${MAX_CONTEXT:-4096}"
BATCH_SIZE="${BATCH_SIZE:-8}"
BATCH_TIMEOUT_MS="${BATCH_TIMEOUT_MS:-25}"
INSPECT_MAX_CONNECTIONS="${INSPECT_MAX_CONNECTIONS:-${BATCH_SIZE}}"
CONDITION="${CONDITION:-direct}"
WANDB_PROJECT="${WANDB_PROJECT:-Original Plus Mixed Danish Instruction Rich L}"
WANDB_RUN_ID="${WANDB_RUN_ID:-origLclean}"
WANDB_RUN_NAME="${WANDB_RUN_NAME:-original-sapient-L-clean-history}"
WANDB_PREFIX="${WANDB_PREFIX:-dfm_eval}"
INCREMENTAL_WANDB_SYNC="${INCREMENTAL_WANDB_SYNC:-1}"
SYNC_INTERVAL_SECONDS="${SYNC_INTERVAL_SECONDS:-30}"
FINAL_WANDB_SYNC="${FINAL_WANDB_SYNC:-0}"
JUDGE_MODEL="${JUDGE_MODEL:-}"
JUDGE_BASE_URL="${JUDGE_BASE_URL:-}"
INSTALL="${INSTALL:-0}"

usage() {
  cat <<'USAGE'
Run dfm-evals against HRM checkpoints through the local OpenAI-compatible shim.

Environment overrides:
  DFM_EVALS_DIR     default: dfm-evals
  CKPT_PATH         default: checkpoints/original_sapient/L
  EPOCHS            default: "1 2 3 4"
  GPU               default: 0
  PORT_BASE         default: 8091
  SUITE_FILE        default: config/dfm_evals_hrm.yaml
  SUITE             default: hrm_danish
  LOG_ROOT          default: logs/dfm_evals/original_sapient_L
  MAX_CONTEXT       default: 4096
  BATCH_SIZE        default: 8
  BATCH_TIMEOUT_MS  default: 25
  INSPECT_MAX_CONNECTIONS default: BATCH_SIZE
  WANDB_PROJECT     default: Original Plus Mixed Danish Instruction Rich L
  WANDB_RUN_ID      default: origLclean
  WANDB_PREFIX      default: dfm_eval
  INCREMENTAL_WANDB_SYNC default: 1; sync each completed Inspect .eval to W&B
  SYNC_INTERVAL_SECONDS default: 30
  FINAL_WANDB_SYNC  default: 0; set 1 to log all epoch metrics again at the end
  JUDGE_MODEL       optional; required by judge-scored tasks such as generative-talemaader
  JUDGE_BASE_URL    optional; base URL for judge model when needed
  INSTALL=1         run `uv sync --project dfm-evals` first

Extra arguments after -- are forwarded to `evals suite`.

Examples:
  scripts/run_dfm_evals_on_checkpoints.sh
  EPOCHS="4" scripts/run_dfm_evals_on_checkpoints.sh -- --limit 25
  INSTALL=1 EPOCHS="1" scripts/run_dfm_evals_on_checkpoints.sh -- --limit 10
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

EXTRA_ARGS=()
if [[ "${1:-}" == "--" ]]; then
  shift
  EXTRA_ARGS=("$@")
elif [[ $# -gt 0 ]]; then
  EXTRA_ARGS=("$@")
fi

cd "${REPO_ROOT}"

if [[ ! -d "${DFM_EVALS_DIR}" ]]; then
  git clone https://github.com/danish-foundation-models/dfm-evals "${DFM_EVALS_DIR}"
fi

if [[ "${INSTALL}" == "1" ]]; then
  uv sync --project "${DFM_EVALS_DIR}"
fi

mkdir -p "${LOG_ROOT}"

SUITE_ROUTING_ARGS=()
if [[ -n "${JUDGE_MODEL}" ]]; then
  SUITE_ROUTING_ARGS+=(--judge-model "${JUDGE_MODEL}")
fi
if [[ -n "${JUDGE_BASE_URL}" ]]; then
  SUITE_ROUTING_ARGS+=(--judge-base-url "${JUDGE_BASE_URL}")
fi

cleanup_pid=""
sync_pid=""
cleanup() {
  if [[ -n "${sync_pid}" ]] && kill -0 "${sync_pid}" 2>/dev/null; then
    kill "${sync_pid}" 2>/dev/null || true
    wait "${sync_pid}" 2>/dev/null || true
  fi
  sync_pid=""

  if [[ -n "${cleanup_pid}" ]] && kill -0 "${cleanup_pid}" 2>/dev/null; then
    kill "${cleanup_pid}" 2>/dev/null || true
    wait "${cleanup_pid}" 2>/dev/null || true
  fi
  cleanup_pid=""
}
trap cleanup EXIT

wait_for_server() {
  local url="$1"
  for _ in $(seq 1 240); do
    if python - "$url" <<'PY'
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

for epoch in ${EPOCHS}; do
  port=$((PORT_BASE + epoch))
  model_name="${MODEL_PREFIX}-epoch-${epoch}"
  base_url="http://${HOST}:${port}/v1"
  run_dir="${LOG_ROOT}/epoch_${epoch}"
  inspect_log_dir="${run_dir}/inspect"
  eee_dir="${run_dir}/eee"
  incremental_sync_dir="${run_dir}/incremental_wandb_sync"
  server_log="${run_dir}/server.log"

  mkdir -p "${inspect_log_dir}" "${eee_dir}" "${incremental_sync_dir}"

  echo "Starting HRM OpenAI shim for epoch ${epoch} on ${HOST}:${port}" | tee "${run_dir}/run.log"
  CUDA_VISIBLE_DEVICES="${GPU}" python scripts/hrm_openai_server.py \
    --ckpt-path "${CKPT_PATH}" \
    --ckpt-epoch "${epoch}" \
    --host "${HOST}" \
    --port "${port}" \
    --model-name "${model_name}" \
    --max-context "${MAX_CONTEXT}" \
    --batch-size "${BATCH_SIZE}" \
    --batch-timeout-ms "${BATCH_TIMEOUT_MS}" \
    --condition "${CONDITION}" \
    > "${server_log}" 2>&1 &
  cleanup_pid="$!"

  wait_for_server "http://${HOST}:${port}/health"

  if [[ "${INCREMENTAL_WANDB_SYNC}" == "1" ]]; then
    echo "Starting incremental dfm-evals W&B sync monitor for epoch ${epoch}" | tee -a "${run_dir}/run.log"
    python scripts/sync_completed_dfm_evals.py \
      --inspect-dir "${inspect_log_dir}" \
      --sync-root "${incremental_sync_dir}" \
      --dfm-evals-dir "${DFM_EVALS_DIR}" \
      --epoch "${epoch}" \
      --project "${WANDB_PROJECT}" \
      --run-id "${WANDB_RUN_ID}" \
      --run-name "${WANDB_RUN_NAME}" \
      --prefix "${WANDB_PREFIX}" \
      --base-url "${base_url}" \
      --interval-seconds "${SYNC_INTERVAL_SECONDS}" \
      > "${run_dir}/incremental-wandb-sync.log" 2>&1 &
    sync_pid="$!"
  fi

  echo "Running dfm-evals suite ${SUITE} for ${model_name}" | tee -a "${run_dir}/run.log"
  OPENAI_API_KEY="${OPENAI_API_KEY:-inspectai}" \
  OPENAI_BASE_URL="${base_url}" \
  DFM_EVALS_MODEL_INFO_OVERRIDES="{\"openai/${model_name}\":{\"context_length\":${MAX_CONTEXT},\"output_tokens\":512,\"display_name\":\"${model_name}\",\"organization\":\"local\"}}" \
  uv run --project "${DFM_EVALS_DIR}" evals suite "${SUITE}" \
    --file "${SUITE_FILE}" \
    --target-model "openai/${model_name}" \
    --target-base-url "${base_url}" \
    "${SUITE_ROUTING_ARGS[@]}" \
    --mode set \
    -- \
    --log-dir "${inspect_log_dir}" \
    --log-dir-allow-dirty \
    --max-connections "${INSPECT_MAX_CONNECTIONS}" \
    "${EXTRA_ARGS[@]}" \
    2>&1 | tee -a "${run_dir}/dfm-evals.log"

  if [[ -n "${sync_pid}" ]] && kill -0 "${sync_pid}" 2>/dev/null; then
    kill "${sync_pid}" 2>/dev/null || true
    wait "${sync_pid}" 2>/dev/null || true
    sync_pid=""
  fi

  if [[ "${INCREMENTAL_WANDB_SYNC}" == "1" ]]; then
    echo "Running final incremental dfm-evals W&B sync pass for epoch ${epoch}" | tee -a "${run_dir}/run.log"
    python scripts/sync_completed_dfm_evals.py \
      --inspect-dir "${inspect_log_dir}" \
      --sync-root "${incremental_sync_dir}" \
      --dfm-evals-dir "${DFM_EVALS_DIR}" \
      --epoch "${epoch}" \
      --project "${WANDB_PROJECT}" \
      --run-id "${WANDB_RUN_ID}" \
      --run-name "${WANDB_RUN_NAME}" \
      --prefix "${WANDB_PREFIX}" \
      --base-url "${base_url}" \
      --once \
      2>&1 | tee -a "${run_dir}/incremental-wandb-sync.log"
  fi

  echo "Exporting dfm-evals logs to Every Eval Ever JSON" | tee -a "${run_dir}/run.log"
  uv run --project "${DFM_EVALS_DIR}" evals eee inspect \
    --log-path "${inspect_log_dir}" \
    --output-dir "${eee_dir}" \
    --source-organization-name "schneiderkamplab" \
    --evaluator-relationship "first_party" \
    --inference-base-url "${base_url}" \
    --inference-provider-name "hrm-openai-shim" \
    2>&1 | tee -a "${run_dir}/eee-export.log"

  if [[ "${FINAL_WANDB_SYNC}" == "1" ]]; then
    echo "Logging all dfm-evals metrics to W&B under ${WANDB_PREFIX}/" | tee -a "${run_dir}/run.log"
    python scripts/log_dfm_evals_to_wandb.py \
      --eee-dir "${eee_dir}" \
      --epoch "${epoch}" \
      --project "${WANDB_PROJECT}" \
      --run-id "${WANDB_RUN_ID}" \
      --run-name "${WANDB_RUN_NAME}" \
      --prefix "${WANDB_PREFIX}" \
      2>&1 | tee -a "${run_dir}/wandb.log"
  fi

  cleanup
done
