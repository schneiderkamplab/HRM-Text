---
type: Runbook
title: Joint Nineteen-Language Synthetic Production
description: Shared request scheduling over the existing seven- and twelve-language ledgers.
tags: [dfm12, synthetic, multilingual, operations]
status: draft
last_updated: 2026-09-29
confidence: high
---
# Joint Synthetic Production

## Campaign Complete And Published, 2026-09-29

Supersedes the in-progress reopening state below: all 19 languages reached all
six family targets, with **875000 accepted conversations**, zero active jobs,
zero waived/remaining targets and no worker/recovery errors at completion.
Final progress is recorded at
`data/dfm12/joint-synthetic-source-expansion-20260929/progress.json`.

The owner subsequently authorized public upload and DFM12 integration.
The final six-language export is
`exports_dfm12/multilingual-final-six-20260929-v1` (350000 conversations).
All 19 packages, including the earlier 525000-row export below, are published
as `schneiderkamplab/dfm12-multilingual-synthetic-{language}` with verified
remote hashes and row counts. Canonical publication receipts are under
`exports_dfm12/multilingual-publication-20260929-v1`; sealed local exports keep
their historical local-only metadata, while publication cards/receipts record
the later authorization and release.

DFM12 integration and tokenization are complete; see
[DFM12 status](dfm12-status.md) for input paths, exact token counts and repeat
policy. Final epoch sampling was not rerun. Shared vLLM servers and unrelated
GPU processes were not changed by export, upload or tokenization.

## Completed-Language Export Scope, 2026-09-29

User requested local export (not upload) of the languages whose six family
targets are all reached. The selected cohort is **de, el, es, fi, fr, it, nb,
nl, nn, pl, ro, sv, uk**: 13 languages and **525000 accepted conversations**.
NB and NN contribute 70000 each; the other eleven contribute 35000 each.
The six reopened languages are excluded from this export snapshot.

Export must use read-only ledger snapshots and preserve all accepted origins:
production, the original pilot, and the first pilot's re-audited imports.
Do not use `export_validator.training_rows` here: it projects messages down to
role/content and would discard native tool-call fields and tool definitions.
Keep native messages and tools intact, with audit/source metadata separate
from the training data. Packaging and full row/hash verification completed at
`exports_dfm12/multilingual-completed-20260929-v1`; no upload was performed
or authorized by this request.

## Six-Language Reopening, 2026-09-29

User authorized unblocking Czech, Catalan, Icelandic, European Portuguese,
Estonian and Faroese, explicitly allowing more generated candidates per source
row where unique source inventory is limited. This supersedes the earlier
Faroese family waiver below: grounded instruction, multi-turn and summary/rewrite
are to be replenished toward their original targets. Accepted targets and quality
gates do not change. Reuse must retain source IDs, produce fresh candidate slots,
and preserve duplicate rejection and independent review.

The previous joint client PID 2423945 drained cleanly at **722234 accepted,
zero active** before implementation. Identity clients and all shared servers
were left running. Source reuse and expanded six-language attempt limits are
being implemented as explicit extensions, not silent edits to sealed campaigns.

Implementation is now available via `--source-expansion` on the parallel
runner: 24 attempts per target accepted row for these six languages (other
languages remain at six), and at most 32 source allocations including the
original allocation. This is not 32 copies of accepted examples. Unique eligible
sources are used first, followed by durable round-robin reuse with fresh slots.
The source provider preserves original selections and source IDs in a sidecar
`source-reuse.sqlite`; quality checks and duplicate rejection remain unchanged.

Each campaign gets a SQLite backup `jobs.source-expansion-v1.backup.sqlite`
and explicit `source-expansion-v1.json` receipt. Migration preserves historical
group/job counts. Future launches of migrated campaigns require the opt-in;
old standalone runners are not compatible with the expanded attempt budgets.
If interrupted before migration commits, an existing uncommitted backup fails
closed for manual inspection rather than being overwritten.

