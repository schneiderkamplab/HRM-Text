#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL_PATH="${MODEL_PATH:-/work/dfm/jacobwashere/brainsurgery/models/google/gemma-4-E4B-it}"
MODEL_NAME="${MODEL_NAME:-openai/gemma-4-e4b-openmath-judge}"
VLLM_PYTHON="${VLLM_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
CLIENT_PYTHON="${CLIENT_PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
RUN_ROOT="${RUN_ROOT:-logs/data_audits/openmathinstruct2_repaired_20260828}"
SAMPLES="${SAMPLES:-$RUN_ROOT/samples.jsonl}"
PORT_BASE="${PORT_BASE:-8500}"
CONCURRENCY="${CONCURRENCY:-64}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
PARTITIONS=8

mkdir -p "$RUN_ROOT"/{servers,partitions,pids,cache}
exec 9>"$RUN_ROOT/launcher.lock"
flock -n 9 || { echo "Another OpenMath audit launcher holds $RUN_ROOT/launcher.lock" >&2; exit 2; }
exec > >(tee -a "$RUN_ROOT/launcher.log") 2>&1

[[ -s "$SAMPLES" ]] || { echo "Missing samples: $SAMPLES" >&2; exit 2; }

SERVER_PIDS=()
WORKER_PIDS=()
cleanup() {
  local pid
  for pid in "${WORKER_PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${SERVER_PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

for gpu in {0..7}; do
  port=$((PORT_BASE + gpu))
  CUDA_VISIBLE_DEVICES="$gpu" \
    CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
    PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
    LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
    VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
    TORCHINDUCTOR_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/torchinductor" \
    TRITON_CACHE_DIR="$RUN_ROOT/cache/gpu${gpu}/triton" \
    setsid "$VLLM_PYTHON" -m vllm.entrypoints.openai.api_server \
      --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
      --host 127.0.0.1 --port "$port" --max-model-len 8192 \
      --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
      --max-num-seqs "$MAX_NUM_SEQS" --enforce-eager \
      >"$RUN_ROOT/servers/gpu${gpu}.log" 2>&1 &
  SERVER_PIDS+=("$!")
  echo "$!" >"$RUN_ROOT/pids/server_gpu${gpu}.pid"
done

for gpu in {0..7}; do
  port=$((PORT_BASE + gpu)); deadline=$((SECONDS + 900))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    (( SECONDS <= deadline )) || { echo "GPU${gpu} server startup timed out" >&2; exit 1; }
    kill -0 "${SERVER_PIDS[$gpu]}" 2>/dev/null || { echo "GPU${gpu} server exited" >&2; exit 1; }
    sleep 2
  done
  echo "server ready: GPU${gpu} port=${port}"
done

for gpu in {0..7}; do
  "$CLIENT_PYTHON" scripts/dfm10_quality_audit.py audit \
    --samples "$SAMPLES" --output "$RUN_ROOT/partitions/partition_${gpu}.jsonl" \
    --base-url "http://127.0.0.1:$((PORT_BASE + gpu))/v1" --model "$MODEL_NAME" \
    --partitions "$PARTITIONS" --partition-index "$gpu" --concurrency "$CONCURRENCY" \
    --max-tokens 512 --retries 3 --resume --progress-interval 25 \
    >"$RUN_ROOT/partitions/partition_${gpu}.log" 2>&1 &
  WORKER_PIDS+=("$!")
  echo "$!" >"$RUN_ROOT/pids/worker_gpu${gpu}.pid"
done

status=0
for gpu in {0..7}; do
  wait "${WORKER_PIDS[$gpu]}" || status=1
done
(( status == 0 )) || exit "$status"

"$CLIENT_PYTHON" scripts/dfm10_quality_audit.py merge \
  --samples "$SAMPLES" --partition-root "$RUN_ROOT/partitions" \
  --partitions "$PARTITIONS" --output "$RUN_ROOT/openmathinstruct2_repaired_quality_audit.jsonl"

echo "OpenMath repaired quality audit complete"
