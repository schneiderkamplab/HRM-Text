#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATA_ROOT="${DATA_ROOT:-$ROOT/data/mimir_grounded_500k_sft}"
TOPUP_ROOT="${TOPUP_ROOT:-$DATA_ROOT/technical_topup_100k}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
EXPECTED_SHARDS="${EXPECTED_SHARDS:-640}"
EXPECTED_TOPUP_SHARDS="${EXPECTED_TOPUP_SHARDS:-128}"
LOG="${LOG:-$ROOT/logs/mimir_grounded_500k_finalize_$(date +%Y%m%dT%H%M%S).log}"
LOCK="$DATA_ROOT/finalize.lock"

mkdir -p "$DATA_ROOT" "$(dirname "$LOG")"
exec 9>"$LOCK"
flock -n 9 || { echo "Another Mimir 500k finalizer holds $LOCK"; exit 1; }
exec > >(tee -a "$LOG") 2>&1

echo "$(date -Is) waiting for $EXPECTED_SHARDS completed generation/audit shards"
while true; do
  completed="$(find "$DATA_ROOT/state/done" -maxdepth 1 -name '*.done' 2>/dev/null | wc -l)"
  (( completed == EXPECTED_SHARDS )) && break
  echo "$(date -Is) completed=$completed/$EXPECTED_SHARDS"
  sleep 60
done

echo "$(date -Is) waiting for $EXPECTED_TOPUP_SHARDS completed Technical/STEM top-up shards"
while true; do
  completed="$(find "$TOPUP_ROOT/state/done" -maxdepth 1 -name '*.done' 2>/dev/null | wc -l)"
  (( completed == EXPECTED_TOPUP_SHARDS )) && break
  echo "$(date -Is) technical_topup_completed=$completed/$EXPECTED_TOPUP_SHARDS"
  sleep 60
done

echo "$(date -Is) running normalized-exact benchmark decontamination"
"$PYTHON" scripts/decontaminate_mimir_grounded_500k_exact.py \
  --data-root "$DATA_ROOT" --additional-data-root "$TOPUP_ROOT"

echo "$(date -Is) retaining all accepted rows, including at least 100k additional Technical/STEM"
"$PYTHON" scripts/mimir_grounded_500k_model.py --data-root "$DATA_ROOT" build \
  --additional-data-root "$TOPUP_ROOT" \
  --output "$DATA_ROOT/accepted/mimir_grounded_expanded_sft.jsonl"
echo "$(date -Is) Mimir grounded 500k finalization complete"
