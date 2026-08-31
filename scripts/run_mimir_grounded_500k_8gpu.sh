#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/mimir_grounded_500k_sft}"
MODEL_PATH="${MODEL_PATH:-$ROOT/data/models/google/gemma-4-31B-it-fresh-20260604}"
MODEL_NAME="${MODEL_NAME:-mimir-grounded-500k-gemma4-31b}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
SHARDS="${SHARDS:-640}"
EXPECTED_CANDIDATES="${EXPECTED_CANDIDATES:-650000}"
CONCURRENCY="${CONCURRENCY:-64}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}"
FREE_THRESHOLD_MIB="${FREE_THRESHOLD_MIB:-3000}"
PORT_BASE="${PORT_BASE:-8800}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/mimir_grounded_500k_$(date +%Y%m%dT%H%M%S)}"
LOCK_FILE="$DATA_ROOT/campaign.lock"

mkdir -p "$DATA_ROOT" "$LOG_ROOT"/{servers,workers,pids,cache,queue/{pending,running,done,failed}}
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Another Mimir 500k runner holds $LOCK_FILE"; exit 1; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$DATA_ROOT/current_run_log_root.txt"

server_pids=()
worker_pids=()
cleanup() {
  for pid in "${worker_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${server_pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "${server_pids[@]:-}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

requests_ready() {
  [[ -s "$DATA_ROOT/requests/summary.json" ]] || return 1
  [[ "$(find "$DATA_ROOT/requests/shards" -maxdepth 1 -name 'part-*.jsonl' | wc -l)" -eq "$SHARDS" ]] || return 1
  [[ "$(jq -r '.total_candidates' "$DATA_ROOT/requests/summary.json")" -eq "$EXPECTED_CANDIDATES" ]]
}

all_gpus_free() {
  local values
  mapfile -t values < <(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  [[ "${#values[@]}" -eq 8 ]] || return 1
  for value in "${values[@]}"; do (( value <= FREE_THRESHOLD_MIB )) || return 1; done
}

echo "$(date -Is) waiting for the complete ${EXPECTED_CANDIDATES}-candidate request manifest"
until requests_ready; do sleep 30; done
echo "$(date -Is) waiting for all GPUs below ${FREE_THRESHOLD_MIB} MiB used"
until all_gpus_free; do sleep 30; done

for shard in "$DATA_ROOT"/requests/shards/part-*.jsonl; do
  base="$(basename "$shard")"
  marker="$DATA_ROOT/state/done/${base}.done"
  [[ -f "$marker" ]] && continue
  printf 'SHARD=%q\n' "$shard" > "$LOG_ROOT/queue/pending/${base}.job"
done
mkdir -p "$DATA_ROOT"/{generated,audits,state/done}

wait_server() {
  local port="$1" pid="$2" deadline=$((SECONDS + 1200))
  until curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; do
    kill -0 "$pid" 2>/dev/null || return 1
    (( SECONDS < deadline )) || return 1
    sleep 2
  done
}

for gpu in $(seq 0 7); do
  port=$((PORT_BASE + gpu))
  cache="$LOG_ROOT/cache/gpu${gpu}"
  mkdir -p "$cache"
  CUDA_VISIBLE_DEVICES="$gpu" \
  CUDA_HOME="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}" \
  PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/bin:/home/ucloud/miniforge3/envs/audit/bin:${PATH}" \
  LD_LIBRARY_PATH="${CUDA_HOME:-/home/ucloud/miniforge3/envs/audit}/lib:${LD_LIBRARY_PATH:-}" \
  VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1 \
  TORCHINDUCTOR_CACHE_DIR="$cache/torchinductor" TRITON_CACHE_DIR="$cache/triton" \
  setsid "$PYTHON" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" --served-model-name "$MODEL_NAME" \
    --hf-overrides '{"architectures":["Gemma4ForCausalLM"]}' \
    --chat-template "$ROOT/data_io/chat_templates/gemma4_native_chat.jinja" \
    --host 127.0.0.1 --port "$port" --tensor-parallel-size 1 \
    --max-model-len "$MAX_MODEL_LEN" --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
    --max-num-seqs "$MAX_NUM_SEQS" --enforce-eager \
    >"$LOG_ROOT/servers/gpu${gpu}.log" 2>&1 &
  server_pids+=("$!")
  echo "$!" > "$LOG_ROOT/pids/server_gpu${gpu}.pid"
done
for gpu in $(seq 0 7); do
  wait_server "$((PORT_BASE + gpu))" "${server_pids[$gpu]}" || {
    echo "GPU $gpu server failed to become ready" >&2
    exit 1
  }
done

claim() {
  local gpu="$1" job destination
  while IFS= read -r -d '' job; do
    destination="$LOG_ROOT/queue/running/gpu${gpu}__$(basename "$job")"
    if mv "$job" "$destination" 2>/dev/null; then printf '%s\n' "$destination"; return 0; fi
  done < <(find "$LOG_ROOT/queue/pending" -maxdepth 1 -name '*.job' -print0 | sort -z)
  return 1
}

worker() {
  local gpu="$1" port=$((PORT_BASE + gpu)) claimed shard base generated audit log pass
  while claimed="$(claim "$gpu")"; do
    # shellcheck disable=SC1090
    source "$claimed"
    shard="$SHARD"; base="$(basename "$shard")"
    generated="$DATA_ROOT/generated/$base"; audit="$DATA_ROOT/audits/$base"
    log="$LOG_ROOT/workers/${base}_gpu${gpu}.log"
    if {
      for pass in 1 2; do
        "$PYTHON" scripts/mimir_grounded_500k_model.py --data-root "$DATA_ROOT" generate \
          --input "$shard" --output "$generated" --base-url "http://127.0.0.1:${port}/v1" \
          --model "$MODEL_NAME" --concurrency "$CONCURRENCY" --max-tokens 2048
      done
      for pass in 1 2; do
        "$PYTHON" scripts/mimir_grounded_500k_model.py --data-root "$DATA_ROOT" audit \
          --input "$generated" --requests "$shard" --output "$audit" \
          --base-url "http://127.0.0.1:${port}/v1" --model "$MODEL_NAME" \
          --concurrency "$CONCURRENCY" --max-tokens 512
      done
    } >>"$log" 2>&1; then
      printf '%s\n' "$(date -Is)" > "$DATA_ROOT/state/done/${base}.done"
      mv "$claimed" "$LOG_ROOT/queue/done/$(basename "$claimed")"
    else
      mv "$claimed" "$LOG_ROOT/queue/failed/$(basename "$claimed")"
    fi
  done
}

for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/worker_gpu${gpu}.log" 2>&1 &
  worker_pids+=("$!")
done
failed=0
for pid in "${worker_pids[@]}"; do wait "$pid" || failed=1; done
worker_pids=()
(( failed == 0 )) || { echo "At least one worker failed" >&2; exit 1; }

failed_jobs="$(find "$LOG_ROOT/queue/failed" -maxdepth 1 -name '*.job' | wc -l)"
done_markers="$(find "$DATA_ROOT/state/done" -maxdepth 1 -name '*.done' | wc -l)"
echo "Mimir 500k candidate generation/audit finished: done=$done_markers failed=$failed_jobs"
(( failed_jobs == 0 && done_markers == SHARDS )) || exit 1
echo "Final accepted build remains gated on benchmark decontamination and exact 5x100k quotas."
