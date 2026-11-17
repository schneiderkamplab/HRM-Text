---
type: Reference
title: DFM8-13 Decision Dataset Review
description: Manifest-backed DFM8-13 bounded-choice source review and inventory gaps.
tags: [decision-datasets, provenance, training-data]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM8-13 Decision Dataset Review

## Scope And Evidence

This is the middle-phase contribution to the DFM1-15 overview, reviewed on
2026-10-21. It inventories sources, not converted Jev datasets. No conversion,
model audit, GPU work, download, live Hub verification or dataset change was
performed. Local manifest membership is high-confidence; proposed applicability
is medium-confidence until row/schema validation. See the
[overview](../decision-datasets.md) and [conversion recipes](conversion-recipes.md)
for common methods and safeguards.

Use the common rubric: **A** existing decision label/options; **B** CPU or
mechanically derived decision target with corruption-validity filters;
**C** validated negatives/new adjudication required; **D** poor/unlabelled,
excluded or deferred. B/C means only the explicitly stated subtask is B;
the remainder is C, not a blanket conversion approval. A synthetic label remains
synthetic supervision, not independently certified truth. A reference response
is never assumed uniquely best. Typed decisions need an observable state and
bounded output, not a renamed free-form completion.

## Complete Manifest Tables

| Inventory | Coverage and links | Membership evidence |
|---|---|---|
| DFM8 | [159 HF repositories](middle-dfm8.md), plus DBC/LexDK below | Historical nonzero sampled inventory, including inherited DFM1-7 sources |
| DFM9 | [9 additions/replacements](middle-dfm9.md) | Converter, downloader and dated sampling record; aliases reconciled |
| DFM10 | [72 packages](middle-dfm10.md) | Export manifest, including upstream IDs and materialized repairs |
| DFM11 | [11 pinned packages](middle-dfm11.md) | Five rebuild configurations; identity/charter caveats below |
| DFM12 | [381 components, part 1](middle-dfm12.md), [part 2](middle-dfm12-2.md) | Recovered epoch-11 composition and builder publication mapping |
| DFM13 | [312 additions, part 1](middle-dfm13.md), [part 2](middle-dfm13-2.md) | Exact current registry records, including four holds |
| Separate DaLA v2 | [34 language packages](middle-dala.md) | Packaging code and exact pinned evaluation-package paths; eval rows remain held out |
| Candidates / upstream | [Downloader and source catalogs](middle-candidates.md) | Not a training-membership claim; explicit unknowns and deferrals |

These counts use different units and overlap. Do not sum them as unique
repositories or independent examples. All IDs preserve recorded case. Source
names, package IDs, upstream IDs and component keys are deliberately separate.
The [coverage ledger](coverage.md) records all-source and historical membership;
join these tables on exact IDs and manifest keys, not display names.

## Applicability Key

The table entries use the following compact source-review terms. These are
routing/qualification notes, not implementation recipes.

