---
type: Dataset Inventory
title: Early DFM Non-Sapient Source Families
description: Exhaustive non-Sapient category names across available DFM1-5 and DFM7 analytics.
tags: [data, decision-datasets, inventory]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Early DFM Non-Sapient Source Families

See [early datasets](early-datasets.md), [A/B/C/D rubric](../decision-datasets.md#common-assessment-scale),
and [recipes](conversion-recipes.md). This table exhausts category prefixes in
Task Coverage Stats of `data/show_analytics_{dfm,dfm2,dfm3,dfm4,dfm5,dfm7}.md`,
excluding original Sapient families documented in the companion attachments.
Versions mean appearance in analytics, including zero exposure: NOT proof of sampling.
DFM6 has no matching analytics file here; consult its manifests and the shared ledger.
Paths: the exact task filenames are in those analytics; downloadable source IDs
are from `scripts/download_training_datasets.py`. Missing IDs are local derived
families, not invented HF repositories. Upstream commits are not pinned by these
manifest entries. Published derivative IDs additionally follow `docs/dfm8-datasets.md`;
this identifies the published lineage, not byte/revision equality with earlier local exports.
Version suffixes in repository IDs are preserved verbatim.

Routes are candidate family-level assessments; see overview for bounded targets.
Excluded/zero-cap source presence never overrides eligibility.

| Exact category | Observed DFM analytics | Upstream ID or local origin | Candidate route |
|---|---|---|---|
| `ai_arena_udtraek` | 7 | `danish-foundation-models/ai_arena_udtraek` | C/D-mixed |
| `allenai_big_reasoning_traces` | 1,2,3,4,5,7 | `allenai/big-reasoning-traces` | C-answer / B-check |
| `allenai_if_sft_verified` | 1,2,3,4,5,7 | `allenai/IF_sft_data_verified` | B-constraint subset / C remainder |
| `allenai_open_math_2_50k_r1` | 1,2,3,4,5,7 | `allenai/open_math_2_50k_r1-original` | C-answer / B-check |
| `allenai_rlvr_gsm` | 7 | `allenai/RLVR-GSM` | C-answer / B-check |
| `allenai_rlvr_math` | 7 | `allenai/RLVR-MATH` | C-answer / B-check |
| `allenai_sciriff_train_mix` | 1,2,3,4,5,7 | `allenai/SciRIFF-train-mix` | C/D-mixed |
| `allenai_tulu_3_personas_algebra` | 1,2,3,4,5,7 | `allenai/tulu-3-sft-personas-algebra` | C/D-mixed |
| `allenai_tulu_3_personas_code` | 1,2,3,4,5,7 | `allenai/tulu-3-sft-personas-code` | C/D-mixed |
| `allenai_tulu_3_personas_if` | 1,2,3,4,5,7 | `allenai/tulu-3-sft-personas-instruction-following` | B-constraint subset / C remainder |
| `allenai_tulu_3_personas_math` | 1,2,3,4,5,7 | `allenai/tulu-3-sft-personas-math` | C-answer / B-check |
| `allenai_tulu_3_sft_mixture` | 1,2,3,4,5,7 | `allenai/tulu-3-sft-mixture` | C/D-mixed |
| `allenai_tulu_v2_sft_long_mixture` | 1,2,3,4,5,7 | `allenai/tulu-v2-sft-long-mixture` | C/D-mixed |
| `allenai_tulu_v2_sft_mixture` | 1,2,3,4,5,7 | `allenai/tulu-v2-sft-mixture` | C/D-mixed |
| `allenai_verifiable_reasoning_gpt41` | 1,2,3,4,5,7 | `allenai/verifiable-reasoning-filtered-gpt-41` | C-answer / B-check |
| `allenai_verifiable_reasoning_o4mini` | 1,2,3,4,5,7 | `allenai/verifiable-reasoning-filtered-o4-mini` | C-answer / B-check |
| `common-pile-denoising` | 5,7 | `schneiderkamplab/common-pile-denoising` | B-corruption |
| `common-pile-paragraph-reordering` | 5,7 | `schneiderkamplab/common-pile-paragraph-reordering` | B-corruption |
| `common-pile-prefix-continuation` | 5,7 | `schneiderkamplab/common-pile-prefix-continuation` | D-raw / C-next |
| `common-pile-span-filling` | 5,7 | `schneiderkamplab/common-pile-span-filling` | B-corruption |
| `danish-dynaword-denoising` | 5,7 | `schneiderkamplab/danish-dynaword-denoising` | B-corruption |
| `danish-dynaword-paragraph-reordering` | 5,7 | `schneiderkamplab/danish-dynaword-paragraph-reordering` | B-corruption |
| `danish-dynaword-prefix-continuation` | 5,7 | `schneiderkamplab/danish-dynaword-prefix-continuation` | D-raw / C-next |
| `danish-dynaword-span-filling` | 5,7 | `schneiderkamplab/danish-dynaword-span-filling` | B-corruption |
| `danish_dynaword` | 1,2,3,4 | `danish-foundation-models/danish-dynaword` | D-raw / C-next |
| `dbc` | 1,2,3,4,5,7 | `data/converted_sources/dbc` | C/D-mixed |
| `dfm2_dynaword_denoising` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_denoising_v2` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_prefix_continuation` | 2,3,4 | `local generated task` | D-raw / C-next |
| `dfm2_dynaword_prefix_continuation_v2` | 2,3,4 | `local generated task` | D-raw / C-next |
| `dfm2_dynaword_span_fill_v1` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_span_fill_v2` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_span_fill_v3` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_span_fill_v4` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_span_fill_v5` | 2,3,4 | `local generated task` | B-corruption |
| `dfm2_dynaword_span_fill_v6` | 2,3,4 | `local generated task` | B-corruption |
| `dfm3_common_pile_denoising` | 3,4 | `local generated task` | B-corruption |
| `dfm3_common_pile_direct_continuation` | 3,4 | `local generated task` | D-raw / C-next |
| `dfm3_common_pile_prefix_continuation` | 3,4 | `local generated task` | D-raw / C-next |
| `dfm3_common_pile_span_fill_v1` | 3,4 | `local generated task` | B-corruption |
| `dfm3_common_pile_span_fill_v2` | 3,4 | `local generated task` | B-corruption |
| `dfm3_common_pile_span_fill_v3` | 3,4 | `local generated task` | B-corruption |
| `dfm4_arxiv_paper_summarization` | 4,5,7 | `common-pile/arxiv_papers_filtered` | C-text |
| `dfm4_common_pile_paragraph_reorder` | 4 | `local generated task` | B-corruption |
| `dfm4_dynaword_paragraph_reorder` | 4 | `local generated task` | B-corruption |
| `dfm4_govreport_summarization` | 4,5,7 | `ccdv/govreport-summarization` | C-text |
| `dfm4_laion_scientific_summaries` | 4,5,7 | `laion/Scientific-Summaries` | C-text |
| `dfm4_wiki_cat_sum_summarization` | 4,5,7 | `GEM/wiki_cat_sum` | C-text |
| `dfm_dyna_instruct` | 7 | `danish-foundation-models/dfm-dyna-instruct` | mixed: see overview |
| `dolci_instruct_sft` | 1,2,3,4,5,7 | `allenai/Dolci-Instruct-SFT` | C/D-mixed |
| `dolci_instruct_sft_no_tools` | 1,2,3,4,5,7 | `allenai/Dolci-Instruct-SFT-No-Tools` | C/D-mixed |
| `dolci_instruct_sft_tool_use` | 1,2,3,4,5,7 | `allenai/Dolci-Instruct-SFT-Tool-Use` | C/D-mixed |
| `dolci_instruct_sft_tool_use_sa` | 1,2,3,4,5,7 | `allenai/Dolci-Instruct-SFT-Tool-Use-SA` | C/D-mixed |
| `dolci_native_tool_use` | 7 | `data/dfm7_special_sources` | B/C-tool |
| `glaive_native_tool_use` | 7 | `glaiveai/glaive-function-calling-v2` | B/C-tool |
| `kaenguruen` | 7 | `danish-foundation-models/kaenguruen` | A-options (split gate) |
| `laerebogen_with_followups` | 1,2,3,4,5,7 | `danish-foundation-models/laerebogen` | C/D-mixed |
| `lexdk` | 1,2,3,4,5,7 | `data/converted_sources/lexdk` | C/D-mixed |
| `nemotron_agentic` | 1,2,3,4,5,7 | `nvidia/Nemotron-SFT-Agentic-v2` | B/C-tool |
| `nemotron_instruction_reasoning_off` | 1,2,3,4,5,7 | `nvidia/Nemotron-SFT-Instruction-Following-Chat-v2` | B-constraint subset / C remainder |
| `nemotron_multilingual` | 1,2,3,4,5,7 | `nvidia/Nemotron-SFT-Multilingual-v1` | C/D-mixed |
| `nemotron_swe` | 1,2,3,4,5 | `nvidia/Nemotron-SFT-SWE-v2` | D-excluded |
| `no_robots` | 1,2,3,4,5,7 | `HuggingFaceH4/no_robots` | C/D-mixed |
| `oliverkinch_autodata_da_sft` | 7 | `oliverkinch/autodata-da-sft` | C/D-mixed |
| `oliverkinch_da_instruct_dynaword` | 7 | `oliverkinch/da-instruct-dynaword` | C/D-mixed |
| `oliverkinch_da_instruct_dynaword_contemporary` | 7 | `oliverkinch/da-instruct-dynaword-contemporary` | C/D-mixed |
| `oliverkinch_da_instruct_dynaword_contemporary_hq` | 7 | `oliverkinch/da-instruct-dynaword-contemporary-hq` | C/D-mixed |
| `oliverkinch_da_instruct_dynaword_hq` | 7 | `oliverkinch/da-instruct-dynaword-hq` | C/D-mixed |
| `oliverkinch_danish_qa` | 7 | `oliverkinch/danish-qa` | C/D-mixed |
| `oliverkinch_danish_summarization` | 7 | `oliverkinch/danish-summarization` | C-text |
| `oliverkinch_danish_university_portals_bt` | 1,2,3,4,5,7 | `oliverkinch/danish-university-portals-bt` | C/D-mixed |
| `oliverkinch_danmarks_statistik_bt` | 1,2,3,4,5,7 | `oliverkinch/danmarks-statistik-bt` | C/D-mixed |
| `oliverkinch_doab_da_bt` | 1,2,3,4,5,7 | `oliverkinch/doab-da-bt` | C/D-mixed |
| `oliverkinch_dst_table_prompts_bt` | 1,2,3,4,5,7 | `oliverkinch/dst-table-prompts-bt` | C/D-mixed |
| `oliverkinch_dynaword_bt` | 1,2,3,4,5,7 | `oliverkinch/dynaword-bt` | C/D-mixed |
| `oliverkinch_eur_lex_bt` | 1,2,3,4,5,7 | `oliverkinch/eur-lex-bt` | C/D-mixed |
| `oliverkinch_eur_lex_sum_instruct` | 1,2,3,4,5,7 | `oliverkinch/eur-lex-sum-instruct` | C/D-mixed |
| `oliverkinch_instruct_bt` | 1,2,3,4,5,7 | `oliverkinch/instruct-bt` | C/D-mixed |
| `oliverkinch_machine_translation_da_ar` | 1,2,3,4,5,7 | `oliverkinch/machine-translation-da-ar` | C-text |
| `oliverkinch_machine_translation_da_en` | 1,2,3,4,5,7 | `oliverkinch/machine-translation-da-en` | C-text |
| `oliverkinch_machine_translation_da_uk` | 1,2,3,4,5,7 | `oliverkinch/machine-translation-da-uk` | C-text |
| `oliverkinch_multi_wiki_qa_high_quality` | 1,2,3,4,5,7 | `oliverkinch/multi-wiki-qa-high-quality-subset` | C/D-mixed |
| `oliverkinch_tidsskrift_dk_bt` | 1,2,3,4,5,7 | `oliverkinch/tidsskrift-dk-bt` | C/D-mixed |
| `opus` | 1,2,3,4,5,7 | `schneiderkamplab/opus-da-en-permissive` | C-text |
| `sapient-synth-flan-dialog-fsopt-data-qrecc` | 7 | `schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc` | C/D-synthetic |
| `sapient-synth-flan-dialog-fsopt-data-qrecc-ii` | 7 | `schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc-ii` | C/D-synthetic |
| `sapient-synth-flan-dialog-zsopt-data-qrecc` | 7 | `schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc` | C/D-synthetic |
| `sapient-synth-flan-dialog-zsopt-data-qrecc-ii` | 7 | `schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc-ii` | C/D-synthetic |
| `sapient-synth-flan-flan-fsnoopt-data-aeslc-1.0.0` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-aeslc-1.0.0` | C/D-synthetic |
| `sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-idebate` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-idebate` | C/D-synthetic |
| `sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-rotten-tomatoes` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-rotten-tomatoes` | C/D-synthetic |
| `sapient-synth-flan-flan-fsopt-data-aeslc-1.0.0` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-aeslc-1.0.0` | C/D-synthetic |
| `sapient-synth-flan-flan-fsopt-data-opinion-abstracts-idebate` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-opinion-abstracts-idebate` | C/D-synthetic |
| `sapient-synth-flan-flan-fsopt-data-opinion-abstracts-rotten-tomatoes` | 7 | `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-opinion-abstracts-rotten-tomatoes` | C/D-synthetic |
| `sapient-synth-flan-flan-zsnoopt-data-aeslc-1.0.0` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-aeslc-1.0.0` | C/D-synthetic |
| `sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-idebate` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-idebate` | C/D-synthetic |
| `sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-rotten-tomatoes` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-rotten-tomatoes` | C/D-synthetic |
| `sapient-synth-flan-flan-zsopt-data-aeslc-1.0.0` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-aeslc-1.0.0` | C/D-synthetic |
| `sapient-synth-flan-flan-zsopt-data-opinion-abstracts-idebate` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-opinion-abstracts-idebate` | C/D-synthetic |
| `sapient-synth-flan-flan-zsopt-data-opinion-abstracts-rotten-tomatoes` | 7 | `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-opinion-abstracts-rotten-tomatoes` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task1309-amazonreview-summary-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1309-amazonreview-summary-classification` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1370-newscomm-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1370-newscomm-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task1371-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1371-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1373-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1373-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1374-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1374-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1375-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1375-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1376-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1376-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task1377-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1377-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task264-paper-reviews-accept-reject` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task264-paper-reviews-accept-reject` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task265-paper-reviews-language-identification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task265-paper-reviews-language-identification` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task266-paper-reviews-reviewer-perspective` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task266-paper-reviews-reviewer-perspective` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task589-amazonfood-summary-text-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task589-amazonfood-summary-text-generation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task590-amazonfood-summary-correction-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task590-amazonfood-summary-correction-classification` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task618-amazonreview-summary-text-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task618-amazonreview-summary-text-generation` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task634-allegro-reviews-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task634-allegro-reviews-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task635-allegro-reviews-answer-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task635-allegro-reviews-answer-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task672-amazon-yelp-summarization` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task672-amazon-yelp-summarization` | C-text |
| `sapient-synth-flan-niv2-fsopt-data-task870-msmarco-answer-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task870-msmarco-answer-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task902-deceptive-opinion-spam-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task902-deceptive-opinion-spam-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task903-deceptive-opinion-spam-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task903-deceptive-opinion-spam-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task906-dialogre-identify-names` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task906-dialogre-identify-names` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task907-dialogre-identify-relationships` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task907-dialogre-identify-relationships` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task908-dialogre-identify-familial-relationships` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task908-dialogre-identify-familial-relationships` | C/D-synthetic |
| `sapient-synth-flan-niv2-fsopt-data-task909-dialogre-prevalent-speakers` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task909-dialogre-prevalent-speakers` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task1309-amazonreview-summary-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1309-amazonreview-summary-classification` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1370-newscomm-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1370-newscomm-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task1371-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1371-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1373-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1373-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1374-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1374-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1375-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1375-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1376-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1376-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task1377-newscomm-translation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1377-newscomm-translation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task264-paper-reviews-accept-reject` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task264-paper-reviews-accept-reject` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task265-paper-reviews-language-identification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task265-paper-reviews-language-identification` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task266-paper-reviews-reviewer-perspective` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task266-paper-reviews-reviewer-perspective` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task589-amazonfood-summary-text-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task589-amazonfood-summary-text-generation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task590-amazonfood-summary-correction-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task590-amazonfood-summary-correction-classification` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task618-amazonreview-summary-text-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task618-amazonreview-summary-text-generation` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task634-allegro-reviews-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task634-allegro-reviews-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task635-allegro-reviews-answer-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task635-allegro-reviews-answer-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task672-amazon-yelp-summarization` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task672-amazon-yelp-summarization` | C-text |
| `sapient-synth-flan-niv2-zsopt-data-task870-msmarco-answer-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task870-msmarco-answer-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task902-deceptive-opinion-spam-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task902-deceptive-opinion-spam-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task903-deceptive-opinion-spam-classification` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task903-deceptive-opinion-spam-classification` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task906-dialogre-identify-names` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task906-dialogre-identify-names` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task907-dialogre-identify-relationships` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task907-dialogre-identify-relationships` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task908-dialogre-identify-familial-relationships` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task908-dialogre-identify-familial-relationships` | C/D-synthetic |
| `sapient-synth-flan-niv2-zsopt-data-task909-dialogre-prevalent-speakers` | 7 | `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task909-dialogre-prevalent-speakers` | C/D-synthetic |
| `sapient-synth-platypus-reclor` | 7 | `schneiderkamplab/sapient-synth-platypus-reclor` | C/D-synthetic |
| `sapient-synth-platypus-scibench` | 7 | `schneiderkamplab/sapient-synth-platypus-scibench` | C/D-synthetic |
| `sapient-synth-tasksource-pragmeval-sarcasm` | 7 | `schneiderkamplab/sapient-synth-tasksource-pragmeval-sarcasm` | C/D-synthetic |
| `sapient-synth-tasksource-reclor` | 7 | `schneiderkamplab/sapient-synth-tasksource-reclor` | C/D-synthetic |
| `synquid_danish_verifiable_reasoning` | 1,2,3,4,5,7 | `synquid/danish-verifiable-reasoning` | C-answer / B-check |
| `synquid_ifbench_train` | 1,2,3,4,5,7 | `synquid/ifbench-train` | B-constraint subset / C remainder |
| `synquid_mt_da_deepseek` | 1,2,3,4,5,7 | `synquid/mt-da-deepseek` | C-text |
| `synquid_translation_100k` | 1,2,3,4,5,7 | `synquid/translation-100k` | C-text |
| `synquid_wiki_instruct_da` | 1,2,3,4,5,7 | `synquid/wiki-instruct-da` | C/D-mixed |
| `synquid_wildchat_100k_qwen_messages` | 1,2,3,4,5,7 | `synquid/wildchat-100k-qwen-messages` | C/D-mixed |
| `synth_high40` | 5 | `local derived/tokenized source; see analytics` | D-mixed |
| `synth_repeat30` | 5 | `local derived/tokenized source; see analytics` | D-mixed |
| `toolace_native_tool_use` | 7 | `Team-ACE/ToolACE` | B/C-tool |
| `transformations-danish-danish` | 5,7 | `schneiderkamplab/transformations-danish-danish` | B/C-transform |
| `transformations-danish-english` | 5,7 | `schneiderkamplab/transformations-danish-english` | B/C-transform |
| `transformations-english-danish` | 5,7 | `schneiderkamplab/transformations-english-danish` | B/C-transform |
| `transformations-english-english` | 5,7 | `schneiderkamplab/transformations-english-english` | B/C-transform |
| `xlam_native_tool_use` | 7 | `Salesforce/xlam-function-calling-60k` | B/C-tool |
