#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/dbc_repaired_100_per_file_20260828}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
SERVED_MODEL="${SERVED_MODEL:-openai/gemma-4-e4b-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8500}"
POLL_SECONDS="${POLL_SECONDS:-30}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

mkdir -p "$AUDIT_DIR"/{servers,workers,pids,cache}
exec > >(tee -a "$AUDIT_DIR/launcher.log") 2>&1

gpu_uuid() {
  nvidia-smi -i "$1" --query-gpu=uuid --format=csv,noheader,nounits | tr -d '[:space:]'
}

gpu_is_free() {
  local uuid="$1"
  ! nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null \
    | sed 's/[[:space:]]//g' | grep -Fxq "$uuid"
}

run_partition() {
  local gpu="$1" partition="$2" port=$((PORT_BASE + gpu)) uuid
  uuid="$(gpu_uuid "$gpu")"
  echo "GPU${gpu}: waiting for all existing compute processes to exit"
  while ! gpu_is_free "$uuid"; do
    sleep "$POLL_SECONDS"
  done

  # Serialize cooperating jobs and recheck after taking the advisory lock.
  exec {lock_fd}>"/tmp/hrm-gpu-${gpu}.lock"
  flock "$lock_fd"
  while ! gpu_is_free "$uuid"; do
    sleep "$POLL_SECONDS"
  done
  echo "GPU${gpu}: free; starting DBC validation partition ${partition}"

  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}" \
    PATH="${CUDA_HOME:-/usr/local/cuda}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
    LD_LIBRARY_PATH="${CUDA_HOME:-/usr/local/cuda}/lib64:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 \
    FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$AUDIT_DIR/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$AUDIT_DIR/cache/gpu${gpu}/triton" \
    "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$SERVED_MODEL" \
      --host 127.0.0.1 --port "$port" --max-model-len 8192 \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 \
      --enforce-eager >"$AUDIT_DIR/servers/gpu${gpu}.log" 2>&1 &
  server_pid=$!
  echo "$server_pid" >"$AUDIT_DIR/pids/server_gpu${gpu}.pid"
  cleanup_partition() {
    local owned_pid
    owned_pid="$(cat "$AUDIT_DIR/pids/server_gpu${gpu}.pid" 2>/dev/null || true)"
    if [[ -n "$owned_pid" ]]; then
      kill "$owned_pid" 2>/dev/null || true
      wait "$owned_pid" 2>/dev/null || true
    fi
  }
  trap cleanup_partition EXIT INT TERM

  local deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    if ! kill -0 "$server_pid" 2>/dev/null; then
      echo "GPU${gpu}: server exited during startup" >&2
      return 1
    fi
    if (( SECONDS > deadline )); then
      echo "GPU${gpu}: server startup timed out" >&2
      return 1
    fi
    sleep 2
  done

  local audit_attempt
  for audit_attempt in 1 2 3 4; do
    if "$CLIENT_PYTHON" scripts/audit_repaired_dbc_sources.py audit \
      --audit-dir "$AUDIT_DIR" --partitions 8 --partition-index "$partition" \
      --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL" \
      --concurrency "$CONCURRENCY" >>"$AUDIT_DIR/workers/partition_${partition}.log" 2>&1; then
      break
    fi
    if (( audit_attempt == 4 )); then
      echo "GPU${gpu}: partition ${partition} exhausted audit retries" >&2
      return 1
    fi
    echo "GPU${gpu}: retrying partition ${partition} after transient judge error (${audit_attempt}/4)"
    sleep $((audit_attempt * 2))
  done
  echo "GPU${gpu}: partition ${partition} complete"
}

worker_pids=()
cleanup_watchers() {
  local pid
  for pid in "${worker_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup_watchers EXIT INT TERM
for gpu in 0 1 2 3 4 5 6 7; do
  run_partition "$gpu" "$gpu" &
  worker_pids+=("$!")
  echo "$!" >"$AUDIT_DIR/pids/watcher_gpu${gpu}.pid"
done

status=0
for pid in "${worker_pids[@]}"; do
  wait "$pid" || status=1
done
if (( status != 0 )); then
  echo "one or more validation partitions failed; merge not attempted" >&2
  exit 1
fi

"$CLIENT_PYTHON" scripts/audit_repaired_dbc_sources.py merge \
  --audit-dir "$AUDIT_DIR" --partitions 8 --model "$SERVED_MODEL"
echo "DBC repaired validation complete"
