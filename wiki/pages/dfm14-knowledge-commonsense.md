---
type: Plan
title: DFM14 Knowledge and Commonsense Sources
description: English and Japanese candidate enrichment distinct from language coverage, with inherited-source checks and native-format admission requirements.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [data, dfm14, reasoning, commonsense, japanese]
---
# DFM14 Knowledge and Commonsense Sources

Research recommendation, not a change to DFM13 or an instruction to launch GPU
work. Complements [language priorities](dfm14-language-priorities.md).

## Ranked Enrichment Candidates

1. **Expand textbook-grounded English SFT.** The existing
   [OpenStax integration](dfm10-openstax-sft.md) records 50,000 accepted examples,
   8,592,140 rendered tokens, 61 historical books, repeat one. This is inherited
   material, not a newly discovered source. Expand uncovered chapters/concepts
   and problems with independent evidence and fresh tasks rather than repeating
   the old rows. Include everyday physics, biology, psychology, economics and
   misconception correction, not only advanced mathematics.
2. **Science SFT:** [nvidia/Nemotron-SFT-Science-v2](https://huggingface.co/datasets/nvidia/Nemotron-SFT-Science-v2).
   Card lists physics, biology, chemistry and 2,837,712 rows across synthetic
   MCQ, chemistry RQA, vendor problems and StackExchange-derived MCQ. Start with
   a balanced no-tool subset fitting context; retain full tool evidence for any
   tool subset. Do not blindly ingest long traces or foreign chat templates.
   Compare source IDs against inherited Nemotron/DOLCI before calling rows new.
3. **Everyday commonsense:** [ATOMIC 2020](https://github.com/allenai/comet-atomic-2020).
   Convert selected event/intent/prerequisite/consequence relations into varied
   scenarios with explicit assumptions and qualified, plausible answers. These
   are defeasible relations, not universal facts. Add contrastive alternatives
   and physical feasibility checks. Check inherited Sapient overlap first.
4. **Explanatory QA:** selected science/engineering/math StackExchange questions
   and answers via [Dolmino](https://huggingface.co/datasets/allenai/dolmino-mix-1124)
   or original sources. Preserve question-answer linkage, equations, attribution
   and indispensable context; accepted/upvoted does not prove correct. Existing
   Common Pile/StackExchange coverage must be deduplicated. Do not import the
   entire Dolmino mixture or bypass the FLAN deny-by-default policy.
5. **Scientific grounding:** [allenai/peS2o](https://huggingface.co/datasets/allenai/peS2o).
   Prefer explanatory introductions/reviews for source-grounded QA, comparison
   and evidence interpretation. Avoid paper-specific unsupported claims, missing
   figures and letting narrow research dominate everyday knowledge.
6. **Math enrichment:** [tokyotech-llm/swallow-math-v2](https://huggingface.co/datasets/tokyotech-llm/swallow-math-v2).
   Card lists English FineMath-derived rewritten QA and textbook variants, about
   32B upstream tokens in total. Prefer a bounded stage3-qa subset; do not add
   parallel textbook/QA rewrites of the same source unchecked. This is English
   reasoning enrichment, not Japanese language training. Upstream tokens are
   not our Gemma token counts and reported model gains are not HRM predictions.

## Japanese First Research Group

- [Swallow-Instruct-v0.1](https://huggingface.co/datasets/tokyotech-llm/Swallow-Instruct-v0.1)
  provides Japanese OASST imitation variants plus English OASST. Separate
  language coverage from genuinely new content; do not double-count alpha/beta
  variants or inherited English OASST.
- The [Swallow educational corpus work](https://huggingface.co/tokyotech-llm/edu-classifier/resolve/main/swallow-corpus-v2.pdf)
  supports investigating educational native prose. Confirm actual downloadable
  corpus availability and terms before scheduling; a paper/classifier release
  alone is not a corpus delivery guarantee.
- Prefer grounded native Japanese science/general-knowledge QA, rewriting and
  multi-turn explanations. Include some independently checked English versions
  of genuinely new material for transfer, with explicit duplicate weights.
- Do not infer Japanese language from the `tokyotech-llm` namespace:
  SwallowMath is English, and Swallow-Nemotron preview rows include English
  code problems with foreign control tokens and source test-split records.
  It needs source/split and native-template review, not blanket inclusion.

## Chinese Expansion and Transfer Follow-up

The public resource inventory supports a European-style expansion for Chinese:
existing instructions/chat, educational text for the four transformations,
grounded QA and synthetic conversational gaps. Russian, Turkish, Arabic and
Japanese also have credible starting pools, but none is already downloaded,
audited and assembly-ready by virtue of this research. Native chat quality,
language-specific correction/corruption rules, sentence segmentation and
teacher/reviewer calibration still require validation.

Chinese shortlist:

- [BAAI/Infinity-Instruct](https://huggingface.co/datasets/BAAI/Infinity-Instruct):
  bilingual instruction pool; select actual Chinese rows and source/task strata.
- [m-a-p/COIG-CQIA](https://huggingface.co/datasets/m-a-p/COIG-CQIA): curated native
  Chinese instruction/QA candidate. Inspect constituent sources, particularly
  exam/logic subsets, for overlap with evaluations; not blanket admission.
- [BAAI/IndustryInstruction](https://huggingface.co/datasets/BAAI/IndustryInstruction):
  education, science/research, geography and technical QA; prefer source-grounded
  Doc2QA examples. The card also describes ungrounded topic-based generation.
- [BAAI/CCI3-HQ](https://huggingface.co/datasets/BAAI/CCI3-HQ): Chinese text
  candidate for domain-balanced selection and transformations, not automatic
  acceptance of all web text as educational material.
- [openbmb/UltraData-Math](https://huggingface.co/datasets/openbmb/UltraData-Math):
  English/Chinese mathematical text and synthetic conversation/QA/exercise
  configurations. Select Chinese explicitly; L3 total counts are bilingual,
  and source rewrites overlap. Convert bounded complete QA into native Gemma
  format rather than indiscriminately importing the full corpus.

[C-Eval](https://github.com/hkust-nlp/ceval) and
[CMMLU](https://github.com/haonan-li/CMMLU) are evaluation suites, not recommended
training additions. Chinese school-science/explanation data targets capabilities
relevant to ARC-C but is not itself a verified Chinese ARC-C equivalent.

English transfer is plausible, not guaranteed. UltraData-Math reports mixed
English/Chinese training evaluated on English MMLU/ARC-C and math as well as
Chinese knowledge tasks; this does not isolate Chinese-only transfer. A
[cross-lingual reasoning study](https://arxiv.org/abs/2509.23657) on Qwen2.5-3B
finds stronger transfer with RL than SFT, so its non-English RL result must not
be presented as proof for our HRM SFT recipe. Compare equal-token native-Chinese,
English-rendered and bilingual versions of the same clean educational content,
with old-language retention and decontamination checks.

## Inherited Source Checks

The downloader already registers `facebook/natural_reasoning`,
`facebook/principia-collection`, `MegaScience/TextbookReasoning`, multiple
Nemotron sources and Common Pile StackExchange. Registration is not proof of
final sampling or non-overlap. Audit actual sampled contributions and source
identifiers before recommending more copies. Narrow FLAN commonsense/science
allow overrides already exist; do not present familiar benchmark training
splits as wholly new additions without checking inherited coverage.

## Pilot Proposal

An initial **500K accepted-row** knowledge pilot, subject to approval:

| Family | Accepted rows |
|---|---:|
| Textbook conceptual/application/misconception tasks | 150,000 |
| Balanced science reasoning SFT | 100,000 |
| Everyday physical/social commonsense scenarios | 100,000 |
| Explanatory technical QA | 75,000 |
| Scientific evidence interpretation | 25,000 |
| SwallowMath QA | 50,000 |

Rough sizing assumption: 500-1,000 rendered tokens/row gives 250-500M tokens;
replace with measured counts before assembly. No download or GPU generation is
authorized by this proposal. Keep Japanese coverage as a separately measured
pilot so language acquisition and reasoning gains can be distinguished.

All accepted data must use native Gemma conversation rendering; preserve needed
evidence, complete answers and tools, and avoid truncating solutions. Remove
evaluation questions and translated duplicates. Evaluate equal-token ablations
on MMLU/ARC-C and commonsense tasks plus Danish retention. More multilingual
text alone is not evidence of improved English reasoning.

## Benchmark Focus and Production Budget

Planning clarification on 2026-10-05: target the underlying capabilities, not
held-out MMLU, ARC-C or MATH questions. The 500K proposal above is separate from
the 35K/70K language-coverage allocations; overlapping sources must be counted
once. MMLU benefits are sought through textbook breadth, science and technical
explanations. ARC-C emphasis is everyday physical science, causal reasoning,
misconceptions and plausible distractor contrasts. MATH emphasis is complete,
verified worked problems with native reasoning/final-answer conventions, not
more answer-format noise. The initial dedicated math allocation is only 50K;
Chinese/English UltraData-Math remains an additional candidate without an
approved row target. Audit inherited MATH training coverage before increasing
repeats or claiming new problems.

On eight dedicated B200s with Gemma 4 26B A4B, provisionally allocate:

| Work | Accepted target | Approximate GPU walltime |
|---|---:|---:|
| New textbook-grounded tasks | 150K | 4-9 h |
| Existing science SFT selection/audit/repair | 100K | 1-4 h |
| New commonsense scenarios | 100K | 3-6 h |
| Existing explanatory QA selection/audit/repair | 75K | 1-3 h |
| New evidence interpretation tasks | 25K | 1-3 h |
| Existing math QA selection/audit/verification/repair | 50K | 2-6 h |

These are estimates, not measured per-source service times. Generation figures
use discounted net acceptance rates; audit figures allow candidate rejection
and repair. Long math/science solutions may be slower than the compact bulk
reviewer. Symbolic/numeric checks where applicable complement, not replace,
reasoning review. Do not assume every answer can be verified automatically.

Total GPU capacity budget is about **12-31 h**, reserve **1-2 days** with
calibration and tails. CPU sourcing, deduplication, provenance, packaging,
tokenization and upload bring the end-to-end pilot to roughly **2-4 days**,
provided the sources are accessible and preparation overlaps inference.
This excludes model training and downstream evaluation. If sharing GPUs with
the language campaign, add the GPU demand rather than promising both campaigns
the full eight-GPU throughput. See [production estimates](dfm14-production-estimate.md).
