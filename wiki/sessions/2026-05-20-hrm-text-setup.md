# Session Digest: HRM-Text Setup And Data Pipeline

Last updated: 2026-05-20  
Confidence: high  
Scope: Summary of work performed in this session.

## FlashAttention

- Installed/adapted FlashAttention 4 for NVIDIA B200.
- Rejected FlashAttention 3 after source/wheel attempts failed on Blackwell.
- Updated dependencies and code paths to avoid FA3 imports.

## Data IO

- Cloned `sapientinc/data_io` under `data_io/`.
- Installed `data_io` Python requirements.
- Identified `sample_tokenized.py` defaults:
  - `tokenized_path=data_tokenized_bpe_65k`
  - `output_path=/dev/shm/sampled`
  - `epochs=10`
  - `context_size=4097`
- Adjusted HRM-Text data path to repo-local `data/sampled`.

## Dataset Review

- Established that HRM-Text expects PrefixLM instruction/response data, not plain raw causal-LM pretraining.
- Decided to include only Danish raw continuation data via DynaWord.
- Removed Common Pile from the downloader manifest.
- Removed AllenAI WildChat from the downloader manifest.
- Classified Sapient FLAN/Tasksource as broad aggregators requiring narrow allow overrides.

## Scripts Added

- `scripts/download_training_datasets.py`
- `scripts/build_filtered_source_tree.py`
- `scripts/convert_filtered_sources.py`
- `scripts/prepare_40b_sapient_plus_danish.py`

## Source Filtering

- Built source filtering policy with broad denies and narrow allow overrides.
- User reported final filtered tree:

```text
Allowed files:      1,525
Denied files:       4,073
Allowed bytes:      248,502,793,134
```

## Rust Tokenizer

- User installed Rust/Cargo.
- Correct tokenizer command must run from `data_io/tokenizer`.
- Use absolute tokenizer path to avoid accidental Hugging Face lookup.

## Current Work

- Conversion is the active next step.
- Converter now supports `--workers` for parallel per-file conversion.

