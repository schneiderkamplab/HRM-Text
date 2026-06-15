#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"
CONCURRENCY_PER_SHARD="${CONCURRENCY_PER_SHARD:-128}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-128}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/sapient_anonymization_repeat30_opportunistic_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$LOG_ROOT/servers" "$LOG_ROOT/workers" "$LOG_ROOT/cache"
cd "$ROOT"

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

for gpu in 3 4; do
  port=$((8910 + gpu))
  CUDA_VISIBLE_DEVICES="$gpu" \
  VLLM_USE_DEEP_GEMM=0 \
  VLLM_MOE_USE_DEEP_GEMM=0 \
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

for gpu in 3 4; do
  port=$((8910 + gpu))
  ready=0
  for _ in $(seq 1 240); do
    if curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
      echo "ready gpu=$gpu port=$port"
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

for gpu in 3 4; do
  port=$((8910 + gpu))
  env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES="$gpu" \
    python scripts/synthesize_anonymized_sapient_exclusions.py \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --num-shards 8 \
      --shard-index "$gpu" \
      --max-attempts 3 \
      --source-priority repeat30 \
      --concurrency "$CONCURRENCY_PER_SHARD" \
      > "$LOG_ROOT/workers/gpu${gpu}_repeat30_shard${gpu}of8.log" 2>&1 &
  worker_pids+=("$!")
  echo "worker gpu=$gpu shard=$gpu/8 pid=${worker_pids[-1]}"
done

echo "LOG_ROOT=$LOG_ROOT"
wait "${worker_pids[@]}"
