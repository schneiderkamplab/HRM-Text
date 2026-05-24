#!/usr/bin/env bash
# Reproduce the HRM-Text L run with the original Sapient data mix.
#
# This records the exact command sequence used in this checkout:
#   1. Download the Sapient cleaned data.
#   2. Tokenize the original Sapient roots directly, not the filtered mixed tree.
#   3. Sample into data/sampled_original_sapient.
#   4. Launch the L-size training run.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/work/dfm/HRM-Text}"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
TOKENIZER_BIN="${TOKENIZER_BIN:-${REPO_ROOT}/data_io/tokenizer/target/release/tokenizer}"
TOKENIZER_JSON="${TOKENIZER_JSON:-${REPO_ROOT}/data_io/trained_tokenizers/bpe/tokenizer.json}"
TMP_ROOT="${TMP_ROOT:-${REPO_ROOT}/tmp}"

SAP_USED="${REPO_ROOT}/data/downloads/datasets/sapient_cleaned"
SAP_CLUSTERED="${SAP_USED}/data_clustered"
SAP_DATA="${SAP_USED}/data"
TOKENIZED="${REPO_ROOT}/data/tokenized_original_sapient"
SAMPLED="${REPO_ROOT}/data/sampled_original_sapient"
ANALYTICS="${REPO_ROOT}/data/show_analytics_original_sapient.md"
CHECKPOINTS="${REPO_ROOT}/checkpoints/original_sapient/L"

usage() {
  cat <<'EOF'
Usage:
  scripts/reproduce_original_sapient_l.sh <stage>

Stages:
  download       Download sapientinc/HRM-Text-data-io-cleaned-20260515 via the local manifest.
  tokenize       Tokenize the original Sapient roots into data/tokenized_original_sapient.
  verify         Verify expected tokenized metadata count.
  sample         Build data/sampled_original_sapient and analytics markdown.
  train          Launch the HRM-Text L reproduction run.
  all            Run download, tokenize, verify, sample, train.

Environment overrides:
  REPO_ROOT      Default: /work/dfm/HRM-Text
  PYTHON         Default: /home/ucloud/miniforge3/envs/hrm/bin/python
  TOKENIZER_BIN  Default: $REPO_ROOT/data_io/tokenizer/target/release/tokenizer
  TOKENIZER_JSON Default: $REPO_ROOT/data_io/trained_tokenizers/bpe/tokenizer.json
  TMP_ROOT       Default: $REPO_ROOT/tmp

Notes:
  - This script intentionally bypasses data/filtered_sources and data/converted_sources.
  - Do not use the mixed-corpus paths for this reproduction run.
  - The tokenizer is single-process by default here. Control effective worker count with taskset.
EOF
}

run_download() {
  cd "${REPO_ROOT}"
  "${PYTHON}" scripts/download_training_datasets.py --groups sapient --download
}

run_tokenize() {
  cd "${REPO_ROOT}"
  mkdir -p "${TMP_ROOT}"
  TMPDIR="${TMP_ROOT}" TEMP="${TMP_ROOT}" TMP="${TMP_ROOT}" \
  nice -n 19 ionice -c3 taskset -c 0-1 \
    "${TOKENIZER_BIN}" \
      "${SAP_CLUSTERED}" \
      "${SAP_DATA}" \
      --tokenizer-path "${TOKENIZER_JSON}" \
      -o "${TOKENIZED}"
}

run_verify() {
  cd "${REPO_ROOT}"
  local metadata_count
  metadata_count="$(find "${TOKENIZED}" -name metadata.json | wc -l)"
  echo "Tokenized metadata count: ${metadata_count}"
  du -sh "${TOKENIZED}"
  if [[ "${metadata_count}" != "5212" ]]; then
    echo "Expected 5212 metadata files for the current Sapient download." >&2
    return 1
  fi
}

run_sample() {
  cd "${REPO_ROOT}/data_io"
  mkdir -p "${TMP_ROOT}"
  TMPDIR="${TMP_ROOT}" TEMP="${TMP_ROOT}" TMP="${TMP_ROOT}" \
    "${PYTHON}" sample_tokenized.py \
      tokenized_path=../data/tokenized_original_sapient \
      output_path=../data/sampled_original_sapient \
      epochs=4 \
      > "${ANALYTICS}"
}

run_train() {
  cd "${REPO_ROOT}"
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  torchrun --nproc_per_node=8 pretrain.py \
    data=original_sapient \
    arch/size@arch=L \
    lr=2.5e-4 \
    global_batch_size=172032 \
    +project_name="Original Sapient L HLM-torch" \
    +run_name=original-sapient-L \
    +checkpoint_path="${CHECKPOINTS}"
}

stage="${1:-}"
case "${stage}" in
  download) run_download ;;
  tokenize) run_tokenize ;;
  verify) run_verify ;;
  sample) run_sample ;;
  train) run_train ;;
  all)
    run_download
    run_tokenize
    run_verify
    run_sample
    run_train
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    usage >&2
    echo "Unknown stage: ${stage}" >&2
    exit 2
    ;;
esac
