---
type: Design
title: Decision Dataset Conversion Recipes
description: Concrete bounded-decision conversions, trustworthy targets and leakage controls for the DFM lineage.
tags: [datasets, decision-modelling, transformations, quality]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Decision Dataset Conversion Recipes

Parent: [DFM1-15 decision assessment](../decision-datasets.md).
These are proposed recipes, not new labels applied to production data.

## Labelled Tasks (A)

Preserve the original prompt, passage, options and answer key. Remove answer
keys, solution explanations and assistant rationales from the **input**.
Normalize choice IDs without changing option text. For classification, supply
label descriptions, not opaque dataset-specific integer meanings.

MCQ includes commonsense, science, school questions, reading comprehension,
math and domain-specific exams wherever present in training sources. NLI
uses entailment/contradiction/neutral; do not collapse neutral into false.
Acceptability uses the source's linguistic judgment rather than factual truth.
Multi-label tasks remain multi-label or become separate binary decisions.
Numeric/ordinal labels need their original rubric and units.

Resolve option-order randomization against the answer map. Repeated/identical
options and multiple valid answers require a gold set, not forced single gold.
Do not assume the last letter in a reasoning response is the answer key.

## Correct Versus Incorrect Sentences (A/B)

For a labelled GEC pair `(incorrect, corrected)`, use both as alternatives
with random position and ask for grammaticality, or show the source plus a
candidate edit and ask whether the specific error was corrected. Only use
rows whose input actually contains an error. Identical pairs, optional style
edits, dialect choices and semantically different rewrites are not reliable
binary grammaticality contrasts. Preserve named entities and intended meaning.

Illustration, not an extracted corpus row:

```json
{"state":{},"question":"Which sentence is grammatical in standard Danish?","options":[{"id":"a","text":"Hun har læst bogen."},{"id":"b","text":"Hun har læse bogen."}],"gold_ids":["a"],"target_kind":"grammaticality"}
```

For existing DaLA labels, single-sentence acceptability is even simpler and
does not need a competing sentence. Do not derive factual truth from fluency.

## Paragraph Permutations (B)

Given original paragraphs `P` and their presented shuffle `S`, calculate the
**inverse mapping** that recovers P from S. Offer this index vector alongside
five distinct non-identity distractor vectors. The identity vector is allowed
as a candidate where appropriate; it must not be systematically the gold.
Use one-based indices consistently and define that a vector is the order in
which to read the *presented* paragraphs, not a mapping into the original.

For example, original `A,B,C`, presented `C,A,B`, the correct application is
`[2,3,1]`. With three paragraphs all six permutations exist. With fewer than
three, six unique candidates are impossible: lower the arity or drop the row.
For longer documents sample five distinct alternatives; do not enumerate n!.
Include adjacent swaps and local coherence violations, not just random order.

Check the chosen vector reconstructs the original byte-normalized sequence
and that all alternatives are bijections with distinct resulting text.
Exclude duplicate paragraphs, arbitrary list-like order and ambiguous
discourse unless the task is explicitly **source-order recovery** rather than
the stronger claim that only one sequence is coherent. The source order is
known; uniqueness of natural-language coherence is not guaranteed.

## Denoising, Span Filling and Prefix Continuation (B/C)

| Transformation | Decision | Target evidence | Main trap |
|---|---|---|---|
| Denoising/error correction | Choose reconstruction; does the candidate repair a specific corruption? | Original text plus corruption trace | A corruption may still be grammatical or semantically acceptable |
| Span filling | Choose one candidate span for a numbered blank, or a consistent bundle of fills | Original masked span and surrounding context | Several words may fit; reference match alone does not prove others wrong |
| Prefix continuation | Choose the actual continuation; judge continuation support/compatibility | Original same-document continuation | A different continuation is often equally valid; source recovery differs from quality |
| Sentence/paragraph transformation | Which output meets tense, length, format or meaning constraint? | Paired instruction/output and executable constraint where possible | Surface compliance is not semantic faithfulness |

For masked documents, never include the complete answer reconstruction in the
state. Use same-language, length-matched candidates and local hard negatives.
When reconstructing corruption traces is impossible, record this limitation;
do not pretend arbitrary string differences encode known errors.

## Tool Use and Agentic Trajectories (A/B/C)

At each assistant decision use only preceding messages, actual tool schemas
and available state. The future tool result and final answer must be hidden.
Options can be tool names plus `respond`/`ask_clarification`/`no_tool`, or
complete candidate calls with JSON arguments. Multiple simultaneous calls
need a set-of-calls candidate or independently labelled component decisions.

