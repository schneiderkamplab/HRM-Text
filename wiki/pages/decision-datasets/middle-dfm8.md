---
type: Reference
title: DFM8 Inherited And Added Sources
description: Complete repository-level historical DFM8 inventory with proposed decision applicability.
tags: [decision-datasets, dfm8, dfm9, dfm10, dfm11, dfm12, dfm13, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM8 Inherited And Added Sources

Part of [DFM8-13 source review](middle-datasets.md). Classifications are proposals, not conversion or admission results.

Evidence: [historical nonzero inventory](../../../docs/dfm8-datasets.md), 159 HF repositories. Every row below was historically sampled, not necessarily retained by later phases. Prefixes identify the exact source category in that report. Recipe names refer to the review's applicability key. Sapient rows require current narrow allowlist checks, regardless of historical membership.

| Exact HF ID | Historical prefix/category | Proposed applicability |
|---|---|---|

| `allenai/big-reasoning-traces` | `allenai_big_reasoning_traces` | B/C: Candidate answer equality or executable result |
| `allenai/Dolci-Instruct-SFT` | `dolci_instruct_sft` | C: Task-routed candidate response judgment |
| `allenai/Dolci-Instruct-SFT-No-Tools` | `dolci_instruct_sft_no_tools` | B/C: Tool name/schema validity; candidate next action |
| `allenai/Dolci-Instruct-SFT-Tool-Use` | `dolci_native_tool_use/dolci_instruct_sft_tool_use` | B/C: Tool name/schema validity; candidate next action |
| `allenai/Dolci-Instruct-SFT-Tool-Use-SA` | `dolci_native_tool_use/dolci_instruct_sft_tool_use_sa` | B/C: Tool name/schema validity; candidate next action |
| `allenai/IF_sft_data_verified` | `allenai_if_sft_verified` | C: Task-routed candidate response judgment |
| `allenai/open_math_2_50k_r1-original` | `allenai_open_math_2_50k_r1` | B/C: Candidate answer equality or executable result |
| `allenai/RLVR-GSM` | `allenai_rlvr_gsm` | B/C: Candidate answer equality or executable result |
| `allenai/RLVR-MATH` | `allenai_rlvr_math` | B/C: Candidate answer equality or executable result |
| `allenai/SciRIFF-train-mix` | `allenai_sciriff_train_mix` | C: Task-routed candidate response judgment |
| `allenai/tulu-3-sft-mixture` | `allenai_tulu_3_sft_mixture` | C: Task-routed candidate response judgment |
| `allenai/tulu-3-sft-personas-algebra` | `allenai_tulu_3_personas_algebra` | B/C: Candidate answer equality or executable result |
| `allenai/tulu-3-sft-personas-code` | `allenai_tulu_3_personas_code` | C: Task-routed candidate response judgment |
| `allenai/tulu-3-sft-personas-instruction-following` | `allenai_tulu_3_personas_if` | C: Task-routed candidate response judgment |
| `allenai/tulu-3-sft-personas-math` | `allenai_tulu_3_personas_math` | B/C: Candidate answer equality or executable result |
| `allenai/tulu-v2-sft-long-mixture` | `allenai_tulu_v2_sft_long_mixture` | C: Task-routed candidate response judgment |
| `allenai/tulu-v2-sft-mixture` | `allenai_tulu_v2_sft_mixture` | C: Task-routed candidate response judgment |
| `allenai/verifiable-reasoning-filtered-gpt-41` | `allenai_verifiable_reasoning_gpt41` | B/C: Candidate answer equality or executable result |
| `allenai/verifiable-reasoning-filtered-o4-mini` | `allenai_verifiable_reasoning_o4mini` | B/C: Candidate answer equality or executable result |
| `ccdv/govreport-summarization` | `dfm4_govreport_summarization` | C: Evidence support / summary or rewrite adequacy |
| `common-pile/arxiv_papers_filtered` | `dfm4_arxiv_paper_summarization` | C: Task-routed candidate response judgment |
| `danish-foundation-models/ai_arena_udtraek` | `ai_arena_udtraek` | A/C: Original pair preference / rating |
| `danish-foundation-models/dfm-dyna-instruct` | `dfm_dyna_instruct` | C: Task-routed candidate response judgment |
| `danish-foundation-models/kaenguruen` | `kaenguruen` | A: Existing label or option |
| `danish-foundation-models/laerebogen` | `laerebogen_with_followups` | C: Task-routed candidate response judgment |
| `GEM/wiki_cat_sum` | `dfm4_wiki_cat_sum_summarization` | C: Evidence support / summary or rewrite adequacy |
| `giannor/dala_tv2r_it` | `giannor_dala_tv2r_it` | A: Existing label or option |
| `giannor/gec_dala_tv2r_it` | `giannor_gec_dala_tv2r_it` | B/C: Known corruption/edit validity or reconstruction |
| `glaiveai/glaive-function-calling-v2` | `glaive_native_tool_use` | B/C: Tool name/schema validity; candidate next action |
| `HuggingFaceH4/no_robots` | `no_robots` | C: Task-routed candidate response judgment |
| `kobprof/skolegpt-instruct` | `kobprof_skolegpt_instruct` | C: Task-routed candidate response judgment |
| `laion/Scientific-Summaries` | `dfm4_laion_scientific_summaries` | C: Evidence support / summary or rewrite adequacy |
| `MegaScience/TextbookReasoning` | `textbookreasoning` | B/C: Candidate answer equality or executable result |
| `nvidia/AceReason-1.1-SFT` | `acereason` | B/C: Candidate answer equality or executable result |
| `nvidia/Nemotron-SFT-Agentic-v2` | `nemotron_agentic` | B/C: Tool name/schema validity; candidate next action |
| `nvidia/Nemotron-SFT-Instruction-Following-Chat-v2` | `nemotron_instruction_reasoning_off` | C: Task-routed candidate response judgment |
| `nvidia/Nemotron-SFT-Multilingual-v1` | `nemotron_multilingual` | C: Task-routed candidate response judgment |
| `nvidia/OpenMathInstruct-2` | `openmathinstruct2` | B/C: Candidate answer equality or executable result |
| `oliverkinch/autodata-da-sft` | `oliverkinch_autodata_da_sft` | C: Task-routed candidate response judgment |
| `oliverkinch/da-instruct-dynaword` | `oliverkinch_da_instruct_dynaword` | C: Task-routed candidate response judgment |
| `oliverkinch/da-instruct-dynaword-contemporary` | `oliverkinch_da_instruct_dynaword_contemporary` | C: Task-routed candidate response judgment |
| `oliverkinch/da-instruct-dynaword-contemporary-hq` | `oliverkinch_da_instruct_dynaword_contemporary_hq` | C: Task-routed candidate response judgment |
| `oliverkinch/da-instruct-dynaword-hq` | `oliverkinch_da_instruct_dynaword_hq` | C: Task-routed candidate response judgment |
| `oliverkinch/danish-qa` | `oliverkinch_danish_qa` | C: Task-routed candidate response judgment |
| `oliverkinch/danish-summarization` | `oliverkinch_danish_summarization` | C: Evidence support / summary or rewrite adequacy |
| `oliverkinch/danish-university-portals-bt` | `oliverkinch_danish_university_portals_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/danmarks-statistik-bt` | `oliverkinch_danmarks_statistik_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/doab-da-bt` | `oliverkinch_doab_da_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/dst-table-prompts-bt` | `oliverkinch_dst_table_prompts_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/dynaword-bt` | `oliverkinch_dynaword_bt` | D: No existing decision target |
| `oliverkinch/eur-lex-bt` | `oliverkinch_eur_lex_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/eur-lex-sum-instruct` | `oliverkinch_eur_lex_sum_instruct` | C: Task-routed candidate response judgment |
| `oliverkinch/instruct-bt` | `oliverkinch_instruct_bt` | C: Task-routed candidate response judgment |
| `oliverkinch/machine-translation-da-ar` | `oliverkinch_machine_translation_da_ar` | C: Translation adequacy or source-target match |
| `oliverkinch/machine-translation-da-en` | `oliverkinch_machine_translation_da_en` | C: Translation adequacy or source-target match |
| `oliverkinch/machine-translation-da-uk` | `oliverkinch_machine_translation_da_uk` | C: Translation adequacy or source-target match |
| `oliverkinch/multi-wiki-qa-high-quality-subset` | `oliverkinch_multi_wiki_qa_high_quality` | C: Task-routed candidate response judgment |
| `oliverkinch/tidsskrift-dk-bt` | `oliverkinch_tidsskrift_dk_bt` | C: Task-routed candidate response judgment |
| `open-thoughts/OpenThoughts2-1M` | `openthoughts2` | C: Task-routed candidate response judgment |
| `Salesforce/xlam-function-calling-60k` | `xlam_native_tool_use` | B/C: Tool name/schema validity; candidate next action |
| `sapientinc/HRM-Text-data-io-cleaned-20260515` | `{Platypus/SYNTH/ampsmathematica/dmmath/flan/sudoku_extreme/tasksource}` | C: Task-routed candidate response judgment |
| `schneiderkamplab/common-pile-denoising` | `common-pile-denoising` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/common-pile-paragraph-reordering` | `common-pile-paragraph-reordering` | B/C: Original-order recovery / valid next block |
| `schneiderkamplab/common-pile-prefix-continuation` | `common-pile-prefix-continuation` | B/C: Masked source-span recovery |
| `schneiderkamplab/common-pile-span-filling` | `common-pile-span-filling` | B/C: Masked source-span recovery |
| `schneiderkamplab/danish-dynaword-denoising` | `danish-dynaword-denoising` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/danish-dynaword-paragraph-reordering` | `danish-dynaword-paragraph-reordering` | B/C: Original-order recovery / valid next block |
| `schneiderkamplab/danish-dynaword-prefix-continuation` | `danish-dynaword-prefix-continuation` | B/C: Masked source-span recovery |
| `schneiderkamplab/danish-dynaword-span-filling` | `danish-dynaword-span-filling` | B/C: Masked source-span recovery |
| `schneiderkamplab/dfm8-openhermes-da` | `dfm8-openhermes-da` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm8-openhermes-en` | `dfm8-openhermes-en` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm8-synthetic-code-debugging` | `dfm8-synthetic-code-debugging` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm8-synthetic-constrained-format-following` | `dfm8-synthetic-constrained-format-following` | B: Pass/fail for explicit output constraints |
| `schneiderkamplab/dfm8-synthetic-danish-summarization-rewrite-controls` | `dfm8-synthetic-danish-summarization-rewrite-controls` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/dfm8-synthetic-multiturn-danish-english-chat` | `dfm8-synthetic-multiturn-danish-english-chat` | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm8-synthetic-native-tool-calling` | `dfm8-synthetic-native-tool-calling` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm8-synthetic-strict-math-answer-contract` | `dfm8-synthetic-strict-math-answer-contract` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/opus-da-en-permissive` | `opus` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc` | `sapient-synth-flan-dialog-fsopt-data-qrecc` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-dialog-fsopt-data-qrecc-ii` | `sapient-synth-flan-dialog-fsopt-data-qrecc-ii` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc` | `sapient-synth-flan-dialog-zsopt-data-qrecc` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-dialog-zsopt-data-qrecc-ii` | `sapient-synth-flan-dialog-zsopt-data-qrecc-ii` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-aeslc-1.0.0` | `sapient-synth-flan-flan-fsnoopt-data-aeslc-1.0.0` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-idebate` | `sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-idebate` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-rotten-tomatoes` | `sapient-synth-flan-flan-fsnoopt-data-opinion-abstracts-rotten-tomatoes` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-aeslc-1.0.0` | `sapient-synth-flan-flan-fsopt-data-aeslc-1.0.0` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-opinion-abstracts-idebate` | `sapient-synth-flan-flan-fsopt-data-opinion-abstracts-idebate` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-fsopt-data-opinion-abstracts-rotten-tomatoes` | `sapient-synth-flan-flan-fsopt-data-opinion-abstracts-rotten-tomatoes` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-aeslc-1.0.0` | `sapient-synth-flan-flan-zsnoopt-data-aeslc-1.0.0` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-idebate` | `sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-idebate` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-rotten-tomatoes` | `sapient-synth-flan-flan-zsnoopt-data-opinion-abstracts-rotten-tomatoes` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-aeslc-1.0.0` | `sapient-synth-flan-flan-zsopt-data-aeslc-1.0.0` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-opinion-abstracts-idebate` | `sapient-synth-flan-flan-zsopt-data-opinion-abstracts-idebate` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-flan-zsopt-data-opinion-abstracts-rotten-tomatoes` | `sapient-synth-flan-flan-zsopt-data-opinion-abstracts-rotten-tomatoes` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1309-amazonreview-summary-classification` | `sapient-synth-flan-niv2-fsopt-data-task1309-amazonreview-summary-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1370-newscomm-classification` | `sapient-synth-flan-niv2-fsopt-data-task1370-newscomm-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1371-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1371-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1373-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1373-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1374-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1374-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1375-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1375-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1376-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1376-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task1377-newscomm-translation` | `sapient-synth-flan-niv2-fsopt-data-task1377-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task264-paper-reviews-accept-reject` | `sapient-synth-flan-niv2-fsopt-data-task264-paper-reviews-accept-reject` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task265-paper-reviews-language-identification` | `sapient-synth-flan-niv2-fsopt-data-task265-paper-reviews-language-identification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task266-paper-reviews-reviewer-perspective` | `sapient-synth-flan-niv2-fsopt-data-task266-paper-reviews-reviewer-perspective` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task589-amazonfood-summary-text-generation` | `sapient-synth-flan-niv2-fsopt-data-task589-amazonfood-summary-text-generation` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task590-amazonfood-summary-correction-classification` | `sapient-synth-flan-niv2-fsopt-data-task590-amazonfood-summary-correction-classification` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task618-amazonreview-summary-text-generation` | `sapient-synth-flan-niv2-fsopt-data-task618-amazonreview-summary-text-generation` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task634-allegro-reviews-classification` | `sapient-synth-flan-niv2-fsopt-data-task634-allegro-reviews-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task635-allegro-reviews-answer-generation` | `sapient-synth-flan-niv2-fsopt-data-task635-allegro-reviews-answer-generation` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task672-amazon-yelp-summarization` | `sapient-synth-flan-niv2-fsopt-data-task672-amazon-yelp-summarization` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task870-msmarco-answer-generation` | `sapient-synth-flan-niv2-fsopt-data-task870-msmarco-answer-generation` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation` | `sapient-synth-flan-niv2-fsopt-data-task871-msmarco-question-generation` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task902-deceptive-opinion-spam-classification` | `sapient-synth-flan-niv2-fsopt-data-task902-deceptive-opinion-spam-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task903-deceptive-opinion-spam-classification` | `sapient-synth-flan-niv2-fsopt-data-task903-deceptive-opinion-spam-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task906-dialogre-identify-names` | `sapient-synth-flan-niv2-fsopt-data-task906-dialogre-identify-names` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task907-dialogre-identify-relationships` | `sapient-synth-flan-niv2-fsopt-data-task907-dialogre-identify-relationships` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task908-dialogre-identify-familial-relationships` | `sapient-synth-flan-niv2-fsopt-data-task908-dialogre-identify-familial-relationships` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-fsopt-data-task909-dialogre-prevalent-speakers` | `sapient-synth-flan-niv2-fsopt-data-task909-dialogre-prevalent-speakers` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1309-amazonreview-summary-classification` | `sapient-synth-flan-niv2-zsopt-data-task1309-amazonreview-summary-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1370-newscomm-classification` | `sapient-synth-flan-niv2-zsopt-data-task1370-newscomm-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1371-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1371-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1373-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1373-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1374-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1374-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1375-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1375-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1376-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1376-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task1377-newscomm-translation` | `sapient-synth-flan-niv2-zsopt-data-task1377-newscomm-translation` | C: Translation adequacy or source-target match |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task264-paper-reviews-accept-reject` | `sapient-synth-flan-niv2-zsopt-data-task264-paper-reviews-accept-reject` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task265-paper-reviews-language-identification` | `sapient-synth-flan-niv2-zsopt-data-task265-paper-reviews-language-identification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task266-paper-reviews-reviewer-perspective` | `sapient-synth-flan-niv2-zsopt-data-task266-paper-reviews-reviewer-perspective` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task589-amazonfood-summary-text-generation` | `sapient-synth-flan-niv2-zsopt-data-task589-amazonfood-summary-text-generation` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task590-amazonfood-summary-correction-classification` | `sapient-synth-flan-niv2-zsopt-data-task590-amazonfood-summary-correction-classification` | B/C: Known corruption/edit validity or reconstruction |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task618-amazonreview-summary-text-generation` | `sapient-synth-flan-niv2-zsopt-data-task618-amazonreview-summary-text-generation` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task634-allegro-reviews-classification` | `sapient-synth-flan-niv2-zsopt-data-task634-allegro-reviews-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task635-allegro-reviews-answer-generation` | `sapient-synth-flan-niv2-zsopt-data-task635-allegro-reviews-answer-generation` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task672-amazon-yelp-summarization` | `sapient-synth-flan-niv2-zsopt-data-task672-amazon-yelp-summarization` | C: Evidence support / summary or rewrite adequacy |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task870-msmarco-answer-generation` | `sapient-synth-flan-niv2-zsopt-data-task870-msmarco-answer-generation` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation` | `sapient-synth-flan-niv2-zsopt-data-task871-msmarco-question-generation` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task902-deceptive-opinion-spam-classification` | `sapient-synth-flan-niv2-zsopt-data-task902-deceptive-opinion-spam-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task903-deceptive-opinion-spam-classification` | `sapient-synth-flan-niv2-zsopt-data-task903-deceptive-opinion-spam-classification` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task906-dialogre-identify-names` | `sapient-synth-flan-niv2-zsopt-data-task906-dialogre-identify-names` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task907-dialogre-identify-relationships` | `sapient-synth-flan-niv2-zsopt-data-task907-dialogre-identify-relationships` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task908-dialogre-identify-familial-relationships` | `sapient-synth-flan-niv2-zsopt-data-task908-dialogre-identify-familial-relationships` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-flan-niv2-zsopt-data-task909-dialogre-prevalent-speakers` | `sapient-synth-flan-niv2-zsopt-data-task909-dialogre-prevalent-speakers` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-platypus-reclor` | `sapient-synth-platypus-reclor` | C: Task-routed candidate response judgment |
| `schneiderkamplab/sapient-synth-platypus-scibench` | `sapient-synth-platypus-scibench` | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/sapient-synth-tasksource-pragmeval-sarcasm` | `sapient-synth-tasksource-pragmeval-sarcasm` | A: Existing label or option |
| `schneiderkamplab/sapient-synth-tasksource-reclor` | `sapient-synth-tasksource-reclor` | C: Task-routed candidate response judgment |
| `schneiderkamplab/transformations-danish-danish` | `transformations-danish-danish` | C: Task-routed candidate response judgment |
| `schneiderkamplab/transformations-danish-english` | `transformations-danish-english` | C: Task-routed candidate response judgment |
| `schneiderkamplab/transformations-english-danish` | `transformations-english-danish` | C: Task-routed candidate response judgment |
| `schneiderkamplab/transformations-english-english` | `transformations-english-english` | C: Task-routed candidate response judgment |
| `synquid/danish-verifiable-reasoning` | `synquid_danish_verifiable_reasoning` | B/C: Candidate answer equality or executable result |
| `synquid/ifbench-train` | `synquid_ifbench_train` | C: Task-routed candidate response judgment |
| `synquid/mt-da-deepseek` | `synquid_mt_da_deepseek` | C: Translation adequacy or source-target match |
| `synquid/translation-100k` | `synquid_translation_100k` | C: Translation adequacy or source-target match |
| `synquid/wiki-instruct-da` | `synquid_wiki_instruct_da` | C: Task-routed candidate response judgment |
| `synquid/wildchat-100k-qwen-messages` | `synquid_wildchat_100k_qwen_messages` | C: Task-routed candidate response judgment |
| `Team-ACE/ToolACE` | `toolace_native_tool_use` | B/C: Tool name/schema validity; candidate next action |
