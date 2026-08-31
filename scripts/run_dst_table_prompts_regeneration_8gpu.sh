#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export AUDIT_DIR="${AUDIT_DIR:-logs/data_repairs/dst_table_prompts_regeneration_20260829}"
export AUDIT_SCRIPT="scripts/regenerate_dst_table_prompts.py"
export AUDIT_LABEL="DST table prompts target regeneration"
export PORT_BASE="${PORT_BASE:-8780}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.70}"
export CONCURRENCY="${CONCURRENCY:-64}"
export MIN_FREE_MEMORY_MIB=0
export STARTUP_STAGGER_SECONDS="${STARTUP_STAGGER_SECONDS:-12}"

exec bash scripts/run_nordjylland_news_audit_8gpu.sh
