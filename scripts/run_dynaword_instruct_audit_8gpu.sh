#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_ROOT="${RUN_ROOT:-logs/data_audits/dynaword_instruct_repair_20260828}"
SAMPLES="${SAMPLES:-$RUN_ROOT/samples.jsonl}"
MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-e4b-dynaword-instruct-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8700}"
CONCURRENCY="${CONCURRENCY:-128}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
IFS=',' read -r -a GPUS <<< "${GPUS:-0,1,2,3,4,5,6,7}"
PARTITIONS="${#GPUS[@]}"

mkdir -p "$RUN_ROOT"/{servers,partitions,pids,cache}
LAYOUT="$RUN_ROOT/partition_count.txt"
if [[ -f "$LAYOUT" ]]; then
  [[ "$(<"$LAYOUT")" == "$PARTITIONS" ]] || {
    echo "Partition count differs from existing run state in $LAYOUT" >&2
    exit 2
  }
else
  shopt -s nullglob
  existing=("$RUN_ROOT"/partitions/partition_*.jsonl)
  shopt -u nullglob
  [[ ${#existing[@]} -eq 0 || ${#existing[@]} -eq $PARTITIONS ]] || {
    echo "Existing partition files do not match requested partition count" >&2
    exit 2
  }
  printf '%s\n' "$PARTITIONS" >"$LAYOUT"
fi
exec 9>"$RUN_ROOT/launcher.lock"
flock -n 9 || { echo "Another launcher holds $RUN_ROOT/launcher.lock" >&2; exit 2; }
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

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
      --host 127.0.0.1 --port "$port" --max-model-len "$MAX_MODEL_LEN" \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-num-seqs 128 --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  SERVER_PIDS+=("$!")
  echo "$!" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
done

for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  port=$((PORT_BASE + worker)); deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    kill -0 "${SERVER_PIDS[$worker]}" 2>/dev/null || { echo "worker ${worker} server exited" >&2; exit 1; }
    sleep 2
  done
done

for worker in "${!GPUS[@]}"; do
  "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$SAMPLES" --output "$RUN_ROOT/partitions/partition_${worker}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + worker))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$worker" --concurrency "$CONCURRENCY" \
    --max-tokens 512 --retries 3 --resume --progress-interval 250 \
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
  --partitions "$PARTITIONS" --output "$RUN_ROOT/dynaword_instruct_quality_audit.jsonl"
