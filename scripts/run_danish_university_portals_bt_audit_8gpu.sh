#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_ROOT="${RUN_ROOT:-logs/data_audits/danish_university_portals_bt_repair_20260829}"
SAMPLES="${SAMPLES:-$RUN_ROOT/samples.jsonl}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-e4b-university-portals-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
PORT_BASE="${PORT_BASE:-8720}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MIN_FREE_MIB="${MIN_FREE_MIB:-180000}"
STABLE_SECONDS="${STABLE_SECONDS:-300}"
IFS=',' read -r -a GPUS <<< "${GPUS:-0,1,2,3,4,5,6,7}"
PARTITIONS="${#GPUS[@]}"

mkdir -p "$RUN_ROOT"/{servers,partitions,pids,cache}
exec 9>"$RUN_ROOT/launcher.lock"
flock -n 9 || { echo "Another university-portals audit launcher is active" >&2; exit 2; }
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid live
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for _ in {1..15}; do
    live=0
    for pid in "${SERVER_PIDS[@]:-}"; do kill -0 "$pid" 2>/dev/null && live=1; done
    (( live == 0 )) && break
    sleep 1
  done
  for pid in "${SERVER_PIDS[@]:-}"; do
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "Waiting for ${PARTITIONS} GPUs to remain above ${MIN_FREE_MIB} MiB free for ${STABLE_SECONDS}s..."
stable_since=0
while true; do
  ready=1
  for gpu in "${GPUS[@]}"; do
    free="$(nvidia-smi -i "$gpu" --query-gpu=memory.free --format=csv,noheader,nounits | tr -d '[:space:]')"
    (( free >= MIN_FREE_MIB )) || ready=0
  done
  if (( ready == 1 )); then
    (( stable_since > 0 )) || stable_since="$(date +%s)"
    (( $(date +%s) - stable_since >= STABLE_SECONDS )) && break
  else
    stable_since=0
  fi
  sleep 10
done

for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  port=$((PORT_BASE + worker))
  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
    PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
    LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/triton" \
    setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
      --chat-template "$CHAT_TEMPLATE" \
      --host 127.0.0.1 --port "$port" --max-model-len 8192 \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-num-seqs 64 --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  SERVER_PIDS+=("$!")
  echo "$!" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
done

for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  port=$((PORT_BASE + worker))
  deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    kill -0 "${SERVER_PIDS[$worker]}" 2>/dev/null || { echo "GPU${gpu} server exited" >&2; exit 1; }
    sleep 2
  done
done

for worker in "${!GPUS[@]}"; do
  "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$SAMPLES" --output "$RUN_ROOT/partitions/partition_${worker}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + worker))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$worker" --concurrency "$CONCURRENCY" \
    --max-tokens 512 --retries 3 --resume --progress-interval 50 \
    >"$RUN_ROOT/partitions/partition_${worker}.log" 2>&1 &
  WORKER_PIDS+=("$!")
done

status=0
for worker in "${!GPUS[@]}"; do
  wait "${WORKER_PIDS[$worker]}" || { echo "Partition $worker failed" >&2; status=1; }
done
WORKER_PIDS=()
(( status == 0 )) || exit "$status"

"$CLIENT_PYTHON" scripts/dfm10_quality_audit.py merge \
  --samples "$SAMPLES" --partition-root "$RUN_ROOT/partitions" \
  --partitions "$PARTITIONS" --output "$RUN_ROOT/quality_audit.jsonl"
echo "University-portals full audit complete."
