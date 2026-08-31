#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/dolci_tool_use_repaired_20260828}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
SERVED_MODEL="${SERVED_MODEL:-openai/gemma-4-e4b-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT="${PORT:-8580}"
CONCURRENCY="${CONCURRENCY:-64}"
POLL_SECONDS="${POLL_SECONDS:-30}"

mkdir -p "$AUDIT_DIR"/{server,results,cache,pids}
exec > >(tee -a "$AUDIT_DIR/launcher.log") 2>&1

gpu_uuid() {
  nvidia-smi -i "$1" --query-gpu=uuid --format=csv,noheader,nounits | tr -d '[:space:]'
}

gpu_is_free() {
  local uuid="$1"
  ! nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null \
    | sed 's/[[:space:]]//g' | grep -Fxq "$uuid"
}

gpu=""
while [[ -z "$gpu" ]]; do
  for candidate in 0 1 2 3 4 5 6 7; do
    uuid="$(gpu_uuid "$candidate")"
    if gpu_is_free "$uuid"; then
      exec {lock_fd}>"/tmp/hrm-gpu-${candidate}.lock"
      if flock -n "$lock_fd" && gpu_is_free "$uuid"; then
        gpu="$candidate"
        break
      fi
      exec {lock_fd}>&-
    fi
  done
  [[ -n "$gpu" ]] || sleep "$POLL_SECONDS"
done
echo "GPU${gpu}: starting repaired DOLCI audit"

CUDA_VISIBLE_DEVICES="$gpu" \
  CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}" \
  PATH="${CUDA_HOME:-/usr/local/cuda}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
  LD_LIBRARY_PATH="${CUDA_HOME:-/usr/local/cuda}/lib64:${LD_LIBRARY_PATH:-}" \
  VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  TORCHINDUCTOR_CACHE_DIR="$AUDIT_DIR/cache/torchinductor" \
  TRITON_CACHE_DIR="$AUDIT_DIR/cache/triton" \
  "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name "$SERVED_MODEL" \
    --host 127.0.0.1 --port "$PORT" --max-model-len 8192 \
    --gpu-memory-utilization 0.90 --max-num-seqs 64 --enforce-eager \
    >"$AUDIT_DIR/server/server.log" 2>&1 &
server_pid=$!
echo "$server_pid" >"$AUDIT_DIR/pids/server.pid"
cleanup() {
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

deadline=$((SECONDS + 900))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; do
  kill -0 "$server_pid" 2>/dev/null || { echo "server exited during startup" >&2; exit 1; }
  (( SECONDS <= deadline )) || { echo "server startup timed out" >&2; exit 1; }
  sleep 2
done

for attempt in 1 2 3 4; do
  if "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$AUDIT_DIR/samples.jsonl" \
    --output "$AUDIT_DIR/results/partition_0.jsonl" \
    --base-url "http://127.0.0.1:${PORT}/v1" --model "$SERVED_MODEL" \
    --partitions 1 --partition-index 0 --concurrency "$CONCURRENCY" --resume; then
    break
  fi
  (( attempt < 4 )) || exit 1
  sleep $((attempt * 2))
done

"$CLIENT_PYTHON" scripts/dfm10_quality_audit.py merge \
  --samples "$AUDIT_DIR/samples.jsonl" \
  --partition-root "$AUDIT_DIR/results" --partitions 1 \
  --output "$AUDIT_DIR/dolci_tool_use_repaired_quality_audit.jsonl"
"$CLIENT_PYTHON" scripts/audit_repaired_dolci_tool_use.py summarize \
  --input "$AUDIT_DIR/dolci_tool_use_repaired_quality_audit.jsonl" \
  --output "$AUDIT_DIR/summary.json"
