#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_PATH="${TOKENIZER_PATH:-/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json}"
CHAT_TEMPLATE="${CHAT_TEMPLATE:-data_io/chat_templates/gemma4_native_chat.jinja}"
TOKENIZER_WORKERS="${TOKENIZER_WORKERS:-16}"
PACKAGE="exports_dfm10/dfm10-mimir-grounded-expanded-sft"
SOURCE_ROOT="data/dfm10_mimir_grounded_expanded_sources"
TOKENIZED_ROOT="data/tokenized_dfm10_mimir_grounded_expanded_sft"

echo "Validating the expanded Mimir export package..."
validation="$($PYTHON "$PACKAGE/recreate_dataset.py")"
[[ "$validation" == '{"rows": 732763, "valid": true}' ]] || {
  echo "Unexpected validation result: $validation" >&2
  exit 2
}

echo "Preparing uniquely named source-shard links..."
temporary="${SOURCE_ROOT}.tmp.$$"
rm -rf "$temporary"
mkdir -p "$temporary"
shopt -s nullglob
shards=("$PACKAGE"/data/train-*.jsonl.gz)
[[ "${#shards[@]}" -gt 0 ]] || { echo "No export shards found" >&2; exit 2; }
for shard in "${shards[@]}"; do
  suffix="${shard##*/train-}"
  ln -s "$ROOT/$shard" "$temporary/mimir_grounded_expanded_sft__part-$suffix"
done
rm -rf "$SOURCE_ROOT"
mv "$temporary" "$SOURCE_ROOT"

echo "Tokenizing expanded Mimir grounded SFT with up to $TOKENIZER_WORKERS workers..."
"$PYTHON" scripts/tokenize_chat_template.py \
  "$SOURCE_ROOT" \
  --tokenizer-path "$TOKENIZER_PATH" \
  --chat-template "$CHAT_TEMPLATE" \
  --output-dir "$TOKENIZED_ROOT" \
  --workers "$TOKENIZER_WORKERS" \
  --force

if pgrep -af '[b]uild_tokenized_dfm10_tree.py' >/dev/null; then
  echo "Another DFM10 union build is active; tokenization is complete but union rebuild is deferred." >&2
  exit 3
fi

echo "Rebuilding the canonical DFM10 tokenized union..."
"$PYTHON" scripts/build_tokenized_dfm10_tree.py --force
echo "Expanded Mimir grounded SFT integration complete."
