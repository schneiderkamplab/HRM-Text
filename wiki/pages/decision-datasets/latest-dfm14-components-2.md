---
type: Reference
title: DFM14 Exact Components 2
description: Exact registered DFM14 component names and Hugging Face packages with decision suitability.
tags: [data, dfm14, decision, inventory]
status: draft
last_updated: 2026-10-21
confidence: high
---
# DFM14 Exact Components 2

[Latest-source analysis and grade definitions](latest-datasets.md).
[Other component part](latest-dfm14-components-1.md).

Direct projection of `config/dfm14_sources.json` on 2026-10-21, inventory
positions 141-277 of 277. Status for every row: registered/released
DFM14 addition, inherited by DFM15 subject to its selections/repairs. Rows are
inventory counts, not decision-labelled yield or verified sampled exposure.
HF IDs identify exports; upstream raw lineage may require row provenance.
Grade is a proposal: A existing acceptability labels; B/C mechanical source
identity or corruption predicates only with validity filters, otherwise C;
C requires validated alternatives/adjudication. See analysis for each family.

| Exact component | Exact HF ID | Inventory rows | Grade |
|---|---|---:|---|
| `dfm14-ja-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-ja-synthetic-tool-dialogue-r1` | 1962 | C |
| `dfm14-ja-translation-r1` | `schneiderkamplab/dfm14-ja-translation-r1` | 583325 | C |
| `dfm14-ko-denoising-r1` | `schneiderkamplab/dfm14-ko-denoising-r1` | 31869 | B/C |
| `dfm14-ko-instruction-r1` | `schneiderkamplab/dfm14-ko-instruction-r1` | 45115 | C |
| `dfm14-ko-paragraph-reordering-r1` | `schneiderkamplab/dfm14-ko-paragraph-reordering-r1` | 9656 | B/C |
| `dfm14-ko-prefix-continuation-r1` | `schneiderkamplab/dfm14-ko-prefix-continuation-r1` | 37496 | C |
| `dfm14-ko-span-filling-r1` | `schneiderkamplab/dfm14-ko-span-filling-r1` | 9995 | B/C |
| `dfm14-ko-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-ko-synthetic-grounded-instruct-r1` | 9868 | C |
| `dfm14-ko-synthetic-math-code-r1` | `schneiderkamplab/dfm14-ko-synthetic-math-code-r1` | 652 | C |
| `dfm14-ko-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-ko-synthetic-multiturn-r1` | 7469 | C |
| `dfm14-ko-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-ko-synthetic-openhermes-r1` | 6270 | C |
| `dfm14-ko-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-ko-synthetic-summary-rewrite-r1` | 4856 | C |
| `dfm14-ko-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-ko-synthetic-tool-dialogue-r1` | 1926 | C |
| `dfm14-ko-translation-r1` | `schneiderkamplab/dfm14-ko-translation-r1` | 11920 | C |
| `dfm14-lb-translation-r1` | `schneiderkamplab/dfm14-lb-translation-r1` | 91 | C |
| `dfm14-lt-translation-r1` | `schneiderkamplab/dfm14-lt-translation-r1` | 59010 | C |
| `dfm14-lv-translation-r1` | `schneiderkamplab/dfm14-lv-translation-r1` | 1205 | C |
| `dfm14-mk-denoising-r1` | `schneiderkamplab/dfm14-mk-denoising-r1` | 18156 | B/C |
| `dfm14-mk-instruction-r1` | `schneiderkamplab/dfm14-mk-instruction-r1` | 18642 | C |
| `dfm14-mk-paragraph-reordering-r1` | `schneiderkamplab/dfm14-mk-paragraph-reordering-r1` | 6165 | B/C |
| `dfm14-mk-prefix-continuation-r1` | `schneiderkamplab/dfm14-mk-prefix-continuation-r1` | 18998 | C |
| `dfm14-mk-span-filling-r1` | `schneiderkamplab/dfm14-mk-span-filling-r1` | 7767 | B/C |
| `dfm14-mk-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-mk-synthetic-grounded-instruct-r1` | 19827 | C |
| `dfm14-mk-synthetic-math-code-r1` | `schneiderkamplab/dfm14-mk-synthetic-math-code-r1` | 1752 | C |
| `dfm14-mk-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-mk-synthetic-multiturn-r1` | 14946 | C |
| `dfm14-mk-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-mk-synthetic-openhermes-r1` | 12440 | C |
| `dfm14-mk-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-mk-synthetic-summary-rewrite-r1` | 9889 | C |
| `dfm14-mk-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-mk-synthetic-tool-dialogue-r1` | 3968 | C |
| `dfm14-mk-translation-r1` | `schneiderkamplab/dfm14-mk-translation-r1` | 100748 | C |
| `dfm14-mt-denoising-r1` | `schneiderkamplab/dfm14-mt-denoising-r1` | 26946 | B/C |
| `dfm14-mt-instruction-r1` | `schneiderkamplab/dfm14-mt-instruction-r1` | 16778 | C |
| `dfm14-mt-paragraph-reordering-r1` | `schneiderkamplab/dfm14-mt-paragraph-reordering-r1` | 1517 | B/C |
| `dfm14-mt-prefix-continuation-r1` | `schneiderkamplab/dfm14-mt-prefix-continuation-r1` | 19720 | C |
| `dfm14-mt-span-filling-r1` | `schneiderkamplab/dfm14-mt-span-filling-r1` | 16085 | B/C |
| `dfm14-mt-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-mt-synthetic-grounded-instruct-r1` | 18565 | C |
| `dfm14-mt-synthetic-math-code-r1` | `schneiderkamplab/dfm14-mt-synthetic-math-code-r1` | 1118 | C |
| `dfm14-mt-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-mt-synthetic-multiturn-r1` | 12489 | C |
| `dfm14-mt-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-mt-synthetic-openhermes-r1` | 9481 | C |
| `dfm14-mt-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-mt-synthetic-summary-rewrite-r1` | 9300 | C |
| `dfm14-mt-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-mt-synthetic-tool-dialogue-r1` | 3484 | C |
| `dfm14-mt-translation-r1` | `schneiderkamplab/dfm14-mt-translation-r1` | 8092 | C |
| `dfm14-nb-translation-r1` | `schneiderkamplab/dfm14-nb-translation-r1` | 6177 | C |
| `dfm14-nl-translation-r1` | `schneiderkamplab/dfm14-nl-translation-r1` | 47027 | C |
| `dfm14-nn-translation-r1` | `schneiderkamplab/dfm14-nn-translation-r1` | 568 | C |
| `dfm14-pl-denoising-r1` | `schneiderkamplab/dfm14-pl-denoising-r1` | 786 | B/C |
| `dfm14-pl-paragraph-reordering-r1` | `schneiderkamplab/dfm14-pl-paragraph-reordering-r1` | 84 | B/C |
| `dfm14-pl-prefix-continuation-r1` | `schneiderkamplab/dfm14-pl-prefix-continuation-r1` | 829 | C |
| `dfm14-pl-span-filling-r1` | `schneiderkamplab/dfm14-pl-span-filling-r1` | 413 | B/C |
| `dfm14-pl-translation-r1` | `schneiderkamplab/dfm14-pl-translation-r1` | 62780 | C |
| `dfm14-pt-pt-translation-r1` | `schneiderkamplab/dfm14-pt-pt-translation-r1` | 77395 | C |
| `dfm14-ro-translation-r1` | `schneiderkamplab/dfm14-ro-translation-r1` | 10995 | C |
| `dfm14-ru-denoising-r1` | `schneiderkamplab/dfm14-ru-denoising-r1` | 146772 | B/C |
| `dfm14-ru-instruction-r1` | `schneiderkamplab/dfm14-ru-instruction-r1` | 72049 | C |
| `dfm14-ru-paragraph-reordering-r1` | `schneiderkamplab/dfm14-ru-paragraph-reordering-r1` | 32640 | B/C |
| `dfm14-ru-prefix-continuation-r1` | `schneiderkamplab/dfm14-ru-prefix-continuation-r1` | 162245 | C |
| `dfm14-ru-span-filling-r1` | `schneiderkamplab/dfm14-ru-span-filling-r1` | 95895 | B/C |
| `dfm14-ru-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-ru-synthetic-grounded-instruct-r1` | 9850 | C |
| `dfm14-ru-synthetic-math-code-r1` | `schneiderkamplab/dfm14-ru-synthetic-math-code-r1` | 573 | C |
| `dfm14-ru-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-ru-synthetic-multiturn-r1` | 7486 | C |
| `dfm14-ru-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-ru-synthetic-openhermes-r1` | 6365 | C |
| `dfm14-ru-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-ru-synthetic-summary-rewrite-r1` | 4959 | C |
| `dfm14-ru-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-ru-synthetic-tool-dialogue-r1` | 1901 | C |
| `dfm14-ru-translation-r1` | `schneiderkamplab/dfm14-ru-translation-r1` | 1556132 | C |
| `dfm14-sk-translation-r1` | `schneiderkamplab/dfm14-sk-translation-r1` | 15612 | C |
| `dfm14-sl-translation-r1` | `schneiderkamplab/dfm14-sl-translation-r1` | 1905 | C |
| `dfm14-sq-translation-r1` | `schneiderkamplab/dfm14-sq-translation-r1` | 412 | C |
| `dfm14-sr-translation-r1` | `schneiderkamplab/dfm14-sr-translation-r1` | 8392 | C |
| `dfm14-sv-translation-r1` | `schneiderkamplab/dfm14-sv-translation-r1` | 8328 | C |
| `dfm14-tr-denoising-r1` | `schneiderkamplab/dfm14-tr-denoising-r1` | 17787 | B/C |
| `dfm14-tr-instruction-r1` | `schneiderkamplab/dfm14-tr-instruction-r1` | 19575 | C |
| `dfm14-tr-paragraph-reordering-r1` | `schneiderkamplab/dfm14-tr-paragraph-reordering-r1` | 5158 | B/C |
| `dfm14-tr-prefix-continuation-r1` | `schneiderkamplab/dfm14-tr-prefix-continuation-r1` | 20123 | C |
| `dfm14-tr-span-filling-r1` | `schneiderkamplab/dfm14-tr-span-filling-r1` | 9743 | B/C |
| `dfm14-tr-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-tr-synthetic-grounded-instruct-r1` | 9858 | C |
| `dfm14-tr-synthetic-math-code-r1` | `schneiderkamplab/dfm14-tr-synthetic-math-code-r1` | 406 | C |
| `dfm14-tr-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-tr-synthetic-multiturn-r1` | 7485 | C |
| `dfm14-tr-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-tr-synthetic-openhermes-r1` | 6360 | C |
| `dfm14-tr-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-tr-synthetic-summary-rewrite-r1` | 4951 | C |
| `dfm14-tr-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-tr-synthetic-tool-dialogue-r1` | 1959 | C |
| `dfm14-tr-translation-r1` | `schneiderkamplab/dfm14-tr-translation-r1` | 1046681 | C |
| `dfm14-uk-translation-r1` | `schneiderkamplab/dfm14-uk-translation-r1` | 47013 | C |
| `dfm14-vi-denoising-r1` | `schneiderkamplab/dfm14-vi-denoising-r1` | 13604 | B/C |
| `dfm14-vi-instruction-r1` | `schneiderkamplab/dfm14-vi-instruction-r1` | 43932 | C |
| `dfm14-vi-paragraph-reordering-r1` | `schneiderkamplab/dfm14-vi-paragraph-reordering-r1` | 1992 | B/C |
| `dfm14-vi-prefix-continuation-r1` | `schneiderkamplab/dfm14-vi-prefix-continuation-r1` | 15134 | C |
| `dfm14-vi-span-filling-r1` | `schneiderkamplab/dfm14-vi-span-filling-r1` | 5807 | B/C |
| `dfm14-vi-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-vi-synthetic-grounded-instruct-r1` | 9868 | C |
| `dfm14-vi-synthetic-math-code-r1` | `schneiderkamplab/dfm14-vi-synthetic-math-code-r1` | 423 | C |
| `dfm14-vi-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-vi-synthetic-multiturn-r1` | 7483 | C |
| `dfm14-vi-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-vi-synthetic-openhermes-r1` | 6272 | C |
| `dfm14-vi-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-vi-synthetic-summary-rewrite-r1` | 4956 | C |
| `dfm14-vi-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-vi-synthetic-tool-dialogue-r1` | 1981 | C |
| `dfm14-vi-translation-r1` | `schneiderkamplab/dfm14-vi-translation-r1` | 19468 | C |
| `dfm14-zh-denoising-r1` | `schneiderkamplab/dfm14-zh-denoising-r1` | 98817 | B/C |
| `dfm14-zh-instruction-r1` | `schneiderkamplab/dfm14-zh-instruction-r1` | 820500 | C |
| `dfm14-zh-paragraph-reordering-r1` | `schneiderkamplab/dfm14-zh-paragraph-reordering-r1` | 25820 | B/C |
| `dfm14-zh-prefix-continuation-r1` | `schneiderkamplab/dfm14-zh-prefix-continuation-r1` | 96447 | C |
| `dfm14-zh-span-filling-r1` | `schneiderkamplab/dfm14-zh-span-filling-r1` | 82637 | B/C |
| `dfm14-zh-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-zh-synthetic-grounded-instruct-r1` | 9463 | C |
| `dfm14-zh-synthetic-math-code-r1` | `schneiderkamplab/dfm14-zh-synthetic-math-code-r1` | 1097 | C |
| `dfm14-zh-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-zh-synthetic-multiturn-r1` | 7480 | C |
| `dfm14-zh-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-zh-synthetic-openhermes-r1` | 5731 | C |
| `dfm14-zh-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-zh-synthetic-summary-rewrite-r1` | 4920 | C |
| `dfm14-zh-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-zh-synthetic-tool-dialogue-r1` | 1998 | C |
| `dfm14-zh-translation-r1` | `schneiderkamplab/dfm14-zh-translation-r1` | 143614 | C |
| `dfm14_dala_v2_compact_id_acceptability` | `schneiderkamplab/dfm14-dala-v2-id-compact` | 879440 | A |
| `dfm14_dala_v2_compact_id_correction` | `schneiderkamplab/dfm14-dala-v2-id-compact` | 879440 | C |
| `dfm14_dala_v2_compact_eu_acceptability` | `schneiderkamplab/dfm14-dala-v2-eu-compact` | 887025 | A |
| `dfm14_dala_v2_compact_eu_correction` | `schneiderkamplab/dfm14-dala-v2-eu-compact` | 887025 | C |
| `dfm14_dala_v2_compact_gl_acceptability` | `schneiderkamplab/dfm14-dala-v2-gl-compact` | 807437 | A |
| `dfm14_dala_v2_compact_gl_correction` | `schneiderkamplab/dfm14-dala-v2-gl-compact` | 807437 | C |
| `dfm14_dala_v2_compact_ga_acceptability` | `schneiderkamplab/dfm14-dala-v2-ga-compact` | 824204 | A |
| `dfm14_dala_v2_compact_ga_correction` | `schneiderkamplab/dfm14-dala-v2-ga-compact` | 824204 | C |
| `dfm14_dala_v2_compact_ko_acceptability` | `schneiderkamplab/dfm14-dala-v2-ko-compact` | 833536 | A |
| `dfm14_dala_v2_compact_ko_correction` | `schneiderkamplab/dfm14-dala-v2-ko-compact` | 833536 | C |
| `dfm14_dala_v2_compact_mk_acceptability` | `schneiderkamplab/dfm14-dala-v2-mk-compact` | 795977 | A |
| `dfm14_dala_v2_compact_mk_correction` | `schneiderkamplab/dfm14-dala-v2-mk-compact` | 795977 | C |
| `dfm14_dala_v2_compact_mt_acceptability` | `schneiderkamplab/dfm14-dala-v2-mt-compact` | 807999 | A |
| `dfm14_dala_v2_compact_mt_correction` | `schneiderkamplab/dfm14-dala-v2-mt-compact` | 807999 | C |
| `dfm14_dala_v2_compact_ja_acceptability` | `schneiderkamplab/dfm14-dala-v2-ja-compact` | 911381 | A |
| `dfm14_dala_v2_compact_ja_correction` | `schneiderkamplab/dfm14-dala-v2-ja-compact` | 911381 | C |
| `dfm14_dala_v2_compact_cy_acceptability` | `schneiderkamplab/dfm14-dala-v2-cy-compact` | 1046231 | A |
| `dfm14_dala_v2_compact_cy_correction` | `schneiderkamplab/dfm14-dala-v2-cy-compact` | 1046231 | C |
| `dfm14_dala_v2_compact_ar_acceptability` | `schneiderkamplab/dfm14-dala-v2-ar-compact` | 850861 | A |
| `dfm14_dala_v2_compact_ar_correction` | `schneiderkamplab/dfm14-dala-v2-ar-compact` | 850861 | C |
| `dfm14_dala_v2_compact_tr_acceptability` | `schneiderkamplab/dfm14-dala-v2-tr-compact` | 920794 | A |
| `dfm14_dala_v2_compact_tr_correction` | `schneiderkamplab/dfm14-dala-v2-tr-compact` | 920794 | C |
| `dfm14_dala_v2_compact_ru_acceptability` | `schneiderkamplab/dfm14-dala-v2-ru-compact` | 823728 | A |
| `dfm14_dala_v2_compact_ru_correction` | `schneiderkamplab/dfm14-dala-v2-ru-compact` | 823728 | C |
| `dfm14_dala_v2_compact_vi_acceptability` | `schneiderkamplab/dfm14-dala-v2-vi-compact` | 859656 | A |
| `dfm14_dala_v2_compact_vi_correction` | `schneiderkamplab/dfm14-dala-v2-vi-compact` | 859656 | C |
| `dfm14_dala_v2_compact_he_acceptability` | `schneiderkamplab/dfm14-dala-v2-he-compact` | 1049799 | A |
| `dfm14_dala_v2_compact_he_correction` | `schneiderkamplab/dfm14-dala-v2-he-compact` | 1049799 | C |
| `dfm14_dala_v2_compact_hi_acceptability` | `schneiderkamplab/dfm14-dala-v2-hi-compact` | 1038773 | A |
| `dfm14_dala_v2_compact_hi_correction` | `schneiderkamplab/dfm14-dala-v2-hi-compact` | 1038773 | C |
| `dfm14_dala_v2_compact_zh_acceptability` | `schneiderkamplab/dfm14-dala-v2-zh-compact` | 1037788 | A |
| `dfm14_dala_v2_compact_zh_correction` | `schneiderkamplab/dfm14-dala-v2-zh-compact` | 1037788 | C |
