#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKENIZER_DIR="${ROOT}/data_io/tokenizer"
TOKENIZER_BIN="${TOKENIZER_BIN:-${TOKENIZER_DIR}/target/release/tokenizer}"
TOKENIZER_PATH="${TOKENIZER_PATH:-${ROOT}/data_io/trained_tokenizers/bpe/tokenizer.json}"
INPUT_ROOT="${INPUT_ROOT:-${ROOT}/data/synth_repeat30_sources}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/data/tokenized_dfm5_synth_repeat30}"
WORKERS="${WORKERS:-1}"

cd "${ROOT}"
python scripts/build_synth_high40_source_tree.py \
  --source-priority repeat30 \
  --force \
  --output "${INPUT_ROOT}"

if [[ ! -d "${INPUT_ROOT}" ]]; then
  echo "Missing input tree: ${INPUT_ROOT}" >&2
  exit 1
fi

cd "${TOKENIZER_DIR}"
if [[ -x "${TOKENIZER_BIN}" ]]; then
  "${TOKENIZER_BIN}" \
    "${INPUT_ROOT}" \
    --tokenizer-path "${TOKENIZER_PATH}" \
    -o "${OUTPUT_ROOT}" \
    --workers "${WORKERS}"
else
  cargo run --release --bin tokenizer -- \
    "${INPUT_ROOT}" \
    --tokenizer-path "${TOKENIZER_PATH}" \
    -o "${OUTPUT_ROOT}" \
    --workers "${WORKERS}"
fi
