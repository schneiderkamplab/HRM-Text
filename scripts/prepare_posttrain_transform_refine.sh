#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="${1:-help}"
WORKERS="${WORKERS:-2}"
TOKENIZER_PATH="${TOKENIZER_PATH:-$ROOT/data_io/trained_tokenizers/bpe/tokenizer.json}"

cd "$ROOT"

case "$STAGE" in
  inventory)
    python scripts/download_training_datasets.py \
      --groups posttrain_transform
    ;;

  download-existing)
    python scripts/download_training_datasets.py \
      --groups posttrain_transform \
      --download \
      --max-workers "${DOWNLOAD_WORKERS:-8}"
    ;;

  convert-existing)
    python scripts/prepare_posttrain_transform_refine.py convert-existing
    ;;

  make-synthetic-requests)
    python scripts/prepare_posttrain_transform_refine.py make-synthetic-requests
    ;;

  shard-synthetic-requests)
    python scripts/prepare_posttrain_transform_refine.py shard-synthetic-requests \
      --requests-per-shard "${REQUESTS_PER_SHARD:-1000}" \
      ${FORCE_SHARDS:+--force}
    ;;

  generate-synthetic)
    : "${GEMMA_OPENAI_BASE_URL:?Set GEMMA_OPENAI_BASE_URL, e.g. http://127.0.0.1:8000/v1}"
    : "${GEMMA_TEACHER_MODEL:?Set GEMMA_TEACHER_MODEL, e.g. gemma-4-31b or gemma-4-26b-a3}"
    python scripts/prepare_posttrain_transform_refine.py generate-synthetic \
      --base-url "$GEMMA_OPENAI_BASE_URL" \
      --model "$GEMMA_TEACHER_MODEL"
    ;;

  convert-synthetic)
    python scripts/prepare_posttrain_transform_refine.py convert-generated
    ;;

  tokenize-existing)
    cd "$ROOT/data_io/tokenizer"
    cargo run --release --bin tokenizer -- \
      "$ROOT/data/converted_sources_posttrain_transform_refine" \
      --tokenizer-path "$TOKENIZER_PATH" \
      -o "$ROOT/data/tokenized_posttrain_transform_refine_existing" \
      --workers "$WORKERS"
    ;;

  tokenize-synthetic)
    cd "$ROOT/data_io/tokenizer"
    cargo run --release --bin tokenizer -- \
      "$ROOT/data/converted_sources_posttrain_transform_refine_synthetic" \
      --tokenizer-path "$TOKENIZER_PATH" \
      -o "$ROOT/data/tokenized_posttrain_transform_refine_synthetic" \
      --workers "$WORKERS"
    ;;

  build-tokenized-tree)
    python scripts/build_tokenized_posttrain_transform_refine_tree.py --force
    ;;

  sample)
    cd "$ROOT/data_io"
    python sample_tokenized.py \
      tokenized_path=../data/tokenized_posttrain_transform_refine \
      output_path=../data/sampled_posttrain_transform_refine \
      prefix_config_path=prefix_config_posttrain_transform_refine.yaml \
      epochs="${EPOCHS:-1}" \
      concat_workers="${CONCAT_WORKERS:-2}" \
      > ../data/show_analytics_posttrain_transform_refine.md
    ;;

  all-before-teacher)
    "$0" download-existing
    "$0" convert-existing
    "$0" make-synthetic-requests
    "$0" tokenize-existing
    "$0" build-tokenized-tree
    "$0" sample
    ;;

  help|*)
    cat <<'EOF'
Usage: scripts/prepare_posttrain_transform_refine.sh <stage>

Stages:
  inventory                 Show selected post-training HF datasets.
  download-existing         Download CoEdIT, Super-NI, and ASSET source files.
  convert-existing          Convert CoEdIT and filtered Super-NI to ready Parquet.
  make-synthetic-requests   Build request JSONL files for later Gemma generation.
  generate-synthetic        Call an OpenAI-compatible Gemma teacher server.
  shard-synthetic-requests  Split synthetic request JSONL into queue shards.
  convert-synthetic         Convert accepted generated rows to ready Parquet.
  tokenize-existing         Tokenize converted existing rows.
  tokenize-synthetic        Tokenize accepted synthetic rows after generation.
  build-tokenized-tree      Link relevant existing DFM4 tasks plus posttrain tasks.
  sample                    Sample data/sampled_posttrain_transform_refine.
  all-before-teacher        Run all stages possible before teacher generation.

Environment:
  WORKERS=2
  DOWNLOAD_WORKERS=8
  EPOCHS=1
  CONCAT_WORKERS=2
  GEMMA_OPENAI_BASE_URL=http://127.0.0.1:8000/v1
  GEMMA_TEACHER_MODEL=gemma-4-31b
  REQUESTS_PER_SHARD=1000
EOF
    ;;
esac
