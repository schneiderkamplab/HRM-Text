---
type: Runbook
title: DFM12 CPU Audit Readiness
description: Refreshable multilingual review snapshots and non-runnable audit queues with pilot and accepted-only gates.
tags: [dfm12, audit, pilot, multilingual, cpu, provenance]
status: draft
last_updated: 2026-09-25
confidence: high
---
# DFM12 CPU Audit Readiness

## Local Accepted HF Packages

### Incremental Multi-Root Exports (2026-09-25)

The user authorized exporting and uploading newly completed accepted subsets,
including isolated Swedish DaLA and the existing local-only Icelandic DynaWord
package. This supersedes the fixed 52-package scope below, not the requirement
for completed sources, kept scores >=4, deterministic gates and package checks.

`export_finished --run` is repeatable. Supply **every owning audit root** for
existing and new packages; their component sets must be disjoint. Existing
package source descriptors must match this union exactly, and all inventoried
data/evidence file sizes and hashes are checked before appending. Missing roots,
duplicate ownership, changed pins and overwrites fail closed. Each audit root
gets a separate read-only completed/terminal freeze with bounded transactions.

Pass `--completed-swedish-authorization` explicitly for the isolated Swedish
root. The exporter forwards it to the existing scoped validator, pins and
bundles the authorization, and never broadens the default DaLA exclusion.
Operational approvals remain unchanged; export permission is recorded as a
separate user-requested operation. PL/IS scoped audit authorization is owned
separately, not implemented by this exporter change.

