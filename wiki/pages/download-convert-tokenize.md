# Download, Convert, Tokenize, Sample

Last updated: 2026-05-23  
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

Convert filtered sources:

```bash
python scripts/convert_filtered_sources.py --copy-ready --workers 32
```

Use `--workers 64` only if storage I/O can keep up.

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
