---
type: Runbook
title: DFM12 European CPU Preparation
description: Incremental screening, transformation replenishment and audit queue preparation for the second language wave.
status: draft
confidence: high
last_updated: 2026-09-28
tags: [dfm12, preparation, screening]
---
# DFM12 European CPU Preparation

Companion to [the source and quota specification](dfm12-european-expansion.md).
All commands below are CPU-only. They do not authorize GPU audit, training
admission, or final sampling.

## European Synthetic Seeds, 2026-09-28

The owner authorized a separate synthetic campaign for DE, FR, ES, IT, CS,
PT-PT, FI, ET, CA, EL, RO and UK, initially **35000 accepted conversations per
language** (420000 total), subject to source availability. Seed counts are not
accepted-row quotas. This CPU worker does not launch generation or alter any
existing production/source database.

`dfm12/european_synthetic_seeds.py` streams the pinned European Wikipedia and
approved CorEGe-PT sources plus English-only repaired DFM8 OpenHermes. It
publishes append-only batches to
`data/dfm12/european-synthetic-seeds-20260928/seeds.sqlite`, using the existing
`SourceProvider` schema, durable cursors and content/document deduplication.
No corpus or full Parquet row group is materialized into Python lists. Windows
are contiguous source substrings with offsets, not invented paragraphs.
PT-PT retains both variant flags, confidence>=0.8 and derivative-permitting
document rights checks; URLs, IDs, rights, revision and file hashes are retained.
Complete eligible English conversations are retained without truncation.

Detached CPU PID **3668771**, log `logs/european-synthetic-seeds-20260928.log`;
`process.json` records the launch. Targets were already sealed at60000 native
seeds/language and30000 shared English seeds when the parent recommended
150000/60000. Do not mutate the active arguments/manifest; future expansion is
needed if rejection rates exhaust these initial inventories. One window per
document is retained; shortages are reported, never filled by wrapping sources.
All13 pools were readable shortly after startup. An early committed snapshot
had1173 PT-PT seeds,1085 English conversations, and3.6K-7.2K per other native
language. These are unaudited preparation seeds, not newly certified native gold.

Six tests passed: incremental restart, `SourceProvider` allocation, exhaustion
without reuse, source drift rejection, exact offsets, English-only conversations
and pt-PT rights/variant gates. The shared generation language registry must
include the12 new codes; its owner handles that integration. This worker changed
no shared production module. Status command:
`python -m dfm12.european_synthetic_seeds status --root data/dfm12/european-synthetic-seeds-20260928`.

## Running Work

### Bounded Synthetic Candidate Reuse, 2026-09-29

Superseding the no-wrapping candidate policy for explicitly authorized blocked
CS, CA, IS, PT-PT, ET and FO only: `dfm12/joint_source_reuse.py` provides
`SourceReuseProvider(provider, root, max_per_seed=32)`. Wrap the original or
European provider; all allocators for a campaign must use the same sidecar root.
The separate `source-reuse.sqlite` stores replayable slot selections, round-robin
cursors and per-language/pool/source additional-use counts. Original selections,
IDs and cursors are not rewritten. Unique allocation is attempted first, including
newly appended seeds; reused candidates retain the exact source payload/ID, fresh
slot-derived task variation and explicit reuse provenance. Existing eligible-source
views constrain reuse, including English-pool exclusions. The cap counts the first
unique allocation plus additional candidates, not accepted outputs. Auditing and
accepted duplicate rejection remain mandatory and unchanged; the FO waiver is
lifted, not replaced by weaker review. This module launches no processes.

Read-only inventory at implementation: FO6793 and IS63562 native seeds;
PT-PT5196, CA/ET/CS60000 each; European shared English pool30000.
32 total allocations permit217376 FO and166272 PT-PT native candidates, but
acceptance quotas are not guaranteed. Exhaustion raises `SeedUnavailable`.
Parent/Poincare owns controller integration and lifecycle changes; this helper
does not change sealed provider modules or already running processes.

Work root: `data/dfm12/european-expansion-20260926`.
Logs: `logs/dfm12_european_expansion/`.
The detached jobs hide GPUs with `CUDA_VISIBLE_DEVICES=""`:

```bash
python -m dfm12.european_expansion cpu --workers 4
python -m dfm12.european_replenish --workers 4
python -m dfm12.european_screen --watch
```

### Parallel Screening Resume

