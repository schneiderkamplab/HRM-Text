#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
MODEL="${MODEL:-/work/mimir/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52}"
INPUT_ROOT="${INPUT_ROOT:-exports_dfm11/dfm11-folketingets-dokumenter-error-correction-repaired}"
OUTPUT_ROOT="${OUTPUT_ROOT:-exports_dfm11/dfm11-folketingets-dokumenter-error-correction}"
RUN_ROOT="${RUN_ROOT:-logs/dfm11_folketing_error_correction/full_audit}"
EXPECTED_ROWS="${EXPECTED_ROWS:-2548956}"
CONCURRENCY_PER_ENDPOINT="${CONCURRENCY_PER_ENDPOINT:-64}"
PORT_BASE="${PORT_BASE:-8100}"
PARTITION_ATTEMPTS="${PARTITION_ATTEMPTS:-6}"
FINALIZE_ON_COMPLETE="${FINALIZE_ON_COMPLETE:-0}"

mkdir -p "$RUN_ROOT/workers"
audit_partition() {
  local partition="$1"
  local port="$2"
  local worker_root="$RUN_ROOT/workers/partition_${partition}"
  local attempt
  for ((attempt = 1; attempt <= PARTITION_ATTEMPTS; attempt++)); do
    echo "partition=${partition} process_attempt=${attempt}/${PARTITION_ATTEMPTS}"
    if "$PYTHON" scripts/prepare_dfm11_folketing_error_correction.py audit \
      --input "$INPUT_ROOT" \
      --output "$worker_root/audit.jsonl" \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$MODEL" \
      --partitions 4 \
      --partition-index "$partition" \
      --concurrency "$CONCURRENCY_PER_ENDPOINT" \
      --retries 4 \
      --timeout 300 \
      --resume; then
      return 0
    fi
    sleep "$((attempt * 5))"
  done
  return 1
}

pids=()
for partition in 0 1 2 3; do
  port=$((PORT_BASE + partition))
  curl -fsS "http://127.0.0.1:${port}/v1/models" >/dev/null
  worker_root="$RUN_ROOT/workers/partition_${partition}"
  mkdir -p "$worker_root"
  audit_partition "$partition" "$port" \
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
  echo "At least one audit partition failed; finalization not run." >&2
  exit 1
fi

if [[ "$FINALIZE_ON_COMPLETE" != "1" ]]; then
  echo "Full audit complete. Finalization is disabled; decisions were not materialized or tokenized."
  exit 0
fi

audit_args=()
for partition in 0 1 2 3; do
  audit_args+=(--audit "$RUN_ROOT/workers/partition_${partition}/audit.jsonl")
done
"$PYTHON" scripts/prepare_dfm11_folketing_error_correction.py finalize \
  --input "$INPUT_ROOT" \
  --output "$OUTPUT_ROOT" \
  "${audit_args[@]}" \
  --expected-rows "$EXPECTED_ROWS" \
  --workers 13 \
  --force \
  >"$RUN_ROOT/finalize.log" 2>&1
