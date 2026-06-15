#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
TASK_FILE="${TASK_FILE:-$ROOT/logs/data_audits/high40_parquet_sources_to_rerun_after_rowid_fix.txt}"
STAMP="${STAMP:-$(date +%Y%m%dT%H%M%S)}"
LOG="$ROOT/logs/sapient_anonymization_clean_reruns_${STAMP}.log"

cd "$ROOT"
mkdir -p "$ROOT/logs"

log() {
  echo "[$(date -Is)] $*" | tee -a "$LOG"
}

slugify_py='
import re, sys
for value in sys.stdin:
    value = value.strip()
    if not value:
        continue
    value = value.replace("/", "__")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    print(value[:220])
'

quarantine_tasks() {
  local task_file="$1"
  local label="$2"
  local stamp="$3"
  while IFS= read -r task; do
    [[ -z "$task" ]] && continue
    slug="$(printf '%s\n' "$task" | python -c "$slugify_py")"
    dir="$ROOT/synth/$slug"
    if [[ -d "$dir" ]]; then
      dest="$dir/quarantine_${label}_${stamp}"
      mkdir -p "$dest"
      for path in "$dir"/data "$dir"/rejected "$dir"/summary.shard*.json "$dir"/summary.json; do
        [[ -e "$path" ]] || continue
        mv "$path" "$dest"/
      done
      log "quarantined $task -> $dest"
    fi
  done < "$task_file"
}

log "waiting for currently running repeat30 workers to finish"
while pgrep -f "synthesize_anonymized_sapient_exclusions.py .*--source-priority repeat30" >/dev/null; do
  sleep 60
  log "still waiting for repeat30 workers"
done

log "current repeat30 workers finished; waiting for old vLLM launchers to clean up"
while pgrep -f "run_high40_then_repeat30_remaining_gpus.sh|run_sapient_repeat30_opportunistic_gpus34.sh" >/dev/null; do
  sleep 10
done
while pgrep -f "vllm.entrypoints.openai.api_server .*--port 89[01][0-9]" >/dev/null; do
  sleep 10
done

log "quarantining pre-fix/partial repeat30 outputs"
repeat_file="$ROOT/logs/data_audits/repeat30_sources.txt"
python - <<'PY' > "$repeat_file"
import importlib.util
from pathlib import Path
root = Path("/work/dfm/HRM-Text")
spec = importlib.util.spec_from_file_location("syn", root / "scripts/synthesize_anonymized_sapient_exclusions.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for task in mod.REPEAT30_PRIORITY_TASKS:
    print(task)
PY
quarantine_tasks "$repeat_file" "prefixed_repeat30" "$STAMP"

log "rerunning repeat30 clean with fixed global Parquet row IDs"
SOURCE_PRIORITY=repeat30 \
CONCURRENCY_PER_SHARD=128 \
MAX_NUM_SEQS=128 \
LOG_ROOT="$ROOT/logs/sapient_anonymization_repeat30_clean_${STAMP}" \
scripts/run_sapient_priority_8gpu.sh 2>&1 | tee -a "$LOG"

log "validating repeat30 clean output"
python scripts/validate_sapient_synth_outputs.py --source-priority repeat30 2>&1 | tee -a "$LOG"

log "quarantining affected high40 Parquet source outputs"
quarantine_tasks "$TASK_FILE" "prefixed_high40_rowid_bug" "$STAMP"

log "rerunning affected high40 Parquet sources clean"
SOURCE_PRIORITY=high40 \
TASK_FILE="$TASK_FILE" \
CONCURRENCY_PER_SHARD=128 \
MAX_NUM_SEQS=128 \
LOG_ROOT="$ROOT/logs/sapient_anonymization_high40_affected_clean_${STAMP}" \
scripts/run_sapient_priority_8gpu.sh 2>&1 | tee -a "$LOG"

log "validating affected high40 clean output"
python scripts/validate_sapient_synth_outputs.py --source-priority high40 --task-file "$TASK_FILE" 2>&1 | tee -a "$LOG"

log "clean rerun workflow complete"
