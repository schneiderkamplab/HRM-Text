#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
RUN_ROOT="${RUN_ROOT:-logs/data_audits/danish_university_portals_bt_repair_20260829}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
STAGE="data/dfm10_university_portals_repaired_sources"

mkdir -p "$RUN_ROOT"
exec 9>"$RUN_ROOT/finisher.lock"
flock -n 9 || { echo "Another university-portals repair finisher is active" >&2; exit 2; }

"$PYTHON" scripts/repair_danish_university_portals_bt.py prepare
RUN_ROOT="$RUN_ROOT" bash scripts/run_danish_university_portals_bt_audit_8gpu.sh
"$PYTHON" scripts/repair_danish_university_portals_bt.py finalize

rm -rf "$STAGE"
mkdir -p "$STAGE"
ln -s "$(realpath data/converted_sources/danish_university_portals_bt_repaired)" \
  "$STAGE/danish_university_portals_bt_repaired"
"$PYTHON" scripts/tokenize_chat_template.py \
  "$STAGE" --tokenizer-path "$TOKENIZER_PATH" --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_university_portals_repaired --workers 1 --force
"$PYTHON" scripts/repair_danish_university_portals_bt.py validate
echo "University-portals replacement passed full-row audit and token reconciliation."
