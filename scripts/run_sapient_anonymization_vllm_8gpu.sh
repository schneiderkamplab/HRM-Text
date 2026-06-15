#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"
GPUS_CSV="${GPUS_CSV:-0,1,2,3,4,5,6,7}"
BASE_PORT="${BASE_PORT:-8900}"
CONCURRENCY_PER_SHARD="${CONCURRENCY_PER_SHARD:-8}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
SOURCE_PRIORITY="${SOURCE_PRIORITY:-high40}"
LAUNCH_STAGGER_SECONDS="${LAUNCH_STAGGER_SECONDS:-1}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
STAMP="${STAMP:-$(date +%Y%m%dT%H%M%S)}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/sapient_anonymization_${STAMP}}"
VLLM_USE_DEEP_GEMM="${VLLM_USE_DEEP_GEMM:-0}"
VLLM_MOE_USE_DEEP_GEMM="${VLLM_MOE_USE_DEEP_GEMM:-0}"

IFS=',' read -r -a GPUS <<< "$GPUS_CSV"
NUM_SHARDS="${#GPUS[@]}"

mkdir -p "$LOG_ROOT/servers" "$LOG_ROOT/workers"
mkdir -p "$LOG_ROOT/cache"

server_pids=()
worker_pids=()

cleanup() {
  set +e
  for pid in "${worker_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${server_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

cd "$ROOT"

for idx in "${!GPUS[@]}"; do
  gpu="${GPUS[$idx]}"
  port="$((BASE_PORT + idx))"
  CUDA_VISIBLE_DEVICES="$gpu" \
  VLLM_USE_DEEP_GEMM="$VLLM_USE_DEEP_GEMM" \
  VLLM_MOE_USE_DEEP_GEMM="$VLLM_MOE_USE_DEEP_GEMM" \
  VLLM_CACHE_ROOT="$LOG_ROOT/cache/vllm_gpu${gpu}" \
  TORCHINDUCTOR_CACHE_DIR="$LOG_ROOT/cache/torchinductor_gpu${gpu}" \
  TRITON_CACHE_DIR="$LOG_ROOT/cache/triton_gpu${gpu}" \
  python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 \
    --port "$port" \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.9 \
    --max-num-seqs "$MAX_NUM_SEQS" \
    > "$LOG_ROOT/servers/gpu${gpu}_port${port}.log" 2>&1 &
  server_pids+=("$!")
  echo "server gpu=$gpu port=$port pid=${server_pids[-1]}"
done

echo "Waiting for vLLM servers..."
for idx in "${!GPUS[@]}"; do
  port="$((BASE_PORT + idx))"
  ready=0
  for _ in $(seq 1 240); do
    if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
      echo "ready port=$port"
      ready=1
      break
    fi
    sleep 2
  done
  if [[ "$ready" != 1 ]]; then
    echo "ERROR: vLLM server on port $port did not become ready" >&2
    exit 1
  fi
done

for idx in "${!GPUS[@]}"; do
  gpu="${GPUS[$idx]}"
  port="$((BASE_PORT + idx))"
  env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES="$gpu" \
    python scripts/synthesize_anonymized_sapient_exclusions.py \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --num-shards "$NUM_SHARDS" \
      --shard-index "$idx" \
      --max-attempts "$MAX_ATTEMPTS" \
      --source-priority "$SOURCE_PRIORITY" \
      --concurrency "$CONCURRENCY_PER_SHARD" \
      > "$LOG_ROOT/workers/gpu${gpu}_shard${idx}of${NUM_SHARDS}.log" 2>&1 &
  worker_pids+=("$!")
  echo "worker gpu=$gpu shard=$idx/$NUM_SHARDS pid=${worker_pids[-1]}"
  sleep "$LAUNCH_STAGGER_SECONDS"
done

echo "LOG_ROOT=$LOG_ROOT"
wait "${worker_pids[@]}"
