---
type: Research
title: Joint European Language Expansion Priorities
description: Combined broad-corpus and DaLA correction-readiness recommendations for additional European languages.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [multilingual, datasets, prioritization, dala]
---
# Joint European Language Expansion Priorities

## Inputs and Scope

Compared on 2026-09-26:

- [HRM five-axis ranking](european-language-expansion-ranking.md) and its
  [HF source inventory](european-language-expansion-sources.md): reach, text
  quality/availability, instruction quality/availability, covering 28 languages.
- DaLA research snapshot at
  `/work/mimir/DaLA/wiki/pages/european-language-ranking.md`, generated
  2026-09-26: 23 languages ranked by observed grammar/spelling evidence,
  safe corruption opportunities, tooling, access and integration effort.
  Its underlying provenance is in
  `/work/mimir/DaLA/wiki/artifacts/european-language-ranking/survey-2026-09-26.json`.

Both exclude the nine already-covered languages. These are complementary
research judgments, not measured model outcomes. This page adds a joint
recommendation; it does not supersede either task-specific ranking or authorize
downloads, training, generation, or changes to the running pilot.

## Mandatory Eligibility Policy

User decision, 2026-09-26: **both surveys act as exclusion gates** for new
language extensions. A high combined score or large speaker reach cannot
compensate for either missing requirement.

1. **DaLA feasibility:** establish a practical route to reliable acceptability
   and grammatical-error-correction data, with usable evidence/resources,
   defensible transformations and independent validation. A checker or a large
   synthetic corpus alone does not establish this.
2. **Broad training-data sufficiency:** establish enough accessible,
   high-quality text **and** instruction data for the intended language/variant
   and training allocation. Raw crawl totals, repetition and promised future
   generation do not substitute for usable supply.

Record each gate separately as passed, unresolved or failed, with supporting
evidence. Extend only when **both pass**. Unresolved evidence means defer, not
an assumption of feasibility; a failed gate excludes the language from the
current expansion. Reconsideration is possible when new evidence/resources
resolve the gap. No numeric row/token threshold was approved in this decision;
document actual screened supply and task/domain coverage against the proposed
training budget rather than inventing a score cutoff.

**Superseded interpretation (2026-09-26):** the weighted ranking and wave labels
below are not admission recommendations on their own. They are research
priorities; the score orders eligible candidates only after both gates pass.
Neither existing survey constitutes a completed two-gate audit. In particular,
DaLA tier A is not automatic approval, tier C is not proof of impossibility,
and languages absent from its survey remain deferred until assessed. Nordic
or other strategic preferences may reorder eligible candidates, not waive gates.

## Combination Method

