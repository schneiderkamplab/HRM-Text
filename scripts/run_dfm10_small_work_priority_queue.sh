#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_ROOT="${LOG_ROOT:-$ROOT/logs/dfm10_small_work_priority_$(date +%Y%m%dT%H%M%S)}"
MAX_STAGE_ATTEMPTS="${MAX_STAGE_ATTEMPTS:-3}"
mkdir -p "$LOG_ROOT"
exec 9>"$ROOT/data/.dfm10-small-work-priority.lock"
flock -n 9 || { echo "Another DFM10 small-work priority queue is active" >&2; exit 2; }
exec > >(tee -a "$LOG_ROOT/runner.log") 2>&1
printf '%s\n' "$LOG_ROOT" > "$ROOT/data/.dfm10-small-work-priority-log-root"

echo "$(date -Is) priority queue ready; stage runners gate on campaign locks and GPU availability"

run_stage() {
  local name="$1"
  shift
  local attempt
  for attempt in $(seq 1 "$MAX_STAGE_ATTEMPTS"); do
    echo "$(date -Is) START $name attempt $attempt/$MAX_STAGE_ATTEMPTS"
    if "$@"; then
      echo "$(date -Is) DONE $name"
      return 0
    fi
    echo "$(date -Is) FAILED $name attempt $attempt/$MAX_STAGE_ATTEMPTS" >&2
    sleep 30
  done
  echo "$(date -Is) EXHAUSTED $name; continuing with the next stage" >&2
  return 1
}

failed=0
run_stage persona_doms env LOG_ROOT="$LOG_ROOT/persona_doms" \
  bash scripts/run_dfm10_persona_doms_chats_8gpu.sh || failed=1
run_stage danish_lexical env LOG_ROOT="$LOG_ROOT/danish_lexical" \
  bash scripts/run_dfm10_danish_lexical_natural_8gpu.sh || failed=1
run_stage answer_contract env RUN_ROOT="$LOG_ROOT/answer_contract" \
  bash scripts/run_mimir_answer_contract_audit_when_free.sh || failed=1

echo "$(date -Is) priority queue complete failed=$failed"
exit "$failed"
