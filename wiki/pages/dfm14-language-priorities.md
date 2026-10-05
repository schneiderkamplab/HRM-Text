---
type: Plan
title: DFM14 Language Priorities
description: Candidate missing languages ranked by coverage value, source readiness, evaluation availability and potential reasoning transfer.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [data, multilingual, dfm14, evaluation]
---
# DFM14 Language Priorities

## Scope and Evidence

The [DFM14 plan](dfm14-plan.md) is the entry point. The expanded
[source readiness assessment](dfm14-language-source-readiness.md) refines the
initial shortlist below, especially Basque and Galician readiness.

Recommendation only: no additions, generation jobs or changes to the running
DFM13 assembly are authorized by this assessment. See the
[language waves](language-extension-waves.md) and
[other post-DFM13 additions](dfm14-potential-additions.md).
DFM13 targets 34 language variants. Missing here means no dedicated extension,
not necessarily zero incidental examples in inherited multilingual sources.

The live [EuroEval dataset index](https://euroeval.com/llms.txt), checked on
2026-10-05, lists language pages already covered by DFM13. It does not list
Russian or Turkish dataset pages. A language definition in the Python registry
is not evidence of a complete benchmark suite. New candidates need explicit
eval integration rather than an assumption that existing EuroEval rows suffice.

## Combined Priority

2026-10-05 follow-up: include Japanese in the first research group alongside
Russian, Turkish, Chinese and Arabic. This changes research scope, not admission
or the evidence behind the ranking. Also pursue English knowledge/commonsense
enrichment regardless of source-country; see
[knowledge and commonsense candidates](dfm14-knowledge-commonsense.md).

This is an engineering judgment balancing the European mission with broader
capability. It is not a measured ranking of transfer gains.

| Rank | Language | Evaluation route | Text and QA/chat route | Rationale |
|---|---|---|---|---|
| 1 | Russian | MERA; Global-MMLU; Belebele | Wikipedia, selected educational prose, audited Russian Aya and native chat candidates | Major European gap; plausible access to additional technical/science explanations; existing Cyrillic coverage helps reuse but does not establish competence. |
| 2 | Turkish | TurkishMMLU; Global-MMLU; Belebele | Wikipedia, selected educational prose, Aya, merve/turkish_instructions as a reviewed seed | Major regional gap with usable evaluation and SFT starting points; translated Alpaca is not sufficient evidence of native chat quality. |
| 3 | Chinese, initially Simplified | Global-MMLU; CMMLU candidate | Educational Chinese text; Chinese portion of BAAI/Infinity-Instruct | Strongest candidate for a new pool of math/science/code supervision; larger adaptation investment than another closely related European language. |
| 4 | Arabic, initially MSA | ArabicMMLU; Global-MMLU; Belebele | Native educational/Wikipedia prose; arbml/CIDAR and Arabic Aya | Major coverage gap with native instructions and exams. Track MSA and dialects separately rather than claiming all Arabic coverage. |
| 5 | Japanese | Global-MMLU; native Japanese exam suites to pin | Educational prose; tokyotech-llm/Swallow-Instruct-v0.1 | Good technical content potential; verify source access and tokenizer efficiency before setting budgets. |
| 6 | Korean | HAERAE-HUB/KMMLU; Global-MMLU | Native educational/Wikipedia prose; Korean Aya followed by grounded native chat | Strong native evaluation; separate training-source quality review still needed. |
| 7 | Hindi | Global-MMLU; Belebele | Native prose; ai4bharat/indic-align, Aya | Large coverage gain with existing instruction infrastructure; Hindi/English code switching needs explicit handling. |
| 8 | Indonesian | Global-MMLU; Belebele; SEACrowd | Native prose; Aya and SEACrowd instruction/QA sources | Practical coverage expansion with text and evaluation ecosystem; generic chat offers less clear English reasoning transfer. |
| 9 | Vietnamese | Global-MMLU; Belebele; SEACrowd | Native prose; Aya and SEACrowd sources | Similar practical case to Indonesian; require native quality review. |
| 10 | Hebrew | Global-MMLU; Belebele | Native prose and Aya; additional native chat procurement | Useful regional extension; smaller immediately identified instruction pool than the top priorities. |

All text candidates require quality filtering and source-specific admission.
[FineWeb2](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2) offers broad
language coverage, but filtered web text is not automatically high-quality
instruction data. Prefer educational/native prose; use web sources as a
screened fallback. Preserve the current non-Danish transform/grounded-SFT
policy rather than silently introducing raw continuation training.

Second group: Irish and Maltese for official-EU-language completeness;
Basque, Galician, Welsh and Macedonian for European breadth. These need a
separate source/evaluation inventory; no claim of ready-made full suites.
Brazilian Portuguese is a variety-coverage question, not a wholly absent
Portuguese language. Thai, Bengali, Urdu, Swahili, Georgian and Armenian are
further candidates, not ruled out by this initial ranking.

## MMLU and ARC-C Expectations

New language coverage is not itself evidence of improved English MMLU/ARC-C.
The proposed Chinese/Russian/Japanese/Korean benefit is access to *additional*
technical and worked-reasoning content, not an intrinsic property of a language.
Generic chat, translation and repeated parallel answers mostly address language
competence and can dilute reasoning exposure at a fixed compute budget.

For English benchmark gains, prioritize independently sourced science concepts,
causal explanations, numerical reasoning, distractor analysis and executable
code tasks. Keep benchmarks and their translations out of training. Use
audited English renderings of a subset of genuinely new educational material
to test cross-language transfer, avoiding uncontrolled duplicate upweighting.

Run equal-token comparisons: existing mixture; English reasoning enrichment;
new-language general SFT; new-language educational/reasoning enrichment.
Keep old-language anchors, training steps and LR schedule comparable. Measure
English MMLU/ARC-C/MATH/HumanEval plus native-language heldouts and Danish
retention. No numeric improvement estimate is defensible before this test.

## Source Entry Points

- [Global-MMLU](https://huggingface.co/datasets/CohereLabs/Global-MMLU) and
  [Belebele](https://huggingface.co/datasets/facebook/belebele): broad evaluation
  starting points, not substitutes for instruction-following and GEC tests.
- [MERA](https://huggingface.co/datasets/MERA-evaluation/MERA),
  [TurkishMMLU](https://github.com/ArdaYueksel/TurkishMMLU),
  [ArabicMMLU](https://huggingface.co/datasets/MBZUAI/ArabicMMLU),
  [KMMLU](https://huggingface.co/datasets/HAERAE-HUB/KMMLU).
- [Aya human-curated dataset](https://huggingface.co/datasets/CohereLabs/aya_dataset)
  versus [Aya Collection](https://huggingface.co/datasets/CohereLabs/aya_collection):
  distinguish original annotations from templated/translated sources; audit and
  deduplicate against inherited sources. Collection size is not unique native chat.
- [Infinity-Instruct](https://huggingface.co/datasets/BAAI/Infinity-Instruct),
  [CIDAR](https://huggingface.co/datasets/arbml/CIDAR),
  [Swallow-Instruct](https://huggingface.co/datasets/tokyotech-llm/Swallow-Instruct-v0.1),
  [IndicAlign](https://huggingface.co/datasets/ai4bharat/indic-align),
  [Turkish instructions](https://huggingface.co/datasets/merve/turkish_instructions),
  [SEACrowd](https://seacrowd.org/projects/2024-seacrowd.html).

This is a dataset-card-level shortlist, not a completed row audit, licence
approval or confirmation of compatibility with every existing evaluator.
