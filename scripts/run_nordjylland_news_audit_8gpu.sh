#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/nordjylland_news_repaired_20260828}"
AUDIT_SCRIPT="${AUDIT_SCRIPT:-scripts/audit_repaired_nordjylland_news.py}"
AUDIT_LABEL="${AUDIT_LABEL:-NordjyllandNews repaired}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
if [[ ! -f "$MODEL_PATH/config.json" ]]; then
  MODEL_PATH="/work/dfm/brainsurgery/models/google/gemma-4-31B-it"
fi
SERVED_MODEL="${SERVED_MODEL:-google/gemma-4-31b-it-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8680}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
MIN_FREE_MEMORY_MIB="${MIN_FREE_MEMORY_MIB:-0}"
POLL_SECONDS="${POLL_SECONDS:-30}"
GPUS="${GPUS:-0,1,2,3,4,5,6,7}"

IFS=',' read -r -a gpu_list <<<"$GPUS"
partitions="${#gpu_list[@]}"
mkdir -p "$AUDIT_DIR"/{servers,workers,pids,cache}
exec > >(tee -a "$AUDIT_DIR/launcher.log") 2>&1

if [[ ! -f "$AUDIT_DIR/inventory.json" ]]; then
  "$CLIENT_PYTHON" "$AUDIT_SCRIPT" prepare \
    --audit-dir "$AUDIT_DIR" --samples 0 --partitions "$partitions"
fi

gpu_uuid() {
  nvidia-smi -i "$1" --query-gpu=uuid --format=csv,noheader,nounits | tr -d '[:space:]'
}

gpu_is_free() {
  local uuid="$1" gpu="$2"
  if (( MIN_FREE_MEMORY_MIB > 0 )); then
    local free_mib
    free_mib="$(nvidia-smi -i "$gpu" --query-gpu=memory.free --format=csv,noheader,nounits | tr -d '[:space:]')"
    (( free_mib >= MIN_FREE_MEMORY_MIB ))
    return
  fi
  ! nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null \
    | sed 's/[[:space:]]//g' | grep -Fxq "$uuid"
}

run_partition() {
  local gpu="$1" partition="$2" port=$((PORT_BASE + partition)) uuid="" server_pid=""
  trap 'echo "GPU${gpu}: partition ${partition} launcher error at line ${LINENO}" >&2' ERR
  if [[ -f "$AUDIT_DIR/results/partition_${partition}.audit.jsonl" ]]; then
    echo "GPU${gpu}: partition ${partition} already complete"
    return 0
  fi
  if (( MIN_FREE_MEMORY_MIB == 0 )); then
    until uuid="$(gpu_uuid "$gpu" 2>/dev/null)" && [[ -n "$uuid" ]]; do
      sleep "$POLL_SECONDS"
    done
  fi
  echo "GPU${gpu}: waiting for a free GPU for partition ${partition}"
  while ! gpu_is_free "$uuid" "$gpu"; do sleep "$POLL_SECONDS"; done
  exec {lock_fd}>"/tmp/hrm-gpu-${gpu}.lock"
  flock "$lock_fd"
  while ! gpu_is_free "$uuid" "$gpu"; do sleep "$POLL_SECONDS"; done

  cleanup() {
    if [[ -n "$server_pid" ]]; then
      kill "$server_pid" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT INT TERM
  echo "GPU${gpu}: starting partition ${partition}"
  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}" \
    PATH="${CUDA_HOME:-/usr/local/cuda}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
    LD_LIBRARY_PATH="${CUDA_HOME:-/usr/local/cuda}/lib64:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$AUDIT_DIR/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$AUDIT_DIR/cache/gpu${gpu}/triton" \
    "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$SERVED_MODEL" \
      --host 127.0.0.1 --port "$port" --max-model-len 8192 \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 \
      --enforce-eager >"$AUDIT_DIR/servers/gpu${gpu}.log" 2>&1 {lock_fd}>&- &
  server_pid=$!
  echo "$server_pid" >"$AUDIT_DIR/pids/server_gpu${gpu}.pid"

  local deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    kill -0 "$server_pid" 2>/dev/null || { echo "GPU${gpu}: server exited" >&2; return 1; }
    (( SECONDS <= deadline )) || { echo "GPU${gpu}: startup timed out" >&2; return 1; }
    sleep 2
  done

  local attempt
  for attempt in 1 2 3 4; do
    if "$CLIENT_PYTHON" "$AUDIT_SCRIPT" audit \
      --audit-dir "$AUDIT_DIR" --partition-index "$partition" \
      --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL" \
      --concurrency "$CONCURRENCY" >>"$AUDIT_DIR/workers/partition_${partition}.log" 2>&1 {lock_fd}>&-; then
      echo "GPU${gpu}: partition ${partition} complete"
      return 0
    fi
    echo "GPU${gpu}: retry ${attempt}/4 for partition ${partition}" >&2
    sleep $((attempt * 2))
  done
  return 1
}

worker_pids=()
cleanup_workers() {
  local pid
  for pid in "${worker_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup_workers EXIT INT TERM
for partition in "${!gpu_list[@]}"; do
  run_partition "${gpu_list[$partition]}" "$partition" &
  worker_pids+=("$!")
  # Avoid an eight-way burst of 60 GB checkpoint reads against WEKA.
  sleep "${STARTUP_STAGGER_SECONDS:-8}"
done
status=0
for pid in "${worker_pids[@]}"; do wait "$pid" || status=1; done
(( status == 0 )) || { echo "one or more partitions failed" >&2; exit 1; }
"$CLIENT_PYTHON" "$AUDIT_SCRIPT" merge \
  --audit-dir "$AUDIT_DIR" --partitions "$partitions" --model "$SERVED_MODEL"
echo "$AUDIT_LABEL audit complete"
