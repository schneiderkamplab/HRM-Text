# Download, Convert, Tokenize, Sample

Last updated: 2026-06-01
Confidence: high
Scope: Concrete commands for the local data pipeline.

## Download

Default all-manifest download excluding gated sources:

```bash
cd /work/dfm/HRM-Text
python scripts/download_training_datasets.py --groups all --exclude-gated --download
```

Download all manifest entries including gated sources when `HF_TOKEN` has access:

```bash
cd /work/dfm/HRM-Text
export HF_TOKEN='...'
python scripts/download_training_datasets.py --groups all --download
```

Download only the newly approved DFM gated additions:

```bash
cd /work/dfm/HRM-Text
export HF_TOKEN='...'
python scripts/download_training_datasets.py \
  --only laerebogen_with_followups,synquid_wiki_instruct_da,oliverkinch_instruct_bt,synquid_mt_da_deepseek,synquid_wildchat_100k_qwen_messages \
  --download
```

Download only Danish raw continuation:

```bash
python scripts/download_training_datasets.py --groups raw --download
```

## Dataset Versions

For Hugging Face snapshots downloaded by `scripts/download_training_datasets.py`, the local snapshot commit is recoverable from:

```text
data/downloads/datasets/<local_name>/.cache/huggingface/download/README.md.metadata
```

The first line is the dataset repository commit hash used by `snapshot_download`; the third line is the local cache timestamp. Local/manual additions such as `dbc`, `lexdk`, and `opus` do not currently have upstream snapshot metadata in this format. Confidence: high.

## Filter

```bash
python scripts/build_filtered_source_tree.py
```

Use `--force` only for an intentional full rebuild.

## Convert

`data_io/tokenizer` requires rows with:

```text
condition, instruction, response
```

Chat data support, verified on 2026-05-26. Confidence: high.

`scripts/convert_filtered_sources.py` already supports Parquet/JSONL datasets
with a `messages` column/key. It normalizes message lists and expands each
assistant turn into one PrefixLM row:

```text
condition = direct
instruction = serialized prior history, with System/User/Assistant/Tool labels
response = current assistant message
```

If a message has `reasoning_content`, the converter prepends it to the
assistant `response` before the visible assistant content. The downstream Rust
tokenizer still only reads `condition`, `instruction`, and `response`; it wraps
the instruction with BOQ/condition/EOQ tokens and the response with EOA.
Training then applies target-only loss to the response span when configured,
not to the serialized chat history. This means the current chat path is
flattened PrefixLM chat, not native multi-turn chat-format training.

Implementation provenance, checked with `git blame` on 2026-05-27. Confidence:
high. The message conversion functions were introduced in commit `45a297f6`
dated `2026-05-24 22:48:35 +0200`.

Tool-calling support is only superficial. Messages with role `tool` are
serialized into the prior history as `Tool:\n...`, so tool results can appear
as context before a later assistant answer. However, the converter only keeps
`role`, `content`, and `reasoning_content`; it drops fields such as
`tool_calls`, `function_call`, `name`, and `tool_call_id`. Assistant messages
with tool calls but empty `content` are not emitted as supervised responses and
are effectively lost except for any non-empty content that exists. There are no
tool-call special tokens or native tool-call loss masks in the tokenizer/model
path.

Convert filtered sources:

```bash
python scripts/convert_filtered_sources.py --copy-ready --workers 32
```

Use `--workers 64` only if storage I/O can keep up.

Both `oliverkinch/instruct-bt` and
`synquid/wildchat-100k-qwen-messages` were verified on 2026-05-27 to expose a
`messages` column/key, so they use the existing message conversion path.

Important tokenizer safety note, discovered on 2026-05-27. Confidence: high.
The Rust tokenizer prunes "orphan" output directories from `-o` when they are
not present under the current input root. Therefore, do not run it against a
subset of inputs while writing to the shared `data/tokenized_mixed` output. A
subset run against `data/converted_sources_dfm_new` removed existing
`data/tokenized_mixed` task directories. Recovery is to run the tokenizer
against the full `data/converted_sources` tree:

```bash
cd /work/dfm/HRM-Text
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_mixed
```

After that full tokenizer run completes with `Done.`, sample the DFM mix:

```bash
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled_dfm \
  epochs=4 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm.yaml \
  > ../data/show_analytics_dfm.md
```

