---
type: Research
title: DFM14 Additional Instruction Candidates
description: Verified multilingual leads separated from existing registrations and admission decisions.
status: draft
confidence: medium
last_updated: 2026-10-07
tags: [dfm14, instruction, multilingual]
---
# Additional Instruction Candidates

HF cards/API and local catalogs inspected on 2026-10-07. These are research
recommendations, not accepted rows or new download authorizations.

| Source | Value and constraints |
| --- | --- |
| [llm-jp/magpie-sft-v1.0](https://huggingface.co/datasets/llm-jp/magpie-sft-v1.0) | Japanese synthetic instructions; Apache-2.0. Card gives 100K-1M size band, not verified exact count. Strong new lead. |
| [FreedomIntelligence/Evol-Instruct-Arabic-GPT4](https://huggingface.co/datasets/FreedomIntelligence/Evol-Instruct-Arabic-GPT4) | 69,997 train rows; GPT4-translated questions with GPT4 Arabic answers. Compare/replace overlapping older evol-instruct-arabic rather than count both as independent. |
| [Vikhrmodels/Grounded-RAG-Chat-RU](https://huggingface.co/datasets/Vikhrmodels/Grounded-RAG-Chat-RU) | 28,075 train conversations grounded in Russian Wikipedia. Custom documents role and consecutive assistant turns need explicit conversion; designed for 16K, so length filtering required. |
| [llm-jp/llm-jp-instructions](https://huggingface.co/datasets/llm-jp/llm-jp-instructions) | 300 manually authored train examples; small diversity addition. Its separate jculture repository is test-only and not a training candidate. |
| [orai-nlp/MagpieEU](https://huggingface.co/datasets/orai-nlp/MagpieEU) | 261,304 Basque train rows, already in DFM14 catalog; expand bounded coverage if audit supports it. Llama3.1 license metadata, not Apache. |
| [indonlp/cendol_collection_v2](https://huggingface.co/datasets/indonlp/cendol_collection_v2) | 12.81M train rows across the collection, not all independent Indonesian chat. Already cataloged; select chat/instruction components and check benchmark/task duplication. |

Existing pools also include Turkish collected instructions/Python, Korean
open-korean-instructions and math, Hindi IndicAlign, Vietnamese viet4all and
Russian Saiga/GrandMaster. Registration does not establish successful full
preparation or quality. The old llm-jp/ichikara-instruction identifier returned
RepositoryNotFoundError; do not count it as acquired.

For older European languages, EU-Instruct-Synthetic, translated DOLCI,
EuroBlocks, Aya, Poro and PLLuM are already registered in previous waves. Compare
actual admitted rows and revisions before proposing them as additions. Portuguese
EU-Instruct cannot automatically be labeled European Portuguese.

Low-resource Irish, Maltese, Welsh, Macedonian and Hebrew remain candidates for
curated Aya plus grounded native synthesis; this search did not verify a large
high-quality native chat pool for each. Do not infer one from a translated-Alpaca
repository name.

## English Follow-up

2026-10-07 card/config review: prioritize the newly generated Apache-2.0
components of [SmolTalk](https://huggingface.co/datasets/HuggingFaceTB/smoltalk):
Smol-Magpie-Ultra (~400K), constraints (~36K), rewrite (~50K), summarize (~100K).
Do not admit the whole mixture: it also includes raw OpenHermes and LongAlign,
which conflict with existing source/evaluation boundaries. Components may overlap
inherited DOLCI/Tulu; absence of a direct prefix is not proof of novel rows.

[SmolTalk2](https://huggingface.co/datasets/HuggingFaceTB/smoltalk2) adds 28,217
multi-turn instruction-following and 9,079 tool-trace examples (Apache-2.0 for
new components). Existing everyday/system chat subsets are already registered.
Preserve reasoning/tool schema and filter whole conversations to native context.

[OpenCoder stage2](https://huggingface.co/datasets/OpenCoder-LLM/opc-sft-stage2)
has MIT metadata: educational 118,278 and package 170,943 are promising
targeted additions; evol is a Magicoder repack, and McEval-derived material
requires explicit evaluation-overlap review rather than bulk admission.
[UltraChat200K](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k)
has 207,865 train_sft examples and MIT metadata, but likely substantial inherited
overlap and less novelty. Do not use test_sft/test_gen.

The inherited DFM11 prefix policy already repeats DOLCI no-tools 3x,
Tulu3 mixture 2x, and repaired DOLCI tools 2x. This is not evidence of
undersampling those large families. Actual DFM13 exposure must be measured from
its sampled indices, not inferred solely from old caps/repeats. Nemotron v2's
CC-BY metadata also comes with card notices about generator-model terms;
mixture-level metadata does not settle every constituent's permissions.
