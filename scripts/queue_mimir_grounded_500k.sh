#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p logs

LOG="logs/mimir_grounded_500k_waiter_$(date +%Y%m%dT%H%M%S).log"
echo "$(date -Is) queued Mimir grounded 5x100k campaign" | tee -a "$LOG"
exec scripts/run_mimir_grounded_500k_8gpu.sh >>"$LOG" 2>&1
