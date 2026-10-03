---
type: Reference
title: Mimir v1.5 Model Card and Comparison Provenance
description: Published training-data documentation and separation of standalone 2850K comparisons from the released epoch-ten checkpoint.
tags: [mimir, release, evaluation, model-card, provenance]
status: stable
last_updated: 2026-09-23
confidence: high
---
# Mimir v1.5 Model Card and Comparison Provenance

User-authorized publication: [card update](https://huggingface.co/danish-foundation-models/DFM-Mimir-v1.5/commit/cc57cebadf375947ced5ccd3317d9da6bf8f9677).

## Checkpoint identity

The released final epoch-10 EMA is step 2,877,261, weight SHA256
`226257d0d6c5dc04d920e48bb7079c3361dcf0866a950f4667bfcc9ae7bb6e48`.
Standalone HRM-test evaluated step 2,850,000 EMA, weight SHA256
`1e995a7daa3a15696d67552266b82092ba0ec650c4e86f20a43955ccd39c2179`.
The card labels the latter as a nearby checkpoint, not measurements of the
released weights. The original card lists 1,750,000 training steps while
the standalone baseline is 1,650,000; family names do not prove identity.

## Comparison and training-data contract

There are 18 current model/checkpoint/mode rows. Category means weight seven
English, three Math/Code and ten Danish task metrics equally. Munin is
Danish-only. Mimir 2850K means are 77.80660975659963, 71.11563182258054 and
62.97261975652402. Gemma E4B thinking PIQA is complete: 108 samples,
accuracy 0.6944444444444444. All category means were recomputed and checked.

Revised HellaSwag-DA includes the letter-only instruction. AngryTweets uses
macro F1, Nordjylland ROUGE-1, and IFEval prompt-strict accuracy. Original
v1 tables, including HRM-Text 1B and E2B thinking, are retained separately
because of metric/prompt differences. Runtime, few-shot and token-budget
differences are documented. Exact released-checkpoint training-integrated
results are preserved separately from the standalone comparison.

The card distinguishes original DFM8 70.479B sampled tokens per epoch from
DFM11's 103,214,604,702. Final-epoch training resumes DFM10 at step 2,482,084.
Eleven public addition revisions and the sampling policy are packaged;
non-public/agreement-backed base material is still required for reproduction.
See [DFM11 portability](dfm11-portability.md) and
[XL epoch-ten resume](dfm11-xl-epoch10-resume.md).

## Provisional Compute Estimate (2026-09-23)

Not a measured billing total or an approved published model-card statistic.
Under the user's simplifying assumption of 2,870,000 steps, each with 262,144
tokens, exposure is 752,353,280,000 tokens. Actual release is step 2,877,261;
historical batch sizes, rollback/replay and lineage branches require accounting
before presenting exact totals.

XL geometry: 16 layers per H/L block, width 1536, MLP 4096, vocabulary 262144,
H2/L3 means eight block forwards. A matmul estimate per token is
`2 * 16 * (4*d*d + 3*d*i) * (8 + 2*BP) + 6*d*v`, plus
`4 * 16 * d * average_attended_keys * (8 + 2*BP)` for attention.
BP5 yields 1.41e22 FLOPs without attention, or 1.54--1.68e22 for
1024--2048 attended keys/token. BP8 yields 1.82e22 without attention,
or 2.00--2.18e22 at those attention densities. Thus roughly 1.5--2.0e22
for the mostly-BP5 lineage with later BP8 is a planning estimate, not a
profiler measurement. Full dense-4K/BP8 throughout gives about 2.54e22.
The estimate excludes optimizer, communication, failed work and evaluation.

Inspected DFM9 XL log tails show 1.10--1.13 s/step; DFM10 BP8 tails show
1.24--1.27 s/step. At 1.1--1.3 s/step, the stated training corresponds to
about 7,000--8,300 B200 GPU-hours. Allow roughly 8,000--12,000 for earlier
slower code, checkpointing and restarts, pending full log accounting.

Synthetic generation/audit/repair cost has not been reconstructed from all
campaign logs. A very-low-confidence planning allowance is 5,000--15,000 B200
GPU-hours across the inherited data campaigns, not attributable exclusively
to this model. Do not present this allowance as measured resource usage.

## Publication artifacts (paths)

Local staging, card backups, scripts and publication receipt are in
`/work/dfm/HRM-test/model_cards/mimir_v1_5/`. Source reports are under
`/work/dfm/HRM-test/runs/three_model_full_20260922/` and
`/work/dfm/HRM-test/runs/hellaswag_da_letter_only_comparison_20260922/`.

Published README.md, comparison_results.json, comparison_macro_averages.csv,
comparison_per_task.csv, original_comparisons.md, training_data_manifest.json
and dfm11_sampling_policy.yaml. Hub ModelCard validation passed; all seven
files were downloaded at the publication revision and byte-verified.
Released weights are unchanged. No training/GPU process was modified.
