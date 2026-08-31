#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/dbc_repaired_100_per_file_20260828}"
GPU="${GPU:-0}"
PORT="${PORT:-8520}"
POLL_SECONDS="${POLL_SECONDS:-30}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
SERVED_MODEL="${SERVED_MODEL:-openai/gemma-4-e4b-dbc-rejudge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"

mkdir -p "$AUDIT_DIR/rejudge_server" "$AUDIT_DIR/cache/rejudge_gpu${GPU}"
exec > >(tee -a "$AUDIT_DIR/rejudge_launcher.log") 2>&1

uuid="$(nvidia-smi -i "$GPU" --query-gpu=uuid --format=csv,noheader,nounits | tr -d '[:space:]')"
gpu_is_free() {
  ! nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null \
    | sed 's/[[:space:]]//g' | grep -Fxq "$uuid"
}

echo "GPU${GPU}: waiting for existing compute processes to exit"
while ! gpu_is_free; do sleep "$POLL_SECONDS"; done
exec {lock_fd}>"/tmp/hrm-gpu-${GPU}.lock"
flock "$lock_fd"
while ! gpu_is_free; do sleep "$POLL_SECONDS"; done

echo "GPU${GPU}: free; starting calibrated DBC rejudge"
CUDA_VISIBLE_DEVICES="$GPU" \
  CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}" \
  PATH="${CUDA_HOME:-/usr/local/cuda}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
  LD_LIBRARY_PATH="${CUDA_HOME:-/usr/local/cuda}/lib64:${LD_LIBRARY_PATH:-}" \
  VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  TORCHINDUCTOR_CACHE_DIR="$AUDIT_DIR/cache/rejudge_gpu${GPU}/torchinductor" \
  TRITON_CACHE_DIR="$AUDIT_DIR/cache/rejudge_gpu${GPU}/triton" \
  setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name "$SERVED_MODEL" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 8192 \
    --gpu-memory-utilization 0.90 --max-num-seqs 64 --enforce-eager \
    >"$AUDIT_DIR/rejudge_server/server.log" 2>&1 &
server_pid=$!
echo "$server_pid" >"$AUDIT_DIR/rejudge_server/server.pid"
cleanup() {
  if kill -0 "$server_pid" 2>/dev/null; then
    kill -TERM -- "-$server_pid" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

deadline=$((SECONDS + 900))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "DBC rejudge server exited during startup" >&2
    exit 1
  fi
  if (( SECONDS > deadline )); then
    echo "DBC rejudge server startup timed out" >&2
    exit 1
  fi
  sleep 2
done

for attempt in 1 2 3 4; do
  if "$CLIENT_PYTHON" scripts/rejudge_repaired_dbc_failures.py audit \
    --audit-dir "$AUDIT_DIR" --base-url "http://127.0.0.1:${PORT}/v1" \
    --model "$SERVED_MODEL" --concurrency 64 >>"$AUDIT_DIR/rejudge_worker.log" 2>&1; then
    break
  fi
  if (( attempt == 4 )); then
    echo "DBC rejudge exhausted retries" >&2
    exit 1
  fi
  sleep $((attempt * 2))
done

"$CLIENT_PYTHON" scripts/rejudge_repaired_dbc_failures.py merge \
  --audit-dir "$AUDIT_DIR" --model "$SERVED_MODEL" >"$AUDIT_DIR/rejudge_merge.log" 2>&1
echo "DBC calibrated rejudge and merge complete"
