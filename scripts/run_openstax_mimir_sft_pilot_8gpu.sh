#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/mimir_openstax_sft}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
SERVED_MODEL="${SERVED_MODEL:-mimir-openstax-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
CONCURRENCY="${CONCURRENCY:-64}"
PORT_BASE="${PORT_BASE:-8700}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/mimir_openstax_sft_pilot_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$LOG_ROOT"/{servers,workers,pids,queue/pending,queue/running,queue/done,queue/failed,cache}
printf '%s\n' "$LOG_ROOT" > "$DATA_ROOT/current_run_log_root.txt"

started_pids=()
worker_pids=()
cleanup() {
  for pid in "${started_pids[@]:-}"; do
    kill -TERM -- "-$pid" >/dev/null 2>&1 || true
  done
  sleep 2
  for pid in "${started_pids[@]:-}"; do
    kill -KILL -- "-$pid" >/dev/null 2>&1 || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

all_gpus_free() {
  local used
  mapfile -t used < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#used[@]}" -eq 8 ]] || return 1
  for value in "${used[@]}"; do
    (( value <= FREE_THRESHOLD_MIB )) || return 1
  done
}

wait_for_inputs_and_gpus() {
  until [[ -f "$DATA_ROOT/requests/summary.json" ]]; do
    echo "$(date -Is) waiting for OpenStax request preparation"
    sleep 60
  done
  until all_gpus_free; do
    echo "$(date -Is) waiting for all GPUs to fall below ${FREE_THRESHOLD_MIB} MiB"
    nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
    sleep 60
  done
}

wait_server() {
  local port="$1" pid="$2" deadline=$((SECONDS + 1200))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    kill -0 "$pid" 2>/dev/null || return 1
    (( SECONDS < deadline )) || return 1
    sleep 2
  done
}

start_server() {
  local gpu="$1" port=$((PORT_BASE + gpu)) log="$LOG_ROOT/servers/gpu${gpu}.log"
  mkdir -p "$LOG_ROOT/cache/gpu${gpu}"
  CUDA_VISIBLE_DEVICES="$gpu" \
  CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
  PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:$PATH" \
  LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
  VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  TORCHINDUCTOR_CACHE_DIR="$LOG_ROOT/cache/gpu${gpu}/torchinductor" \
  TRITON_CACHE_DIR="$LOG_ROOT/cache/gpu${gpu}/triton" \
  setsid "$PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --served-model-name "$SERVED_MODEL" \
    --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
    --chat-template "$ROOT/data_io/chat_templates/gemma4_native_chat.jinja" \
    --host 127.0.0.1 \
    --port "$port" \
    --tensor-parallel-size 1 \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --enforce-eager \
    >"$log" 2>&1 &
  local pid=$!
  echo "$pid" >"$LOG_ROOT/pids/server_gpu${gpu}.pid"
  started_pids+=("$pid")
  wait_server "$port" "$pid"
  echo "server ready gpu=$gpu port=$port pid=$pid"
}

prepare_queue() {
  local shard base
  while read -r shard; do
    base="$(basename "$shard")"
    [[ -f "$LOG_ROOT/queue/done/$base.job" ]] && continue
    printf 'SHARD=%q\n' "$shard" >"$LOG_ROOT/queue/pending/$base.job"
  done < <(find "$DATA_ROOT/requests/shards" -maxdepth 1 -type f -name 'part-*.jsonl' | sort)
}

claim() {
  local gpu="$1" job base destination
  while IFS= read -r -d '' job; do
    base="$(basename "$job")"
    destination="$LOG_ROOT/queue/running/gpu${gpu}__${base}"
    if mv "$job" "$destination" 2>/dev/null; then
      printf '%s\n' "$destination"
      return 0
    fi
  done < <(find "$LOG_ROOT/queue/pending" -maxdepth 1 -type f -name '*.job' -print0 | sort -z)
  return 1
}

worker() {
  local gpu="$1" port=$((PORT_BASE + gpu)) claimed shard base generated audit log pass
  while claimed="$(claim "$gpu")"; do
    # shellcheck disable=SC1090
    source "$claimed"
    shard="$SHARD"
    base="$(basename "$shard")"
    generated="$DATA_ROOT/generated/$base"
    audit="$DATA_ROOT/audits/$base"
    log="$LOG_ROOT/workers/${base}_gpu${gpu}.log"
    mkdir -p "$DATA_ROOT/generated" "$DATA_ROOT/audits"
    if {
      for pass in 1 2; do
        "$PYTHON" scripts/openstax_sft_model.py --data-root "$DATA_ROOT" generate \
          --input "$shard" --output "$generated" \
          --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL" \
          --concurrency "$CONCURRENCY" --max-tokens 2048
      done
      for pass in 1 2; do
        "$PYTHON" scripts/openstax_sft_model.py --data-root "$DATA_ROOT" audit \
          --input "$generated" --requests "$shard" --output "$audit" \
          --base-url "http://127.0.0.1:${port}/v1" --model "$SERVED_MODEL" \
          --concurrency "$CONCURRENCY" --max-tokens 512
      done
    } >>"$log" 2>&1; then
      mv "$claimed" "$LOG_ROOT/queue/done/$(basename "$claimed")"
    else
      mv "$claimed" "$LOG_ROOT/queue/failed/$(basename "$claimed")"
    fi
  done
}

wait_for_inputs_and_gpus
prepare_queue

for gpu in {0..7}; do
  start_server "$gpu"
done
for gpu in {0..7}; do
  worker "$gpu" >"$LOG_ROOT/workers/worker_gpu${gpu}.log" 2>&1 &
  pid=$!
  echo "$pid" >"$LOG_ROOT/pids/worker_gpu${gpu}.pid"
  started_pids+=("$pid")
  worker_pids+=("$pid")
done
for pid in "${worker_pids[@]}"; do
  wait "$pid"
done

failed="$(find "$LOG_ROOT/queue/failed" -maxdepth 1 -type f -name '*.job' | wc -l)"
if (( failed > 0 )); then
  echo "failed shards: $failed" >&2
  exit 1
fi

"$PYTHON" scripts/openstax_sft_model.py --data-root "$DATA_ROOT" build --target 50000 \
  >"$LOG_ROOT/build.log" 2>&1
echo "OpenStax Mimir SFT pilot complete: $DATA_ROOT/accepted/openstax_mimir_sft.jsonl"
