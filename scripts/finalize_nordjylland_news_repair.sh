#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FULL_AUDIT_DIR="${FULL_AUDIT_DIR:-logs/data_audits/nordjylland_news_repaired_31b_full_20260828}"
FULL_AUDIT="$FULL_AUDIT_DIR/nordjylland_news_repaired_quality_audit.jsonl"
FULL_SUMMARY="$FULL_AUDIT_DIR/summary.json"
FILTERED="${FILTERED:-data/converted_sources/nordjylland_news_repaired_grounded}"
FINAL_AUDIT_DIR="${FINAL_AUDIT_DIR:-logs/data_audits/nordjylland_news_repaired_31b_filtered_20260828}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"

if [[ "${WAIT_FOR_AUDIT:-0}" == "1" ]]; then
  until [[ -s "$FULL_AUDIT" && -s "$FULL_SUMMARY" ]]; do sleep 30; done
fi
[[ -s "$FULL_AUDIT" && -s "$FULL_SUMMARY" ]] || {
  echo "Full NordjyllandNews audit is incomplete: $FULL_AUDIT_DIR" >&2
  exit 2
}

python - "$FULL_SUMMARY" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
if summary.get("counts", {}).get("audited") != 73_097:
    raise SystemExit(f"expected 73,097 audited rows, got {summary.get('counts')}")
PY

python scripts/filter_repaired_nordjylland_news.py \
  --audit "$FULL_AUDIT" --output-dir "$FILTERED" --force

python scripts/audit_repaired_nordjylland_news.py prepare \
  --input-dir "$FILTERED" --audit-dir "$FINAL_AUDIT_DIR" \
  --samples 800 --partitions 8
AUDIT_DIR="$FINAL_AUDIT_DIR" scripts/run_nordjylland_news_audit_8gpu.sh

python - "$FINAL_AUDIT_DIR/summary.json" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
counts = summary.get("counts", {})
audited = counts.get("audited", 0)
strict = counts.get("strict_accepted", 0)
if audited != 800 or strict / audited < 0.90:
    raise SystemExit(f"post-filter quality gate failed: {strict}/{audited}")
PY

STAGE="data/dfm10_nordjylland_news_repaired_sources"
rm -rf "$STAGE"
mkdir -p "$STAGE/nordjylland_news_repaired"
ln -s "$(realpath "$FILTERED/train.parquet")" \
  "$STAGE/nordjylland_news_repaired/train.parquet"
python scripts/tokenize_chat_template.py \
  "$STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_nordjylland_news_repaired \
  --workers 16 \
  --force

echo "NordjyllandNews repair filtered, validated, and tokenized"
