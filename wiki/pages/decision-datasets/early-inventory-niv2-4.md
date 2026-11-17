---
type: Dataset Inventory
title: Early Sapient niv2 inventory 4
description: Original Sapient subtask identifiers and provisional bounded-decision mapping.
tags: [data, decision-datasets, sapient, inventory]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# Early Sapient niv2 inventory 4

See the [A/B/C/D rubric](../decision-datasets.md#common-assessment-scale),
[recipes](conversion-recipes.md), and [early datasets](early-datasets.md) for route definitions, evidence, policy caveats,
and exact path reconstruction. These are name-based candidate routes, not row audits
or permission to train. A requires retained labels/options; B requires a valid checker.
D-review explicitly defers a subtask whose target contract is not established here.
Policy is today's path-filter result, not historical inclusion or legal clearance.

| Exact task/file identifier | Template codes | Route | Current path filter |
|---|---|---|---|
| `flan/task906_dialogre_identify_names.parquet` | NF,NZ | C-text | denied |
| `flan/task907_dialogre_identify_relationships.parquet` | NF,NZ | C-text | denied |
| `flan/task908_dialogre_identify_familial_relationships.parquet` | NF,NZ | C-text | denied |
| `flan/task909_dialogre_prevalent_speakers.parquet` | NF,NZ | C-text | denied |
| `flan/task910_bianet_classification.parquet` | NF,NZ | A-label | default |
| `flan/task911_bianet_translation.parquet` | NF,NZ | C-text | default |
| `flan/task912_bianet_classification.parquet` | NF,NZ | A-label | default |
| `flan/task913_bianet_translation.parquet` | NF,NZ | C-text | default |
| `flan/task914_bianet_translation.parquet` | NF,NZ | C-text | default |
| `flan/task917_coqa_question_generation.parquet` | NF,NZ | C-text | override |
| `flan/task918_coqa_answer_generation.parquet` | NF,NZ | C-answer | override |
| `flan/task919_coqa_incorrect_answer_generation.parquet` | NF,NZ | C-neg | override |
| `flan/task921_code_x_glue_information_retreival.parquet` | NF,NZ | A-label | override |
| `flan/task922_event2mind_word_generation.parquet` | NF,NZ | D-review | default |
| `flan/task923_event2mind_classifier.parquet` | NF,NZ | D-review | default |
| `flan/task924_event2mind_word_generation.parquet` | NF,NZ | D-review | default |
| `flan/task925_coached_conv_pref_classifier.parquet` | NF,NZ | D-review | default |
| `flan/task926_coached_conv_pref_word_generation.parquet` | NF,NZ | D-review | default |
| `flan/task927_yelp_negative_to_positive_style_transfer.parquet` | NF,NZ | D-review | denied |
| `flan/task928_yelp_positive_to_negative_style_transfer.parquet` | NF,NZ | D-review | denied |
| `flan/task929_products_reviews_classification.parquet` | NF,NZ | A-label | denied |
| `flan/task930_dailydialog_classification.parquet` | NF,NZ | C-text | override |
| `flan/task931_dailydialog_classification.parquet` | NF,NZ | C-text | override |
| `flan/task932_dailydialog_classification.parquet` | NF,NZ | C-text | override |
| `flan/task933_wiki_auto_style_transfer.parquet` | NF,NZ | D-review | default |
| `flan/task934_turk_simplification.parquet` | NF,NZ | D-review | default |
| `flan/task935_defeasible_nli_atomic_classification.parquet` | NF,NZ | A-label | default |
| `flan/task936_defeasible_nli_snli_classification.parquet` | NF,NZ | A-label | override |
| `flan/task937_defeasible_nli_social_classification.parquet` | NF,NZ | A-label | default |
| `flan/task938_copa_hi_commonsense_reasoning.parquet` | NF,NZ | D-review | override |
| `flan/task939_copa_hi_commonsense_cause_effect.parquet` | NF,NZ | D-review | override |
| `flan/task940_copa_gu_commonsense_reasoning.parquet` | NF,NZ | D-review | override |
| `flan/task941_copa_gu_commonsense_cause_effect.parquet` | NF,NZ | D-review | override |
| `flan/task942_copa_mr_commonsense_reasoning.parquet` | NF,NZ | D-review | override |
| `flan/task943_copa_mr_commonsense_cause_effect.parquet` | NF,NZ | D-review | override |
| `flan/task944_wiki_cloze_as_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task945_wiki_cloze_bn_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task946_wiki_cloze_gu_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task947_wiki_cloze_hi_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task948_wiki_cloze_kn_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task949_wiki_cloze_ml_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task950_wiki_cloze_mr_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task951_wiki_cloze_or_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task952_wiki_cloze_pa_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task953_wiki_cloze_ta_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task954_wiki_cloze_te_multiple_choice_question_answering.parquet` | NF,NZ | A-options | default |
| `flan/task955_wiki_auto_style_transfer.parquet` | NF,NZ | D-review | default |
| `flan/task956_leetcode_420_strong_password_check.parquet` | NF,NZ | D-review | default |
| `flan/task957_e2e_nlg_text_generation_generate.parquet` | NF,NZ | C-text | default |
| `flan/task958_e2e_nlg_text_generation_parse.parquet` | NF,NZ | C-text | default |
| `flan/task959_e2e_nlg_text_generation_identify.parquet` | NF,NZ | C-text | default |
| `flan/task960_ancora-ca-ner_named_entity_recognition.parquet` | NF,NZ | D-review | default |
| `flan/task961_ancora-ca-ner_text_auto_completion.parquet` | NF,NZ | D-review | default |
| `flan/task962_ancora-ca-ner_missing_word_prediction.parquet` | NF,NZ | D-review | default |
| `flan/task963_librispeech_asr_next_word_prediction.parquet` | NF,NZ | D-review | default |
| `flan/task964_librispeech_asr_text_auto_completion.parquet` | NF,NZ | D-review | default |
| `flan/task965_librispeech_asr_missing_word_prediction.parquet` | NF,NZ | D-review | default |
| `flan/task966_ruletaker_fact_checking_based_on_given_context.parquet` | NF,NZ | A-label | default |
| `flan/task967_ruletaker_incorrect_fact_generation_based_on_given_paragraph.parquet` | NF,NZ | A-label | default |
| `flan/task968_xcopa_commonsense_reasoning_et.parquet` | NF,NZ | D-review | override |
| `flan/task969_xcopa_commonsense_cause_effect_et.parquet` | NF,NZ | D-review | override |
| `flan/task970_sherliic_causal_relationship.parquet` | NF,NZ | D-review | default |
| `flan/task974_prachathai67k_sentiment_classification.parquet` | NF,NZ | C-text | denied |
| `flan/task975_prachathai67k_same_genre_classification.parquet` | NF,NZ | C-text | denied |
| `flan/task976_pib_indian_language_identification.parquet` | NF,NZ | A-label | default |
| `flan/task977_pib_translation_oriya_urdu.parquet` | NF,NZ | C-text | default |
| `flan/task978_pib_translation_urdu_oriya.parquet` | NF,NZ | C-text | default |
| `flan/task979_pib_translation_malayalam_oriya.parquet` | NF,NZ | C-text | default |
| `flan/task980_pib_translation_oriya_malayalam.parquet` | NF,NZ | C-text | default |
| `flan/task981_pib_translation_bengali_tamil.parquet` | NF,NZ | C-text | default |
| `flan/task982_pib_translation_tamil_bengali.parquet` | NF,NZ | C-text | default |
| `flan/task983_pib_translation_gujarati_marathi.parquet` | NF,NZ | C-text | default |
| `flan/task984_pib_translation_marathi_gujarati.parquet` | NF,NZ | C-text | default |
| `flan/task985_pib_translation_hindi_oriya.parquet` | NF,NZ | C-text | default |
| `flan/task986_pib_translation_oriya_hindi.parquet` | NF,NZ | C-text | default |
| `flan/task987_pib_translation_english_oriya.parquet` | NF,NZ | C-text | default |
| `flan/task988_pib_translation_oriya_english.parquet` | NF,NZ | C-text | default |
| `flan/task989_pib_translation_marathi_urdu.parquet` | NF,NZ | C-text | default |
| `flan/task990_pib_translation_urdu_marathi.parquet` | NF,NZ | C-text | default |
| `flan/task991_pib_translation_english_tamil.parquet` | NF,NZ | C-text | default |
| `flan/task992_pib_translation_tamil_english.parquet` | NF,NZ | C-text | default |
| `flan/task993_pib_translation_hindi_tamil.parquet` | NF,NZ | C-text | default |
| `flan/task994_pib_translation_tamil_hindi.parquet` | NF,NZ | C-text | default |
| `flan/task995_pib_translation_bengali_english.parquet` | NF,NZ | C-text | default |
| `flan/task996_pib_translation_english_bengali.parquet` | NF,NZ | C-text | default |
| `flan/task997_pib_translation_bengali_oriya.parquet` | NF,NZ | C-text | default |
| `flan/task998_pib_translation_oriya_bengali.parquet` | NF,NZ | C-text | default |
| `flan/task999_pib_translation_malayalam_tamil.parquet` | NF,NZ | C-text | default |
