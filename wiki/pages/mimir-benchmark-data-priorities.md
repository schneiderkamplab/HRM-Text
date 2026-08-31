---
type: Plan
title: Mimir Benchmark Data Priorities
description: Marginal curation and generation priorities for answer contracts, WinoGrande, HellaSwag, IFEval, BoolQ, and DROP after the expanded grounded SFT integration, with MMLU and ARC-C capability augmentation deferred.
tags: [mimir, dfm10, data-generation, evaluation, instruction-following, commonsense]
status: draft
last_updated: 2026-08-30
confidence: medium
sources:
  - id: ifeval-paper
    resource: https://arxiv.org/abs/2311.07911
    title: Instruction-Following Evaluation for Large Language Models
  - id: drop-paper
    resource: https://arxiv.org/abs/1903.00161
    title: DROP - A Reading Comprehension Benchmark Requiring Discrete Reasoning Over Paragraphs
  - id: hellaswag-paper
    resource: https://arxiv.org/abs/1905.07830
    title: HellaSwag - Can a Machine Really Finish Your Sentence?
  - id: winogrande-paper
    resource: https://arxiv.org/abs/1907.10641
    title: WinoGrande - An Adversarial Winograd Schema Challenge at Scale
  - id: boolq-paper
    resource: https://arxiv.org/abs/1905.10044
    title: BoolQ - Exploring the Surprising Difficulty of Natural Yes/No Questions
  - id: arc-paper
    resource: https://arxiv.org/abs/1803.05457
    title: Think you have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge
---
# Mimir Benchmark Data Priorities

## Decision frame

This is a **marginal** plan after integrating
`dfm10-mimir-grounded-expanded-sft`: 732,763 accepted rows already contribute
223,728 Technical/STEM, 127,944 professional-domain, 125,036 compositional,
128,687 factual-QA, and 127,368 MCQ-contract examples. DFM10 also already
contains verified instruction-following sources. Re-evaluate an early DFM10
checkpoint before launching every slice below; do not assume that Mimir v1's
pre-DFM10 gaps survive unchanged.

Mimir v1's relevant baselines are MMLU 0.585, ARC-C 0.799, WinoGrande 0.732,
HellaSwag 0.673, BoolQ 0.878, DROP 0.835 F1, and English IFEval 74.35%. The
largest credible MMLU gaps are technical science, formal/mathematical reasoning,
professional medicine/law/accounting, and compositional reasoning. Historical
MCQ invalids must be separated from capability errors by the corrected scorer.

## Prioritized marginal program

| Priority | Accepted rows | Primary benchmarks | Data to curate or generate | Required quality gate |
|---:|---:|---|---|---|
| 1 | 200k--300k | IFEval | Verifier-backed instruction tasks spanning one to five interacting constraints: exact sections, counts, required/forbidden terms, ordering, transformations, JSON/XML schemas, audience/style, and multi-turn corrections. Content should vary independently from constraint templates. | Every target must pass deterministic per-constraint checks. Keep failed generations as negatives only for preference training, never SFT targets. |
| 2 | 100k--200k | All exact-match and classification evaluations | A dedicated answer-contract calibration corpus covering the contracts actually observed in the production evaluators and current training sources. It must vary prompt wording, cue placement, label vocabulary, capitalization, number of options, and whether reasoning is allowed before a required final line. See the inventory below. | Deterministically render the requested target, validate byte-level or normalized-exact compliance according to the stated contract, balance labels, and keep task content novel and independent of benchmark examples. |
| 3 | 300k--450k | HellaSwag, WinoGrande | Two linked slices: event/procedure continuation from permissively licensed narratives, dialogues, manuals, and public-domain transcripts; and paired coreference examples with controlled antecedent swaps, role reversals, gender/name balancing, and causal plausibility. Generate hard but clearly wrong continuations rather than random negatives. | Programmatic pair invariance checks, independent plausibility judgment, lexical-artifact classifier, and answer-position balance. |
| 4 | 200k--300k | DROP | Passage-grounded discrete reasoning over public reports, statistics, tables, timelines, and factual prose. Cover addition, subtraction, count, sort, min/max, date intervals, multi-span extraction, comparison, and two-to-four-operation composition. | Generate the answer from an executable symbolic program, verify every operand against the passage, and require exact agreement between program result and assistant target. |
| 5 | 100k--200k | BoolQ | Balanced passage-entailment questions over the same licensed source pool. Include explicit support, contradiction, negation, quantifiers, temporal scope, coreference, and multi-sentence inference. Construct difficult `no` cases by controlled evidence edits rather than unsupported teacher invention. | Exactly balanced labels by source/domain; evidence-span annotation; deterministic contradiction checks where possible; reject questions answerable from lexical shortcuts alone. |

