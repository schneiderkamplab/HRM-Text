---
type: Reference
title: DFM10 Materialized Packages
description: All 72 DFM10 export-manifest entries with upstream attribution and bounded-choice assessment.
tags: [decision-datasets, dfm8, dfm9, dfm10, dfm11, dfm12, dfm13, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM10 Materialized Packages

Part of [DFM8-13 source review](middle-datasets.md). Classifications are proposals, not conversion or admission results.

Evidence: [export manifest](../../../exports_dfm10/manifest.json), exact `packages[].name`, `upstream`, `status`, and transformation records. HF destination is `schneiderkamplab/<name>`. All 72 entries say `uploaded`; this is a local historical receipt claim, not a fresh Hub check or proof of current sampling. Upstream strings are copied literally: descriptive/non-HF attributions are not invented HF IDs. Repaired exports and their original sources must not be counted as independent content.

| Exact package HF ID | Upstream attribution | Proposed applicability |
|---|---|---|

| `schneiderkamplab/dfm10-ai-arena-udtraek-sft` | `danish-foundation-models/ai_arena_udtraek` | A/C: Original pair preference / rating |
| `schneiderkamplab/dfm10-alexandra-dane` | `alexandrainst/dane` | B: Token/span label or candidate-entity membership |
| `schneiderkamplab/dfm10-alexandra-multi-zebra-logic` | `alexandrainst/multi-zebra-logic` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-alexandra-scandi-qa-da` | `alexandrainst/scandi-qa` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-andersen-modernization` | `ogierMontanus/hcandersenDk_data_2024` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/dfm10-arxiv-paper-summarization-sft` | `common-pile/arxiv_papers_filtered` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/dfm10-bornholmsk-parallel` | `strombergnlp/bornholmsk_parallel` | C: Translation adequacy or source-target match |
| `schneiderkamplab/dfm10-code-meta-reasoning-repaired` | `allenai/code-meta-reasoning-filtered` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-cor-sem-sft` | `DSL/CST COR.SEM 1.0` | B: Token/span label or candidate-entity membership |
| `schneiderkamplab/dfm10-croco-munin-chosen-sft` | `danish-foundation-models/croco-munin-apertus-8b-da-simpo-full-50k` | A/C: Original pair preference / rating |
| `schneiderkamplab/dfm10-danish-book-ads-sft` | `chcaa/danish-book-ads` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-danish-framenet-sft` | `dsldk/dansk-frame-net` | B: Token/span label or candidate-entity membership |
| `schneiderkamplab/dfm10-danish-lexical-sentiment-sft` | `dsldk/danish-sentiment-lexicon` | A: Existing label or option |
| `schneiderkamplab/dfm10-danish-persona-chats` | `oliverkinch/danish-personas` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-danish-university-portals-bt-repaired` | `oliverkinch/danish-university-portals-bt` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-danish-wikipedia-open-chats` | `danish-foundation-models/danish-dynaword/wikipedia`; `Danish Wikipedia` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-danmarks-statistik-bt-repaired` | `oliverkinch/danmarks-statistik-bt` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-deepdive-gemma4-tool-use` | `zai-org/DeepDive` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-diem-historical-modernization` | `RA-Data-Science/DiEm_HTR` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/dfm10-dolci-tool-use-repaired` | `allenai/Dolci-Instruct-SFT-Tool-Use`; `allenai/Dolci-Instruct-SFT-Tool-Use-SA` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-domsdatabasen-grounded-chats` | `alexandrainst/domsdatabasen` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-dst-table-prompts-repaired` | `oliverkinch/dst-table-prompts-bt` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-dynaword-instruct-repaired` | `oliverkinch/da-instruct-dynaword`; `oliverkinch/da-instruct-dynaword-hq`; `oliverkinch/da-instruct-dynaword-contemporary`; `oliverkinch/da-instruct-dynaword-contemporary-hq` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-folketingets-dokumenter-denoising` | `Rigsarkivet handover 14004 / Folketinget` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/dfm10-folketingets-dokumenter-error-correction` | `Rigsarkivet handover 14004 / Folketinget` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/dfm10-folketingets-dokumenter-prefix-continuation` | `Rigsarkivet handover 14004 / Folketinget` | B/C: Masked source-span recovery |
| `schneiderkamplab/dfm10-folketingets-dokumenter-span-filling` | `Rigsarkivet handover 14004 / Folketinget` | B/C: Masked source-span recovery |
| `schneiderkamplab/dfm10-glaive-native-tool-use` | `glaiveai/glaive-function-calling-v2` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-govreport-summarization-repaired` | `ccdv/govreport-summarization` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/dfm10-machine-translation-da-uk-repaired` | `oliverkinch/machine-translation-da-uk` | C: Translation adequacy or source-target match |
| `schneiderkamplab/dfm10-medquad-danish-sft` | `abachaa/MedQuAD` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-medquad-english-sft` | `abachaa/MedQuAD` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-mimir-answer-contract-calibration` | `Novel deterministic transformations of audited grounded Mimir rows` | B: Pass/fail for explicit output constraints |
| `schneiderkamplab/dfm10-mimir-boolq-entailment-sft` | `Novel openly grounded passages and generated propositions` | A: Existing label or option |
| `schneiderkamplab/dfm10-mimir-drop-reasoning-sft` | `Novel openly grounded passages and generated questions` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-mimir-event-coreference-sft` | `Novel event-coreference and temporal-state synthetic tasks` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-mimir-grounded-expanded-sft` | `Common Pile source collections with row-level provenance` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-mimir-ifeval-verifier-sft` | `Novel verifier-backed synthetic instruction tasks` | B: Pass/fail for explicit output constraints |
| `schneiderkamplab/dfm10-natural-instructions-filtered-sft` | `Muennighoff/natural-instructions` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-nemotron-swe-repaired` | `nvidia/Nemotron-SFT-SWE-v2` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-nemotron-terminal-sft` | `nvidia/Nemotron-Terminal-Corpus` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-nordjylland-news-repaired` | `alexandrainst/nordjylland-news-summarization` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-numinamath-valid-sft` | `AI-MO/NuminaMath-1.5` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-openmathinstruct2-repaired` | `nvidia/OpenMathInstruct-2` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-openstax-mimir-sft` | `OpenStax official immutable CC BY 4.0 source books` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-openstax-open-chats` | `OpenStax official immutable CC BY 4.0 source books` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-opus-da-en-repaired` | `schneiderkamplab/opus-da-en-permissive` | C: Translation adequacy or source-target match |
| `schneiderkamplab/dfm10-sapient-acereason-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `AceReason` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-amps-mathematica-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `AMPS Mathematica` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-dmmath-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `DeepMind Mathematics` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-flan-cot-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `FLAN chain-of-thought` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-flan-dialog-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `FLAN dialogue` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-flan-flan-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `FLAN collection` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-flan-niv2-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `FLAN Natural Instructions v2` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-flan-t0-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `FLAN T0` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-openmathinstruct2-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `OpenMathInstruct-2` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-openthoughts2-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `OpenThoughts2` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-platypus-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `Platypus` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-qrecc-ii-repaired` | `Sapient FLAN QReCC-II variants` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-scibench-repaired` | `Sapient Platypus SciBench variant` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-sudoku-extreme-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `Sudoku Extreme` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-sapient-synth-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `Sapient SYNTH` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-tasksource-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `Tasksource` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-sapient-textbook-reasoning-filtered-sft` | `sapientinc/HRM-Text-data-io-cleaned-20260515`; `Textbook reasoning` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm10-scientific-summaries-repaired` | `laion/Scientific-Summaries` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/dfm10-sks-tei-sft` | `kb-dk/SKS_tei` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-synthetic-values-model-charter-da` | `danish-foundation-models/synthetic-values-model-charter` | A/C: Original pair preference / rating |
| `schneiderkamplab/dfm10-tidsskrift-open-chats` | `tidsskrift.dk OAI-PMH article metadata and PDFs` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-tidsskrift-open-sft` | `tidsskrift.dk OAI-PMH article metadata and PDFs` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm10-toolace-native-tool-use` | `Team-ACE/ToolACE` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm10-wiki-cat-sum-repaired` | `GEM/wiki_cat_sum` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/dfm10-xlam-native-tool-use` | `Salesforce/xlam-function-calling-60k` | B/C: Tool name/schema validity; candidate next action |
