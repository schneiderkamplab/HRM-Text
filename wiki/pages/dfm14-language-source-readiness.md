---
type: Research Note
title: DFM14 Language Source Readiness
description: Source-card-level readiness assessment for the next languages, including native instruction breadth and preparation gaps.
status: draft
confidence: medium
last_updated: 2026-10-05
tags: [data, dfm14, multilingual, sources]
---
# DFM14 Language Source Readiness

See [DFM14 plan](dfm14-plan.md) and [priorities](dfm14-language-priorities.md).
Checked public source cards on 2026-10-05. These are discovery candidates, not
download receipts, audited row counts, licence approvals or integration results.
The practical question is whether there are credible inputs for our previous
European-wave recipe, not whether all prerequisites already exist locally.

## Main Candidates

| Language | Instruction/chat candidates | Text/grounding route | Evaluation route | Assessment and missing work |
|---|---|---|---|---|
| Russian | `IlyaGusev/saiga_scored`, Russian Aya, OASST Russian branches | Native Wikipedia, selected educational texts; `IlyaGusev/gazeta` for news-summary pairs | MERA, Global-MMLU, Belebele | Strong starting point. Score fields are not independent factual verification; deduplicate OASST and inspect current source composition. |
| Turkish | `merve/turkish_instructions`, Turkish Aya; procure more native multi-turn material | `ytu-ce-cosmos/Cosmos-Turkish-Corpus-v1.0`, native Wikipedia | TurkishMMLU, Global-MMLU, Belebele | Viable; translated Alpaca cannot supply all chat/reasoning breadth. Web-corpus title does not establish educational quality. |
| Chinese | Infinity-Instruct, COIG-CQIA, IndustryInstruction, UltraData-Math selected Chinese QA | CCI3-HQ, selected educational/industry text | C-Eval, CMMLU, Global-MMLU, Chinese math holdouts | Strong supply. See knowledge note for detailed sources. Source-level overlap, unsupported claims and exam leakage need explicit checks. |
| Arabic | `arbml/CIDAR`, Arabic Aya; translated chat only as a supplement | Native Wikipedia and selected educational text; screened Arabic FineWeb2 | ArabicMMLU, Global-MMLU, Belebele | Viable for MSA. Dialects require separate targets. Do not conflate translated English tasks with new native knowledge. |
| Japanese | `tokyotech-llm/Swallow-Instruct-v0.1`; investigate original Ichikara instruction release | Native Wikipedia, selected educational text, Swallow corpus work subject to payload access | Global-MMLU plus pinned native exam/reading suites | Strong starting point. SwallowMath is English, not Japanese. Confirm original Ichikara terms and avoid alpha/beta duplicates. |
| Korean | `heegyu/open-korean-instructions`, `HAERAE-HUB/HR-Instruct-Math-v0.1`, Korean Aya; KorQuAD training subset with passage | `HAERAE-HUB/KOREAN-WEBTEXT`, native Wikipedia | KMMLU, Global-MMLU; separate reading holdouts | Viable. Some instruction sources are translated/aggregated; inspect overlap and formal/informal language balance. |
| Hindi | `ai4bharat/indic-align`, Hindi Aya | Native Wikipedia; Indic corpora to pin and screen | Global-MMLU, Belebele | Strong volume. IndicAlign contains multiple languages and English; select real Hindi, distinguish scripts/code switching, audit answers. |
| Indonesian | `indonlp/cendol_collection_v2`, Aya and SEACrowd candidates | Native Wikipedia and screened FineWeb2 | Global-MMLU, Belebele, SEACrowd | Strong starting point. Cendol is multilingual and task-templated; select Indonesian and preserve evaluation splits. |
| Vietnamese | `Viet-Mistral/viet4all`, Aya and native QA candidates via SEACrowd | Native Wikipedia, screened educational/web text | Global-MMLU, Belebele, SEACrowd | Viable, but translated OpenHermes ancestry needs deduplication and modernized native-format audit. |
| Hebrew | Hebrew Aya; further native multi-turn sources still to locate | Native Wikipedia, modern prose; separately review historical Ben-Yehuda material | Global-MMLU, Belebele | Text route credible, native chat breadth least established among these ten. Dicta model releases/calibration samples do not prove public SFT availability. |

FineWeb2 is a fallback pool, not a replacement for domain/quality selection.
For all languages preserve paragraphs in transformation seeds and filter missing
figures, bad OCR, navigation and context-dependent fragments. Native Wikipedia
is a seed option, not a claim that it is uniformly accurate or sufficient alone.