Launch PID **1056294**, root
`data/dfm12/joint-synthetic-source-expansion-20260929`, log
`logs/dfm12/joint-synthetic-source-expansion-20260929.log`.
Same two clients/server, 1024 combined slots/server and 100% KV admission as
the prior launch, plus `--source-expansion`. 86 source-reuse, migration and
scheduler tests passed. Both migrations completed and production resumed with
16 workers and zero waived rows. Initial verification found Faroese at 28212
accepted with 1157 active and Portuguese at 15796 accepted with 1144 active;
these previously blocked source-backed groups are advancing. All eight GPUs
were active (79-100%). The existing attempt/target fairness order initially
prioritizes the most source-starved groups; all six expanded languages are
eligible, but need not have simultaneous active reservations.

Math/code exhaustion is not a GPU issue. Czech had 18000 attempts for 2244
accepted; common failures included competing final boxes (3482), invalid text
controls in user text (2659), repeated-text loops (1241), and length exhaustion
(914). Increasing attempts must not weaken these checks.

## Authorization

On 2026-09-28 the user requested restarting the original seven and new twelve
languages as one joint campaign, with approximately 512 concurrent requests
per GPU. This supersedes the separate standalone concurrency ceilings of
64 and 16 respectively for this joint launch only. Generation/review contracts,
accepted-row targets, source reuse restrictions and model choice are unchanged.

The existing campaign roots remain authoritative:

- `data/dfm12/multilingual-quarter-native-20260927`
- `data/dfm12/european-synthetic-tenth-20260928`

At the clean pause both had `phase=drained`, zero active work, and respectively
217458 and 7420 accepted rows. Preserve both ledgers, accepted rows, immutable
specifications, source cursors and fingerprint ownership. Joint scheduling does
not mean copying rows into a new dataset or recounting accepted pilots.

The three waived Faroese families remain intentionally complete: grounded
instruction 2453, multi-turn 601, summary/rewrite 725. Do not replenish or retry
them. Effective combined target is 343779 + 490000 = **833779** accepted rows,
subject to other source/attempt limits. The sealed original nominal targets
still sum to 875000; report the waived 41221 separately.

## Server And Admission Limits

Existing shared servers on ports 8600-8607 use Gemma-4-26B-A4B-it. Inspection
at this restart found max_num_seqs=1024, max_model_len=16384,
max_num_batched_tokens=16384, memory utilization 0.80, TP=1 and eager mode.
These servers were externally restarted; this joint-campaign work did not
change, stop or launch them. Other threads may use them.

512 is a joint per-endpoint in-flight ceiling, not a guarantee that 512 long
requests can decode simultaneously. GPU0 reported 426696 KV-token capacity,
only about 833 KV tokens per request at 512 requests without cache sharing or
other allocation effects. Preserve KV and queue backpressure and monitor actual
running/waiting counts. Generation and review share the same request budget.

Related: [original seven](dfm12-multilingual-quarter-production.md),
[new twelve](dfm12-european-synthetic-production.md).

## Dispatcher

`python -m dfm12.joint_synthetic_campaign run` uses the existing ledger,
provider and generation/review implementations. One process holds both original
controller locks and a joint runtime lock; SQLite reservations and acceptance
remain on its sole event-loop thread. The new joint root records explicit
concurrency authorization and pins the original manifests and implementations.
Old sealed manifests are not silently rewritten to authorize throughput changes.

One round-robin queue supplies all eight endpoints. After one campaign has no
eligible work, the other can consume its available client capacity. Individual
Faroese waivers are checked before source allocation. HTTP pool limits are
shared across campaigns, not 512 for each campaign independently. In-flight
generation and review drain on SIGTERM; no server receives a signal.

Initial sealing expects an empty joint root except for its lock; redirect the
launch log outside that directory. Request timeout remains 600 seconds. Do not
launch standalone controllers while the joint dispatcher owns their locks.

## Initial Launch, 2026-09-28 (Superseded)

Launched detached PID **4064676**, using the `hrm` Python environment:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.joint_synthetic_campaign run \
  --root data/dfm12/joint-synthetic-20260928 \
  --concurrency-per-server 512 --timeout 600 \
  --admission-spacing 0.002 --max-kv-cache-utilization 0.90