2026-09-26: the CPU screen/queue runner was resumed with `--workers 64` after
37 components had fully completed both stages. The old serial runner and its
anchor follow-up waiter were stopped by verified PID, without touching GPU jobs.
`screened/pre-64-worker-resume.json` pins the completed receipt checksums.
New log: `logs/dfm12_european_expansion/screen-64.log`; current PID is recorded in
`logs/dfm12_european_expansion/screen.process.json`.

```bash
python -m dfm12.european_screen --watch --workers 64
```

Default remains one worker. Up to 64 spawned workers parse/validate records,
compute fingerprints and serialize/hash audit requests. One ordered writer
performs all reference lookups, cross-source deduplication and SQLite updates;
workers never open those databases. At most 128 batches are outstanding, each
at most 64 rows or 1 MiB of input (a single oversized row is allowed). Completed
out-of-order results count against this bound. Queue IDs/payloads and duplicate
winners are unchanged. No databases or prepared components are recreated.

Completed components are checksum-verified, not regenerated; the displayed
component counter temporarily walks through them during resume. An interrupted
screening component rolls back and replays from its start. Audit queue insertion
uses the existing deterministic IDs with INSERT OR IGNORE, preserving committed
jobs, attempts and results. The single database writer and filesystem remain
throughput limits; 64 configured workers does not imply 64 busy cores.
Serial/parallel parity, duplicate ordering, partial queue preservation and worker
failure rollback were tested; the expanded focused suite passed 120 tests.

The replenisher waits for each initial text conversion. It expands deficient
unaudited candidate pools before screening, never modifies accepted first-wave
packages, and refuses to replace an already-screened candidate. Portuguese
retains both variant flags, confidence thresholds and derivative-permitting
rights checks. Up to 32 distinct deterministic 4,000-character windows per
eligible Portuguese document are available; other languages retain one
8,000-character window. A threefold reservoir reserve offsets invalid/short
windows. These are opt-in sampler options; existing defaults are unchanged.
Any remaining target shortfall is reported, not disguised by repetition.

## Screening and Queue Ownership

`screened/reference-inputs.json` freezes 467 available reference files,
including inherited references, 89 accepted first-wave DFM12 packages and
the new instruction sources' retrieved held-out splits. This is **partial
inherited coverage**, not complete benchmark decontamination. Exact normalized
text/chat checks do not establish absence of fuzzy or translated overlap.

The SQLite reference index resumes at completed-file boundaries. Component
locks, checksummed receipts, atomic output replacement and transactional
ownership prevent races and permit recovery after partial writes. Both
translation directions are screened. Screened candidates are queued in
`screened/jobs.sqlite`, with `screened/audit-manifest.json` recording pending
calibration and incomplete coverage explicitly.

Superseded (2026-09-26): direct queueing of raw expansion candidates.
`european_expansion queue-audits` now runs the screening path first. Future
audit workers must use the screened queue. TrustLLM's 19,937 generation jobs
remain separate; generated answers still need screening and independent audit.
No TrustLLM answers were generated by this CPU campaign.

## OPUS Evidence

Preparation recorded 162 supplied pairs and 12 pairs with no approved direct
supply, across 174 new edges. The observed candidate snapshot was 2,982,857
parallel pairs. These counts are not accepted rows or guaranteed token caps.
All 504 unique corpus-version evidence requests completed without errors.
Evidence collection does not approve the remaining license-review entries.

GitHub's unauthenticated revision lookup returned HTTP 403. Reusing the pinned
OPUS metadata revision worked:

```bash
python -m dfm12.opus_review \
  --root data/dfm12/european-expansion-20260926 \
  --revision 42d4fbe382245487a68e853ca53bea832a41a02a
```

YAML dates in OPUS metadata must be normalized to ISO strings for JSON receipts;
the original YAML evidence remains retained. Quality exclusions and named
corpus-version approval policy are unchanged.

## English-Anchor Supplements

Owner authorized reuse on 2026-09-26. This supersedes the blanket no-new-pivots
restriction for the twelve new pair edges lacking approved direct supply:
CA-IS, CS-IS, DE-FO, EL-FI, EL-FO, EL-IS, ES-FO, ET-IS, FO-IT, FO-PT-PT,
FO-RO and FO-UK. Availability of shared anchors is not yet guaranteed.

`python -m dfm12.european_anchors` indexes existing approved EN-language
candidates on CPU, joins exact English strings within the same corpus/version,
and excludes anchors with multiple distinct translations on either side.
Both original lineages and English audit context are retained. This generates
no machine translations. Inputs are checksummed; completed outputs are immutable.
The job runs detached, with log `logs/dfm12_european_expansion/anchors.log`.

