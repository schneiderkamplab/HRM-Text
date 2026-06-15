#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
LOG="${LOG:-$ROOT/logs/sapient_anonymization_repeat30_after_high40.log}"

cd "$ROOT"
mkdir -p "$(dirname "$LOG")"

echo "[$(date -Is)] waiting for high40 workers to finish" | tee -a "$LOG"
while pgrep -f "synthesize_anonymized_sapient_exclusions.py .*--source-priority high40" >/dev/null; do
  sleep 60
  echo "[$(date -Is)] still waiting for high40 workers" >> "$LOG"
done

echo "[$(date -Is)] high40 workers gone; waiting for ports 8900-8907 vLLM servers to exit" | tee -a "$LOG"
while pgrep -f "vllm.entrypoints.openai.api_server .*--port 890[0-7]" >/dev/null; do
  sleep 10
done

echo "[$(date -Is)] waiting for opportunistic repeat30 workers/servers to exit" | tee -a "$LOG"
while pgrep -f "synthesize_anonymized_sapient_exclusions.py .*--source-priority repeat30" >/dev/null \
  || pgrep -f "vllm.entrypoints.openai.api_server .*--port 891[34]" >/dev/null; do
  sleep 30
done

echo "[$(date -Is)] launching repeat30" | tee -a "$LOG"
SOURCE_PRIORITY=repeat30 \
CONCURRENCY_PER_SHARD=128 \
MAX_NUM_SEQS=128 \
scripts/run_sapient_anonymization_vllm_8gpu.sh 2>&1 | tee -a "$LOG"
