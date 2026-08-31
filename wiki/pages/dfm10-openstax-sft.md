---
type: Dataset Integration Record
title: DFM10 OpenStax Grounded SFT
description: Provenance, generation, audit, tokenization, and DFM10 activation record for the grounded OpenStax derivative corpus.
tags: [dfm10, openstax, grounded-sft, audit, provenance]
status: stable
last_updated: 2026-08-29
confidence: high
---
# DFM10 OpenStax Grounded SFT

## Decision And Boundary

DFM10 includes independently audited derivative SFT produced from 61 immutable
historical OpenStax CC BY 4.0 artifacts. This decision does not admit the
provenance-poor Hugging Face repack, current CC BY-NC-SA editions, unverified
artifacts, or separately restricted content. Exact source and licence history
is recorded in the
[Mimir v1 evaluation gap analysis](/pages/mimir-v1-evaluation-gap-analysis.md)
and `docs/openstax_cc_by_inventory.csv`.

## Construction

The expanded run used 65,000 unique passage/task-family requests across all 61
books. Its five task families were concept explanation, grounded application,
misconception correction, worked problems, and comparison/transfer. The source
passage appeared only in teacher and auditor prompts; final rows contain only a
standalone user instruction and assistant response.

The initial 13,000-request pipeline pilot produced 10,000 accepted rows and is
preserved as
`data/mimir_openstax_sft/accepted/openstax_mimir_sft_pilot10k.jsonl`. It is not
linked into DFM10.

## Production Gate

Integration is fail-closed through
`scripts/integrate_openstax_mimir_sft_when_audited.sh`. It requires all 64
generation/audit shards to finish with zero failures, validates every accepted
row's positive judge decision and five scores of at least 4/5, requires CC BY
provenance, and rejects Gemma 4 training conversations above 4,096 rendered
tokens. `scripts/finalize_openstax_mimir_sft.py` atomically stages 16 JSONL
shards for parallel tokenization.

All 64 shards completed on 2026-08-29 with zero failures. The final accepted
corpus has:

| Quantity | Value |
| --- | ---: |
| Accepted rows | 50,000 |
| Books represented | 61 |
| Rendered training tokens | 8,592,140 |
| Maximum row length | 859 tokens |
| Rows rejected at the 4,096-token build gate | 0 |
| Tokenized tasks | 16 |

The accepted JSONL SHA-256 is
`76b6b15fa7261eec73e3ab12af10fc10221ab469a3f4cc4db39149e7f53beca0`.

## DFM10 Activation

The final staging tree is `data/dfm10_openstax_sft_sources`; tokenized data is
under `data/tokenized_dfm10_openstax_sft`. The integration marker is
`data/tokenized_dfm10_openstax_sft/.dfm10_integration_complete`. All 16 tasks
are linked into `data/tokenized_dfm10` under prefix
`openstax_mimir_sft__`, configured at repeat one in
`data_io/prefix_config_dfm10.yaml`.

Existing sampled DFM10 epochs were not mutated. Every future DFM10 sampling run
using the canonical tokenized union and prefix configuration includes this
source.
