---
type: Reference
title: DFM13 Addition Registry
description: Every one of the 312 DFM13 addition-registry records with explicit status.
tags: [decision-datasets, dfm8, dfm9, dfm10, dfm11, dfm12, dfm13, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM13 Addition Registry

Part of [DFM8-13 source review](middle-datasets.md). Classifications are proposals, not conversion or admission results.

Evidence: [DFM13 registry](../../../config/dfm13_sources.json), exact `additions[].name` key. Upstream and export fields are distinct; non-HF URLs remain literal provenance. Revisions, receipt hashes, context views and admission blockers remain in the keyed record. Status census: 298 `accepted_uploaded`, four `quality_hold_source_fidelity`, one `source_native_tokenized`, nine without a `status` field. Missing status is not a hold or acceptance inference; recorded publication state is shown separately. Registry entry/publication does not alone prove final sampled membership.

| Registry name | Exact upstream ID / origin | Exact HF export ID | Recorded status | Proposed applicability |
|---|---|---|---|---|

| `ai_arenaen_preferred` | `danish-foundation-models/ai-arenaen` | `schneiderkamplab/dfm13-ai-arenaen-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `arena_human_preference_140k` | `lmarena-ai/arena-human-preference-140k` | `schneiderkamplab/dfm13-arena-human-preference-140k-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `arena_human_preference_100k` | `lmarena-ai/arena-human-preference-100k` | `schneiderkamplab/dfm13-arena-human-preference-100k-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `arena_human_preference_55k` | `lmarena-ai/arena-human-preference-55k` | `schneiderkamplab/dfm13-arena-human-preference-55k-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `comparia_preferred` | `ministere-culture/comparia-fr-arena` | `schneiderkamplab/dfm13-comparia-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `helpsteer3_edit` | `nvidia/HelpSteer3` | `schneiderkamplab/dfm13-helpsteer3-edit` | status absent; publication=verified | A/C: Original pair preference / rating |
| `helpsteer3_preference` | `nvidia/HelpSteer3` | `schneiderkamplab/dfm13-helpsteer3-preference` | status absent; publication=verified | A/C: Original pair preference / rating |
| `arena_expert5k` | `lmarena-ai/arena-expert-5k` | `schneiderkamplab/dfm13-arena-expert5k-preferred` | status absent; publication=verified | A/C: Original pair preference / rating |
| `hendrycks_math_worked` | `EleutherAI/hendrycks_math` | not recorded; upstream only | status absent; publication=not recorded | B/C: Candidate answer equality or executable result |
| `jjzha_skillspan` | `jjzha/skillspan` | `schneiderkamplab/dfm13-jjzha-skillspan` | accepted_uploaded | B: Token/span label or candidate-entity membership |
| `jjzha_kompetencer` | `jjzha/kompetencer` | `schneiderkamplab/dfm13-jjzha-kompetencer` | accepted_uploaded | B: Token/span label or candidate-entity membership |
| `jjzha_green` | `jjzha/green` | `schneiderkamplab/dfm13-jjzha-green` | accepted_uploaded | B: Token/span label or candidate-entity membership |
| `jjzha_imdb_dutch` | `jjzha/imdb-dutch-instruct` | `schneiderkamplab/dfm13-jjzha-imdb-dutch` | accepted_uploaded | A: Existing label or option |
| `jjzha_dutch_exam` | `jjzha/dutch-central-exam-mcq` | `schneiderkamplab/dfm13-jjzha-dutch-exam` | accepted_uploaded | A: Existing label or option |
| `jjzha_croco` | `jjzha/croco-translated-data` | `schneiderkamplab/dfm13-jjzha-croco` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_administraktor_hrvatski_dataset_v2_hr` | `administraktor/hrvatski-dataset-v2` | `schneiderkamplab/dfm13-wave4-administraktor-hrvatski-dataset-v2-hr` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_CohereLabs_aya_dataset_hu` | `CohereLabs/aya_dataset` | `schneiderkamplab/dfm13-wave4-CohereLabs-aya_dataset-hu` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_CohereLabs_aya_dataset_sr` | `CohereLabs/aya_dataset` | `schneiderkamplab/dfm13-wave4-CohereLabs-aya_dataset-sr` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_CohereLabs_aya_dataset_fa` | `CohereLabs/aya_dataset` | `schneiderkamplab/dfm13-wave4-CohereLabs-aya_dataset-fa` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_utter_project_EuroBlocks_SFT_2512_bg` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave4-utter-project-EuroBlocks-SFT-2512-bg` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_utter_project_EuroBlocks_SFT_2512_hr` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave4-utter-project-EuroBlocks-SFT-2512-hr` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_utter_project_EuroBlocks_SFT_2512_sk` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave4-utter-project-EuroBlocks-SFT-2512-sk` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_utter_project_EuroBlocks_SFT_2512_sl` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave4-utter-project-EuroBlocks-SFT-2512-sl` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_utter_project_EuroBlocks_SFT_2512_hu` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave4-utter-project-EuroBlocks-SFT-2512-hu` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_alban_labs_Kapibara_sq` | `alban-labs/Kapibara` | `schneiderkamplab/dfm13-wave4-alban-labs-Kapibara-sq` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_jvalline_LuxIT_wiki_subset_lb` | `jvalline/LuxIT_wiki_subset` | `schneiderkamplab/dfm13-wave4-jvalline-LuxIT_wiki_subset-lb` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_fo_lv` | `schneiderkamplab/dfm13-wave3-opus-fo-lv` | `schneiderkamplab/dfm13-wave3-opus-fo-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_ca_lt` | `schneiderkamplab/dfm13-wave3-opus-ca-lt` | `schneiderkamplab/dfm13-wave3-opus-ca-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_ca_lv` | `schneiderkamplab/dfm13-wave3-opus-ca-lv` | `schneiderkamplab/dfm13-wave3-opus-ca-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_cs_lv` | `schneiderkamplab/dfm13-wave3-opus-cs-lv` | `schneiderkamplab/dfm13-wave3-opus-cs-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_da_lt` | `schneiderkamplab/dfm13-wave3-opus-da-lt` | `schneiderkamplab/dfm13-wave3-opus-da-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_da_lv` | `schneiderkamplab/dfm13-wave3-opus-da-lv` | `schneiderkamplab/dfm13-wave3-opus-da-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_de_lt` | `schneiderkamplab/dfm13-wave3-opus-de-lt` | `schneiderkamplab/dfm13-wave3-opus-de-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_de_lv` | `schneiderkamplab/dfm13-wave3-opus-de-lv` | `schneiderkamplab/dfm13-wave3-opus-de-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_el_lt` | `schneiderkamplab/dfm13-wave3-opus-el-lt` | `schneiderkamplab/dfm13-wave3-opus-el-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_el_lv` | `schneiderkamplab/dfm13-wave3-opus-el-lv` | `schneiderkamplab/dfm13-wave3-opus-el-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_is_lv` | `schneiderkamplab/dfm13-wave3-opus-is-lv` | `schneiderkamplab/dfm13-wave3-opus-is-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_es_lt` | `schneiderkamplab/dfm13-wave3-opus-es-lt` | `schneiderkamplab/dfm13-wave3-opus-es-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_es_lv` | `schneiderkamplab/dfm13-wave3-opus-es-lv` | `schneiderkamplab/dfm13-wave3-opus-es-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_et_lt` | `schneiderkamplab/dfm13-wave3-opus-et-lt` | `schneiderkamplab/dfm13-wave3-opus-et-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_et_lv` | `schneiderkamplab/dfm13-wave3-opus-et-lv` | `schneiderkamplab/dfm13-wave3-opus-et-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_fi_lt` | `schneiderkamplab/dfm13-wave3-opus-fi-lt` | `schneiderkamplab/dfm13-wave3-opus-fi-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_fi_lv` | `schneiderkamplab/dfm13-wave3-opus-fi-lv` | `schneiderkamplab/dfm13-wave3-opus-fi-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_fo_lt` | `schneiderkamplab/dfm13-wave3-opus-fo-lt` | `schneiderkamplab/dfm13-wave3-opus-fo-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_fr_lt` | `schneiderkamplab/dfm13-wave3-opus-fr-lt` | `schneiderkamplab/dfm13-wave3-opus-fr-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_fr_lv` | `schneiderkamplab/dfm13-wave3-opus-fr-lv` | `schneiderkamplab/dfm13-wave3-opus-fr-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_is_lt` | `schneiderkamplab/dfm13-wave3-opus-is-lt` | `schneiderkamplab/dfm13-wave3-opus-is-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_it_lt` | `schneiderkamplab/dfm13-wave3-opus-it-lt` | `schneiderkamplab/dfm13-wave3-opus-it-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_it_lv` | `schneiderkamplab/dfm13-wave3-opus-it-lv` | `schneiderkamplab/dfm13-wave3-opus-it-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_CohereLabs_aya_dataset_sq_tosk` | `CohereLabs/aya_dataset` | `schneiderkamplab/dfm13-wave4-CohereLabs-aya_dataset-sq-tosk` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_lt_lv` | `schneiderkamplab/dfm13-wave3-opus-lt-lv` | `schneiderkamplab/dfm13-wave3-opus-lt-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lt_nb` | `schneiderkamplab/dfm13-wave3-opus-lt-nb` | `schneiderkamplab/dfm13-wave3-opus-lt-nb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_cs_lt` | `schneiderkamplab/dfm13-wave3-opus-cs-lt` | `schneiderkamplab/dfm13-wave3-opus-cs-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_transform_Wikipedia_lt_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lt-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave3_transform_Wikipedia_lt_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lt-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave3_transform_Wikipedia_lt_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lt-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_Wikipedia_lt_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lt-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_Wikipedia_lv_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lv-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave3_transform_Wikipedia_lv_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lv-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave3_transform_Wikipedia_lv_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lv-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_Wikipedia_lv_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave3-transform-Wikipedia_lv-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_parlamint_lt_denoising` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/1432/ParlaMint-LT.tgz?sequence=12&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lt-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave3_baltic_lt_aya` | `CohereLabs/aya_dataset` | `schneiderkamplab/dfm13-wave3-baltic_lt_aya` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave3_transform_parlamint_lt_paragraph_reordering` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/1432/ParlaMint-LT.tgz?sequence=12&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lt-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave3_transform_parlamint_lt_prefix_continuation` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/1432/ParlaMint-LT.tgz?sequence=12&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lt-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_parlamint_lt_span_filling` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/1432/ParlaMint-LT.tgz?sequence=12&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lt-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_parlamint_lv_denoising` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/ParlaMint-LV.tgz?sequence=20&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lv-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave3_transform_parlamint_lv_paragraph_reordering` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/ParlaMint-LV.tgz?sequence=20&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lv-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave3_transform_parlamint_lv_prefix_continuation` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/ParlaMint-LV.tgz?sequence=20&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lv-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_parlamint_lv_span_filling` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/ParlaMint-LV.tgz?sequence=20&isAllowed=y` | `schneiderkamplab/dfm13-wave3-transform-parlamint_lv-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_baltic_lv_qa` | `martinsu/latvian-wikipedia-qa-gemma3` | `schneiderkamplab/dfm13-wave3-baltic_lv_qa` | quality_hold_source_fidelity | D: held; intrinsic C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_lt_nl` | `schneiderkamplab/dfm13-wave3-opus-lt-nl` | `schneiderkamplab/dfm13-wave3-opus-lt-nl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lt_nn` | `schneiderkamplab/dfm13-wave3-opus-lt-nn` | `schneiderkamplab/dfm13-wave3-opus-lt-nn` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lt_pl` | `schneiderkamplab/dfm13-wave3-opus-lt-pl` | `schneiderkamplab/dfm13-wave3-opus-lt-pl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lt_ro` | `schneiderkamplab/dfm13-wave3-opus-lt-ro` | `schneiderkamplab/dfm13-wave3-opus-lt-ro` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_ParsiAI_FarsInstruct_fa_farstail` | `ParsiAI/FarsInstruct` | `schneiderkamplab/dfm13-wave4-ParsiAI-FarsInstruct-fa-farstail` | accepted_uploaded | A: Existing label or option |
| `dfm13_wave3_baltic_lt_qa` | `neurotechnology/lithuanian-qa-v1` | `schneiderkamplab/dfm13-wave3-baltic_lt_qa` | quality_hold_source_fidelity | D: held; intrinsic C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_lt_sv` | `schneiderkamplab/dfm13-wave3-opus-lt-sv` | `schneiderkamplab/dfm13-wave3-opus-lt-sv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lt_uk` | `schneiderkamplab/dfm13-wave3-opus-lt-uk` | `schneiderkamplab/dfm13-wave3-opus-lt-uk` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_nb` | `schneiderkamplab/dfm13-wave3-opus-lv-nb` | `schneiderkamplab/dfm13-wave3-opus-lv-nb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_nl` | `schneiderkamplab/dfm13-wave3-opus-lv-nl` | `schneiderkamplab/dfm13-wave3-opus-lv-nl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_nn` | `schneiderkamplab/dfm13-wave3-opus-lv-nn` | `schneiderkamplab/dfm13-wave3-opus-lv-nn` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_baltic_euroblocks` | `utter-project/EuroBlocks-SFT-2512` | `schneiderkamplab/dfm13-wave3-baltic-euroblocks` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_lv_pl` | `schneiderkamplab/dfm13-wave3-opus-lv-pl` | `schneiderkamplab/dfm13-wave3-opus-lv-pl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_ro` | `schneiderkamplab/dfm13-wave3-opus-lv-ro` | `schneiderkamplab/dfm13-wave3-opus-lv-ro` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_sv` | `schneiderkamplab/dfm13-wave3-opus-lv-sv` | `schneiderkamplab/dfm13-wave3-opus-lv-sv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_uk` | `schneiderkamplab/dfm13-wave3-opus-lv-uk` | `schneiderkamplab/dfm13-wave3-opus-lv-uk` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_transform_baltic_lt_blkt_denoising_newgenltu` | `VSSA-SDSA/LT_AI_BLKT` | `schneiderkamplab/dfm13-wave3-transform-baltic-lt-blkt-denoising-newgenltu` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave3_transform_baltic_lt_blkt_prefix_continuation_newgenltu` | `VSSA-SDSA/LT_AI_BLKT` | `schneiderkamplab/dfm13-wave3-transform-baltic-lt-blkt-prefix-continuation-newgenltu` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_transform_baltic_lt_blkt_span_filling_newgenltu` | `VSSA-SDSA/LT_AI_BLKT` | `schneiderkamplab/dfm13-wave3-transform-baltic-lt-blkt-span-filling-newgenltu` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_bg_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bg-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_bg_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bg-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_bg_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bg-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_bg_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bg-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_latvian_p3_cc_by_4_0` | `matiss/P3-Latvian-translategemma-27b` | `schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-4-0` | quality_hold_source_fidelity | D: held; intrinsic C: Task-routed candidate response judgment |
| `dfm13_wave3_latvian_p3_cc_by_sa_4_0` | `matiss/P3-Latvian-translategemma-27b` | `schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-sa-4-0` | quality_hold_source_fidelity | D: held; intrinsic C: Task-routed candidate response judgment |
| `dfm13_wave4_wikipedia_be_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-be-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_be_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-be-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_be_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-be-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_be_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-be-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_bs_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bs-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_bs_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bs-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_bs_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bs-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_bs_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-bs-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_baltic_lt_summary_newgenltu` | `VytautoDidziojoUniversitetas/LT_Summarisation_Corpus` | `schneiderkamplab/dfm13-wave3-baltic-lt-summary-newgenltu` | accepted_uploaded | C: Evidence support / summary or rewrite adequacy |
| `dfm13_wave4_wikipedia_fa_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-fa-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_fa_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-fa-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_fa_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-fa-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_fa_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-fa-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave3_opus_lt_pt_pt` | `schneiderkamplab/dfm13-wave3-opus-lt-pt_pt` | `schneiderkamplab/dfm13-wave3-opus-lt-pt_pt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_lv_pt_pt` | `schneiderkamplab/dfm13-wave3-opus-lv-pt_pt` | `schneiderkamplab/dfm13-wave3-opus-lv-pt_pt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_ParsiAI_FarsInstruct_fa_parsinlu_comp` | `ParsiAI/FarsInstruct` | `schneiderkamplab/dfm13-wave4-ParsiAI-FarsInstruct-fa-parsinlu_comp` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave4_ParsiAI_FarsInstruct_fa_persian_qa` | `ParsiAI/FarsInstruct` | `schneiderkamplab/dfm13-wave4-ParsiAI-FarsInstruct-fa-persian_qa` | accepted_uploaded | C: Task-routed candidate response judgment |
| `dfm13_wave3_opus_en_lv` | `schneiderkamplab/dfm13-wave3-opus-en-lv` | `schneiderkamplab/dfm13-wave3-opus-en-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave3_opus_en_lt` | `schneiderkamplab/dfm13-wave3-opus-en-lt` | `schneiderkamplab/dfm13-wave3-opus-en-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_wikipedia_hr_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hr-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_hr_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hr-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_hr_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hr-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_hr_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hr-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_hu_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hu-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_hu_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hu-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_hu_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hu-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_hu_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-hu-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_lb_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-lb-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_lb_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-lb-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_lb_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-lb-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_lb_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-lb-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sk_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sk-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_sk_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sk-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_sk_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sk-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sk_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sk-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sl_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sl-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_sl_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sl-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_sl_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sl-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sl_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sl-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sq_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sq-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_sq_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sq-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_sq_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sq-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sq_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sq-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sr_denoising` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sr-denoising` | accepted_uploaded | B/C: Known corruption/edit validity or reconstruction |
| `dfm13_wave4_wikipedia_sr_paragraph_reordering` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sr-paragraph-reordering` | accepted_uploaded | B/C: Original-order recovery / valid next block |
| `dfm13_wave4_wikipedia_sr_prefix_continuation` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sr-prefix-continuation` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_wikipedia_sr_span_filling` | `wikimedia/wikipedia` | `schneiderkamplab/dfm13-wave4-wikipedia-sr-span-filling` | accepted_uploaded | B/C: Masked source-span recovery |
| `dfm13_wave4_opus_be_en` | `schneiderkamplab/dfm13-wave4-opus-be-en` | `schneiderkamplab/dfm13-wave4-opus-be-en` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_et` | `schneiderkamplab/dfm13-wave4-opus-bs-et` | `schneiderkamplab/dfm13-wave4-opus-bs-et` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_fa` | `schneiderkamplab/dfm13-wave4-opus-bs-fa` | `schneiderkamplab/dfm13-wave4-opus-bs-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_fi` | `schneiderkamplab/dfm13-wave4-opus-bs-fi` | `schneiderkamplab/dfm13-wave4-opus-bs-fi` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_fo` | `schneiderkamplab/dfm13-wave4-opus-bs-fo` | `schneiderkamplab/dfm13-wave4-opus-bs-fo` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_fr` | `schneiderkamplab/dfm13-wave4-opus-bs-fr` | `schneiderkamplab/dfm13-wave4-opus-bs-fr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_hu` | `schneiderkamplab/dfm13-wave4-opus-bs-hu` | `schneiderkamplab/dfm13-wave4-opus-bs-hu` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_is` | `schneiderkamplab/dfm13-wave4-opus-bs-is` | `schneiderkamplab/dfm13-wave4-opus-bs-is` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_lb` | `schneiderkamplab/dfm13-wave4-opus-bs-lb` | `schneiderkamplab/dfm13-wave4-opus-bs-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_lt` | `schneiderkamplab/dfm13-wave4-opus-bs-lt` | `schneiderkamplab/dfm13-wave4-opus-bs-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_lv` | `schneiderkamplab/dfm13-wave4-opus-bs-lv` | `schneiderkamplab/dfm13-wave4-opus-bs-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_nb` | `schneiderkamplab/dfm13-wave4-opus-bs-nb` | `schneiderkamplab/dfm13-wave4-opus-bs-nb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_nl` | `schneiderkamplab/dfm13-wave4-opus-bs-nl` | `schneiderkamplab/dfm13-wave4-opus-bs-nl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_nn` | `schneiderkamplab/dfm13-wave4-opus-bs-nn` | `schneiderkamplab/dfm13-wave4-opus-bs-nn` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_pl` | `schneiderkamplab/dfm13-wave4-opus-bs-pl` | `schneiderkamplab/dfm13-wave4-opus-bs-pl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_sv` | `schneiderkamplab/dfm13-wave4-opus-bs-sv` | `schneiderkamplab/dfm13-wave4-opus-bs-sv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_bs_uk` | `schneiderkamplab/dfm13-wave4-opus-bs-uk` | `schneiderkamplab/dfm13-wave4-opus-bs-uk` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_fa` | `schneiderkamplab/dfm13-wave4-opus-ca-fa` | `schneiderkamplab/dfm13-wave4-opus-ca-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_hr` | `schneiderkamplab/dfm13-wave4-opus-ca-hr` | `schneiderkamplab/dfm13-wave4-opus-ca-hr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_hu` | `schneiderkamplab/dfm13-wave4-opus-ca-hu` | `schneiderkamplab/dfm13-wave4-opus-ca-hu` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_lb` | `schneiderkamplab/dfm13-wave4-opus-ca-lb` | `schneiderkamplab/dfm13-wave4-opus-ca-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_sl` | `schneiderkamplab/dfm13-wave4-opus-ca-sl` | `schneiderkamplab/dfm13-wave4-opus-ca-sl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_sq` | `schneiderkamplab/dfm13-wave4-opus-ca-sq` | `schneiderkamplab/dfm13-wave4-opus-ca-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_ca_sr` | `schneiderkamplab/dfm13-wave4-opus-ca-sr` | `schneiderkamplab/dfm13-wave4-opus-ca-sr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_cs_fa` | `schneiderkamplab/dfm13-wave4-opus-cs-fa` | `schneiderkamplab/dfm13-wave4-opus-cs-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_cs_lb` | `schneiderkamplab/dfm13-wave4-opus-cs-lb` | `schneiderkamplab/dfm13-wave4-opus-cs-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_cs_sq` | `schneiderkamplab/dfm13-wave4-opus-cs-sq` | `schneiderkamplab/dfm13-wave4-opus-cs-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_da_fa` | `schneiderkamplab/dfm13-wave4-opus-da-fa` | `schneiderkamplab/dfm13-wave4-opus-da-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_da_hr` | `schneiderkamplab/dfm13-wave4-opus-da-hr` | `schneiderkamplab/dfm13-wave4-opus-da-hr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_da_lb` | `schneiderkamplab/dfm13-wave4-opus-da-lb` | `schneiderkamplab/dfm13-wave4-opus-da-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_da_sl` | `schneiderkamplab/dfm13-wave4-opus-da-sl` | `schneiderkamplab/dfm13-wave4-opus-da-sl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_da_sq` | `schneiderkamplab/dfm13-wave4-opus-da-sq` | `schneiderkamplab/dfm13-wave4-opus-da-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_de_lb` | `schneiderkamplab/dfm13-wave4-opus-de-lb` | `schneiderkamplab/dfm13-wave4-opus-de-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_de_sq` | `schneiderkamplab/dfm13-wave4-opus-de-sq` | `schneiderkamplab/dfm13-wave4-opus-de-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_el_fa` | `schneiderkamplab/dfm13-wave4-opus-el-fa` | `schneiderkamplab/dfm13-wave4-opus-el-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_el_lb` | `schneiderkamplab/dfm13-wave4-opus-el-lb` | `schneiderkamplab/dfm13-wave4-opus-el-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_en_lb` | `schneiderkamplab/dfm13-wave4-opus-en-lb` | `schneiderkamplab/dfm13-wave4-opus-en-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_es_fa` | `schneiderkamplab/dfm13-wave4-opus-es-fa` | `schneiderkamplab/dfm13-wave4-opus-es-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_es_lb` | `schneiderkamplab/dfm13-wave4-opus-es-lb` | `schneiderkamplab/dfm13-wave4-opus-es-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_es_sq` | `schneiderkamplab/dfm13-wave4-opus-es-sq` | `schneiderkamplab/dfm13-wave4-opus-es-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_et_fa` | `schneiderkamplab/dfm13-wave4-opus-et-fa` | `schneiderkamplab/dfm13-wave4-opus-et-fa` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_et_hr` | `schneiderkamplab/dfm13-wave4-opus-et-hr` | `schneiderkamplab/dfm13-wave4-opus-et-hr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_et_lb` | `schneiderkamplab/dfm13-wave4-opus-et-lb` | `schneiderkamplab/dfm13-wave4-opus-et-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_et_sl` | `schneiderkamplab/dfm13-wave4-opus-et-sl` | `schneiderkamplab/dfm13-wave4-opus-et-sl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_fi` | `schneiderkamplab/dfm13-wave4-opus-fa-fi` | `schneiderkamplab/dfm13-wave4-opus-fa-fi` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_fo` | `schneiderkamplab/dfm13-wave4-opus-fa-fo` | `schneiderkamplab/dfm13-wave4-opus-fa-fo` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_hr` | `schneiderkamplab/dfm13-wave4-opus-fa-hr` | `schneiderkamplab/dfm13-wave4-opus-fa-hr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_is` | `schneiderkamplab/dfm13-wave4-opus-fa-is` | `schneiderkamplab/dfm13-wave4-opus-fa-is` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_it` | `schneiderkamplab/dfm13-wave4-opus-fa-it` | `schneiderkamplab/dfm13-wave4-opus-fa-it` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_lb` | `schneiderkamplab/dfm13-wave4-opus-fa-lb` | `schneiderkamplab/dfm13-wave4-opus-fa-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_lt` | `schneiderkamplab/dfm13-wave4-opus-fa-lt` | `schneiderkamplab/dfm13-wave4-opus-fa-lt` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_lv` | `schneiderkamplab/dfm13-wave4-opus-fa-lv` | `schneiderkamplab/dfm13-wave4-opus-fa-lv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_nb` | `schneiderkamplab/dfm13-wave4-opus-fa-nb` | `schneiderkamplab/dfm13-wave4-opus-fa-nb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_nn` | `schneiderkamplab/dfm13-wave4-opus-fa-nn` | `schneiderkamplab/dfm13-wave4-opus-fa-nn` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_pl` | `schneiderkamplab/dfm13-wave4-opus-fa-pl` | `schneiderkamplab/dfm13-wave4-opus-fa-pl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_sl` | `schneiderkamplab/dfm13-wave4-opus-fa-sl` | `schneiderkamplab/dfm13-wave4-opus-fa-sl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_sq` | `schneiderkamplab/dfm13-wave4-opus-fa-sq` | `schneiderkamplab/dfm13-wave4-opus-fa-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_sr` | `schneiderkamplab/dfm13-wave4-opus-fa-sr` | `schneiderkamplab/dfm13-wave4-opus-fa-sr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_sv` | `schneiderkamplab/dfm13-wave4-opus-fa-sv` | `schneiderkamplab/dfm13-wave4-opus-fa-sv` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fa_uk` | `schneiderkamplab/dfm13-wave4-opus-fa-uk` | `schneiderkamplab/dfm13-wave4-opus-fa-uk` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fi_lb` | `schneiderkamplab/dfm13-wave4-opus-fi-lb` | `schneiderkamplab/dfm13-wave4-opus-fi-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fi_sq` | `schneiderkamplab/dfm13-wave4-opus-fi-sq` | `schneiderkamplab/dfm13-wave4-opus-fi-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fo_hr` | `schneiderkamplab/dfm13-wave4-opus-fo-hr` | `schneiderkamplab/dfm13-wave4-opus-fo-hr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fo_lb` | `schneiderkamplab/dfm13-wave4-opus-fo-lb` | `schneiderkamplab/dfm13-wave4-opus-fo-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fo_sl` | `schneiderkamplab/dfm13-wave4-opus-fo-sl` | `schneiderkamplab/dfm13-wave4-opus-fo-sl` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fo_sq` | `schneiderkamplab/dfm13-wave4-opus-fo-sq` | `schneiderkamplab/dfm13-wave4-opus-fo-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fo_sr` | `schneiderkamplab/dfm13-wave4-opus-fo-sr` | `schneiderkamplab/dfm13-wave4-opus-fo-sr` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fr_lb` | `schneiderkamplab/dfm13-wave4-opus-fr-lb` | `schneiderkamplab/dfm13-wave4-opus-fr-lb` | accepted_uploaded | C: Translation adequacy or source-target match |
| `dfm13_wave4_opus_fr_sq` | `schneiderkamplab/dfm13-wave4-opus-fr-sq` | `schneiderkamplab/dfm13-wave4-opus-fr-sq` | accepted_uploaded | C: Translation adequacy or source-target match |
