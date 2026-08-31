#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
SOURCE_ROOT="${SOURCE_ROOT:-data/opus_da_en_quality/source_shards}"
OUTPUT_ROOT="${OUTPUT_ROOT:-data/opus_da_en_quality/scored_shards}"
BATCH_SIZE="${BATCH_SIZE:-256}"
GPUS_CSV="${GPUS:-0,1,2,3,4,5,6,7}"
mkdir -p "$OUTPUT_ROOT" logs/data_audits/opus_da_en_filter
IFS=',' read -r -a GPU_IDS <<< "$GPUS_CSV"

mapfile -t SHARDS < <(find "$SOURCE_ROOT" -maxdepth 1 -type f -name 'part-*.parquet' | sort)
if [[ "${#SHARDS[@]}" -eq 0 ]]; then
  echo "No source shards found under $SOURCE_ROOT" >&2
  exit 2
fi

worker() {
  local gpu="$1"
  local ordinal="$2"
  local index
  local child=""
  trap '[[ -z "$child" ]] || kill -TERM "$child" 2>/dev/null || true' INT TERM
  for ((index=ordinal; index<${#SHARDS[@]}; index+=${#GPU_IDS[@]})); do
    local input="${SHARDS[$index]}"
    local output="$OUTPUT_ROOT/$(basename "$input")"
    if [[ -s "$output" ]]; then
      continue
    fi
    CUDA_VISIBLE_DEVICES="$gpu" "$PYTHON" scripts/filter_opus_da_en.py \
      "$input" --output "$output" \
      --device cuda --batch-size "$BATCH_SIZE" \
      > "logs/data_audits/opus_da_en_filter/gpu${gpu}_part${index}.log" 2>&1 &
    child="$!"
    wait "$child"
    child=""
  done
}

pids=()
for ordinal in "${!GPU_IDS[@]}"; do
  gpu="${GPU_IDS[$ordinal]}"
  worker "$gpu" "$ordinal" &
  pids+=("$!")
done
trap 'kill "${pids[@]}" 2>/dev/null || true' INT TERM
status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
exit "$status"
