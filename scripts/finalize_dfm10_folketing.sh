#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FILTERED="${FILTERED:-data/dfm10_folketing_transform_sources_audited}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"

if [[ "${WAIT_FOR_FILTER:-0}" == "1" ]]; then
  until [[ -s "$FILTERED/filter_summary.json" ]]; do sleep 30; done
fi
[[ -s "$FILTERED/filter_summary.json" ]] || {
  echo "Folketing accepted tree is incomplete: $FILTERED" >&2
  exit 2
}

"$PYTHON" - "$FILTERED/filter_summary.json" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
datasets = summary.get("datasets", {})
expected = {
    "folketingets-dokumenter-denoising",
    "folketingets-dokumenter-error-correction",
    "folketingets-dokumenter-prefix-continuation",
    "folketingets-dokumenter-span-filling",
}
if datasets.keys() != expected:
    raise SystemExit(f"Folketing filter coverage mismatch: {sorted(datasets)}")
seen = sum(int(row.get("seen", 0)) for row in datasets.values())
kept = sum(int(row.get("kept", 0)) for row in datasets.values())
if seen != 14_586_873 or kept != 13_225_678:
    raise SystemExit(f"Folketing count mismatch: seen={seen:,} kept={kept:,}")
PY

"$PYTHON" scripts/tokenize_chat_template.py \
  "$FILTERED" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_folketing \
  --workers 16 \
  --force

echo "Folketing accepted corpus materialized and tokenized"
