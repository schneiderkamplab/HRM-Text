---
type: Reference
title: DFM15 Native Reasoning and Dyna Decision Candidates
description: Native reasoning replacements, all four late additions and organization-scan dispositions for bounded decision supervision.
tags: [data, dfm15, decision, reasoning, dynainstruct]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM15 Native Reasoning and Dyna Candidates

[Latest-source overview and A-D rubric](latest-datasets.md).
[DFM1-15 overview](../decision-datasets.md).

## Native Reasoning Is Replacement, Not New Gold

Inspected `data/dfm15/native-reasoning-v2/inventory.json` and
`source-replacements.json`: **83 parts in six families**. These replace
inherited tokenized sources rather than adding independent problems. The native
repair separates thought/final channels, preserves usable direct answers and
quarantines unusable responses. It does not certify mathematical correctness,
tool success or reasoning validity. No new verifier was run in this review.

| Exact source / release ID | Parts | Grade and proposed decision |
|---|---:|---|
| `allenai/big-reasoning-traces` | 44 | C for final/step validity; B only for independently checkable predicates. Inventory includes 43 DeepSeek parts and one DeepSeek_debug part, not two independent corpora. |
| `allenai/open_math_2_50k_r1-original` | 1 | B for mechanically checked candidate-answer equivalence where a trustworthy final target/checker exists; otherwise C. Do not infer all rows were solver-verified. |
| `allenai/verifiable-reasoning-filtered-gpt-41` | 6 | C by default; name is not proof of preserved executable checks. Recover source labels/options for A or original checkers for B. |
| `allenai/verifiable-reasoning-filtered-o4-mini` | 2 | Same conditional A/B/C mapping; keep provenance distinct from GPT-41 and prevent shared-problem leakage. |
| `nvidia/Nemotron-Terminal-Corpus`; materialized `schneiderkamplab/dfm10-nemotron-terminal-sft` | 29 | C for action/success judgments; B for schema/type/known execution outcomes only. Missing environment state or tool output prevents sound counterfactual labels. |
| `schneiderkamplab/dfm12-norwegian-magpie-qwen3-bokmaal` | 1 | C for response or atomic instruction adequacy; prompt-marker cleanup is not a new decision label. |

Terminal coverage includes adapters `code`, `math`, `swe`; easy tasks in
data_processing, data_querying, data_science, debugging, dependency_management,
file_operations, scientific_computing, security, software_engineering; medium
adds model_training and system_administration to those nine; mixed covers
data_processing, data_science, debugging, file_operations, scientific_computing,
security. These total 29 parts. Exact part paths and original/repaired pairing
are preserved in the replacement inventory; no additional hard-task family is
implied.

A useful state excludes the hidden final label and any answer-revealing thought
when the task is to choose the final answer. For a step-validity task, explicitly
include only the relevant prior steps. Long solutions may require decomposed
atomic questions; they do not become easy System One decisions simply by
changing the output type. Malformed/truncated thought text is not a reliable
negative reasoning example, nor is a transport or audit error.

Later DFM15 answer-format conditioning touches OpenMathInstruct2, AllenAI Open
Math, GSM-Symbolic and a Tulu personas math example. The [completion history](../dfm15-plan.md)
explicitly records an inherited semantic inconsistency in that Tulu example;
adding an `ANSWER:` line preserves it rather than verifying it. Formatting
variants must not be counted as fresh independent decision examples.

## Four Late Additions

Exact IDs/revisions from `config/dfm15_sources.json`; admission numbers from
the October 17 [full-sample record](../dfm15-plan.md). All four are **active per
that completion record**, with a local-verification gap: the cited
`data/sampled_dfm15/full-mixture-verified.json` is absent here. The registration
file's staging status and `sampled: false` are older metadata, not proof that
the completed full sample omitted them.

| Exact HF ID | Pinned revision | Staged / admitted rows | Grade |
|---|---|---:|---|
| `danish-foundation-models/faroese-dyna-instruct` | `a27cb2696d6fd2285d73e4bae04aa87e1bd26b1f` | 1,008,797 / 1,008,183 | C overall; A/B only after recovering appropriate constituent labels/relations |
| `danish-foundation-models/icelandic-dyna-instruct` | `650c1e80c8f91fece52348b8f80cf16e726e0844` | 610,104 / 608,280 | C overall; conditional A/B lexical predicates |
| `danish-foundation-models/multilingual-gsm-symbolic` | `75ce20d919d93ba78340adc6f70d2120f3ca3ce3` | 3,799 / 3,799 | B for reliable numeric candidate equivalence; C for unverified reasoning/semantic validity |
| `danish-foundation-models/linguistic-quality` | `884c73cce486243ff2b17bf26b5c22abd25bc73f` | 615 / 615 | C correction selection; B only for mechanically established edit properties |

Faroese excludes 614 and Icelandic 1,824 overlength conversations, not truncated
targets. Completion reports 1,620,877 admitted rows / 145,489,360 tokens per
epoch for these four additions at repeat one. Staged token counts should not
be substituted for the admitted totals.

