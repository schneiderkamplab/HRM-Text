---
type: Knowledge Collection
title: DFM1-15 Sources for Decision Modelling
description: Source inventory and conversion assessment for bounded-choice, verification and routing supervision derived from the DFM corpus lineage.
tags: [datasets, decision-modelling, classification, dfm, jev]
status: draft
last_updated: 2026-10-21
confidence: medium
sources:
  - id: typesafe-introduction
    resource: https://docs.typesafe.ai/introduction
    title: TypeSafe introduction
  - id: typesafe-choice
    resource: https://docs.typesafe.ai/primitives/choice
    title: TypeSafe Choice primitive
---
# DFM1-15 Sources for Decision Modelling

This is a **conversion assessment, not an implemented dataset or a change to
DFM training**. The source inventories are inspected locally; conversion
quality and usable row yields remain proposals until row-level validation.
Read the source tables together with their evidence and coverage limits, not
as a claim that every row in a named repository is convertible.

For measured cluster volumes and benchmark-specific priorities, see
[Typed Decisions / Decision Index assessment](decision-datasets/benchmark-priorities.md).

## Meaning of Decision Modelling

Here this means the Jev-like task interface, not business-process decision
diagrams: supplied context plus a bounded question, producing a choice,
truth judgment or rubric score. TypeSafe documents Choice, Score and Noul
primitives. This inventory proposes supervision for such tasks; it does not
claim to reproduce Jev's architecture, training method or calibration.
[Official introduction](https://docs.typesafe.ai/introduction),
[Choice specification](https://docs.typesafe.ai/primitives/choice).

Our most useful unit is **state + question + alternatives + trusted target**.
A parser that emits valid option IDs does not ensure semantic correctness.
Likewise, a reference response does not prove that a different response is
wrong. Distinguish provenance-recovery tasks from correctness judgments.

## Read the Inventory

* [Early sources: DFM1-7](decision-datasets/early-datasets.md).
* [Middle sources: DFM8-13](decision-datasets/middle-datasets.md).
* [Latest sources: DFM14-15](decision-datasets/latest-datasets.md).
* [Conversion recipes and safeguards](decision-datasets/conversion-recipes.md).
* [Coverage and evidence limits](decision-datasets/coverage.md).
* [Detailed collection index](decision-datasets/index.md), including the
  machine-readable source coverage ledger.

Membership in any earlier DFM matters, even if the source was later removed
or replaced. It does **not** override licensing, source-filter exclusions or
evaluation holdouts. Dataset repositories, subsets, generated derivatives
and repeated sampling exposures are different units; do not add their counts
as if they were independent source datasets.

## Priority and Effort

| Priority | Sources/tasks | Decision supervision | Why start here? |
|---|---|---|---|
| 1 | DaLA/language acceptability; existing MCQ, NLI, sentiment, intent and other classification subsets | Preserve existing label/options; normalize question and option IDs | Existing finite target; little or no new adjudication |
| 1 | GEC-DaLA and other explicit incorrect/correct pairs | Which sentence is grammatical? Does this edit fix the stated error? | Paired evidence; discard identical and non-error paraphrases |
| 1 | Paragraph reordering from DynaWord, Common Pile and later derivatives | Choose one of six distinct permutations to apply | CPU-only candidate construction with known source order; ambiguity filter still needed |
| 2 | Denoising, span filling, transformation constraints | Choose valid repair/fill; detect a specific violation | Known corruption or executable rule can provide a target |
| 2 | Native tool-call trajectories and verified format/instruction data | Select tool, supplied argument object, next action, or constraint result | Useful operational decisions; preserve state and tool schemas |
| 2 | Verified math/code examples | Select checked answer/program or judge a checked step | Good when a verifier or explicit answer key exists; not all reasoning is easy |
| 3 | Translation, grounded QA, summaries, retrieval/search traces | Candidate relevance, support, translation/summary selection | Need difficult, genuinely false negatives; random alternatives alone are weak |
| 3 | Preference pairs and source audit records | Pairwise preference or defined accept/reject judgment | Useful only with matching context/rubric and original label provenance |
| 4 | Unlabelled chat, creative writing, raw text and broad synthetic instructions | Usually requires newly judged candidates | Not an easy wholesale conversion; retain eligible subrows only |

## Common Assessment Scale

* **A: existing decision target.** Labels/options already provide supervision.
* **B: mechanically derivable.** CPU transformations or executable checks can
  construct targets. This does not remove the need to filter ambiguity.
* **C: candidate only.** New validated alternatives, adjudication or extraction
  is needed. A positive reference alone is insufficient.
* **D: poor fit/deferred.** No cheap trustworthy decision target, or unsuitable
  status such as excluded/held-out-only. Keep the coverage entry nevertheless.

The same repository can contain A, B and C rows. Restrict conversion to a
verified subtask rather than assigning the entire mixture its easiest label.

## Recommended First Build

1. Start with training-only A rows and paired GEC/paragraph B rows. Preserve
   exact source revision, subset, original row and parent-document identity.
2. Add deterministic constraint checks, tool-schema choices and verified
   math/code. Keep each decision atomic and operationally meaningful.
3. Add retrieval, translation and summarization only after validating the
   candidate construction. Do not label a plausible alternative false simply
   because it differs from the stored reference.
4. Keep audit-derived labels in a separate provenance tier. An old accept
   decision for general training quality is not a grammaticality, truth or
   safety label. Rejected technical failures are not semantic negatives.
5. Measure unique parent rows and valid decisions by task, language and
   provenance. Existing DFM token repetitions are not decision-row counts.
6. Evaluate accuracy and calibration on held-out parent documents, including
   reordered options, hard negatives, ties and insufficient-evidence cases.
   Training with one-hot labels does not establish calibrated confidence.

This documentation task performs no generation, GPU auditing, tokenization,
uploading or sampling and does not change the production dataset mix.
