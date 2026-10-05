---
type: Runbook
title: DaLA v2 Multilingual Audit
description: Requested audit scope and source-preserving processing for 26 DaLA v2 languages.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, dala, audit]
---
# DaLA v2 Audit

## Baseline Audit Completed, 2026-10-04

The baseline runner exited with `complete.json` in
`data/dfm13/dala-v2-baseline-batch-audit-20261004-v1`: 34,939,912
rows have completed decisions and 271,399 exhausted request failures, totaling
35,211,311 rows. There are no remaining pending or running jobs in that receipt.
Completed decisions are not accepted-row counts; downstream quality selection,
held-out filtering, export and publication remain separate operations. The last
periodic progress snapshot still showed 224 running rows and is superseded by
the completion receipt. Shared servers remain needed by Baltic generation and
the queued fourth wave.

## Feeding Diagnosis, 2026-10-04

Read-only inspection found 265-384 queued request batches per endpoint despite
uneven vLLM active counts. Source starvation or permanently wrong GPU assignment
is not supported by that snapshot. Claims, source insertion and result commits
share one database executor; request workers await durable completion before
taking the next batch. Recorded cumulative claim/put/finish/pending time was
about 19,908 seconds against 20,032 seconds elapsed, consistent with a saturated
single database worker. This is cumulative evidence, not a new profiler result.

The reporter also performs full status/endpoint aggregate scans; its recorded
maximum read took 113.8 seconds despite a nominal 15-second reporting sleep.
Current runner requests a 512 MiB SQLite cache and 2 GiB mmap limit. Prioritize
database throughput, cheaper reporting and bounded request/result pipelining
over simply adding clients or moving them between servers. Preserve durable
completion, lease ownership and backpressure. No live changes in this diagnosis.

## Operational Update, 2026-10-04

### Future Large-Audit Queue Partitioning

User-approved direction on 2026-10-04: use eight independent queue databases
for future large audits rather than funneling all eight GPU clients through one
SQLite writer. Do not repartition the current nearly completed audit in place.
This is a design decision, not an implemented migration.

Partition deterministically by a stable hash of the canonical audit ID modulo
eight. Preserve source aliases and provenance with that canonical record so
duplicates cannot acquire independent acceptance credits. Prepare the partitions
in one source pass, not eight full scans. Each database has its own writer,
leases, transactions and resume state. Record partition counts and input hashes
in a campaign manifest; finalization must verify disjoint IDs and complete
coverage before combining accepted decisions. Test union parity against a
single-database fixture and crash/resume ownership before production use.

Database partitions need not be pinned to GPU IDs. A bounded ready queue can
dispatch the next request to a healthy endpoint with available capacity while
keeping its originating database and lease owner attached. In-flight requests
stay on their original endpoint. Result persistence retains bounded backpressure
and durable completion; dynamic dispatch does not justify unbounded pending
writes or replaying requests with unknown outcomes. Address persistence and
admission pauses before expecting dispatch changes to improve utilization.

Latest resource allocation supersedes the solo 512/server setting below:
the baseline audit was gracefully drained and restarted at **384/server**
(PID 2883484), reserving **128/server** for Baltic synthetic generation and
review toward 70K accepted conversations per language. Shared servers were not
restarted; prior completed decisions and exhausted-failure records were retained.
Restart log: `data/dfm13/dala-v2-baseline-batch-audit-20261004-v1/resume-384-baltic-share.log`.
The predecessor config SHA256 was
`9ebf5dacbcf9ef882e77a90440257a393ec449f88fd67ffbde82099b70e454d2`.

The 26-language inventory below is superseded by the 34-language baseline
manifest at `data/dfm13/dala-v2-audit34/manifest.json`. Completed Dutch and
Persian recovery exports are audited separately using
`data/dfm13/dala-v2-nl-fa-recovery-inputs-20261004-v1/manifest.json`.
Both clients were drained and resumed at 128 requests per server each, for
256 combined requests per server on ports 8800-8807. The shared servers were
not restarted. Concurrency changes require an explicit predecessor config hash;
source and review-contract checks remain enforced. Each request audits up to
16 records. This concurrency target applies while both clients are active.

### Response ID Failure Diagnosis

Read-only inspection on 2026-10-04 found 3,578 baseline failed rows with
`Unexpected response IDs` and three with invalid/missing members. In two
500-response samples, 91 baseline batches and 84 recovery batches contained
unexpected IDs. All 185 unexpected IDs closely resembled supplied hashes
(similarity greater than 0.9); examples dropped one or two characters from
64-character hashes. All 1,000 sampled responses finished with `stop`.
The parser rejects the entire batch when any unknown ID appears, amplifying
these copying errors into retries of otherwise correctly identified members.
These samples diagnose formatting, not linguistic rejection or GPU failure.
Recommended future fix: short request-local IDs with an exact saved mapping
to canonical hashes, plus independently preserving exact valid members.
Never fuzzy-match IDs for acceptance. No running audit was changed for this
investigation; any protocol change needs explicit versioning and validation.

