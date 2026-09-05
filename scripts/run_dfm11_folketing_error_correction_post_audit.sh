#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

AUDIT_PYTHON="${AUDIT_PYTHON:-/home/ucloud/miniforge3/envs/audit/bin/python}"
HRM_PYTHON="${HRM_PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
RUN_ROOT="${RUN_ROOT:-logs/dfm11_folketing_error_correction}"
PACKAGE="${PACKAGE:-exports_dfm11/dfm11-folketingets-dokumenter-error-correction}"
EXPECTED_ROWS="${EXPECTED_ROWS:-2548956}"

if [[ -z "${HF_TOKEN:-}" ]]; then
  HF_TOKEN="$("$HRM_PYTHON" -c 'from huggingface_hub import get_token; print(get_token() or "")')"
  export HF_TOKEN
fi
if [[ -z "$HF_TOKEN" ]]; then
  echo "HF_TOKEN must be set for the verified publication stage." >&2
  exit 1
fi

echo "Waiting for the active full-audit clients to stop..."
while pgrep -f 'prepare_dfm11_folketing_error_correction.py audit --input exports_dfm11/dfm11-folketingets-dokumenter-error-correction-repaired' >/dev/null; do
  sleep 60
done

echo "Resuming/verifying all audit partitions..."
complete_partitions=0
for partition in 0 1 2 3; do
  if [[ -f "$RUN_ROOT/full_audit/workers/partition_${partition}/audit.jsonl" ]]; then
    complete_partitions=$((complete_partitions + 1))
  fi
done
if [[ "$complete_partitions" -eq 4 ]]; then
  echo "All four final audit files exist; no judge endpoints are needed."
else
  FINALIZE_ON_COMPLETE=0 bash scripts/run_dfm11_folketing_error_correction_full_audit.sh
fi

audit_args=()
for partition in 0 1 2 3; do
  audit_args+=(--audit "$RUN_ROOT/full_audit/workers/partition_${partition}/audit.jsonl")
done

echo "Materializing the rejection-filtered upload package..."
"$AUDIT_PYTHON" scripts/prepare_dfm11_folketing_error_correction.py finalize \
  --input exports_dfm11/dfm11-folketingets-dokumenter-error-correction-repaired \
  --output "$PACKAGE" \
  "${audit_args[@]}" \
  --expected-rows "$EXPECTED_ROWS" \
  --workers 13 \
  --force \
  > "$RUN_ROOT/finalize.log" 2>&1

echo "Validating the complete package..."
"$HRM_PYTHON" "$PACKAGE/validate_dataset.py" \
  > "$RUN_ROOT/package-validation.log" 2>&1

echo "Uploading the package to Hugging Face..."
"$HRM_PYTHON" scripts/upload_export_upload_to_hf.py \
  --root exports_dfm11 \
  --include-glob dfm11-folketingets-dokumenter-error-correction \
  --large-folder \
  --workers 8 \
  --log "$RUN_ROOT/upload.log"

echo "Verifying the remote package and pinning its revision..."
"$HRM_PYTHON" scripts/prepare_dfm11_folketing_error_correction.py record-upload \
  --package "$PACKAGE" \
  --receipt "$RUN_ROOT/upload_receipt.json"

echo "Tokenizing the audited replacement into the DFM11 additions store..."
"$HRM_PYTHON" scripts/tokenize_chat_template.py "$PACKAGE" \
  --tokenizer-path /work/mimir/brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --output-dir data/tokenized_dfm11_additions \
  --workers 13 \
  --max-seq-len 4096 \
  --skip-bad-json

if [[ -d data/tokenized_dfm10 ]]; then
  echo "Building the DFM11 union..."
  "$HRM_PYTHON" scripts/build_tokenized_dfm11_tree.py --force
else
  echo "data/tokenized_dfm10 is absent; replacement is tokenized/configured, but union materialization is deferred."
fi

echo "DFM11 Folketing error-correction post-audit pipeline complete."
