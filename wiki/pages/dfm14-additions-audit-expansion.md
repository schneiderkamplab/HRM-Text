---
type: Operational State
title: DFM14 Additions and Translation Expansion
description: October 7 audit submissions, translation gaps, knowledge preparation and calibration gates.
tags: [dfm14, auditing, translation, calibration]
status: draft
last_updated: 2026-10-07
confidence: high
---
# DFM14 Additions and Translation Expansion

## GPU Status After Shared-Pipeline Migration (2026-10-07)

Update later the same day: the broad translation audit is now running at
128/server on the eight shared servers, alongside generation/review at 512.
It covers 3,788,527 previously unaudited pairs, excluding 4,240 overlaps with
prior verdicts. See [the shared runner](shared-audit-pipeline.md) for paths.
This supersedes the pending translation status in the historical snapshot below.

Original, Asian, English and enrichment source audits have completed. The English
legacy additions-controller failure records its intentional migration stop;
`english-additions-audit-v1/pipeline/state.json` is the authoritative completed
state. Synthetic generation and immediate review remain active on all eight GPUs.

Do not confuse completed gap-bridge audits with a full translation audit:
`parallel-expansion-v4/coverage.json` contains 3,792,767 candidate pairs, while
the original direct preparation still marks semantic audit pending. Persian,
Slovak, institutional and sparse gap batches were audited separately; preserve
their decisions and avoid re-auditing overlaps. Broad direct/pivot semantic
auditing is still outstanding, not currently running. Accepted-only integration,
decontamination, packaging, tokenization and sampling also remain, mostly CPU
work. Historical repair decisions need a separate admission/repair decision;
compact accept/reject does not automatically authorize repairing everything.

Complements [the CPU handoff](dfm14-curated-cpu-audit.md) and
[the knowledge pilot](dfm14-knowledge-commonsense.md). Counts are candidates,
not accepted training rows. No DFM13 training inputs were changed.

## Shared Audit Submissions

`python -m dfm14.additions_campaign` runs independent preparation/readiness/audit
chains for `baai-expansion-v1` plus `ja-ar-ru-additions-v1`, and for
`english-additions-v1`. Each uses eight existing servers on 8800-8807 with 32
requests/server, alongside the original audit's 256. Separate controller/chunk
locks and journals prevent writer collisions. The Asian audit started producing
completed receipts: 1,212,077 rows, 2,425 chunks after structural holds/dedup.

State/logs: `logs/dfm14/shared-gemma-20261007/additions/`. Input roots are
`data/dfm14/{asian,english}-additions-gpu-v1`; results use `*-audit-v1`.
The original audit is uninterrupted. Extended evidence includes tool definitions
and English/Faroese/Polish/Persian, selected by readiness metadata. The original
`audit_protocol.py` hash was restored and verified against the running original
audit's configuration, preserving its resume compatibility.

English preparation: 17/17 files, 1,118,268 candidates:

| Component | Candidates | Intended repeat |
|---|---:|---:|
| Smol Magpie Ultra | 406,255 | 1 |
| Smol constraints | 34,305 | 2 |
| Smol rewrite | 53,342 | 2 |
| Smol summarize | 96,355 | 2 |
| SmolTalk2 multi-turn reasoning/IF | 27,695 | 2 |
| SmolTalk2 tool traces | 4,601 | 2 |
| OpenCoder educational | 117,068 | 1 |
| OpenCoder package | 170,941 | 1 |
| UltraChat train_sft | 207,706 | 1 |

These precede cross-file audit-preparation deduplication. The component name
`ultrachat-nonoverlapping` describes intended admission, not completed inherited
deduplication. Inherited/benchmark checks, repairs and accepted-only export still
gate training admission. Structured tools retain schemas, arguments, IDs, results
and native reasoning. Undeclared tools are held, never fabricated.

## Translation Coverage