GSM uses only `data/eng/train_synthetic-00000-of-00001.parquet`; 21 internal
duplicates were removed. The 191 original GSM8k-derived train rows are not
added again, and all test splits stay eval-only. Conversion's numeric-target
versus `####` consistency check is not an independent proof that the word
problem was solved correctly. Units, equivalence, ambiguous wording and shared
template families matter for distractors and train/test separation.

Linguistic-quality uses `train.parquet`: Danish correction pairs, not 615
independently scored alternatives. Do not label every unobserved correction
wrong or assume the provided correction uniquely best. A Score needs its own
rubric-aligned labels; edit distance is not a quality score.

All 571 composite FO-Instruct rows matched the inherited `Setur/fo-instruct`
multiset and were excluded from the new composite, retaining the inherited
repeat-10 route. The existing overlap report finds no further identical
normalized conversations across the four additions; it is explicitly **not**
a full cross-corpus overlap check. Shared DynaWord grounding also creates
near-duplicate and document-family leakage risks beyond exact conversation
matching.

## Dyna Constituent Coverage

The exact subset identifiers below are projected from
`data/dfm15/organization-inventory.json`. Each path is
`data/{subset}/{subset}.parquet` in its named repository. Availability in the
inventory is not a new row audit or a guarantee of native semantic quality.

### Faroese

Repository: `danish-foundation-models/faroese-dyna-instruct`, 14 inventoried
payloads, of which `fo-instruct` is excluded as the duplicate route above.

| Exact subset(s) | Proposed task / caution |
|---|---|
| `dynaword-reverse-instruct` | C: grounded candidate response. Reverse-generated prompts may leak target phrasing; split by underlying document. |
| `faroese-flan-fmd`, `faroese-flan-fo-wiktionary`, `faroese-flan-islex-fo`, `faroese-flan-ravnlex`, `faroese-flan-sprotin` | Conditional B lexical relation or sense choice when the actual schema provides the relation; otherwise C. Polysemy, inflection, spelling variants and incomplete dictionaries invalidate naive negatives. |
| `faroese-flan-fo-wikisource`, `faroese-flan-fpsc`, `faroese-flan-gerdabokur` | C: evidence or text-transformation choice; verify task fields rather than treating a subset name as a gold label. |
| `faroese-flan-kunngerdaportalur`, `faroese-flan-logir`, `faroese-flan-logting-spurningar`, `faroese-flan-lum` | C: document-grounded claims/answerability; preserve dates, speaker and actual question-answer linkage. |
| `fo-instruct` | Excluded duplicate here; inherited `Setur/fo-instruct` remains. C for general answer choice unless original explicit labels are recovered. |

### Icelandic

Repository: `danish-foundation-models/icelandic-dyna-instruct`, 19 payloads.

| Exact subset(s) | Proposed task / caution |
|---|---|
| `dynaword-reverse-instruct` | C: source-grounded choice, with prompt/answer leakage and shared-document split controls. |
| `icelandic-flan-bin-dmii`, `icelandic-flan-dim-valency`, `icelandic-flan-dmii-abbr`, `icelandic-flan-enis-glossary`, `icelandic-flan-icewordnet`, `icelandic-flan-islensk-nutimamalsordabok`, `icelandic-flan-islex`, `icelandic-flan-ordanet`, `icelandic-flan-ordskiptingar` | Conditional B for source-explicit morphology, expansion, relation or segmentation predicates; A only where original options/labels survive. Validate syncretism, multiple accepted forms, senses and abbreviation ambiguity; otherwise C. |
| `icelandic-flan-ejournals-is`, `icelandic-flan-eso`, `icelandic-flan-hagstofa`, `icelandic-flan-igc-news`, `icelandic-flan-rafbokavefur` | C: grounded claim or candidate-answer judgment. Preserve timestamps, numerical units and missing-table/figure restrictions. |
| `icelandic-flan-icesquer`, `icelandic-flan-spjallromur` | C: contextual/conversational adequacy, not automatic single-best response. Inspect actual task schema before a narrower mapping. |
| `icelandic-flan-stjornartidindi`, `icelandic-flan-umbodsmadur` | C: date-conditioned document evidence; no unqualified present-day legal truth labels. |

The standalone `danish-foundation-models/Icelandic-flan` repository has no
Parquet/JSONL payload in the scan; this does not negate Icelandic FLAN content
inside Dyna-Instruct.

## Organization Scan

The [complete 42-repository disposition table](latest-organization-scan.md)
preserves exact IDs and the recorded scan decisions. Pending private collections
are `danish-foundation-models/dialog-k2-da` and
`danish-foundation-models/instruction-dataset-v1`: the recorded 403 is an
organization private-storage limit, not simply missing authentication.
No access retry or new audit was performed here. D while blocked; conditional
C/A/B after access and constituent verification is not admission authorization.

The four prepared additions, inherited audited routes, explicitly excluded
WildChat, unchanged Danish/Norwegian composites, raw grounding and eval-only
boundaries must remain separate. In particular, the nine Croco variants are
not nine independent admitted datasets, and metadata collections are not
decision targets. Preserve earlier exclusions inside composites, including
direct Synquid duplicates and Norwegian evaluation sources.
