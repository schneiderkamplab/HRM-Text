---
type: Reference
title: Decision Benchmark Priorities and Cluster Volumes
description: Benchmark-informed prioritization of DFM decision-conversion candidates, with source-volume accounting separated from conversion yield.
tags: [decision-datasets, benchmarks, data-selection]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Benchmark Priorities

Parent: [decision dataset overview](../decision-datasets.md).
Counting caveats: [volume basis](volume-method.md).
The priorities below are hypotheses about transfer, not measured improvements.
No training, conversion or evaluation was launched for this assessment.

## Benchmarks Checked

[Typed Decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions)
tests agent traces, customer service, invoices and security incidents. Its
400 test cases contain 2,000 decisions; metrics include accuracy and
probability calibration. Gold probabilities come from a small teacher, not
independent adjudication. Specialist and general-model scores are not directly
comparable. Prefer evidence-conditioned actions and calibrated choices over
generic prose. Never train on its test labels or prediction dumps.

[Decision Index](https://huggingface.co/spaces/multimodalart/jev-decision-index)
is now version 0.4: the full ranking weights private same-skill tests 60% and
private new-domain tests 40%. The 37-task public suite is still required but
has zero weight in that full score. Its public tasks cover reasoning, language,
retrieval/classification, tools and human taste. Therefore public-task overlap
is a useful skill map, not evidence of private leaderboard gains. See the
[official reproduction kit](https://github.com/apolinario/decision-index).

The active public panel, rather than stale catalog membership flags, is in
[index-0.3.json](https://raw.githubusercontent.com/apolinario/decision-index/main/decision_index/data/index-0.3.json).
It includes NLI, intent/OOS classification, tool selection, reasoning/code and
preference tasks. Concrete matches include ContractNLI, ANLI, BANKING77,
CLINC150, BFCL, API-Bank, When2Call, GSM8K, CRUXEval and RAGTruth. The
[task catalog](https://raw.githubusercontent.com/apolinario/decision-index/main/decision_index/data/benchmarks.json)
describes individual decision interfaces; some differ from ordinary generative
benchmarks with the same name. For example, tool-name selection is not full
argument generation or tool execution.

## Selection Implications

Start with recoverable labels and evidence-conditioned choices, then tool/action
selection, executable instruction constraints, verified math and executable code.
These offer both relatively strong supervision and relevant decisions. For
Typed Decisions specifically, action selection and evidence interpretation rank
above mathematical problem solving; Decision Index gives math/code a stronger
case. Mixed reasoning must not be silently relabeled as verified mathematics.

DaLA acceptability, GEC, paragraph reordering and corruption recovery are useful
auxiliary decision tasks but less direct workflow matches. Corrected sentences
can have multiple valid alternatives. Original paragraph order is a provenance
label, not proof that every other permutation is incoherent. Require explicit
ambiguity controls before deriving negatives.

Preference data is valuable only where both candidates and a justified label
survive conversion. A preferred-only chat export is not a preference pair.
QA, summaries and translations need independently checked distractors or support
labels: a different answer from the reference is not automatically wrong.

The largest gaps are workflow-specific evidence/next-action supervision,
out-of-scope/abstention calibration, and human-taste tasks. Large volumes of
multilingual transformations do not remove these gaps. Prioritize English
subsets for direct transfer to these English benchmark interfaces, while
retaining multilingual counterparts for multilingual decision capability.

## Volume Evidence

The companion measurement uses a dated, verified DFM15 source-range census,
not a sum of DFM versions. Source storage includes inactive and superseded
representations; epoch exposure includes repeats. Neither is distinct content
or the output size of a converted decision dataset. Cluster assignment is
source-name/narrative triage, not row-level semantic verification.

Measurement: `scripts/measure_decision_cluster_volumes.py`.
Machine-readable outputs: `docs/reports/decision_dataset_volumes_20261021.json`
and `.tsv`. The latter includes exact source assignments for inspection.

### Measured Cluster Table

Counts below use the October 20 published epoch-zero receipt. Rows are millions
of sampled occurrences; epoch tokens are billions including repeats. Stored
tokens are billions of physical source variants, including inactive ranges.
Neither column is a deduplicated historical union. Missing source row counts
are explicitly null in the machine report, not estimated from token lengths.

Rank is a joint prioritization; TD/DI indicate inferred relevance to Typed
Decisions / Decision Index's public skill map. H/M/L mean high/medium/low.

| Rank | Cluster | Epoch rows M | Epoch tokens B | Stored tokens B | TD/DI | Decision task to extract |
|---|---|---:|---:|---:|---|---|
| 1 | Classification, NLI, MCQ families | 3.771 | 1.081 | 3.509 | H/H | Intent, entailment, supported option; recover original labels |
| 2 | Tools and agent actions | 14.984 | 18.802 | 58.295 | H/H | Choose tool, next action, or whether a call is needed |
| 3 | Instruction constraints | 1.458 | 1.636 | 1.758 | H/H | Decide which response satisfies an explicit contract |
| 4 | Math and formal reasoning | 62.218 | 6.392 | 19.124 | M/H | Choose verified result or valid reasoning step |
| 5 | Code | 1.141 | 1.183 | 3.568 | M/H | Choose output, repair or implementation using tests |
| 6 | Mixed reasoning | 6.135 | 4.539 | 7.995 | M/H | Recover domain-specific choices; correctness not established |
| 7 | QA and grounded evidence | 31.713 | 12.467 | 11.458 | H/H | Supported answer, relevant evidence or contradiction |
| 8 | Preference-origin data | 0.190 | 0.163 | 0.163 | M/H | Choose preferable response, only if both alternatives survive |
| 9 | Language acceptability | 57.990 | 4.123 | 4.127 | L/M | Acceptable versus unacceptable sentence |
| 10 | Grammatical correction | 55.062 | 6.633 | 6.633 | L/M | Choose correct sentence or applicable repair |
| 11 | Paragraph reordering | 1.117 | 1.110 | 0.879 | M/M | Choose source permutation from bounded alternatives |
| 12 | Denoising and span filling | 7.137 | 9.028 | 16.512 | L/M | Recover missing span or discriminate a corruption |
| 13 | Summaries and rewriting | 2.631 | 2.466 | 9.082 | M/M | Supported, faithful or constraint-compliant summary |
| 14 | Translation | 68.257 | 5.927 | 16.081 | L/L | Translation adequacy or alignment; validate negatives |
| 15 | Mixed chat/instruction | 82.741 | 52.655 | 97.707 | ?/? | Requires row-level routing; no uniform decision target |
| 16 | Raw, continuation, unknown | 11.869 | 6.311 | 7.244 | L/L | No bounded target identified |
| | **Total** | **408.413** | **134.517** | **264.135** | | |

The existing-label/mechanical-target candidate clusters (1, 9-12) account for
125,077,268 sampled row occurrences and 21.974996604B epoch tokens; their stored
variants occupy 31.659224969B tokens. This is a screening pool, not certified
usable volume. In particular, MCQ-named sources can include explanation and
question-generation variants.

Including the conditional candidates in ranks 2-8 and 13-14 gives
313,802,775 occurrences / 75.550800736B epoch tokens, backed by 159.183686038B
stored tokens. Mixed and unresolved clusters add 58.965829998B epoch tokens;
they must not be advertised as readily convertible decision data.

An additional historical transformation shortlist represents 43.324M rows /
52.813B serialized tokens. It is **not added** to these totals because document
and successor overlap is unresolved; see [historical reconciliation](volume-method.md).
The full DFM1-15 unique-content union and post-conversion token count remain
unknown. Converting long rationales into option labels can substantially reduce
tokens, while constructing alternative candidates can increase prompt length.