Tatoeba uses `cmn`, not `zh`, for Mandarin. Correcting this recovered 48,294 usable
English-Chinese candidates from 49,851 raw pairs. `dfm14.parallel_expand` builds
direct Mandarin candidates and exact-English pivots. SQLite uses one writer
during leg indexing, then read-only workers. Short anchors, conflicting mappings,
identical targets, overlength conversations and direct duplicates are excluded.
Both leg provenance and English anchors are retained.

`python -m dfm14.parallel_report` deduplicates all routes and writes novel-only
additions plus `data/dfm14/parallel-expansion-v2/coverage.json`:

| Measure | Before | After |
|---|---:|---:|
| Candidate pairs | 3,042,215 | 3,788,527 |
| Empty pairings, out of 664 | 259 | 41 |
| Pairings below 100 examples | 508 | 374 |
| Pairings below 1,000 examples | 580 | 525 |
| Pairings with at least 10,000 examples | 30 | 48 |

Added 113,042 direct Mandarin pairs and 633,270 novel pivots. Combined candidate
rendering is 330,615,380 tokens, both directions. Per-pair budgets are ceilings,
not quotas; never repeat scarce data to fill them. Exact pivots still require
both-direction semantic/sense/variant audit and decontamination. Institutional
sources remain a route to additional volume without mined-web backfill.

## Dyna, Matina and Knowledge

`python -m dfm14.enrichment` defaults to `enrichment-v2`: 34 files completed,
889,029 candidates. V1 evidence is preserved. New adapters handle Nemotron
Science structured tools/reasoning and Swallow numbered Q/A, rejecting ambiguous
boundaries, incomplete code and undeclared tools.

| Component | Candidates |
|---|---:|
| Faroese DynaWord documents | 5,045 |
| Polish DynaWord documents | 982 |
| Matina book documents | 5,249 |
| Nemotron Science instruction traces | 39,923 |
| Swallow English math Q/A | 318,703 |
| peS2o evidence documents | 199,999 |
| StackExchange explanatory documents | 319,128 |

`python -m dfm14.matina_summaries` separately maps `Long_summary` and `Title` in
`data_360book.jsonl.gz`: 184 secondary book summaries, NOT full original books.
The enrichment/summary audit chain uses `chain('enrichment', roots, 16)` from
`dfm14.additions_campaign`. peS2o/StackExchange remain generation seeds, not direct
training rows. State/logs use the same additions directory.

`python -m dfm14.knowledge_seeds` prepared 268,266 unique nonempty ATOMIC train
relation seeds, pinned to `Estwld/atomic2020-origin` revision
`82293ed322e798dbe2d1509775bce2a2c40c360b`. Relations are plausible, not universal
facts. Of 20,047 OpenStax passages, 18,157 already supported the earlier accepted
corpus, leaving 1,890 unused. The 150K textbook-task target cannot be described
as 150K new evidence passages; expand source coverage or explicitly diversify
tasks. Manifest: `data/dfm14/knowledge-pilot-v1/manifest.json`. Grounded generation,
independent review and decontamination remain pending.

## Calibration Gate

Supersedes the earlier running-v5 status: v5 finished with 92 automated accepts,
83 errors and 17 rejections out of 192. Its 18 exposed controls had six false
accepts and eight errors.

V6 removes contradictory summary/authorization field instructions, uses actual
message indices and thinking-enabled review with an 8K output reservation.
The actual template is counted within 32K; generation remains non-thinking.
V6 finished with 125 automated accepts, 34 errors and 33 rejections. The 18
controls still had six false accepts, four errors and no false rejections.
Thinking is NOT a demonstrated semantic fix. At the end of calibration, bulk production remained held;
all `production_authorized` flags were false. Improve independent review and
deterministic constraint checks before approval. Better schema completion alone
does not establish quality.

Evidence: `data/dfm14/{quality-calibration,review-regression}-v{5,6}/`.
Forty DFM14 unit tests passed; they do not certify semantic quality.

### Owner Override and Production (2026-10-07)

