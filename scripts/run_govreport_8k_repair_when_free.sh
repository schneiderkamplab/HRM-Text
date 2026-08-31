#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
CANDIDATES="${CANDIDATES:-data/converted_sources/govreport_summarization_repaired_8k}"
AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/govreport_summarization_repaired_8k_full_20260829}"
FILTERED="${FILTERED:-data/converted_sources/govreport_summarization_grounded_8k}"
STAGING="${STAGING:-data/dfm10_govreport_repaired_8k_sources}"
TOKENIZED="${TOKENIZED:-data/tokenized_dfm10_govreport_repaired_8k}"

if [[ ! -f "$CANDIDATES/repair_summary.json" ]]; then
  "$PYTHON" scripts/repair_govreport_summarization.py \
    --output-dir "$CANDIDATES" \
    --tokenizer-path "$TOKENIZER_PATH" \
    --chat-template "$CHAT_TEMPLATE" \
    --max-seq-len 8192 \
    --max-response-tokens 2048 \
    --workers 8 \
    --force
fi

if [[ ! -f "$AUDIT_DIR/samples.jsonl" ]]; then
  "$PYTHON" scripts/audit_repaired_govreport.py prepare \
    --input-dir "$CANDIDATES" \
    --audit-dir "$AUDIT_DIR" \
    --samples-per-file 100000 \
    --source-id ccdv/govreport-summarization-repaired-8k \
    --task-name govreport_summarization_repaired_8k \
    --form "complete-report grounded summarization up to 8192 tokens"
fi

AUDIT_DIR="$AUDIT_DIR" \
MAX_MODEL_LEN=16384 \
PORT="${PORT:-8594}" \
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}" \
  scripts/run_repaired_govreport_audit_when_free.sh

"$PYTHON" scripts/filter_repaired_govreport.py \
  --input-dir "$CANDIDATES" \
  --audit "$AUDIT_DIR/results/audit.jsonl" \
  --output-dir "$FILTERED" \
  --force

rm -rf "$STAGING"
mkdir -p "$STAGING/govreport_summarization_repaired_8k"
for source in "$FILTERED"/*.parquet; do
  ln -s "$(realpath "$source")" \
    "$STAGING/govreport_summarization_repaired_8k/$(basename "$source")"
done

"$PYTHON" scripts/tokenize_chat_template.py \
  "$STAGING" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir "$TOKENIZED" \
  --workers 8 \
  --force

echo "GovReport 8K+ repair, exhaustive E4B audit, publication, and tokenization completed."
