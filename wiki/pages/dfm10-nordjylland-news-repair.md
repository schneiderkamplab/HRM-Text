---
type: Runbook
title: DFM10 NordjyllandNews Repair
description: Headline-aware conversion, full-corpus grounding audit, and strict replacement policy for NordjyllandNews summarization.
tags: [dfm10, danish, summarization, grounding, repair]
status: draft
last_updated: 2026-08-29
confidence: high
---
# DFM10 NordjyllandNews Repair

## Defect and policy

The inherited `alexandrainst/nordjylland-news-summarization` conversion treats
all 75,219 targets as conventional summaries. Many authentic targets are
instead concise news headlines or teasers. The source also contains genuine
target defects: unsupported location and identity details, malformed markup,
incomplete headlines, and occasional claims not established by the article.

DFM10 disables `alexandra_nordjylland_original__`. It will use only the new
`nordjylland_news_repaired__` prefix after full-corpus judging and strict
filtering. The prompt explicitly accepts either an informative headline or a
grounded summary of at most three sentences; it does not relax factual
grounding.

## Deterministic conversion

[`scripts/repair_nordjylland_news.py`](/../scripts/repair_nordjylland_news.py)
renders every candidate through the exact Gemma 4 tokenizer and native chat
template and never truncates. It rejects short inputs, dangling targets,
extreme target/article ratios, targets over 256 tokens, pairs over 4,096
tokens, and exact duplicate pairs. The atomic conversion produced:

| Outcome | Rows |
|---|---:|
| Source rows | 75,219 |
| Candidates written | 73,097 |
| Short/empty | 98 |
| Excessive summary ratio | 619 |
| Incomplete target | 1,381 |
| Exact duplicate | 15 |
| Over context | 9 |

The candidate corpus is
`data/converted_sources/nordjylland_news_repaired/train.parquet`.

## Judge calibration

**Superseded 2026-08-28:** an 800-row E4B pilot accepted 472 rows under the
strict threshold (59.0%), but manual review found contradictory and plainly
incorrect low-score decisions. It is retained only as calibration evidence and
must not determine training eligibility.

The authoritative 800-row Gemma 4 31B IT pilot accepted 493 rows (61.625%)
under the strict threshold and 494 as broadly usable. Mean language,
coherence, grounding, and training-value scores were 4.193, 4.124, 3.940, and
3.558. Its 234 unsupported-claim findings matched manual examples such as
locations, occupations, or strengthened claims absent from the article.

## Full audit and publication gate

[`scripts/audit_repaired_nordjylland_news.py`](/../scripts/audit_repaired_nordjylland_news.py)
assigns all 73,097 candidates to eight deterministic disjoint partitions. Its
JSONL writes are resumable and partition-locked; merge rejects missing,
duplicate, or unexpected sample IDs. The authoritative judge is Gemma 4 31B
IT. Strict acceptance requires `usable_for_training=true`, `complete=true`,
language at least 3, coherence at least 4, grounding at least 4, and training
value at least 3.

[`scripts/filter_repaired_nordjylland_news.py`](/../scripts/filter_repaired_nordjylland_news.py)
requires exact full coverage before atomically publishing
`data/converted_sources/nordjylland_news_repaired_grounded/train.parquet` and
its provenance summary. Only that filtered Parquet may be tokenized. The
tokenized source is wired as `data/tokenized_dfm10_nordjylland_news_repaired`
with repeat one. A separate post-filter sample must pass at least 90% strict
acceptance with zero judge errors before DFM10 sampling.

## Operational state

**Superseded 2026-08-29:** the previous operational snapshot had only partition
2 complete (9,255/73,097 rows) after an older launcher failed with an unbound
`uuid`. The corrected launcher resumed only the seven missing deterministic
partitions and completed exact full coverage.

The authoritative full audit at
`logs/data_audits/nordjylland_news_repaired_31b_full_20260828` judged all
73,097 candidates with Gemma 4 31B IT. The strict gate retained 47,120 rows
(64.4623%) and rejected 25,977. The dominant rejection was
`unsupported_claim` (21,167 rows), followed by `incomplete` (2,626) and
`language_error` (1,884). Mean grounding, coherence, language, and training
value scores were 3.976, 4.181, 4.217, and 3.633.

The independent 800-row post-filter audit accepted 797 rows (99.625%), above
the 90% publication gate, with zero judge errors. The accepted source was
published at
`data/converted_sources/nordjylland_news_repaired_grounded/train.parquet` and
Gemma-native tokenization produced 47,120 rows and 26,590,391 tokens under
`data/tokenized_dfm10_nordjylland_news_repaired`. This repeat-one source is now
eligible for the DFM10 union.

[`scripts/finalize_nordjylland_news_repair.sh`](/../scripts/finalize_nordjylland_news_repair.sh)
is the resumable handoff after the full merge. With `WAIT_FOR_AUDIT=1`, it waits
for exact 73,097-row coverage, filters, runs the independent 800-row 31B gate,
and tokenizes with 16 workers only after that gate passes.
