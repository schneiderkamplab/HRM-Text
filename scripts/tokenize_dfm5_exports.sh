#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKENIZER_DIR="${ROOT}/data_io/tokenizer"
TOKENIZER_BIN="${TOKENIZER_BIN:-${TOKENIZER_DIR}/target/release/tokenizer}"
TOKENIZER_PATH="${TOKENIZER_PATH:-${ROOT}/data_io/trained_tokenizers/bpe/tokenizer.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${ROOT}/data/tokenized_dfm5_exports}"
WORKERS="${WORKERS:-1}"

AUDITED_DATASETS=(
  common-pile-denoising
  common-pile-paragraph-reordering
  common-pile-prefix-continuation
  common-pile-span-filling
  danish-dynaword-denoising
  danish-dynaword-paragraph-reordering
  danish-dynaword-prefix-continuation
  danish-dynaword-span-filling
)

TRANSFORM_DATASETS=(
  transformations-danish-danish
  transformations-danish-english
  transformations-english-danish
  transformations-english-english
)

run_tokenizer() {
  local dataset="$1"
  local input="$2"
  local output="${OUTPUT_ROOT}/${dataset}"

  if [[ ! -d "${input}" ]]; then
    echo "Missing input dataset: ${input}" >&2
    exit 1
  fi

  echo "Tokenizing ${dataset}"
  echo "  input:  ${input}"
  echo "  output: ${output}"
  if [[ -x "${TOKENIZER_BIN}" ]]; then
    "${TOKENIZER_BIN}" \
      "${input}" \
      --tokenizer-path "${TOKENIZER_PATH}" \
      -o "${output}" \
      --workers "${WORKERS}"
  else
    cargo run --release --bin tokenizer -- \
      "${input}" \
      --tokenizer-path "${TOKENIZER_PATH}" \
      -o "${output}" \
      --workers "${WORKERS}"
  fi
}

mkdir -p "${OUTPUT_ROOT}"

cd "${TOKENIZER_DIR}"
for dataset in "${AUDITED_DATASETS[@]}"; do
  run_tokenizer "${dataset}" "${ROOT}/export/${dataset}/audited/data"
done

for dataset in "${TRANSFORM_DATASETS[@]}"; do
  run_tokenizer "${dataset}" "${ROOT}/export/${dataset}/data"
done
