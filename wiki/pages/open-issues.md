# Open Issues

Last updated: 2026-05-25  
Confidence: medium  
Scope: Known blockers, risks, and future improvements.

## Full Training Validation

The attention code was smoke-tested, but a real training step remains unverified until tokenized/sampled data exists.

Superseded in part on 2026-05-25: tiny 3-step training diagnostics now verify the dense PrefixLM backend with finite loss/gradients/parameters, using `scripts/create_tiny_sampled_dataset.py` and `scripts/debug_nan_training_step.py`. The explicit `cpu` backend was verified in a fresh Python 3.13 `hrm` conda env with `torch==2.13.0.dev20260524`. Actual Apple GPU MPS execution was also verified outside the sandbox on the same M2 Max machine; the earlier `torch.backends.mps.is_available() == False` result was caused by sandbox device visibility. Confidence: high.

## Conversion Coverage

`scripts/convert_filtered_sources.py` supports:

- already-normalized `condition/instruction/response`
- `prompt/target`, with optional `reasoning`
- `instruction/output`
- `messages`
- DynaWord `text` continuation chunks

Unknown schemas are skipped and should be reviewed after conversion completes.

## Gated Datasets

Current download run used `--exclude-gated`, so gated datasets are absent unless downloaded later with a token that has accepted access.

## Token-Budgeted Sampling

The current `data_io/sample_tokenized.py` samples by per-source rules and repeats. A future script should enforce explicit token budgets per bucket for a 40B run.

Before producing final `data/sampled` for the current mixed corpus:

1. Wait for tokenization to finish and confirm `1317` tokenized source metadata files.
2. Inspect token counts and source distribution.
3. Create/update a mixed sampling config or token-budgeted sampler.
4. Run sampling into `data/sampled`.
5. Train using `config/data/hlm.yaml`.

## PII Filtering

PII filtering is not yet implemented. Higher-risk sources include real chat/user text and broad web-derived datasets. AllenAI WildChat was removed from the manifest; other chat datasets may still need scans.

## Converter Parallelism

Converter now supports `--workers`. If conversion is slow, rerun:

```bash
python scripts/convert_filtered_sources.py --force --copy-ready --workers 32
```

## JSONL Control Characters

Some downloaded JSONL sources can contain unescaped control characters. The converter now uses `json.JSONDecoder(strict=False)` for JSONL and literal-string parsing. If parsing still fails, it raises an error with the source file and line number.
