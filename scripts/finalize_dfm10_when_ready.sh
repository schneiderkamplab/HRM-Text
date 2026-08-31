#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-/home/ucloud/miniforge3/envs/hrm/bin/python}"
POLL_SECONDS="${POLL_SECONDS:-60}"

wait_for_artifact() {
  local label="$1" path="$2"
  while [[ ! -s "$path" ]]; do
    echo "Waiting for $label: $path"
    sleep "$POLL_SECONDS"
  done
}

required=(
  data/tokenized_dfm10_deepdive/completion.json
  data/tokenized_dfm10_dolci_tool_use_repaired/completion.json
  data/tokenized_dfm10_nemotron_terminal_native/completion.json
  data/tokenized_dfm10_wiki_cat_sum_repaired/.recovery_complete
  data/tokenized_dfm10_scientific_summaries_repaired/tokenizer_info.json
  data/tokenized_dfm10_machine_translation_da_uk_repaired/tokenizer_info.json
  data/tokenized_dfm10_qrecc_ii_repaired/tokenizer_info.json
  data/tokenized_dfm10_scibench_repaired/tokenizer_info.json
  data/converted_sources/wiki_cat_sum_repaired_with_recovery/filter_summary.json
  data/converted_sources/machine_translation_da_uk_repaired/manifest.json
)
for path in "${required[@]}"; do
  wait_for_artifact "required final DFM10 artifact" "$path"
done

echo "Building final DFM10 tokenized union..."
"$PYTHON" scripts/build_tokenized_dfm10_tree.py --force

echo "Reconciling all audited Filter sources against the final union..."
PYTHONPATH=. "$PYTHON" scripts/reconcile_dfm10_filter_sources.py

echo "Sampling ten final DFM10 epochs..."
(
  cd data_io
  "$PYTHON" sample_tokenized.py \
    tokenized_path=../data/tokenized_dfm10 \
    output_path=../data/sampled_dfm10 \
    epochs=10 \
    concat_workers=4 \
    default_long_context=drop \
    prefix_config_path=prefix_config_dfm10.yaml \
    > ../data/show_analytics_dfm10.md
)
echo "Final DFM10 union and ten sampled epochs are complete."
