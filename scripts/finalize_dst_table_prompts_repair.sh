#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_DIR="${AUDIT_DIR:-logs/data_audits/dst_table_prompts_regenerated_20260829}"
AUDIT="$AUDIT_DIR/dst_table_prompts_repaired_quality_audit.jsonl"
SUMMARY="$AUDIT_DIR/summary.json"
INPUT_DIR="${INPUT_DIR:-data/converted_sources/dst_table_prompts_regenerated}"
FILTERED="${FILTERED:-data/converted_sources/dst_table_prompts_repaired_grounded}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm-cu132/bin/python}"

if [[ "${WAIT_FOR_AUDIT:-0}" == "1" ]]; then
  until [[ -s "$AUDIT" && -s "$SUMMARY" ]]; do sleep 30; done
fi
[[ -s "$AUDIT" && -s "$SUMMARY" ]] || {
  echo "Full DST table-prompts audit is incomplete: $AUDIT_DIR" >&2
  exit 2
}

"$PYTHON" - "$SUMMARY" <<'PY'
import json
import sys
from pathlib import Path

summary = json.loads(Path(sys.argv[1]).read_text())
counts = summary.get("counts", {})
audited = counts.get("audited", 0)
strict = counts.get("strict_accepted", 0)
if audited != 3_016:
    raise SystemExit(f"expected 3,016 audited rows, got {counts}")
if strict / audited < 0.80:
    raise SystemExit(f"DST production grounding gate failed: {strict}/{audited}")
PY

"$PYTHON" scripts/filter_repaired_dst_table_prompts.py \
  --input-dir "$INPUT_DIR" --audit "$AUDIT" --output-dir "$FILTERED" --force

STAGE="data/dfm10_dst_table_prompts_repaired_sources"
"$PYTHON" - "$STAGE" "$FILTERED/train.parquet" <<'PY'
import shutil
import sys
from pathlib import Path

stage = Path(sys.argv[1])
source = Path(sys.argv[2]).resolve()
if stage.exists() or stage.is_symlink():
    if stage.is_symlink() or stage.is_file():
        stage.unlink()
    else:
        shutil.rmtree(stage)
target = stage / "dst_table_prompts_repaired"
target.mkdir(parents=True)
(target / "train.parquet").symlink_to(source)
PY

"$PYTHON" scripts/tokenize_chat_template.py \
  "$STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_dst_table_prompts_repaired \
  --workers 16 \
  --force

"$PYTHON" - "$INPUT_DIR" "$AUDIT" "$FILTERED/filter_summary.json" <<'PY'
import json
import os
import sys
from pathlib import Path

output = Path("data/tokenized_dfm10_dst_table_prompts_repaired/production_gate.json")
payload = {
    "input": sys.argv[1],
    "audit": sys.argv[2],
    "filter_summary": json.loads(Path(sys.argv[3]).read_text()),
    "status": "production_ready",
}
temporary = output.with_suffix(".json.tmp")
temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
with temporary.open("rb") as handle:
    os.fsync(handle.fileno())
temporary.replace(output)
PY

echo "DST table-prompts repair audited, filtered, and tokenized"
