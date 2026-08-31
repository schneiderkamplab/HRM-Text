---
type: Runbook
title: DFM10 WikiCatSum Grounding Repair
description: Evidence-selected rebuilding and row-level grounding audit for GEM/wiki_cat_sum.
tags: [dfm10, data-quality, summarization, grounding, wikicatsum]
status: draft
last_updated: 2026-08-29
confidence: high
---
# DFM10 WikiCatSum Grounding Repair

## Problem

The inherited `GEM/wiki_cat_sum` conversion contains 153,911 training rows and
scored only 57% usable in the 100-row DFM10 source audit. The source consists of
Wikipedia lead sentences paired with retrieved web snippets. The inherited
converter concatenated the noisy snippets and truncated their beginning before
the exact Gemma-template fit was known. As a result, targets frequently stated
facts absent from the visible prompt, while prompts retained HTML, copyright,
navigation, advertising, and unrelated retrieval fragments.

## Grounded rebuild

`scripts/repair_wiki_cat_sum.py` scans all three train domains directly from
the local HF download. It divides each multi-gigabyte JSONL into 16 disjoint
byte ranges, processes up to 16 ranges concurrently, and publishes each output
Parquet and metadata record atomically. The conversion:

1. splits retrieved material into bounded evidence snippets and removes known
   web boilerplate;
2. evaluates every lead sentence against its best evidence using content-token
   and ordered-bigram recall;
3. retains only sentences with at least 90% content support and 50% bigram
   support;
4. requires the first retained sentence to identify the titled entity, thereby
   rejecting contextless later-lead fragments beginning with pronouns;
5. emits only the evidence selected for retained target sentences; and
6. checks the exact Gemma 4 native rendering against the 4,096-token limit.

**Superseded 2026-08-28:** the first candidate pass used 60% content recall and
15% bigram recall. It retained 68,624/155,546 raw rows, but a 300-row pilot
passed only 101 rows (33.67%) under the strict audit gate. Manual and automated
review showed that broad lexical overlap still admitted unsupported dates,
locations, identities, and isolated non-self-contained lead sentences. That
candidate tree and its pilot are diagnostic only.

Converter version 2 is authoritative before row-level judging. It retained
14,479 candidates from 155,546 raw rows: 4,370 animal, 5,707 company, and 4,402
film examples. It rejected 140,470 rows without a sufficiently grounded,
title-anchored sentence and 597 rows whose surviving response was shorter than
60 characters. All 48 output shards are under
`data/converted_sources/wiki_cat_sum_grounded_candidates`.

## Row-level gate

`scripts/audit_repaired_wiki_cat_sum.py` uses a WikiCatSum-specific grounding
rubric. It rejects every material claim not established by the selected source
evidence and separately scores language, instruction/answer coherence,
grounding, completeness, and training value. A row passes only when the judge
marks it usable and complete and every numeric score is at least three.

The version-2 pilot contains 100 deterministic examples from each of animal,
company, and film. It is queued at
`logs/data_audits/wiki_cat_sum_repaired_pilot_v2_20260828`. The launcher
`scripts/run_repaired_wiki_cat_sum_audit_8gpu.sh` supports a stable all-GPU idle
gate; the current launch requires all GPUs to remain process-free for 120
seconds so it cannot enter gaps between another campaign's waves. Do not enable
the repaired sampling prefix until this pilot passes, every candidate receives
the same row-level judgment, strict passes are filtered into
`data/converted_sources/wiki_cat_sum_repaired`, and the final corpus is
tokenized and audited exactly.

**Superseded 2026-08-28:** the first merge counted 263/300 pilot rows as strict
usable (87.67%) by trusting the judge's `usable` and `complete` booleans. A
consistency review found judgments that set those booleans while also naming a
primary problem. The authoritative fail-closed criterion additionally requires
`primary_problem: none`; it retains 244/300 pilot rows (81.33%): 90% animal and
77% each company and film. Mean grounding remains 4.65/5. The campaign gate is
therefore 80%, while every row must still pass the stricter individual test.

