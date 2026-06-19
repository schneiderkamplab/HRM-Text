#!/usr/bin/env bash
set -euo pipefail

cd /work/dfm/HRM-Text

GPU="${GPU:-0}"
PORT="${PORT:-18641}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/brainsurgery/models/google/gemma-4-E2B-it}"
MODEL_NAME="${MODEL_NAME:-gemma4-e2b-it-smoke}"
LOG_ROOT="${LOG_ROOT:-logs/eval/gemma4_e2b_clean_standard_smoke_$(date +%Y%m%d_%H%M%S)}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
SMOKE_BATCH_SIZE="${SMOKE_BATCH_SIZE:-8}"

mkdir -p "${LOG_ROOT}"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

CUDA_VISIBLE_DEVICES="${GPU}" \
VLLM_CACHE_ROOT="${LOG_ROOT}/vllm-cache" \
TORCHINDUCTOR_CACHE_DIR="${LOG_ROOT}/torchinductor-cache" \
TRITON_CACHE_DIR="${LOG_ROOT}/triton-cache" \
CUDA_CACHE_PATH="${LOG_ROOT}/cuda-cache" \
"${PYTHON_BIN}" -m vllm.entrypoints.openai.api_server \
  --model "${MODEL_PATH}" \
  --served-model-name "${MODEL_NAME}" \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --dtype bfloat16 \
  --max-model-len 4096 \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.9}" \
  --enforce-eager \
  --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
  --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/gemma4_native_chat.jinja \
  > "${LOG_ROOT}/vllm.log" 2>&1 &
SERVER_PID="$!"

deadline=$((SECONDS + 900))
until curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; do
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "vLLM server exited during startup; see ${LOG_ROOT}/vllm.log" >&2
    exit 71
  fi
  if (( SECONDS >= deadline )); then
    echo "vLLM server did not become healthy; see ${LOG_ROOT}/vllm.log" >&2
    exit 124
  fi
  sleep 2
done

"${PYTHON_BIN}" -u -m evaluation.main \
  config=evaluation/config/external_chat_smoke.yaml \
  engine=OpenAIEngine \
  model="${MODEL_NAME}" \
  base_url="http://127.0.0.1:${PORT}/v1" \
  api_key="${OPENAI_API_KEY:-inspectai}" \
  generation_config.batch_size="${SMOKE_BATCH_SIZE}" \
  save_generations_dir="${LOG_ROOT}/generations" \
  2>&1 | tee "${LOG_ROOT}/evaluation.log"

echo "Smoke output: ${LOG_ROOT}"
