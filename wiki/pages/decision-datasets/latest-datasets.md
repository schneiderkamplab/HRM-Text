---
type: Reference
title: Latest DFM Decision Dataset Candidates
description: Inventory-based decision suitability of DFM14 language additions and DFM15 reasoning and Dyna additions, with historical lineage boundaries.
tags: [data, decision, dfm14, dfm15, jev]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Latest DFM Decision Dataset Candidates

Review only: no conversions, audits, GPU work, admission changes or source-data
edits. Inventory facts are locally inspected; suitability assessments are
proposals, not validated decision datasets. See the [DFM1-15 decision overview](../decision-datasets.md)
for historical membership and the all-source ledger. This page covers the
latest additions, not a replacement accounting of the inherited corpus.

## Contract and Rubric

Jev evaluates typed questions against supplied state: Choice selects an option,
Score evaluates a rubric, and Noul evaluates a truth statement. It is not a
freeform answer generator. See the [primary introduction](https://docs.typesafe.ai/introduction).
The mappings below are proposed dataset designs, not claims of Jev compatibility
or measured performance. See the [overview](../decision-datasets.md) and
[conversion recipes](conversion-recipes.md) for methods and safeguards;
this page supplies source-specific evidence.

| Grade | Meaning |
|---|---|
| A | Existing decision label/options; preserve the original label semantics. |
| B | CPU/mechanically derived decision target, with corruption-validity filters. |
| C | Needs validated negatives/new adjudication; not easy wholesale. |
| D | Poor/unlabelled or deferred. |

A grade is independent of admission status. An eval-only MCQ can be A in
structure but remains prohibited as training. Generated references are never
assumed uniquely best. A format repair supplies no new correctness label.

## Coverage and Status

The [DFM14 component ledger, part 1](latest-dfm14-components-1.md) and
[part 2](latest-dfm14-components-2.md) enumerate all **277** names and exact HF
IDs from `config/dfm14_sources.json`, cross-checkable against
`data/dfm14/release-v1/source-inventory.json`. These are 261 unique HF packages:
245 regular components plus 32 acceptability/correction components sharing 16
DaLA repositories. Registered/released is not a claim that every backing row is
sampled or decision-labelled.

DFM14 inherits DFM13, which inherits earlier DFM versions. Its 277 additions
are not the entire corpus. Historical source exclusions, repetitions, repairs,
split boundaries and replacement routes remain in force. The reconciled DFM14
inventory records 135,548,235,716 tokens/epoch and three epochs; an earlier
113.88B remote sample omitted inherited exposure and was superseded. See
[release history](../dfm14-cpu-release.md).

DFM15 has two distinct changes: **83 repaired inherited parts across six source
families**, and **four late additions**. See [native reasoning and late
additions](latest-dfm15.md), including the complete 42-repository organization
scan. Neither is a new set of 83 independent datasets.

**Status conflict, resolved in documentation only (2026-10-21):**
`config/dfm15_sources.json` still says `tokenized_staging_not_resampled` and
`sampled: false`; the October 17 full-sample completion record in
[DFM15 plan](../dfm15-plan.md) supersedes that staging status and reports all
four additions admitted after length exclusions. Mark these **active per
completion record**, not pending merely because the registration metadata is
stale. The cited `data/sampled_dfm15/full-mixture-verified.json` is absent on this
checkout, so fresh local receipt verification remains a gap. Do not infer live
process status from either document.

## All Language Expansions

DFM14 adds Arabic `ar`, Welsh `cy`, Basque `eu`, Irish `ga`, Galician `gl`,
Hebrew `he`, Hindi `hi`, Indonesian `id`, Japanese `ja`, Korean `ko`, Macedonian
`mk`, Maltese `mt`, Russian `ru`, Turkish `tr`, Vietnamese `vi`, Chinese `zh`.
Each has all twelve regular components below plus acceptability and correction
in `schneiderkamplab/dfm14-dala-v2-{code}-compact`. This accounts for 224
components (16 x 14), not 224 distinct source corpora.

Exact regular HF pattern: `schneiderkamplab/dfm14-{code}-{suffix}-r1`.
The explicit ledgers remove any ambiguity in this compact cross-product.

| Suffix / component | Grade | Bounded decision proposal and limitation |
|---|---|---|
| `instruction` | C | Candidate response adequacy or atomic constraint truth. Recover A labels only where original tasks actually preserve them; a mixed SFT export is not all A. |
| `denoising` | B/C | B for known corruption detection or exact source restoration under an explicit identity task; C for best grammatical correction. Exclude no-op/valid corruptions and alternative legitimate readings. |
| `paragraph-reordering` | B/C | B for original-position relations with source indices; C for uniquely coherent ordering. Swaps can preserve coherence, and duplicate paragraphs are ambiguous. |
| `prefix-continuation` | C | Select a context-compatible continuation after adjudication. Actual continuation is not the only valid one; unrelated random text is usually too easy. |
| `span-filling` | B/C | B for source-exact span identification with offsets and an explicit reconstruction contract; C for semantic completion. Inflectional and synonymous alternatives are not automatically wrong. |
| `synthetic-grounded-instruct` | C | Evidence-supported claim Choice/Noul. Require visible support and validated contradictions; absent support is not always falsehood. |
| `synthetic-math-code` | C | B only where executable tests or an exact reliable checker independently establish candidate outcomes. A generated solution alone is not such a checker. |
| `synthetic-multiturn` | C | Next-action or conversation-state decision. Keep all prerequisite turns; alternate reasonable responses need adjudication. |
| `synthetic-openhermes` | C | Atomic constraint satisfaction or response choice; avoid teacher style/length proxies for quality. |
| `synthetic-summary-rewrite` | C | Claim preservation, omitted fact or edit validity; many summaries/rewrites are valid. Score requires a defined rubric and labels. |
| `synthetic-tool-dialogue` | C | Tool/action/argument choices from state and schema; B for schema/type violations only. Syntactic validity does not establish task success. |
| `translation` | C | Translation adequacy or meaning-preservation choice with adjudicated alternatives. Exact English pivots do not guarantee semantic equivalence. |
| DaLA acceptability | A | Existing acceptable/unacceptable labels to Choice/Noul, preserving heldouts and label polarity. Audit-accepted packaging is not independent native-speaker gold. |
| DaLA correction | C | Choose among corrections only after validating alternatives; B is limited to mechanically established edit/corruption properties. |

Remaining **53 components** are fully included, not hidden by the new-language
summary: 34 translation components for inherited variants; four transformations
each for Persian `fa`, Faroese `fo`, Polish `pl` (12); English instruction r1/r2
and five English synthetic knowledge components (7).

The 34 inherited translation codes are `be bg bs ca cs da de el en es et fa fi
fo fr hr hu is it lb lt lv nb nl nn pl pt-pt ro sk sl sq sr sv uk`. Together
with the sixteen additions this is 50 variants, not evidence of balanced
pairwise coverage or equal native quality. Chinese scope is initially Simplified
Mandarin, Arabic Modern Standard Arabic; neither implies all dialects.
Preserve `nb`/`nn` and `pt-pt` distinctions. Test native morphology, script,
sentence boundaries and cultural plausibility of negatives per language.

## English Knowledge and Enrichment

The exact seven non-translation English packages are
`schneiderkamplab/dfm14-en-instruction-r1`,
`schneiderkamplab/dfm14-en-instruction-r2`,
`schneiderkamplab/dfm14-en-synthetic-commonsense-r1`,
`schneiderkamplab/dfm14-en-synthetic-evidence-r1`,
`schneiderkamplab/dfm14-en-synthetic-explanatory-qa-r1`,
`schneiderkamplab/dfm14-en-synthetic-science-r1`, and
`schneiderkamplab/dfm14-en-synthetic-textbook-r1`. All default to C.
Commonsense contrasts can have multiple reasonable answers; evidence tasks
need entailment/contradiction adjudication; science/textbook questions must be
answerable without missing figures. A label-free explanation is not a Score.

These are release packages, not one-to-one upstream datasets. The preparation
history includes Smol Magpie/constraints/rewrite/summarize, SmolTalk2 reasoning
and tools, OpenCoder educational/package, UltraChat, Nemotron Science, Swallow
math, peS2o and StackExchange. Recover row-level upstream lineage from release
provenance before source-level splits or deduplication; package names alone do
not establish which upstream subset supplied an individual row. Do not count
both the preparation corpus and its accepted export as separate additions.

## Dyna and Pending Sources

The Persian/Faroese/Polish transformation packages above are released additions.
Their grounding candidates include `MatinaAI/matina_persian_text_corpus`,
`danish-foundation-models/faroese-dynaword` (`logir`) and
`SlayerLab/polish-dynaword`. Raw grounding is D as a direct decision dataset;
mechanical predicates can be B, semantic QA/summary choice remains C.
Access granted to Matina is not itself evidence of usable decision labels.

The [Dyna review](../dfm14-potential-additions.md) also records candidates that
must not be silently promoted because related languages have release packages:

| Exact source / subset | Status and grade | Caution / proposed bounded task |
|---|---|---|
| `danish-foundation-models/danish-dynaword`, `logir` | Candidate; D raw, C grounded | Date-conditioned evidence judgments; historical law is not timeless truth. Shared hosting with Faroese does not prove parallelism. |
| `SlayerLab/polish-dynaword`: `openstax_pl`, `open_agh_chemistry_pl`, `edukacja_medialna_pl`, `open_icm_pl`, `studia_bas`, `wiadomosci_statystyczne_pl`, `kultura_bez_barier_pl` | Candidate subset provenance; B/C derived | Educational/scientific/policy grounding. Release-level `pl` membership does not prove every proposed subset was admitted. |
| Same repository: `sejm_api_2011_2022`, `sejm_committee_transcripts`, `sejm_interpellations` | Candidate; C | Speaker/claim attribution, answer linkage; questions without actual answers do not supply QA gold. |
| Same repository: `fandom_pl`, `common_voice_pl`, `ted_pl` | Candidate; B/C | Fiction-aware evidence, sentence corruption, procurement extraction respectively. `ted_pl` is not TED talks; short sentences cannot support paragraph-order tasks. |
| Same repository: `plwiki_talk`, `plwiki_user_talk`, `nonsa` | Deferred; D | Context-poor discussion and satire are poor generic factual targets. |
| Same repository: `samorzad_gov_pl` | Replacement candidate; D raw | De-identified replacement, not additive duplicate. |
| Same repository: `global_voices`, `rock_pollub_pl`, `uzp_orzeczenia_pl` | Not new payload additions | Sidecar-only changes or already present baseline; no new independent exposure. |
| Danish DynaWord `adl` | Replacement candidate; D raw | Repaired extraction/edition dates; avoid counting repaired and old copies twice. |
| `syvai/danish-dynaword-laya` | Candidate; A only for verified typed labels, otherwise C | Typed extraction/decisions are promising; verify window-local evidence, train/test isolation and synthetic-label validity. `ctx1024` and longer default overlap; confidence is not gold. |
| `syvai/danish-dynaword-extractions` | Deferred; D | Undocumented semantics at scanned revision; overlap with Laya unresolved. |

## Eval-Only and Gaps

Protect the [DFM14/15 evaluation inventory](../dfm14-evaluation-inventory.md),
including the DaLA paired heldouts in `config/dfm14_dala_eval_registry.json`
and `config/dfm14_dala_heldout.json`. Eval structure may be A/B but does not
authorize train use. FLORES/evaluation text is not translation backfill.

Remaining gaps: row-level decision-label counts, reliable hard-negative yield,
source-level upstream attribution inside composite exports, full inherited
exact/near-duplicate matching, local full-mixture receipt availability, native
label calibration, and balance across sparse language pairs. No new row audit
was performed. Broad conversion-volume estimates would therefore be speculative.
All component coverage is an inventory accounting claim, not semantic validation.

Historical DFM1-13 membership and exclusions belong to the all-source accounting
linked from the [overview](../decision-datasets.md); they are not inferred from
the 277 latest component names.
