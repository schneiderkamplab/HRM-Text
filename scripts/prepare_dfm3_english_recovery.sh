#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

COMMON_PILE_ONLY=common_pile_wikimedia_filtered,common_pile_wikiteam_filtered,common_pile_stackexchange_filtered,common_pile_pubmed_filtered,common_pile_arxiv_abstracts_filtered,common_pile_arxiv_papers_filtered,common_pile_usgpo_filtered,common_pile_regulations_filtered,common_pile_uspto_filtered,common_pile_project_gutenberg_filtered,common_pile_public_domain_review_filtered,common_pile_library_of_congress

usage() {
  cat <<'EOF'
Usage: scripts/prepare_dfm3_english_recovery.sh <stage>

Stages:
  inventory-common-pile   Show selected Common Pile download inventory.
  download-common-pile    Download selected Common Pile sources.
  filter                  Rebuild filtered source symlink tree incrementally.
  convert                 Convert newly filtered sources into data/converted_sources.
  generate                Generate DFM3 Common Pile self-supervised tasks.
  tokenize                Tokenize generated DFM3 tasks with one worker.
  build-union             Build data/tokenized_dfm3 symlink union.
  sample                  Sample data/sampled_dfm3 with prefix_config_dfm3.yaml.
  all-after-download      Run filter, convert, generate, tokenize, build-union, sample.

The heavy download stage is intentionally separate.
EOF
}

stage="${1:-}"
if [[ -z "${stage}" || "${stage}" == "-h" || "${stage}" == "--help" ]]; then
  usage
  exit 0
fi

case "${stage}" in
  inventory-common-pile)
    python scripts/download_training_datasets.py --groups common_pile
    ;;
  download-common-pile)
    python scripts/download_training_datasets.py \
      --groups common_pile \
      --only "${COMMON_PILE_ONLY}" \
      --download
    ;;
  filter)
    python scripts/build_filtered_source_tree.py
    ;;
  convert)
    python scripts/convert_filtered_sources.py --copy-ready --workers "${CONVERT_WORKERS:-8}"
    ;;
  generate)
    python scripts/generate_dfm3_common_pile_tasks.py \
      --output-root data/converted_sources_dfm3_common_pile_tasks \
      --force
    ;;
  tokenize)
    ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
      data/converted_sources_dfm3_common_pile_tasks \
      --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
      --workers 1 \
      -o data/tokenized_dfm3_common_pile_tasks
    ;;
  build-union)
    python scripts/build_tokenized_dfm3_tree.py --force
    ;;
  sample)
    (
      cd data_io
      ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
        tokenized_path=../data/tokenized_dfm3 \
        output_path=../data/sampled_dfm3 \
        epochs=4 \
        concat_workers=4 \
        prefix_config_path=prefix_config_dfm3.yaml \
        > ../data/show_analytics_dfm3.md
    )
    ;;
  all-after-download)
    "$0" filter
    "$0" convert
    "$0" generate
    "$0" tokenize
    "$0" build-union
    "$0" sample
    ;;
  *)
    usage
    exit 2
    ;;
esac
