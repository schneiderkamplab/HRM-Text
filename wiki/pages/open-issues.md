# Open Issues

Last updated: 2026-06-01
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

DFM4 status on 2026-06-01: tokenization is already complete for the current
DFM4 generated tasks, and the active open step is resampling after the latest
`prefix_config_dfm4.yaml` cap/repeat edits. The existing tokenized DFM4 trees
do not contain the harsh-robots FLAN patterns checked
(`natural_questions_open`, `naturalquestion`, `msmarco`, `wmt`, `newscomm`).
Some stale converted Natural Questions files remain under
`data/converted_sources`, but they are not present in `data/tokenized_mixed`,
`data/tokenized_dfm3`, or `data/tokenized_dfm4`; do not rebuild tokenized trees
from stale converted sources without rerunning conversion from
`data/filtered_sources`.

Next DFM4 step:

```bash
cd /work/dfm/HRM-Text/data_io
ionice -c2 -n7 nice -n 10 python sample_tokenized.py \
  tokenized_path=../data/tokenized_dfm4 \
  output_path=../data/sampled_dfm4 \
  epochs=4 \
  concat_workers=4 \
  prefix_config_path=prefix_config_dfm4.yaml \
  > ../data/show_analytics_dfm4.md \
  2> ../logs/tokenize/dfm4_sample_stderr.log
```

Inspect `data/show_analytics_dfm4.md` after resampling before treating the
token proportions as final.

## PII Filtering

PII filtering is not yet implemented. Higher-risk sources include real chat/user text and broad web-derived datasets. AllenAI WildChat was removed from the manifest; other chat datasets may still need scans.

Current source-policy TODO: keep auditing file-level GDPR/PII risk for Sapient
FLAN/Tasksource files under the clarified policy: Article 3 TDM for EU research
organisations is the working copyright basis when access is lawful; GDPR/PII
risk for non-public persons is the hard constraint; benchmark adjacency and
ShareAlike are not blockers. `reclor.jsonl` and `scibench.jsonl` stay out of
training by project decision and can be reserved for evaluation. `scienceqa`
is included under the same lawful-access/TDM rationale unless a later legal
review rejects that basis.

## Converter Parallelism

Converter now supports `--workers`. If conversion is slow, rerun:

```bash
python scripts/convert_filtered_sources.py --force --copy-ready --workers 32
```

## JSONL Control Characters

Some downloaded JSONL sources can contain unescaped control characters. The converter now uses `json.JSONDecoder(strict=False)` for JSONL and literal-string parsing. If parsing still fails, it raises an error with the source file and line number.