`convert_filtered_sources.py` is incremental by default. It skips current outputs and writes `.convert_meta.json` sidecars for new conversions. Outputs created before sidecars existed are skipped when their output mtime is newer than or equal to the source mtime.

Local DBC additions were moved under:

```text
data/downloads/datasets/dbc
data/downloads/datasets/lexdk
data/downloads/datasets/opus
```

The filter allowlists only:

```text
dbc/dbc-abstracts_*.jsonl.gz
dbc/dbc-reviews.jsonl.gz
dbc/dbc-faktalink.jsonl.gz
dbc/dbc-farfatterweb.jsonl.gz
lexdk/lexdk_articles.jsonl.gz
opus/opus_da_en.jsonl.gz
opus/opus-da_*.jsonl.gz
opus/opus-en_*.jsonl.gz
```

All other local DBC raw/crawl files are denied by default. After rescanning OPUS on 2026-05-23, the OPUS directory contained one direct paired file, `opus_da_en.jsonl.gz`, with `id`, `da`, `en`, and `source` fields. Rebuilding `data/filtered_sources` with `--force` removed stale old `opus-da_*.jsonl.gz` symlinks and left one OPUS symlink. A smoke conversion of `opus_da_en.jsonl.gz` produced `58,522,188` bidirectional translation rows.

## Tokenize

Run from `data_io/tokenizer`, because that is where `Cargo.toml` lives.

```bash
cd /work/dfm/HRM-Text/data_io/tokenizer
cargo run --release --bin tokenizer -- \
  /work/dfm/HRM-Text/data/converted_sources \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  -o /work/dfm/HRM-Text/data/tokenized_mixed
```

Use an absolute tokenizer path. If the tokenizer path is wrong, the `tokenizers` library treats it as a Hugging Face repo id and may try a URL like `https://huggingface.co/data_io/...`.

## DFM2 Raw-Text Task Pipeline

Added on 2026-05-30. Confidence: high for commands/config paths and final
sampled analytics.

DFM2 keeps the existing DFM tokenized tree and adds DynaWord-derived raw-text
tasks. The generated task source tree is separate:

```text
Generated converted task sources: data/converted_sources_dfm2_dynaword_tasks
Tokenized generated tasks:        data/tokenized_dfm2_dynaword_tasks
Tokenized DFM2 union:             data/tokenized_dfm2
Sampled DFM2 output:              data/sampled_dfm2
Sampling config:                  data_io/prefix_config_dfm2.yaml
Training data config:             config/data/dfm2.yaml
Analytics:                        data/show_analytics_dfm2.md
```

Generate the DynaWord-derived task sources:

```bash
cd /work/dfm/HRM-Text
python scripts/generate_dfm2_dynaword_tasks.py \
  --output-root data/converted_sources_dfm2_dynaword_tasks \
  --force
```

The generator creates:

```text
dfm2_dynaword_prefix_continuation:    60,000 rows/source file
dfm2_dynaword_prefix_continuation_v2: 60,000 rows/source file
dfm2_dynaword_denoising:              30,000 rows/source file
dfm2_dynaword_denoising_v2:           30,000 rows/source file
dfm2_dynaword_span_fill_v1:           30,000 rows/source file
dfm2_dynaword_span_fill_v2:           30,000 rows/source file
dfm2_dynaword_span_fill_v3:           30,000 rows/source file
dfm2_dynaword_span_fill_v4:           30,000 rows/source file
dfm2_dynaword_span_fill_v5:           30,000 rows/source file
dfm2_dynaword_span_fill_v6:           30,000 rows/source file
```

Tokenize the generated tasks with one worker only:

```bash
cd /work/dfm/HRM-Text
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm2_dynaword_tasks \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm2_dynaword_tasks
```

Build the tokenized union:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_dfm2_tree.py --force
```

Sample DFM2:

```bash
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm2 \
  output_path=../data/sampled_dfm2 \
  epochs=4 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm2.yaml \
  > ../data/show_analytics_dfm2.md
