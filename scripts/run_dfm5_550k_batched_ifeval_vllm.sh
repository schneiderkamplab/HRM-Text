#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

EXPORT_DIR="${EXPORT_DIR:-/work/dfm/HRM-Text/exports/dfm5_L_step550000_ema_hf}"
MODEL_NAME="${MODEL_NAME:-hrm-dfm5-L-vllm-native-proxy-euroeval-step_550000}"
OUT_ROOT="${OUT_ROOT:-logs/euroeval/dfm5_L_step550000_vllm_native_proxy_batched_ifeval_$(date +%Y%m%d_%H%M%S)/step_550000}"
GPUS="${GPUS:-0,1}"
CONCURRENCY="${CONCURRENCY:-32}"
MAX_TOKENS="${MAX_TOKENS:-2048}"
EPOCH="${EPOCH:-1.4976296606915782}"
HOST="${HOST:-127.0.0.1}"
BASE_PORT="${BASE_PORT:-26000}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.22}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---enforce-eager --attention-backend FLASH_ATTN --chat-template /work/dfm/HRM-Text/evaluation/chat_templates/hrm_direct_chat.jinja}"

IFS=',' read -r -a GPU_LIST <<< "${GPUS}"
if [[ "${#GPU_LIST[@]}" -lt 2 ]]; then
  echo "Need at least two GPUs in GPUS for ifeval-da and ifeval." >&2
  exit 2
fi

mkdir -p "${OUT_ROOT}"
echo "${OUT_ROOT}" > /tmp/dfm5_550k_batched_ifeval_out_root

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

server_pids=()
cleanup() {
  for pid in "${server_pids[@]:-}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

run_task() {
  local task="$1"
  local gpu="$2"
  local offset="$3"
  local out_dir="${OUT_ROOT}/${task}"
  local proxy_port=$((BASE_PORT + offset))
  local vllm_port=$((BASE_PORT + 1000 + offset))
  mkdir -p "${out_dir}"

  CUDA_VISIBLE_DEVICES="${gpu}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION}" \
  VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS}" \
  scripts/hrm_vllm_openai_server.sh \
    --model "${EXPORT_DIR}" \
    --served-model-name "${MODEL_NAME}" \
    --host "${HOST}" \
    --port "${vllm_port}" \
    --max-model-len 4096 \
    > "${out_dir}/vllm.log" 2>&1 &
  local vllm_pid="$!"
  server_pids+=("${vllm_pid}")
  wait_for_vllm "http://${HOST}:${vllm_port}" "${MODEL_NAME}"

  "${PYTHON_BIN}" scripts/native_compatible_openai_proxy.py \
    --host "${HOST}" \
    --port "${proxy_port}" \
    --target-base-url "http://${HOST}:${vllm_port}/v1" \
    --model-name "${MODEL_NAME}" \
    --target-model-name "${MODEL_NAME}" \
    --api-key inspectai \
    --log-jsonl "${out_dir}/proxy_payloads.jsonl" \
    > "${out_dir}/server.log" 2>&1 &
  local proxy_pid="$!"
  server_pids+=("${proxy_pid}")
  wait_for_proxy "http://${HOST}:${proxy_port}/health"

  "${PYTHON_BIN}" scripts/run_ifeval_batched_openai.py \
    --dataset "${task}" \
    --api-base "http://${HOST}:${proxy_port}/v1" \
    --api-key inspectai \
    --model "${MODEL_NAME}" \
    --output-dir "${out_dir}" \
    --concurrency "${CONCURRENCY}" \
    --max-tokens "${MAX_TOKENS}" \
    --epoch "${EPOCH}" \
    --resume \
    > "${out_dir}/batched_ifeval.log" 2>&1
}

task_pids=()
run_task ifeval-da "${GPU_LIST[0]}" 0 &
task_pids+=("$!")
run_task ifeval "${GPU_LIST[1]}" 1 &
task_pids+=("$!")

status=0
for pid in "${task_pids[@]}"; do
  if ! wait "${pid}"; then
    status=1
  fi
done
trap - EXIT
cleanup

echo "Wrote ${OUT_ROOT}"
exit "${status}"