The preceding PL/IS limitation is superseded by
[scoped accepted-export support](/pages/dfm12-scandi-translated-instruct.md#accepted-export-support-2026-09-25),
including strict preservation of the separate identity companion inventory.

Example (CPU only):

```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -m dfm12.export_finished \
  --run data/dfm12/full-audit-20260924-v1 \
  --run data/dfm12/full-audit-sv-20260924-v1 \
  --completed-swedish-authorization data/dfm12/full-audit-sv-20260924-v1/completed-swedish-authorization.json \
  --crossscreen data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json \
  --output exports_dfm12 --authorize-local-accepted-export --incremental
```

Only after **exit zero**, including the final source/approval/screen pin checks,
run `python -m dfm12.upload_exports --output exports_dfm12`. The uploader uses
cached HF auth and its explicit package file allowlist; root snapshots, root
metadata and unregistered partial snapshots must never be uploaded.

New license mappings cover Norwegian DynaWord, the exact `SlayerLab/polish-dynaword`
repository and Dutch UltraChat. Constituent-table parsing supports linked source
names, lowercase headers and code-formatted labels. Existing per-record notices
are retained. Norwegian Wikipedia explicitly preserves both the upstream
collection/datasheet CC0 declaration and the prior preparation restriction to
retain Wikipedia attribution/share-alike obligations, bundling both pinned
datasheets and the preparation receipt. No replacement license is asserted.

The initial exporter PID 2014656 was deliberately stopped during copying to
correct that Norwegian caveat. `metadata/snapshot-20260925T042328-0/aborted.json`
marks the incomplete, unregistered local snapshot; zero packages were built and
the original 53-package manifest was untouched. The retry started at
`snapshot-20260925T042523-0`. Logs:
`data/dfm12/export-incremental-20260925-retry.log` and
`data/dfm12/export-upload-20260925-tests.log`.

The retry exited zero after all final pin checks. Main snapshot eligibility
took 0.063 seconds (241.6 seconds to copy); Swedish eligibility took 0.0035
seconds (196.5 seconds to copy). Source audits and servers were untouched.
Five new packages passed standalone validation:

| Component | Accepted rows | Audit rejected | Unresolved | Pre-audit quarantine |
| --- | ---: | ---: | ---: | ---: |
| dynaword-no | 370,048 | 144,697 | 70 | 93 |
| dynaword-pl | 198,590 | 61,046 | 41 | 59 |
| ultrachat-nl | 171,508 | 21,079 | 4 | 0 |
| dala-sv-acceptability | 740,980 | 24,302 | 1,004 | 0 |
| dala-sv-correction | 742,384 | 23,478 | 424 | 0 |

Newly exported: **2,223,510 accepted rows**, 274,602 audit rejections,
1,543 unresolved requests and 152 pre-audit quarantines. These counts start
from the screened audit inputs; earlier screening removals are separate.
Norwegian accepted language counts are 187,659 NN and 182,389 NB. The original
53 packages were preserved, yielding **58 packages / 3,431,930 rows**.
Including previously local-only `dynaword-is` (162,270 rows), publication
completed for six packages / 2,385,780 rows. The uploader exited zero, verified
each new commit's remote file inventory, and all **58** upload receipts match
their local package manifest hashes and row counts. No root metadata was
uploaded. A final read-only check found no other completed main components
awaiting export; unfinished audits remain outside this inventory.

| New public repository under `schneiderkamplab/` | Rows | Verified commit |
| --- | ---: | --- |
| dfm12-dynaword-is | 162,270 | `bdf35fdfc7ab9e47ed9ffbde077e3ecf88614723` |
| dfm12-dynaword-no | 370,048 | `12d3c74e0baaf13e7a79edb2700cc177e1fa81b7` |
| dfm12-dynaword-pl | 198,590 | `4061c3f1a6e737f3ad786bbade3909277e2d06eb` |
| dfm12-ultrachat-nl | 171,508 | `44ff1ca2d9039cf575646e32552f694237398860` |
| dfm12-dala-sv-acceptability | 740,980 | `3fa2cccf504fd1d77188674425d2ccf17c9010f6` |
| dfm12-dala-sv-correction | 742,384 | `b77fd7d4d903a2f7da3e526a83572bf0494c4d8c` |

Export PID 2016090 and uploader PID 2027997 exited successfully. Upload log:
`data/dfm12/upload-exports-20260925.log`; publication authority:
`exports_dfm12/metadata/upload-receipts.json`. Machine-readable parent/Tesla
handoff: `data/dfm12/export-upload-handoff-20260925.json`. Token accounting is
separately owned by Tesla; these are exact accepted row counts, not token
estimates. No audit, server, sampling, training or evaluation changes were made.

Regression verification: **27 tests passed** across export, license, upload and
audit-gate tests. The new upload test proves private root snapshots are absent
from the commit allowlist. Full source ownership/pin mismatch, default Swedish
denial, scoped authorization forwarding, hard-held-out gate preservation and
Norwegian license-caveat preservation are covered. Final test log:
`data/dfm12/export-upload-20260925-tests-final.log`.

### Public Upload Authorization (2026-09-24)

The user subsequently authorized uploading all completed datasets. This
supersedes the earlier no-upload instruction for the 52 validated packages,
not unfinished candidates or private root snapshots. Publish with
`python -m dfm12.upload_exports`: public repositories use
`schneiderkamplab/dfm12-<component>`. The uploader holds the export lock,
revalidates each package, uses an explicit file allowlist, refuses existing
repositories without its own matching receipt, and records commit IDs and
remote inventory verification in local-only
`exports_dfm12/metadata/upload-receipts.json`. It does not change source audit
approvals or training data. Historical `upload_performed: false` fields remain
pre-publication snapshot facts; the upload receipts are publication authority.
Source cards preserve all license caveats, including the two island instruction
sources' unspecified generated-instruction licenses.

Publication completed: all 52 packages (1,046,150 training rows) were uploaded
to public `schneiderkamplab/dfm12-*` repositories. Every commit's remote file
inventory was checked. An unauthenticated HF streaming load of
`schneiderkamplab/dfm12-opus-da-nb` verified the intended train split and native
message schema. Private root snapshots were not uploaded. Per-repository
commit hashes and completion times are in the upload receipts above.

### License Metadata Resolution (2026-09-24)

`dfm12.export_licenses` resolves missing export license labels using the
constituent tables of revision-pinned DynaWord/Dyna-Instruct cards, not their
collection-level CC0/CC-BY frontmatter. Future exports use this automatically.
For existing packages, run `python -m dfm12.refresh_export_licenses` under the
export lock. It stages and validates each package before replacement, retains
the previous package under local-only `exports_dfm12/metadata/license-refresh-*`,
refreshes checksums/inventory sizes, and preserves training bytes and original
audit records. Only the export provenance, evidence and card are enriched.

The Faroese/Icelandic reverse-instruction datasheets explicitly leave generated
instruction licensing unspecified while identifying underlying passage licenses
as CC-BY-4.0/CC-BY-SA-4.0. Preserve that distinction and the user's source-use
approval; do not invent a blanket license. Norwegian reasoning retains both its
upstream CC-BY-SA-3.0 notice and composite CC-BY-SA-4.0 claim. These are recorded
source declarations, not independent legal certification. Nothing is uploaded
by either command.

Completed refresh: eight packages and 349,608 accepted-record labels enriched;
337,030 have explicit constituent declarations, 3,159 preserve differing
upstream/composite share-alike claims, and 9,419 island reverse-instruction
records remain explicitly partially specified. All eight refreshed packages
passed the standalone validator. The 52-package inventory still contains
1,046,150 training rows and 378,826,787 compressed training bytes, unchanged.
Recovery copies and the refresh report are in local-only
`exports_dfm12/metadata/license-refresh-20260924T193924/`.

On 2026-09-24 the user explicitly authorized packaging audit-finished sources
under `exports_dfm12`, without uploading. This is an operation-specific
authorization, not a change to the running auditor's operational approval.
Use `python -m dfm12.export_finished --help` for the local exporter. Its snapshot
requires complete source preparation and no pending/running/parked jobs. Failed
requests are terminal unresolved exclusions, not quality rejections. Kept
decisions require all three scores at least four and a fresh deterministic gate
check. Existing package directories cannot be overwritten.

For later batches use `--incremental`. Existing source pins and package file
checksums must still match. Already exported components are excluded from the
new read-only snapshot and retained in the combined root inventory. Snapshot
copying first reads row IDs/components and only fetches selected record bodies,
avoiding rereading all previously exported source text.

Packages contain native chat JSONL gzip shards, dataset cards with explicit HF
data-file selection, audit metadata, checksums, bundled source attribution and a
standalone stdlib validator. OPUS pairs become two linked directional examples;
multi-turn messages and explicit assistant target indices are preserved. Excluded
conversations are absent even from uploadable metadata. Their full records are
retained only in the local root snapshot. **Never upload root
`exports_dfm12/metadata/`; upload only separately authorized nonempty validated
dataset folders.** Empty accepted subsets are not upload-ready. Root README and
manifest enumerate package counts and compressed data/whole-package sizes.

## Streaming Full Audit: 2026-09-24

### Authorized 512-Concurrency Deployment

**Supersedes the 256 settings below.** The user explicitly authorized 512
clients per endpoint and `--max-num-seqs 512` on all eight audit servers.
`audit_full --concurrency` defaults to 256 and now derives worker count,
connector limits, queue capacity, outstanding leases and pending preparation
capacity from that argument. At 512 on eight endpoints: 4,096 HTTP coroutines,
512 queued requests per endpoint, 8,192 maximum outstanding jobs, 16,384 pending
preparation capacity and one SQLite writer. Preparation remains 16 processes.

`dfm12.audit_resize` verified complete command lines, process birth times, GPU
ownership and unique internal ports before signalling anything. Client 1445687
drained via its SIGTERM handler, preserving **606,382 done results**, 266 failed
rows and 8,139 pending rows with **zero running leases**. Endpoint running and
waiting counters were also zero before API shutdown. Only the eight pinned APIs
were signalled; after all exited and GPU memory cleared, replacements launched
in parallel. Live environments were inherited in memory without printing or
persisting secrets. Only server `--max-num-seqs` changed; utilization remains
0.90, context 8,192, eager mode, model, GPU mapping and internal ports unchanged.

New API PIDs in GPU order: **1483285, 1483286, 1483287, 1483288, 1483289,
1483290, 1483291, 1483292**. Resumed client: **1483293**. Preparation children:
**1483296..1483311**. Exact server/client argv and baseline metrics are recorded
in `logs/dfm12-audit-20260924/servers-maxseq512/restart.json`; server logs are
adjacent `gpuN.log`. Supervisor PID 1482638 and its exact invocation are in
`logs/dfm12-audit-20260924/resize-512-process.json`; supervisor log is
`resize-512.log`. The unchanged full-audit run directory contains `runner-512.log`,
`process.json`, `configuration.json`, and preserved pre-512 process/config files.

The verification artifact `concurrency-512-verification.json` records health,
actual completed rows, per-endpoint active requests, KV usage, preemption counters
and retained errors. Compare measured rows/minute against the coordinator's
17-minute baseline of **16,120/min**, not token throughput. Larger concurrency
may approach KV capacity on longer rows, so a short mixed-corpus window is not
proof of a sustained speedup. No acceptance gate or source policy changed.

All eight health endpoints returned 200 and actual completions resumed on every
endpoint. Live PID/argv checks confirmed max sequences 512 and utilization 0.90.
The final **122.16-second** measurement increased done rows from **616,205 to
663,825**, or **23,388.5 completed rows/minute**, approximately **45% above** the
coordinator's prior 16,120/min baseline. This is a short, changing-corpus comparison,
not a controlled sustained benchmark. Observed KV use ranged **63.7%..75.5%**;
all eight preemption counters remained **zero**. Failed rows increased from 266
to 278: 11 incomplete length-limited generations and one contradictory keep/score
response. All remain retained failures, not accepted examples. Final sampled
pending/running counts were 15,783/7,606, with no producer error reported.

The measurement-only process was stopped after sufficient samples at the user's
request; client 1483293 and all eight servers remain running unchanged. **144 tests
passed**, including concurrency scaling and exact-PID safety; OKF validation
reported **zero errors and zero warnings**. The coordinating parent is explicitly
cleared to update central `dfm12-status`; this agent has not edited that page.

### Parallel Preparation Deployment

The user subsequently authorized CPU preparation parallelism. `audit_full`
now defaults to `--preparation-workers 16` (configurable 1..32), using spawned
processes rather than Python threads for tokenization, rendering and screening.
Each process owns one source iterator at a time and receives a request for only
one batch of at most 128 records. There is no unbounded process-pool submission
queue. A shared commit lock checks pending capacity before the single SQLite
writer commits a batch; new preparation cannot raise pending work above 8,192.
Duplicate component IDs are rejected, and every batch must start at the exact
next source ordinal. Records, quarantine decisions and cursor advancement share
one transaction. Full conversations, target indices and provenance are unchanged.

Source hashing checks a cancellation event between 4 MiB reads; row iteration
also checks cancellation. Preparation exchanges have a 300-second timeout and
cleanup bounds child joins before terminating only owned preparation children.
New clients handle SIGTERM/SIGINT by stopping preparation/claims and preserving
all already claimed HTTP results before exit. A stopped run writes `drained.json`,
not a false corpus completion receipt.

The original client lacked a drain handler. Deployment PID **1445687** was
launched with `--preparation-workers 16 --drain-client-pid 1413633`. Its
legacy-client transition parks newly inserted/pending/retry jobs using temporary
SQLite triggers while existing requests finish normally. Only after running
rows reach zero does it signal the exact verified old client, remove the triggers
and restore parked rows. Done rows and retry counts are never reset. On timeout,
parking is removed so the unchanged old client can continue. Parking can briefly
accumulate more work than the new producer limit because the legacy producer has
no pause handler; the new producer waits for any inherited excess to drain.
No server process is restarted or signalled by this deployment.

Commands/PIDs are recorded in `process.json`, previous client argv in
`process-serial.json`, deployment output in `runner-parallel.log` and completed
drain evidence in `legacy-drain.json`, all under the full-audit run directory.
The pre-deployment runtime is preserved in `runtime-before-parallel.json`.
**134 tests passed**, including real two-process versus serial preparation parity,
unknown Norwegian/full multi-turn preservation, quarantine parity, source cursor
rollback, concurrent producer bounds and legacy draining without lost responses
or retry resets. Existing 21 failed full-audit rows were all incomplete generations
(`finish_reason=length`); these remain failed/reviewable, not accepted or reset.

Deployment completed: the legacy drain took 57 seconds, stopped with **zero
running rows**, preserved **192,553 done rows**, and restored **20,170 parked
rows**. Preparation child PIDs are **1448431..1448446**, parent **1445687**.
All eight original server PIDs remained unchanged and no aborts were recorded.
The drain triggers were verified removed after transition.

`parallel-verification.json` preserves two post-transition samples 30 seconds
apart, after inherited pending work was below the new bound. Prepared/queued
records increased by **9,143**, successful decisions by **8,555** (approximately
302 prepared and 282 completed per second). Pending work increased from **3,765
to 5,149**; 43 sources had contributed rows. Thus parallel preparation was keeping
ahead of consumption rather than relying only on the parked legacy workload.
Total completed decisions reached **221,717**, with 24 retained failures and no
producer error. Endpoint occupancy varied from 226..252 in the first sample to
103..230 in the second; all eight continued serving. This verifies feeding all
GPUs, not a claim of constant full occupancy or uniform GPU utilization.
No additional restart was performed after this verification.

**Supersedes the historical server and client concurrency settings below.**
After explicit user authorization and draining pilot requests, all eight audit
servers were restarted with `--max-num-seqs 256`, utilization 0.90 and model
`google/gemma-4-26B-A4B-it`. API PIDs in GPU order are 1387943, 1387945,
1387946, 1387947, 1387948, 1387949, 1387950 and 1387951. HTTP ports remain
8400..8407; distinct internal `VLLM_PORT` bases are 26000..26700 in steps of
100. Exact commands and logs live in
`logs/dfm12-audit-20260924/servers-maxseq256/restart.json` and `gpuN.log`.
All eight endpoints have produced successful full-audit responses.

Detached client PID **1413633** runs `python -u -m dfm12.audit_full` using the
HRM environment. Its exact argv is in
`data/dfm12/full-audit-20260924-v1/process.json`; configuration, streaming
runtime, SQLite jobs, operational approval, source receipts and runner log are
in that directory. It uses **256 HTTP coroutines per endpoint, 2,048 total**,
one SQLite broker connection and bounded queues. It does not wait for the full
corpus to be staged. Verified runtime reached **44,615 completed decisions**,
129 pending and 796 leased/running, with no producer error; these are a dated
observation, not final counts. Every endpoint had more than 5,500 completions.

The source manifest pins 67 components. Filtered outputs from
`screened-candidates-20260924-v1/integration.json` supersede raw integrated
reordering and inclusive Norwegian inputs. Completed DaLA NB/NN/FO are included
from `dala-nb-nn-fo-20260924-v1/integration.json`; running PL/SV/IS are excluded.
Per-source completion evidence and hashes are checked while streaming.
Held-out screening remains enforced; legacy XML/native tool records are
deterministically quarantined, and oversized full conversations are quarantined
without truncation. Original records, provenance, rejection and failure results
remain available for review.

Operational review is recorded in `operational-approval.json`, **not a training
acceptance approval**. It documents all nine languages and unknown/mixed
Norwegian, the Polish XML-tool false acceptance and the contradictory Nynorsk
false rejection. Automated scores do not certify native-speaker quality.
No accepted exports, final sampling or training resumption are authorized.
Previous pilot snapshots/results remain unchanged. The expanded pilot ended
with 4,487 valid completions and 14 length-limit failures; the three earlier
pilots contributed 300 valid completions. Full audits allow 1,024 output tokens
and still reject incomplete generations.

Focused/full regression tests passed **128 tests**. A restart edge case was
fixed after launch: the next client invocation waits for existing live leases
instead of declaring completion before lease expiry. Error cleanup now cancels
worker tasks before closing the broker, and the producer's pending bound is
strict. These code fixes do not hot-patch or interrupt the active client.

Future readiness refresh must use the filtered integration and completed DaLA
integration separately from active pilot snapshots:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.audit_readiness refresh \
  --root data/dfm12 --output data/dfm12/audit_readiness_filtered_final \
  --workers 4 \
  --integration-manifest data/dfm12/screened-candidates-20260924-v1/integration.json \
  --integration-manifest data/dfm12/dala-nb-nn-fo-20260924-v1/integration.json \
  --crossscreen-manifest data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json
```

That final readiness snapshot is not claimed complete here; the full audit
already uses these authoritative integrations directly.

## Failed-Only Server Recovery and Expanded Review

At 12:11 UTC / 14:11 local on 2026-09-24, the coordinator explicitly authorized
relaunching **failed GPUs 2, 5 and 6 only**. Their original API and engine
processes had exited with c10d `EADDRINUSE` (ports 59947, 48179 and 45031).
GPU memory was zero on those three. The five live API PIDs
1030426, 1030427, 1030429, 1030430 and 1030433 were never signalled or changed.

Installed vLLM's `envs.py` and `utils/network_utils.py` confirm `VLLM_PORT` is
the internal starting port, with upward scanning; it is separate from the HTTP
`--port`. Replacement processes inherit the proven live GPU0 environment,
changing only `CUDA_VISIBLE_DEVICES` and `VLLM_PORT`. Environment secrets are
not written to receipts. Commands are unchanged except the HTTP port.

| GPU | API PID | Engine PID | HTTP Port | Internal Base | Log |
| --- | ---: | ---: | ---: | ---: | --- |
| 2 | 1236274 | 1238007 | 8402 | 25200 | `servers/gpu2.retry1.log` |
| 5 | 1236275 | 1238015 | 8405 | 25500 | `servers/gpu5.retry1.log` |
| 6 | 1236276 | 1237933 | 8406 | 25600 | `servers/gpu6.retry1.log` |

Logs are under `logs/dfm12-audit-20260924/`; exact commands and ownership checks
are in `servers/failed-only-relaunch-1.json`. The three replacements were launched
without waiting between startup phases. **No sequential-server-start policy is
authorized for future launches.** All three internal bases were subsequently
observed listening, and all eight GPUs reached 2,960 MiB allocated. This verifies
CUDA/distributed initialization progress, **not endpoint readiness or inference**.
Filesystem-bound imports, including Numba, were still progressing at this check.

The user then explicitly authorized executing the **full review-sample pool**
as a pilot, not the multi-million-row corpus. `dfm12/audit_review_gpu.py` stages
and executes that finite scope using the existing leased queue, HTTP query and
decision validators, with stage **`pilot-review`**, never accepted stage `audit`.
No human approval file or accepted export is created. Endpoint identity is
retained in each completed job's owner field and summarized per endpoint.

Expanded review client PID **1245362**, directory
`logs/dfm12-audit-20260924/pilot-full-review-v1/`, has **4,501 verified pending
jobs** after context validation and exclusion of 300 already-queued pilot record
IDs. Alongside 180 main, 40 Norwegian and 80 reordering records, this gives
**4,801 queued review jobs**, zero attempts at enqueue verification. It waits for
the reordering summary, then uses 32 workers per endpoint across all eight.
`plan.json`, `command.json`, `context-preflight.json`, `heartbeat.json` and
`jobs.sqlite` provide durable evidence. Later authoritative filtered/DaLA
refreshes must create a new plan rather than mutate these pinned queues.
The combined focused suite now passes **117 tests**. At 12:18 UTC all eight
GPUs had **52,144 MiB allocated** during safetensors loading; all HTTP model
probes were still unavailable and all 4,801 queue attempts remained zero.
`logs/dfm12-audit-20260924/endpoint-verification.json` preserves that distinction.

## Preliminary Post-Integration Refresh

On 2026-09-24, completed reconciled reordering and additive Norwegian were
registered in a **separate** output root,
`data/dfm12/audit_readiness_postintegration/`. This is preliminary: the later
request for completed DaLA NB/NN/FO and authoritative Poincare-filtered sources
requires another refresh after those owners supply integration manifests.
DaLA PL/SV/IS remain excluded while running. No bulk approval is inferred.

Snapshot `8f087c2ef87ddd169a8aff1ddf4fe4fb7e861b583f06de8407895932d55350be`
contains **61 components / 8,265,480 candidate rows / 4,801 review records /
6,839 student views**. Eight integrated reordering components total **256,360**
candidate rows: native paragraphs and synthetic text blocks remain distinct
tasks for NB/NN/NL/SV. The original readiness pointer and all active pilot
snapshot contents were left unchanged.

New implementation: `dfm12/audit_integration.py` verifies the reconciled receipt,
verification receipt and candidate hashes, writing only registration wrappers.
`dfm12/audit_gates.py` consumes the frozen Scandi cross-screen evidence.
Exact refresh argv/PID and output are in `refresh-process.json` and `refresh.log`
under the separate output root. The refresh uses both the Norwegian additive
manifest and `reordering-registration/integration.json`, plus
`--crossscreen-manifest data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json`.

Known gates are enforced before this module's accepted export, even after a
model `keep`: absent or stale screening evidence, input files not present with
the exact hash in coverage, held-out quarantine, unresolved duplicate chat and
shared-source review all block acceptance. No duplicate winner is selected.
Gate hashes cover reverse translation views too. Source/provenance and gate
metadata remain outside student messages. Generic shared export is not this
gated path and must not be used as a shortcut.

At review selection, **37 sampled rows were excluded**: 25 legacy Dutch
paragraph-reordering rows superseded by the reconciled pool, nine unresolved
shared-source rows and three duplicate Swedish integrated paragraphs. Full
candidate files were not rewritten. These are review-sample counts, not counts
of exclusions from the full corpus. Poincare owns authoritative filtered outputs.

Both actual Norwegian leakage rows were replayed from their source files and
blocked: `dynaword-no` ordinal 366300 and `blocks-v3:nb` ordinal 4096. Tests also
changed their IDs/components and still caught their held-out text/reference
hashes. Evidence: `real-heldout-gate-verification.json`. The two additive
Norwegian and eight integrated reordering files postdate the frozen cross-screen:
review is allowed but **accepted export remains blocked for missing coverage**.
Known exclusion application is not complete inherited/benchmark clearance.

The bounded reordering pilot is detached as PID **1133845**, 80 records (ten per
language/task component), in `logs/dfm12-audit-20260924/pilot-reordering-v1/`.
It waits for `pilot-norwegian-v1/summary.json`, which itself waits for the main
nine-language pilot. Exact argv is `command.json`; heartbeat and queue are
isolated. Canonical Gemma4 context preflight chooses fitting complete records,
not truncated turns, and records every considered length in
`context-preflight.json`. A later filtered refresh must not mutate this pinned
inspection queue. No server was interrupted or signalled.
Context preflight inspected 797 eligible reordering review records, all fitting;
the 80 selected prompts have a maximum of 5,012 input tokens plus 512 reserved
output tokens. Combined base/Polish/readiness/gate/integration/pilot tests:
**114 passed**. At the handoff all three queues were pending, zero attempts:
180 main + 40 Norwegian + 80 reordering. Final filtered/DaLA NB-NN-FO receipt
is pending the owner-provided manifests, not claimed complete here.

## Authorized GPU Pilot, 2026-09-24

The CPU-only scope below describes the earlier handoff, not the later explicit
user authorization to execute GPU review pilots. Bulk audits still require real
human pilot approval. No approval file or accepted training export is created.

Server ownership transferred to the coordinating agent, which launched eight
Gemma4 26B-A4B replicas on localhost ports 8400 through 8407. This worker did not
launch, restart or stop servers, training or scheduler processes. Server logs:
`logs/dfm12-audit-20260924/servers/gpuN.log`. Startup was initially blocked by
shared-filesystem reads of `libnvJitLink.so.13`; health is not an inference result.

Client implementation: `dfm12/audit_pilot_gpu.py`. Initial detached client PID:
**1032346**, with session independence via `subprocess.Popen(start_new_session=True)`.
Run directory: `logs/dfm12-audit-20260924/pilot-v1/`. Exact argv is recorded in
`command.json`; `client.pid`, `client.log`, `execution.json` and `jobs.sqlite`
retain execution evidence. The command is:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.audit_pilot_gpu \
  --snapshot data/dfm12/audit_readiness/snapshots/607a969eb79d7629f8259657140b167b2c1f4439a0764cd3f8b831dd46161184 \
  --output logs/dfm12-audit-20260924/pilot-v1 \
  --endpoints http://127.0.0.1:8400/v1 http://127.0.0.1:8401/v1 \
  http://127.0.0.1:8402/v1 http://127.0.0.1:8403/v1 \
  http://127.0.0.1:8404/v1 http://127.0.0.1:8405/v1 \
  http://127.0.0.1:8406/v1 http://127.0.0.1:8407/v1
```

This finite queue contains **180 records, 20 assigned per language**, stage
`pilot-audit` rather than executable accepted-data stage `audit`. Translation
records may cover a language via their reverse direction without relabelling
the record. The existing leased queue, HTTP client and decision validator run
with **32 workers per endpoint**, strict JSON-schema responses, thinking off,
and a 1,024-token response budget. Only complete, schema-valid decisions count.
Model readiness is checked before requests. Final `summary.json` reports actual
completions and decisions; model `keep` never means human approval.

The pilot prompt explicitly permits authorized unknown-standard and mixed
Norwegian, while requiring punctuation and speaker/wording preservation. The
additive integration retains `language=no`, original message languages and
speaker metadata, not a blanket NB label. `--norwegian-supplement` selects a
separate bounded 20 unknown + 20 mixed review, only from the pinned authorized
adapter. Refresh integration before running that supplement in a new directory.

Tests: `tests/test_dfm12_audit_pilot_gpu.py` plus readiness tests: **22 passed**
at initial client launch. Final sampling, bulk activation and accepted exports
remain out of scope. Later readiness refreshes do not silently change an already
running, pinned pilot queue.

### Context Preflight and Additive Refresh

The initial client above was superseded **before any attempt**: two full audit
prompts (7,192 and 7,391 tokens) plus a 1,024-token allowance exceeded the server's
8,192-token context. The response allowance is now **512**, with no input text
truncation. `pilot-v1/superseded.json` preserves that history. Its PID was the only
process stopped by this worker; no server or unrelated process was touched.

Current detached clients: **1037186** (`pilot-v2`, 180 nine-language records) and
**1042363** (`pilot-norwegian-v1`, 40 additive Norwegian records). Each run directory
under `logs/dfm12-audit-20260924/` contains exact `command.json`, `client.pid`,
`client.log`, `execution.json`, `context-preflight.json`, and isolated `jobs.sqlite`.
Both commands use the endpoints above; the Norwegian client adds
`--norwegian-supplement --after logs/dfm12-audit-20260924/pilot-v2/summary.json`.
It replaces idle PID 1037187 before any attempts and waits for the main pilot to
finish, preserving the aggregate limit of 32 requests per endpoint. Both pin snapshot
`8e5ec69e1c16ae8a15a23e1d36e025b07799321d4448ea104ba1d01a7581eeba`.
Context checks passed for **all 220 requests**, max input 5,899 tokens in the main
pilot and 2,689 in the supplement, each with 512 reserved output tokens.

The refresh command used the original root/output flags plus:

```bash
--workers 2 --integration-manifest data/dfm12/norwegian-inclusive-20260924-v1/integration.json
```

This completed snapshot adds **4,496 unknown-standard punctuation rows and 1,245
mixed NB/NN pairs** to readiness, producing **53 components, 8,009,120 candidate
records, 4,038 review records and 6,076 student views**. The supplement samples
20 from each authorized category, retaining full conversations and speaker
metadata in the auditor record. Generic Norwegian does not count as NB coverage.
At 10:48 UTC clients were polling health with **zero attempted/completed requests**;
server launch/readiness remains owned by the coordinating agent. Do not report
pending jobs or endpoint health as successful audits.

Before any requests, the main selection was corrected to round-robin the actual
top-level component field, not a nonexistent provenance component. Evidence:
`pilot-v2/selection-verification.json`. All **51 original completed components**
are represented, including all six original instruction sources, both Polish
sources and FO-NL; the separate supplement adds the two Norwegian constituents.
At 10:49 UTC all eight coordinator-owned server PIDs 1030426 through 1030433
were still in `folio_wait_bit_common`, elapsed over six minutes, with GPU memory
and utilization zero. Clients remain detached and ready; this is a filesystem
startup blocker, not verified GPU execution. Combined base, Polish, readiness
and pilot tests: **101 passed**, including component round-robin coverage.
`logs/dfm12-audit-20260924/pilot-progress.json` records a timestamped queue check.

### Read-Only Startup Investigation and Durable Waiting

At approximately 11:09-11:12 UTC on 2026-09-24, all eight original server PIDs
1030426-1030433 remained alive in `folio_wait_bit_common`, with empty logs and no
inference. **No server was signalled, restarted, reconfigured or otherwise
modified.** The user explicitly required leaving these imports/loading intact.

The earlier observation of `libnvJitLink.so.13` must not be read as a permanent
single-library hang. Read-only `/proc/<pid>/fd` snapshots now show progression
through `filelock`, `torch/_thread_safe_fork`, then `networkx` bytecode files.
Across 30.91 seconds each server advanced by 316 read syscalls / 1,246,556
characters; over the following 111.39 seconds each advanced by 365 calls /
2,541,310 characters. All replicas were reading the same current import file.
This is observable progress at very low completed-read throughput, not proof
that normal model initialization should take this long.

The audit environment resolves onto the **WEKA filesystem** at `/work/mimir`,
not local disk. Its mount reports `readahead_kb=32768`. Even the 187-byte
`torch/_thread_safe_fork` bytecode appeared as the common blocked descriptor.
There was approximately 2 PB free on that mount; cgroup CPU throttling was zero,
no cgroup IO limit was set, and memory `max` events stayed at 736 with zero OOM
kills during the check. These observations support shared file-page read latency
during small-file imports as the immediate bottleneck. They do **not** identify
the backend storage/network fault or establish that memory reclaim is irrelevant.
Kernel stacks/syscalls were permission-denied, WEKA admin tools unavailable,
and block `read_bytes=0` is not a reliable measure of WEKA traffic here.

Raw evidence: `logs/dfm12-audit-20260924/io-evidence-{1,2,3}.json`, recording
timestamps, per-process descriptors, wait channels and IO counters/deltas.
No extra bulk reads, cache eviction, environment copying or storage tuning was
performed. Backend diagnosis would require platform/storage telemetry outside
the available container permissions; current server startup must remain intact.

Both original pilot clients were alive, not lost; the Norwegian supplement was
silently waiting for the prior summary. To remove the old one-hour expiry, only
the two idle **client** processes were replaced. Current PIDs are **1099398**
(main) and **1099399** (Norwegian supplement), still detached. The command files
are unchanged. Queue equality checks under SQLite write transactions verified
all **180 + 40 pending rows unchanged**, with zero attempts/results at handoff;
checksums and old/new PIDs are in `client-readiness-handoff.json`.

Readiness now defaults to **indefinite** waiting, with no job claims or attempt
consumption while endpoints are unavailable. Optional `--readiness-timeout N`
is available, but neither running command sets it. Each run writes atomic
`heartbeat.json` every 30 seconds, including PID, timestamp and wait reason.
The supplement heartbeat explicitly names its dependency on the main summary.
Every endpoint is rechecked for the expected model on each readiness pass.
Summary writes are atomic so the supplement cannot observe a partial file.
Tests cover waiting beyond the former one-hour limit and refusal of a wrong
model; combined base, Polish, readiness and pilot suite: **103 passed**. At
11:13:30 UTC both queue integrity checks returned `ok`, all 220 jobs remained
pending with zero attempts, and both heartbeats were fresh. No pilot approval,
acceptance or final sampling is implied by readiness.

## Scope and Current Result

Implementation: `dfm12/audit_readiness.py`; tests:
`tests/test_dfm12_audit_readiness.py`. All operations in this handoff were CPU-only.
No teacher endpoint, GPU worker, server, training, evaluation, final sampling or
accepted export was run. Existing preparation outputs and the central
`data/dfm12/jobs.sqlite` were not modified. Central status/index ownership stays
with the coordinating agent; this new page needs its index handoff.

The completed refresh inspected **51 components / 8,003,379 candidate records**
(a translation pair counts as one record), selecting **3,838 review records**
and **5,876 student-facing directional views**. Every observed sampling stratum
has representation in this snapshot. These are review samples, **not accepted
training data or a final DFM12 mix**.

Covered completed preparations:

- All six original instruction routes: EN/NL DaLA, Dutch UltraChat, NL/PL/SV Dolci.
- Polish main PLLuMIC and PLLuM-Align, kept as separate components.
- Completed Icelandic/Faroese DynaInstruct v3, without adding earlier alternative runs.
- Norwegian Magpie Bokmaal and same-variant NB-Samtale pairs; ambiguous holds excluded.
- All six original DynaWord candidate files spanning seven new languages.
- All 32 prepared direct OPUS pair groups, plus the separate FO-NL English-anchor route.

FO-NL has all **94 joint pair records / 188 directional views** in the review.
Its English anchor remains in provenance/audit context, not appended to student
messages. Align's **100 sampled records retain `target_message_index`** for the
final preferred assistant response; earlier assistant turns remain context.

Related: [component preparation](dfm12-components.md),
[Polish staging](dfm12-polish-instructions.md),
[island instructions](dfm12-island-instruct.md),
[Norwegian preparation](dfm12-norwegian-dynainstruct.md),
[structure-preserving reordering](dfm12-structure-preserving-reordering.md).

## Evidence and Coverage

Output root: `data/dfm12/audit_readiness/`.
`latest.json` resolves the current immutable snapshot. At this check its ID is
`607a969eb79d7629f8259657140b167b2c1f4439a0764cd3f8b831dd46161184`.

Within `snapshots/<ID>/`:

- `REPORT.md`: per-component scanned/review counts and pending integrations.
- `manifest.json`: full-corpus source paths, receipt/candidate hashes, row counts,
  language/task/stratum coverage and review-file hashes. Full-corpus audit jobs
  are **not** enqueued; this is the manifest for their later preparation.
- `review_only/student_views.jsonl`: only ID, native role/content messages and
  optional assistant target index. These views are explicitly review-only.
- `review_only/audit_records.jsonl`: full record, attribution, audit context,
  source record ID, component, source checksum and source-file ordinal.
- `staged_jobs.sqlite`: existing `Queue` API / `audit_payload` schema, but stage
  **`audit-staged`**, not executable `audit`.

Root evidence: `refresh.log`, `refresh-repeat.log`, and
`verification-<ID>.json`. The repeat refresh returned the same snapshot and
3,838 jobs without adding duplicates. Verification found all jobs pending,
zero attempts, zero accepted exports and no activated queue.

| Language | Student-facing review views |
| --- | ---: |
| English | 600 |
| Danish | 505 |
| Dutch | 1,014 |
| Bokmal | 922 |
| Nynorsk | 473 |
| Swedish | 768 |
| Icelandic | 338 |
| Faroese | 332 |
| Polish | 924 |

Audit-record task counts: acceptability 100, correction 100, instruction 1,000,
denoising 168, prefix continuation 166, span filling 166, paragraph reordering
100, and joint translation pairs 2,038. Translation views are counted twice in
the language table but only once in audit records.

The original candidate set has no native paragraph-reordering rows for **NB,
NN or SV**. This is a real coverage gap, not an omitted existing stratum.
Isolated repair/alternative runs are deliberately not added before the owning
agent reconciles them. Synthetic sentence blocks must keep their distinct task
labels and boundary provenance, not masquerade as original paragraphs.

## Refresh and Integration Contract

Run from repository root:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.audit_readiness refresh \
  --root data/dfm12 --output data/dfm12/audit_readiness --workers 4
```

The command starts no model clients. It verifies candidate SHA256 against
completed receipts and checks source stability. It scans all candidate rows,
keeps bounded deterministic hash-ranked samples per language, reverse language,
task, constituent, length bin, turn-count bin and DaLA yes/no label, then selects
up to 100 per component with round-robin language/task coverage. Sampling is
for inspection, not a claim of prevalence-weighted quality or acceptance rate.
Observed-stratum counts and uncovered strata stay visible in each manifest.

Workers are capped at 16; this run used four. Cached sample selection is reused
only after source checksums are revalidated. Source receipts, integration
evidence, code hash and settings define the immutable snapshot identity.
Changed input or integration creates a new snapshot and moves `latest.json`;
superseded snapshots cannot be activated or exported by this module.

Later complete integrations can be supplied with `--integration-manifest PATH`
or deposited under `data/dfm12/audit_readiness/integrations/*.json`. Schema:

```json
{
  "version": 1,
  "status": "complete_unaudited",
  "supersedes": ["dynaword-nl"],
  "resolves": ["reordering-integration"],
  "components": [
    {
      "component": "dynaword-nl-reconciled",
      "family": "transformation",
      "path": "/absolute/path/to/candidates.jsonl",
      "receipt": "/absolute/path/to/receipt.json",
      "sha256": "candidate SHA256 matching the completed receipt"
    }
  ]
}
```

Paths should be absolute. The completed receipt must contain `sha256` or
`candidates_sha256`. Each candidate needs ID, native messages, language, task,
provenance, and transformation reference `audit_context` where applicable.
`supersedes` replaces **whole named components**, not only one task within them:
the integration owner must retain all desired tasks when replacing a combined
original component. Omit `supersedes` for genuinely additional sources. Duplicate
component keys fail closed. Running/incomplete manifests stay pending and their
partial candidate files are not read.

`resolves` is an explicit handoff declaration, not automatic scientific
clearance. Current pending keys: `reordering-integration`, `additional-dala`,
`norwegian-variant-holds`, `cross-source-screening`, `identity`, `pllumic-syn`,
`scandi-instruct`, and `danish-increments`. The last three describe explicit
deferral/no-cleared-rows/no-new-rows rather than a requirement to manufacture
additional data. This module does not access gates or duplicate other agents'
generation/preparation work.

## Pilot and Acceptance Gates

The existing `dfm12.pilot.require_pilot` checks the approved model, all nine
languages and explicit review evidence. **No approval file was created here.**
The real activation attempt failed with:
`Pilot review required before bulk work: data/dfm12/pilot-approval.json`.
No `approved/` directory was created.

After genuine pilot sign-off, explicit activation is CPU-only:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.audit_readiness activate \
  --snapshot /absolute/path/from/latest.json --pilot-root data/dfm12
```

This revalidates source/review hashes and stages runnable `audit` jobs in
`<snapshot>/approved/jobs.sqlite` using the existing Queue and audit-payload
APIs. It still runs no GPU client. Existing generation/audit pilots in the
central queue remain separate: coordinate which queue to execute so overlapping
pilot examples are not audited twice. Activation covers review samples only;
it does not enqueue or accept the remaining millions of source rows.

Optional future accepted export:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.audit_readiness export-accepted \
  --snapshot /absolute/path/from/latest.json --pilot-root data/dfm12 \
  --output /new/immutable/accepted-review-subset
```

Export again requires pilot approval and a current unchanged snapshot. It reads
only completed `audit` jobs, verifies each payload against the immutable review
record and uses existing `validate_audit` score/decision checks. Only explicit
`keep: true` records are emitted; pending, running, failed and rejected rows
cannot enter student output. An empty accepted subset is refused. Both
translation directions share one audit decision. Student data and audit/
provenance sidecars stay separate, and target indices survive export. Retokenize
that accepted subset; never reuse whole unaudited arrays after row rejection.

**Integration risk discovered:** the shared `prepare.export_accepted` currently
omits `target_message_index`. Do not route the Align review through that generic
exporter without a coordinated fix; this module's isolated accepted-subset
export preserves the index. Shared code was not modified here.

## Verification

The combined readiness/Polish/base DFM12 suites passed **92 tests**, including
15 readiness tests. Coverage includes deterministic full-file stratification,
cache/source changes, held-out/ambiguous-language rejection, metadata isolation,
joint translations, pilot/model/language gates, staged non-runnability,
idempotent activation, accepted-only decisions, malformed audit scores,
superseded snapshots, immutable outputs and replacing rather than adding an
integrated component.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_audit_readiness.py tests/test_dfm12_polish.py tests/test_dfm12.py -q
```

Runtime verification also checked all student message keys, exact student-view
reconstruction, every sampled Align target index, all nine languages, FO-NL
anchor isolation, staged queue status/zero attempts and the real pilot gate.
No quality score, human fluency judgment or corpus acceptance is claimed.

OKF validation reported only missing central index links for this page and the
concurrently added `dfm12-dala-registration.md` and `dfm12-token-accounting.md`.
Those index updates are left to the coordinating parent, as requested.
