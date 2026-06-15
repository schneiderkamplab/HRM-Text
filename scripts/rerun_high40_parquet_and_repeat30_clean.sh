#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/work/dfm/HRM-Text}"
STAMP="${STAMP:-$(date +%Y%m%dT%H%M%S)}"
LOG="${LOG:-$ROOT/logs/sapient_anonymization_clean_high40_parquet_repeat30_${STAMP}.log}"
HIGH40_PARQUET_TASK_FILE="${HIGH40_PARQUET_TASK_FILE:-$ROOT/logs/data_audits/high40_parquet_sources_all.txt}"
REPEAT30_TASK_FILE="${REPEAT30_TASK_FILE:-$ROOT/logs/data_audits/repeat30_sources.txt}"

cd "$ROOT"
mkdir -p "$ROOT/logs/data_audits" "$(dirname "$LOG")"

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
  while IFS= read -r task; do
    [[ -z "$task" ]] && continue
    slug="$(printf '%s\n' "$task" | python -c "$slugify_py")"
    dir="$ROOT/synth/$slug"
    if [[ -d "$dir" ]]; then
      dest="$dir/quarantine_${label}_${STAMP}"
      mkdir -p "$dest"
      for path in "$dir"/data "$dir"/rejected "$dir"/summary.shard*.json "$dir"/summary.json; do
        [[ -e "$path" ]] || continue
        mv "$path" "$dest"/
      done
      log "quarantined $task -> $dest"
    fi
  done < "$task_file"
}

log "writing task manifests"
python - <<'PY'
import importlib.util
from pathlib import Path

root = Path("/work/dfm/HRM-Text")
spec = importlib.util.spec_from_file_location("syn", root / "scripts/synthesize_anonymized_sapient_exclusions.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
(root / "logs/data_audits/high40_parquet_sources_all.txt").write_text(
    "\n".join(task for task in mod.HIGH_PRIORITY_TASKS if task.endswith(".parquet")) + "\n",
    encoding="utf-8",
)
(root / "logs/data_audits/repeat30_sources.txt").write_text(
    "\n".join(mod.REPEAT30_PRIORITY_TASKS) + "\n",
    encoding="utf-8",
)
PY

log "quarantining all high40 Parquet outputs"
quarantine_tasks "$HIGH40_PARQUET_TASK_FILE" "old_high40_parquet_rowid_bug"

log "quarantining all repeat30 outputs"
quarantine_tasks "$REPEAT30_TASK_FILE" "old_repeat30_rowid_bug"

log "rerunning all high40 Parquet sources clean"
SOURCE_PRIORITY=high40 \
TASK_FILE="$HIGH40_PARQUET_TASK_FILE" \
CONCURRENCY_PER_SHARD=128 \
MAX_NUM_SEQS=128 \
LOG_ROOT="$ROOT/logs/sapient_anonymization_high40_parquet_clean_${STAMP}" \
scripts/run_sapient_priority_8gpu.sh 2>&1 | tee -a "$LOG"

log "validating clean high40 Parquet outputs"
python scripts/validate_sapient_synth_outputs.py --source-priority high40 --task-file "$HIGH40_PARQUET_TASK_FILE" 2>&1 | tee -a "$LOG"

log "rerunning repeat30 clean"
SOURCE_PRIORITY=repeat30 \
TASK_FILE="$REPEAT30_TASK_FILE" \
CONCURRENCY_PER_SHARD=128 \
MAX_NUM_SEQS=128 \
LOG_ROOT="$ROOT/logs/sapient_anonymization_repeat30_clean_${STAMP}" \
scripts/run_sapient_priority_8gpu.sh 2>&1 | tee -a "$LOG"

log "validating clean repeat30 outputs"
python scripts/validate_sapient_synth_outputs.py --source-priority repeat30 --task-file "$REPEAT30_TASK_FILE" 2>&1 | tee -a "$LOG"

log "clean high40 Parquet + repeat30 rerun complete"
