#!/usr/bin/env bash
set -euo pipefail

# Run judge audits for the eight non-synthetic export datasets with one
# single-GPU vLLM Gemma server per dataset/GPU. This script does not filter the
# data; after auditing, run each dataset's self-contained:
#   python recreate_dataset.py filter --audit audit_full/audit.jsonl --output-root audited --force
# The filter subcommand keeps only rows with keep=true in the audit file. Rows
# that were judged negatively, errored, or were never audited are not retained.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPORT_ROOT="${EXPORT_ROOT:-${ROOT}/export}"
MODEL_PATH="${MODEL_PATH:-${ROOT}/data/models/google/gemma-4-31B-it-fresh-20260604}"
if [[ ! -d "$MODEL_PATH" ]]; then
  MODEL_PATH="/work/dfm/brainsurgery/models/google/gemma-4-31B-it"
fi
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"
PORT_BASE="${PORT_BASE:-8200}"
GPU_LIST="${GPU_LIST:-0 1 2 3 4 5 6 7}"
AUDIT_ROOT_NAME="${AUDIT_ROOT_NAME:-audit_full}"
SAMPLE_RATE="${SAMPLE_RATE:-1.0}"
CONCURRENCY="${CONCURRENCY:-8}"
MAX_RECORDS="${MAX_RECORDS:-}"
LOG_ROOT="${LOG_ROOT:-${ROOT}/logs/export_dataset_audits_$(date +%Y%m%dT%H%M%S)}"
VLLM_PYTHON="${VLLM_PYTHON:-python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-python}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-1}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
DEEP_GEMM_WARMUP="${DEEP_GEMM_WARMUP:-skip}"

DATASETS=(
  common-pile-denoising
  common-pile-paragraph-reordering
  common-pile-prefix-continuation
  common-pile-span-filling
  danish-dynaword-denoising
  danish-dynaword-paragraph-reordering
  danish-dynaword-prefix-continuation
  danish-dynaword-span-filling
)

mkdir -p "$LOG_ROOT"/{servers,audits,pids}

cleanup() {
  for pidfile in "$LOG_ROOT"/pids/vllm_gpu*.pid; do
    [[ -e "$pidfile" ]] || continue
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT

start_server() {
  local gpu="$1"
  local port="$2"
  local log="$LOG_ROOT/servers/gpu${gpu}.log"
  read -r -a extra_args <<<"$VLLM_EXTRA_ARGS"
  mkdir -p "$LOG_ROOT/cache/gpu${gpu}"
  CUDA_VISIBLE_DEVICES="$gpu" \
  VLLM_DEEP_GEMM_WARMUP="$DEEP_GEMM_WARMUP" \
  TORCHINDUCTOR_CACHE_DIR="$LOG_ROOT/cache/gpu${gpu}/torchinductor" \
  TRITON_CACHE_DIR="$LOG_ROOT/cache/gpu${gpu}/triton" \
  "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 \
    --port "$port" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    "${extra_args[@]}" \
    >"$log" 2>&1 &
  echo "$!" >"$LOG_ROOT/pids/vllm_gpu${gpu}.pid"
}

wait_server() {
  local port="$1"
  local deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    if (( SECONDS > deadline )); then
      echo "Timed out waiting for vLLM server on port ${port}" >&2
      return 1
    fi
    sleep 2
  done
}

read -r -a GPUS <<<"$GPU_LIST"
if (( ${#GPUS[@]} < ${#DATASETS[@]} )); then
  echo "Need at least ${#DATASETS[@]} GPUs in GPU_LIST, got ${#GPUS[@]}" >&2
  exit 1
fi

echo "Starting ${#DATASETS[@]} vLLM servers from model: $MODEL_PATH"
for idx in "${!DATASETS[@]}"; do
  gpu="${GPUS[$idx]}"
  port=$((PORT_BASE + idx))
  start_server "$gpu" "$port"
done

for idx in "${!DATASETS[@]}"; do
  port=$((PORT_BASE + idx))
  wait_server "$port"
  echo "server ready: port=$port dataset=${DATASETS[$idx]}"
done

echo "Launching audits. Logs: $LOG_ROOT"
for idx in "${!DATASETS[@]}"; do
  dataset="${DATASETS[$idx]}"
  port=$((PORT_BASE + idx))
  dataset_dir="$EXPORT_ROOT/$dataset"
  audit_dir="$dataset_dir/$AUDIT_ROOT_NAME"
  audit_log="$LOG_ROOT/audits/${dataset}.log"
  max_args=()
  if [[ -n "$MAX_RECORDS" ]]; then
    max_args=(--max-records "$MAX_RECORDS")
  fi
  (
    cd "$dataset_dir"
    "$CLIENT_PYTHON" recreate_dataset.py audit \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --sample-rate "$SAMPLE_RATE" \
      --concurrency "$CONCURRENCY" \
      --audit-root "$audit_dir" \
      --force \
      "${max_args[@]}"
  ) >"$audit_log" 2>&1 &
  echo "$!" >"$LOG_ROOT/pids/audit_${dataset}.pid"
done

status=0
for dataset in "${DATASETS[@]}"; do
  pid="$(cat "$LOG_ROOT/pids/audit_${dataset}.pid")"
  if wait "$pid"; then
    echo "audit complete: $dataset"
  else
    echo "audit failed: $dataset (see $LOG_ROOT/audits/${dataset}.log)" >&2
    status=1
  fi
done

echo "Audit logs and server logs: $LOG_ROOT"
exit "$status"
