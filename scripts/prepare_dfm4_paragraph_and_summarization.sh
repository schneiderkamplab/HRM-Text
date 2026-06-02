#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKENIZER="$ROOT/data_io/tokenizer/target/release/tokenizer"
TOKENIZER_JSON="$ROOT/data_io/trained_tokenizers/bpe/tokenizer.json"
WORKERS="${TOKENIZE_WORKERS:-1}"
CONVERT_WORKERS="${CONVERT_WORKERS:-8}"

usage() {
  cat <<'USAGE'
Usage: scripts/prepare_dfm4_paragraph_and_summarization.sh <stage>

Stages:
  inventory-dfm4      Dry-run inventory for DFM4 HF additions
  download-dfm4       Download GovReport, WikiCatSum, and LAION Scientific-Summaries
  filter              Rebuild filtered source symlink tree
  convert             Convert newly downloaded regular sources
  generate            Generate DFM4 paragraph and summarization task Parquets
  tokenize-paragraph  Tokenize DFM4 paragraph-reordering tasks with one worker by default
  tokenize-summary    Tokenize DFM4 summarization tasks with one worker by default
  build-union         Build data/tokenized_dfm4 symlink union
  sample              Sample data/sampled_dfm4 using data_io/prefix_config_dfm4.yaml
  all-after-download  filter, convert, generate, tokenize, build-union, sample
USAGE
}

cd "$ROOT"

stage="${1:-}"
case "$stage" in
  inventory-dfm4)
    python scripts/download_training_datasets.py \
      --groups dfm4 \
      --only govreport_summarization,wiki_cat_sum,laion_scientific_summaries
    ;;
  download-dfm4)
    python scripts/download_training_datasets.py \
      --groups dfm4 \
      --only govreport_summarization,wiki_cat_sum,laion_scientific_summaries \
      --download
    ;;
  filter)
    python scripts/build_filtered_source_tree.py
    ;;
  convert)
    python scripts/convert_filtered_sources.py --copy-ready --workers "$CONVERT_WORKERS"
    ;;
  generate)
    python scripts/generate_dfm4_tasks.py --force
    ;;
  tokenize-paragraph)
    ionice -c2 -n7 nice -n 10 "$TOKENIZER" \
      data/converted_sources_dfm4_paragraph_reorder \
      --tokenizer-path "$TOKENIZER_JSON" \
      --workers "$WORKERS" \
      -o data/tokenized_dfm4_paragraph_reorder
    ;;
  tokenize-summary)
    ionice -c2 -n7 nice -n 10 "$TOKENIZER" \
      data/converted_sources_dfm4_summarization \
      --tokenizer-path "$TOKENIZER_JSON" \
      --workers "$WORKERS" \
      -o data/tokenized_dfm4_summarization
    ;;
  build-union)
    python scripts/build_tokenized_dfm4_tree.py --force
    ;;
  sample)
    cd "$ROOT/data_io"
    ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
      tokenized_path=../data/tokenized_dfm4 \
      output_path=../data/sampled_dfm4 \
      epochs=4 \
      concat_workers=4 \
      prefix_config_path=prefix_config_dfm4.yaml \
      > ../data/show_analytics_dfm4.md
    ;;
  all-after-download)
    "$0" filter
    "$0" convert
    "$0" generate
    "$0" tokenize-paragraph
    "$0" tokenize-summary
    "$0" build-union
    "$0" sample
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
