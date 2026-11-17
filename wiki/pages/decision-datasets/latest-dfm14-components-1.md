---
type: Reference
title: DFM14 Exact Components 1
description: Exact registered DFM14 component names and Hugging Face packages with decision suitability.
tags: [data, dfm14, decision, inventory]
status: draft
last_updated: 2026-10-21
confidence: high
---
# DFM14 Exact Components 1

[Latest-source analysis and grade definitions](latest-datasets.md).
[Other component part](latest-dfm14-components-2.md).

Direct projection of `config/dfm14_sources.json` on 2026-10-21, inventory
positions 1-140 of 277. Status for every row: registered/released
DFM14 addition, inherited by DFM15 subject to its selections/repairs. Rows are
inventory counts, not decision-labelled yield or verified sampled exposure.
HF IDs identify exports; upstream raw lineage may require row provenance.
Grade is a proposal: A existing acceptability labels; B/C mechanical source
identity or corruption predicates only with validity filters, otherwise C;
C requires validated alternatives/adjudication. See analysis for each family.

| Exact component | Exact HF ID | Inventory rows | Grade |
|---|---|---:|---|
| `dfm14-ar-denoising-r1` | `schneiderkamplab/dfm14-ar-denoising-r1` | 77801 | B/C |
| `dfm14-ar-instruction-r1` | `schneiderkamplab/dfm14-ar-instruction-r1` | 63808 | C |
| `dfm14-ar-paragraph-reordering-r1` | `schneiderkamplab/dfm14-ar-paragraph-reordering-r1` | 19997 | B/C |
| `dfm14-ar-prefix-continuation-r1` | `schneiderkamplab/dfm14-ar-prefix-continuation-r1` | 85279 | C |
| `dfm14-ar-span-filling-r1` | `schneiderkamplab/dfm14-ar-span-filling-r1` | 38707 | B/C |
| `dfm14-ar-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-ar-synthetic-grounded-instruct-r1` | 9961 | C |
| `dfm14-ar-synthetic-math-code-r1` | `schneiderkamplab/dfm14-ar-synthetic-math-code-r1` | 757 | C |
| `dfm14-ar-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-ar-synthetic-multiturn-r1` | 7486 | C |
| `dfm14-ar-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-ar-synthetic-openhermes-r1` | 6425 | C |
| `dfm14-ar-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-ar-synthetic-summary-rewrite-r1` | 4967 | C |
| `dfm14-ar-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-ar-synthetic-tool-dialogue-r1` | 1978 | C |
| `dfm14-ar-translation-r1` | `schneiderkamplab/dfm14-ar-translation-r1` | 62629 | C |
| `dfm14-be-translation-r1` | `schneiderkamplab/dfm14-be-translation-r1` | 7866 | C |
| `dfm14-bg-translation-r1` | `schneiderkamplab/dfm14-bg-translation-r1` | 8055 | C |
| `dfm14-bs-translation-r1` | `schneiderkamplab/dfm14-bs-translation-r1` | 213 | C |
| `dfm14-ca-translation-r1` | `schneiderkamplab/dfm14-ca-translation-r1` | 1580 | C |
| `dfm14-cs-translation-r1` | `schneiderkamplab/dfm14-cs-translation-r1` | 15925 | C |
| `dfm14-cy-denoising-r1` | `schneiderkamplab/dfm14-cy-denoising-r1` | 8517 | B/C |
| `dfm14-cy-instruction-r1` | `schneiderkamplab/dfm14-cy-instruction-r1` | 16552 | C |
| `dfm14-cy-paragraph-reordering-r1` | `schneiderkamplab/dfm14-cy-paragraph-reordering-r1` | 1225 | B/C |
| `dfm14-cy-prefix-continuation-r1` | `schneiderkamplab/dfm14-cy-prefix-continuation-r1` | 9235 | C |
| `dfm14-cy-span-filling-r1` | `schneiderkamplab/dfm14-cy-span-filling-r1` | 3412 | B/C |
| `dfm14-cy-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-cy-synthetic-grounded-instruct-r1` | 18956 | C |
| `dfm14-cy-synthetic-math-code-r1` | `schneiderkamplab/dfm14-cy-synthetic-math-code-r1` | 1239 | C |
| `dfm14-cy-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-cy-synthetic-multiturn-r1` | 13626 | C |
| `dfm14-cy-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-cy-synthetic-openhermes-r1` | 10057 | C |
| `dfm14-cy-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-cy-synthetic-summary-rewrite-r1` | 9567 | C |
| `dfm14-cy-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-cy-synthetic-tool-dialogue-r1` | 3796 | C |
| `dfm14-cy-translation-r1` | `schneiderkamplab/dfm14-cy-translation-r1` | 1703 | C |
| `dfm14-da-translation-r1` | `schneiderkamplab/dfm14-da-translation-r1` | 12356 | C |
| `dfm14-de-translation-r1` | `schneiderkamplab/dfm14-de-translation-r1` | 303768 | C |
| `dfm14-el-translation-r1` | `schneiderkamplab/dfm14-el-translation-r1` | 10247 | C |
| `dfm14-en-instruction-r1` | `schneiderkamplab/dfm14-en-instruction-r1` | 1077985 | C |
| `dfm14-en-instruction-r2` | `schneiderkamplab/dfm14-en-instruction-r2` | 131332 | C |
| `dfm14-en-synthetic-commonsense-r1` | `schneiderkamplab/dfm14-en-synthetic-commonsense-r1` | 99967 | C |
| `dfm14-en-synthetic-evidence-r1` | `schneiderkamplab/dfm14-en-synthetic-evidence-r1` | 24746 | C |
| `dfm14-en-synthetic-explanatory-qa-r1` | `schneiderkamplab/dfm14-en-synthetic-explanatory-qa-r1` | 72122 | C |
| `dfm14-en-synthetic-science-r1` | `schneiderkamplab/dfm14-en-synthetic-science-r1` | 99305 | C |
| `dfm14-en-synthetic-textbook-r1` | `schneiderkamplab/dfm14-en-synthetic-textbook-r1` | 142628 | C |
| `dfm14-en-translation-r1` | `schneiderkamplab/dfm14-en-translation-r1` | 1798967 | C |
| `dfm14-es-translation-r1` | `schneiderkamplab/dfm14-es-translation-r1` | 255697 | C |
| `dfm14-et-translation-r1` | `schneiderkamplab/dfm14-et-translation-r1` | 1560 | C |
| `dfm14-eu-denoising-r1` | `schneiderkamplab/dfm14-eu-denoising-r1` | 11394 | B/C |
| `dfm14-eu-instruction-r1` | `schneiderkamplab/dfm14-eu-instruction-r1` | 56309 | C |
| `dfm14-eu-paragraph-reordering-r1` | `schneiderkamplab/dfm14-eu-paragraph-reordering-r1` | 1573 | B/C |
| `dfm14-eu-prefix-continuation-r1` | `schneiderkamplab/dfm14-eu-prefix-continuation-r1` | 12926 | C |
| `dfm14-eu-span-filling-r1` | `schneiderkamplab/dfm14-eu-span-filling-r1` | 5892 | B/C |
| `dfm14-eu-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-eu-synthetic-grounded-instruct-r1` | 19097 | C |
| `dfm14-eu-synthetic-math-code-r1` | `schneiderkamplab/dfm14-eu-synthetic-math-code-r1` | 770 | C |
| `dfm14-eu-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-eu-synthetic-multiturn-r1` | 14421 | C |
| `dfm14-eu-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-eu-synthetic-openhermes-r1` | 11274 | C |
| `dfm14-eu-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-eu-synthetic-summary-rewrite-r1` | 9174 | C |
| `dfm14-eu-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-eu-synthetic-tool-dialogue-r1` | 3887 | C |
| `dfm14-eu-translation-r1` | `schneiderkamplab/dfm14-eu-translation-r1` | 7522 | C |
| `dfm14-fa-denoising-r1` | `schneiderkamplab/dfm14-fa-denoising-r1` | 4744 | B/C |
| `dfm14-fa-paragraph-reordering-r1` | `schneiderkamplab/dfm14-fa-paragraph-reordering-r1` | 711 | B/C |
| `dfm14-fa-prefix-continuation-r1` | `schneiderkamplab/dfm14-fa-prefix-continuation-r1` | 4601 | C |
| `dfm14-fa-span-filling-r1` | `schneiderkamplab/dfm14-fa-span-filling-r1` | 1694 | B/C |
| `dfm14-fa-translation-r1` | `schneiderkamplab/dfm14-fa-translation-r1` | 2061 | C |
| `dfm14-fi-translation-r1` | `schneiderkamplab/dfm14-fi-translation-r1` | 50724 | C |
| `dfm14-fo-denoising-r1` | `schneiderkamplab/dfm14-fo-denoising-r1` | 3351 | B/C |
| `dfm14-fo-paragraph-reordering-r1` | `schneiderkamplab/dfm14-fo-paragraph-reordering-r1` | 629 | B/C |
| `dfm14-fo-prefix-continuation-r1` | `schneiderkamplab/dfm14-fo-prefix-continuation-r1` | 3637 | C |
| `dfm14-fo-span-filling-r1` | `schneiderkamplab/dfm14-fo-span-filling-r1` | 1585 | B/C |
| `dfm14-fo-translation-r1` | `schneiderkamplab/dfm14-fo-translation-r1` | 80 | C |
| `dfm14-fr-translation-r1` | `schneiderkamplab/dfm14-fr-translation-r1` | 404694 | C |
| `dfm14-ga-denoising-r1` | `schneiderkamplab/dfm14-ga-denoising-r1` | 11731 | B/C |
| `dfm14-ga-instruction-r1` | `schneiderkamplab/dfm14-ga-instruction-r1` | 15032 | C |
| `dfm14-ga-paragraph-reordering-r1` | `schneiderkamplab/dfm14-ga-paragraph-reordering-r1` | 2042 | B/C |
| `dfm14-ga-prefix-continuation-r1` | `schneiderkamplab/dfm14-ga-prefix-continuation-r1` | 10621 | C |
| `dfm14-ga-span-filling-r1` | `schneiderkamplab/dfm14-ga-span-filling-r1` | 5287 | B/C |
| `dfm14-ga-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-ga-synthetic-grounded-instruct-r1` | 17568 | C |
| `dfm14-ga-synthetic-math-code-r1` | `schneiderkamplab/dfm14-ga-synthetic-math-code-r1` | 890 | C |
| `dfm14-ga-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-ga-synthetic-multiturn-r1` | 12281 | C |
| `dfm14-ga-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-ga-synthetic-openhermes-r1` | 8832 | C |
| `dfm14-ga-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-ga-synthetic-summary-rewrite-r1` | 8517 | C |
| `dfm14-ga-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-ga-synthetic-tool-dialogue-r1` | 3857 | C |
| `dfm14-ga-translation-r1` | `schneiderkamplab/dfm14-ga-translation-r1` | 9734 | C |
| `dfm14-gl-denoising-r1` | `schneiderkamplab/dfm14-gl-denoising-r1` | 8963 | B/C |
| `dfm14-gl-instruction-r1` | `schneiderkamplab/dfm14-gl-instruction-r1` | 63023 | C |
| `dfm14-gl-paragraph-reordering-r1` | `schneiderkamplab/dfm14-gl-paragraph-reordering-r1` | 1390 | B/C |
| `dfm14-gl-prefix-continuation-r1` | `schneiderkamplab/dfm14-gl-prefix-continuation-r1` | 9935 | C |
| `dfm14-gl-span-filling-r1` | `schneiderkamplab/dfm14-gl-span-filling-r1` | 5060 | B/C |
| `dfm14-gl-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-gl-synthetic-grounded-instruct-r1` | 19852 | C |
| `dfm14-gl-synthetic-math-code-r1` | `schneiderkamplab/dfm14-gl-synthetic-math-code-r1` | 1121 | C |
| `dfm14-gl-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-gl-synthetic-multiturn-r1` | 14875 | C |
| `dfm14-gl-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-gl-synthetic-openhermes-r1` | 12098 | C |
| `dfm14-gl-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-gl-synthetic-summary-rewrite-r1` | 9916 | C |
| `dfm14-gl-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-gl-synthetic-tool-dialogue-r1` | 3945 | C |
| `dfm14-gl-translation-r1` | `schneiderkamplab/dfm14-gl-translation-r1` | 10222 | C |
| `dfm14-he-denoising-r1` | `schneiderkamplab/dfm14-he-denoising-r1` | 83132 | B/C |
| `dfm14-he-instruction-r1` | `schneiderkamplab/dfm14-he-instruction-r1` | 16153 | C |
| `dfm14-he-paragraph-reordering-r1` | `schneiderkamplab/dfm14-he-paragraph-reordering-r1` | 17577 | B/C |
| `dfm14-he-prefix-continuation-r1` | `schneiderkamplab/dfm14-he-prefix-continuation-r1` | 92082 | C |
| `dfm14-he-span-filling-r1` | `schneiderkamplab/dfm14-he-span-filling-r1` | 45136 | B/C |
| `dfm14-he-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-he-synthetic-grounded-instruct-r1` | 9629 | C |
| `dfm14-he-synthetic-math-code-r1` | `schneiderkamplab/dfm14-he-synthetic-math-code-r1` | 780 | C |
| `dfm14-he-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-he-synthetic-multiturn-r1` | 7247 | C |
| `dfm14-he-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-he-synthetic-openhermes-r1` | 6175 | C |
| `dfm14-he-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-he-synthetic-summary-rewrite-r1` | 4748 | C |
| `dfm14-he-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-he-synthetic-tool-dialogue-r1` | 1927 | C |
| `dfm14-he-translation-r1` | `schneiderkamplab/dfm14-he-translation-r1` | 276242 | C |
| `dfm14-hi-denoising-r1` | `schneiderkamplab/dfm14-hi-denoising-r1` | 8091 | B/C |
| `dfm14-hi-instruction-r1` | `schneiderkamplab/dfm14-hi-instruction-r1` | 15417 | C |
| `dfm14-hi-paragraph-reordering-r1` | `schneiderkamplab/dfm14-hi-paragraph-reordering-r1` | 1970 | B/C |
| `dfm14-hi-prefix-continuation-r1` | `schneiderkamplab/dfm14-hi-prefix-continuation-r1` | 10912 | C |
| `dfm14-hi-span-filling-r1` | `schneiderkamplab/dfm14-hi-span-filling-r1` | 6524 | B/C |
| `dfm14-hi-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-hi-synthetic-grounded-instruct-r1` | 9924 | C |
| `dfm14-hi-synthetic-math-code-r1` | `schneiderkamplab/dfm14-hi-synthetic-math-code-r1` | 969 | C |
| `dfm14-hi-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-hi-synthetic-multiturn-r1` | 7483 | C |
| `dfm14-hi-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-hi-synthetic-openhermes-r1` | 6268 | C |
| `dfm14-hi-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-hi-synthetic-summary-rewrite-r1` | 4983 | C |
| `dfm14-hi-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-hi-synthetic-tool-dialogue-r1` | 1909 | C |
| `dfm14-hi-translation-r1` | `schneiderkamplab/dfm14-hi-translation-r1` | 17022 | C |
| `dfm14-hr-translation-r1` | `schneiderkamplab/dfm14-hr-translation-r1` | 1863 | C |
| `dfm14-hu-translation-r1` | `schneiderkamplab/dfm14-hu-translation-r1` | 43229 | C |
| `dfm14-id-denoising-r1` | `schneiderkamplab/dfm14-id-denoising-r1` | 18753 | B/C |
| `dfm14-id-instruction-r1` | `schneiderkamplab/dfm14-id-instruction-r1` | 11161 | C |
| `dfm14-id-paragraph-reordering-r1` | `schneiderkamplab/dfm14-id-paragraph-reordering-r1` | 3433 | B/C |
| `dfm14-id-prefix-continuation-r1` | `schneiderkamplab/dfm14-id-prefix-continuation-r1` | 21924 | C |
| `dfm14-id-span-filling-r1` | `schneiderkamplab/dfm14-id-span-filling-r1` | 11728 | B/C |
| `dfm14-id-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-id-synthetic-grounded-instruct-r1` | 9923 | C |
| `dfm14-id-synthetic-math-code-r1` | `schneiderkamplab/dfm14-id-synthetic-math-code-r1` | 277 | C |
| `dfm14-id-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-id-synthetic-multiturn-r1` | 7487 | C |
| `dfm14-id-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-id-synthetic-openhermes-r1` | 6369 | C |
| `dfm14-id-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-id-synthetic-summary-rewrite-r1` | 4971 | C |
| `dfm14-id-synthetic-tool-dialogue-r1` | `schneiderkamplab/dfm14-id-synthetic-tool-dialogue-r1` | 1993 | C |
| `dfm14-id-translation-r1` | `schneiderkamplab/dfm14-id-translation-r1` | 30352 | C |
| `dfm14-is-translation-r1` | `schneiderkamplab/dfm14-is-translation-r1` | 5298 | C |
| `dfm14-it-translation-r1` | `schneiderkamplab/dfm14-it-translation-r1` | 129463 | C |
| `dfm14-ja-denoising-r1` | `schneiderkamplab/dfm14-ja-denoising-r1` | 63623 | B/C |
| `dfm14-ja-instruction-r1` | `schneiderkamplab/dfm14-ja-instruction-r1` | 114334 | C |
| `dfm14-ja-paragraph-reordering-r1` | `schneiderkamplab/dfm14-ja-paragraph-reordering-r1` | 15140 | B/C |
| `dfm14-ja-prefix-continuation-r1` | `schneiderkamplab/dfm14-ja-prefix-continuation-r1` | 61142 | C |
| `dfm14-ja-span-filling-r1` | `schneiderkamplab/dfm14-ja-span-filling-r1` | 57064 | B/C |
| `dfm14-ja-synthetic-grounded-instruct-r1` | `schneiderkamplab/dfm14-ja-synthetic-grounded-instruct-r1` | 9513 | C |
| `dfm14-ja-synthetic-math-code-r1` | `schneiderkamplab/dfm14-ja-synthetic-math-code-r1` | 1048 | C |
| `dfm14-ja-synthetic-multiturn-r1` | `schneiderkamplab/dfm14-ja-synthetic-multiturn-r1` | 7472 | C |
| `dfm14-ja-synthetic-openhermes-r1` | `schneiderkamplab/dfm14-ja-synthetic-openhermes-r1` | 5777 | C |
| `dfm14-ja-synthetic-summary-rewrite-r1` | `schneiderkamplab/dfm14-ja-synthetic-summary-rewrite-r1` | 4849 | C |
