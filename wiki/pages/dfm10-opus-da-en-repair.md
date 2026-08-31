---
type: Runbook
title: DFM10 OPUS DA-EN Quality Repair
description: Deterministic language, direction, and semantic-alignment filtering of the permissive OPUS Danish-English corpus.
tags: [dfm10, opus, translation, filtering, danish, english]
status: stable
last_updated: 2026-08-28
confidence: high
sources:
  - id: opus-da-en-hf
    resource: https://huggingface.co/datasets/schneiderkamplab/opus-da-en-permissive
    title: schneiderkamplab/opus-da-en-permissive
    author: org:schneiderkamplab
  - id: labse-hf
    resource: https://huggingface.co/sentence-transformers/LaBSE
    title: sentence-transformers/LaBSE
    author: org:sentence-transformers
---
# DFM10 OPUS DA-EN Quality Repair

## Rationale

The inherited `schneiderkamplab/opus-da-en-permissive` conversion contains
29,261,517 canonical Danish-English pairs and expands them into 58,523,034
directional training rows. DFM8/9/10 historically sampled at most 30M of those
rows. The 2026-08-26 source audit found 75/100 sampled rows usable. Failures
were dominated by unrelated but fluent pairings, incomplete translations,
corrupted fragments, and occasional wrong-language targets. The defects are
pair-level and should be filtered rather than regenerated at this scale.

The existing conversion also put `Source: OPUS ...` inside the text presented
for translation while omitting it from the target. The repaired conversion
keeps provenance in Parquet columns and removes it from the user-visible task.

## Filter Contract

The authoritative source is
`data/downloads/datasets/opus/opus_da_en.jsonl.gz`, with `id`, `source`, `da`,
and `en` fields. Filtering occurs once per canonical pair before producing both
translation directions.

1. Normalize Unicode and whitespace; reject blank/non-linguistic/control-text
   rows and strong source/target length mismatches.
2. Use the repository's Rust-backed Lingua dependency for language and
   direction checks. Reject high-confidence swapped DA/EN sides and
   high-confidence third-language text. Short proper names are not rejected
   merely because language ID is uncertain.
3. Encode both sides with `sentence-transformers/LaBSE` and reject cosine
   similarity below `0.60`.
4. Write every scored pair to an atomic Parquet shard with language labels,
   confidence, alignment score, acceptance, and one explicit reason.
5. Emit accepted pairs in both directions without exposing provenance as
   translation input.

LaBSE is an Apache-2.0, 109-language shared-vector-space model with a 256-token
model limit. It is used here as a scalable bitext-alignment filter, not as a
general quality judge. The main residual risk is a semantically related but
incorrect translation that receives a high embedding score.

## Calibration

The initial 100-row E4B audit was rescored with the deterministic filter. At a
`0.60` LaBSE threshold, the first policy retained 71/75 judged-good examples
and rejected 16/25 judged-bad examples. A high-confidence third-language guard
then removed the Spanish-on-Danish-side case, leaving 79 deterministic accepts
in the calibration sample. Remaining false accepts were mostly related but
incomplete translations or spelling/spacing defects beyond embedding-based
filtering.

Activation requires an independent 1,000-row E4B audit of accepted pairs with
at least 90% `usable_for_training` and 85% strict three-dimension passes. All
source, scored, converted, and tokenized counts must reconcile exactly.

## Pipeline

Install the optional quality dependency with `uv` in the `hrm` environment:

```bash
uv pip install --python /home/ucloud/miniforge3/envs/hrm/bin/python \
  sentence-transformers
```

Shard once, score resumably, build the repaired tasks, and prepare the audit:

```bash
python scripts/shard_opus_da_en.py --shards 64
GPUS=0,1,2,3,4,5,6,7 bash scripts/run_opus_da_en_filter_8gpu.sh
python scripts/build_opus_da_en_repaired.py --force
python scripts/prepare_opus_da_en_reaudit.py --samples 1000
bash scripts/run_opus_da_en_reaudit_8gpu.sh
python scripts/validate_opus_da_en_repaired.py
```

Tokenization uses the Gemma 4 native chat template and 16 non-Rust workers via
`scripts/prepare_dfm10_data.sh`. Once the gate passes, DFM10 disables the
legacy `opus__` prefix and caps each of 64 balanced repaired shards at 468,750
directional rows, preserving the previous 30M-row per-epoch OPUS budget.

## 2026-08-28 Production Result

- Source sharding completed: 64 deterministic shards, exactly 29,261,517
  canonical pairs.
- LaBSE and `sentence-transformers==6.0.0` are installed in `hrm`.
- `fasttext-wheel==0.9.2` was superseded as the LID implementation because its
  bundled source did not compile under Python 3.13. Lingua is already a pinned
  project dependency and passed the calibration cases.
- Deterministic scoring accepted 20,577,773 pairs (70.3237%) and rejected
  8,683,744. The largest rejection classes were semantic misalignment
  (5,013,151), a third language on the Danish side (1,803,804), and a third
  language on the English side (1,284,865).
- Bidirectional conversion produced 41,155,546 rows in 64 balanced shards.
  Gemma-native tokenization reconciled every row and produced 3,629,237,788
  rendered tokens (15 GiB on disk).
- The independent E4B audit covered 1,000 deterministic reservoir samples:
  97.3% were usable, 87.2% passed all three dimensions at score 4 or better,
  and no judge errors occurred. Both activation gates passed.
- DFM10 now disables the legacy `opus__` prefix and caps each repaired shard
  at 468,750 rows. All shards contain 641,242--644,882 rows, so the effective
  contribution is exactly 30,000,000 directional rows per sampled epoch.
- The current generated `data/tokenized_dfm10` union was incrementally updated
  with all 64 repaired tasks. `scripts/build_tokenized_dfm10_tree.py` and
  `scripts/prepare_dfm10_data.sh` reproduce the integration on the next full
  rebuild.

The first audit launch raced a separate benchmark that reclaimed the GPUs
while vLLM initialized. No audit rows were written by that attempt. The
finisher now requires all eight GPUs to remain above the free-memory threshold
for 120 seconds before launching judges and bounds cleanup of partial server
starts. This is a scheduling guard, not a data-quality exception.
