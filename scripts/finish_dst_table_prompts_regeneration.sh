#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
REGENERATED="data/converted_sources/dst_table_prompts_regenerated"
AUDIT_DIR="logs/data_audits/dst_table_prompts_regenerated_20260829"

until [[ -s "$REGENERATED/train.parquet" && -s "$REGENERATED/regeneration_summary.json" ]]; do
  sleep 30
done

if [[ ! -s "$AUDIT_DIR/inventory.json" ]]; then
  "$PYTHON" scripts/audit_repaired_dst_table_prompts.py prepare \
    --input-dir "$REGENERATED" --audit-dir "$AUDIT_DIR" \
    --samples 0 --partitions 8
fi

AUDIT_DIR="$AUDIT_DIR" PORT_BASE=8800 \
  bash scripts/run_dst_table_prompts_audit_when_free.sh

INPUT_DIR="$REGENERATED" AUDIT_DIR="$AUDIT_DIR" \
  FILTERED="data/converted_sources/dst_table_prompts_repaired_grounded" \
  bash scripts/finalize_dst_table_prompts_repair.sh

echo "DST regeneration, independent full audit, filter, and tokenization complete"