```

Verified final DFM2 outputs on 2026-05-30:

```text
data/converted_sources_dfm2_dynaword_tasks: 13G, 450 Parquet files
data/tokenized_dfm2_dynaword_tasks:         53G, 450 tokenized task dirs
data/tokenized_dfm2:                        1,827 linked task dirs
data/sampled_dfm2:                          692G, 18 files
data/show_analytics_dfm2.md:                352K
```

`data/sampled_dfm2/metadata.json` reports:

```json
{"max_seq_len": 4097, "total_length": 42317252803}
```

The final generated DynaWord self-supervised additions contribute
`14,063,448,049` covered tokens per epoch, which is `4.998x` the retained direct
DynaWord slice (`2,813,942,923` covered tokens per epoch). No `repeat: 2` is
used for these generated task families; additional unique variants are
generated instead.

## DFM3 English Recovery Pipeline

Added on 2026-05-31. Confidence: high for local commands and dry-run inventory;
medium for final token proportions until sampling analytics are inspected.

DFM3 = DFM2 plus selected Common Pile raw-text objectives plus upweighted
approved English instruction data.

Use the stage script:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm3_english_recovery.sh --help
```

Inventory selected Common Pile sources:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm3_english_recovery.sh inventory-common-pile
```

Verified 2026-05-31 dry-run result:

```text
Estimated selected HF bytes: 275.1 GB
Selected files: 480
```

Download selected Common Pile sources:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm3_english_recovery.sh download-common-pile
```

Then run the remaining stages:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm3_english_recovery.sh all-after-download
```

Equivalent expanded sequence:

```bash
cd /work/dfm/HRM-Text
python scripts/build_filtered_source_tree.py
python scripts/convert_filtered_sources.py --copy-ready --workers 8
python scripts/generate_dfm3_common_pile_tasks.py \
  --output-root data/converted_sources_dfm3_common_pile_tasks
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm3_common_pile_tasks \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm3_common_pile_tasks
python scripts/build_tokenized_dfm3_tree.py --force
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm3 \
  output_path=../data/sampled_dfm3 \
  epochs=4 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm3.yaml \
  > ../data/show_analytics_dfm3.md
```

Important: keep tokenizer workers at `1` for the generated DFM3 task
tokenization unless the storage situation changes.

DFM3 tokenization progress must be measured by completed tokenized task
directories, not by raw file count under the output path. Each completed task
directory contains multiple files such as `tokens.npy`, `resp_start.npy`,
`resp_len.npy`, `inst_len.npy`, and `metadata.json`, so this is the reliable
progress check:

```bash
find data/tokenized_dfm3_common_pile_tasks -mindepth 1 -maxdepth 1 -type d | wc -l
find data/tokenized_dfm3_common_pile_tasks -name metadata.json | wc -l
find data/converted_sources_dfm3_common_pile_tasks -name '*.parquet' | wc -l
du -sh data/tokenized_dfm3_common_pile_tasks
```

On 2026-05-31, generated DFM3 Common Pile tasks contained `2,862` Parquet input
files. At `12:07 CEST`, one-worker tokenization had completed `484 / 2862`
tokenized task dirs and written about `100G`. Confidence: high.

DFM3 paths:

```text
Generated converted Common Pile tasks: data/converted_sources_dfm3_common_pile_tasks
Tokenized Common Pile tasks:          data/tokenized_dfm3_common_pile_tasks
Tokenized DFM3 union:                 data/tokenized_dfm3
Sampled DFM3 output:                  data/sampled_dfm3
Sampling config:                      data_io/prefix_config_dfm3.yaml
Training data config:                 config/data/dfm3.yaml
Analytics:                            data/show_analytics_dfm3.md
```

## DFM4 Paragraph Reordering And Summarization Pipeline

Added on 2026-06-01. Confidence: high for commands and verified local DFM4
outputs.

DFM4 keeps DFM3 and adds paragraph-reordering plus summarization sources:

```text
Generated paragraph tasks: data/converted_sources_dfm4_paragraph_reorder
Generated summary tasks:   data/converted_sources_dfm4_summarization
Tokenized paragraph tasks: data/tokenized_dfm4_paragraph_reorder
Tokenized summary tasks:   data/tokenized_dfm4_summarization
Tokenized DFM4 union:      data/tokenized_dfm4
Sampled DFM4 output:       data/sampled_dfm4
Sampling config:           data_io/prefix_config_dfm4.yaml
Training data config:      config/data/dfm4.yaml
Analytics:                 data/show_analytics_dfm4.md
```

Inventory/download the new HF sources:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm4_paragraph_and_summarization.sh inventory-dfm4
scripts/prepare_dfm4_paragraph_and_summarization.sh download-dfm4
```

