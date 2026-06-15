#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GPU_LIST="${GPU_LIST:-0,1,2,3,4,5,6,7}"
BASE_PORT="${BASE_PORT:-8100}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-posttrain-gemma-teacher}"
GEMMA_MODEL_PATH="${GEMMA_MODEL_PATH:-/work/dfm/HRM-Text/data/models/google/gemma-4-31B-it-fresh-20260604}"
PYTHON_BIN="${PYTHON_BIN:-/home/ucloud/miniforge3/envs/hrm/bin/python}"

MISSING_SHARD_ROOT="${MISSING_SHARD_ROOT:-data/synthetic_request_shards_posttrain_transform_refine_v3_missing}"
GENERATED_ROOT="${GENERATED_ROOT:-data/generated_posttrain_transform_refine}"
AUDIT_ROOT="${AUDIT_ROOT:-logs/posttrain_transform_refine_generation/audits_to_1m_$(date +%Y%m%dT%H%M%S)}"
REGEN_REQUEST_ROOT="${REGEN_REQUEST_ROOT:-data/synthetic_requests_posttrain_transform_refine_regen_from_audit}"
REGEN_SHARD_ROOT="${REGEN_SHARD_ROOT:-data/synthetic_request_shards_posttrain_transform_refine_regen_from_audit}"
REGEN_GENERATED_ROOT="${REGEN_GENERATED_ROOT:-data/generated_posttrain_transform_refine_regen_from_audit}"

CLIENT_CONCURRENCY="${CLIENT_CONCURRENCY:-32}"
AUDIT_CONCURRENCY="${AUDIT_CONCURRENCY:-32}"
REQUESTS_PER_SHARD="${REQUESTS_PER_SHARD:-1000}"
MAX_REGEN_ROUNDS="${MAX_REGEN_ROUNDS:-1}"

export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

IFS=',' read -r -a GPUS <<< "$GPU_LIST"

port_for_index() {
  local idx="$1"
  echo $((BASE_PORT + idx))
}

cleanup_servers() {
  local pid_dir="$1"
  for pidfile in "$pid_dir"/vllm_gpu*.pid; do
    [[ -f "$pidfile" ]] || continue
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill -- "-$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
    fi
  done
  sleep 5
  for pidfile in "$pid_dir"/vllm_gpu*.pid; do
    [[ -f "$pidfile" ]] || continue
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL -- "-$pid" 2>/dev/null || true
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
}

echo "Phase 1/4: generate missing 550k judged rows"
env \
  VLLM_PYTHON="$PYTHON_BIN" \
  CLIENT_PYTHON="$PYTHON_BIN" \
  GEMMA_MODEL_PATH="$GEMMA_MODEL_PATH" \
  SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
  GPU_LIST="$GPU_LIST" \
  BASE_PORT="$BASE_PORT" \
  REQUESTS_PER_SHARD="$REQUESTS_PER_SHARD" \
  CLIENT_CONCURRENCY="$CLIENT_CONCURRENCY" \
  GENERATION_ENDPOINT=chat \
  JUDGE_QUALITY=1 \
  JUDGE_RETRIES=2 \
  SHARD_ROOT="$MISSING_SHARD_ROOT" \
  GENERATED_ROOT="$GENERATED_ROOT" \
  LOG_ROOT=logs/posttrain_transform_refine_generation_to_1m_missing \
  STOP_SERVERS_ON_EXIT=0 \
  scripts/run_posttrain_synthetic_generation_vllm.sh

PID_DIR="logs/posttrain_transform_refine_generation_to_1m_missing/pids"
trap 'cleanup_servers "$PID_DIR"' EXIT

echo "Phase 2/4: audit English-source generated rows with the judge"
mkdir -p "$AUDIT_ROOT"
for idx in "${!GPUS[@]}"; do
  gpu="${GPUS[$idx]}"
  port="$(port_for_index "$idx")"
  (
    set -euo pipefail
    gpu_audit_root="$AUDIT_ROOT/gpu${gpu}"
    mkdir -p "$gpu_audit_root"
    "$PYTHON_BIN" scripts/prepare_posttrain_transform_refine.py audit-generated \
      --generated-root "$GENERATED_ROOT" \
      --audit-root "$gpu_audit_root/en_en" \
      --generated-glob "*_en_en__shard_*.gpu${gpu}.jsonl" \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --concurrency "$AUDIT_CONCURRENCY" \
      --force
    "$PYTHON_BIN" scripts/prepare_posttrain_transform_refine.py audit-generated \
      --generated-root "$GENERATED_ROOT" \
      --audit-root "$gpu_audit_root/en_da" \
      --generated-glob "*_en_da__shard_*.gpu${gpu}.jsonl" \
      --base-url "http://127.0.0.1:${port}/v1" \
      --model "$SERVED_MODEL_NAME" \
      --concurrency "$AUDIT_CONCURRENCY" \
      --force
  ) > "$AUDIT_ROOT/gpu${gpu}.log" 2>&1 &
done
wait

echo "Phase 3/4: build regeneration requests from unhappy judge rows"
"$PYTHON_BIN" scripts/prepare_posttrain_transform_refine.py make-regeneration-requests \
  --generated-root "$GENERATED_ROOT" \
  --audit-root "$AUDIT_ROOT" \
  --regen-request-root "$REGEN_REQUEST_ROOT" \
  --force

regen_count="$(find "$REGEN_REQUEST_ROOT" -maxdepth 1 -type f -name 'regen_*.jsonl' -print0 2>/dev/null | xargs -0 -r cat | wc -l)"
echo "regeneration requests: $regen_count"

if [[ "$regen_count" -gt 0 ]]; then
  echo "Phase 4/4: generate judged replacements for unhappy rows"
  "$PYTHON_BIN" scripts/prepare_posttrain_transform_refine.py shard-synthetic-requests \
    --request-root "$REGEN_REQUEST_ROOT" \
    --shard-root "$REGEN_SHARD_ROOT" \
    --requests-per-shard "$REQUESTS_PER_SHARD" \
    --force

  round=1
  while [[ "$round" -le "$MAX_REGEN_ROUNDS" ]]; do
    env \
      VLLM_PYTHON="$PYTHON_BIN" \
      CLIENT_PYTHON="$PYTHON_BIN" \
      GEMMA_MODEL_PATH="$GEMMA_MODEL_PATH" \
      SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
      GPU_LIST="$GPU_LIST" \
      BASE_PORT="$BASE_PORT" \
      REQUESTS_PER_SHARD="$REQUESTS_PER_SHARD" \
      CLIENT_CONCURRENCY="$CLIENT_CONCURRENCY" \
      GENERATION_ENDPOINT=chat \
      JUDGE_QUALITY=1 \
      JUDGE_RETRIES=2 \
      SHARD_ROOT="$REGEN_SHARD_ROOT" \
      GENERATED_ROOT="$REGEN_GENERATED_ROOT" \
      LOG_ROOT="logs/posttrain_transform_refine_generation_to_1m_regen_round${round}" \
      START_SERVERS=0 \
      STOP_SERVERS_ON_EXIT=0 \
      scripts/run_posttrain_synthetic_generation_vllm.sh
    round=$((round + 1))
  done
else
  echo "Phase 4/4: no judged failures found; no regeneration needed"
fi

echo "Done. Generated missing rows: $GENERATED_ROOT"
echo "Audit root: $AUDIT_ROOT"
echo "Regeneration requests: $REGEN_REQUEST_ROOT"
echo "Regenerated rows: $REGEN_GENERATED_ROOT"
