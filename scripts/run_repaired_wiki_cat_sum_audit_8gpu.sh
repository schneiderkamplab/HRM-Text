#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/wiki_cat_sum_repaired_20260828}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
SERVED_MODEL="${SERVED_MODEL:-openai/gemma-4-e4b-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8700}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
POLL_SECONDS="${POLL_SECONDS:-15}"
WAIT_FOR_ALL_GPUS_IDLE_SECONDS="${WAIT_FOR_ALL_GPUS_IDLE_SECONDS:-0}"

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

all_gpus_are_free() {
  [[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d')" ]]
}

if (( WAIT_FOR_ALL_GPUS_IDLE_SECONDS > 0 )); then
  idle_since=0
  echo "Waiting for all GPUs to remain free for ${WAIT_FOR_ALL_GPUS_IDLE_SECONDS}s"
  while true; do
    if all_gpus_are_free; then
      (( idle_since == 0 )) && idle_since=$SECONDS
      (( SECONDS - idle_since >= WAIT_FOR_ALL_GPUS_IDLE_SECONDS )) && break
    else
      idle_since=0
    fi
    sleep "$POLL_SECONDS"
  done
  echo "All GPUs passed the stable-idle gate"
fi

run_partition() {
  local gpu="$1" partition="$2" port=$((PORT_BASE + gpu)) uuid server_pid=""
  if [[ -f "$AUDIT_DIR/results/partition_${partition}.audit.jsonl" ]]; then
    echo "GPU${gpu}: partition ${partition} already complete"
    return 0
  fi
  uuid="$(gpu_uuid "$gpu")"
  while ! gpu_is_free "$uuid"; do sleep "$POLL_SECONDS"; done
  exec {lock_fd}>"/tmp/hrm-gpu-${gpu}.lock"
  flock "$lock_fd"
  while ! gpu_is_free "$uuid"; do sleep "$POLL_SECONDS"; done

  cleanup() {
    if [[ -n "$server_pid" ]]; then
      kill "$server_pid" 2>/dev/null || true
      wait "$server_pid" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT INT TERM
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
      --enforce-eager >"$AUDIT_DIR/servers/gpu${gpu}.log" 2>&1 &
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
    if "$CLIENT_PYTHON" scripts/audit_repaired_wiki_cat_sum.py audit \
      --audit-dir "$AUDIT_DIR" --partitions 8 --partition-index "$partition" \
      --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL" \
      --concurrency "$CONCURRENCY" >>"$AUDIT_DIR/workers/partition_${partition}.log" 2>&1; then
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
for gpu in 0 1 2 3 4 5 6 7; do
  run_partition "$gpu" "$gpu" &
  worker_pids+=("$!")
done

status=0
for pid in "${worker_pids[@]}"; do wait "$pid" || status=1; done
(( status == 0 )) || { echo "one or more partitions failed" >&2; exit 1; }
"$CLIENT_PYTHON" scripts/audit_repaired_wiki_cat_sum.py merge \
  --audit-dir "$AUDIT_DIR" --partitions 8 --model "$SERVED_MODEL"
echo "WikiCatSum audit complete"
