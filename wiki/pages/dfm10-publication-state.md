---
type: Dataset Inventory
title: DFM10 Publication and Sampling State
description: Current Hugging Face publication completeness and the remaining final-sampling delta.
tags: [dfm10, datasets, hugging-face, sampling]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM10 Publication and Sampling State

Direct reconciliation against the public `schneiderkamplab` Hugging Face
namespace on 2026-08-31 found all 71 materialized
`exports_dfm10/dfm10-*` packages present. No materialized package remains to
upload.

The individual package records in `exports_dfm10/manifest.json` are
authoritative. Its top-level `uploaded_packages` list and generated README are
a stale 65-package summary that omits the English and Danish MedQuAD packages
plus the Mimir BoolQ, DROP, event-coreference, and IFEval packages. All six are
present on the Hub.

Publication completeness does not imply sampling completeness. The current
`data/sampled_dfm10` snapshot contains 103,143,215,009 tokens per epoch and
predates the four Mimir benchmark campaigns, the two MedQuAD packages, and the
equal one-million-row caps for each Folketing task family. Rebuild the sampled
epochs from the current 15,745-task tokenized union before treating DFM10 as
final.