| Family | Class / proposed decision | Principal limitation |
|---|---|---|
| Existing label or option | A | Preserve original ontology, synthetic-label provenance and ambiguity; no relabelling from a reference answer. |
| Token/span label or candidate-entity membership | B | Use explicit annotated tokens/offsets; reject broken BIO, incomplete annotation and cross-split duplicates. |
| Candidate answer equality or executable result | B/C | B only for independently checkable numeric/symbolic/executable targets; otherwise C. Preserve units, domains, alternate valid answers. |
| Tool name/schema validity; candidate next action | B/C | B for explicit schema violations and trace extraction; semantic tool/action preference is C; retain history and tool results. |
| Pass/fail for explicit output constraints | B | Use a complete deterministic validator; a valid format is not a correct factual answer. |
| Known corruption/edit validity or reconstruction | B/C | B only with traceable corruption and validity filters; valid alternative edits need C; no changed-text-is-bad heuristic. |
| Original-order recovery / valid next block | B/C | B for recorded permutation recovery with distinct blocks; semantic coherence or unique best order needs C. |
| Masked source-span recovery | B/C | B only for explicitly defined exact source recovery; plausible alternative completions require C. |
| Translation adequacy or source-target match | C | Parallel positive is not a uniquely best translation; validate mismatches, equivalence, alignment and language variants. |
| Evidence support / summary or rewrite adequacy | C | Need supported claims and adjudicated distractors; reference alone cannot rank other faithful summaries. |
| Original pair preference / rating | A/C | A only when original candidates, same state, tie semantics and votes/scores survive; chosen-only exports are C until recovered. |
| Task-routed candidate response judgment | C | Split constituent tasks first; recover original bounded labels where present; broad SFT has no negative labels. |
| Fact-registry entailment / identity consistency | B/C | B for explicit versioned facts; conversational style and implied self-claims need C; profile-specific, not general truth. |
| No existing decision target | D | Grounding/raw documents only; require a separately specified B transformation or C adjudication, not wholesale conversion. |
| Defer / excluded | D | Do not override rights, privacy, source-fidelity, evaluation or unresolved provenance holds. |

## DFM8 Specific Additions

The [targeted synthesis history](../dfm8-plan/dfm8-targeted-synthetic-upload.md)
and historical inventory name all six packages explicitly:

| Exact HF ID | Proposed decision and source-specific caveat |
|---|---|
| `schneiderkamplab/dfm8-synthetic-code-debugging` | B only for candidate test/compile results under a preserved harness; otherwise C repair ranking. Passing tests is not proof of unique correct code. |
| `schneiderkamplab/dfm8-synthetic-constrained-format-following` | B constraint pass/fail for recoverable machine-checkable contracts; C for semantics. Do not infer an absent validator from a package title. |
| `schneiderkamplab/dfm8-synthetic-danish-summarization-rewrite-controls` | C summary support/style or rewrite adequacy; B only for explicit surface constraints. Multiple faithful outputs are valid. |
| `schneiderkamplab/dfm8-synthetic-multiturn-danish-english-chat` | C next-response suitability with full conversation; no labels for alternative responses. |
| `schneiderkamplab/dfm8-synthetic-native-tool-calling` | B schema/argument-type validity; C tool/action correctness. Later DFM11 replacement must be preferred for repaired training lineage. |
| `schneiderkamplab/dfm8-synthetic-strict-math-answer-contract` | B answer-format and independently checkable answer validity; C when gold equivalence cannot be mechanically established. |

The eight Common Pile/DynaWord transforms and four bilingual
`transformations-*` repositories are individually enumerated in the DFM8 table.
Task-specific corruption records can support B, but translation and semantic
reconstruction judgments remain C. Raw Common Pile is not thereby approved
continuation data. Only Danish DynaWord has the stated raw-continuation role.
DBC and LexDK are agreement-backed local sources, **no established public HF
ID**: C for supported factual decisions after provenance reconstruction, D for
unlabelled text/uncleared redistribution. Do not invent public repository aliases.

## DFM9 And DFM10 Qualifications

[DFM9 source additions](../dfm9-plan/new-source-additions-code-math-english-instruction.md)
contain historical aliases; the DFM9 table records exact converter/downloader
IDs separately. Inherited Sapient/FLAN/Tasksource membership does not override
the current deny-by-default policy and narrow task allows. Mixed repositories
need constituent/task resolution; apparently labelled tasks are not blanket A.

The following DFM10 packages merit explicit treatment, not generic SFT labels:

