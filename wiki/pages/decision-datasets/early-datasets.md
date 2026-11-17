---
type: Dataset Assessment
title: Original Sapient and DFM1-7 Decision Dataset Coverage
description: Exhaustive early source inventory with bounded-target routes, historical versions, and exclusion caveats.
tags: [data, decision-datasets, sapient, dfm]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Original Sapient and DFM1-7 Decision Dataset Coverage

Part of [DFM1-15 decision modelling](../decision-datasets.md). Use its
[A/B/C/D rubric](../decision-datasets.md#common-assessment-scale) and the
[conversion recipes and safeguards](conversion-recipes.md). This is a review,
not a conversion, audit campaign, source-policy change, or training change.
The common interface is state plus a typed Choice, Score or Noul target, not
freeform response generation. No generated reference is presumed uniquely best.

## Coverage and Evidence

The original Sapient task inventory is recovered from the **Task Coverage
Stats** table in `data/show_analytics_original_sapient.md`: 5,212 named files.
The attachments preserve every name, grouping FLAN's identical task names
across explicitly listed template variants, and expressing only the 500 SYNTH
shards as the closed range `synth_001.parquet` through `synth_500.parquet`.
This is exhaustive inventory coverage, not exhaustive semantic row validation.
Route assignments inferred from descriptive task names are provisional;
unresolved tasks remain explicitly `D-review`, not silently omitted.

| Original family | Files in analytics | Exhaustive names and candidate mapping |
|---|---:|---|
| FLAN, excluding NIV2 | 1,096 | [FLAN inventory](early-inventory-flan-1.md): 285 task/template names |
| FLAN NIV2 | 3,112 | [Part 1](early-inventory-niv2-1.md), [part 2](early-inventory-niv2-2.md), [part 3](early-inventory-niv2-3.md), [part 4](early-inventory-niv2-4.md): 1,556 task IDs, each with NF and NZ |
| Tasksource | 182 | [Tasksource inventory](early-inventory-tasksource-1.md), all 182 constituent file names |
| Platypus | 10 | [Other Sapient inventory](early-inventory-other-1.md) |
| SYNTH | 500 | Same attachment, closed shard range; internal subtask provenance not recovered from shard names |
| ampsmathematica | 137 | Same attachment, all Mathematica task file names |
| dmmath | 168 | Same attachment, all difficulty/module task file names |
| acereason | 1 | Same attachment |
| openmathinstruct2 | 2 | Same attachment, CoT/direct variants |
| openthoughts2 | 1 | Same attachment |
| sudoku_extreme | 1 | Same attachment |
| textbookreasoning | 2 | Same attachment, CoT/direct variants |

[Early DFM family inventory](early-inventory-dfm-families.md) additionally
enumerates all 168 non-original-Sapient category names appearing in available
DFM1-5 and DFM7 task analytics. That includes zero-exposure entries and generated
replacement families. The collection's shared source ledger supplies the
full filename/historical membership joins; use the exact constituent names in
these attachments as join keys, not just the FLAN or Tasksource umbrella ID.

Evidence inspected:

* `data/show_analytics_{dfm,dfm2,dfm3,dfm4,dfm5,dfm7}.md`: historical task
  inventory, not proof that every listed file has nonzero sampled exposure.
* `data/dfm6_chat_sources/dfm6_chat_source_manifest.json`,
  `data/tokenized_dfm6/union_manifest.json`, and
  `data/tokenized_dfm7/union_manifest.json`: available manifest evidence for
  joins. There is no `data/show_analytics_dfm6.md` in this checkout; do not
  manufacture DFM6 exposure from the DFM7 table.
* `data_io/prefix_config_dfm.yaml` and `data_io/prefix_config_dfm2.yaml`
  through `prefix_config_dfm7.yaml`: cap/repeat policies, not row labels.
* `scripts/build_tokenized_dfm5_tree.py`,
  `scripts/build_dfm6_chat_source_tree.py`,
  `scripts/build_dfm7_chat_source_tree.py`,
  `scripts/build_tokenized_dfm7_tree.py`, and
  `scripts/prepare_dfm7_special_sources.py`: naming, inheritance, and adapters.
* `scripts/download_training_datasets.py`: source IDs, including explicit
  version suffixes. `docs/dfm8-datasets.md` identifies published derivative
  repositories; it does not prove revision identity with DFM5-7 local exports.

## Reading the Sapient Attachments

Original mirror ID: `sapientinc/HRM-Text-data-io-cleaned-20260515`.
Root: `data/downloads/datasets/sapient_cleaned/`. The date in the ID is a
version identifier, not a recovered Git revision; no commit is asserted here.

For a FLAN row `flan/<task>.parquet` and each listed template, reconstruct:
`data_clustered/flan/<template>__<task>.parquet` beneath the root above.
Its original tokenized key is `flan__<template>__<task>.parquet`.
For other families replace **only the first** `__` with `/`: Platypus lives
under `data/`; the other families live under `data_clustered/`. Preserve
remaining double underscores in filenames, especially dmmath module names.
DFM1-4 commonly prepend `sapient_cleaned__data_clustered__` (or `...__data__`);
DFM5 restores original Sapient names. Do not confuse a renamed file with new data.

| Code | Exact FLAN template |
|---|---|
| CF / CZ | `cot_fsopt_data` / `cot_zsopt_data` |
| DF / DZ | `dialog_fsopt_data` / `dialog_zsopt_data` |
| FF / FFN | `flan_fsopt_data` / `flan_fsnoopt_data` |
| FZ / FZN | `flan_zsopt_data` / `flan_zsnoopt_data` |
| NF / NZ | `niv2_fsopt_data` / `niv2_zsopt_data` |
| TF / TFN | `t0_fsopt_data` / `t0_fsnoopt_data` |
| TZ / TZN | `t0_zsopt_data` / `t0_zsnoopt_data` |

`data_io/pipe_clustered/clean_flan.py` preserves `_task_name`, inputs and
targets with filesystem-safe name substitution; direct versus CoT is stored
as `condition`. Few-shot demonstrations are part of the prompt, not independent
supervised decisions. An `opt` template name alone does not establish MCQ.
Tasksource's cleaner uses `tasksource/tasksource-instruct-v0`, split `train`,
filters `TASK_SET`, maps inputs to instruction, and strips a trailing period
from the target. Its `safe_filename` replaces `/` with `_`; compare the
cleaner's `TASK_SET` to recover upstream configuration names such as
`probability_words_nli/reasoning_1hop`, `robust_nli/IS_CS`, and
`vitaminc/tals--vitaminc`. A Tasksource name absent from the attachment was not
in this measured original snapshot, even if present in a newer TASK_SET.

## Route Dictionary

These suffixes refine the common rubric, not replace it. The attachment
class is a **candidate task route**; eligibility can still make it D/excluded.

| Route | Bounded target and necessary restriction |
|---|---|
| A-label | Preserve finite class vocabulary or native scalar label; map to Choice or a defined Score scale. Verify target normalization, including punctuation, multilabel cases and missing labels. |
| A-options | Preserve supplied alternatives and gold index/text. Require exact option-to-target alignment; reject duplicate/equivalent options and absent visual context. No invented distractors. |
| B-check | Verify a supplied candidate with a deterministic calculator, symbolic rule or sandboxed test; keep only supported, well-defined tasks. Arbitrary math prose is NOT automatically B. |
| B-grid | Sudoku candidate-grid validity or bounded next-cell choices with a solver/checker. Check givens and constraints; do not reject an alternative valid solution merely for differing from reference. |
| B-tags | Recover per-token/span finite labels with alignment and fixed vocabulary. Candidate spans must be supplied; document-wide tag strings are not one small Choice. |
| C-answer | Free numeric, span or factual answer needs validated alternatives or answer-equivalence checks. Answer keys do not provide automatically false distractors. |
| C-text | Translation, summary, explanation, question generation or continuation requires new candidate adjudication. Can be B only for a narrower explicit executable property, not overall quality. |
| C-neg | Wrong-answer generation is not a certified negative set; validate wrongness for the same question and all acceptable answers. |
| D-mixed | Opaque mixed synthetic/instruction shard; recover task provenance before claiming a usable decision target. |
| D-review | Descriptive filename does not establish a target contract here. Keep it in inventory; defer rather than infer labels. |

Name-based dispatch checks generative/question-writing variants separately
from source-benchmark names. Some files contain multiple contracts; the route
does not certify every template or row. In particular, CoT target extraction
can lose the final answer or misread a demonstration. NIL/abstention needs an
evidence-defined target, not a fabricated extra class. A reference rating can
support Score only on its original defined scale, not a new quality rubric.

## Original Sapient: Practical Assessment

**FLAN:** Native MCQ/label candidates include the preserved versions
`ai2_arc_ARC-Challenge_1.0.0`, `ai2_arc_ARC-Easy_1.0.0`, `bool_q_1.0.0`,
`openbookqa_0.1.0`, `piqa_1.0.0`, `hellaswag_1.1.0`, `winogrande_1.1.0`,
`story_cloze_2016_1.0.0`, GLUE `2.0.0`, SuperGLUE `1.0.2`, and SNLI `1.1.0`.
The complete task/template inventory, not this shortlist, defines coverage.
RACE question-writing/no-option templates, SciQ Direct Question templates,
Social IQa question generation, QASC fact generation and CoS-E explanations
must not inherit A just from their benchmark name. NIV2 is explicitly split
into 1,556 named tasks: classification can be A, list/arithmetic checks B,
translation/generation C, and unresolved descriptions D. All are listed.

**Tasksource:** Existing NLI/logic candidates include WANLI, ConTRoL-nli,
fracas, FOLIO, Ruletaker, PARARULE-Plus, temporal-nli, tomi-nli, monotonicity,
robust NLI and probability-words variants. MedQA-USMLE-4-options-hf, medmcqa,
LogiQA, balanced-copa and other preserved MCQ tasks map to supplied options.
Citation intent/scicite and scientific exaggeration can retain class labels.
CoNLL, Few-NERD, JNLPBA, NCBI Disease and dependency/tag configurations need
aligned atomic tag decisions (B-tags). The attachment explicitly includes
social/review/toxicity tasks even when path-denied; being easy classification
does not clear privacy or training restrictions. Remaining D-review entries
are genuine review gaps, not assertions that the upstream dataset has no label.

**Platypus:** Exact files are `arb_law`, `arb_math`, `arb_physics`,
`arb_reading`, `arb_science`, `openbookqa`, `reclor`, `scibench`, `scienceqa`,
and `theoremqa`, all `.jsonl`. MCQ branches are A candidates; numeric/free
responses require C/B checks. ReClor and SciBench originals are excluded /
eval-only under the documented filter; do not resurrect them. ScienceQA
requires text-sufficiency checks for visual questions, plus split eligibility.

**Math and reasoning:** `nvidia/AceReason-1.1-SFT`,
`nvidia/OpenMathInstruct-2`, `open-thoughts/OpenThoughts2-1M`, and
`MegaScience/TextbookReasoning` are identified in their local
`data_io/pipe_clustered/clean_*.py` cleaners. A stored rationale or boxed
answer is not a correctness proof; C-answer is the default, with B only for
supported verifiable subsets. `dmmath` comes from
`raw_data/mathematics_dataset-v1.0`; difficulty/module identities are retained
for all 168 files. AMPS Mathematica's 137 symbolic task files have plausible
checker-based routes, but require domain assumptions, numerical tolerance and
equivalence handling rather than string inequality. The attachment's B-check
therefore means conditional feasibility, not an implemented verifier.

**Sudoku and SYNTH:** `data_io/pipe_clustered/clean_sudoku.py` reads
`sapientinc/sudoku-extreme/train.csv`, retaining 81-character puzzles and
solutions in `sudoku_extreme__all.parquet`: B-grid is concrete. In contrast,
the 500 original SYNTH shard names reveal no constituent task identities;
they remain D-mixed. Do not conflate these with later `sapient-synth-*`
anonymized replacement repositories or `synth_high40`/`synth_repeat30` pools.

## DFM1-7 Version Changes

| Version | What changes for decision coverage | Local evidence |
|---|---|---|
| DFM1 (`dfm`) | Filtered Sapient plus Danish raw/text, instruction, translation, math and agent mixtures. Raw text has no native decision label. | `data/show_analytics_dfm.md`; `data_io/prefix_config_dfm.yaml` |
| DFM2 | Adds DynaWord prefix-continuation variants 1-2, denoising variants 1-2, and span-fill variants 1-6. B applies only to well-defined reconstruction/corruption decisions; continuation remains C/D. | `scripts/generate_dfm2_dynaword_tasks.py`; `data/converted_sources_dfm2_dynaword_tasks` |
| DFM3 | Adds Common Pile direct/prefix continuation, denoising and span-fill v1-v3. Historical raw inclusion is recorded, not authorized anew. | `scripts/generate_dfm3_common_pile_tasks.py`; `data/converted_sources_dfm3_common_pile_tasks` |
| DFM4 | Adds DynaWord/Common Pile paragraph reordering and four summarization families. B for source-order provenance; C for overall summary quality. | `scripts/generate_dfm4_tasks.py`; `data/converted_sources_dfm4_paragraph_reorder`; `data/converted_sources_dfm4_summarization` |
| DFM5 | Restores original Sapient task names; replaces older DynaWord objective trees with exported task families; adds synthetic replacements and transformations. | `scripts/build_tokenized_dfm5_tree.py`; `export/`; `export-upload/` |
| DFM6 | Rebuilds richer chat/tool supervision from original messages rather than flattened instruction/response. Adds no automatic correctness labels. | `scripts/build_dfm6_chat_source_tree.py`; `data/dfm6_chat_sources` |
| DFM7 | Adds Danish mixed instructions, Kaenguruen, arena branches, RLVR math adapters, and corrected native tool families. Original malformed DOLCI tool branches are zero-capped. | `scripts/prepare_dfm7_special_sources.py`; `data/dfm7_special_sources`; canonical July 1 rebuild |

Historical Common Pile components named by the local filtered/converted roots:
`arxiv_abstracts_filtered`, `arxiv_papers_filtered`, `library_of_congress`,
`project_gutenberg_filtered`, `public_domain_review_filtered`,
`pubmed_filtered`, `regulations_filtered`, `stackexchange_filtered`,
`usgpo_filtered`, `uspto_filtered`, `wikimedia_filtered`, and
`wikiteam_filtered` (under `common_pile_*`). These were source documents for
multiple objectives, not independent labels. Current raw-continuation policy
permits only Danish DynaWord; a historical Common Pile entry is not a proposal
to restore raw continuation or bypass component eligibility.

The four DFM4 summarization origins are `common-pile/arxiv_papers_filtered`,
`ccdv/govreport-summarization`, `GEM/wiki_cat_sum`, and
`laion/Scientific-Summaries` (arXiv slice). All are C for semantic candidate
selection; structured-summary truncation can invalidate apparent evidence.
Do not transfer later repaired-source quality claims to these historical rows.

## Other Early Families

Every exact category and known HF ID is in the
[family table](early-inventory-dfm-families.md); the following mapping explains
its routes without treating umbrella mixtures as homogeneous.

* **Executable constraints (B subset):** `allenai/IF_sft_data_verified`,
  `synquid/ifbench-train`, `allenai/tulu-3-sft-personas-instruction-following`,
  and `nvidia/Nemotron-SFT-Instruction-Following-Chat-v2` can provide
  constraint-pass/fail questions only where original constraints and reliable
  CPU checkers are retained. A verified positive alone does not supply false
  responses. Semantics/style requirements without checkers stay C.
* **Grounded Danish/reference (C):** `danish-foundation-models/laerebogen`,
  local `dbc`, `lexdk`, `synquid/wiki-instruct-da`, and all named Oliver Kinch
  QA/backtranslation/document families need source-supported candidate
  adjudication. Numeric table facts in `dst-table-prompts-bt` can become B
  only with the actual table and a verified calculation retained.
* **Translation (C):** `schneiderkamplab/opus-da-en-permissive`,
  `synquid/translation-100k`, `synquid/mt-da-deepseek`, and Oliver Kinch
  `machine-translation-da-{en,uk,ar}` retain parallel positives, not a
  complete set of incorrect alternatives. Source/target language and
  exact-copy violations support narrower B checks, not translation quality.
* **General chat/instruction (C/D):** Tulu v2/v2-long/3 mixtures, Dolci base
  and No-Tools, `HuggingFaceH4/no_robots`, WildChat-Qwen, Nemotron multilingual,
  and arena conversation branches need constituent routing. Do not call
  two recorded answers a preference pair without an actual comparison label.
* **Reasoning/code (C, B subset):** AllenAI personas math/algebra/code,
  big-reasoning-traces, verifiable GPT-4.1/o4-mini, open_math_2_50k_r1,
  `synquid/danish-verifiable-reasoning`, and RLVR GSM/MATH use checkers where
  available. DFM7's RLVR adapter recovers `ground_truth` and boxes the answer;
  boxing is formatting, not newly verified reasoning.
* **SciRIFF (mixed/deferred):** `allenai/SciRIFF-train-mix` can contain finite
  labels and extraction tasks as well as generation. Retain task IDs and route
  A/B only on documented schemas; the category alone supports no blanket A.
* **Historical derivatives:** published `schneiderkamplab/common-pile-*`,
  `danish-dynaword-*`, `transformations-*`, and `sapient-synth-*` IDs are
  explicitly resolved in the family table from `docs/dfm8-datasets.md`.
  Denoising/span-fill/reordering are B only under corruption-validity rules.
  Danish-Danish, Danish-English, English-Danish and English-English
  transformation variants preserve direction; semantic rewrites remain C.
  Synthetic replacements need their own provenance and target validation;
  they do not restore permission to use excluded originals.

## DFM7 Constituents and Split Gates

`danish-foundation-models/dfm-dyna-instruct` is not one task. The historical
DFM7 analytics explicitly list these data directories (the final `.parquet`
filename normally repeats the directory name):

| Subdataset | Candidate mapping |
|---|---|
| `agentic-code-sft-mix-v1` | C next-action/code candidates; B only with executable state/tests; not native tool-call target supervision |
| `apertus-sft-mixture-shards` | D/mixed pending source routing; `part-0000.parquet` through `part-0097.parquet` are all observed shards |
| `da-refusals` | C refusal appropriateness; generated refusals alone do not establish a binary policy gold label |
| `danish-verifiable-reasoning` | C/B verified math/code subset |
| `ifbench-train` | B executable constraint subset |
| `mt-da-deepseek` | C translation |
| `translation-100k` | C translation |
| `when2call` | A candidate for explicit decision/no-call labels; not native call-argument SFT |
| `wiki-instruct-da` | C grounded QA/instruction |
| `wildchat-qwen` | C/D general chat; privacy gate |

The source-tree builder replaces the monolithic
`data/apertus-sft-mixture/apertus-sft-mixture.parquet` with those shards.
Seven additional Oliver Kinch categories are explicit in the family table:
`danish-qa`, `danish-summarization`, `da-instruct-dynaword`,
`da-instruct-dynaword-hq`, `da-instruct-dynaword-contemporary`,
`da-instruct-dynaword-contemporary-hq`, and `autodata-da-sft`.

Native tool mappings:

| DFM7 derivative | Origin | Decision assessment |
|---|---|---|
| `dolci_native_tool_use` | `allenai/Dolci-Instruct-SFT-Tool-Use` and `allenai/Dolci-Instruct-SFT-Tool-Use-SA` | B schema validity; A only for demonstrably labelled routing; C for semantic best-next-action |
| `glaive_native_tool_use` | `glaiveai/glaive-function-calling-v2` | Same; preserve original tool definitions and call context |
| `toolace_native_tool_use` | `Team-ACE/ToolACE` | Same; parallel-call sets are not necessarily single-choice |
| `xlam_native_tool_use` | `Salesforce/xlam-function-calling-60k` | Same; supplied candidate arguments need semantic checks |
| `nemotron_agentic` | `nvidia/Nemotron-SFT-Agentic-v2` | Already structured tools/calls; schema-valid does not imply successful or uniquely correct action |

**Kaenguruen split warning:** `scripts/prepare_dfm7_special_sources.py`
function `write_kaenguruen` explicitly loads
`danish-foundation-models/kaenguruen`, split **test**, and emits `train.jsonl`.
The analytics also list `kaenguruen__data__test-00000-of-00001.parquet`.
Existing options make it structurally A, but do not authorize fresh training
or an independent test score. Treat as D/held-out pending the shared split
policy; preserve historical exposure and deduplicate both representations.

`ai_arena_udtraek` extracts both `conversation_a` and `conversation_b`;
branch existence is not a winner label. `ai_arenaen_conversations` appears in
the DFM7 builder's candidate list but not as a category in the inspected
canonical analytics; distinguish configured candidate from observed exposure.
`danish_wildchat4_8m` and `nemotron_swe` are explicitly excluded by the DFM7
union builder. The former has translated user prompts without assistant
answers; the latter has context/size risks. Both are historical/deferred D,
not recommended easy decision material.

## Eligibility Overrides and Remaining Limits

The current path-filter column is a read-only application of
`config/data/source_filter.yaml` precedence: include, allow override, deny,
then default allow. `override`/`default` are not legal clearance or historical
sampling proof. `denied` overrides proposed A/B feasibility for this review.
Raw excluded sources remain historical entries and must not be resurrected.

Historical note retained rather than overwritten: the earlier
[Sapient cleaned policy](../data-mix-policy/sapient-cleaned-policy.md) broadly
excluded most FLAN/Tasksource. The later
[source-filtering record](../source-filtering.md) explicitly documents its
superseding default-allow implementation on 2026-08-18 with privacy-focused
denials and overrides. Neither version can be retroactively used to infer
every earlier DFM's exposure. ReClor/SciBench originals, denied personal/social
content, eval-only splits and disabled sources remain separate status gates.

No row-level audit, exact yield estimate, new negative generation, checker
implementation, tokenization or GPU work was done for this assessment.
Unpinned source revisions, opaque SYNTH tasks, unresolved D-review contracts,
and DFM6 exposure joins are explicit limits. The parent collection owns the
shared ledger, directory indexes and bundle-level update log.