Run the normal remaining stages:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_dfm4_paragraph_and_summarization.sh all-after-download
```

Equivalent expanded sequence:

```bash
cd /work/dfm/HRM-Text
python scripts/build_filtered_source_tree.py
python scripts/convert_filtered_sources.py --copy-ready --workers 8
python scripts/generate_dfm4_tasks.py --force
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm4_paragraph_reorder \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm4_paragraph_reorder
ionice -c2 -n7 nice -n 10 ./data_io/tokenizer/target/release/tokenizer \
  data/converted_sources_dfm4_summarization \
  --tokenizer-path /work/dfm/HRM-Text/data_io/trained_tokenizers/bpe/tokenizer.json \
  --workers 1 \
  -o data/tokenized_dfm4_summarization
python scripts/build_tokenized_dfm4_tree.py --force
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm4 \
  output_path=../data/sampled_dfm4 \
  epochs=5 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm4.yaml \
  > ../data/show_analytics_dfm4.md
```

Keep tokenizer workers at `1` unless storage pressure has been re-evaluated.

Current verified DFM4 outputs on 2026-06-01:

```text
data/converted_sources_dfm4_summarization:                     2.5G, 4019 Parquet files
data/tokenized_dfm4_summarization:                             6.6G, 4019 tokenized task dirs
data/tokenized_dfm4_paragraph_reorder_dynaword_windows:        3.2G, 25 tokenized task dirs
data/tokenized_dfm4_paragraph_reorder_common_existing:         425 symlinked task dirs
data/tokenized_dfm4:                                           9158 linked task dirs
data/sampled_dfm4:                                             1.2T
```

`data/sampled_dfm4/metadata.json` reports:

```json
{"max_seq_len": 4097, "total_length": 72007089569}
```

The sampled output stores one large `tokens.npy` plus per-epoch `inst_*` and
`resp_*` arrays under `epoch_0` through `epoch_4`; there is no single
`epoch_indices.npy` file. The five epoch index directories were rewritten on
2026-06-01 at `20:32-20:33 CEST`. Confidence: high.

Important targeted-regeneration note, 2026-06-01. Confidence: high.
`scripts/generate_dfm4_tasks.py --only paragraph --force` was updated to sample
multiple paragraph windows per long document. A full DFM4 paragraph
regeneration was stopped because Common Pile paragraph generation became slow
on large shards. The final union therefore uses:

```text
new DynaWord paragraph-window tokenization:
  data/tokenized_dfm4_paragraph_reorder_dynaword_windows
existing complete Common Pile paragraph tokenization:
  data/tokenized_dfm4_paragraph_reorder_common_existing
```

Do not use the partially regenerated
`data/converted_sources_dfm4_paragraph_reorder` Common Pile contents as a
complete paragraph source tree. If a fully fresh paragraph tree is required,
rerun paragraph generation end-to-end and expect it to take substantially
longer than the DynaWord-only targeted replacement.

Operational note: DFM4 sampling can hold about `1.2T` RSS while writing the
final `tokens.npy`, and can spend minutes in kernel I/O wait after the
`Writing tokens` progress bar reaches `9158/9158`. Let it finish rather than
restarting unless it errors.

## DFM5 Tokenized Tree And Accepted Exports

Last updated: 2026-06-12
Confidence: high
Scope: Local DFM5 preparation commands and tokenizer changes.

DFM5 uses:

- `data/tokenized_original_sapient` filtered by
  `data/filtered_sources/sapient_cleaned`, preserving original Sapient task
  names and sampling prefixes;
- selected Danish and non-Danish mixed-source tokenized tasks from
  `data/tokenized_mixed`;
- DFM4 summarization tokenized tasks from `data/tokenized_dfm4_summarization`;
- accepted-only exported JSONL.GZ task datasets after tokenization into
  `data/tokenized_dfm5_exports`.

The Rust tokenizer now supports `.jsonl.gz` input rows with either
`condition`/`instruction`/`response` or chat `messages`. A one-shard smoke run
from `export/danish-dynaword-paragraph-reordering` succeeded on 2026-06-12.

Tokenize the accepted export datasets:

```bash
cd /work/dfm/HRM-Text
WORKERS=1 scripts/tokenize_dfm5_exports.sh
```

The audited raw-task exports are read from `export/<dataset>/audited/data`.
The transformation exports are read from `export/<dataset>/data`, because the
expert export builder wrote only accepted rows for those datasets. If the
normal `/work/dfm/HRM-Text` path is temporarily not visible but an existing
process still holds the checkout open, the wrapper can be run through that
process' cwd handle, for example:

```bash
cd /
WORKERS=1 /proc/478730/cwd/scripts/tokenize_dfm5_exports.sh
```

Then build the DFM5 tokenized union:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_dfm5_tree.py --force
```

