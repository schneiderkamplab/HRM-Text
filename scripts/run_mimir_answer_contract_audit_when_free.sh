#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/mimir_answer_contract_calibration}"
RUN_ROOT="${RUN_ROOT:-$ROOT/logs/data_audits/mimir_answer_contract_calibration_20260830}"
SAMPLES="${SAMPLES:-$DATA_ROOT/audit/samples.jsonl}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-e4b-answer-contract-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-9100}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
STABLE_SECONDS="${STABLE_SECONDS:-30}"
IFS=',' read -r -a GPUS <<< "${GPUS:-0,1,2,3,4,5,6,7}"
PARTITIONS="${#GPUS[@]}"

mkdir -p "$RUN_ROOT"/{servers,partitions,pids,cache}
exec 9>"$DATA_ROOT/audit/campaign.lock"
flock -n 9 || { echo "Another answer-contract audit holds the campaign lock" >&2; exit 2; }
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1

[[ -s "$SAMPLES" ]] || { echo "Missing audit samples: $SAMPLES" >&2; exit 1; }

echo "$(date -Is) waiting for Open Chats and its chained Tidsskrift campaign"
while pgrep -f '[r]un_dfm10_open_grounded_chats_8gpu.sh|[r]un_dfm10_tidsskrift_(after_open_chats|grounded_8gpu).sh' >/dev/null; do
  sleep 30
done

all_gpus_free() {
  local values value
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq "${#GPUS[@]}" ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}

echo "$(date -Is) waiting for all GPUs to remain below ${FREE_THRESHOLD_MIB} MiB"
while true; do
  all_gpus_free || { sleep 30; continue; }
  sleep "$STABLE_SECONDS"
  all_gpus_free && break
done

server_pids=()
worker_pids=()
cleanup() {
  local pid
  for pid in "${worker_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${server_pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "${server_pids[@]:-}"; do
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  port=$((PORT_BASE + worker))
  cache="$RUN_ROOT/cache/gpu${gpu}"
  mkdir -p "$cache"
  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
    PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
    LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$cache/torchinductor" TRITON_CACHE_DIR="$cache/triton" \
    setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
      --host 127.0.0.1 --port "$port" --max-model-len "$MAX_MODEL_LEN" \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-num-seqs 128 --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pids+=("$!")
  echo "$!" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
done

for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  port=$((PORT_BASE + worker))
  deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    kill -0 "${server_pids[$worker]}" 2>/dev/null || { echo "GPU${gpu} server exited" >&2; exit 1; }
    sleep 2
  done
done

for worker in "${!GPUS[@]}"; do
  "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$SAMPLES" --output "$RUN_ROOT/partitions/partition_${worker}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + worker))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$worker" --concurrency "$CONCURRENCY" \
    --max-tokens 512 --retries 3 --resume --progress-interval 25 \
    >"$RUN_ROOT/partitions/partition_${worker}.log" 2>&1 &
  worker_pids+=("$!")
done

status=0
for worker in "${!GPUS[@]}"; do
  wait "${worker_pids[$worker]}" || { echo "Partition $worker failed" >&2; status=1; }
done
worker_pids=()
(( status == 0 )) || exit "$status"

"$CLIENT_PYTHON" scripts/dfm10_quality_audit.py merge \
  --samples "$SAMPLES" --partition-root "$RUN_ROOT/partitions" \
  --partitions "$PARTITIONS" --output "$RUN_ROOT/answer_contract_quality_audit.jsonl"
echo "$(date -Is) answer-contract audit complete"
