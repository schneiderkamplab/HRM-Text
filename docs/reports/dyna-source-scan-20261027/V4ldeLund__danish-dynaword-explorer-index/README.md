---
language: da
pretty_name: Danish Dynaword explorer serving indexes
tags:
  - dynaword
  - search
  - topic-modeling
  - derived-data
viewer: false
---

# Danish Dynaword explorer serving indexes

Immutable runtime artifacts for [the explorer](https://v4ldesalnikov.github.io/scandinavian-dynaword-website/).
Source code and build instructions: https://github.com/V4ldeSalnikov/scandinavian-dynaword-website.

Source: [danish-foundation-models/danish-dynaword](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/tree/c2f51be06848df26b5aad71cafeec1bc6064b1cc).
Pinned source revision: `c2f51be06848df26b5aad71cafeec1bc6064b1cc`. Coverage: 7,399,685 records across 50 sources.
`runtime.json` records SHA-256 checksums and sizes for every serving artifact.
The text index includes original document text. Annotations are model predictions; PII flags do not imply anonymization.

## Attribution and licenses

Original texts and annotations retain their original licenses and restrictions, which vary by source.
`manifest.json` lists each collection's license and links to its original dataset card; consult those cards before reusing content.
This repository does not relicense the underlying corpus.

The fastText vocabulary vectors and derived document vectors use **CC BY-SA 3.0**:
Grave, Bojanowski, Gupta, Joulin, Mikolov (2018), *Learning Word Vectors for 157 Languages*.
Original vectors: https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.da.300.vec.gz.
The vocabulary is limited to the first 100,000 entries, normalized and weighted as described in `danish-fasttext/definition.json`.
Derived document vectors, reduced topic assignments and map coordinates were produced by the explorer's build scripts.
`topics_manifest.json` documents the Turftopic run, sampling, projection, model limitations and full-corpus assignment coverage.

## Contents

- `corpus.duckdb`: all document metadata and annotations.
- `fulltext/`: Tantivy BM25 index with stored original texts.
- `semantic/`, `danish-fasttext/`: full-corpus search vectors and query vocabulary.
- `topics/`: assignments for all usable document vectors and a sampled interactive map.
- `*_manifest.json`: coverage and reproducibility information.

Training caches, logs, temporary files and credentials are excluded.
