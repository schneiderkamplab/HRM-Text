#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${GEMMA_MODEL_PATH:?Set GEMMA_MODEL_PATH to the HF id or local path for the Gemma teacher model}"

GPU_LIST="${GPU_LIST:-0,1,2,3,4,5,6,7}"
BASE_PORT="${BASE_PORT:-8100}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"
REQUESTS_PER_SHARD="${REQUESTS_PER_SHARD:-1000}"
CLIENT_CONCURRENCY="${CLIENT_CONCURRENCY:-32}"
GENERATION_ENDPOINT="${GENERATION_ENDPOINT:-chat}"
JUDGE_QUALITY="${JUDGE_QUALITY:-0}"
JUDGE_RETRIES="${JUDGE_RETRIES:-2}"
MAX_TOKENS="${MAX_TOKENS:-900}"
TEMPERATURE="${TEMPERATURE:-0.7}"
TOP_P="${TOP_P:-0.95}"
RETRIES="${RETRIES:-3}"
START_SERVERS="${START_SERVERS:-1}"
STOP_SERVERS_ON_EXIT="${STOP_SERVERS_ON_EXIT:-1}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
SHARD_ROOT="${SHARD_ROOT:-data/synthetic_request_shards_posttrain_transform_refine}"
GENERATED_ROOT="${GENERATED_ROOT:-data/generated_posttrain_transform_refine}"
LOG_ROOT="${LOG_ROOT:-logs/posttrain_transform_refine_generation}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
VLLM_PYTHON="${VLLM_PYTHON:-python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-$VLLM_PYTHON}"
CUDA_HOME="${CUDA_HOME:-$ROOT/external/cuda-13.2-shim}"
DG_JIT_NVCC_COMPILER="${DG_JIT_NVCC_COMPILER:-$CUDA_HOME/bin/nvcc}"
NVIDIA_CU13_ROOT="${NVIDIA_CU13_ROOT:-/home/ucloud/miniforge3/envs/hrm/lib/python3.13/site-packages/nvidia/cu13}"

PENDING_DIR="$SHARD_ROOT/pending"
RUNNING_DIR="$SHARD_ROOT/running"
DONE_DIR="$SHARD_ROOT/done"
FAILED_DIR="$SHARD_ROOT/failed"
SERVER_LOG_DIR="$LOG_ROOT/servers"
WORKER_LOG_DIR="$LOG_ROOT/workers"
PID_DIR="$LOG_ROOT/pids"

mkdir -p "$RUNNING_DIR" "$DONE_DIR" "$FAILED_DIR" "$SERVER_LOG_DIR" "$WORKER_LOG_DIR" "$PID_DIR" "$GENERATED_ROOT"

IFS=',' read -r -a GPUS <<< "$GPU_LIST"

cleanup_servers() {
  if [[ "$START_SERVERS" == "1" && "$STOP_SERVERS_ON_EXIT" == "1" ]]; then
    for pidfile in "$PID_DIR"/vllm_gpu*.pid; do
      [[ -f "$pidfile" ]] || continue
      pid="$(cat "$pidfile")"
      if kill -0 "$pid" 2>/dev/null; then
        kill -- "-$pid" 2>/dev/null || true
        kill "$pid" 2>/dev/null || true
      fi
    done
    sleep 5
    for pidfile in "$PID_DIR"/vllm_gpu*.pid; do
      [[ -f "$pidfile" ]] || continue
      pid="$(cat "$pidfile")"
      if kill -0 "$pid" 2>/dev/null; then
        kill -KILL -- "-$pid" 2>/dev/null || true
        kill -KILL "$pid" 2>/dev/null || true
      fi
      rm -f "$pidfile"
    done
  fi
}
trap cleanup_servers EXIT

port_for_gpu_index() {
  local idx="$1"
  echo $((BASE_PORT + idx))
}

wait_for_server() {
  local port="$1"
  local deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    if (( SECONDS > deadline )); then
      echo "Timed out waiting for vLLM server on port ${port}" >&2
      return 1
    fi
    sleep 5
  done
}

