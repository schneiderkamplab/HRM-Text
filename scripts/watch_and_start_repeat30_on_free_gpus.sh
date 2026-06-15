#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
LOG_ROOT="${LOG_ROOT:-$ROOT/logs/sapient_anonymization_repeat30_snatch_$(date +%Y%m%dT%H%M%S)}"
CONCURRENCY_PER_SHARD="${CONCURRENCY_PER_SHARD:-128}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"

mkdir -p "$LOG_ROOT/workers"
cd "$ROOT"

echo "LOG_ROOT=$LOG_ROOT"
echo "[$(date -Is)] watching GPUs for high40 completion and starting repeat30 shards"

is_high40_running() {
  local shard="$1"
  pgrep -f "synthesize_anonymized_sapient_exclusions.py .*--source-priority high40 .*--shard-index ${shard}( |$)" >/dev/null
}

is_repeat30_running() {
  local shard="$1"
  pgrep -f "synthesize_anonymized_sapient_exclusions.py .*--source-priority repeat30 .*--shard-index ${shard}( |$)" >/dev/null
}

start_repeat30() {
  local gpu="$1"
  local port="$2"
  local log="$LOG_ROOT/workers/gpu${gpu}_repeat30_shard${gpu}of8.log"
  if is_repeat30_running "$gpu"; then
    echo "[$(date -Is)] repeat30 shard $gpu already running"
    return
  fi
  if ! curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
    echo "[$(date -Is)] port $port is not ready for GPU $gpu; skipping for now"
    return
  fi
  env PYTHONUNBUFFERED=1 CUDA_VISIBLE_DEVICES="$gpu" \
    python scripts/synthesize_anonymized_sapient_exclusions.py \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --num-shards 8 \
      --shard-index "$gpu" \
      --max-attempts "$MAX_ATTEMPTS" \
      --source-priority repeat30 \
      --concurrency "$CONCURRENCY_PER_SHARD" \
      > "$log" 2>&1 &
  echo "[$(date -Is)] started repeat30 gpu=$gpu shard=$gpu/8 port=$port pid=$! log=$log"
}

started=()
for _ in 0 1 2 3 4 5 6 7; do
  started+=("0")
done

while true; do
  all_started=1
  for gpu in 0 1 2 3 4 5 6 7; do
    if [[ "${started[$gpu]}" == "1" ]] || is_repeat30_running "$gpu"; then
      started[$gpu]="1"
      continue
    fi
    all_started=0
    if ! is_high40_running "$gpu"; then
      start_repeat30 "$gpu" "$((8900 + gpu))"
      if is_repeat30_running "$gpu"; then
        started[$gpu]="1"
      fi
    fi
  done
  if [[ "$all_started" == "1" ]]; then
    echo "[$(date -Is)] all repeat30 shards are running or have been started"
    break
  fi
  sleep 15
done

wait