The complete production inventory has already been materialized as eight
partitions under `logs/data_audits/wiki_cat_sum_repaired_20260828`, with
14,479 unique rows and 1,809–1,810 rows per partition. The locked finalizer
`scripts/finalize_wiki_cat_sum_repair.sh` waits for the pilot, requires exactly
300 pilot judgments and at least 80% strict usability, runs the full audit,
requires exact full-corpus coverage and the same 80% gate, filters strict
passes, and tokenizes the result. Direct production filtering independently
enforces these coverage checks, so a pilot result cannot be promoted by
mistake.

DFM10 sampling disables the inherited
`dfm4_wiki_cat_sum_summarization__` prefix and uses
`wiki_cat_sum_repaired__ repeat: 2`. The DFM10 preparation path requires the
fully audited tokenized replacement, making this replacement fail closed.

## Completed production result

The full eight-GPU E4B audit covered all 14,479 candidates with no coverage
gap. The authoritative consistency-safe merge accepted 11,791 rows (81.44%):
3,928 animal, 4,443 company, and 3,420 film rows. The strict filter rejected
2,688 rows, including every contradictory non-`none` problem judgment. The
accepted corpus is at
`data/converted_sources/wiki_cat_sum_repaired`; its audit and filter summaries
are under `logs/data_audits/wiki_cat_sum_repaired_20260828` and in the corpus
root, respectively.

Gemma-native tokenization completed across 48 shards with zero skipped rows.
The result at `data/tokenized_dfm10_wiki_cat_sum_repaired` contains 2,317,983
rendered tokens; repeat two contributes 4,635,966 sampled tokens per epoch.
The longest retained rendering is 1,833 tokens and none exceeds 4,096.

The repaired source is wired into `scripts/build_tokenized_dfm10_tree.py`,
`scripts/prepare_dfm10_data.sh`, `scripts/dfm10_quality_audit.py`, and
`data_io/prefix_config_dfm10.yaml`. The aggregate `data/tokenized_dfm10` union
was not rebuilt in this operation because independent Folketing and
Nordjylland repaired token roots were still pending. Once those roots exist,
the normal DFM10 preparation command will rebuild the complete union and
include this replacement.

## Additive generated recovery

The 11,791-row strict corpus is safe but small. DFM10 therefore adds a second,
disjoint recovery path instead of lowering its lexical or audit thresholds.
`scripts/prepare_wiki_cat_sum_recovery.py` reconstructs the version-2 decision
for every raw row and considers only rows that did not become existing strict
candidates. It selects a deterministic, domain-balanced maximum of 20,000 rows
each from animal, company, and film, cleans and bounds their retrieved
evidence, and records immutable raw domain, row ID, and row-index provenance.

`scripts/generate_wiki_cat_sum_recovery.py` uses Gemma 4 31B IT to write a
concise English summary from only the supplied evidence. Generator self-ratings
are provenance, not an acceptance gate. Candidate construction requires a
nonempty summary and exact Gemma-native fit within 4,096 tokens.
`scripts/audit_wiki_cat_sum_recovery.py` then gives every generated candidate
to an independent Gemma 4 E4B judge together with its authoritative evidence.
Only rows satisfying the existing WikiCatSum strict predicate can be unioned
with the 11,791 baseline rows.

The end-to-end resumable launcher is
`scripts/run_wiki_cat_sum_recovery_when_free.sh`. It uses one 31B generator per
GPU, tears those servers down, starts one E4B auditor per GPU, requires exact
partition coverage, writes
`data/converted_sources/wiki_cat_sum_repaired_with_recovery`, and retokenizes
the canonical `data/tokenized_dfm10_wiki_cat_sum_repaired` prefix. A CPU request
inventory scan and detached continuation were started on 2026-08-29 after the
DST and university recoveries completed. Final accepted rows and tokens are
pending and must replace this paragraph when the strict audit completes.