The calibration hold above is superseded by the owner's explicit instruction to
close calibration and launch production, NOT by a passing diagnostic. Evidence
and the failed controls remain valid. `data/dfm14/production-v1/authorization.json`
records the override; final training admission remains unauthorized.
Production uses eight shared endpoints with 128 requests per endpoint, targeting
770,000 native-language six-family rows and 500,000 English knowledge rows.
All seed pools finished preparation and production is running. Three English
pilot smoke rows (textbook, math, commonsense) passed their automated reviews.
This is not an independent semantic quality certification.

Completed production chunks initially yielded 2,297 accepted rows, 1,554 rejected
attempts and 4,026 errored attempts. Errors include unexpected JSON properties,
incomplete review, missing literal boxed math instructions and translation field
budgets. Retries are attempts, not distinct rows; exhausted slots remain explicit
shortfalls. Do not equate passing automated review with training admission.

Production diagnosis later the same day: counting active journals as well as
completed chunks yielded 3,091 accepts / 10,058 finished attempts (30.7%), with
5,066 errors and 1,901 rejections. Math/code yielded 212 accepts / 3,095 attempts;
grounded instruction 640 / 891. JSON-object transport does not enforce the full
schema during decoding; unexpected fields are rejected afterwards. Reviews
use thinking with an 8,192-token ceiling: recorded review output was 13.23M
tokens versus 4.82M generation tokens. Six attempts per slot and waiting for
all slots before claiming another chunk create tails. Production shares servers
with source audits; this is not a dedicated eight-GPU generation run. No runtime
policy was changed during this diagnosis.

### Synthetic Restart: Schema and Non-Thinking (2026-10-07)

The owner superseded the thinking-review policy: **synthetic generation and its
reviews only** now use decoder-enforced JSON schemas, disabled thinking, and at
most two attempts per slot (initial attempt plus one retry, no nested HTTP
retries). Reviews return `decision: accept|reject` and a reason of at most 120
characters, empty for accepts, with a 256-token output budget. Semantic and
native-format checks remain; no quality failure is converted to acceptance.
The four ongoing source audits were neither stopped nor modified.

`python -m dfm14.production restart-contract` archived the old journals and
manifest under `production-v1/history/dfm14-whole-conversation-quality-v7-schema-no-thinking/`.
All **3,489 accepted records were verified byte-for-byte preserved**, including
accepts on old attempt indices above one. Other slots restart under the new
two-attempt policy. Production resumed at 128 concurrency per endpoint on the
existing eight servers; log: `logs/dfm14/shared-gemma-20261007/production-v7.log`.
Six live smoke requests exercised the families: five accepted, one math content
check failure, no schema failures. All 44 DFM14 unit tests passed. This smoke is
transport validation, not a claim of semantic calibration success.

### Persian Bridge (2026-10-07)

`python -m dfm14.persian_bridge` adds Tatoeba `en-pes`, mapping `pes` to internal
`fa`. Of 5,141 raw pairs, 5,125 survive structural filtering and deduplication.
The bridge produces nonempty exact-English pivots for all 16 new-language/Persian
pairings. Outputs are in `data/dfm14/parallel-expansion-v3`; unchanged v2 outputs
are linked, and the English-leg database is copied before augmentation. V2
evidence is not rewritten. The combined report is `coverage.json` in v3.
Completed coverage: 2,632 new unique pivots, 3,791,159 total candidate pairs,
330,900,984 rendered tokens, and 25 empty pairings (down from 41).
Both-direction semantic audit and inherited/benchmark decontamination are still
required; these are candidates, not accepted training data.

### Slovak Download and Persian Audit (2026-10-07)

