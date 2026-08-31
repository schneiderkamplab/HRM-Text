#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# The shared launcher takes an exclusive per-GPU lock and, with the default
# zero threshold, waits until each GPU has no compute process at all.
export AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/dst_table_prompts_repaired_20260829}"
export AUDIT_SCRIPT="scripts/audit_repaired_dst_table_prompts.py"
export AUDIT_LABEL="DST table prompts repaired"
export PORT_BASE="${PORT_BASE:-8760}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
export CONCURRENCY="${CONCURRENCY:-64}"
export MIN_FREE_MEMORY_MIB=0
export STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-12}"

exec bash scripts/run_nordjylland_news_audit_8gpu.sh