Each pair is capped at **165,332,456 rendered tokens**, both directions combined,
repeat 1. This is a conservative pre-audit cap, not an accepted-token guarantee.
The eventual per-epoch allowance must be shared with direct data, not added to
it; preparation fails if direct candidates have appeared for these missing pairs.
Additional repeats must not bypass this combined cap during final sampling.
After preparation, the job waits for the existing screening writer, then reuses
the resumable screening and audit queue path to include these components.
No GPU audit is launched. Existing direct pairs are not rewritten or expanded.

The earlier FO-NL feasibility probe found 122 shared anchors and 94 unambiguous
pairs; that establishes preparation feasibility, not quality acceptance for the
new pairs. Same-string English can hide meaning differences: bilingual audit
remains mandatory, including pt-PT variant verification.

### Corrected Anchor Result

Superseded, 2026-09-26: the initial zero-match reports were stale empty outputs
created before missing EN-FO/EN-IS bridge inputs and alphabetically ordered
DE-EN/EL-EN candidates were indexed. The original outputs were archived before
screening, not accepted or audited. Completed receipts now bind the entire
input-index signature and fail closed if inputs change. Both English directions
are handled explicitly. All twelve pairs have matches:

| Pair | Candidate pairs | Both-direction tokens |
|---|---:|---:|
| CA-IS | 84 | 7,236 |
| CS-IS | 368 | 33,444 |
| DE-FO | 125 | 10,768 |
| EL-FI | 1,494 | 129,870 |
| EL-FO | 52 | 4,798 |
| EL-IS | 363 | 32,356 |
| ES-FO | 126 | 10,678 |
| ET-IS | 120 | 9,714 |
| FO-IT | 74 | 6,820 |
| FO-PT-PT | 106 | 9,856 |
| FO-RO | 40 | 3,704 |
| FO-UK | 83 | 7,680 |
| Total | 3,035 | 266,924 |

## GPU Handoff

### Deferred European DaLA Import

2026-09-26: FI/CA/CS/ES DaLA was requested, then explicitly deferred pending
audit by the separate DaLA producer thread. The CPU import was stopped by its
verified process-group ID. Partial local preparation is retained at
`data/dfm12/dala-fi-ca-cs-es-20260926-v1`; it is not accepted training data.
The eight reserved components were removed from the active expansion handoff
so they do not block the already completed 216 components. Deferral evidence:
`data/dfm12/european-expansion-20260926/deferred-dala-fi-ca-cs-es.json`.
Do not restart the importer or queue a duplicate audit automatically. After the
producer audit, adapt the importer to consume its accepted-only outputs and
audit receipts, rather than importing all unaudited train pairs.

Completion verified: all 216 components screened and queued, with no missing
components. Input: 14,426,887 records; retained/audit queued: 14,420,705;
CPU exclusions: 6,182. The 64-worker process has exited. This supersedes the
in-progress indexing/screening snapshot below. GPU work has not started for
this expansion; partial inherited/benchmark coverage caveats remain unchanged.

All initial downloads/conversions and all twelve transformation replenishments
finished: 7,945,191 instruction candidates and 3,495,804 transformation rows.
Every transformation candidate target (including the 1.5x audit allowance) was
met. Reference indexing and screening/queueing continue on CPU; do not confuse
prepared counts with screened or accepted counts.

Use `dfm12.european_handoff`, not the earlier raw TrustLLM `transfer`/`audit`
commands for this expansion. The latter remain historical helpers but bypass
the expansion's new screened queue. The new stages are explicitly ordered:

```bash
python -m dfm12.european_handoff check
# Once check succeeds and endpoints have been explicitly allocated:
python -m dfm12.european_handoff generate \
  --endpoint http://localhost:8400/v1 --concurrency 64
python -m dfm12.european_handoff materialize
python -m dfm12.european_handoff audit \
  --endpoint http://localhost:8400/v1 --concurrency 64 \
  --reviewer-approval /path/to/reviewed-calibration-approval.json
```

Repeat `--endpoint` for each allocated server. The pinned request model is
`google/gemma-4-26B-A4B-it`. These commands neither create nor kill servers and
have not been launched for GPU work. Reuse explicitly allocated infrastructure;
do not attach clients to unrelated training/diagnostic servers. Concurrency is
per endpoint and should be validated against measured capacity before raising it.

