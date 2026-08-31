#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PILOT_AUDIT="${PILOT_AUDIT:-logs/data_audits/wiki_cat_sum_repaired_pilot_v2_20260828}"
FULL_AUDIT="${FULL_AUDIT:-logs/data_audits/wiki_cat_sum_repaired_20260828}"
CANDIDATES="${CANDIDATES:-data/converted_sources/wiki_cat_sum_grounded_candidates}"
REPAIRED="${REPAIRED:-data/converted_sources/wiki_cat_sum_repaired}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
TOKENIZER_WORKERS="${TOKENIZER_WORKERS:-16}"
POLL_SECONDS="${POLL_SECONDS:-30}"

mkdir -p "$FULL_AUDIT"
exec 9>"$FULL_AUDIT/finalize.lock"
if ! flock -n 9; then
  echo "Another WikiCatSum finalizer holds $FULL_AUDIT/finalize.lock" >&2
  exit 1
fi

echo "Waiting for the version-2 WikiCatSum pilot..."
until [[ -f "$PILOT_AUDIT/summary.json" ]]; do
  sleep "$POLL_SECONDS"
done
python - "$PILOT_AUDIT/summary.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
summary = json.loads(path.read_text(encoding="utf-8"))
if int(summary.get("rows", -1)) != 300:
    raise SystemExit(f"pilot row-count mismatch: {summary.get('rows')} != 300")
rate = float(summary.get("strict_usable_rate", 0.0))
if rate < 0.80:
    raise SystemExit(f"pilot strict audit gate failed: {rate:.4%} < 80%")
print(f"Pilot passed: {summary['strict_usable']}/300 strict usable ({rate:.2%})")
PY

echo "Running the full 14,479-row WikiCatSum audit..."
AUDIT_DIR="$FULL_AUDIT" \
PORT_BASE="${PORT_BASE:-8740}" \
WAIT_FOR_ALL_GPUS_IDLE_SECONDS="${WAIT_FOR_ALL_GPUS_IDLE_SECONDS:-30}" \
scripts/run_repaired_wiki_cat_sum_audit_8gpu.sh

echo "Filtering strict full-audit passes..."
python scripts/audit_repaired_wiki_cat_sum.py filter \
  --input-dir "$CANDIDATES" \
  --audit-dir "$FULL_AUDIT" \
  --output-dir "$REPAIRED"

echo "Tokenizing the repaired WikiCatSum corpus..."
STAGE="data/dfm10_wiki_cat_sum_repaired_sources"
rm -rf "$STAGE"
mkdir -p "$STAGE"
ln -s "$(realpath "$REPAIRED")" "$STAGE/wiki_cat_sum_repaired"
python scripts/tokenize_chat_template.py \
  "$STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_wiki_cat_sum_repaired \
  --workers "$TOKENIZER_WORKERS" \
  --force
echo "WikiCatSum repair finalized and tokenized."
