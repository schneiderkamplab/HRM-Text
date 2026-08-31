#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
LOG_ROOT="${LOG_ROOT:-logs/data_prep/mimir_grounded_500k/source_workers_$(date +%Y%m%dT%H%M%S)}"
SPOOL_DIR="${SPOOL_DIR:-data/mimir_grounded_500k/source_passage_spool}"
mkdir -p "$LOG_ROOT"

sources=(arxiv openlogic openstax_cc_by pubmed regulations stackexchange usgpo wikimedia)
pids=()
for source in "${sources[@]}"; do
  "$PYTHON" scripts/prepare_mimir_grounding_passages.py \
    --only-source "$source" --spool-dir "$SPOOL_DIR" \
    >"$LOG_ROOT/${source}.log" 2>&1 &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
(( failed == 0 )) || { echo "At least one source worker failed; inspect $LOG_ROOT" >&2; exit 1; }

"$PYTHON" scripts/prepare_mimir_grounding_passages.py \
  --merge-spools --spool-dir "$SPOOL_DIR" \
  >"$LOG_ROOT/merge.log" 2>&1
echo "Mimir grounding passages complete; logs: $LOG_ROOT"
