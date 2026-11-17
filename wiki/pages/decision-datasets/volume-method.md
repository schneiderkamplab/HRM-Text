---
type: Reference
title: Decision Candidate Volume Basis
description: Metadata-only volume audit distinguishing current storage, available rows, historical variants and distinct sampled examples.
tags: [decision-datasets, volume, provenance]
status: draft
last_updated: 2026-10-21
confidence: high
---
# Volume Basis

Parent: [decision dataset overview](../decision-datasets.md). This audit does
not certify a deduplicated DFM1-15 union or usable decision-target yield.

## Count Semantics

`data_io/sample_tokenized.py` computes analytics `Rows` and `Tokens` from
task indices after selection and length admission. They are available
serialized rows/tokens, not sampled repeat occurrences. `Cov Rows` and
`Cov Toks` sum coverage multiplicities across the report's epochs. Only the
global footer reports distinct covered row positions; per-task unique coverage
is computed internally but not printed. Even those uniques do not deduplicate
identical content across task files or templates. Do not divide coverage by
epochs/repeats and call the result a distinct-row count.

The October 20 current source-domain manifest at
`data/category_preparation/dfm15-epoch0-source-domains-published-20261020/category-manifest.json`
contains 38,877 ranges and 264,134,952,845 stored tokens. This is physical
backing storage, including inherited and appended repair/conditioning ranges,
not 264.135B unique selected tokens. Its ranges do not supply row counts.
The documented latest 134,516,139,170 tokens/epoch is exposure, not reservoir
or distinct union volume. Neither number answers decision-candidate yield.

## Historical Reconciliation

Bounded inspection of canonical DFM1-5 and DFM7-10 analytics retained the
latest positive observation per exact task, without summing epochs or DFM
versions. Removing only `sapient_cleaned__data_clustered__` and
`sapient_cleaned__data__`, then allowing `flan__` to match `flan_factual__`,
resolved every historical positive FLAN, Tasksource and Platypus task key
against current stored ranges. This establishes key presence, not identical
rows, current admission or preservation of all historical examples. A naive
exact-key difference would incorrectly report 266 FLAN files containing
16,495,724 available rows / 9,603,096,705 tokens as historical-only.

The following latest-numbered historical transformation variants have absent
exact keys and conditional B source-recovery uses. Counts are the latest
positive historical available counts, all observed in DFM4 analytics:

| Historical family | Available rows | Available tokens |
|---|---:|---:|
| `dfm2_dynaword_denoising_v2` | 927,476 | 1,456,578,755 |
| `dfm2_dynaword_span_fill_v6` | 927,871 | 1,418,272,107 |
| `dfm3_common_pile_denoising` | 19,043,339 | 23,724,752,985 |
| `dfm3_common_pile_span_fill_v3` | 19,043,381 | 23,790,825,523 |
| `dfm4_common_pile_paragraph_reorder` | 2,443,026 | 1,583,838,733 |
| `dfm4_dynaword_paragraph_reorder` | 939,361 | 838,269,385 |
| Separate, NOT additive to current | 43,324,454 | 52,812,537,488 |

This 52.813B subtotal is serialized historical variant volume, not a novel
increment or distinct-parent count. Denoising, span filling and reordering
share parent documents; current `common-pile-*` and `danish-dynaword-*`
derivatives also exist. Current payload availability and lineage overlap were
not established by reading historical analytics. Older numbered variants,
raw/direct continuation and prefix continuation are not added to this
conditional-B shortlist. This shortlist is not an exhaustive historical-only
A/B census.

## Reporting Contract

Report the latest physical source-variant reservoir
separately from historical candidates not added because overlap is unknown.
Canonicalize package/task aliases and apply explicit replacement maps first.
Do not describe their arithmetic sum as a certified union. A sum can be an
overlap-ignorant ceiling for that explicitly enumerated selection only, not
an upper bound for all historical DFM1-15 examples: historical snapshots and
membership coverage are incomplete, and latest versions need not contain
every earlier row.

DaLA acceptability and correction must remain separate task views, with shared
parent counts acknowledged. Do not classify every `dala` key as A. FLAN's
RACE question generation/no-option/span variants, CoS-E explanations and
QASC fact generation do not become MCQ merely through benchmark-name matches.
`flan_factual` is an alias/routing family, not a uniform label contract.
Repaired tool sources and native reasoning replacements are not independent
new corpora. Source-prefix matches require explicit precedence; the sampler
uses the first matching rule, not necessarily the longest prefix.

No payload/token-array scan or GPU work was performed. No production files
were changed. The parent assessment owns indexing and final volume tables.
