#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
MODEL="${MODEL:-/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52}"
SAMPLE_ROOT="${SAMPLE_ROOT:-data/dfm11_folketing_error_correction/audit_sample/folketingets-dokumenter-error-correction}"
RUN_ROOT="${RUN_ROOT:-logs/dfm11_folketing_error_correction}"
CONCURRENCY_PER_ENDPOINT="${CONCURRENCY_PER_ENDPOINT:-64}"
PORT_BASE="${PORT_BASE:-8100}"

mkdir -p "$RUN_ROOT/workers"
pids=()
for partition in 0 1 2 3; do
  port=$((PORT_BASE + partition))
  curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null
  worker_root="$RUN_ROOT/workers/partition_${partition}"
  mkdir -p "$worker_root"
  "$PYTHON" scripts/prepare_dfm11_folketing_error_correction.py audit \
    --input "$SAMPLE_ROOT" \
    --output "$worker_root/audit.jsonl" \
    --base-url "http://127.0.0.1:${port}/v1" \
    --model "$MODEL" \
    --partitions 4 \
    --partition-index "$partition" \
    --concurrency "$CONCURRENCY_PER_ENDPOINT" \
    --retries 4 \
    --timeout 300 \
    --force \
    >"$worker_root/worker.log" 2>&1 &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=1
  fi
done
if (( failed )); then
  echo "At least one audit partition failed; production gate not run." >&2
  exit 1
fi

gate_args=()
for partition in 0 1 2 3; do
  gate_args+=(--audit "$RUN_ROOT/workers/partition_${partition}/audit.jsonl")
done
"$PYTHON" scripts/prepare_dfm11_folketing_error_correction.py gate \
  "${gate_args[@]}" \
  --expected-rows 5000 \
  --minimum-keep-rate 0.90 \
  --output "$RUN_ROOT/production_gate.json"
