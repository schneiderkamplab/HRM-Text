#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"
DST_PID_FILE="${DST_PID_FILE:-logs/data_audits/danmarks_statistik_bt_article_generation_31b_20260829/launcher.pid}"
DST_RESULT="${DST_RESULT:-data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery/filter_summary.json}"
GOV_RESULT="${GOV_RESULT:-data/converted_sources/govreport_summarization_grounded_8k/filter_summary.json}"
UNIVERSITY_RESULT="${UNIVERSITY_RESULT:-data/converted_sources/danish_university_portals_bt_repaired/filter_summary.json}"
POLL_SECONDS="${POLL_SECONDS:-30}"
RUN_GOVREPORT_8K="${RUN_GOVREPORT_8K:-0}"

if [[ -f "$DST_PID_FILE" ]]; then
  dst_pid="$(tr -dc '0-9' < "$DST_PID_FILE")"
  while [[ -n "$dst_pid" ]] && kill -0 "$dst_pid" 2>/dev/null; do
    echo "Waiting for DST article recovery (PID $dst_pid)."
    sleep "$POLL_SECONDS"
  done
fi
[[ -f "$DST_RESULT" ]] || {
  echo "DST article recovery did not publish $DST_RESULT; stopping queue." >&2
  exit 1
}

if (( RUN_GOVREPORT_8K == 1 )); then
  echo "DST article recovery passed; starting deferred GovReport 8K+ recovery."
  PYTHON="$PYTHON" scripts/run_govreport_8k_repair_when_free.sh
  [[ -f "$GOV_RESULT" ]] || {
    echo "GovReport 8K+ recovery did not publish $GOV_RESULT; stopping queue." >&2
    exit 1
  }
else
  echo "Leaving GovReport 8K+ candidates deferred for a long-context DFM10 version."
fi

echo "Retrying university source-grounded recovery."
PYTHON="$PYTHON" scripts/finish_danish_university_portals_incomplete_recovery.sh
[[ -f "$UNIVERSITY_RESULT" ]] || {
  echo "University recovery did not publish $UNIVERSITY_RESULT; stopping queue." >&2
  exit 1
}

echo "DFM10 DST, GovReport 8K+, and university recovery queue completed."