```

Launch receipt: `logs/dfm12/joint-synthetic-20260928.launch.json`.
Error/output log: `logs/dfm12/joint-synthetic-20260928.log`.
Combined status: `data/dfm12/joint-synthetic-20260928/progress.json`.
Per-campaign progress remains at the original paths. The joint runtime has a
new manifest/seal; original campaign manifests and quality pins were untouched.

78 tests passed across joint scheduling, retained ledger operations and
admission control. The joint query adapter translates HTTP exceptions into the
European private controller's exception class, preserving its retained retry
policy. All endpoints permanently paused now drain and report blocked instead
of waiting forever. These fixes are confined to the new wrapper.

## Current Fresh-Connection Launch

Initial PID 4064676 drained cleanly at 225786 accepted and zero active rows.
Some generation/review POST requests failed before receiving headers with
`ServerDisconnectedError`, triggering 30-second endpoint cooldowns despite low
KV usage. Server logs did not show matching crashes. Stale pooled connections
were plausible, not proved. The controlled replacement disables connection
reuse on the inference HTTP pool only (`force_close=True`); the monitoring
pool and all quality/retry rules are unchanged. Unknown-status failed requests
were not automatically replayed.

Current detached PID: **4083705**. Current joint root:
`data/dfm12/joint-synthetic-20260928-fresh-connections`.
Log/launch receipt:
`logs/dfm12/joint-synthetic-20260928-fresh-connections.{log,launch.json}`.
Same command as above, changing only `--root` to this fresh joint root.
Fresh runtime pins preserve the initial runtime manifest as historical evidence.
79 focused tests pass after the transport change. Both underlying campaign
directories and all accepted rows remain unchanged in location.

## Client Underfeeding Diagnosis

The initial 512-client limit did not translate into that many running requests.
A measured window showed only roughly 100-170 concurrent server requests in
total, low KV usage and underutilized GPUs. Fresh inference connections removed
the early repeated disconnect/cooldown pattern in the observed replacement
window, but did not remove the serial client bottleneck.

A bounded restart-based cProfile run collected 60 seconds of active production
plus startup/drain (110.46 seconds total). Artifact:
`logs/dfm12/joint-client.cprofile`. External py-spy attachment failed with
permission errors, including sudo; no kernel permissions were changed.
Profile cumulative costs include 21.5 seconds in JSON-schema checking,
11.4 seconds in streaming loop guards, 5.65 seconds in 415 full Prometheus
metric parses, and 3.25 seconds in 407 reservations. Filesystem opens, replaces
and fsync also run synchronously. These times overlap by call hierarchy and
must not be summed as independent totals. Profiling overhead means they are
diagnostic proportions, not uninstrumented wall-time predictions.

The profile drained successfully and automatically resumed ordinary production
as PID **4111301** using the same fresh-connections runtime root. This supersedes
PID 4083705 above. A separate per-endpoint process implementation is being
prepared to parallelize CPU validation and I/O without weakening checks or
giving multiple processes write ownership of the ledgers.

## Parallel Client Design

`dfm12/joint_synthetic_parallel.py` moves candidate processing into eight CPU
processes, one per existing server. Each process has its own event loop,
tokenizers, validators, HTTP pool and endpoint admission gate. It does not load
a model onto a GPU. One parent retains source selection, ledger writes and
accepted-row materialization. Private bounded socket RPCs carry reservations,
atomic fingerprint claims and terminal notifications. A separate synchronous
claim channel preserves the retained processor's synchronous deduplication
interface without blocking on its own event loop.

Children report completion only after all owned requests and terminal records
are finished. Recovery must never run while an old worker can still write;
runtime lock ownership must therefore outlive all endpoint workers. Any later
profiling or scheduling optimization must preserve this lifetime constraint.

## Initial Parallel Launch (Superseded)

Supersedes the serial launches above. PID 4111301 drained at **229276 accepted,
zero active**. Replacement parent PID **4154133** launched detached with eight
spawned CPU workers, PIDs 4154247-4154254, serving ports 8600-8607 respectively.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.joint_synthetic_parallel run \
  --root data/dfm12/joint-synthetic-parallel-20260928 \
  --concurrency-per-server 512 --timeout 600 \
  --admission-spacing 0.002 --max-kv-cache-utilization 0.90
```

Status: `data/dfm12/joint-synthetic-parallel-20260928/progress.json`.
Log/receipt: `logs/dfm12/joint-synthetic-parallel-20260928.{log,launch.json}`.
Launch observations: `logs/dfm12/joint-parallel-startup-observation.json`.