Schema validity and semantic correctness are different tasks. Changing a
required key gives a mechanically invalid call; choosing an incorrect city
usually requires a semantic check. A demonstrated tool is not necessarily
the only suitable tool. Tool **necessity** and refusal require explicit labels
or fresh validation, not an assumption that absence of a call means no tool
was needed. Keep Gemma-native markers as serialization, not answer shortcuts.

Search traces can yield evidence relevance and answer support after retrieval.
Provide actual snippets and timestamps. Do not infer support from citation
presence or invent failed actions from successful-only trajectories.

## Math, Code and Reasoning (A/B/C)

Existing MCQ is A. Free-response numeric/symbolic questions can become B when
answer equivalence is executable and alternatives are verified distinct.
Preserve units, domains, rounding and multi-answer semantics. A changed
number is not invariably a wrong answer. Long theorem proofs without a
checker remain C, regardless of whether their generator was accepted.

For code, use original tests where available and sandbox candidate execution.
A program passing visible tests is not proved universally correct. Mutants
must fail a relevant test; alternative implementations that pass are not
negatives. If using failed tests as labels, decide whether test results are
input evidence (triage task) or hidden verifier evidence (code reasoning task).

Do not turn a correct full solution into a reference answer leaked alongside
the question. Step validity needs a checked erroneous step, not a random cut
of an otherwise valid chain. Hard multi-step math can be represented as a
decision but may not fit the intended fast, atomic-decision workload.

## Grounded QA, Summary, Translation and Chat (Mostly C)

* QA: choose a supported answer or evidence span among alternatives. Retain
  the passage; distinguish unsupported from contradicted and unanswerable.
* Summary: choose a source-supported summary, find a fabricated detail or
  check a requested length. Source document and validated controlled edits
  are needed; ROUGE similarity is not a correctness label.
* Translation: choose a faithful translation or detect a specific omission,
  number/entity error or negation change. Equivalent translations remain
  valid. Random cross-document negatives mostly teach topic matching.
* Multi-turn chat: instruction retention, reference resolution, requested
  next action or constraint satisfaction can be useful. General response
  quality, helpfulness or tone requires explicit preferences/rubrics.
* Creative writing: verifiable formatting/constraint decisions are possible;
  which story is better is not derivable from a single accepted story.
* Raw corpora: language/topic labels and document provenance may be available,
  but factual QA or quality labels require extra work. Metadata classification
  alone is not substantive reasoning supervision.

## Preference and Audit Evidence

Retain chosen/rejected pairs only if they concern the same input and the
preference objective is known. A pairwise preference is not absolute
correctness; score differences are meaningful only with the original scale.
General quality-audit accept/reject can supervise that **same** rubric.
Timeouts, invalid JSON, truncation, duplicates and retry failures must not
be relabelled semantic rejection. Accepted-only releases contain no observed
negative labels; rejected rows may also be unsuitable to redistribute.

This is a proposal for reusing stored evidence, not a request to run new judges.

## Canonical Records and Validation

Store `source_repo`, immutable revision, subset, split, source row ID,
parent-document/group ID, DFM memberships, language, task family, question,
state, option IDs/text, gold ID set or original rubric label, derivation,
seed, original target and verifier evidence. Keep provenance out of the model
input if it reveals labels. A semantic target must be distinguishable from a
source-provenance target and from a machine-schema-validity target.

Split **before** generating variants, by document/conversation/problem and
underlying source, including translations, repairs, resyntheses and repeated
DFM exposures. Keep existing eval registries disjoint, especially DaLA,
GEC, math/code benchmarks and overlapping instruction mixtures. A dataset
historically used for training is not automatically a clean evaluation set.

Validate label coverage, bijections, equivalence, language, evidence presence,
input-length limits, zero answer leakage and option-order balance. Report
unique parent counts separately from generated decisions and sampled repeats.
Evaluate more than accuracy: per-task confusion, option-swap invariance,
abstention coverage, Brier/log loss and calibration on a held-out set. Do not
write a made-up confidence target of 1.0 for every accepted row.

Use varied option counts and orderings, neutral IDs and explicit descriptions;
include tests with renamed labels so the model cannot solve the task by a
familiar label token alone. Separate genuinely unanswerable cases from ordinary
model uncertainty. Only add `none`/`insufficient_evidence` targets where the
example establishes that outcome; arbitrary removal of gold does not prove
that all surviving candidates are false. Keep meaningful semantic contrasts
alongside easy syntax checks, or the model may learn formatting rather than
the intended judgment.
