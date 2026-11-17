---
type: Reference
title: DFM9 Added Source Inventory
description: Source-level bounded-choice applicability and provenance for the DFM8-13 review.
tags: [decision-datasets, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM9 Added Source Inventory

Part of [DFM8-13 review](middle-datasets.md). Review only; no new conversion or admission.

Evidence: [new-source history](../dfm9-plan/new-source-additions-code-math-english-instruction.md), [extension history](../dfm9-plan/dfm9-extension-huggingface-org-scan.md), [new-source converter](../../../scripts/convert_dfm9_new_sources.py), [extension converter](../../../scripts/convert_dfm9_extension.py), and [current downloader](../../../scripts/download_training_datasets.py). Historical pages contain abbreviated/obsolete source names; exact IDs below follow the executable local source mappings. This is a documented reconciliation, not a silent rewrite of historical pages. Historical revision identity remains a separate ledger task.

| Source | Exact mapped HF ID | Proposed decision | Membership / pitfall |
|---|---|---|---|
| NuminaMath 1.5 | `AI-MO/NuminaMath-1.5` | B checked numeric/symbolic candidate equality; C uncheckable proof ranking | Added DFM9; later DFM10 valid-SFT replacement; preserve test exclusions. |
| Terminal Corpus | `nvidia/Nemotron-Terminal-Corpus` | B schema/exit-result checks; C next-action preference | Historical page uses lower-case alias; DFM9 flattened context, DFM10 restores native roles. |
| Code Meta Reasoning | `allenai/code-meta-reasoning-filtered` | B only if executable code/test artifacts survive; otherwise C | Historical `allenai/code_meta_reasoning` name is not the current downloader ID. Historical raw continuation conversion is poor decision supervision. |
| Natural Instructions | `Muennighoff/natural-instructions` | A recoverable closed-label tasks; B explicit validators; C open generation | DFM9 excluded 96 PII-sensitive tasks; task definitions/options must be resolved individually. Mixed corpus not blanket A. |
| CoEdIT | `grammarly/coedit` | C edit adequacy; B exact documented corruption recovery only | SFT reference does not establish unique good edit. Historical train/validation exposure needs split accounting. |
| ASSET | `facebook/asset` | C simplification adequacy / meaning preservation | Multiple good simplifications; historical licensing conflict remains separate from intrinsic suitability. |
| Nemotron SWE | `nvidia/Nemotron-SFT-SWE-v2` | B preserved deterministic test results; C patch/action preference | Historical `nvidia/nemotron-swe` alias/windowed representation; original system/tools discarded, so context-sensitive decisions may be unrecoverable from derivative. |
| CroCo Munin | `danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k` | A original chosen/rejected pair; C chosen-only derivative until pair recovery | Exact converter ID supersedes the history's abbreviated `croco-munin/apertus-8b-da-simpo-full-50k` attribution for reconstruction. |
| Danish GSM Symbolic | `danish-foundation-models/multilingual-gsm-symbolic` | B answer verification where numeric semantics recoverable | Exact converter ID differs from historical `google/multilingual_gsm_symbolic`; Danish subset, generated GSM8K-style provenance, decontamination required. |

DFM9 additionally changes factual-FLAN caps/repeats within the inherited Sapient
inventory. That is not a tenth new repository. The current source allowlist is
not inferred from old sampling weights. DFM8's 159-source table supplies the
inherited repository inventory; DFM10 exports show materialized replacements.