Dry-run build before export tokenization, verified on 2026-06-12:

```text
sapient_linked_tasks:       4,891
danish_mixed_linked_tasks:     54
extra_mixed_linked_tasks:     139
summarization_linked_tasks: 4,019
export_linked_tasks:           0
total_tasks:                9,103
sapient_missing_tasks:         []
```

Final export-tokenized counts, verified on 2026-06-12:

```text
common-pile-denoising:                    477 task dirs,   321,874,205 tokens
common-pile-paragraph-reordering:          30 task dirs,    62,098,317 tokens
common-pile-prefix-continuation:          477 task dirs,   429,844,139 tokens
common-pile-span-filling:               1,431 task dirs,   302,093,149 tokens
danish-dynaword-denoising:                 90 task dirs,    98,232,115 tokens
danish-dynaword-paragraph-reordering:      25 task dirs,    49,706,915 tokens
danish-dynaword-prefix-continuation:       90 task dirs,    76,473,360 tokens
danish-dynaword-span-filling:             270 task dirs,    76,165,391 tokens
transformations-danish-danish:            250 task dirs,   203,867,639 tokens
transformations-danish-english:           250 task dirs,   187,177,032 tokens
transformations-english-danish:           409 task dirs,   168,463,570 tokens
transformations-english-english:          388 task dirs,   136,630,930 tokens
total export tasks:                     4,187 task dirs, 2,112,626,762 tokens
```

Final DFM5 tokenized union build, verified on 2026-06-12:

```text
sapient_linked_tasks:        4,891
danish_mixed_linked_tasks:      54
extra_mixed_linked_tasks:      139
summarization_linked_tasks:  4,019
export_linked_tasks:        4,187
total_tasks:               13,290
sapient_missing_tasks:         []
```

Sample DFM5 after the exports have been tokenized and the union rebuilt:

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm5 \
  output_path=../data/sampled_dfm5 \
  epochs=5 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm5.yaml \
  > ../data/show_analytics_dfm5.md
```

Training config: `config/data/dfm5.yaml`.

## MPS Partial Original-Sapient Smoke

Added upstream on 2026-05-25. Confidence: high for the upstream-reported
commands and outputs.

For the MPS branch partial original-Sapient smoke work on 2026-05-25, the release binary was already built and could be run from the repo root against the partially downloaded completed Sapient files:

```bash
cd /Users/petersk/Nobackup/HRM-Text-mps
data_io/tokenizer/target/release/tokenizer \
  data/downloads/datasets/sapient_cleaned/data_clustered \
  data/downloads/datasets/sapient_cleaned/data \
  --tokenizer-path data_io/trained_tokenizers/bpe/tokenizer.json \
  -o data/tokenized_original_sapient_partial \
  --workers 12
```

Verified result: after stopping a still-running background downloader, `490` completed input files produced `490` `metadata.json` files under `data/tokenized_original_sapient_partial`, about `83G` total. A final tokenizer validation scan reported `Processing 0 files on 11 threads...`. The tokenizer skipped already-completed output directories across restarts, so it is safe to resume the same output path when increasing or lowering worker count. Confidence: high.

Rust build note: the tokenizer crate uses Rust edition 2024, so Cargo/Rust 1.83 was too old. Updating stable Rust to 1.95.0 allowed `cargo build --release --bin tokenizer` to complete. Confidence: high.

## Sample

Do not jump straight from tokenization into final training data for the mixed corpus. The current working sequence after tokenization completes is:

1. Confirm all tokenized source files exist:

   ```bash
   find /work/dfm/HRM-Text/data/tokenized_mixed -name metadata.json | wc -l
   du -sh /work/dfm/HRM-Text/data/tokenized_mixed
   ```

   Expected count for the current converted tree is `1317`.

2. Inspect token counts and source distribution before sampling.

3. Create or update a mixed sampling config for the filtered mixed data.

4. Run the sampler to produce `data/sampled`.

5. Train with `config/data/hlm.yaml`, which points at `data/sampled`.

The default `data_io/sample_tokenized.py` config was written for the original HRM/Sapient-style sources. The mixed corpus also includes Nemotron, AllenAI, Synquid, Danish DynaWord, and other sources, so review source balance before treating the sampled output as final.

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_mixed \
  output_path=../data/sampled \
  epochs=4 \
  > ../data/show_analytics.md
```

