#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_ROOT="${RUN_ROOT:-logs/data_audits/dynaword_instruct_prompt_repair_20260828}"
REQUESTS="${REQUESTS:-data/dynaword_instruct_repair/prompt_repair_requests.jsonl}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
[[ -f "$MODEL_PATH/config.json" ]] || MODEL_PATH="/work/dfm/brainsurgery/models/google/gemma-4-31B-it"
MODEL_NAME="${MODEL_NAME:-posttrain-gemma-teacher}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
PORT_BASE="${PORT_BASE:-8800}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.85}"
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
exec 9>"$RUN_ROOT/launcher.lock"; flock -n 9 || exit 2
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1
SERVER_PIDS=(); WORKER_PIDS=()
cleanup() {
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM
for worker in "${!GPUS[@]}"; do
  gpu="${GPUS[$worker]}"
  CUDA_VISIBLE_DEVICES="$gpu" VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    VLLM_DEEP_GEMM_WARMUP=skip \
    TORCHINDUCTOR_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/triton" \
    setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" --host 127.0.0.1 --port "$((PORT_BASE+worker))" \
      --max-model-len 8192 --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" --max-num-seqs 64 --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  SERVER_PIDS+=("$!"); echo "$!" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
done
for worker in "${!GPUS[@]}"; do
  deadline=$((SECONDS+900))
  until curl -fsS "http://127.0.0.1:$((PORT_BASE+worker))/v1/models" >/dev/null 2>&1; do
    ((SECONDS<=deadline)) || exit 1
    kill -0 "${SERVER_PIDS[$worker]}" 2>/dev/null || exit 1
    sleep 2
  done
done
for worker in "${!GPUS[@]}"; do
  "$CLIENT_PYTHON" scripts/generate_dynaword_instruct_prompt_repairs.py generate \
    --requests "$REQUESTS" --output "$RUN_ROOT/partitions/partition_${worker}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE+worker))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$worker" --concurrency "$CONCURRENCY" --resume \
    >"$RUN_ROOT/partitions/partition_${worker}.log" 2>&1 &
  WORKER_PIDS+=("$!")
done
status=0
for worker in "${!GPUS[@]}"; do wait "${WORKER_PIDS[$worker]}" || status=1; done
WORKER_PIDS=(); ((status==0)) || exit "$status"
"$CLIENT_PYTHON" scripts/generate_dynaword_instruct_prompt_repairs.py merge \
  --requests "$REQUESTS" --partition-root "$RUN_ROOT/partitions" --partitions "$PARTITIONS" \
  --output "$RUN_ROOT/prompt_repairs.jsonl"
