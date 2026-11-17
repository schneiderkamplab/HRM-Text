---
type: Reference
title: DFM12 Component Inventory
description: All 381 DFM12 source components in the recovered epoch-11 composition report.
tags: [decision-datasets, dfm8, dfm9, dfm10, dfm11, dfm12, dfm13, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM12 Component Inventory

Part of [DFM8-13 source review](middle-datasets.md). Classifications are proposals, not conversion or admission results.

Evidence: [composition JSON](../../../docs/reports/dfm12_training_composition.json), `source_rows[]` filtered to `component=dfm12_additions`, grouped by exact `source`; [builder mapping](../../../dfm12/build_training.py) records `schneiderkamplab/<name>` for exported packages. The 24 local DaLA components instead use the exact [12-repository reuse map](../../../docs/reports/dfm12_inherited_dala_upload_targets_20261004.json). Namespace-derived package IDs below are code-backed mappings, not independently reopened upload receipts. Missing local export roots prevent fresh pin verification.

Rows are sampled epoch-11 rows, not unique source rows. Zero identity rows are intentional: this active no-identity snapshot differs from later approved DFM13 identity weighting. Inheritance later uses all 381 components once over DFM11, not old DFM12 plus 381. Generic text/DynaWord packages contain transformations: B only after routing by recorded task; unclassified constituent tasks remain C/D.

| Component | Exact HF destination / producer ID | Epoch-11 rows | Proposed applicability |
|---|---|---:|---|

| `dfm12-reordering-integrated-nb-paragraph-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nb-paragraph-reordering` | 47492 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-nb-text-block-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nb-text-block-reordering` | 18835 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-nl-paragraph-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nl-paragraph-reordering` | 34536 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-nl-text-block-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nl-text-block-reordering` | 13667 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-nn-paragraph-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nn-paragraph-reordering` | 19650 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-nn-text-block-reordering` | `schneiderkamplab/dfm12-reordering-integrated-nn-text-block-reordering` | 5403 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-sv-paragraph-reordering` | `schneiderkamplab/dfm12-reordering-integrated-sv-paragraph-reordering` | 45422 | B/C: Original-order recovery / valid next block |
| `dfm12-reordering-integrated-sv-text-block-reordering` | `schneiderkamplab/dfm12-reordering-integrated-sv-text-block-reordering` | 31047 | B/C: Original-order recovery / valid next block |
| `dfm12-scandi-included-da` | `schneiderkamplab/dfm12-scandi-included-da` | 152168 | C: Task-routed candidate response judgment |
| `dfm12-scandi-included-nb` | `schneiderkamplab/dfm12-scandi-included-nb` | 97270 | C: Task-routed candidate response judgment |
| `dfm12-scandi-included-nn` | `schneiderkamplab/dfm12-scandi-included-nn` | 48974 | C: Task-routed candidate response judgment |
| `dfm12-scandi-included-no` | `schneiderkamplab/dfm12-scandi-included-no` | 1475 | C: Task-routed candidate response judgment |
| `dfm12-scandi-included-sv` | `schneiderkamplab/dfm12-scandi-included-sv` | 155416 | C: Task-routed candidate response judgment |
| `dfm12-smoltalk2-chat-en` | `schneiderkamplab/dfm12-smoltalk2-chat-en` | 101071 | C: Task-routed candidate response judgment |
| `dfm12-text-ca` | `schneiderkamplab/dfm12-text-ca` | 260240 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-cs` | `schneiderkamplab/dfm12-text-cs` | 258615 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-de` | `schneiderkamplab/dfm12-text-de` | 254171 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-el` | `schneiderkamplab/dfm12-text-el` | 258325 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-es` | `schneiderkamplab/dfm12-text-es` | 251016 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-et` | `schneiderkamplab/dfm12-text-et` | 259028 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-fi` | `schneiderkamplab/dfm12-text-fi` | 258582 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-fr` | `schneiderkamplab/dfm12-text-fr` | 242057 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-it` | `schneiderkamplab/dfm12-text-it` | 253458 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-pt_pt` | `schneiderkamplab/dfm12-text-pt_pt` | 248785 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-ro` | `schneiderkamplab/dfm12-text-ro` | 244010 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-text-uk` | `schneiderkamplab/dfm12-text-uk` | 251171 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-trustllm-ca` | `schneiderkamplab/dfm12-trustllm-ca` | 761 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-cs` | `schneiderkamplab/dfm12-trustllm-cs` | 848 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-da` | `schneiderkamplab/dfm12-trustllm-da` | 835 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-de` | `schneiderkamplab/dfm12-trustllm-de` | 232 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-el` | `schneiderkamplab/dfm12-trustllm-el` | 557 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-en` | `schneiderkamplab/dfm12-trustllm-en` | 877 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-es` | `schneiderkamplab/dfm12-trustllm-es` | 666 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-et` | `schneiderkamplab/dfm12-trustllm-et` | 618 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-fi` | `schneiderkamplab/dfm12-trustllm-fi` | 758 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-fo` | `schneiderkamplab/dfm12-trustllm-fo` | 682 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-fr` | `schneiderkamplab/dfm12-trustllm-fr` | 774 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-is` | `schneiderkamplab/dfm12-trustllm-is` | 600 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-it` | `schneiderkamplab/dfm12-trustllm-it` | 800 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-nb` | `schneiderkamplab/dfm12-trustllm-nb` | 759 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-nl` | `schneiderkamplab/dfm12-trustllm-nl` | 599 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-nn` | `schneiderkamplab/dfm12-trustllm-nn` | 783 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-pl` | `schneiderkamplab/dfm12-trustllm-pl` | 827 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-pt_pt` | `schneiderkamplab/dfm12-trustllm-pt_pt` | 935 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-ro` | `schneiderkamplab/dfm12-trustllm-ro` | 867 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-sv` | `schneiderkamplab/dfm12-trustllm-sv` | 904 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-trustllm-uk` | `schneiderkamplab/dfm12-trustllm-uk` | 734 | C: reformulation equivalence; prompt lineage alone supplies no negative |
| `dfm12-ultrachat-nl` | `schneiderkamplab/dfm12-ultrachat-nl` | 673370 | C: Task-routed candidate response judgment |