Partial original-Sapient smoke sample, verified on 2026-05-25:

```text
Tokenized subset view: data/tokenized_original_sapient_partial_smoke
Sampled output:        data/sampled_original_sapient_partial_smoke
```

The subset view symlinks three small completed tokenized SYNTH task directories and copies `tokenizer_info.json`. Sampling command:

```bash
cd /Users/petersk/Nobackup/HRM-Text-mps/data_io
conda run -n hrm python sample_tokenized.py \
  tokenized_path=../data/tokenized_original_sapient_partial_smoke \
  output_path=../data/sampled_original_sapient_partial_smoke \
  epochs=1 \
  concat_workers=2
```

Verified result: `data/sampled_original_sapient_partial_smoke` is about `519M`, with `metadata.total_length=21,359,878`, `max_seq_len=4097`, and one epoch covering `60,000` rows. Confidence: high.

## Config Path

`config/data/hlm.yaml` points HRM-Text at repo-local sampled data:

```text
data/sampled
```

For the original Sapient L reproduction run, use `config/data/original_sapient.yaml` instead:

```text
data/sampled_original_sapient
```

Do not reuse `data/tokenized_mixed` or `data/sampled` for the original Sapient reproduction run. See [[original-l-reproduction]].

For the third `original ∪ mixed` dataset, use a separate symlinked tokenized view and sampled output:

```text
Original plus mixed tokenized view: data/tokenized_original_plus_mixed
Original plus mixed sampled path:   data/sampled_original_plus_mixed
Original plus mixed data config:    config/data/original_plus_mixed.yaml
Original plus mixed analytics:      data/show_analytics_original_plus_mixed.md
```

Build the tokenized view:

```bash
cd /work/dfm/HRM-Text
python scripts/build_tokenized_original_plus_mixed_tree.py --force
```

Verified on 2026-05-23 after the mixed tokenizer had additional outputs: this linked `5,212` original Sapient tokenized task directories and `226` non-Sapient mixed task directories, skipped `1,139` mixed `sapient_cleaned__*` task directories to avoid double-counting sources already present in the full original Sapient tokenization, and produced `5,438` task directories total. The manifest is:

```text
data/tokenized_original_plus_mixed/union_manifest.json
```

Sample the third dataset:

```bash
cd /work/dfm/HRM-Text/data_io
python sample_tokenized.py \
  tokenized_path=../data/tokenized_original_plus_mixed \
  output_path=../data/sampled_original_plus_mixed \
  epochs=4 \
  concat_workers=4 \
  > ../data/show_analytics_original_plus_mixed.md
```

Verified on 2026-05-23: this completed successfully with `ionice -c2 -n7 nice -n 10`, wrote `data/sampled_original_plus_mixed`, and produced metadata:

```text
max_seq_len: 4097
total_length: 46,825,293,021
rows per epoch: 111,058,569
output size: 1.2T
```

The analytics report is:

```text
data/show_analytics_original_plus_mixed.md
```

Analytics global summary:

```text
Total unique tokens sampled: 73,008,641,849 / 216,160,760,173 (33.78%)
Total unique rows sampled:   230,146,020 / 718,222,737 (32.04%)
```

Comparison to `data/sampled_original_sapient`, verified on 2026-05-23: `original ∪ mixed` is not materially oversampling the original categories. Categories common to the original sample contribute `56,140,602,538` sampled tokens across four epochs, versus `56,140,714,711` in the original-only sample, a negligible difference. The added non-original categories contribute `131,160,569,547` sampled tokens across four epochs, or about `32.79B` tokens per epoch. Confidence: high.

A less aggressive union sampling config is available at:

```text
data_io/prefix_config_original_plus_mixed_balanced.yaml
```

