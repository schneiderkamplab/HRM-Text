---
type: Reference
title: Candidate And Upstream Catalog
description: Source-level bounded-choice applicability and provenance for the DFM8-13 review.
tags: [decision-datasets, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Candidate And Upstream Catalog

Part of [DFM8-13 review](middle-datasets.md). Review only; no new conversion or admission.

This appendix preserves all 131 literal downloader entries, even when inherited,
raw, grounding-only, helper-model training or deferred. It is a candidate/source
catalog **not 131 middle-phase additions**. Evidence is the exact keyed
[HFDataset declarations](../../../scripts/download_training_datasets.py).
Group tags and notes establish intended role, not proof of active sampling.
Apply the phase-specific tables first for membership and replacements.

Each row below receives a conservative disposition: the note remains authoritative
for source-specific scope. "C/unknown" means original bounded labels have not
been established by this inventory, not that every row needs generation.

| Local name | Exact HF ID | Declared groups | Applicability / intended role |
|---|---|---|---|
| `sapient_cleaned` | `sapientinc/HRM-Text-data-io-cleaned-20260515` | sapient | C/unknown: task-specific response judgment; inspect original labels and provenance. Cleaned Sapient HRM-Text data_io corpus. |
| `danish_dynaword` | `danish-foundation-models/danish-dynaword` | danish, danish_continuation, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Raw Danish documents; convert to continuation rows. |
| `dfm10_elrc_medical` | `qanastek/ELRC-Medical-V2` | dfm10, danish, english, medical, translation | C translation validity; parallel reference does not validate negatives. CC-BY-4.0 English-Danish medical/public-health parallel text. DFM10 filters document artefacts and converts both directions. |
| `dfm10_emea_medical` | `qanastek/EMEA-V3` | dfm10, danish, english, medical, translation | C translation validity; parallel reference does not validate negatives. CC-BY-4.0 OPUS/EMA Danish-English medical parallel text. DFM10 converts both directions and deduplicates against ELRC. |
| `dfm10_ecdc_medical` | `qanastek/ECDC` | dfm10, danish, english, medical, translation | C translation validity; parallel reference does not validate negatives. EU/ECDC professional public-health translation memory. Its terms grant commercial and non-commercial reuse with notice retention. |
| `dfm10_nhs_synthetic_clinical_notes` | `NHSEDataScience/synthetic_clinical_notes` | dfm10, english, medical, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. MIT-licensed fully synthetic notes. DFM10 uses grounded note classification and exact span-reconstruction supervision only. |
| `alexandra_nordjylland_news` | `alexandrainst/nordjylland-news-summarization` | dfm10, danish, instruction, summarization | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM10 uses only the original 75,219-row train file; the synthetic 63,855-row file is already inherited through Oliver Kinch. |
| `alexandra_scandi_qa` | `alexandrainst/scandi-qa` | dfm10, danish, instruction, qa | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM10 uses only Danish train; validation and test remain held out. |
| `alexandra_multi_zebra_logic` | `alexandrainst/multi-zebra-logic` | dfm10, danish, english, instruction, reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM10 uses selected Danish and English train configs only; validation and test remain held out. |
| `alexandra_dane` | `alexandrainst/dane` | dfm10, danish, instruction, ner | C/unknown: task-specific response judgment; inspect original labels and provenance. The DFM10 converter downloads the upstream ddt.zip referenced by the dataset loader and reads ddt.train.conllu only. |
| `alexandra_dacoref` | `alexandrainst/dacoref` | dfm10, danish, instruction, coreference | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM10 uses train only; validation and test remain held out. |
| `zai_deepdive` | `zai-org/DeepDive` | dfm10, english, instruction, agentic, search | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM10 uses only the 858 successful SFT search trajectories. QA/RL splits are excluded; trajectories require native-tool conversion. |
| `dfm10_synthetic_values_model_charter` | `danish-foundation-models/synthetic-values-model-charter` | dfm10, english, instruction, alignment, preference | A only original pair/vote labels; C chosen-only or unlabeled chats. DFM10 includes both nominal SFT splits; both DPO splits remain in a separate preference export. Based on model-charter commit e60e41aad338c6261cc21f926847b3ab77ff4226. |
| `dfm10_synthetic_values_model_charter_da` | `schneiderkamplab/dfm10-synthetic-values-model-charter-da` | dfm10, danish, instruction, alignment, preference | A only original pair/vote labels; C chosen-only or unlabeled chats. Audited Danish SFT/DPO adaptation; DFM10 SFT uses accepted chosen responses at repeat 10. |
| `dfm10_bornholmsk_parallel` | `strombergnlp/bornholmsk_parallel` | dfm10, danish, translation, dialect | C translation validity; parallel reference does not validate negatives. DFM10 includes train, validation, and test in both translation directions. The converter fetches the six raw files from the immutable upstream revision pinned by the dataset loader. |
| `ra_diem_htr` | `RA-Data-Science/DiEm_HTR` | dfm10, danish, historical, modernization | C/unknown: task-specific response judgment; inspect original labels and provenance. Historical Danish ALTO transcriptions. DFM10 admits only independently audited Gemma 4 31B modernization targets, never the page images as text SFT. |
| `dfm10_danish_book_ads` | `chcaa/danish-book-ads` | dfm10, danish, historical, bibliographic | C/unknown: task-specific response judgment; inspect original labels and provenance. Historical book advertisements. DFM10 admits only grounded, checked extraction/classification targets after overlap and quality auditing. |
| `dfm10_croco_munin_da_50k_candidate` | `danish-foundation-models/croco-munin-apertus-8b-da-50k` | audit_candidate, danish, instruction, alignment, preference_candidate | C/unknown: task-specific response judgment; inspect original labels and provenance. Excluded from DFM10 after overlap audit: only seven prompts were absent from the active croco-munin-apertus-8b-da-simpo-full-50k. |
| `dfm10_danish_personas_seed` | `oliverkinch/danish-personas` | dfm10, danish, synthetic_seed | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Generation seed only; persona rows are never tokenized directly. |
| `dfm10_domsdatabasen` | `alexandrainst/domsdatabasen` | dfm10, danish, legal, grounding_source | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Grounding source only. DFM10 uses non-empty pseudonymized text for generated and audited legal conversations; judgments are never admitted as raw continuation data. |
| `common_pile_wikimedia_filtered` | `common-pile/wikimedia_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered Wikimedia; CC-BY-SA metadata in rows. |
| `common_pile_wikiteam_filtered` | `common-pile/wikiteam_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered WikiTeam dumps; review row licenses during attribution. |
| `common_pile_stackexchange_filtered` | `common-pile/stackexchange_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered StackExchange; CC-BY-SA rows. |
| `common_pile_pubmed_filtered` | `common-pile/pubmed_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered PubMed/PubMed Central open-license scientific text. |
| `common_pile_arxiv_abstracts_filtered` | `common-pile/arxiv_abstracts_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered arXiv abstracts. |
| `common_pile_arxiv_papers_filtered` | `common-pile/arxiv_papers_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered arXiv papers; use capped raw-objective sampling. |
| `common_pile_usgpo_filtered` | `common-pile/usgpo_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered US Government Publishing Office public-domain text. |
| `common_pile_regulations_filtered` | `common-pile/regulations_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered regulations.gov public-domain text. |
| `common_pile_uspto_filtered` | `common-pile/uspto_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered USPTO patent text. |
| `common_pile_project_gutenberg_filtered` | `common-pile/project_gutenberg_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Filtered Project Gutenberg public-domain books. |
| `common_pile_public_domain_review_filtered` | `common-pile/public_domain_review_filtered` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Small public-domain review source. |
| `common_pile_library_of_congress` | `common-pile/library_of_congress` | common_pile, english_raw, raw | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Library of Congress public-domain/open metadata text. |
| `govreport_summarization` | `ccdv/govreport-summarization` | english, summarization, dfm4 | C/unknown: task-specific response judgment; inspect original labels and provenance. Long-document government report summarization; train split only. |
| `wiki_cat_sum` | `GEM/wiki_cat_sum` | english, summarization, wikipedia, dfm4 | C/unknown: task-specific response judgment; inspect original labels and provenance. Wikipedia/WikiSum-derived multi-document summarization; train splits only. |
| `laion_scientific_summaries` | `laion/Scientific-Summaries` | english, summarization, science, dfm4 | C/unknown: task-specific response judgment; inspect original labels and provenance. CC-BY-4.0 LLM-generated scientific summaries; arXiv config only by default. |
| `laerebogen_with_followups` | `danish-foundation-models/laerebogen` | danish, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated Danish multi-turn instruction data. |
| `synquid_wiki_instruct_da` | `synquid/wiki-instruct-da` | danish, instruction, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated Danish wiki instruction data. |
| `synquid_danish_verifiable_reasoning` | `synquid/danish-verifiable-reasoning` | danish, reasoning, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `synquid_translation_100k` | `synquid/translation-100k` | danish, translation, synquid | C translation validity; parallel reference does not validate negatives. unknown |
| `synquid_ifbench_train` | `synquid/ifbench-train` | danish, instruction, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `oliverkinch_instruct_bt` | `oliverkinch/instruct-bt` | danish, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated; requires accepted access. |
| `oliverkinch_multi_wiki_qa_high_quality` | `oliverkinch/multi-wiki-qa-high-quality-subset` | danish, qa, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Danish Wikipedia-derived extractive QA subset; CC-BY-4.0. |
| `oliverkinch_eur_lex_sum_instruct` | `oliverkinch/eur-lex-sum-instruct` | danish, instruction, summarization, legal | C/unknown: task-specific response judgment; inspect original labels and provenance. Danish EUR-Lex summarization instruction data derived from EU legal text. |
| `oliverkinch_machine_translation_da_en` | `oliverkinch/machine-translation-da-en` | danish, translation | C translation validity; parallel reference does not validate negatives. Danish-English OPUS-derived translation data; cap during sampling. |
| `opus` | `schneiderkamplab/opus-da-en-permissive` | danish, translation, dfm_rebuild | C translation validity; parallel reference does not validate negatives. Processed Danish-English OPUS permissive/public-domain subset used by DFM mixes. |
| `dfm11_koolbardi_da` | `schneiderkamplab/dfm11-koolbardi-da` | dfm11, danish, instruction, multi_turn, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. Controlled Danish Koolbardi conversations; assistant-turn audited and admitted at repeat 1. |
| `dfm11_koolbardi_en` | `schneiderkamplab/dfm11-koolbardi-en` | dfm11, english, instruction, multi_turn, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. Controlled English Koolbardi conversations; assistant-turn audited and admitted at repeat 1. |
| `dfm11_fineinstructions_en` | `schneiderkamplab/dfm11-fineinstructions-en` | dfm11, english, instruction, multi_turn, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. Complete grounded English pair/chat release. DFM11 trains on all 316,022 controlled chats plus a deterministic source-balanced 100,000-chat legacy cap, each at repeat 1; pair rows are not separately admitted. |
| `dfm11_fineinstructions_da` | `schneiderkamplab/dfm11-fineinstructions-da` | dfm11, danish, instruction, multi_turn, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. Complete grounded Danish pair/chat release. DFM11 trains on all 503,740 independently audited chats at repeat 1; matching pair rows are published for provenance but are not separately admitted. |
| `dfm11_danish_query_templatizer_training` | `schneiderkamplab/dfm11-danish-query-templatizer-training` | dfm11_artifact, helper_training, danish, synthetic | D helper-model artifacts: not direct assistant/decision training. Published supervision for the Danish FineInstructions query templatizer; not a DFM11 language-model training source. |
| `dfm11_danish_template_instantiator_training` | `schneiderkamplab/dfm11-danish-template-instantiator-training` | dfm11_artifact, helper_training, danish, synthetic | D helper-model artifacts: not direct assistant/decision training. Published independently accepted supervision for the Danish FineInstructions template instantiator; not a DFM11 language-model training source. |
| `oliverkinch_machine_translation_da_uk` | `oliverkinch/machine-translation-da-uk` | danish, translation | C translation validity; parallel reference does not validate negatives. Danish-Ukrainian OPUS-derived translation data; cap during sampling. |
| `oliverkinch_machine_translation_da_ar` | `oliverkinch/machine-translation-da-ar` | danish, translation | C translation validity; parallel reference does not validate negatives. Danish-Arabic OPUS-derived translation data; cap during sampling. |
| `oliverkinch_danmarks_statistik_bt` | `oliverkinch/danmarks-statistik-bt` | danish, instruction, backtranslation | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation from Danmarks Statistik CC-BY-4.0 publications. |
| `oliverkinch_danmarks_statistik` | `oliverkinch/danmarks-statistik` | danish, grounding_source, dfm10 | D raw/seed/grounding: no decision target; separate transformation/adjudication required. Source metadata and passages used with live DST URLs to recover rejected BT rows. |
| `oliverkinch_tidsskrift_dk_bt` | `oliverkinch/tidsskrift-dk-bt` | danish, instruction, backtranslation | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation from tidsskrift.dk CC-BY academic articles. |
| `oliverkinch_doab_da_bt` | `oliverkinch/doab-da-bt` | danish, instruction, backtranslation | C/unknown: task-specific response judgment; inspect original labels and provenance. Small backtranslation set from DOAB Danish open-access material. |
| `oliverkinch_danish_university_portals_bt` | `oliverkinch/danish-university-portals-bt` | danish, instruction, backtranslation | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation from Danish university portal publications; source card says CC-BY-only material. |
| `oliverkinch_danish_university_portals` | `oliverkinch/danish-university-portals` | dfm10_repair_support, danish, source_documents | C/unknown: task-specific response judgment; inspect original labels and provenance. Authoritative CC-BY full documents used to recover and audit truncated university-portals BT targets. |
| `oliverkinch_eur_lex_bt` | `oliverkinch/eur-lex-bt` | danish, instruction, backtranslation, legal | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation from EUR-Lex Danish legal text. |
| `oliverkinch_dynaword_bt` | `oliverkinch/dynaword-bt` | danish, instruction, backtranslation | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation from Danish DynaWord; cap/review by source subset during sampling. |
| `oliverkinch_dst_table_prompts_bt` | `oliverkinch/dst-table-prompts-bt` | danish, instruction, backtranslation, tables | C/unknown: task-specific response judgment; inspect original labels and provenance. Backtranslation/data-to-text from Danmarks Statistik tables; CC-BY-4.0. |
| `synquid_mt_da_deepseek` | `synquid/mt-da-deepseek` | danish, instruction, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated; schema should be inspected after access is granted. |
| `synquid_danish_wildchat_100k` | `synquid/danish-wildchat-100k` | danish, prompts, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated prompt-only source; not directly trainable without responses. |
| `synquid_wildchat_100k_qwen_messages` | `synquid/wildchat-100k-qwen-messages` | danish, instruction, synquid | C/unknown: task-specific response judgment; inspect original labels and provenance. Gated generated responses for WildChat prompts in messages format; include with a tight cap. |
| `dfm_dyna_instruct` | `danish-foundation-models/dfm-dyna-instruct` | dfm7, danish, instruction, code_agentic, tool_use | B schema validity; C semantic action/argument correctness. DFM7 expanded instruction collection; de-duplicate against DFM6 constituents. |
| `xlam_function_calling_60k` | `Salesforce/xlam-function-calling-60k` | dfm7, tool_use, function_calling | B schema validity; C semantic action/argument correctness. APIGen/xLAM function-calling SFT; convert to native Gemma tools when access is available. |
| `glaive_function_calling_v2` | `glaiveai/glaive-function-calling-v2` | dfm7, tool_use, function_calling | B schema validity; C semantic action/argument correctness. Text-format function-calling SFT; parse system/chat strings into native Gemma tools. |
| `toolace` | `Team-ACE/ToolACE` | dfm7, tool_use, function_calling | B schema validity; C semantic action/argument correctness. ToolACE function-calling conversations; parse bracketed tool-call strings into native Gemma tools. |
| `danish_wildchat4_8m` | `danish-foundation-models/danish-wildchat4.8M` | dfm7, danish, instruction, chat | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM7 expanded Danish WildChat replacement for the 100k messages slice. |
| `ai_arenaen_conversations` | `danish-foundation-models/ai-arenaen-conversations` | dfm7, danish, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. Danish AI-Arenaen conversation/preference data. |
| `ai_arenaen` | `danish-foundation-models/ai-arenaen` | dfm13, danish, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. DFM13: keep A for a_better, B for b_better, both for both_good; selected-turn supervision only. |
| `arena_human_preference_140k` | `lmarena-ai/arena-human-preference-140k` | dfm13, multilingual, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. DFM13 winning-side SFT; exclude ties/both_bad; prepare_dfm13_arena.py pins revisions and deduplicates releases. |
| `arena_human_preference_100k` | `lmarena-ai/arena-human-preference-100k` | dfm13, multilingual, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. DFM13 winning-side SFT; prompts CC-BY-4.0, outputs governed by provider terms. |
| `arena_human_preference_55k` | `lmarena-ai/arena-human-preference-55k` | dfm13, multilingual, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. DFM13 winning-side SFT; JSON turn lists; merged tie/both-bad labels excluded. |
| `ai_arena_udtraek` | `danish-foundation-models/ai_arena_udtraek` | dfm7, danish, dialogue, alignment | A only original pair/vote labels; C chosen-only or unlabeled chats. Danish AI Arena extract. |
| `kaenguruen` | `danish-foundation-models/kaenguruen` | dfm7, danish, math_reasoning | B independently checkable answer; C otherwise. DFM7 decision: include for training; convert to explicit Danish MCQ prompts before tokenization. |
| `oliverkinch_danish_qa` | `oliverkinch/danish-qa` | dfm7, danish, qa, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Danish factual QA. |
| `oliverkinch_danish_summarization` | `oliverkinch/danish-summarization` | dfm7, danish, summarization | C/unknown: task-specific response judgment; inspect original labels and provenance. Danish summarization configs, including EUR-Lex and Nordjylland. |
| `oliverkinch_da_instruct_dynaword` | `oliverkinch/da-instruct-dynaword` | dfm7, danish, instruction, dynaword | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM7 breadth source: include alongside HQ/contemporary variants. |
| `oliverkinch_da_instruct_dynaword_hq` | `oliverkinch/da-instruct-dynaword-hq` | dfm7, danish, instruction, dynaword | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM7 breadth source. |
| `oliverkinch_da_instruct_dynaword_contemporary` | `oliverkinch/da-instruct-dynaword-contemporary` | dfm7, danish, instruction, dynaword | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM7 breadth source. |
| `oliverkinch_da_instruct_dynaword_contemporary_hq` | `oliverkinch/da-instruct-dynaword-contemporary-hq` | dfm7, danish, instruction, dynaword | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM7 breadth source. |
| `oliverkinch_autodata_da_sft` | `oliverkinch/autodata-da-sft` | dfm7, danish, instruction, synthetic | C/unknown: task-specific response judgment; inspect original labels and provenance. Small Danish synthetic SFT/chat source. |
| `giannor_dala_tv2r_it` | `giannor/dala_tv2r_it` | dfm8, danish, gec, linguistic_acceptability | A acceptability labels; B/C correction with corruption-validity filters. DFM8 decision: fully include TV2R instruction-formatted DaLA acceptability rows. |
| `giannor_gec_dala_tv2r_it` | `giannor/gec_dala_tv2r_it` | dfm8, danish, gec, correction | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM8 decision: fully include TV2R instruction-formatted GEC-DaLA rows. |
| `dala_english_common_pile` | `schneiderkamplab/dala-english-common-pile` | dfm12, english, instruction, linguistic_acceptability, correction | A acceptability labels; B/C correction with corruption-validity filters. DFM12: include both training configurations; render messages only with Gemma4. Preserve metadata separately; known source-label noise. |
| `dala_dutch_dynaword` | `schneiderkamplab/dala-dutch-dynaword` | dfm12, dutch, instruction, linguistic_acceptability, correction | A acceptability labels; B/C correction with corruption-validity filters. DFM12: include both training configurations; render messages only with Gemma4. Preserve metadata separately; exclude validation/test. |
| `kobprof_skolegpt_instruct` | `kobprof/skolegpt-instruct` | dfm8, danish, education, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. DFM8 Danish school/education instruction source; convert system_prompt/question/response rows to Gemma4 chat. |
| `posttrain_coedit` | `grammarly/coedit` | posttrain_transform, instruction, editing | C/unknown: task-specific response judgment; inspect original labels and provenance. Instruction-style grammar/editing/rewrite data; convert src/tgt rows. |
| `posttrain_natural_instructions` | `Muennighoff/natural-instructions` | posttrain_transform, instruction, editing | C/unknown: task-specific response judgment; inspect original labels and provenance. Super-NaturalInstructions preprocessing; filter to transformation-style train tasks before conversion. |
| `posttrain_asset` | `facebook/asset` | posttrain_transform, simplification, editing | C/unknown: task-specific response judgment; inspect original labels and provenance. ASSET simplification validation/test rows; use as synthetic seed material rather than direct training rows. |
| `nemotron_terminal_corpus` | `nvidia/Nemotron-Terminal-Corpus` | nemotron, terminal, code_agentic | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `nemotron_instruction_reasoning_off` | `nvidia/Nemotron-SFT-Instruction-Following-Chat-v2` | nemotron, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `nemotron_agentic` | `nvidia/Nemotron-SFT-Agentic-v2` | nemotron, agentic, code_agentic | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `nemotron_swe` | `nvidia/Nemotron-SFT-SWE-v2` | nemotron, swe, code_agentic | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `nemotron_multilingual` | `nvidia/Nemotron-SFT-Multilingual-v1` | nemotron, multilingual | C/unknown: task-specific response judgment; inspect original labels and provenance. No Danish; useful for multilingual STEM/code transfer. |
| `dolci_instruct_sft` | `allenai/Dolci-Instruct-SFT` | dolci, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Main Dolci Instruct SFT mixture. |
| `dolci_instruct_sft_no_tools` | `allenai/Dolci-Instruct-SFT-No-Tools` | dolci, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Dolci Instruct SFT subset without tool-use data. |
| `dolci_instruct_sft_tool_use` | `allenai/Dolci-Instruct-SFT-Tool-Use` | dolci, instruction, agentic | C/unknown: task-specific response judgment; inspect original labels and provenance. Dolci tool-use SFT data. |
| `dolci_instruct_sft_tool_use_sa` | `allenai/Dolci-Instruct-SFT-Tool-Use-SA` | dolci, instruction, agentic | C/unknown: task-specific response judgment; inspect original labels and provenance. Small Dolci tool-use single-agent subset. |
| `allenai_tulu_3_sft_mixture` | `allenai/tulu-3-sft-mixture` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. General chat/instruction mixture; ODC-By. |
| `allenai_tulu_v2_sft_mixture` | `allenai/tulu-v2-sft-mixture` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_tulu_v2_sft_long_mixture` | `allenai/tulu-v2-sft-long-mixture` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. Long-context Tulu v2 JSONL mixture. |
| `allenai_tulu_3_personas_math` | `allenai/tulu-3-sft-personas-math` | allenai, math_reasoning, instruction | B independently checkable answer; C otherwise. unknown |
| `allenai_tulu_3_personas_algebra` | `allenai/tulu-3-sft-personas-algebra` | allenai, math_reasoning, instruction | B independently checkable answer; C otherwise. unknown |
| `allenai_tulu_3_personas_code` | `allenai/tulu-3-sft-personas-code` | allenai, code_agentic, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_tulu_3_personas_if` | `allenai/tulu-3-sft-personas-instruction-following` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_sciriff_train_mix` | `allenai/SciRIFF-train-mix` | allenai, instruction, reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. Scientific instruction-following data. |
| `allenai_if_sft_verified` | `allenai/IF_sft_data_verified` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_if_multi_constraints_upto5` | `allenai/IF_multi_constraints_upto5` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_verifiable_reasoning_gpt41` | `allenai/verifiable-reasoning-filtered-gpt-41` | allenai, reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_verifiable_reasoning_o4mini` | `allenai/verifiable-reasoning-filtered-o4-mini` | allenai, reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_code_meta_reasoning` | `allenai/code-meta-reasoning-filtered` | allenai, code_agentic, reasoning, dfm10 | C/unknown: task-specific response judgment; inspect original labels and provenance. Structured source used by the DFM10 repair; retains prompt family, question, generation prompt, and response boundaries. |
| `allenai_open_math_2_50k_r1` | `allenai/open_math_2_50k_r1-original` | allenai, math_reasoning | B independently checkable answer; C otherwise. unknown |
| `allenai_rlvr_gsm` | `allenai/RLVR-GSM` | allenai, math_reasoning | B independently checkable answer; C otherwise. unknown |
| `allenai_rlvr_math` | `allenai/RLVR-MATH` | allenai, math_reasoning | B independently checkable answer; C otherwise. unknown |
| `allenai_rlvr_ifeval` | `allenai/RLVR-IFeval` | allenai, instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `allenai_big_reasoning_traces` | `allenai/big-reasoning-traces` | allenai, reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. Large reasoning traces; cap during sampling. |
| `openmathinstruct2` | `nvidia/OpenMathInstruct-2` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `numinamath_1_5` | `AI-MO/NuminaMath-1.5` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `openthoughts2_1m` | `open-thoughts/OpenThoughts2-1M` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `webinstruct_verified` | `TIGER-Lab/WebInstruct-verified` | instruction, math_reasoning | B independently checkable answer; C otherwise. unknown |
| `omni_math` | `KbsdJames/Omni-MATH` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `gsm8k` | `openai/gsm8k` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `hendrycks_math` | `EleutherAI/hendrycks_math` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `theoremqa` | `TIGER-Lab/TheoremQA` | math_reasoning | B independently checkable answer; C otherwise. unknown |
| `no_robots` | `HuggingFaceH4/no_robots` | instruction | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `natural_reasoning` | `facebook/natural_reasoning` | reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `principia_collection` | `facebook/principia-collection` | reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |
| `textbook_reasoning` | `MegaScience/TextbookReasoning` | reasoning | C/unknown: task-specific response judgment; inspect original labels and provenance. unknown |

## DFM12 Upstream Catalog

Evidence: [pinned/source-config catalog](../../../dfm12/config.yaml), keyed by
source name. Catalog review notes may predate later accepted derivative exports;
these rows describe upstream scope, not current package admission.

| Source key | Exact HF ID | Kind / proposed decision | Review boundary |
|---|---|---|---|
| `dala-en` | `schneiderkamplab/dala-english-common-pile` | A acceptability; B/C correction | Selected file/config only; preserve train split and revision |
| `dala-nl` | `schneiderkamplab/dala-dutch-dynaword` | A acceptability; B/C correction | Selected file/config only; preserve train split and revision |
| `ultrachat-nl` | `BramVanroy/ultrachat_200k_dutch` | C response suitability; constituent labels unknown | Selected file/config only; preserve train split and revision |
| `dolci-nl` | `openeurollm/Dolci-Instruct-SFT-translated` | C response suitability; constituent labels unknown | Selected file/config only; preserve train split and revision |
| `dolci-pl` | `openeurollm/Dolci-Instruct-SFT-translated` | C response suitability; constituent labels unknown | Selected file/config only; preserve train split and revision |
| `dolci-sv` | `openeurollm/Dolci-Instruct-SFT-translated` | C response suitability; constituent labels unknown | Selected file/config only; preserve train split and revision |
| `scandi-instruct` | `V4ldeLund/scandi-translated-instruct` | C response suitability; constituent labels unknown | owner inclusion approved 2026-09-25; use scoped Scandi admission with provenance, deduplication and quality audit, including generic Norwegian where lineage establishes it |
| `norquad-wikipedia` | `danish-foundation-models/norwegian-dyna-instruct` | C response suitability; constituent labels unknown | owner included full Wikipedia training subset 2026-09-25; retain held-out passage-overlap annotations and quality audit |
| `fleurs-alpaca-en-no` | `danish-foundation-models/norwegian-dyna-instruct` | C response suitability; constituent labels unknown | owner included 2026-09-25 despite FLORES evaluation-text origin; retain lineage and quality audit |
| `dyna-instruct-no` | `danish-foundation-models/norwegian-dyna-instruct` | C response suitability; constituent labels unknown | source quality and NB/NN language labels; NorQuAD and FLEURS now have separate owner-approved component routes |
| `dyna-instruct-is` | `danish-foundation-models/icelandic-dyna-instruct` | C response suitability; constituent labels unknown | constituent currently has unknown license on source card |
| `dyna-instruct-fo` | `danish-foundation-models/faroese-dyna-instruct` | C response suitability; constituent labels unknown | constituent currently has unknown license on source card |
| `pllumic` | `pelcra/PLLuMIC` | C response suitability; constituent labels unknown | gated access, inspect schema and identity answers |
| `pllumic-syn` | `pelcra/PLLuMIC-syn-ext` | C response suitability; constituent labels unknown | gated access and overlap with PLLuMIC |
| `pllum-align` | `NASK-PIB/PLLuM-Align` | A upstream rankings/ratings; C chosen-only derivative | remove conflicting model identity and deduplicate chosen conversations |
| `dyna-instruct-da-increments` | `danish-foundation-models/dfm-dyna-instruct` | C response suitability; constituent labels unknown | require inherited content fingerprint index; multilingual and English subsets must not be labelled Danish |
| `dynaword-nl` | `danish-foundation-models/dutch-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents with documented rights |
| `dynaword-no` | `danish-foundation-models/norwegian-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents; require explicit NB or NN labels |
| `dynaword-sv` | `danish-foundation-models/swedish-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents; avoid uncorrected OCR |
| `dynaword-is` | `danish-foundation-models/icelandic-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents with documented rights |
| `dynaword-fo` | `danish-foundation-models/faroese-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents; allow corpus exhaustion |
| `dynaword-pl` | `SlayerLab/polish-dynaword` | D raw; separately derived B/C transformations | select high-quality constituents with documented rights |

## Explicit DFM13 Deferrals

Evidence: [jjzha catalog](../../../config/dfm13_jjzha_sources.json) and
[Baltic catalog](../../../config/dfm13_baltic_sources.json). D here is an admission
hold, not necessarily intrinsic unsuitability. Do not promote MCQ or labelled
sources out of an evaluation/privacy/rights hold.

| Exact HF ID | Applicability | Recorded reason |
|---|---|---|
| `jjzha/skillskape` | D deferred/excluded | Relevant skill matching, but no license declared in source card; resolve before admission. |
| `jjzha/sayfullina` | D deferred/excluded | Unknown license; narrow soft-skill task already covered by selected sources. |
| `jjzha/gnehm` | D deferred/excluded | CC-BY-NC-SA; not a default public-training addition. |
| `jjzha/fijo` | D deferred/excluded | CC-BY-NC-SA; not a default public-training addition. |
| `jjzha/jobstack` | D deferred/excluded | De-identification labels on original personal entities; needs dedicated privacy review/converter; GPL card. |
| `jjzha/sefl` | D deferred/excluded | Intentionally incorrect student outputs; requires teacher-feedback-only conversion and quality audit, not prompt/completion SFT. |
| `jjzha/fs1-2708` | D deferred/excluded | Observed WebQTest ID, synthetic reasoning and embedded Qwen identity/template; no source card/license or safe train partition. |
| `jjzha/rt-2708` | D deferred/excluded | No source card/license; embedded Qwen identity/template, provenance and benchmark partition unresolved. |
| `jjzha/fs1-benchmark-2708` | D deferred/excluded | Explicit benchmark test data; excluded from training. |
| `jjzha/danish-citizen-global-exams` | D deferred/excluded | Repackages Danish citizenship exams used by our EuroEval knowledge benchmark; no safe training partition established. |
| `jjzha/belgian-entrance-exam-physician` | D deferred/excluded | Train split separates INCLUDE benchmark, but license explicitly unknown; defer pending permission. |
| `jjzha/dutch-central-exam-mcq-multimodal-subset` | D deferred/excluded | Images required and overlaps exam benchmark; do not strip images to create text-only supervision. |
| `jjzha/flemish_multimodal_exams_physician` | D deferred/excluded | Images required and overlaps exam benchmark; no text-only conversion. |
| `saillab/alpaca-lithuanian-cleaned` | D deferred/excluded | CC-BY-NC, not selected |
| `saillab/alpaca-latvian-cleaned` | D deferred/excluded | CC-BY-NC, not selected |
| `additional_OPUS_pairs` | D deferred/excluded | Preparation now active in translations and institutional-translations; remaining unreviewed releases stay excluded. |

## Baltic Upstream Sources

| Exact source / HF ID | Proposed decision | Boundary |
|---|---|---|
| `baltic_lt_qa` / `neurotechnology/lithuanian-qa-v1` | C evidence/response or summary judgment | Inspect later addition-registry disposition; raw-source listing is not accepted export |
| `baltic_lv_qa` / `martinsu/latvian-wikipedia-qa-gemma3` | C evidence/response or summary judgment | Inspect later addition-registry disposition; raw-source listing is not accepted export |
| `baltic_lt_aya` / `CohereLabs/aya_dataset` | C evidence/response or summary judgment | Inspect later addition-registry disposition; raw-source listing is not accepted export |
| `baltic_lt_summary` / `VytautoDidziojoUniversitetas/LT_Summarisation_Corpus` | C evidence/response or summary judgment | custom_terms_and_medical_privacy_review |
| `baltic_lt_finepdfs` / `HuggingFaceFW/finepdfs-edu` | D raw; B/C only separately admitted transforms | document_rights_ocr_language_screening |
| `baltic_lv_finepdfs` / `HuggingFaceFW/finepdfs-edu` | D raw; B/C only separately admitted transforms | document_rights_ocr_language_screening |
| `baltic_lt_blkt` / `VSSA-SDSA/LT_AI_BLKT` | D raw; B/C only separately admitted transforms | custom_terms_and_source_stratification |

`matiss/P3-Latvian-translategemma-27b`: D source-fidelity hold; intrinsic A on
recoverable original classification/MCQ tasks, C on open generation. Both licence
slices are individually retained in the DFM13 addition table. ParlaMint LT v2.1
and LV v5.0 are CLARIN/non-HF origins, not missing HF IDs: B/C transformations
only, with exact upstream URLs preserved in that table. OPUS corpora are
non-HF source archives; released pair-package IDs are fully enumerated in the
DFM12/13 tables. Pair direction duplicates must stay in the same split.