Workers inherit duplicated descriptors for the same exclusive controller locks,
retaining them through event-loop cleanup even if the parent dies. Replacement
controllers therefore cannot recover a ledger while old workers can still
write. RPC deadlines are 60 seconds. A genuinely uninterruptible worker can
still hold locks until it exits; this blocks recovery safely rather than
allowing concurrent writers. Stop the verified parent PID with SIGTERM to drain;
do not kill the shared vLLM servers. Do not start the old standalone clients.

Initial parallel server snapshot reached **1069 active requests**, compared
with roughly 100-170 in the serial snapshots, with KV usage 15-43%. This is a
startup observation, not a steady-state throughput claim or a guarantee of
512 active requests on every GPU. Admission guards and server limits remain.

The first measured post-startup 30-second interval produced approximately
4486 completed server requests/minute, 27497 generated tokens/second,
168857 input tokens/second and 1244 accepted conversations/minute, with zero
preemptions and 836 active server requests at the ending snapshot. Serial
accepted throughput was about 296/minute in the preceding measured interval.
Thus the observed improvement was roughly fourfold, not proof of sustained
512-way occupancy per GPU or a full-campaign ETA. All original seven and new
twelve languages retain the same targets and independent audit requirement.
100 focused tests passed, including real spawned-worker/fake-HTTP integration,
worker-held lock lifetime, atomic duplicate claims and bounded RPC handling.

The later 60-second observation measured 4160 completed requests/minute,
25654 generated tokens/second and 1125 accepted conversations/minute. Ending
server concurrency was 726 total (68-126/server), KV occupancy 15.3-26.9%,
zero queued requests and zero preemptions. All eight worker processes remained
alive. The configured 512/server ceiling is therefore not achieved occupancy;
the parallel change improves throughput substantially but does not eliminate
all client-side/admission overhead.

## Doubled Client Ceiling, 2026-09-28 (Superseded Launch)

At the user's request, the 512/server parallel launch was drained cleanly:
240974 accepted rows, zero active, no worker or recovery errors. The replacement
uses **1024 client slots per endpoint**, 8192 across eight endpoints, shared by
generation and audit. This supersedes the 512 ceiling above, not the measured
throughput observations. Actual server occupancy remains workload-dependent.

Detached parent PID: **164935**. Runtime root:
`data/dfm12/joint-synthetic-parallel-1024-20260928`.
Log: `logs/dfm12/joint-synthetic-parallel-1024-20260928.log`.
Use the parallel command above with this root and
`--concurrency-per-server 1024`. Timeout 600, admission spacing 0.002,
zero-waiting admission and KV ceiling 0.90 remain unchanged. No shared vLLM
server was restarted or reconfigured. Both existing ledgers and accepted rows
are preserved. 101 focused tests passed, including the new 8192-slot ceiling.

## Two Clients Per Server, 2026-09-28

The user authorized two CPU client processes per GPU server, retaining the
1024/server ceiling: **16 clients, 512 slots each**. Parent PID 164935 and all
eight old clients drained and exited at 264301 accepted, zero active. Shared
vLLM servers were not restarted or reconfigured.

The replacement parent is **579539**. Launch command:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.joint_synthetic_parallel run \
  --root data/dfm12/joint-synthetic-two-clients-20260928 \
  --workers-per-server 2 --concurrency-per-server 1024 --timeout 600 \
  --admission-spacing 0.002 --max-kv-cache-utilization 0.90
```

Launched detached with hrm on PATH and CPU thread limits of one. Log:
`logs/dfm12/joint-synthetic-two-clients-20260928.log`. Live status is the
runtime root's `progress.json`; `runtime.json` maps 16 unique worker IDs to PIDs
and endpoints. Original campaign ledgers remain authoritative.

For two clients, the parent owns one shared admission gate per endpoint,
including spacing, queue/KV checks and circuit recovery. Dedicated admission
RPCs use heartbeats so a cooldown cannot block finish/status recording. Only
the parent reserves rows, claims fingerprints and writes ledgers. Children
retain controller locks until their work drains. 114 focused tests passed.

Measure throughput without issuing generation requests:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/measure_joint_synthetic_throughput.py \
  --jointroot data/dfm12/joint-synthetic-two-clients-20260928 --window 300 --poll 30
```