It keeps the original Sapient prefix policy intact but adds caps for large mixed additions such as Nemotron Multilingual, DynaWord, Oliver Kinch translation, DOLCI, Tulu, and AllenAI reasoning traces. Estimated from the completed analytics on 2026-05-23, before resampling: mixed additions would drop from about `32.79B` sampled tokens per epoch to about `11.02B`, making the whole union about `25.06B` tokens per epoch instead of `46.83B`. Confidence: medium, because this estimate uses per-task average token lengths rather than a completed resample.

A Danish-instruction-rich variant is available at:

```text
data_io/prefix_config_original_plus_mixed_danish_instruction_rich.yaml
```

It keeps the same non-Danish mixed caps as the balanced config and keeps the balanced raw continuation / pure translation volume:

```text
danish_dynaword__, opus__, oliverkinch_machine_translation_*, synquid_translation_100k__
```

and increases Danish instruction/reference-like sources:

```text
dbc__, lexdk__, synquid_danish_verifiable_reasoning__, synquid_ifbench_train__,
oliverkinch_*_bt__, oliverkinch_multi_wiki_qa_high_quality__,
oliverkinch_eur_lex_sum_instruct__
```

Estimated from the completed analytics on 2026-05-23, before resampling: mixed additions would be about `13.65B` tokens per epoch. Continuation/translation-like Danish sources remain about `3.24B` tokens per epoch, Danish instruction/reference-like sources rise from about `0.55B` to `3.68B` tokens per epoch, and other mixed instruction sources are reduced to about `6.73B` tokens per epoch. Confidence: medium.

Train from it with:

```bash
data=original_plus_mixed
```

## Known Failure Modes

- `cargo run` from `data_io` root fails because `Cargo.toml` is in `data_io/tokenizer`.
- Tokenizer processing `0 files` usually means `data/converted_sources` is missing or empty.
- `find -type f` does not count symlinks in `data/filtered_sources`; use `find -L` if inspecting symlink targets.
- `data_io/sample_tokenized.py` now sizes its epoch buffer from the actual
  sampled rows per task, including `repeat`, rather than from unique row count.
  This was fixed on 2026-06-04 after the post-training config triggered
  `ValueError: could not broadcast input array...` during repeated sampling.
  Confidence: high.

## Post-Training Transformation Refine Dataset

Added on 2026-06-04. Confidence: high for local commands and outputs; medium
for final sampling balance until synthetic rows are generated and evaluated.

Purpose: separate post-training data path for final-checkpoint refinement on
controlled text transformations: exact sentence-count summarization, tense
rewriting, child-friendly simplification, numbered fact extraction, and
non-copy paraphrasing.

Core files:

```text
scripts/prepare_posttrain_transform_refine.py
scripts/prepare_posttrain_transform_refine.sh
scripts/build_tokenized_posttrain_transform_refine_tree.py
data_io/prefix_config_posttrain_transform_refine.yaml
config/data/posttrain_transform_refine.yaml
```

Downloaded sources:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_posttrain_transform_refine.sh download-existing
```

This downloads `grammarly/coedit`, `Muennighoff/natural-instructions`, and
`facebook/asset` into `data/downloads/datasets/posttrain_*`. Inventory on
2026-06-04 estimated about `3.6G`, mostly Super-NI.

Convert existing supervised rows:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_posttrain_transform_refine.sh convert-existing
```

Verified local output:

```text
data/converted_sources_posttrain_transform_refine/posttrain_coedit/data/train.parquet
  70,783 rows
data/converted_sources_posttrain_transform_refine/posttrain_superni_filtered/data/train.parquet
  500,000 rows across 64 filtered transformation-style Super-NI tasks
```

ASSET is not used as direct supervised training data because it only exposes
validation/test simplification splits locally. It is used as seed text for
synthetic simplification/transformation requests.

Create synthetic teacher-model requests:

```bash
cd /work/dfm/HRM-Text
scripts/prepare_posttrain_transform_refine.sh make-synthetic-requests
```

Verified local output: `10` request JSONL files under
`data/synthetic_requests_posttrain_transform_refine`, one for each combination
of five task families and two languages (`en`, `da`), with `50,000` requests
each (`500,000` total). These are request/seed files only; they are not sampled
until a Gemma teacher has generated responses and `convert-synthetic` has
accepted them.

