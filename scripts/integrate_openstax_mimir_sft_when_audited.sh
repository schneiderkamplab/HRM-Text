#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
POLL_SECONDS="${POLL_SECONDS:-60}"
RUN_ROOT="${RUN_ROOT:-$(cat data/mimir_openstax_sft/current_run_log_root.txt)}"
LOG="${LOG:-logs/mimir_openstax_sft_dfm10_integration.log}"

exec >>"$LOG" 2>&1
echo "$(date -Is) waiting for audited OpenStax run: $RUN_ROOT"
while true; do
  pending="$(find "$RUN_ROOT/queue/pending" -maxdepth 1 -type f -name '*.job' | wc -l)"
  running="$(find "$RUN_ROOT/queue/running" -maxdepth 1 -type f -name '*.job' | wc -l)"
  done_count="$(find "$RUN_ROOT/queue/done" -maxdepth 1 -type f -name '*.job' | wc -l)"
  failed="$(find "$RUN_ROOT/queue/failed" -maxdepth 1 -type f -name '*.job' | wc -l)"
  echo "$(date -Is) done=$done_count running=$running pending=$pending failed=$failed"
  if (( failed > 0 )); then
    echo "OpenStax generation/audit has failed shards; refusing DFM10 integration." >&2
    exit 1
  fi
  if (( done_count == 64 && running == 0 && pending == 0 )); then
    break
  fi
  sleep "$POLL_SECONDS"
done

while pgrep -f '[r]un_openstax_mimir_sft_pilot_8gpu.sh|[o]penstax_sft_model.py' >/dev/null; do
  sleep 10
done

echo "$(date -Is) validating and staging accepted rows"
"$PYTHON" scripts/finalize_openstax_mimir_sft.py

echo "$(date -Is) tokenizing audited OpenStax rows"
"$PYTHON" scripts/tokenize_chat_template.py \
  data/dfm10_openstax_sft_sources \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir data/tokenized_dfm10_openstax_sft \
  --workers 16 \
  --force

echo "$(date -Is) rebuilding canonical DFM10 tokenized union"
"$PYTHON" scripts/build_tokenized_dfm10_tree.py --force
touch data/tokenized_dfm10_openstax_sft/.dfm10_integration_complete
echo "$(date -Is) audited OpenStax SFT is active in data/tokenized_dfm10"
