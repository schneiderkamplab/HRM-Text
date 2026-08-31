#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
WORK="${WORK:-$ROOT/data/dfm10_model_charter_da_work}"
MODEL="${MODEL:-google/gemma-4-31B-it-fresh-20260604}"
PORT_BASE="${PORT_BASE:-9500}"
CONCURRENCY="${CONCURRENCY:-64}"
LOG_ROOT="${LOG_ROOT:-$(cat "$WORK/current_log_root")}"

"$PYTHON" scripts/prepare_dfm10_model_charter_da.py --work "$WORK" prepare --shards 8
mkdir -p "$WORK/translations" "$WORK/audits" "$LOG_ROOT/workers"

worker() {
  local gpu="$1" name base_url
  name="part-$(printf '%02d' "$gpu")-of-08.jsonl"
  base_url="http://127.0.0.1:$((PORT_BASE + gpu))/v1"
  for pass in $(seq 1 4); do
    echo "$(date -Is) pass=$pass translate"
    "$PYTHON" scripts/prepare_dfm10_model_charter_da.py --work "$WORK" translate \
      --input "$WORK/requests/$name" --output "$WORK/translations/$name" \
      --audit-output "$WORK/audits/$name" --base-url "$base_url" --model "$MODEL" \
      --concurrency "$CONCURRENCY" --max-tokens 4096 --timeout 900 --retries 3
    echo "$(date -Is) pass=$pass audit"
    "$PYTHON" scripts/prepare_dfm10_model_charter_da.py --work "$WORK" audit \
      --requests "$WORK/requests/$name" --input "$WORK/translations/$name" \
      --output "$WORK/audits/$name" --base-url "$base_url" --model "$MODEL" \
      --concurrency "$CONCURRENCY" --max-tokens 768 --timeout 900 --retries 3 --min-score 4
  done
}

pids=()
for gpu in $(seq 0 7); do
  worker "$gpu" >"$LOG_ROOT/workers/gpu${gpu}.log" 2>&1 &
  pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
"$PYTHON" scripts/prepare_dfm10_model_charter_da.py --work "$WORK" build
