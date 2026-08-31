---
type: Policy Record
title: Oliver Kinch Source Policy
description: 'Part of Data Mix Policy: Oliver Kinch Source Policy.'
tags:
- data
- licensing
- provenance
- privacy
status: stable
last_updated: 2026-08-29
confidence: high
part_of: /pages/data-mix-policy.md
---
# Oliver Kinch Source Policy

Part of [Data Mix Policy](/pages/data-mix-policy.md).

Reviewed on 2026-05-21 from Hugging Face dataset metadata, cards, and sample schemas.

## DFM contributor status

Update, 2026-08-17: the project owner confirmed that both Oliver Kinch and
Synquid work as part of the DFM project. Their authored dataset contributions
(including transformations, synthetic generations, labels, metadata, and
instruction wrappers) are therefore authorized DFM contributions. This does
not replace provenance review for retained upstream text, prompts, or
conversations.

Consequently, an Oliver/Synquid repository does not need Article 3 merely
because its added transformation layer lacks a separate public licence. Article
3 remains relevant only where an incorporated upstream component is not
otherwise covered. Current examples are Synquid's retained DOLCI puzzle prompts
and WildChat conversations/prompts.

Include:

- Public Danish backtranslation/instruction datasets where targets come from CC-BY, EU legal, DST, DOAB, university portal, tidsskrift.dk, or DynaWord-style public provenance.
- Public Danish QA from Wikipedia-derived `multi-wiki-qa-high-quality-subset`.
- Danish translation pairs from `machine-translation-da-en`, `machine-translation-da-uk`, and `machine-translation-da-ar`, with sampling caps because `da-en` is much larger than the other additions.

Exclude by default:

- Raw Oliver Kinch document corpora such as `danish_wikipedia`, `eur-lex`, `tidsskrift-dk`, `tidsskrift-dk-en`, `danmarks-statistik`, `danish-university-portals`, `doab-da`, and `dst-table-prompts`; the current plan allows only Danish DynaWord as raw continuation data.
- `oliverkinch/dsk-bt`; the card says it is derived from non-public internal DSK material and is not intended for public redistribution.
- `oliverkinch/da-bird`; useful as an evaluation/text-to-SQL benchmark, but its Harbor task layout and CC-BY-SA inherited BIRD tasks make it a poor fit for the current mixed training corpus.
- `oliverkinch/dynaword-no-bt`; Norwegian rather than Danish.
- Small/no-license synthetic/demo datasets (`life-in-the-uk-multiple-choice`, `synthetic-qa`, `synthetic-qa-context-qa`, `mt_da_uk`) unless separately justified.

Confidence: medium for source-card safety; high for local manifest/converter support after `py_compile` and downloader dry-run.

## Tidsskrift.dk local holding, 2026-08-29

**Superseded 2026-08-29:** the initial inspection found the derived
`oliverkinch/tidsskrift-dk-bt` tree but missed the raw corpus nested under the
local DynaWord snapshot. The statement that the raw articles were absent must
not be used for planning.

The repository has both the derived `oliverkinch/tidsskrift-dk-bt` training
split and the raw corpus at
`data/downloads/datasets/danish_dynaword/data/tidsskrift-dk/tidsskrift-dk.parquet`.
The raw parquet contains 4,121 rows and approximately 50.01 million Llama-3
tokens under CC BY 4.0. The local BT Parquet has
62,934 prompt/target passages derived from 3,359 distinct source-article rows
across 13 journals. Its tokenized form contributes 38,334,152 tokens at DFM10
repeat 1. Source URLs, article titles, journal slugs, and source-row identities
are retained in each BT row.

The upstream raw dataset card identifies 4,132 currently exposed rows and a
single `CC BY` license value; its documentation describes 5,699 collected
articles across 16 journals. The BT card describes 62,934 train plus 6,993 eval
passages, but the downloader intentionally fetched only `data/train-*.parquet`
for the BT dataset. The raw DynaWord copy and the BT data substantially overlap
and must not be counted as independent source content. Preserve article-level
author/journal attribution in any grounded generation or expanded harvest.

The current DynaWord `tidsskrift-dk` component is sourced from the same Oliver
Kinch corpus and is not a larger independent Tidsskrift.dk harvest. A future
expansion must deduplicate by canonical article URL, DOI, and normalized text.
