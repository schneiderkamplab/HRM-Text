#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
SCORED_ROOT="${SCORED_ROOT:-data/opus_da_en_quality/scored_shards}"
EXPECTED_SHARDS="${EXPECTED_SHARDS:-64}"
MIN_FREE_MIB="${MIN_FREE_MIB:-160000}"
GPU_FREE_STABLE_SECONDS="${GPU_FREE_STABLE_SECONDS:-120}"
GPU_FREE_POLL_SECONDS="${GPU_FREE_POLL_SECONDS:-10}"
RUN_ROOT="${RUN_ROOT:-logs/data_audits/opus_da_en_repaired_20260828}"
mkdir -p "$RUN_ROOT"
exec 9>"$RUN_ROOT/finisher.lock"
flock -n 9 || { echo "Another OPUS finisher is active" >&2; exit 2; }

echo "Waiting for OPUS scoring workers..."
while pgrep -f '[f]ilter_opus_da_en.py' >/dev/null; do sleep 60; done
scored_count="$(find "$SCORED_ROOT" -maxdepth 1 -type f -name 'part-*.parquet' | wc -l)"
if [[ "$scored_count" -ne "$EXPECTED_SHARDS" ]]; then
  echo "OPUS scoring stopped with $scored_count/$EXPECTED_SHARDS complete shards" >&2
  exit 2
fi
find "$SCORED_ROOT" -maxdepth 1 -type f -name '.*.tmp.*' -delete

echo "Building accepted bidirectional OPUS rows..."
"$PYTHON" scripts/build_opus_da_en_repaired.py
"$PYTHON" scripts/prepare_opus_da_en_reaudit.py --samples 1000

echo "Waiting for eight GPUs with at least ${MIN_FREE_MIB} MiB free each for ${GPU_FREE_STABLE_SECONDS}s..."
stable_since=0
while true; do
  mapfile -t free_mib < <(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits)
  ready=1
  [[ "${#free_mib[@]}" -eq 8 ]] || ready=0
  for value in "${free_mib[@]}"; do
    (( value >= MIN_FREE_MIB )) || ready=0
  done
  if (( ready == 1 )); then
    (( stable_since > 0 )) || stable_since="$(date +%s)"
    (( $(date +%s) - stable_since >= GPU_FREE_STABLE_SECONDS )) && break
  else
    stable_since=0
  fi
  sleep "$GPU_FREE_POLL_SECONDS"
done

echo "Running independent E4B accepted-pair audit..."
RUN_ROOT="$RUN_ROOT" bash scripts/run_opus_da_en_reaudit_8gpu.sh
"$PYTHON" scripts/validate_opus_da_en_repaired.py

echo "Tokenizing accepted OPUS pairs with the Gemma 4 template..."
STAGE="data/dfm10_opus_repaired_sources"
if [[ ! -e "$STAGE/opus_da_en_repaired" ]]; then
  mkdir -p "$STAGE"
  ln -s "$(realpath data/converted_sources/opus_da_en_repaired)" \
    "$STAGE/opus_da_en_repaired"
fi
"$PYTHON" scripts/tokenize_chat_template.py \
  "$STAGE" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_opus_repaired \
  --workers 16

echo "Validating scored, converted, audited, and tokenized OPUS artifacts..."
"$PYTHON" scripts/validate_opus_da_en_repaired.py
echo "OPUS repair artifacts passed all activation gates."