| Exact HF package | Proposed decision | Qualification |
|---|---|---|
| `schneiderkamplab/dfm10-mimir-boolq-entailment-sft` | A only for preserved yes/no/entailment labels; otherwise C | Novel grounded passages/propositions, not authorization to import BoolQ evaluation rows. Generated propositions need support checks. |
| `schneiderkamplab/dfm10-mimir-drop-reasoning-sft` | B arithmetic/count/span checks where evidence and operation are recoverable; C otherwise | Novel DROP-style tasks, not the DROP benchmark itself. Numeric formatting/units and evidence completeness matter. |
| `schneiderkamplab/dfm10-mimir-event-coreference-sft` | A explicit relation labels or B candidate-link membership; C semantic alternatives | Preserve entity/event IDs and temporal state; no closed-world negatives from incomplete annotations. |
| `schneiderkamplab/dfm10-mimir-ifeval-verifier-sft` | B explicit verifier pass/fail | Do not call all generated responses positive without running the recorded verifier in a future conversion. |
| `schneiderkamplab/dfm10-mimir-answer-contract-calibration` | B contract-choice/validity | A surface-answer contract is separate from factual correctness. |
| `schneiderkamplab/dfm10-mimir-grounded-expanded-sft` | C evidence support or response adequacy | Recover grounding provenance; accepted SFT is not a labelled negative set. |
| `schneiderkamplab/dfm10-alexandra-dane` | B token-type or proposed-span membership | Preserve original token offsets and ontology; do not infer negatives outside exhaustive labels. |
| `schneiderkamplab/dfm10-alexandra-multi-zebra-logic` | B finite assignment/constraint satisfaction if original constraints survive; C otherwise | Do not generate arbitrary plausible-but-unchecked distractors. |
| `schneiderkamplab/dfm10-danish-lexical-sentiment-sft` | A original polarity / Score when scale preserved | Lexical polarity is not necessarily contextual sentence sentiment. |
| `schneiderkamplab/dfm10-danish-framenet-sft`, `schneiderkamplab/dfm10-cor-sem-sft` | B annotated frame/sense membership; C unannotated alternative senses | Polysemy and incomplete lexical coverage prevent universal negative labels. |
| `schneiderkamplab/dfm10-synthetic-values-model-charter-da` | A original DPO labels if pair provenance retained; C SFT response ranking | Inspect nominal split policy; historical authorization included all 1,360 SFT and DPO rows, not a protected test split. |

All 72 package records are in the full table, including MedQuAD, OpenStax,
Folketing, native tools, scholarly summaries, modernization and repaired sources.
The manifest excludes `alexandrainst/dacoref`; it is a B candidate for gold
coreference membership but **D deferred/excluded for this DFM10 membership**.
The original Nordjylland conversion was replaced. A released repair does not
make both versions independent evidence. `abachaa/MedQuAD`, `kb-dk/SKS_tei`
and `DSL/CST COR.SEM 1.0` are literal upstream attribution strings; the first
two must not be advertised as HF datasets without separate host evidence.

## DFM11 Boundaries

Tool replacement configuration distinguishes structural validation/semantic
sampling from full task correctness. Native trace prefixes can provide observed
actions but do not prove all other tools/actions wrong. TinyGSM Python and
GSM8K Prolog packages support B executable/numeric decisions only with preserved
execution/gold evidence; retain train/test exclusion and solver failure states.

FineInstructions EN/DA and Koolbardi DA/EN are C for response suitability. The
English rebuild selects controlled chats plus a source-balanced 100K legacy
chat slice; paired rows are published but not separately tokenized. Danish
training similarly selects chats. Recover full document evidence from metadata
before judging grounding; model acceptance is not gold preference supervision.
The withdrawn `fineinstructions/fineinstructions_nemotron` proposal is D and
must not be confused with these DFM-owned releases.

DFM11 inherits the DFM10 charter package above. Its post-plan notes a physical
alias `data__model_charter_values_da.jsonl` versus policy prefix
`dfm10_synthetic_values_model_charter_da__`; resolve before claiming coverage.
`config/data/dfm11_identity_da_en.yaml` names a later continuation corpus, not a
new independently identified DFM11 Hub repository. The relevant identity data
are DFM12-generated XL/profile-specific packages in the 381-source table.
Proposed B is consistency against versioned explicit identity facts; broader
conversation judgments are C. Never blend XL and XXL-wide identities.
See [identity provenance](../dfm12-identity-export.md) and
[DFM11 post-plan](../dfm11-post-plan.md).

