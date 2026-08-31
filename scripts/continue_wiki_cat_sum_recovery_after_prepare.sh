#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PREPARE_PID_FILE="${PREPARE_PID_FILE:-logs/data_audits/wiki_cat_sum_recovery_31b_20260829/prepare.pid}"
SUMMARY="${SUMMARY:-data/wiki_cat_sum_recovery/requests.summary.json}"
POLL_SECONDS="${POLL_SECONDS:-20}"

prepare_pid="$(cat "$PREPARE_PID_FILE")"
while kill -0 "$prepare_pid" 2>/dev/null; do
  sleep "$POLL_SECONDS"
done

python - "$SUMMARY" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if summary["requests"] != 60_000:
    raise SystemExit(f"unexpected WikiCatSum recovery request inventory: {summary}")
print(json.dumps(summary, indent=2))
PY

exec scripts/run_wiki_cat_sum_recovery_when_free.sh
