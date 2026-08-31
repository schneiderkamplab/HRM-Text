#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_ROOT="${ENV_ROOT:-/home/ucloud/miniforge3/envs/hrm}"
WIKI_PID="${WIKI_PID:-161584}"
LOG_ROOT="logs/data_audits/machine_translation_da_uk_repair_20260829"
INPUT_ROOT="data/machine_translation_da_uk_repair/input_shards"
SCORED_ROOT="data/machine_translation_da_uk_repair/scored_shards"
mkdir -p "$LOG_ROOT" "$SCORED_ROOT"

"$ENV_ROOT/bin/python" scripts/repair_machine_translation_da_uk.py prepare
while kill -0 "$WIKI_PID" 2>/dev/null; do
  echo "Waiting for WikiCat recovery PID $WIKI_PID before using GPUs..."
  sleep 60
done

pids=()
for gpu in $(seq 0 7); do
  input=$(printf '%s/part-%05d-of-00008.parquet' "$INPUT_ROOT" "$gpu")
  output=$(printf '%s/part-%05d-of-00008.parquet' "$SCORED_ROOT" "$gpu")
  CUDA_VISIBLE_DEVICES="$gpu" "$ENV_ROOT/bin/python" \
    scripts/repair_machine_translation_da_uk.py score "$input" "$output" \
    > "$LOG_ROOT/gpu${gpu}.log" 2>&1 &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
if [[ "$failed" -ne 0 ]]; then
  echo "At least one DA/UK scoring shard failed; refusing to build." >&2
  exit 1
fi
"$ENV_ROOT/bin/python" scripts/repair_machine_translation_da_uk.py build

stage="data/dfm10_machine_translation_da_uk_repaired_sources"
mkdir -p "$stage"
if [[ ! -e "$stage/machine_translation_da_uk_repaired" ]]; then
  ln -s "$(realpath data/converted_sources/machine_translation_da_uk_repaired)" \
    "$stage/machine_translation_da_uk_repaired"
fi
"$ENV_ROOT/bin/python" scripts/tokenize_chat_template.py "$stage" \
  --tokenizer-path /work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm10_machine_translation_da_uk_repaired \
  --workers 16 \
  --force