Generate synthetic responses later using an OpenAI-compatible Gemma teacher
server:

```bash
cd /work/dfm/HRM-Text
GEMMA_OPENAI_BASE_URL=http://127.0.0.1:8000/v1 \
GEMMA_TEACHER_MODEL=gemma-4-31b \
scripts/prepare_posttrain_transform_refine.sh generate-synthetic
scripts/prepare_posttrain_transform_refine.sh convert-synthetic
```

The generator stores raw generations in
`data/generated_posttrain_transform_refine` and accepted ready rows in
`data/converted_sources_posttrain_transform_refine_synthetic`. Validation
checks include non-empty output, max length, exact two-sentence count for
summary tasks, exact five numbered items for extraction tasks, and a placeholder
copy-ratio policy for non-copy rewrites.

Sharded 8-GPU vLLM generation path, added on 2026-06-04. Confidence: high for
local sharding and syntax checks; medium for vLLM launch until the target Gemma
model path is provided and servers are started.

The request queue is already split locally:

```text
data/synthetic_request_shards_posttrain_transform_refine/pending
  500 shards
  1,000 requests per shard
  500,000 requests total
```

The sharding command is:

```bash
cd /work/dfm/HRM-Text
FORCE_SHARDS=1 REQUESTS_PER_SHARD=1000 \
scripts/prepare_posttrain_transform_refine.sh shard-synthetic-requests
```

The 8-GPU single-server-per-GPU runner is:

```bash
cd /work/dfm/HRM-Text
GEMMA_MODEL_PATH=<hf-id-or-local-path> \
SERVED_MODEL_NAME=posttrain-gemma-teacher \
GPU_LIST=0,1,2,3,4,5,6,7 \
REQUESTS_PER_SHARD=1000 \
CLIENT_CONCURRENCY=8 \
scripts/run_posttrain_synthetic_generation_vllm.sh
```

It starts one vLLM OpenAI API server per GPU on ports `8100..8107`, then starts
one worker per GPU. Workers atomically move shards from `pending` to `running`,
write generations to `data/generated_posttrain_transform_refine`, and move
completed shards to `done`. Failed shards go to `failed`.

Progress command:

```bash
cd /work/dfm/HRM-Text
python scripts/report_posttrain_synthetic_generation_progress.py
```

Use `--watch` for repeated status output.

Tokenize and sample existing rows:

```bash
cd /work/dfm/HRM-Text
WORKERS=2 scripts/prepare_posttrain_transform_refine.sh tokenize-existing
scripts/prepare_posttrain_transform_refine.sh build-tokenized-tree
CONCAT_WORKERS=2 EPOCHS=1 scripts/prepare_posttrain_transform_refine.sh sample
```

Verified local outputs on 2026-06-04:

```text
data/tokenized_posttrain_transform_refine_existing/posttrain_coedit__data__train.parquet
  22M
data/tokenized_posttrain_transform_refine_existing/posttrain_superni_filtered__data__train.parquet
  766M
data/tokenized_posttrain_transform_refine/union_manifest.json
  4,117 linked tasks: 4,115 selected existing DFM4/relevant tasks plus 2 new tasks
data/sampled_posttrain_transform_refine/metadata.json
  total_length: 29,131,369,710 tokens for one epoch
data/show_analytics_posttrain_transform_refine.md
  analytics report
```

## Tokenizer Resource Behavior

Verified from `data_io/tokenizer/src/main.rs` on 2026-05-21:

- The tokenizer streams input rows from JSONL/Parquet, but it does not stream output.
- Each worker tokenizes one whole input file into in-memory vectors:
  - `all_tokens: Vec<u32>`
  - `inst_start`, `inst_len`, `resp_start`, `resp_len`
- Only after the entire file has been read and tokenized does the worker create the output directory and write five `.npy` files plus `metadata.json`.
- Running more workers multiplies peak resident memory by the largest active files, and also creates synchronized large write bursts when several workers finish near the same time.
- Staging source files in `/dev/shm` adds tmpfs memory pressure equal to staged compressed source size. Writing tokenized output to `/dev/shm` can temporarily duplicate data: tokens exist in process memory and then also as tmpfs pages.

Operational consequence: this binary is not equivalent to a fully streaming high-throughput tokenizer. For large files, either split inputs first, keep worker count conservative, or patch the tokenizer to shard/flush output incrementally.
