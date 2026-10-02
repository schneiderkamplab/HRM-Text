---
type: Research
title: European Language Expansion Source Inventory
description: Verified Hugging Face text, SFT and preference candidates and language-specific supply evidence for the expansion ranking.
status: draft
confidence: medium
last_updated: 2026-09-26
tags: [multilingual, hf, text, instruction, source-inventory]
---
# European Language Expansion Source Inventory

Portuguese update (2026-09-26): the [variant reassessment](portuguese-expansion-reassessment.md)
adds AMALIA, CorEGe-PT and GigaVerbo-v2 sources missed in this initial snapshot.

Evidence supporting the [five-score ranking](european-language-expansion-ranking.md).
Inspected HF repository cards/API metadata and dataset-viewer size/statistics
on 2026-09-26. Counts below are upstream supply, not accepted, deduplicated
training rows. No bulk corpus download or native-language audit was performed.

## Cross-Language Building Blocks

| HF dataset | Role and inspected evidence | Important qualification |
| --- | --- | --- |
| [coral-nlp/german-commons](https://huggingface.co/datasets/coral-nlp/german-commons) | German text: card reports 154.56B GPT-2 tokens, 35.78M documents, 41 sources, seven domains; per-record licenses, perplexity and OCR quality | Historical news/cultural material dominates. Prefer contemporary political/scientific/reference subsets and high OCR quality; these are not our tokenizer's token counts |
| [PleIAs/common_corpus](https://huggingface.co/datasets/PleIAs/common_corpus) | Open-license/public-domain text, card reports 2.27T tokens and 33 languages above 1B; books, news, science, government/legal and reference sources | Language/source/OCR filtering required; do not infer every shortlisted language has 1B tokens. This is Common Corpus, not Common Pile |
| [wikimedia/wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia) | Native reference articles, language-specific configurations | Reliable seed structure, not infallible facts. Snapshot age, topic skew, citations and evaluation overlap require screening |
| [wikimedia/wikisource](https://huggingface.co/datasets/wikimedia/wikisource) | Native longer-form source texts | Historical orthography and edition quality; use selectively rather than making it the default conversational register |
| [HuggingFaceFW/finepdfs-edu](https://huggingface.co/datasets/HuggingFaceFW/finepdfs-edu) | 69-language PDF collection, 350B+ tokens overall; per-language row counts below | Web-derived PDFs, not uniformly edited prose. Card explicitly warns of code-switching; top-decile educational filtering does not guarantee high absolute quality. Check page/full-document LID, OCR, truncation, source domains and rights |
| [HPLT/HPLT3.0](https://huggingface.co/datasets/HPLT/HPLT3.0) | Large multilingual text reserve when curated seeds are insufficient | Web-derived fallback, not primary evidence of high-quality native instructions |
| [openeurollm/Dolci-Instruct-SFT-translated](https://huggingface.co/datasets/openeurollm/Dolci-Instruct-SFT-translated) | Roughly 495K rows each for cs/de/el/es/fi/fr/it/nl/pl/ro/sv/uk; exact counts below | Translated, not native-authored; card largely metadata-only. Translator and language-specific audit evidence need investigation. Reuse DOLCI-specific semantic/tool converters, not literal foreign template text |
| [openeurollm/Dolci-Instruct-DPO-translated](https://huggingface.co/datasets/openeurollm/Dolci-Instruct-DPO-translated) | Preference release; metadata lists cs/de/es/el/fi/fr/it/pl/ro/sv/uk | No Dutch in inspected DPO language metadata. Size endpoint returned HTTP 500; do not infer exact per-language counts or blindly reuse translated preference labels |
| [openeurollm/EU-Instruct-Synthetic](https://huggingface.co/datasets/openeurollm/EU-Instruct-Synthetic) | 1,497,276 single-turn instruction pairs across 11 languages, 119K-150K per language | Card describes synthgen-if generation but limited audit detail. It is single-turn supply, not evidence of multi-turn competence |
| [utter-project/EuroBlocks-SFT-2512](https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-2512) | 1,094,265 conversations overall; language-labelled counts vary greatly | English dominates. Card warns language labels can be inaccurate; mixed-language labels are separate. Do not assume 1M conversations per EU language |
| [utter-project/EuroBlocks-SFT-Synthetic-1124](https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-Synthetic-1124) | 340,286 rows with source/quality metadata; native-seeded, constraint-following and other synthetic subsets | Likely overlaps later EuroBlocks and Aya. Different subset terms, noisy reward scores, and MMLU/ARC-like subsets need provenance/contamination checks |
| [CohereLabs/aya_dataset](https://huggingface.co/datasets/CohereLabs/aya_dataset) | 202,364 human-written/edited train pairs across 71 language/dialect labels | Tiny per-language amounts in some cases. Keep train only; demographic records are not training text |
| [CohereLabs/aya_collection_language_split](https://huggingface.co/datasets/CohereLabs/aya_collection_language_split) | Much larger templated/translated task mixture, distinct from the human Aya Dataset | Not 513M unique human chat examples. Source-level train/test isolation and dedup are mandatory; task-template diversity is not conversational diversity |
| [MBZUAI/Bactrian-X](https://huggingface.co/datasets/MBZUAI/Bactrian-X) | Around 67K translated Alpaca/Dolly prompts per supported language, GPT-3.5 responses | Older synthetic fallback, not a premium source. Translated copies share IDs across languages; review source terms and benchmark overlap |

The HF search for DynaWord found the already known Danish/Norwegian/Swedish/
Dutch/Icelandic/Faroese/Polish families, not equivalent DynaWord releases for
all the languages ranked here. Do not invent `german-dynaword` or similar IDs.

## Comparable Supply Snapshot

PDF rows come from the FinePDFs-Edu `size` API, with one language configuration
per row. They are documents, not tokens and not all usable modern native text.
EuroBlocks counts come from `statistics` on `default/train`, exact monolingual
label only; translation-pair labels are excluded. A dash means no matching
configuration/label found in the inspected response, not universal absence.

| Language | FinePDFs-Edu config | PDF rows | DOLCI SFT translated rows | EU-Instruct-Synthetic rows | EuroBlocks-2512 monolingual-labelled rows |
| --- | --- | ---: | ---: | ---: | ---: |
| Spanish | spa_Latn | 2,820,804 | 494,816 | 132,736 | 37,576 |
| French | fra_Latn | 2,983,957 | 494,795 | 119,497 | 35,792 |
| German | deu_Latn | 3,844,508 | 494,796 | 135,786 | 33,524 |
| Portuguese | por_Latn | 1,269,644 | - | 131,707 | 30,277 |
| Russian | rus_Cyrl | 1,724,870 | - | - | 15,623 |
| Italian | ita_Latn | 1,868,040 | 494,796 | 136,407 | 34,015 |
| Czech | ces_Latn | 586,520 | 494,757 | 150,129 | 4,549 |
| Ukrainian | ukr_Cyrl | 290,072 | 494,836 | 146,092 | 5,710 |
| Finnish | fin_Latn | 211,328 | 494,731 | - | 1,607 |
| Turkish | tur_Latn | 185,207 | - | - | 742 |
| Greek | ell_Grek | 209,039 | 494,661 | 138,048 | 572 |
| Romanian | ron_Latn | 328,609 | 494,843 | 129,112 | 5,270 |
| Catalan | cat_Latn | 200,432 | - | - | 1,358 |
| Hungarian | hun_Latn | 343,121 | - | - | 4,236 |
| Basque | eus_Latn | 37,708 | - | - | - |
| Galician | glg_Latn | 30,901 | - | - | - |
| Estonian | ekk_Latn | 57,559 | - | - | 288 |
| Bulgarian | bul_Cyrl | 138,264 | - | - | 261 |
| Serbian | srp_Cyrl | 97,596 | - | - | - |
| Croatian | hrv_Latn | 149,301 | - | - | 51 |
| Slovak | slk_Latn | 228,821 | - | - | 874 |
| Lithuanian | lit_Latn | 96,715 | - | - | 14 |
| Latvian | lvs_Latn | 58,471 | - | - | 165 |
| Albanian | als_Latn | 20,962 | - | - | 7 |
| Slovenian | slv_Latn | 101,931 | - | - | 197 |
| Welsh | cym_Latn | 16,560 | - | - | 42 |
| Irish | not present | - | - | - | - |
| Maltese | mlt_Latn | 16,490 | - | - | - |

Reproduce metadata queries without loading corpora:

```text
https://huggingface.co/api/datasets/<HF_ID>
https://huggingface.co/datasets/<HF_ID>/raw/main/README.md
https://datasets-server.huggingface.co/size?dataset=<HF_ID>
https://datasets-server.huggingface.co/statistics?dataset=<HF_ID>&config=default&split=train
```

These are live endpoints. Pin revisions before acquisition; viewer statistics
may lag repository updates. Exact figures are the observed snapshot, not a
promise of accepted yield. The ranking is intentionally not a linear function
of these row counts because document lengths and content quality differ.

## Language-Specific Shortlists And Score Rationale

### Large Western Languages

| Language | Text candidates | Instruction/preference candidates | Why this score; principal limitation |
| --- | --- | --- | --- |
| Spanish | [PleIAs/Spanish-PD-Books](https://huggingface.co/datasets/PleIAs/Spanish-PD-Books), [PleIAs/Spanish-PD-Newspapers](https://huggingface.co/datasets/PleIAs/Spanish-PD-Newspapers), Common Corpus, Wikipedia, selected FinePDFs | [BSC-LT/ALIA-2606-SFT](https://huggingface.co/datasets/BSC-LT/ALIA-2606-SFT): 135,512 Spanish rows; DOLCI, EU-Instruct, EuroBlocks, Aya | Broad reach and strong local post-training ecosystem. ALIA includes foreign self-identity, FLORES-dev and reused components: filter rather than import wholesale |
| French | [croissantllm/croissant_dataset_no_web_data](https://huggingface.co/datasets/croissantllm/croissant_dataset_no_web_data), [OpenLLM-France/Lucie-Training-Dataset](https://huggingface.co/datasets/OpenLLM-France/Lucie-Training-Dataset) non-web/reference/parliamentary subsets, Common Corpus | [angeluriot/french_instruct](https://huggingface.co/datasets/angeluriot/french_instruct): 275,600 conversations, card estimates 84.9M tokens; DOLCI, EU-Instruct, EuroBlocks | Native text breadth plus mixed human/synthetic instructions. French Instruct's human/synthetic labels help selection, but source-level audit remains necessary |
| German | German Commons, [PleIAs/German-PD](https://huggingface.co/datasets/PleIAs/German-PD), Wikipedia, selected FinePDFs | DOLCI, EU-Instruct; [OpenAssistant/OASST-DE](https://huggingface.co/datasets/OpenAssistant/OASST-DE): 3,721 native/translated conversations; [DiscoResearch/germanrag](https://huggingface.co/datasets/DiscoResearch/germanrag) for grounded answering/abstention | Particularly transparent text supply; strong total SFT supply but much is translated. GermanRAG derives from GermanDPR and requires evaluation-overlap screening |
| Portuguese | [TucanoBR/GigaVerbo](https://huggingface.co/datasets/TucanoBR/GigaVerbo) selected quality-labelled components, [PleIAs/Portuguese-PD](https://huggingface.co/datasets/PleIAs/Portuguese-PD), Wikipedia | [TucanoBR/Tucano-SFT](https://huggingface.co/datasets/TucanoBR/Tucano-SFT): approximately 680K synthetic conversations, including math; EU-Instruct, EuroBlocks; Aya train has 8,997 Portuguese rows | Substantial supply and global reach, but much is Brazilian Portuguese. Track pt-BR/pt-PT explicitly. GigaVerbo retains low-quality records too: filter labels, confidence and source |
| Italian | [PleIAs/Italian-PD](https://huggingface.co/datasets/PleIAs/Italian-PD), Common Corpus, Lucie Italian sources, Wikipedia | DOLCI, EU-Instruct, EuroBlocks; [SerFabio89/italian-open-sft-chat-dataset](https://huggingface.co/datasets/SerFabio89/italian-open-sft-chat-dataset): 69,285 rows across splits | Good availability, more uncertain broad-chat quality. The smaller Italian-first collection has formatting/multi-turn tasks but anonymized teacher names and no attached audit summary; treat as a pilot candidate, not certified quality |

Do not mistake [OpenLLM-France/Luciole-PostTraining-Dataset-1.1](https://huggingface.co/datasets/OpenLLM-France/Luciole-PostTraining-Dataset-1.1)
for a multi-million-row French corpus: its card explicitly says primarily
English. Select verified French subsets only. Likewise, the ALIA SFT mixture
is 713,619 total rows, not that many Spanish rows.

### Central, Eastern And Northern Europe

| Language | Text candidates | Instruction/preference candidates | Why this score; principal limitation |
| --- | --- | --- | --- |
| Russian | [PleIAs/Russian-PD](https://huggingface.co/datasets/PleIAs/Russian-PD), Common Corpus, Wikipedia, selected FinePDFs | [IlyaGusev/saiga_scored](https://huggingface.co/datasets/IlyaGusev/saiga_scored): 41,609 train rows; [IlyaGusev/ru_turbo_saiga](https://huggingface.co/datasets/IlyaGusev/ru_turbo_saiga), [IlyaGusev/saiga_preferences](https://huggingface.co/datasets/IlyaGusev/saiga_preferences), EuroBlocks, Aya | Large reach and text pool. Saiga scored card is sparse and license metadata missing in inspected response; audit provenance, duplication and teacher identity |
| Czech | [PleIAs/Czech-PD](https://huggingface.co/datasets/PleIAs/Czech-PD): card reports about 259M words; Wikipedia, selected FinePDFs | [ctu-aic/cs_instruction_tuning_collection](https://huggingface.co/datasets/ctu-aic/cs_instruction_tuning_collection): 103,440 train rows, native library/language QA plus translated/generated components; DOLCI, EU-Instruct | Stronger native instruction evidence than population would suggest. Keep training split; corpus contains MURI/Bactrian/OASST overlap and CC-BY-NC components |
| Ukrainian | [PleIAs/Ukrainian-CulturalHeritage-Books](https://huggingface.co/datasets/PleIAs/Ukrainian-CulturalHeritage-Books), Wikipedia, selected FinePDFs | DOLCI, EU-Instruct, EuroBlocks, Aya | Ready broad instruction backbone. Check Russian leakage, contemporary register versus historical books, and translated answer quality |
| Finnish | Wikipedia/Wikisource, selected FinePDFs and HPLT; curated native subsets before generic crawl | [LumiOpen/poro2-instruction-collection](https://huggingface.co/datasets/LumiOpen/poro2-instruction-collection): 1,424,671 total EN/FI rows, Finnish count not established here; DOLCI; [LumiOpen/AutoIF-FI](https://huggingface.co/datasets/LumiOpen/AutoIF-FI) candidate | Poro2 documents translated Tulu prompts, multiple candidate answers and selection, plus native assistant data. Do not assign the EN/FI total to Finnish or re-add included OASST/Avoin Avustaja |
| Romanian | Wikipedia, selected FinePDFs; [OpenLLM-Ro/ro_wiki](https://huggingface.co/datasets/OpenLLM-Ro/ro_wiki) as a potentially duplicate mirror | DOLCI, EU-Instruct; [OpenLLM-Ro/ro_sft_magpie_mt](https://huggingface.co/datasets/OpenLLM-Ro/ro_sft_magpie_mt), [OpenLLM-Ro/ro_sft_norobots](https://huggingface.co/datasets/OpenLLM-Ro/ro_sft_norobots), [OpenLLM-Ro/ro_dpo_ultrafeedback](https://huggingface.co/datasets/OpenLLM-Ro/ro_dpo_ultrafeedback) | Broad SFT/DPO supply; Magpie translated with GPT-4o mini, NoRobots with Systran. Translation fidelity and duplicated English originals constrain quality confidence |
| Greek | Common Corpus (card lists Greek above 10B tokens), Wikipedia, selected FinePDFs | DOLCI, EU-Instruct, Aya; [CausalLM/GPT-4-Self-Instruct-Greek](https://huggingface.co/datasets/CausalLM/GPT-4-Self-Instruct-Greek) candidate | Better instruction supply than EuroBlocks' small Greek subset suggests. Distinguish modern Greek from ancient texts and avoid the many Greek evaluation-only datasets |
| Hungarian | Wikipedia/Wikisource, selected FinePDFs, HPLT fallback | EuroBlocks (4,236 labelled rows), [saillab/alpaca-hungarian-cleaned](https://huggingface.co/datasets/saillab/alpaca-hungarian-cleaned), Aya | Reasonable native text; narrow/older translated instruction supply. Task and morphology review needed before expansion |
| Estonian | [tartuNLP/fineweb-2-et](https://huggingface.co/datasets/tartuNLP/fineweb-2-et) is a FineWeb mirror, not extra independent supply; [tartuNLP/finepdfs-et](https://huggingface.co/datasets/tartuNLP/finepdfs-et), Wikipedia, selected FinePDFs-Edu | [tartuNLP/magpie-gemma-3-12b-it-100k-et](https://huggingface.co/datasets/tartuNLP/magpie-gemma-3-12b-it-100k-et): 100,564 rows; [TalTechNLP/instructionSum](https://huggingface.co/datasets/TalTechNLP/instructionSum): 248,718 rows | Particularly viable small-language candidate. Magpie used Gemma 3 12B, light same-model filtering and GlotLID, not independent native review. Summarization combines native news and translated dialogues; isolate constituent evaluation splits |
| Bulgarian | Wikipedia/Wikisource, selected FinePDFs, HPLT fallback | [saillab/alpaca-bulgarian-cleaned](https://huggingface.co/datasets/saillab/alpaca-bulgarian-cleaned), small EuroBlocks subset | Text is not the bottleneck; general modern multi-turn instruction quality is. Bulgarian benchmark translations are not substitutes for training corpora |
| Slovak | Wikipedia/Wikisource and selected FinePDFs | [mbenco/slovak-sft](https://huggingface.co/datasets/mbenco/slovak-sft): 29,962 full training rows; EuroBlocks | Alpaca + Slovak QA mixture; smaller 1K/5K/10K/etc. files are prefixes, not additional data. Preserve validation split and check SkQuAD overlap |
| Lithuanian | Wikipedia/Wikisource, selected FinePDFs | [neurotechnology/lithuanian-qa-v1](https://huggingface.co/datasets/neurotechnology/lithuanian-qa-v1): 13,848 Wikipedia-derived QA pairs; Aya (916 train rows); [saillab/alpaca-lithuanian-cleaned](https://huggingface.co/datasets/saillab/alpaca-lithuanian-cleaned) fallback | Useful local grounding, limited broad conversational evidence. Prefer native-grounded generation over relying on just 14 EuroBlocks-labelled rows |
| Latvian | Wikipedia, selected FinePDFs | [matiss/P3-Latvian-Full](https://huggingface.co/datasets/matiss/P3-Latvian-Full), [matiss/P3-Latvian-translategemma-27b](https://huggingface.co/datasets/matiss/P3-Latvian-translategemma-27b), small EuroBlocks subset | Large templated-task potential, not equivalent to unique multi-turn chats. Audit translation method/version; repeated templates and explicit test/validation components require strict filtering |

### Southern And Smaller Languages

| Language | Text candidates | Instruction/preference candidates | Why this score; principal limitation |
| --- | --- | --- | --- |
| Turkish | [turkish-nlp-suite/BellaTurca](https://huggingface.co/datasets/turkish-nlp-suite/BellaTurca), especially documented academic/curated subsets; Wikipedia | [turkish-nlp-suite/InstrucTurca](https://huggingface.co/datasets/turkish-nlp-suite/InstrucTurca), Aya (4,046 train pairs), EuroBlocks | Strong reach, broad texts. InstrucTurca is translated using Snowflake Arctic with relatively light filtering. BellaTurca card says books were excluded for copyright reasons despite a legacy Kitaplar entry in metadata; do not include it by glob |
| Catalan | Wikipedia, selected FinePDFs, ALIA-related native seed sources | ALIA SFT: 87,011 Catalan rows, including local QA, instruction following and multi-turn | Strong local ecosystem and relevant task coverage; mixed reusable sources require dedup |
| Basque | Wikipedia, selected FinePDFs; [HiTZ/basqueparl](https://huggingface.co/datasets/HiTZ/basqueparl) parliamentary candidate | ALIA SFT: 59,359 Basque rows; Aya (939 train rows); [HiTZ/BasqueSumm](https://huggingface.co/datasets/HiTZ/BasqueSumm) only with proper held-out split protection | Good local instruction support despite small reach. BasqueSumm reference is title+subtitle, not an independently written summary; do not count it as premium abstractive supervision |
| Galician | Wikipedia, selected FinePDFs | ALIA SFT: 56,724 Galician rows; [proxectonos/galician-gec-corpora](https://huggingface.co/datasets/proxectonos/galician-gec-corpora) candidate | ALIA lifts instruction prospects. Separate Galician from Portuguese and protect GEC evaluation splits |
| Serbian | Wikipedia plus selected Cyrillic FinePDFs; verify Latin-script balance separately | [datatab/ultrafeedback_binarized_serbian](https://huggingface.co/datasets/datatab/ultrafeedback_binarized_serbian), [datatab/alpaca-cleaned-serbian-full](https://huggingface.co/datasets/datatab/alpaca-cleaned-serbian-full), Aya | Preference data exists, but translated answer rankings need revalidation. Script and Serbian/Croatian/Bosnian variant fidelity matter |
| Croatian | Wikipedia and selected FinePDFs | [administraktor/croatian-dataset-llmhr](https://huggingface.co/datasets/administraktor/croatian-dataset-llmhr): 45K train of 50K total, synthetic; small EuroBlocks subset | Modest usable candidate; not yet independently audited. Separate pilot/validation/test files and check repetitive templates |
| Slovenian | Wikipedia, selected FinePDFs, HPLT fallback | EuroBlocks (197 monolingual-labelled rows), train-only source-filtered Aya Collection where language support is verified | No substantial modern native broad-chat release verified in this scan. Expect bespoke generation and native review rather than claiming ready supply |
| Albanian | Wikipedia; selected als_Latn FinePDFs is specifically Tosk, not all dialects | Aya has 120 Tosk Albanian train pairs; [akadriu/albanian-news-instructions](https://huggingface.co/datasets/akadriu/albanian-news-instructions) candidate | Small verified native/SFT supply and dialect coverage gaps; publisher details need deeper inspection |
| Welsh | Wikipedia/Wikisource and selected FinePDFs | [locailabs/nemotron-chat-welsh](https://huggingface.co/datasets/locailabs/nemotron-chat-welsh) candidate, 42 EuroBlocks-labelled rows | Promising translated candidate, insufficient verified scale/quality evidence. Preserve Welsh orthography and avoid English-heavy contamination |
| Irish | Wikipedia/Wikisource; [ReliableAI/Irish-Text-Collection](https://huggingface.co/datasets/ReliableAI/Irish-Text-Collection) access candidate | Aya has 1,245 Irish train pairs | Human instruction seed exists, but text repo README returned 401 unauthenticated. Availability score is conservative; access investigation could improve it |
| Maltese | Wikipedia and selected FinePDFs (16,490 rows) | EuroBlocks has some en_mt translation-labelled supply, but no monolingual Maltese label in inspected statistics | Do not mistake bilingual sentence translation for broad Maltese instruction following; new generation/native review likely needed |

## Important Non-Additions

- Do not add FLORES, MMLU, ARC, HellaSwag, IFEval or other evaluation datasets
  merely because they are the most downloaded resources in a language. ALIA
  explicitly includes FLORES-dev; EuroBlocks includes MMLU/ARC-like synthetic
  subsets. Check lineage and intended held-out splits, not only dataset names.
- [openeurollm/oellm-eu-tooluse-v1](https://huggingface.co/datasets/openeurollm/oellm-eu-tooluse-v1)
  is currently **English-only**, despite its name. Its card describes Qwen3.5
  wrappers and reused Glaive/ToolACE/Hermes sources. It does not establish new
  multilingual tool-use coverage and must not bypass our Gemma-native parser.
- OpenEuroLLM also has Dutch, Polish and Swedish translated DOLCI SFT subsets
  (494,880 / 494,773 / 494,841 rows respectively). These may improve already
  covered languages but are not new-language additions in the ranking.
- Translation siblings and reused DOLCI/Tulu/Alpaca/OASST components can
  duplicate existing DFM content semantically even without exact string matches.
  Track original IDs, avoid multiplying repeats unknowingly, and select only
  the target-language increment.
- No raw OpenHermes dataset is proposed here. Existing project decisions to
  use only repaired/modernized versions remain unchanged.