The measurement writes JSON under `logs/dfm12/`. Accepted rows belong to this
campaign; server counters include all clients sharing those servers.

The completed five-minute measurement accepted 6282 rows (1256/minute), with
zero preemptions; artifact:
`logs/dfm12/joint-two-clients-five-minutes-20260928.json`. Doubling CPU clients
did not establish a clear throughput gain over the preceding single-client
windows. Do not infer causality from unequal, workload-dependent windows.

Read-only investigation found an admission bottleneck candidate: the retained
gate serializes a full metrics fetch/parse before each conversation and sleeps
two seconds whenever even one request is waiting. A 32.5-second observation
(60 snapshots per endpoint) saw nonzero queues in 1-7 snapshots per server,
usually only one request, at mean running counts of 63.5-164.6. This establishes
that the trigger occurs, not the fraction of wall time actually gated. Parent
CPU was about36% of one core and workers17-20%; neither was CPU-saturated in
the observed process snapshot. Some filesystem waits were visible. The next
controlled experiment should address admission (short cached metrics and
bounded transient queue tolerance), retaining KV/circuit protections, rather
than adding more clients. No admission behavior was changed by this diagnosis.

## Transient Queue Tolerance, 2026-09-28

User authorized replacing the zero-waiting rule. The joint clients now allow
up to **8 queued requests per server**, and retry admission after **0.1 seconds**
for larger queues or excessive KV usage, replacing the two-second busy backoff.
The KV ceiling remains 0.90 and failure cooldown/recovery remains intact.
`dfm12/joint_admission.py` contains the joint-specific gate; sealed standalone
campaign implementations and manifests were not modified. The joint runtime
pins this module. No metrics caching or further concurrency change was added.

Previous parent 579539 drained and exited at **274404 accepted, zero active**.
Replacement parent **756318**, root
`data/dfm12/joint-synthetic-queue8-20260928`, log
`logs/dfm12/joint-synthetic-queue8-20260928.log`, otherwise the same two-client
launch arguments above. All **118 focused tests passed**, including small
queue admission and continued blocking for excessive queue/KV levels.
Shared vLLM servers were left running throughout.

## Queue 128, 2026-09-28 (Superseded Launch)

The user superseded the proposed queue32/50ms setting before launch with
**128 queued requests per server and 10ms busy backoff**. The queue8 clients
drained fully at **319816 accepted**, with zero active. The two clients/server,
512 slots/client, 0.002s admission spacing, 0.90 KV ceiling and failure
cooldown remain unchanged. No vLLM server lifecycle or memory setting changed.

Current root: `data/dfm12/joint-synthetic-queue128-20260928`.
Log: `logs/dfm12/joint-synthetic-queue128-20260928.log`.
Use the same two-client command above with this new root. The PID and worker
mapping are in `runtime.json`. All **120 focused tests passed**, including
admission at queue128 and continued blocking at queue129 or excessive KV use.

## Read-Only Admission Investigation, 2026-09-28

With queue128/10ms in production, a 60-second read-only probe captured 61
snapshots per server and parent/client CPU and wait channels. Artifact:
`logs/dfm12/joint-admission-diagnosis-20260928.json`.
None of the 488 server observations crossed admission limits: waiting peaked
at 2, KV at 54.3%, and no preemptions occurred. Short events between snapshots
are not excluded. Reducing the 10ms busy backoff further is therefore not the
leading optimization supported by this measurement.

The parent used 48.4% of one CPU core; its main thread was in
`folio_wait_bit_common` in 19/61 snapshots and `commit_blocking_request` in
15/61, with the other 27 snapshots runnable. Worker CPU was 22-24% each, with
socket/event waits and some filesystem waits. These are sampled observations,
not exact wall-time attribution. Kernel block-I/O delay counters reported zero
and do not rule out filesystem waits.

The active files reside on WEKA. Code inspection confirms sole-parent
synchronous SQLite WAL transactions with `synchronous=FULL`, per-row JSON
fsync/rename, and synchronous fingerprint/finish RPCs. This makes the parent's
I/O path a stronger current bottleneck candidate than insufficient client
count. Do not disable durability or introduce independent SQLite writers.