## Answer-contract inventory and corpus design

The existing 127,368-row Mimir MCQ slice covers only one contract: the English
instruction `Answer with exactly one option letter.` with a bare uppercase
`A`--`D` target. That is useful but insufficient for the production stack.
Inspection on 2026-08-30 found these distinct contracts:

| Contract family | Observed production or training wording | Required calibration targets |
|---|---|---|
| Legacy standard MCQ | MMLU, ARC-C, HellaSwag, WinoGrande, and BoolQ list choices as `A. ...` and end the prompt with `Answer:`; few-shot demonstrations contain `Answer: A`. Generation is limited to one token. | Bare uppercase letters with 2--10 valid options. Include prompts ending in `Answer:` and explicit variants such as “answer only with the letter.” |
| Inspect-AI MCQ | DFM `mc9` and FlexOLMo tasks say the entire response must be `ANSWER: $LETTER`; the CoT variant permits reasoning but requires that exact final line. | Exact `ANSWER: A`; reasoning followed by a final `ANSWER: A`; and multi-answer `ANSWER: A,C` only for tasks that explicitly permit multiple answers. |
| Danish prefixed MCQ | Kaenguruen asks for `Svar: <bogstav>` and its training target is `Svar: A`. | Exact `Svar: A` with uppercase letters and varied natural Danish wording. |
| Danish bare-letter MCQ | DFM PIQA says `Svar kun med A eller B.`; DFM7 MCQ says `Svar kun med bogstavet`; Danish citizen tests request lowercase `a, b, ...` and nothing else. | Bare uppercase `A`/`B` and `A`--`D`, plus bare lowercase `a`--`d` when the prompt requests lowercase. Never silently normalize the target style during construction. |
| Binary verbal labels | BoolQ choices are `Yes`/`No`; DaLA requests `ja` or `nej`; EuroEval linguistic acceptability uses localized yes/no labels. | Bare `Yes`, `No`, `ja`, and `nej`, with capitalization exactly matching the request. Include both choice-list and direct yes/no formulations. |
| Semantic class labels | EuroEval classification, sentiment, and NLI request only one localized label, including Danish `positiv/neutral/negativ` and `sand/neutral/falsk`. | Exact requested label drawn from the labels supplied in the prompt. Vary natural wording and label inventories without changing their semantics. |
| Short extractive answer | Standard DROP uses few-shot `Q: ...\nA:` and accepts a concise span, number, date, or list; DFM MultiWikiQA and EuroEval reading comprehension impose maximum word counts. | Bare span/number/date/list targets and explicit one-, three-, or N-word limits. No introduction, quotation wrapper, or repeated cue unless requested. |
| Mathematical final answer | Current GSM8K scoring accepts a bare integer or boxed answer; MATH expects a final `\\boxed{...}` where possible. Training includes RLVR boxed targets and ScienceQA rationale followed by `Answer: A`. | Bare numeric answer, exact `Answer: <value>`, exact `\\boxed{...}`, and reasoning followed by one required final-answer line. Each row declares whether reasoning is forbidden, optional, or required. |
| Exact payload | DFM and EuroEval tasks include translation-only, SQL-only, corrected-sentence-only, JSON dictionaries, and native tool-call structures. | Exact payload with no prose or markdown wrapper: translation, SQL, corrected text, valid schema-conforming JSON, and native tool calls. These overlap IFEval but belong here when the contract is the scoring boundary. |

Construct content first, then independently sample a compatible contract and
prompt realization. Do not let subject matter predict output syntax. Keep
direct-answer and reason-then-final examples as separate rows, and include
English and Danish realizations where the production stack uses both. A
reasonable 150k-row center point is 45% selection labels, 20% verbal/semantic
labels, 15% short spans and numeric finals, 10% reason-then-final, and 10%
structured exact payloads. This slice calibrates compliance; it must not be
reported as evidence of improved benchmark knowledge.