### Local-ID Upgrade and Higher Concurrency

Later on 2026-10-04, the user authorized the recommended fix and 512 combined
requests per server. This supersedes the 256 target above: two clients each
use 256/server. Server `--max-num-seqs` remains 1024; no server restart.
Requests use short local IDs with schema enums and raw-log canonical hash maps.
Only exact IDs are mapped; valid members survive an unrelated unknown ID,
while missing or duplicate members retry. A predecessor configuration hash and
`--upgrade-local-ids` explicitly authorize the adapter migration. Existing
completed judgments are preserved. Eight tests and a live pair/control request
passed before resuming clients. Previously exhausted rows remain recorded and
are not silently reset by this migration.

### Preparation and Dispatch Throughput

After recovery completed, the baseline client's pending queue emptied and
servers had only 3-14 active requests each. The 2026-10-04 fix uses 2,048-row
source chunks, one dispatcher claiming groups for bounded per-server queues,
and one transaction/database call per finished response batch instead of per
row. SQLite ownership remains confined to one executor thread; cursor checks,
source hashes, aliases, and split provenance remain intact. Queued leased work
drains on stop before process exit.

Raw request/response writes previously performed synchronous fsync on the
network event loop. This runner now opts into threaded durable writes through
`raw_query(..., offload_writer=True)`, with a private UUID writer per request.
Other callers retain the prior default behavior. No durability check is removed.
The sole remaining audit client uses 512/server after recovery completion;
shared vLLM servers are unchanged. Source/resume and calibration tests: 43 passed.

### Measured Remaining Database Bottleneck

Further timings on 2026-10-04 supersede the implication that threaded raw
writes alone solved feeding: in a 20-second sample the writer thread spent
5 seconds reporting, 5 finishing results, 4.2 inserting sources, and 4.3
claiming jobs. Network servers remained underfed despite a prepared backlog.

The runner now reports through a separate read-only SQLite connection, combines
up to 64 completed response batches in one transaction, and claims up to 64
request batches per endpoint instead of eight. Workers await the durable result
commit; soft stop drains queued work and results. Ownership checks and rollback
are tested. Full backlog polling sleeps two seconds only when the database
already contains its bounded pending target, not before sending requests.
This first change measured 67K completed rows/min over a full minute, versus
25.6K previously, with no new failures/preemptions. It did not fully saturate
the servers.

The queue database was 9.1 GiB while using SQLite's default 2 MiB page cache.
The runner now uses a bounded 512 MiB writer page cache and a 2 GiB mmap limit;
the read-only reporter also uses mmap. These are connection-local settings,
not a change to transactions or durability. Cumulative operation timing and
per-endpoint dispatch queue depth are recorded in `progress.json` for further
diagnosis. External py-spy attachment was denied even with sudo on this host.
The revised regression suite passed 44 tests, including bulk-finish rollback
and rejection of a wrong lease owner.

After the page-cache change, a 61.2-second server measurement showed 7,330
requests/min and 92,176 generated tokens/s; progress snapshots spanning 60.04
seconds added 95,554 completed rows (about 95.5K/min), with no additional failed
rows. All sampled GPU utilizations were 100%. Active requests reached 3,937;
KV occupancy briefly approached 100%, with 30 preemptions and at most 134
waiting requests in sampled snapshots. Thus the former persistent underfeeding
was relieved, but the requested 512/server ceiling can now cause transient
KV pressure. No server settings or concurrency were reduced during this fix.

The user requested v2, not prior DaLA releases, for these 26 languages:
en, de, fr, es, it, pt-PT, cs, sk, pl, uk, be, bg, ro, el, ca, fi, et,
lv, lt, sv, nb, nn, is, fo, hr, sl.

Source discovery uses the DaLA repository's
`wiki/artifacts/v2-audit-readiness-20261003.json`. Its ready entries total
24,075,603 candidate pairs and 3,624,839 clean controls for this exact subset.
These are inventory counts, not GPU acceptance or completed audit counts.
Freeze actual exported gzip hashes and counts before processing. Source paths
are under `/work/mimir/DaLA/la_output/v2/`; preserve that repository and unrelated
ongoing generation processes unchanged.

Audit whether the clean sentence is valid in the specified language/variant,
whether the noisy sentence genuinely contains the intended error, and whether
the correction removes errors while preserving meaning. Audit clean controls
as controls, not as failed attempts to introduce errors. Audit a pair once for
both acceptability and correction suitability; do not duplicate model requests
for two downstream task formats. Preserve train/validation/test provenance;
auditing held-out rows does not authorize adding them to training.

Use shared Gemma4 26B-A4B servers with bounded batches, exact item IDs and
recoverable missing judgments. Keep the compact audit-first approach, retain
raw decisions and separate accepted-only exports. Initial calibration and full
processing are pending; no completion or throughput claim follows from this
inventory. Coordinate request budgets with existing repairs and DaLA clients.
