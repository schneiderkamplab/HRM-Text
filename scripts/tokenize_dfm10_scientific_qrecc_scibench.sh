#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER="${TOKENIZER:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
TEMPLATE="${TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
WORKERS="${WORKERS:-16}"

for specification in \
  "data/dfm10_sapient_qrecc_ii_repaired_sources:data/tokenized_dfm10_qrecc_ii_repaired" \
  "data/dfm10_sapient_scibench_repaired_sources:data/tokenized_dfm10_scibench_repaired" \
  "data/dfm10_scientific_summaries_repaired_sources:data/tokenized_dfm10_scientific_summaries_repaired"; do
  IFS=: read -r source output <<< "$specification"
  "$PYTHON" scripts/tokenize_chat_template.py "$source" \
    --tokenizer-path "$TOKENIZER" \
    --chat-template "$TEMPLATE" \
    --output-dir "$output" \
    --workers "$WORKERS" \
    --force
done