The ManyThings Tatoeba Slovak ZIP returned HTTP 406 to the default urllib client.
An explicit `User-Agent: curl/8.5.0` and `Accept: */*` resolved it. The downloaded
14,226-row archive, CC BY 2.0 license description, per-row attribution and hash
are retained under `data/dfm14/translation-gap-search-v1/`.
`python -m dfm14.translation_gap_search` found 1,636 unambiguous English-pivot
matches across 13 of 16 missing Slovak edges. Welsh, Irish and Maltese remain
unmatched to Slovak. A French pivot also found one Korean-Maltese match.
These are discovery counts, not integrated or audited candidates; native render,
semantic review and decontamination remain required. Source and report:
[ManyThings](https://www.manythings.org/anki/) and the local `report.json`.

`python -m dfm14.parallel_audit` is running the 2,632 Persian pivot candidates on
the existing eight endpoints, concurrency 16/server. Each verdict checks BOTH
directions and the English anchor. Non-thinking JSON-schema output contains only
accept/reject and a short reason, max 256 tokens; at most one retry for failed
requests. Pair locks and resumable journals isolate writers. Results:
`data/dfm14/persian-bridge-audit-v1/`; log:
`logs/dfm14/shared-gemma-20261007/persian-bridge-audit.log`.
Other audits, synthetic clients and all shared servers remain untouched.

### Integrated Slovak and Broader Pivot Search (2026-10-07)

`python -m dfm14.slovak_bridge` materialized attributed Slovak legs and rendered
1,608 unique two-direction native candidates (1,636 initial anchor matches before
text-pair deduplication). Latest coverage: `parallel-expansion-v4/coverage.json`,
3,792,767 total candidates, 331,070,270 rendered tokens, **12 empty pairings**.
Verified all non-Slovak counts and hashes unchanged from v3. The Slovak candidates
are auditing under `slovak-bridge-audit-v1` via `dfm14.parallel_audit --language sk
--source data/dfm14/parallel-expansion-v4 --output data/dfm14/slovak-bridge-audit-v1`.
The Persian audit finished: **2,061 accept / 571 reject / zero errors**.

`python -m dfm14.alternate_pivots` downloaded missing older-language Tatoeba
bridges and searched every available intermediate language. Results and both-leg
attribution: `data/dfm14/alternate-pivots-v1/report.json`. Four extra routes have
only ONE match each: Belarusian-Irish and Welsh-Serbian via German; Catalan-Maltese
and Korean-Maltese via French. Inspection found two literary-quote translations
and two Esperanto slogans, with nonstandard Serbian/Korean orthography and a
Catalan Europe/EU mismatch among the examples. These are not meaningful coverage
and have NOT been admitted or counted as resolved in v4.

No matches were found for Welsh-Slovak, Basque-Luxembourgish, Irish-Luxembourgish,
Irish-Slovak, Indonesian-Maltese, Luxembourgish-Maltese, Maltese-Nynorsk or
Maltese-Slovak under the current conservative exact-anchor and ambiguity filters.
Do not relax these filters or pull mined-web/evaluation text simply to close gaps.

### Further Parallel Sources and Esperanto (2026-10-07)

The follow-up `alternate-pivots-v2/report.json` includes Esperanto and reuses v1
downloads. It adds one Irish-Luxembourgish and one Luxembourgish-Maltese match,
both translations of the same political slogan. This supersedes the zero-match
discovery statement above for these two pairs, but does not provide meaningful
coverage. None of these exploratory matches has been admitted: integrated v4
still has 12 empty pairs.

Promising alternatives, not yet integrated or audited:

| Source | Relevant coverage | Evidence and next action |
|---|---|---|
| DGT v2021 | Irish-Slovak: 317,267; Maltese-Slovak: 4,088,189 advertised OPUS pairs | Professional EU translations; download, deduplicate, cap and audit. Counts are raw discovery metadata, not usable-row estimates. |
| ECDC v2016-03-16 | Irish-Slovak: 1,217; Maltese-Slovak: 2,425 advertised pairs | Smaller health-domain supplement; preserve the release's terms and verify alignment. |
| Tech-in-GOV Luxembourgish corpus | Luxembourgish-English/French/German; approximately 150,000 Luxembourgish source words | CC0, professionally translated, aligned JSONL/TMX. Test exact joins for Basque/Irish/Maltese; overlap is not yet demonstrated. |
| EFTA translation memories | English, Bokmal and Nynorsk | CC0; inspect actual Nynorsk records and join to Maltese EU-law translations through English. Do not confuse Bokmal with Nynorsk. |

Primary sources:
[DGT terms](https://joint-research-centre.ec.europa.eu/language-technology-resources/dgt-translation-memory_en),
[ECDC](https://joint-research-centre.ec.europa.eu/language-technology-resources/ecdc-translation-memory_en),
[Luxembourgish corpus](https://data.public.lu/en/datasets/meisproochegen-iwwersetzungskorpus-fir-dletzebuergescht/),
[EFTA catalogue](https://data.norge.no/en/datasets/43cd8538-a5aa-3a24-a19c-35a3f00bdb6d/translation-memories-from-efta).
DGT permits reuse under Commission reuse rules with attribution; its software
EUPL license must not be mistaken for the database terms.

EUbookshop, QED and TED advertise additional sparse pairs, but require more
specific rights checks. LuxAlign explicitly warns its news pairs need not be
exact translations. These are weaker choices than the institutional resources
above. Keep FLORES/evaluation corpora and mined-web backfill excluded. Shared
servers, source audits and synthetic production were not interrupted by this
research.

### Institutional Pilot Materialized (2026-10-07)

`python -m dfm14.institutional_parallel` downloaded DGT v2021 ga-sk, mt-sk and
en-mt, plus the CC0 Luxembourgish master archive and EFTA memories. Inputs and
checksums are retained; no existing source/audit files were rewritten.
Output: `data/dfm14/institutional-parallel-v1/coverage.json`.

| Pair | Raw source pairs | Native 4K audit candidates |
|---|---:|---:|
| Irish-Slovak | 317,267 | 9,664 |
| Maltese-Slovak | 4,088,189 | 9,654 |
| Maltese-Nynorsk | 968 EFTA English-Nynorsk units | 71 |

Direct DGT pilots use deterministic seed-0 reservoir sampling of up to 10,000
structurally eligible rows, then text-pair deduplication/native rendering. This
is an initial audit workload cap, NOT a change to final training token budgets.
EFTA has 707 eligible English anchors, one ambiguous. DGT en-mt matches 136;
65 conflicting Maltese translations are excluded, leaving 71 native candidates.
The Luxembourgish corpus has 10,807 aligned rows but no exact joins for
Basque/Irish/Maltese through the existing English, French or German legs.
No approximate semantic joins were substituted.

`python -m dfm14.institutional_audit` audits 19,389 candidates in 500-row chunks
across the eight existing shared servers, concurrency 16/server. It reuses the
parallel audit transport in an isolated process, with an optional-anchor prompt
for direct pairs. Non-thinking strict JSON schema, concise verdicts, one retry.
Chunk locks and single-writer journals protect against races. On completion it
packages accepted rows under `institutional-parallel-v1/accepted`; inherited and
benchmark decontamination plus combined-route selection still gate admission.
State: `institutional-parallel-v1/audit/state.json`; log:
`institutional-parallel-v1/audit.log`. Integrated v4 coverage remains unchanged
pending that admission, rather than prematurely declaring three gaps closed.

### Sparse Nine-Pair Closure (2026-10-07)

The owner explicitly requested even a few sentences for EVERY remaining pair.
For this bounded exception, `python -m dfm14.sparse_parallel` searches exact
anchors with at least 12 characters and eight alphabetic characters rather than
the general 40-character/six-word minimum. The general pipeline is unchanged.
Ambiguous target mappings remain excluded; no fuzzy joins or synthetic
translations are used. Both legs retain Tatoeba attribution. Every candidate
receives a non-thinking JSON-schema semantic/orthographic audit, one retry at
most, using the existing servers at concurrency eight/server.

| Pair | Accepted sentence pairs |
|---|---:|
| Belarusian-Irish | 73 |
| Catalan-Maltese | 15 |
| Welsh-Slovak | 28 |
| Welsh-Serbian | 32 |
| Basque-Luxembourgish | 4 |
| Irish-Luxembourgish | 25 |
| Indonesian-Maltese | 20 |
| Korean-Maltese | 18 |
| Luxembourgish-Maltese | 7 |
| Total | 222 |

All nine gaps now have audit-accepted sentence coverage, NOT yet final training
admission. Of 261 candidates, 222 accepted, 38 rejected, one Korean-Maltese
request remained an error after its retry. Accepted-only per-pair JSONL and
audit receipts: `data/dfm14/sparse-parallel-v1/{accepted,audit}`; summary:
`report.json`. Inherited/benchmark decontamination and combined source selection
still apply. Four/seven accepted examples are sparse coverage, not balanced
pair exposure; do not repeat them to fill quotas.

The institutional pilot also completed: 6,895 Irish-Slovak, 7,318 Maltese-Slovak
and 52 Maltese-Nynorsk accepted (14,265 total, 5,122 reject, two errors).
Thus none of the former twelve empty pairs lacks audit-accepted additions,
although v4 remains the unchanged pre-integration coverage report.

### Synthetic Concurrency 256 (2026-10-07)

The owner requested 256 synthetic requests/server. Existing production jobs
contain at most 128 slots and each endpoint worker waits for its whole chunk;
simply increasing a semaphore would not expose 256 requests. Short and long
families also have different service times, producing chunk tails despite
dynamic job claiming. Low KV occupancy alone is not evidence of low compute use.

`python -m dfm14.production_parallel --concurrency 256` runs two independent
128-slot worker streams per endpoint, using unchanged production functions,
code pins, chunk locks, journals and retry policy. It overlaps tails without
repartitioning or regenerating completed slots. Only the nine exact old
production controller/worker PIDs were stopped; source audits and servers stayed
running. The handoff preserved and verified 51,751 accepted slots; evidence:
`data/dfm14/production-v1/concurrency256-handoff.json`. New log:
`logs/dfm14/shared-gemma-20261007/production-v7-c256.log`.
This doubles the client concurrency ceiling, not a promised throughput doubling.

### Read-Only Utilization Diagnosis (2026-10-07)

`scripts/diagnose_dfm14_utilization.py --seconds 60 --output <new.jsonl>` samples
GPU utilization/power, vLLM counters and client/process CPU ticks without stopping
workers. Evidence: `logs/dfm14/shared-gemma-20261007/utilization-diagnosis-20261007.jsonl`.
Over one minute after the 256-concurrency change, per-GPU mean utilization was
84.4, 99.8, 94.0, 93.0, 95.4, 92.3, 93.2 and 92.8 percent; mean power 816-945 W.
Aggregate generation throughput was about 29,618 tokens/s (all shared clients).
Mean queue latency was 0.71-1.05 s against 6.14-10.49 s end-to-end, estimated from
counter deltas; zero cache preemptions and peak sampled KV occupancy 88.7%.
These are short-window GPU-busy measurements, not FLOP utilization or a controlled
before/after concurrency benchmark.

Confirmed scheduling barrier: audit workers await all approximately 500 rows
before claiming another chunk; live workers were at 496/500 and 496/498. Synthetic
streams similarly wait for their 128-slot chunks. Jobs are dynamically claimed,
so this is primarily within-chunk tail blocking, not static unequal GPU shards.
Audit client CPU used 4.5-7.8% of one core; generation streams 0-6.2%; most sampled
wait states were epoll. Sustained client CPU saturation is not supported by this
measurement. Synchronous tokenization/validation/fsync exist in the async paths,
but their latency contribution has not been quantified.

vLLM deferred requests can include structured-output grammar readiness; installed
scheduler code confirms that state, but metrics do not isolate that cause here.
Do not claim grammar compilation is the dominant bottleneck. py-spy attachment
was permission-denied both normally and with sudo; no live stack profile was
obtained. Suggested next improvement is bounded rolling refill across locked
chunks while preserving writer ownership and concurrency limits, not indiscriminate
concurrency growth or disabling schema enforcement. Running jobs were unchanged.