## Deferred MMLU and ARC-C capability work

Do not curate or generate MMLU- or ARC-C-targeted capability data yet. The
expanded Mimir corpus already adds large Technical/STEM, professional-domain,
compositional, factual-QA, and MCQ slices. First evaluate an early DFM10
checkpoint, inspect corrected per-subject MMLU results and ARC-C error classes,
and distinguish knowledge gaps from reasoning and answer-contract failures.
Only then define narrowly grounded additions for persistent holes. The generic
answer-contract corpus above may include novel educational content, but it must
not be selected or weighted using MMLU/ARC questions or subject-level misses.

## Source strategy

Prefer immutable, attributable sources already present in the project: official
OpenStax artifacts, the Open Logic Project, government science/health/legal
materials, public statistical reports, Folketing and Danmarks Statistik where
Danish variants are useful, and provenance-preserving Common-Pile passages
whose row-level terms permit the intended use. Add new open textbook or manual
collections only after per-artifact licence checks.

For event and coreference data, do not use HellaSwag or WinoGrande items as
seeds. Use unrelated permissive/public-domain narratives and procedures.
BoolQ and DROP evaluation items should likewise not become source templates.
MMLU/ARC-C capability curation is deferred as described above.

## Contamination and evaluation firewall

1. Freeze untouched shadow evaluations before generation.
2. Use benchmark-level failure aggregates and broad ontologies, never failed
   question text, choices, or answers as generation inputs.
3. Apply only the existing reproducible normalized-exact decontamination check.
   Do not add lexical-overlap, fuzzy, embedding, or semantic-neighbor filters.
4. Do not hold out source documents, prompt templates, constraint combinations,
   or reasoning-program families from the completed training corpus. Validation
   may inspect stratified samples, but every accepted unique row remains
   eligible for training.
5. Run ablations by slice. Do not commit the full program before an early DFM10
   checkpoint identifies which gaps remain.

## Recommended execution order

Start with IFEval and the answer-contract corpus because both are cheap to
verify and directly address instruction reliability and scoring-boundary
failures. Run event/coreference and DROP generation next; both fill capabilities
not explicitly targeted by the expanded Mimir corpus. BoolQ is already strong
and should receive a smaller, inference-focused slice rather than broad factual
QA scaling. Keep MMLU/ARC-C capability work paused until corrected post-DFM10
diagnostics identify persistent, specific holes.

## Implementation status, 2026-08-30

The deterministic answer-contract corpus is complete at
`data/mimir_answer_contract_calibration/final/mimir_answer_contract_calibration.jsonl`.
It contains 150,000 unique rows derived from 150,000 distinct accepted
grounded-Mimir sources, with no held-out rows: 67,368 selection-label, 30,000
binary/semantic, 22,632 short-answer, 15,000 reason-then-final, and 15,000
structured-payload examples. Exact structural validation passes. Its 1,600-row
family-stratified E4B audit found 1,596 usable rows (99.75%) and zero judge
errors, satisfying the predeclared 99% gate. The corpus is tokenized, integrated
at repeat one, and published as
`schneiderkamplab/dfm10-mimir-answer-contract-calibration` at remote revision
`4ed7c561de4f3ca5cf4b87401f4f720c24c81007`.

The IFEval, BoolQ, DROP, and event/coreference programs are implemented and
running through a common atomic 1,024-shard queue. Their deterministic request
manifest has 990,000 candidates: 260,000 IFEval, 150,000 BoolQ, 320,000 DROP,
and 260,000 event/coreference requests. Paired coreference requests may yield
two accepted rows. The initial generation prompt was **superseded on
2026-08-30** after a first-shard inspection found that the teacher used
semantically reasonable but inconsistent JSON keys. The current prompt states
literal per-variant schemas; existing structurally valid rows remain resumable.
Operational details are in the
[campaign runbook](/pages/mimir-benchmark-campaign-runbook.md).

The four still-active generated programs have stable, non-materialized records
in `exports_dfm10/manifest.json`. Registration does not imply acceptance,
tokenization, DFM10 sampling activation, or upload readiness.