Separate sequential probes (10 per endpoint) measured HTTP metrics reads at
2.5-5.2ms and the actual admission parser at 4.8-6.5ms; artifact:
`logs/dfm12/joint-admission-serial-probes-20260928.json`. The concurrent probe's
HTTP timings include event-loop delay from parsing other replies, so use the
sequential probe for this estimate. Cache metrics briefly (e.g. 250ms, with
stale/error samples failing closed) as a small first experiment. Next consider
bounded batching of sole-writer commits with acknowledgements only after
durability, or moving blocking I/O off the admission event loop while retaining
one owner. No production code or settings changed during this investigation.

### Follow-Up: Parent I/O And Synchronous Claims

The follow-up qualifies the batching recommendation above: an isolated small
database benchmark did **not** show intrinsically slow SQLite commits. On the
same WEKA mount, 100 FULL-WAL commits averaged 0.23ms, 100 atomic 10KB JSON
writes 1.11ms, and hot indexed seed reads with a fresh connection 0.28-0.37ms.
Artifact: `logs/dfm12/parent-io-probe-_yy3w28g/results.json`. These small/hot
tests do not represent tails or automatic checkpoints in the live 0.7-2.7GB
ledgers and 0.45-1.5GB source-selection databases.

A separate 2000-snapshot, 10.46-second live parent sample found 627 filesystem
commit waits, 395 page waits, and 978 runnable observations. Transient open
descriptors included seed SQLite/shm, specifications, outcomes and accepted
records. Descriptor presence cannot identify the exact blocking syscall.
Artifact: `logs/dfm12/joint-parent-fd-sampling-20260928.json`. Direct syscall
and stack inspection was denied, including sudo; no permissions changed.

Code review identifies amplification: worker `RemoteSeen` performs synchronous
`SyncRPC.call` for fingerprint claim and confirmation. Each wait blocks that
worker's entire event loop, including unrelated HTTP streams. An accepted
candidate normally entails four parent SQLite commits (source allocation,
reservation, fingerprint claim, finish), two atomic JSON writes, and multiple
reads. Separate sockets avoid deadlock but not these stalls. This is stronger
evidence for combined parent service latency plus synchronous-client blocking
than for any particular slow SQLite commit mechanism.

Next optimization order: short cached metrics as the smallest independent
change; then isolate blocking sole-owner ledger/file work from admission, or
remove synchronous claim waits from client event loops. Preserve exactly-once
claims, durable-before-ack semantics and drain/recovery ordering. If further
attribution is needed, collect per-operation reserve/claim/confirm/finish
timings on a future planned restart. Do not jump directly to a durability or
multi-writer redesign. This follow-up changed no production behavior.

## KV Admission At 100%, 2026-09-28 (Current)

The async-claims launch below was drained at 364597 accepted and zero active.
After 150 focused tests passed, clients restarted under PID 2423945 with root
`data/dfm12/joint-synthetic-kv100-20260928` and log
`logs/dfm12/joint-synthetic-kv100-20260928.log`.
Explicit `--max-kv-cache-utilization 1.0` supersedes the earlier 90% admission
threshold for this run. Defaults remain 90%. Two clients per server, combined
1024 slots per server, queue tolerance 128, 10ms backoff and 2ms spacing remain.
This changes client admission only: shared vLLM servers retain 0.80 GPU-memory
allocation and were not restarted. All eight GPUs were active after restart.

## Cached Metrics And Async Claims, 2026-09-28 (Superseded Launch)

After user authorization, the queue128 clients drained at **353288 accepted,
zero active**. The replacement keeps two clients/server, 1024 combined slots,
queue128, 10ms busy backoff, 2ms admission spacing and the 90% KV threshold.

- Validated admission metrics are cached per endpoint for 250ms, timed from
  fetch start. Expiry or forced recovery requires a successful fresh probe;
  failed probes discard the old sample. Circuit trips invalidate the cache.
- Fingerprint claims now use a dedicated asynchronous RPC. The parent still
  performs the same atomic durable insertion. The redundant confirmation RPC
  is removed; accepted materialization still verifies fingerprint ownership.
- The retained processing flow is copied into `joint_async_process.py` with
  only asynchronous claim substitution, using each campaign's original/private
  pilot adapter. Prompts, quality checks and review policies are unchanged.
  Claim transport/protocol failures stop the worker rather than permit acceptance.