start_server() {
  local idx="$1"
  local gpu="$2"
  local port="$3"
  local log="$SERVER_LOG_DIR/gpu${gpu}_port${port}.log"
  local pidfile="$PID_DIR/vllm_gpu${gpu}.pid"

  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "vLLM server already running for GPU ${gpu}: PID $(cat "$pidfile")"
    return
  fi

  read -r -a extra_args <<< "$VLLM_EXTRA_ARGS"
  if [[ ${#extra_args[@]} -eq 0 && "${VLLM_FORCE_TEXT_ONLY:-0}" == "1" ]]; then
    extra_args=(
      --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}'
    )
  fi
  echo "Starting vLLM server on GPU ${gpu}, port ${port}; log: ${log}"
  CUDA_VISIBLE_DEVICES="$gpu" \
  CUDA_HOME="$CUDA_HOME" \
  DG_JIT_NVCC_COMPILER="$DG_JIT_NVCC_COMPILER" \
  LD_LIBRARY_PATH="$NVIDIA_CU13_ROOT/lib:$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}" \
  setsid \
  "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$GEMMA_MODEL_PATH" \
    --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 \
    --port "$port" \
    --tensor-parallel-size 1 \
    --dtype bfloat16 \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --disable-uvicorn-access-log \
    "${extra_args[@]}" \
    > "$log" 2>&1 &
  echo "$!" > "$pidfile"
}

claim_shard() {
  local gpu="$1"
  local shard
  local base
  local target
  for _ in {1..128}; do
    shard="$(find "$PENDING_DIR" -maxdepth 1 -type f -name '*.jsonl' | sort | head -n 1 || true)"
    [[ -n "$shard" ]] || return 1
    base="$(basename "$shard")"
    target="$RUNNING_DIR/${base%.jsonl}.gpu${gpu}.jsonl"
    if mv "$shard" "$target" 2>/dev/null; then
      echo "$target"
      return 0
    fi
    sleep 0.05
  done
  return 1
}

worker_loop() {
  local idx="$1"
  local gpu="$2"
  local port="$3"
  local log="$WORKER_LOG_DIR/gpu${gpu}.log"
  local base_url="http://127.0.0.1:${port}/v1"

  {
    echo "worker gpu=${gpu} port=${port} base_url=${base_url}"
    while true; do
      local shard
      if ! shard="$(claim_shard "$gpu")"; then
        echo "no pending shards left for gpu=${gpu}"
        break
      fi
      local shard_base
      shard_base="$(basename "$shard")"
      local clean_base="${shard_base%.gpu${gpu}.jsonl}.jsonl"
      echo "START $(date --iso-8601=seconds) gpu=${gpu} shard=${clean_base}"
      judge_args=()
      if [[ "$JUDGE_QUALITY" == "1" ]]; then
        judge_args=(--judge-quality --judge-retries "$JUDGE_RETRIES")
      fi
      if "$CLIENT_PYTHON" scripts/prepare_posttrain_transform_refine.py generate-synthetic \
        --request-root "$RUNNING_DIR" \
        --request-glob "$shard_base" \
        --generated-root "$GENERATED_ROOT" \
        --base-url "$base_url" \
        --model "$SERVED_MODEL_NAME" \
        --temperature "$TEMPERATURE" \
        --top-p "$TOP_P" \
        --max-tokens "$MAX_TOKENS" \
        --retries "$RETRIES" \
        --concurrency "$CLIENT_CONCURRENCY" \
        --endpoint "$GENERATION_ENDPOINT" \
        "${judge_args[@]}"; then
        mv "$shard" "$DONE_DIR/$clean_base"
        echo "DONE  $(date --iso-8601=seconds) gpu=${gpu} shard=${clean_base}"
      else
        mv "$shard" "$FAILED_DIR/$clean_base"
        echo "FAIL  $(date --iso-8601=seconds) gpu=${gpu} shard=${clean_base}"
      fi
    done
  } > "$log" 2>&1
}

if [[ ! -d "$PENDING_DIR" ]] || [[ -z "$(find "$PENDING_DIR" -maxdepth 1 -type f -name '*.jsonl' -print -quit 2>/dev/null)" ]]; then
  echo "Creating request shards under $PENDING_DIR"
  "$CLIENT_PYTHON" scripts/prepare_posttrain_transform_refine.py shard-synthetic-requests \
    --requests-per-shard "$REQUESTS_PER_SHARD" \
    --force
fi

if [[ "$START_SERVERS" == "1" ]]; then
  for idx in "${!GPUS[@]}"; do
    start_server "$idx" "${GPUS[$idx]}" "$(port_for_gpu_index "$idx")"
  done
fi

for idx in "${!GPUS[@]}"; do
  wait_for_server "$(port_for_gpu_index "$idx")"
done

echo "All vLLM servers are ready. Starting ${#GPUS[@]} shard workers."
worker_pids=()
for idx in "${!GPUS[@]}"; do
  worker_loop "$idx" "${GPUS[$idx]}" "$(port_for_gpu_index "$idx")" &
  worker_pid="$!"
  worker_pids+=("$worker_pid")
  echo "$worker_pid" > "$PID_DIR/worker_gpu${GPUS[$idx]}.pid"
done

for worker_pid in "${worker_pids[@]}"; do
  wait "$worker_pid"
done

if [[ -n "$(find "$FAILED_DIR" -maxdepth 1 -type f -name '*.jsonl' -print -quit 2>/dev/null)" ]]; then
  echo "Some shards failed. Inspect $FAILED_DIR and $WORKER_LOG_DIR." >&2
  exit 1
fi

echo "All shards completed. Generated outputs are in $GENERATED_ROOT"