## DFM12 And DFM13 Boundaries

The [inherited-base reconciliation](../dfm13-inherited-base-readiness.md)
supersedes treating the old 89-component DFM12 base as complete: later scope
has 381 components, 292 additional names and nine replacement identity hashes.
357 exported packages plus 24 local DaLA task components are not 381 HF repos.
The latter map to 12 existing producer repositories. The no-identity epoch-11
snapshot has identity repeat zero; subsequent approved DFM13 XL identity21
weighting is separate. Published XXL-wide identity21 stays excluded/repeat zero.

Historical `giannor/dala_tv2r_it` and `giannor/gec_dala_tv2r_it` are Danish,
not Italian. They intentionally included all splits; legacy evaluation is
train-contaminated. New DaLA releases use train-only integration. Their
validation/test package paths prove evaluation availability, not training
admission. Existing21 legacy evals and accepted-v2 evals are different
populations. Preserve pairs/clean-source groups across splits. Source-article
overlap was explicitly permitted in some lineage; it is not global
sentence-level decontamination. See [TV2R policy](../dfm8-plan/danish-linguistic-acceptability-and-gec-data.md)
and [DaLA coverage](../dfm13-dala-eval-coverage.md).

In DFM13, jjzha SkillSpan/Kompetencer/Green support B from validated BIO tokens;
Dutch exam MCQ supports A from original options/answer index, train only.
IMDb supports A binary `positief/negatief`, not an invented neutral class.
CroCo translations remain C unless constituent labels can be recovered; 9,337
FLAN-derived rows were excluded and tool-bearing rows were separately held.
[The jjzha runbook](../dfm13-jjzha-native-additions.md) records these boundaries.

Arena/ComparIA/HelpSteer upstream votes or ratings may support A Choice/Score,
including ties/abstention. Preferred-only exports cannot reconstruct losing
candidates or numeric ratings. Recover original same-state pairs; audit repairs
may invalidate old pair comparisons. Overlapping Arena 55K/100K/140K variants
must be deduplicated. HelpSteer edits are not automatically preferences.
The registry says automated accepted/recovered/repaired, **not certified gold**.

Baltic QA and both Latvian P3 licence slices remain four explicit
`quality_hold_source_fidelity` entries. Uploaded/tokenized is not admission.
Latvian P3 task labels alone cannot clear source fidelity, denied constituent
lineages or benchmark overlap. Persian Fars summary exclusions are not erased
by other accepted Fars components. RepoChat and both search datasets are excluded
from the finalized inheritance scope recorded in the runbook; reviewed campaign
artifacts are not automatically additions.

## Gaps And Handoff

The local `data/dfm12`, `data/dfm13` and `exports_dfm12` roots were absent
on this host. Repository reports/configs support enumeration, but current
row schemas, per-package revisions and actual final sample membership cannot
all be reverified here. DFM12 destinations use the builder's documented mapping;
that is not a replacement for receipt-level pins in the [coverage ledger](coverage.md).

Broad Sapient, Natural Instructions, DynaInstruct, Dolci/Tulu and multilingual
packages are exhaustively listed at repository/component granularity, not every
embedded original dataset. Their unexpanded constituent tasks remain explicit
C/unknown until metadata is joined. Audit verdict stores are not clean public
datasets: reject may mean language, PII, truncation, transport or unsupported
premise, not an incorrect answer. Future use requires same-state candidate and
rubric recovery, policy/rights clearance and new adjudication where necessary.

DBC/LexDK and local identity continuations have explicit no-HF/unknown mappings.
Current HF existence/access was not checked. No missing ID was guessed from a
friendly source name. Namespace-derived DFM12 destinations are marked as such.
See the [overview](../decision-datasets.md), [coverage ledger](coverage.md) and
[conversion recipes](conversion-recipes.md) for cross-phase coverage and methods.