- SQLite durability, the sole writer, worker-held locks and drain/recovery
  ordering are unchanged. Shared vLLM servers were not restarted.

Current root: `data/dfm12/joint-synthetic-async-claims-20260928`.
Log: `logs/dfm12/joint-synthetic-async-claims-20260928.log`.
PID/worker mapping: runtime root's `runtime.json`. Use the existing two-client
command with this root. New modules are included in runtime pins; do not edit
them during production. **143 focused tests passed**, including processing
parity for both adapters, cancellation, duplicate handling, cache expiry,
failed recovery probes and spawned-process integration.

Initial 60-second production observation: **8078 completed requests/minute,
52958 generated tokens/second, 1595 accepted conversations/minute**, zero
preemptions and no measurement errors. Artifact:
`logs/dfm12/joint-async-claims-startup-20260928.json`. This is an early window,
not a steady-state benchmark; generated throughput was about29% above the
earlier read-only probe's 41089 tokens/second with the old client path.

## Completed-Language Export Restart, 2026-09-29

Local-only export root: `exports_dfm12/multilingual-completed-20260929-v1`.
The fixed cohort is de/el/es/fi/fr/it/nb/nl/nn/pl/ro/sv/uk: 70,000 each for
NB/NN and 35,000 each otherwise, totaling 525,000 accepted conversations.
No upload, GPU work, source-controller lock, or production changes are involved.

The initial exporter PID 3171222 and its eight verified CPU children were
terminated before completion to incorporate review findings. Partial packages
are retained under `interrupted/`; the read-only ledger snapshot is unchanged.
Replacement PID 3294689 uses `--resume-snapshot --workers 8`; its launch receipt
is `data/dfm12/multilingual-completed-export-20260929-v1-resume-process.json`
and log is `data/dfm12/multilingual-completed-export-20260929-v1-resume.log`.
This launch subsequently completed successfully; the final evidence is below.

Before workers start, the parent verifies the snapshot database hash once and
requires `private/sources.json` to equal the sources in `snapshot.json`.
Every production/pilot row must reconstruct exactly with retained
`generation_assemble`, in addition to ledger, fingerprint, raw independent
review, and applicable accepted-materialization checks. Imported first-pilot
re-audits use their committed journal and pinned external evidence instead of
inventing production stage paths. Native messages and tools remain unchanged.
All 24 actual source/origin/family smoke checks passed after the restart;
14 focused exporter/verifier CPU tests passed. `snapshot-verification.json` and
`smoke-receipt.json` record these pre-export checks.

### Verified Completion

The root `completion.json` confirms all 13 packages and **525,000 rows**.
The independent `dfm12.verify_multilingual_completed` pass reopened every
compressed training/audit shard, verified all pinned package file hashes,
recounted families and origins, checked per-language ID/fingerprint uniqueness,
and bound every training row to its audit receipt and native messages/tools
fingerprint. Its successful receipt is `verification.json` in the export root.
The exporter and verifier have finished; no export workers remain required.

| Language | Rows | Package Bytes |
|---|---:|---:|
| de | 35,000 | 91,348,415 |
| el | 35,000 | 108,689,818 |
| es | 35,000 | 89,055,604 |
| fi | 35,000 | 82,977,210 |
| fr | 35,000 | 87,580,831 |
| it | 35,000 | 88,709,522 |
| nb | 70,000 | 174,069,123 |
| nl | 35,000 | 90,551,833 |
| nn | 70,000 | 170,703,825 |
| pl | 35,000 | 98,697,760 |
| ro | 35,000 | 89,257,782 |
| sv | 35,000 | 98,385,421 |
| uk | 35,000 | 107,358,765 |

Package total: **1,377,385,909 bytes**, including **469,062,362 bytes** of
compressed training shards and **908,282,298 bytes** of compressed audit
shards, plus manifests/cards. Private snapshot/evidence bookkeeping occupies
2,583,582,805 bytes separately; retained interrupted outputs occupy
264,240,009 bytes and are not part of the completed packages. Only each
package's `data/` directory is training input. This local export does not
upload, admit additional rows, or change active production or GPU processes.
