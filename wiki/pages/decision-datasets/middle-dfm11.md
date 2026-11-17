---
type: Reference
title: DFM11 Registered Additions
description: Eleven pinned DFM11 rebuild sources and their replacement or generation boundaries.
tags: [decision-datasets, dfm8, dfm9, dfm10, dfm11, dfm12, dfm13, provenance]
status: draft
last_updated: 2026-10-21
confidence: medium
---
# DFM11 Registered Additions

Part of [DFM8-13 source review](middle-datasets.md). Classifications are proposals, not conversion or admission results.

Evidence: five linked data configurations are consumed by [Hub rebuild script](../../../scripts/tokenize_dfm11_from_hub.py). Replacement sources are not additive copies of the old tasks. See [DFM11 portability](../dfm11-portability.md) for corrected sampling completion; configuration-local pending fields may predate that completion.

| Exact HF ID | Revision | Configuration / lineage | Proposed applicability |
|---|---|---|

| `schneiderkamplab/dfm11-fineinstructions-da` | `80e37a930948c6e52bcaaffa20408842de87732c` | [config/data/dfm11_fineinstructions_danish.yaml](../../../config/data/dfm11_fineinstructions_danish.yaml) | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm11-fineinstructions-en` | `80f44dfc3cbc0ac8d6e219cc65bee4275db27414` | [config/data/dfm11_fineinstructions_english.yaml](../../../config/data/dfm11_fineinstructions_english.yaml) | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm11-koolbardi-da` | `de2b92ba6684001fe2504d2b96520b394bc08897` | [config/data/dfm11_koolbardi.yaml](../../../config/data/dfm11_koolbardi.yaml) | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm11-koolbardi-en` | `81ad1affa1539006b04fb833664ea393fbab59c1` | [config/data/dfm11_koolbardi.yaml](../../../config/data/dfm11_koolbardi.yaml) | C: Task-routed candidate response judgment |
| `schneiderkamplab/dfm11-mathagentic-tinygsm-python` | `17a3df5ccdd70ce71983485c6c48cce54b60f05e` | [config/data/dfm11_mathagentic.yaml](../../../config/data/dfm11_mathagentic.yaml) | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm11-mathagentic-gsm8k-prolog` | `1d32034d3b2467e51a6128b2cb249852969f17d0` | [config/data/dfm11_mathagentic.yaml](../../../config/data/dfm11_mathagentic.yaml) | B/C: Candidate answer equality or executable result |
| `schneiderkamplab/dfm11-glaive-native-tool-use-repaired` | `270781c192980b2d32a492f92b2b1ba2d694a258` | [config/data/dfm11_tool_replacements.yaml](../../../config/data/dfm11_tool_replacements.yaml); replaces `schneiderkamplab/dfm10-glaive-native-tool-use` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm11-toolace-native-tool-use-repaired` | `2768a3ff3b65effb60d200042c8e09a10e07cc59` | [config/data/dfm11_tool_replacements.yaml](../../../config/data/dfm11_tool_replacements.yaml); replaces `schneiderkamplab/dfm10-toolace-native-tool-use` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm11-nemotron-agentic-tool-calling-repaired` | `ad3251630ba1c0435a559fb9737267554ab208ff` | [config/data/dfm11_tool_replacements.yaml](../../../config/data/dfm11_tool_replacements.yaml); replaces `nvidia/Nemotron-SFT-Agentic-v2:data/tool_calling.jsonl` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm11-synthetic-native-tool-calling-repaired` | `aef80ae81d10b0bb9d9ca7e7760ba09297df4b56` | [config/data/dfm11_tool_replacements.yaml](../../../config/data/dfm11_tool_replacements.yaml); replaces `schneiderkamplab/dfm8-synthetic-native-tool-calling` | B/C: Tool name/schema validity; candidate next action |
| `schneiderkamplab/dfm11-folketingets-dokumenter-error-correction` | `2bac151ddb2c81ff7098bd6d970ca59115a362bf` | [config/data/dfm11_tool_replacements.yaml](../../../config/data/dfm11_tool_replacements.yaml); replaces `schneiderkamplab/dfm10-folketingets-dokumenter-error-correction` | B/C: Known corruption/edit validity or reconstruction |