`check` refuses incomplete CPU screening, missing anchor/direct/source components
or incomplete replenishment. `materialize` refuses unfinished generation jobs,
freezes terminal outputs, validates native prompt preservation and Gemma context
fit, then screens and queues only retained conversations. Request failures remain
recorded; they are not training examples. No final sampling is performed.

Audit requires a reviewed calibration approval JSON with `approved: true`,
`model`, all 21 `languages`, `audit_prompt_sha256` equal to
`dfm12.io.digest(dfm12.jobs.AUDIT_PROMPT)`, and `evidence_path` plus
`evidence_sha256` identifying the reviewed calibration report. This is a human
approval gate, not proof that an arbitrary supplied report passed calibration.
The first-wave nine-language approval and the other thread's smaller diagnostic
must not be treated as automatically covering the twelve new languages.
No such approval has been fabricated. Generation and independent audit use
different prompts; audit results are never inserted as assistant targets.

## Verification Results

## Delayed GPU Campaign (2026-09-26)

The owner requested a 30-minute delay, then TrustLLM generation followed by
the complete queued audit once all eight GPUs are free. Detached supervisor
PID 2930448 has a not-before time of **2026-09-26 21:26:10 Europe/Berlin**.
Receipts, status and logs are under
`data/dfm12/european-expansion-20260926/gpu-campaign-20260926-205610/`.
`status.json` records the supervisor phase; `generate/` and `audit/` contain
client status and minute-by-minute KV/concurrency measurements.

`dfm12.european_campaign` waits for two consecutive free-GPU checks, then
owns eight Gemma 4 26B A4B servers at utilization 0.90. It reuses them across
generation, materialization/screening, and audit. It never stops unrelated
processes. Cleanup signals only session/token/identity-verified owned servers.
`dfm12.european_stage` uses leased existing queues with one database writer,
bounded asynchronous requests, and up to four attempts. Concurrency starts
at 128 per server and adapts up to 1024 using KV usage and waiting requests;
the target is 50--90% KV, not a guarantee for short inputs. Repeated transport
failures stop the stage rather than exhausting the full queue.

The previous calibration gate remains applicable to **training admission**.
For this explicitly requested automated audit, the campaign collects judgments
after an operational positive-control check, not a purported 21-language
quality calibration. Its authorization receipt explicitly sets
`accepted_training_export_authorized=false` and
`multilingual_quality_calibration_complete=false`. No final sampling/export
is authorized by this campaign. FI/CA/CS/ES DaLA remains deferred to the
other thread's audit. Existing terminal failed requests remain recorded.

Five focused stage/handoff tests passed before launch; CPU readiness verified
216 components. GPU startup/inference has not yet been exercised by this
campaign because of the requested delay.

## Earlier Verification Results

### Audit resume authorized (2026-09-27 07:32)

### Lower-memory audit restart (2026-09-27 07:58)

### Smooth audit dispatch (2026-09-27 08:54)

Owner requested smoother utilization. The previous client drained outstanding
requests after SIGTERM, then its supervisor released all owned servers. New
supervisor PID 3548049 uses the same 0.45 allocation and existing audit database.
Logs: `data/dfm12/european-expansion-20260926/audit-smooth-20260927-085456/`.
Start concurrency is 96/server, based on observed active-request KV capacity,
not the previous burst of 512. This supersedes the burst-start configuration.

Telemetry now runs independently every 10 seconds, scraping all endpoints
concurrently with its own HTTP connection pool. Result flushing is a separate
coroutine, serialized through a flush lock and the existing single database
writer. Dispatch no longer waits for each telemetry/flush cycle. Uncommitted
results are bounded; final shutdown flushes before releasing owned leases.
Concurrency grows by only 2--8 requests per sample below 80% KV, provided the
current budget is actually being used and the server queue is small; it holds
in the 80--95% band, and falls 10% on preemption/high KV. Model/schema failures
no longer occupy an active slot while sleeping. Transport retries keep bounded
backoff. Eight tests passed including mock-HTTP end-to-end queue completion.
Live performance must be assessed after startup; no speedup is assumed.

The first launch stopped at its port preflight because recently closed sockets
were still unavailable to a non-reuse bind (no matching listening servers).
Preflight now uses SO_REUSEADDR, still refusing active listeners. Relaunched
supervisor PID **3549360** in the same work directory; `relaunch.json` records
ownership. All eight servers passed readiness and audit resumed. Initial
verification: 9,374 committed rows, about 4,925 rows/minute in the latest minute,
only two cumulative preemptions across all GPUs. This is not a throughput win:
client in-flight counts still exceed vLLM running counts, so further feeding
investigation remains necessary. Do not describe smoothing as a proven speedup.