**Snapshot warning (2026-09-26):** the table and 23-rank normalization below
describe the initial DaLA snapshot. Its updated survey now separates pt-PT
(11/B) and pt-BR (12/B), yielding 24 entries, and reports French as tier A.
See the [Portuguese follow-up](portuguese-expansion-reassessment.md#updated-dala-assessment-2026-09-26).
Do not interpret these historical joint scores as recalculated variant scores;
the mandatory two-gate policy remains controlling.

Use 70% broad-training priority and 30% DaLA readiness:

```text
DaLA rank percentile = 100 * (23 - rank) / 22
joint priority = 0.70 * HRM score + 0.30 * DaLA rank percentile
```

The 70/30 split is a proposed planning preference: broad language capability
remains the main objective, with explicit weight for constructing dependable
acceptability/correction supervision. DaLA supplied ordinal ranks, not scores;
the percentile is only an aggregation device. Zero for its final rank means
last within this shortlist, not zero utility. Equal spacing between ranks is an
assumption, not an empirical finding. Differences of a few points should not
determine funding or inclusion. Italian and Czech are effectively tied.

The five original HRM scoring columns remain documented on the linked ranking
page; DaLA evidence is not silently folded into those scores.

## Ranked Suggestions

| Rank | Language | HRM /100 | DaLA rank /23 | Joint /100 | Main reason or caveat |
|---|---|---:|---:|---:|---|
| 1 | German | 86.5 | 1 | 90.5 | Best joint starting point: German Commons plus DOLCI/EU-Instruct, and Falko-MERLIN with morphological tooling. |
| 2 | Spanish | 92.0 | 5 | 88.9 | Highest broad-data score; ALIA and large multilingual SFT supply, with COWS-L2H correction evidence. |
| 3 | French | 90.5 | 7 | 85.2 | Strong broad instruction supply; correction-rule tooling is better established than unrestricted correction-corpus access. |
| 4 | Italian | 78.0 | 4 | 80.5 | Broad translated SFT plus MERLIN/CItA native and learner error evidence. |
| 5 | Czech | 74.0 | 2 | 80.4 | Exceptionally strong GECCC evidence; DOLCI/EU-Instruct and Czech instruction collection make a balanced package. |
| 6 | Ukrainian | 71.5 | 3 | 77.3 | UA-GEC provides explicitly separable GEC supervision; substantial translated instruction supply. |
| 7 | Portuguese | 83.5 | 11 | 74.8 | Strong broad SFT, but mainly Brazilian; DaLA specifically evaluates European Portuguese. Separate variants. |
| 8 | Russian | 78.5 | 9 | 74.0 | Strong reach and text supply; instruction provenance and RULEC-GEC access need resolution. |
| 9 | Turkish | 70.0 | 8 | 69.5 | GECTurk offers an actionable rule pipeline; text/SFT filtering and source terms still matter. |
| 10 | Catalan | 69.0 | 12 | 63.3 | ALIA plus Softcatala tooling; independently observed correction evidence needs strengthening. |
| 11 | Estonian | 55.5 | 6 | 62.0 | Largest positive DaLA adjustment: EstNLTK and learner evidence complement Magpie and instructionSum. |
| 12 | Greek | 69.5 | 14 | 60.9 | DOLCI/EU-Instruct and correction resources; confirm corpus access and grammar coverage. |
| 13 | Romanian | 69.0 | 15 | 59.2 | Substantial translated SFT; RoGEC evidence requires scope and access checks. |
| 14 | Finnish | 70.5 | 17 | 57.5 | Strong general instruction opportunity; weaker verified ready-to-use correction evidence, not weak Finnish language data. |
| 15 | Basque | 57.5 | 16 | 49.8 | ALIA and morphology/GEC resources; distinguish synthetic scale from human-validated coverage. |
| 16 | Latvian | 49.5 | 13 | 48.3 | LaVA and morphology strengthen a comparatively thin broad instruction offering. |
| 17 | Slovenian | 43.5 | 10 | 48.2 | Solar and Sloleks make correction feasible, but broad modern instruction supply remains limited. |
| 18 | Hungarian | 58.5 | 21 | 43.7 | Text exists; stronger native instruction and safe correction resources still needed. |
| 19 | Slovak | 51.5 | 18 | 42.9 | Small SFT collection and learner resources; correction filtering/access remain work. |
| 20 | Bulgarian | 53.5 | 20 | 41.5 | Narrow synthetic grammar coverage and limited verified broad SFT. |
| 21 | Lithuanian | 50.0 | 19 | 40.5 | Wikipedia-derived QA and generator code; broader corrected evidence needed. |
| 22 | Irish | 38.0 | 22 | 28.0 | Checker and small human instruction leads; accessible clean text/correction evidence needs work. |
| 23 | Welsh | 38.5 | 23 | 26.9 | Checker/corpus leads do not imply downloadable correction training data. |

## Practical Sequence (Subject to Both Gates)

1. **First joint wave: German, Spanish, French, Italian, Czech, Ukrainian.**
   This combines large general-purpose supply with viable correction work.
   Pilot German first; Czech/Ukrainian offer particularly useful correction
   evidence, while Spanish/French supply broad coverage.
2. **Next broad expansion: Portuguese, Russian, Turkish, Catalan.**
   Resolve variant policy and corpus-specific access/provenance before scale-up.
3. **Targeted European coverage: Estonian, Greek, Romanian, Finnish.**
   For a Nordic/Baltic strategic objective, move Finnish and Estonian earlier
   explicitly; do not claim this changes their measured data quality.
4. **Later targeted packs:** the remaining ranked languages. They can be
   valuable without immediately supporting a full general-purpose expansion.

The first six remain the same set when broad-training weight is varied from
60% to 80%, although their internal order changes. This is more useful than
overinterpreting single-point differences.

## Important Disagreements

**Portuguese update, 2026-09-26:** the initial supply assessment missed
AMALIA's substantial pt-PT resources. See the [variant reassessment](portuguese-expansion-reassessment.md).
The historical score is retained, but pt-PT now merits near-term verification;
the remaining DaLA validation requirement is not waived.

- German rises from HRM rank 3 to joint rank 1 through its DaLA readiness.
- Czech and Ukrainian rise from 7/8 to 5/6, respectively.
- Estonian rises from 17 to 11. This does not establish a large clean-text
  yield: DaLA did not screen or size new clean corpora.
- Finnish falls from 9 to 14 because DaLA found less ready-to-use minimal
  correction evidence. Its general SFT case remains strong.
- Slovenian rises from 25 to 17 on correction infrastructure, without resolving
  its thin broad instruction supply.
- Portuguese is not an exact match: HRM scores the language globally, largely
  using Brazilian sources; DaLA ranks European Portuguese specifically.
  Treat the joint result as provisional until pt-PT and pt-BR are separated.

## Languages Missing from DaLA's Survey

Do not assign missing languages zero readiness. These retain their HRM scores,
but cannot receive a comparable joint score without an additional DaLA survey:

| Language | HRM rank | HRM /100 | Suggested treatment |
|---|---:|---:|---|
| Galician | 16 | 57.5 | Most promising unpaired candidate: ALIA and Galician GEC leads; investigate alongside Catalan/Basque. |
| Serbian | 19 | 53.0 | Audit script/variant handling and observed correction evidence. |
| Croatian | 20 | 51.5 | Validate synthetic instruction quality and seek correction evidence. |
| Albanian | 24 | 44.0 | Establish wider instruction and correction coverage. |
| Maltese | 28 | 32.0 | Targeted resource investigation before a broad expansion. |

These are not ranked below the 23 combined candidates: their joint placement
is unknown.

## Integration Gates

- Use original licensed correction resources, not indiscriminately redistributed
  MultiGEC bundles. DaLA reports research-only, personal-access/no-redistribution
  terms for the combined distribution; originals can have different terms.
- Preserve correction benchmarks and all existing evaluation splits. Learn
  constrained error patterns from training evidence, not benchmark answers.
- Explicitly name the target language/variant in acceptability and correction
  prompts; do not mark valid dialectal or orthographic alternatives incorrect.
- Independently audit clean text, instruction pairs and generated corruptions.
  Existing self-judging or a checker returning no warning is not sufficient.
- Convert instruction, correction and tool data through the intended Gemma
  template. Raw text availability primarily supports grounded transformations
  and QA; this recommendation does not reverse the continuation-data policy.
