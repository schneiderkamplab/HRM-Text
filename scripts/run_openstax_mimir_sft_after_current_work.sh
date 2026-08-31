#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG="${LOG:-$ROOT/logs/mimir_openstax_sft_waiter_$(date +%Y%m%dT%H%M%S).log}"
exec > >(tee -a "$LOG") 2>&1

echo "$(date -Is) waiting for current WikiCat recovery work"
while pgrep -f '[r]un_wiki_cat_sum_recovery_when_free.sh|[g]enerate_wiki_cat_sum_recovery.py|[a]udit_wiki_cat_sum_recovery.py' >/dev/null; do
  sleep 60
done

echo "$(date -Is) starting the provenance-verified OpenStax pilot"
exec scripts/run_openstax_mimir_sft_pilot_8gpu.sh
