---
type: Reference
title: Mimir Training Corpus Collections
description: Public Hugging Face collections for the DFM8 and DFM11 training sources.
status: stable
confidence: medium
last_updated: 2026-09-25
tags: [datasets, huggingface, mimir, dfm8, dfm11]
---
# Mimir Training Corpus Collections

Created under `schneiderkamplab` on 2026-09-25:

| Collection | Corpus | Hub repositories |
|---|---|---:|
| [Mimir Training Corpus v1](https://huggingface.co/collections/schneiderkamplab/mimir-training-corpus-v1-6ab67a48a0dcee505249deb4) | DFM8 | 159 |
| [Mimir Training Corpus v1.5](https://huggingface.co/collections/schneiderkamplab/mimir-training-corpus-v15-6ab67a624edba2b4380b06c2) | DFM11 | 215 |

134 repositories occur in both collections. Hugging Face permits this; a
collection links to repositories without copying their data.

Membership and verified remote receipts are saved in
`docs/mimir-training-corpus-collections.json`. The DFM8 membership follows
`docs/dfm8-datasets.md`. DFM11 membership combines that base ledger with
`data_io/prefix_config_dfm11.yaml`, the DFM10 export specifications, DFM11
replacement rules, and the completed default-repeat Mimir benchmark campaigns.
The local DFM11 tokenized union is not present on this transferred machine;
DFM11 reconciliation is policy/lineage-based, not a fresh per-row index audit.

Collections include upstream source repositories and published derivatives.
Their presence does not mean every upstream row or split was trained on, nor
that all collection entries should be concatenated: some entries describe
overlapping upstream and packaged provenance. Caps, filtering, train splits,
and repetition remain defined by the corpus preparation pipeline.

DBC and Lex.dk are agreement-only sources and cannot be represented as Hub
dataset items. Raw OpenHermes is not included: both modernized English and
Danish packages are included. DFM11 uses repaired tool and other replacements;
helper models and helper-only training datasets are not included.

Reconcile locally with `scripts/build_mimir_collection_manifest.py`; review
the resulting membership before publishing. Publish or verify idempotently:

```bash
python scripts/publish_mimir_corpus_collections.py \
  docs/mimir-training-corpus-collections.json --publish
```

The publisher requires the cached HF credential with organization write
access, verifies exact remote membership, and never removes existing items.
HF collection descriptions have a 150-character limit.