## Smaller European Extensions

| Language | Concrete starting point | Current assessment |
|---|---|---|
| Basque | HiTZ instruction collection and `BSC-LT/ALIA-2606-SFT`; native Latxa evaluation resources to pin | More practical than the previous generic low-resource grouping implied; good candidate for a Europe-first second group. Verify individual corpus delivery and Basque share. |
| Galician | `BSC-LT/ALIA-2606-SFT`, `proxectonos/cpt_instruction_datasets`, `proxectonos/galician-gec-corpora` | Promising instruction and correction routes. Newer native/curated resources preferred to simply adding the old translated 52K Alpaca. Pin independent eval holdouts. |
| Irish | `jmcinern/Dolly-V2-gle`; native prose/official documents to inventory | Feasible seed, but translated Dolly is not broad native chat. More grounded generation and independent language review needed. |
| Maltese | `ptrdvn/kakugo-mlt`; native prose/official documents to inventory | Concrete synthetic chat candidate, not an empty landscape. Card includes thinking prompts/tags: convert semantics, do not teach foreign template tags. Native audit required. |
| Welsh | `ptrdvn/kakugo-cym`, original `techiaith/cofnodycynulliad_en-cy` parallel source | Promising synthetic and parallel starting points. Parallel parliamentary material is not automatically multi-turn assistant dialogue. |
| Macedonian | `MartinV/clement-mk-handwritten` candidate; native prose to inventory | Thin independently established native instructions. Card raises translation-quality concerns; do not generalize those claims to all corpora without our own sample audit. |

Brazilian Portuguese remains a variant-coverage audit, not a new language.
Thai, Bengali, Urdu, Swahili, Georgian and Armenian remain a later research
backlog; no completed readiness assessment is claimed for them.

## Primary Source Links

- [Saiga scored](https://huggingface.co/datasets/IlyaGusev/saiga_scored) and
  [Gazeta](https://huggingface.co/datasets/IlyaGusev/gazeta).
- [Cosmos Turkish](https://huggingface.co/datasets/ytu-ce-cosmos/Cosmos-Turkish-Corpus-v1.0)
  and [Turkish instructions](https://huggingface.co/datasets/merve/turkish_instructions).
- [CIDAR](https://huggingface.co/datasets/arbml/CIDAR),
  [Swallow-Instruct](https://huggingface.co/datasets/tokyotech-llm/Swallow-Instruct-v0.1).
- [Korean instructions](https://huggingface.co/datasets/heegyu/open-korean-instructions),
  [Korean math](https://huggingface.co/datasets/HAERAE-HUB/HR-Instruct-Math-v0.1),
  [Korean web text](https://huggingface.co/datasets/HAERAE-HUB/KOREAN-WEBTEXT).
- [IndicAlign](https://huggingface.co/datasets/ai4bharat/indic-align),
  [Cendol v2](https://huggingface.co/datasets/indonlp/cendol_collection_v2),
  [Viet4all](https://huggingface.co/datasets/Viet-Mistral/viet4all).
- [HiTZ instructions](https://huggingface.co/collections/HiTZ/instruction-datasets),
  [ALIA SFT](https://huggingface.co/datasets/BSC-LT/ALIA-2606-SFT),
  [Galician instructions](https://huggingface.co/datasets/proxectonos/cpt_instruction_datasets),
  [Galician GEC](https://huggingface.co/datasets/proxectonos/galician-gec-corpora).
- [Irish Dolly](https://huggingface.co/datasets/jmcinern/Dolly-V2-gle),
  [Maltese Kakugo](https://huggingface.co/datasets/ptrdvn/kakugo-mlt),
  [Welsh Kakugo](https://huggingface.co/datasets/ptrdvn/kakugo-cym),
  [Welsh parliamentary parallel](https://huggingface.co/datasets/techiaith/cofnodycynulliad_en-cy),
  [Macedonian handwritten](https://huggingface.co/datasets/MartinV/clement-mk-handwritten).

## Next Research Gates

1. Pin revisions and inspect random rows per source/component, not only previews.
2. Measure unique native rows and complete multi-turn conversations after
   inherited-source deduplication; do not assign 35K vs 70K from aggregate sizes.
3. Inventory native educational texts and English parallel pairs with actual
   volumes, terms and split provenance. All-to-all translation coverage remains
   unverified at this stage.
4. Audit language quality, coherence, grounding and usefulness. Calibrate the
   reviewer per language and reject unsupported context rather than invent it.
5. Prepare native-format examples and separate holdouts before generation.