Owner requested stopping the 07:32 audit and restarting all eight servers at
**0.45** memory utilization. The client handled SIGTERM and released its leases;
its supervisor shut down owned servers. Verified no GPU compute processes before
launch. The new supervisor is PID 3484988, with receipts/logs under
`data/dfm12/european-expansion-20260926/audit-mem045-20260927-075827/`.

The client previously waited for a durable transaction for every result on the
same database thread used to claim jobs. It now batches result/event updates
atomically (128 results or 0.5 seconds), retaining owner/attempt checks and
SQLite durability. Dispatch claims up to 1024 rows per transaction instead of
256. Requests no longer await individual commits. Completed counters count
committed results, and shutdown flushes before releasing remaining leases.
Future client SIGTERM drains outstanding requests before exit. This restart
starts at 512 requests/server (previously about 100 actually in flight), with
the same adaptive KV/preemption guard and 1024 ceiling. Seven focused tests
passed. Live throughput improvements must be measured, not assumed.

Live restart verification: all eight servers passed readiness and the audit
resumed. GPU memory was 85,986 MiB each; utilization 97--100%. The first full
snapshot showed 258--272 in-flight requests/server and 79--99% KV occupancy,
with preemptions. The controller reduced limits to 409 after further
preemptions. The next short interval committed about 7,962 rows/minute;
16,978 rows were committed since restart. This does **not** establish a 4--5x
throughput improvement or sustained 400--500 active requests/server. At this
smaller memory allocation, KV pressure already limits active concurrency;
keep the adaptive guard rather than forcing the requested multiplier.

Owner authorized resumption after the pause. Detached supervisor PID 3460253
uses `dfm12.european_campaign --audit-only --not-before 0`, with logs under
`data/dfm12/european-expansion-20260926/audit-resume-20260927-073208/`.
This supersedes the earlier no-restart instruction. It resumes the existing
screened SQLite queue with the hardened clients, preserving completed and
terminal failed rows; generation and materialization are skipped. Eight owned
Gemma 4 26B A4B servers use utilization 0.90 and adaptive client concurrency.
Startup and the operational positive control must succeed before dispatch.

### Campaign paused and client hardened (2026-09-27)

At the owner's request, stopped supervisor 2930448, audit client 3219849,
and all eight identity-verified owned servers. No GPU compute processes
remained at verification. Released 220 in-flight audit leases only after
confirming client/server exit, refunding the interrupted claim attempt.
Database snapshot: 2,124,876 done, 9,164 failed, 12,305,094 pending.
Completed and terminal failed rows were not reset. Receipt:
`gpu-campaign-20260926-205610/manual-lease-release.json` under the expansion root.
**Do not restart without a new owner instruction.**

Superseding the initial controller: a single HTTP/read error no longer halves
concurrency. Transport/408/429/transient-5xx errors receive bounded exponential
backoff with jitter; sustained infrastructure failure stops the stage and
releases its leases instead of consuming model-attempt budgets throughout the
queue. Model/schema failures retain bounded attempts and now save response
excerpts in `errors.jsonl`. SIGTERM/SIGINT cancel requests and release only
that client's running leases. Owner identity is persisted before dispatch.

KV control now increases concurrency gradually below 85% occupancy, holds at
85--95%, and reduces it on >95% or new preemptions. Queue pressure prevents
further increases but does not itself halve concurrency. These changes are
CPU-tested (six stage/handoff tests), not yet GPU-benchmarked.

Near-100% KV usage is not itself the throughput objective: cached prefixes can
occupy space without active work, while short audit inputs may saturate compute
before memory. On resume, compare sustained completed rows/minute, active and
waiting requests, preemption deltas and KV usage over matched windows. Aim for
85--95% if useful, leave output-growth headroom, and do not force 100% through
unbounded queuing. The current 1024 request/server ceiling remains; increase it
only after measuring benefit and confirming server sequence capacity. Existing
terminal failures are preserved for a separate, explicitly approved retry.

On 2026-09-26, 117 focused tests passed across European expansion, screening,
existing DFM12 converters and audit gates. Initial instruction preparation had
reached 6,965,671 candidate rows while more conversion was still running.
Replenishment and reference indexing were active, not finished. Audit acceptance,
accepted-only tokenization and final dataset integration remain subsequent gates.
