#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
WAIT_PID="${WAIT_PID:-3166244}"
WAIT_FOR_PERSONA="${WAIT_FOR_PERSONA:-0}"
LOG="${LOG:-$ROOT/logs/dfm10_completed_integration.log}"
exec > >(tee -a "$LOG") 2>&1

echo "$(date -Is) waiting for prerequisite union worker PID $WAIT_PID"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done

if [[ "$WAIT_FOR_PERSONA" == "1" ]]; then
  echo "$(date -Is) waiting for completed persona tokenization and package validation"
  while [[ ! -s data/tokenized_dfm10_danish_persona_chats/completion.json || \
           ! -s exports_dfm10/dfm10-danish-persona-chats/metadata/validation.json ]]; do
    sleep 30
  done
fi

echo "$(date -Is) rebuilding DFM10 union with all currently completed sources"
flock data/.dfm10-union.lock "$PYTHON" scripts/build_tokenized_dfm10_tree.py --force

export WAIT_FOR_PERSONA
"$PYTHON" - <<'PY'
import json
import os
from pathlib import Path

manifest = json.loads(Path("data/tokenized_dfm10/union_manifest.json").read_text())
counts = manifest["task_counts"]
if counts.get("domsdatabasen_grounded_chats") != 1:
    raise SystemExit(f"Doms integration failed: {counts.get('domsdatabasen_grounded_chats')}")
print("Validated Domsdatabasen integration into canonical DFM10 union")
if counts.get("danish_lexical_sft") != 4:
    raise SystemExit(f"Danish lexical integration failed: {counts.get('danish_lexical_sft')}")
print("Validated four Danish lexical tasks in canonical DFM10 union")
if os.environ["WAIT_FOR_PERSONA"] == "1":
    if counts.get("danish_persona_chats") != 1:
        raise SystemExit(f"Persona integration failed: {counts.get('danish_persona_chats')}")
    print("Validated persona-chat integration into canonical DFM10 union")
PY

echo "$(date -Is) completed-source integration finished"
