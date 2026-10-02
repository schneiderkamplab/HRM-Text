---
type: Reference
title: DFM12 Training Composition Report
description: Evidence boundaries for language and task-family token accounting and corruption statistics.
tags: [dfm12, datasets, multilingual, reporting]
status: draft
last_updated: 2026-10-02
confidence: high
---
# DFM12 Training Composition Report

The report requested on 2026-10-02 concerns the active XL epoch-11 mixture,
`data/sampled_dfm12_xl_epoch11_noidentity/epoch_10`, not the older
`data/sampled_dfm12` snapshot. Its build receipt records 103,215,092,251 base
tokens plus 13,785,598,511 addition tokens, totaling 117,000,690,762 tokens.
There are 235,520,711 base rows plus 48,859,993 addition rows, totaling
284,380,704 sampled rows. Identity repeat is zero. Counts include sampling
repeats and input plus response tokens, not only supervised response tokens.

## Accounting Rules

- Task-family names follow the multilingual evaluation report, but broad SFT
  sources are not automatically instruction-following benchmark supervision.
- Keep mixed or unclassified sources explicit. An absent attribution is not
  evidence that the dataset contains zero examples of a task.
- Distinguish exact sampled counts, source inventories, and estimates.
- Spelling/grammar classification must come from recorded corruption metadata,
  not from edit distance. An edit can be grammatical, orthographic, stylistic,
  or a consequence of another edit.
- Distinct corruption rules and distinct original-to-corrupted substitutions
  are different diversity measures; label them separately.
- State whether a percentage denominator is all sampled training rows or only
  correction rows. Keep clean controls and missing metadata visible in
  mistake-count distributions. Never treat missing metadata as zero mistakes.

## Recovered Provenance and Regeneration

2026-10-02 update supersedes the missing-inherited-provenance and Danish-unknown
claims in the initial report notes below. Recovery from `ssh.cloud.sdu.dk:6768`
(`/work/dfm/HRM-Text`) is preserved in
`data/provenance/dfm11_remote_20261002`. All 16,023 source tasks reconcile with
the corrected sampling log; 48,015 token probes match the local backing store.
All 103,215,092,251 inherited rendered tokens now have source attribution.
Language and semantic family attribution remain incomplete for broad sources;
unknown language is not unknown provenance.

The regenerated two-page PDF includes million tokens and both whole-epoch token
and row percentages in each composition cell. Correction statistics cover
16,874,605 sampled rows / 5,870,903,549 tokens, including inherited sources.
Missing corruption annotations remain unknown. Actual sampled TV2R test/train/
validation and CoEdit train/validation exposure is retained; this report does
not assert held-out decontamination. Both PDF pages contain all 21 languages.

To regenerate from the recovered JSON analysis, run only the final report-builder
and LuaLaTeX commands below. Do not rerun the additions-only accounting commands
over the recovered reports without subsequently reapplying inherited recovery.

## Reproduction

CPU-only, read-only source accounting; no sampling, GPU or W&B changes:

```bash
python scripts/dfm12_training_composition.py
python scripts/dfm12_training_composition.py --refine-only
python scripts/dfm12_error_composition.py
python -m scripts.build_dfm12_composition_report
lualatex -interaction=nonstopmode -halt-on-error -output-directory=docs/reports docs/reports/dfm12_training_composition_report.tex
```

Outputs live under `docs/reports/`: `dfm12_training_composition.json`,
`dfm12_error_composition.json`, and `dfm12_training_composition_report`
with JSON, LaTeX and PDF extensions. The two-page A3 landscape report retains
all nine evaluation-family columns, plus mixed SFT and other categories.
Unassigned inherited tokens are explicitly visible: 88.22% of the epoch lacks
a locally recoverable source-offset map. This is a partial family attribution,
not a complete measurement of language exposure. Recovering that map or the
exact original tokenized source union is necessary to fill the inherited part.

The correction report joins accepted input/target sentences to train-only
producer records, validates recorded edits by reconstructing the corrupted
sentence, and weights matching rows using the actual sampled indices. It
reports spelling/grammar row and token shares, rule and edit-pair diversity,
and 0/1/2/3/4+/unknown corruption-operation distributions. Generic deletion
and swap labels remain unclassified rather than being assumed grammatical.
The Danish inherited correction portion remains unknown.

Completed report verification: two PDF pages, all 21 language rows on both
pages, exact token reconciliation, and 13 focused tests pass. The correction
scan identifies 12,773,305 sampled rows / 1,480,965,277 rendered tokens across
20 non-Danish languages. This is not the full corpus's correction total.

See [DFM12 status](dfm12-status.md) and
[multilingual evaluation populations](multilingual-headline-populations.md).
