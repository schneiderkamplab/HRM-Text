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

| `dfm12-alia-ca-es` | `schneiderkamplab/dfm12-alia-ca-es` | 296188 | C: Task-routed candidate response judgment |
| `dfm12-amalia-if` | `schneiderkamplab/dfm12-amalia-if` | 8098 | C: Task-routed candidate response judgment |
| `dfm12-amalia-persona` | `schneiderkamplab/dfm12-amalia-persona` | 153394 | C: Task-routed candidate response judgment |
| `dfm12-amalia-summarize` | `schneiderkamplab/dfm12-amalia-summarize` | 59454 | C: Evidence support / summary or rewrite adequacy |
| `dfm12-amalia-wikipedia` | `schneiderkamplab/dfm12-amalia-wikipedia` | 413424 | C: Task-routed candidate response judgment |
| `dfm12-aya-human-train` | `schneiderkamplab/dfm12-aya-human-train` | 13189 | C: Task-routed candidate response judgment |
| `dfm12-dala-ca-acceptability` | `schneiderkamplab/dala-ca-audited` | 583584 | A: Existing label or option |
| `dfm12-dala-ca-correction` | `schneiderkamplab/dala-ca-audited` | 583584 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-cs-acceptability` | `schneiderkamplab/dala-cs-audited` | 630058 | A: Existing label or option |
| `dfm12-dala-cs-correction` | `schneiderkamplab/dala-cs-audited` | 630058 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-de-acceptability` | `schneiderkamplab/dala-de-audited` | 691942 | A: Existing label or option |
| `dfm12-dala-de-correction` | `schneiderkamplab/dala-de-audited` | 691942 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-el-acceptability` | `schneiderkamplab/dala-el-audited` | 610258 | A: Existing label or option |
| `dfm12-dala-el-correction` | `schneiderkamplab/dala-el-audited` | 610258 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-en` | `schneiderkamplab/dfm12-dala-en` | 1402300 | A acceptability; B/C correction (separate configs) |
| `dfm12-dala-es-acceptability` | `schneiderkamplab/dala-es-audited` | 702898 | A: Existing label or option |
| `dfm12-dala-es-correction` | `schneiderkamplab/dala-es-audited` | 702898 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-et-acceptability` | `schneiderkamplab/dala-et-audited` | 538836 | A: Existing label or option |
| `dfm12-dala-et-correction` | `schneiderkamplab/dala-et-audited` | 538836 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-fi-acceptability` | `schneiderkamplab/dala-fi-audited` | 634358 | A: Existing label or option |
| `dfm12-dala-fi-correction` | `schneiderkamplab/dala-fi-audited` | 634358 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-fo-acceptability` | `schneiderkamplab/dfm12-dala-fo-acceptability` | 131764 | A: Existing label or option |
| `dfm12-dala-fo-correction` | `schneiderkamplab/dfm12-dala-fo-correction` | 127629 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-fr-acceptability` | `schneiderkamplab/dala-fr-audited` | 700764 | A: Existing label or option |
| `dfm12-dala-fr-correction` | `schneiderkamplab/dala-fr-audited` | 700764 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-is-acceptability` | `schneiderkamplab/dfm12-dala-is-acceptability` | 722660 | A: Existing label or option |
| `dfm12-dala-is-correction` | `schneiderkamplab/dfm12-dala-is-correction` | 704375 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-it-acceptability` | `schneiderkamplab/dala-it-audited` | 693824 | A: Existing label or option |
| `dfm12-dala-it-correction` | `schneiderkamplab/dala-it-audited` | 693824 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-nb-acceptability` | `schneiderkamplab/dfm12-dala-nb-acceptability` | 729666 | A: Existing label or option |
| `dfm12-dala-nb-correction` | `schneiderkamplab/dfm12-dala-nb-correction` | 738211 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-nl` | `schneiderkamplab/dfm12-dala-nl` | 1403084 | A acceptability; B/C correction (separate configs) |
| `dfm12-dala-nn-acceptability` | `schneiderkamplab/dfm12-dala-nn-acceptability` | 736432 | A: Existing label or option |
| `dfm12-dala-nn-correction` | `schneiderkamplab/dfm12-dala-nn-correction` | 733039 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-pl-acceptability` | `schneiderkamplab/dfm12-dala-pl-acceptability` | 737464 | A: Existing label or option |
| `dfm12-dala-pl-correction` | `schneiderkamplab/dfm12-dala-pl-correction` | 729165 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-pt-pt-acceptability` | `schneiderkamplab/dala-pt-pt-audited` | 667234 | A: Existing label or option |
| `dfm12-dala-pt-pt-correction` | `schneiderkamplab/dala-pt-pt-audited` | 667234 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-ro-acceptability` | `schneiderkamplab/dala-ro-audited` | 482388 | A: Existing label or option |
| `dfm12-dala-ro-correction` | `schneiderkamplab/dala-ro-audited` | 482388 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-sv-acceptability` | `schneiderkamplab/dfm12-dala-sv-acceptability` | 740980 | A: Existing label or option |
| `dfm12-dala-sv-correction` | `schneiderkamplab/dfm12-dala-sv-correction` | 742384 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dala-uk-acceptability` | `schneiderkamplab/dala-uk-audited` | 660926 | A: Existing label or option |
| `dfm12-dala-uk-correction` | `schneiderkamplab/dala-uk-audited` | 660926 | B/C: Known corruption/edit validity or reconstruction |
| `dfm12-dolci-nl` | `schneiderkamplab/dfm12-dolci-nl` | 287599 | C: Task-routed candidate response judgment |
| `dfm12-dolci-pl` | `schneiderkamplab/dfm12-dolci-pl` | 284481 | C: Task-routed candidate response judgment |
| `dfm12-dolci-sv` | `schneiderkamplab/dfm12-dolci-sv` | 284969 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-cs` | `schneiderkamplab/dfm12-dolci-translated-cs` | 354672 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-de` | `schneiderkamplab/dfm12-dolci-translated-de` | 348694 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-el` | `schneiderkamplab/dfm12-dolci-translated-el` | 337901 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-es` | `schneiderkamplab/dfm12-dolci-translated-es` | 359242 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-fi` | `schneiderkamplab/dfm12-dolci-translated-fi` | 313597 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-fr` | `schneiderkamplab/dfm12-dolci-translated-fr` | 349656 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-it` | `schneiderkamplab/dfm12-dolci-translated-it` | 358236 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-ro` | `schneiderkamplab/dfm12-dolci-translated-ro` | 343794 | C: Task-routed candidate response judgment |
| `dfm12-dolci-translated-uk` | `schneiderkamplab/dfm12-dolci-translated-uk` | 351342 | C: Task-routed candidate response judgment |
| `dfm12-dolly-nl-train` | `schneiderkamplab/dfm12-dolly-nl-train` | 9997 | C: Task-routed candidate response judgment |
| `dfm12-dyna-instruct-fo` | `schneiderkamplab/dfm12-dyna-instruct-fo` | 4965 | C: Task-routed candidate response judgment |
| `dfm12-dyna-instruct-is` | `schneiderkamplab/dfm12-dyna-instruct-is` | 4454 | C: Task-routed candidate response judgment |
| `dfm12-dynaword-fo` | `schneiderkamplab/dfm12-dynaword-fo` | 101281 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-dynaword-is` | `schneiderkamplab/dfm12-dynaword-is` | 162270 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-dynaword-nl` | `schneiderkamplab/dfm12-dynaword-nl` | 78699 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-dynaword-no` | `schneiderkamplab/dfm12-dynaword-no` | 370048 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-dynaword-pl` | `schneiderkamplab/dfm12-dynaword-pl` | 198590 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-dynaword-sv` | `schneiderkamplab/dfm12-dynaword-sv` | 108847 | B/C: task-routed corruption, order and masked-span recovery; inspect task metadata |
| `dfm12-eu-instruct-cs` | `schneiderkamplab/dfm12-eu-instruct-cs` | 127771 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-de` | `schneiderkamplab/dfm12-eu-instruct-de` | 129217 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-el` | `schneiderkamplab/dfm12-eu-instruct-el` | 112996 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-es` | `schneiderkamplab/dfm12-eu-instruct-es` | 127486 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-fr` | `schneiderkamplab/dfm12-eu-instruct-fr` | 112885 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-it` | `schneiderkamplab/dfm12-eu-instruct-it` | 129092 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-nl` | `schneiderkamplab/dfm12-eu-instruct-nl` | 123247 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-pl` | `schneiderkamplab/dfm12-eu-instruct-pl` | 136784 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-ro` | `schneiderkamplab/dfm12-eu-instruct-ro` | 115071 | C: Task-routed candidate response judgment |
| `dfm12-eu-instruct-uk` | `schneiderkamplab/dfm12-eu-instruct-uk` | 140422 | C: Task-routed candidate response judgment |
| `dfm12-euroblocks` | `schneiderkamplab/dfm12-euroblocks` | 994201 | C: Task-routed candidate response judgment |
| `dfm12-fleurs-alpaca-en-no` | `schneiderkamplab/dfm12-fleurs-alpaca-en-no` | 1017 | C: Task-routed candidate response judgment |
| `dfm12-identity-xl-full-bp-ca` | `schneiderkamplab/dfm12-identity-xl-full-bp-ca` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-cs` | `schneiderkamplab/dfm12-identity-xl-full-bp-cs` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-da` | `schneiderkamplab/dfm12-identity-xl-full-bp-da` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-de` | `schneiderkamplab/dfm12-identity-xl-full-bp-de` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-el` | `schneiderkamplab/dfm12-identity-xl-full-bp-el` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-en` | `schneiderkamplab/dfm12-identity-xl-full-bp-en` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-es` | `schneiderkamplab/dfm12-identity-xl-full-bp-es` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-et` | `schneiderkamplab/dfm12-identity-xl-full-bp-et` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-fi` | `schneiderkamplab/dfm12-identity-xl-full-bp-fi` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-fo` | `schneiderkamplab/dfm12-identity-xl-full-bp-fo` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-fr` | `schneiderkamplab/dfm12-identity-xl-full-bp-fr` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-is` | `schneiderkamplab/dfm12-identity-xl-full-bp-is` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-it` | `schneiderkamplab/dfm12-identity-xl-full-bp-it` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-nb` | `schneiderkamplab/dfm12-identity-xl-full-bp-nb` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-nl` | `schneiderkamplab/dfm12-identity-xl-full-bp-nl` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-nn` | `schneiderkamplab/dfm12-identity-xl-full-bp-nn` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-pl` | `schneiderkamplab/dfm12-identity-xl-full-bp-pl` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-pt_pt` | `schneiderkamplab/dfm12-identity-xl-full-bp-pt_pt` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-ro` | `schneiderkamplab/dfm12-identity-xl-full-bp-ro` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-sv` | `schneiderkamplab/dfm12-identity-xl-full-bp-sv` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-identity-xl-full-bp-uk` | `schneiderkamplab/dfm12-identity-xl-full-bp-uk` | 0 | B/C: Fact-registry entailment / identity consistency |
| `dfm12-magpie-et` | `schneiderkamplab/dfm12-magpie-et` | 78212 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-ca` | `schneiderkamplab/dfm12-multilingual-synthetic-ca` | 125091 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-cs` | `schneiderkamplab/dfm12-multilingual-synthetic-cs` | 63497 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-de` | `schneiderkamplab/dfm12-multilingual-synthetic-de` | 63735 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-el` | `schneiderkamplab/dfm12-multilingual-synthetic-el` | 62593 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-es` | `schneiderkamplab/dfm12-multilingual-synthetic-es` | 63914 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-et` | `schneiderkamplab/dfm12-multilingual-synthetic-et` | 121675 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-fi` | `schneiderkamplab/dfm12-multilingual-synthetic-fi` | 64028 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-fo` | `schneiderkamplab/dfm12-multilingual-synthetic-fo` | 122881 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-fr` | `schneiderkamplab/dfm12-multilingual-synthetic-fr` | 63763 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-is` | `schneiderkamplab/dfm12-multilingual-synthetic-is` | 121138 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-it` | `schneiderkamplab/dfm12-multilingual-synthetic-it` | 63759 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-nb` | `schneiderkamplab/dfm12-multilingual-synthetic-nb` | 127531 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-nl` | `schneiderkamplab/dfm12-multilingual-synthetic-nl` | 63711 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-nn` | `schneiderkamplab/dfm12-multilingual-synthetic-nn` | 128004 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-pl` | `schneiderkamplab/dfm12-multilingual-synthetic-pl` | 63768 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-pt_pt` | `schneiderkamplab/dfm12-multilingual-synthetic-pt_pt` | 63820 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-ro` | `schneiderkamplab/dfm12-multilingual-synthetic-ro` | 63723 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-sv` | `schneiderkamplab/dfm12-multilingual-synthetic-sv` | 63587 | C: Task-routed candidate response judgment |
| `dfm12-multilingual-synthetic-uk` | `schneiderkamplab/dfm12-multilingual-synthetic-uk` | 63668 | C: Task-routed candidate response judgment |
| `dfm12-norquad-wikipedia` | `schneiderkamplab/dfm12-norquad-wikipedia` | 1866 | C: Task-routed candidate response judgment |
| `dfm12-norwegian-inclusive-nb-samtale-pairs` | `schneiderkamplab/dfm12-norwegian-inclusive-nb-samtale-pairs` | 561 | C: Task-routed candidate response judgment |
| `dfm12-norwegian-inclusive-reasoning-norwegian` | `schneiderkamplab/dfm12-norwegian-inclusive-reasoning-norwegian` | 3159 | B/C: Candidate answer equality or executable result |
| `dfm12-norwegian-magpie-qwen3-bokmaal` | `schneiderkamplab/dfm12-norwegian-magpie-qwen3-bokmaal` | 468 | C: Task-routed candidate response judgment |
| `dfm12-norwegian-nb-samtale-pairs` | `schneiderkamplab/dfm12-norwegian-nb-samtale-pairs` | 1250 | C: Task-routed candidate response judgment |
| `dfm12-opus-ca-cs` | `schneiderkamplab/dfm12-opus-ca-cs` | 12 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-da` | `schneiderkamplab/dfm12-opus-ca-da` | 16 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-de` | `schneiderkamplab/dfm12-opus-ca-de` | 1528 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-el` | `schneiderkamplab/dfm12-opus-ca-el` | 96 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-en` | `schneiderkamplab/dfm12-opus-ca-en` | 4406 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-es` | `schneiderkamplab/dfm12-opus-ca-es` | 5660 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-et` | `schneiderkamplab/dfm12-opus-ca-et` | 8 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-fi` | `schneiderkamplab/dfm12-opus-ca-fi` | 12 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-fo` | `schneiderkamplab/dfm12-opus-ca-fo` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-fr` | `schneiderkamplab/dfm12-opus-ca-fr` | 1492 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-is-english-anchor` | `schneiderkamplab/dfm12-opus-ca-is-english-anchor` | 160 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-it` | `schneiderkamplab/dfm12-opus-ca-it` | 624 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-nb` | `schneiderkamplab/dfm12-opus-ca-nb` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-nl` | `schneiderkamplab/dfm12-opus-ca-nl` | 1306 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-nn` | `schneiderkamplab/dfm12-opus-ca-nn` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-pl` | `schneiderkamplab/dfm12-opus-ca-pl` | 178 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-pt_pt` | `schneiderkamplab/dfm12-opus-ca-pt_pt` | 2858 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-ro` | `schneiderkamplab/dfm12-opus-ca-ro` | 92 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-sv` | `schneiderkamplab/dfm12-opus-ca-sv` | 14 | C: Translation adequacy or source-target match |
| `dfm12-opus-ca-uk` | `schneiderkamplab/dfm12-opus-ca-uk` | 920 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-da` | `schneiderkamplab/dfm12-opus-cs-da` | 38 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-de` | `schneiderkamplab/dfm12-opus-cs-de` | 10064 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-el` | `schneiderkamplab/dfm12-opus-cs-el` | 48 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-en` | `schneiderkamplab/dfm12-opus-cs-en` | 85558 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-es` | `schneiderkamplab/dfm12-opus-cs-es` | 4144 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-et` | `schneiderkamplab/dfm12-opus-cs-et` | 10 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-fi` | `schneiderkamplab/dfm12-opus-cs-fi` | 170 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-fo` | `schneiderkamplab/dfm12-opus-cs-fo` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-fr` | `schneiderkamplab/dfm12-opus-cs-fr` | 1052 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-is-english-anchor` | `schneiderkamplab/dfm12-opus-cs-is-english-anchor` | 706 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-it` | `schneiderkamplab/dfm12-opus-cs-it` | 2130 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-nb` | `schneiderkamplab/dfm12-opus-cs-nb` | 56 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-nl` | `schneiderkamplab/dfm12-opus-cs-nl` | 258 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-nn` | `schneiderkamplab/dfm12-opus-cs-nn` | 6 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-pl` | `schneiderkamplab/dfm12-opus-cs-pl` | 1168 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-pt_pt` | `schneiderkamplab/dfm12-opus-cs-pt_pt` | 250 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-ro` | `schneiderkamplab/dfm12-opus-cs-ro` | 24 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-sv` | `schneiderkamplab/dfm12-opus-cs-sv` | 42 | C: Translation adequacy or source-target match |
| `dfm12-opus-cs-uk` | `schneiderkamplab/dfm12-opus-cs-uk` | 5986 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-de` | `schneiderkamplab/dfm12-opus-da-de` | 37802 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-el` | `schneiderkamplab/dfm12-opus-da-el` | 8 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-es` | `schneiderkamplab/dfm12-opus-da-es` | 20024 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-et` | `schneiderkamplab/dfm12-opus-da-et` | 10 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-fi` | `schneiderkamplab/dfm12-opus-da-fi` | 8750 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-fo` | `schneiderkamplab/dfm12-opus-da-fo` | 12 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-fr` | `schneiderkamplab/dfm12-opus-da-fr` | 3782 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-is` | `schneiderkamplab/dfm12-opus-da-is` | 12 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-it` | `schneiderkamplab/dfm12-opus-da-it` | 652 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-nb` | `schneiderkamplab/dfm12-opus-da-nb` | 4500 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-nl` | `schneiderkamplab/dfm12-opus-da-nl` | 3448 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-nn` | `schneiderkamplab/dfm12-opus-da-nn` | 164 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-pl` | `schneiderkamplab/dfm12-opus-da-pl` | 320 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-pt_pt` | `schneiderkamplab/dfm12-opus-da-pt_pt` | 1534 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-ro` | `schneiderkamplab/dfm12-opus-da-ro` | 28 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-sv` | `schneiderkamplab/dfm12-opus-da-sv` | 8970 | C: Translation adequacy or source-target match |
| `dfm12-opus-da-uk` | `schneiderkamplab/dfm12-opus-da-uk` | 146 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-el` | `schneiderkamplab/dfm12-opus-de-el` | 10664 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-en` | `schneiderkamplab/dfm12-opus-de-en` | 707124 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-es` | `schneiderkamplab/dfm12-opus-de-es` | 170592 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-et` | `schneiderkamplab/dfm12-opus-de-et` | 1304 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-fi` | `schneiderkamplab/dfm12-opus-de-fi` | 24054 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-fo-english-anchor` | `schneiderkamplab/dfm12-opus-de-fo-english-anchor` | 230 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-fr` | `schneiderkamplab/dfm12-opus-de-fr` | 248000 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-is` | `schneiderkamplab/dfm12-opus-de-is` | 1906 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-it` | `schneiderkamplab/dfm12-opus-de-it` | 45402 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-nb` | `schneiderkamplab/dfm12-opus-de-nb` | 8236 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-nl` | `schneiderkamplab/dfm12-opus-de-nl` | 75542 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-nn` | `schneiderkamplab/dfm12-opus-de-nn` | 528 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-pl` | `schneiderkamplab/dfm12-opus-de-pl` | 21574 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-pt_pt` | `schneiderkamplab/dfm12-opus-de-pt_pt` | 31500 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-ro` | `schneiderkamplab/dfm12-opus-de-ro` | 7616 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-sv` | `schneiderkamplab/dfm12-opus-de-sv` | 10016 | C: Translation adequacy or source-target match |
| `dfm12-opus-de-uk` | `schneiderkamplab/dfm12-opus-de-uk` | 46104 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-en` | `schneiderkamplab/dfm12-opus-el-en` | 53398 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-es` | `schneiderkamplab/dfm12-opus-el-es` | 5606 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-et` | `schneiderkamplab/dfm12-opus-el-et` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-fi-english-anchor` | `schneiderkamplab/dfm12-opus-el-fi-english-anchor` | 2908 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-fo-english-anchor` | `schneiderkamplab/dfm12-opus-el-fo-english-anchor` | 98 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-fr` | `schneiderkamplab/dfm12-opus-el-fr` | 3258 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-is-english-anchor` | `schneiderkamplab/dfm12-opus-el-is-english-anchor` | 714 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-it` | `schneiderkamplab/dfm12-opus-el-it` | 932 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-nb` | `schneiderkamplab/dfm12-opus-el-nb` | 24 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-nl` | `schneiderkamplab/dfm12-opus-el-nl` | 2072 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-nn` | `schneiderkamplab/dfm12-opus-el-nn` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-pl` | `schneiderkamplab/dfm12-opus-el-pl` | 288 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-pt_pt` | `schneiderkamplab/dfm12-opus-el-pt_pt` | 4324 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-ro` | `schneiderkamplab/dfm12-opus-el-ro` | 94 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-sv` | `schneiderkamplab/dfm12-opus-el-sv` | 490 | C: Translation adequacy or source-target match |
| `dfm12-opus-el-uk` | `schneiderkamplab/dfm12-opus-el-uk` | 106 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-es` | `schneiderkamplab/dfm12-opus-en-es` | 440720 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-et` | `schneiderkamplab/dfm12-opus-en-et` | 5168 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-fi` | `schneiderkamplab/dfm12-opus-en-fi` | 156658 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-fr` | `schneiderkamplab/dfm12-opus-en-fr` | 566824 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-it` | `schneiderkamplab/dfm12-opus-en-it` | 1026454 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-nb` | `schneiderkamplab/dfm12-opus-en-nb` | 120338 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-nl` | `schneiderkamplab/dfm12-opus-en-nl` | 1353744 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-nn` | `schneiderkamplab/dfm12-opus-en-nn` | 4914 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-pl` | `schneiderkamplab/dfm12-opus-en-pl` | 111244 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-pt_pt` | `schneiderkamplab/dfm12-opus-en-pt_pt` | 377378 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-ro` | `schneiderkamplab/dfm12-opus-en-ro` | 36884 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-sv` | `schneiderkamplab/dfm12-opus-en-sv` | 1242740 | C: Translation adequacy or source-target match |
| `dfm12-opus-en-uk` | `schneiderkamplab/dfm12-opus-en-uk` | 343374 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-et` | `schneiderkamplab/dfm12-opus-es-et` | 74 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-fi` | `schneiderkamplab/dfm12-opus-es-fi` | 19444 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-fo-english-anchor` | `schneiderkamplab/dfm12-opus-es-fo-english-anchor` | 222 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-fr` | `schneiderkamplab/dfm12-opus-es-fr` | 103110 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-is` | `schneiderkamplab/dfm12-opus-es-is` | 458 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-it` | `schneiderkamplab/dfm12-opus-es-it` | 29496 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-nb` | `schneiderkamplab/dfm12-opus-es-nb` | 1700 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-nl` | `schneiderkamplab/dfm12-opus-es-nl` | 55766 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-nn` | `schneiderkamplab/dfm12-opus-es-nn` | 154 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-pl` | `schneiderkamplab/dfm12-opus-es-pl` | 15562 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-pt_pt` | `schneiderkamplab/dfm12-opus-es-pt_pt` | 111480 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-ro` | `schneiderkamplab/dfm12-opus-es-ro` | 4248 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-sv` | `schneiderkamplab/dfm12-opus-es-sv` | 5224 | C: Translation adequacy or source-target match |
| `dfm12-opus-es-uk` | `schneiderkamplab/dfm12-opus-es-uk` | 45416 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-fi` | `schneiderkamplab/dfm12-opus-et-fi` | 580 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-fo` | `schneiderkamplab/dfm12-opus-et-fo` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-fr` | `schneiderkamplab/dfm12-opus-et-fr` | 172 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-is-english-anchor` | `schneiderkamplab/dfm12-opus-et-is-english-anchor` | 226 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-it` | `schneiderkamplab/dfm12-opus-et-it` | 70 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-nb` | `schneiderkamplab/dfm12-opus-et-nb` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-nl` | `schneiderkamplab/dfm12-opus-et-nl` | 92 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-nn` | `schneiderkamplab/dfm12-opus-et-nn` | 436 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-pl` | `schneiderkamplab/dfm12-opus-et-pl` | 26 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-pt_pt` | `schneiderkamplab/dfm12-opus-et-pt_pt` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-ro` | `schneiderkamplab/dfm12-opus-et-ro` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-sv` | `schneiderkamplab/dfm12-opus-et-sv` | 32 | C: Translation adequacy or source-target match |
| `dfm12-opus-et-uk` | `schneiderkamplab/dfm12-opus-et-uk` | 84 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-fo` | `schneiderkamplab/dfm12-opus-fi-fo` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-fr` | `schneiderkamplab/dfm12-opus-fi-fr` | 6138 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-is` | `schneiderkamplab/dfm12-opus-fi-is` | 6 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-it` | `schneiderkamplab/dfm12-opus-fi-it` | 3992 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-nb` | `schneiderkamplab/dfm12-opus-fi-nb` | 4652 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-nl` | `schneiderkamplab/dfm12-opus-fi-nl` | 614 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-nn` | `schneiderkamplab/dfm12-opus-fi-nn` | 2256 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-pl` | `schneiderkamplab/dfm12-opus-fi-pl` | 1166 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-pt_pt` | `schneiderkamplab/dfm12-opus-fi-pt_pt` | 888 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-ro` | `schneiderkamplab/dfm12-opus-fi-ro` | 30 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-sv` | `schneiderkamplab/dfm12-opus-fi-sv` | 20020 | C: Translation adequacy or source-target match |
| `dfm12-opus-fi-uk` | `schneiderkamplab/dfm12-opus-fi-uk` | 88 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-fr` | `schneiderkamplab/dfm12-opus-fo-fr` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-is` | `schneiderkamplab/dfm12-opus-fo-is` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-it-english-anchor` | `schneiderkamplab/dfm12-opus-fo-it-english-anchor` | 144 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-nb` | `schneiderkamplab/dfm12-opus-fo-nb` | 40 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-nl-english-anchor` | `schneiderkamplab/dfm12-opus-fo-nl-english-anchor` | 162 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-nn` | `schneiderkamplab/dfm12-opus-fo-nn` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-pl` | `schneiderkamplab/dfm12-opus-fo-pl` | 10 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-pt_pt-english-anchor` | `schneiderkamplab/dfm12-opus-fo-pt_pt-english-anchor` | 192 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-ro-english-anchor` | `schneiderkamplab/dfm12-opus-fo-ro-english-anchor` | 74 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-sv` | `schneiderkamplab/dfm12-opus-fo-sv` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-fo-uk-english-anchor` | `schneiderkamplab/dfm12-opus-fo-uk-english-anchor` | 164 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-is` | `schneiderkamplab/dfm12-opus-fr-is` | 360 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-it` | `schneiderkamplab/dfm12-opus-fr-it` | 155932 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-nb` | `schneiderkamplab/dfm12-opus-fr-nb` | 628 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-nl` | `schneiderkamplab/dfm12-opus-fr-nl` | 57168 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-nn` | `schneiderkamplab/dfm12-opus-fr-nn` | 332 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-pl` | `schneiderkamplab/dfm12-opus-fr-pl` | 7964 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-pt_pt` | `schneiderkamplab/dfm12-opus-fr-pt_pt` | 46972 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-ro` | `schneiderkamplab/dfm12-opus-fr-ro` | 6968 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-sv` | `schneiderkamplab/dfm12-opus-fr-sv` | 7060 | C: Translation adequacy or source-target match |
| `dfm12-opus-fr-uk` | `schneiderkamplab/dfm12-opus-fr-uk` | 56386 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-it` | `schneiderkamplab/dfm12-opus-is-it` | 452 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-nb` | `schneiderkamplab/dfm12-opus-is-nb` | 228 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-nl` | `schneiderkamplab/dfm12-opus-is-nl` | 18 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-nn` | `schneiderkamplab/dfm12-opus-is-nn` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-pl` | `schneiderkamplab/dfm12-opus-is-pl` | 28 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-pt_pt` | `schneiderkamplab/dfm12-opus-is-pt_pt` | 114 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-ro` | `schneiderkamplab/dfm12-opus-is-ro` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-sv` | `schneiderkamplab/dfm12-opus-is-sv` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-is-uk` | `schneiderkamplab/dfm12-opus-is-uk` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-nb` | `schneiderkamplab/dfm12-opus-it-nb` | 1722 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-nl` | `schneiderkamplab/dfm12-opus-it-nl` | 19516 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-nn` | `schneiderkamplab/dfm12-opus-it-nn` | 10 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-pl` | `schneiderkamplab/dfm12-opus-it-pl` | 4426 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-pt_pt` | `schneiderkamplab/dfm12-opus-it-pt_pt` | 18634 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-ro` | `schneiderkamplab/dfm12-opus-it-ro` | 2298 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-sv` | `schneiderkamplab/dfm12-opus-it-sv` | 1518 | C: Translation adequacy or source-target match |
| `dfm12-opus-it-uk` | `schneiderkamplab/dfm12-opus-it-uk` | 27282 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-nl` | `schneiderkamplab/dfm12-opus-nb-nl` | 364 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-nn` | `schneiderkamplab/dfm12-opus-nb-nn` | 1082 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-pl` | `schneiderkamplab/dfm12-opus-nb-pl` | 548 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-pt_pt` | `schneiderkamplab/dfm12-opus-nb-pt_pt` | 836 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-ro` | `schneiderkamplab/dfm12-opus-nb-ro` | 30 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-sv` | `schneiderkamplab/dfm12-opus-nb-sv` | 1136 | C: Translation adequacy or source-target match |
| `dfm12-opus-nb-uk` | `schneiderkamplab/dfm12-opus-nb-uk` | 1340 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-nn` | `schneiderkamplab/dfm12-opus-nl-nn` | 16 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-pl` | `schneiderkamplab/dfm12-opus-nl-pl` | 4332 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-pt_pt` | `schneiderkamplab/dfm12-opus-nl-pt_pt` | 14532 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-ro` | `schneiderkamplab/dfm12-opus-nl-ro` | 9232 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-sv` | `schneiderkamplab/dfm12-opus-nl-sv` | 368 | C: Translation adequacy or source-target match |
| `dfm12-opus-nl-uk` | `schneiderkamplab/dfm12-opus-nl-uk` | 29664 | C: Translation adequacy or source-target match |
| `dfm12-opus-nn-pl` | `schneiderkamplab/dfm12-opus-nn-pl` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-nn-pt_pt` | `schneiderkamplab/dfm12-opus-nn-pt_pt` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-nn-ro` | `schneiderkamplab/dfm12-opus-nn-ro` | 2 | C: Translation adequacy or source-target match |
| `dfm12-opus-nn-sv` | `schneiderkamplab/dfm12-opus-nn-sv` | 132 | C: Translation adequacy or source-target match |
| `dfm12-opus-nn-uk` | `schneiderkamplab/dfm12-opus-nn-uk` | 4 | C: Translation adequacy or source-target match |
| `dfm12-opus-pl-pt_pt` | `schneiderkamplab/dfm12-opus-pl-pt_pt` | 2144 | C: Translation adequacy or source-target match |
| `dfm12-opus-pl-ro` | `schneiderkamplab/dfm12-opus-pl-ro` | 470 | C: Translation adequacy or source-target match |
| `dfm12-opus-pl-sv` | `schneiderkamplab/dfm12-opus-pl-sv` | 2768 | C: Translation adequacy or source-target match |
| `dfm12-opus-pl-uk` | `schneiderkamplab/dfm12-opus-pl-uk` | 18914 | C: Translation adequacy or source-target match |
| `dfm12-opus-pt_pt-ro` | `schneiderkamplab/dfm12-opus-pt_pt-ro` | 3934 | C: Translation adequacy or source-target match |
| `dfm12-opus-pt_pt-sv` | `schneiderkamplab/dfm12-opus-pt_pt-sv` | 664 | C: Translation adequacy or source-target match |
| `dfm12-opus-pt_pt-uk` | `schneiderkamplab/dfm12-opus-pt_pt-uk` | 8538 | C: Translation adequacy or source-target match |
| `dfm12-opus-ro-sv` | `schneiderkamplab/dfm12-opus-ro-sv` | 34 | C: Translation adequacy or source-target match |
| `dfm12-opus-ro-uk` | `schneiderkamplab/dfm12-opus-ro-uk` | 22 | C: Translation adequacy or source-target match |
| `dfm12-opus-sv-uk` | `schneiderkamplab/dfm12-opus-sv-uk` | 70 | C: Translation adequacy or source-target match |
| `dfm12-pllum-align` | `schneiderkamplab/dfm12-pllum-align` | 1364 | A/C: Original pair preference / rating |
| `dfm12-pllumic` | `schneiderkamplab/dfm12-pllumic` | 790 | C: Task-routed candidate response judgment |
| `dfm12-poro2-fi` | `schneiderkamplab/dfm12-poro2-fi` | 472852 | C: Task-routed candidate response judgment |
