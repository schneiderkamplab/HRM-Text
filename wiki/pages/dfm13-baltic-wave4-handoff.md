---
type: Runbook
title: Baltic To Wave4 Synthetic Handoff
description: Guarded sequential26B generation and compact audit for Baltic140K then W4770K.
tags: [dfm13, synthetic, audit, scheduling]
status: draft
last_updated: 2026-10-04
confidence: high
---
# Baltic To Wave4 Synthetic Handoff

## Blocked-Group Diagnosis And Training Intent, 2026-10-04

**Latest owner decision:** after CPU recovery projected sufficient rows for the
other ten languages, proceed to finalization and DFM12 resume without unnecessary
GPU top-up. Keep as much valid, unique Luxembourgish as recoverable, superseding
the 35K cap discussion; do not discard existing accepted rows. The ten other
languages retain 70K targets. Final Luxembourgish totals must be measured after
validation/deduplication rather than inferred from the older family-capped
projection. CPU export/integration may continue while training resumes.

**CPU parallelism decision:** the owner requests 256 recovery workers instead
of two. Partition candidate inventories and output writers independently;
raising a process-pool cap alone is insufficient because the original runner
has only eight shard tasks. Preserve committed checks, avoid shared SQLite
writers, and cap per-process native threads. This changes CPU recovery only,
not GPU client concurrency or source-quality admission rules.

**Owner guidance on shortfalls:** Luxembourgish may finish at 35,000 accepted
conversations instead of 70,000. The owner is open to doubling attempt limits;
this is not evidence that a live budget change has been applied. Recover saved
technical review failures first, then assess the remaining deficits and fix the
actual clean-keep validation path before any additional GPU attempts. Reducing
the target must not discard already accepted rows or silently rewrite sealed
campaign manifests. A source-shortage block is not solved by a higher attempt
limit alone.

**Follow-up owner authorization:** perform narrow CPU recovery of saved
clean-keep/empty-reason review-validation failures, retaining all other checks,
original evidence and quota/dedup safeguards. Finalize, export, integrate and
prepare all finished accepted datasets for upload; CPU work may continue after
the GPU generation pass. Keep the existing DFM12 plan, not DFM13 training.
Do not add new GPU generation/repair solely to meet nominal quotas on this
authority. Recompute shortfalls after recovery rather than assuming every
review-invalid candidate is acceptable.

Read-only inspection found a technical review-validation failure in exhausted
groups: all 24 review-invalid cases within a 50-outcome sample of Persian and
Luxembourgish math/code plus Belarusian OpenHermes had complete `keep` responses,
empty issues and empty reasons rejected by the nonempty-reason schema. This is
not proof that all invalid rows are good. Prefer a narrow, provenance-preserving
CPU recovery with unchanged candidate/source checks and quotas before spending
more GPU time. Source shortages need additional distinct sources or bounded
new variants; genuine generation/review quality problems need targeted fixes,
not indiscriminate attempt-budget increases. Detailed evidence:
`docs/reports/dfm13_wave4_blocked_groups_diagnosis_20261004.md`.

The user's intended training continuation is XL DFM12 from
`ephemeral_step_3081500` through the existing
`logs/scheduler/dfm12_XL_epoch11_noidentity` plan, after required GPU data work
finishes. DFM13 training was discussed hypothetically only and must not be
scheduled on this authority. A mid-epoch dataset switch would need a new sample
and explicit cursor/epoch/LR-boundary migration, not simply changing data paths.

User authorization2026-10-04 queues fourth-wave synthetic generation AFTER
successful [Baltic generation and auditing](dfm13-baltic-compact-production.md).
W4 target is770000accepted,70000each for sq,be,bs,bg,hr,hu,lb,sr,sk,sl,fa,
retaining all66family groups. Shared26B endpoints8800-8807,128combined
generation/review workers per server, no new servers or training changes.

## Durable Queue

Module: `dfm12.wave4_compact_handoff`, reusing the private existing quota
controller, compact reviewer, generation constraints, provider, recovery and
backpressure. No running Baltic dependency was edited.22focused tests pass.

Authoritative queued root:
`data/dfm13/wave4/synthetic-compact-after-baltic-20261004-v2`.
Detached watcher PID2915055, start_ticks249893691. `watcher-launch.json` stores
exact identity/command; `watcher.log` and `handoff-status.json` show progress.
The earlier v1 is a preserved never-launched preparation superseded by v2's
missing-client detection and incremental verification progress. Do not run v1.

## Completion Gate

- Baltic must report phase complete, every group exactly at its target, zero
  active/running jobs, verified manifest/ledger pins, and released controller lock.
- The watcher acquires that lock and rechecks EVERY credited candidate using
  existing strict generation assembly/raw review validation, exact materialized
  messages/tools/provenance and unique fingerprint ownership. Group totals must
  match140000. PID exit alone never permits launch.
- Accepted evidence goes into accepted-audit-proof.jsonl with a digest bound by
  baltic-completion-verified.json. W4 run itself requires that completion proof.
- Any exhausted6xattempt budget below quota emits handoff-blocked.json and stops
  the watcher. Drained/failed/blocked Baltic phases likewise do not launch.
  Three30-second observations without the expected Baltic client also stop with
  a diagnostic. There is no silent infinite wait on cap exhaustion/client death.
- Launch intent is written before detached Popen. Existing launch intent blocks
  automatic duplicate/retry launch; exact W4 child identity is saved in launch.json.
  Changed pins or invalid required accepted-stage evidence fail closed. Explicit
  investigation/rearm is required after a blocker; no quality relaxation.

## Audit And Repair Semantics

Every structurally valid, nonduplicate candidate proceeds to compact review
before it can receive accepted quota credit. Invalid generations and duplicates
are nonaccepted terminal attempts. Passing requires semantic keep plus existing
deterministic checks; repair/reject/needs_verification never count as accepted.

The running Baltic path does NOT automatically execute repairs. A repair verdict
remains an unaccepted hold; the controller may generate replacement candidates
within its attempt cap. W4 uses the same behavior, not an implicit repair loop.
Any future credited repaired candidate needs exact final-hash fresh audit evidence
and a separately reviewed import/disposition path. The handoff does not approve
pending repair rows, failed reviews, source-fidelity holds or prior staging keeps.

Prior W4 staged ledgers were inspected: all contained zero jobs. They remain
unchanged with manifest hashes recorded in the successor. A populated historical
ledger would block preparation pending explicit migration, not be silently reset.
Calibration/review/source artifacts remain untouched and uncredited. Baltic's
historical LV rows remain held in its successor pending explicit clearance.

Current low observed keep rates may exhaust a family budget before its accepted
target. A queued770K target is not a promise of completion; main owns failure
diagnosis. The watcher records that situation and leaves W4 unstarted.

## Technical Recovery Rearm, 2026-10-04

Superseded watcher PID2915055 was stopped after matching start_ticks249893691
and its exact watch command. No Baltic/server/training process was signaled by
the handoff owner. Boole subsequently applied the isolated empty-rationale
recovery, migrated the Baltic manifest and restarted Baltic as PID2936091.

Completion proof now selects `dfm12.compact_keep_recovery.controller()` only
for the explicit migrated technical-adapter manifest. This verifies original,
private-schema and receipt-backed recovered keeps against their raw evidence;
unknown adapters fail closed. Legacy manifests retain the original factory.
The watcher also recognizes the migrated client module.16 handoff/recovery
tests passed. The experimental semantic adapter remains undeployed; no
include_reasoning change was made.

`python -m scripts.rearm_baltic_recovery_handoff` verified migration and the
live replacement client, all unrelated pins, zero W4 jobs and ledger seals.
It archived previous manifest/seal/handoff state under `pre-recovery-rearm`,
updated implementation and prerequisite pins, verified the new seal, and
launched watcher PID2936761, start_ticks250061468. At launch it reported
waiting with22462 Baltic accepted and33 active; W4 was not launched.

Receipts in `data/dfm13/wave4/synthetic-compact-after-baltic-20261004-v2`:
`watcher-stop-recovery-upgrade.json`, `recovery-rearm-verification.json`,
`watcher-recovery-launch.json`; log `watcher-recovery.log`.
New W4 manifest SHA256:
`f9e3b5dd3966ac81cf925839735809655cdd545a5d287e628c35e130fc48017c`.
Baltic prerequisite manifest SHA256:
`92749105fadfb9189bde88f4ed3e893e9a14af85c3ebc67ff96c17dead642fe9`.
Rearm is a one-shot explicit upgrade, not a generic retry command: an existing
archive blocks repetition for manual inspection. All quota, budget-exhaustion,
quiescence and per-accepted-candidate audit checks remain required.

## Baltic384 Rearm, 2026-10-04

Superseded watcher2936761 was stopped by matching its saved command, create-time
and start_ticks250061468. Boole owns the user-authorized Baltic-only384 migration
and restart; handoff ownership did not signal Baltic or any shared server.
For the explicit `runtime_module=dfm12.baltic_concurrency384` and concurrency384
manifest, completion proofs now use that module's recovery-aware `controller()`.
Unknown runtime policies fail closed. W4's own controller remains128/server,
verified by regression test; no semantic reviewer or transport change is included.

After migration and restart, the rearm helper ran with
`--baltic384-migration data/dfm13/baltic/concurrency384-migration-20261004-v1/receipt.json`.
It checked the migration hash, live Baltic3051744, unrelated pins and empty W4
ledger, archived previous state under `pre-384-rearm`, and verified new seals.
Watcher3052704 (start_ticks251498664) is waiting. Its initial snapshot reported
98751accepted/240active; W4 remains unlaunched.18 handoff/recovery tests passed.

Receipts: `watcher-stop-384-upgrade.json`, `384-rearm-verification.json`,
`watcher-384-launch.json`; log `watcher-384.log`, under the existing W4v2 root.
W4 manifest SHA256:
`59ae76e637b5d25ec415e94938e518f8e61f3596539a04343b01ffe2df9484d4`.
Baltic prerequisite SHA256:
`6a22dc6981f35114b8688e1414304290a67f7b30dbc92732b7a8fc724612a4a8`.

## Superseding W4 Configuration:768, 2026-10-04

Explicit user authorization supersedes all earlier W4-only128 settings:770000
accepted target remains, now768 concurrent workers/server (6144 combined
generation/review maximum), zero fixed admission spacing, asynchronous CPU/I/O.
`dfm12.wave4_async_runtime` privately reuses Boole's pinned `baltic_async_io`
single-owner offloading, raw-writer offloading,2s client keepalive and nonextending
circuit deadlines. W4 overrides only concurrency and spacing; retains90%KV gate,
inherited waiting<=128 guard,5s cooldown and metrics/health checks. Zero spacing
does not mean disabling shared-server backpressure or guaranteeing full occupancy.
Shared/Baltic modules and live processes were not modified by this upgrade.

Both preparation and verification require768/zero-spacing manifest fields;
the run CLI creates the dedicated I/O owner and installs the actual offloaded
runner, not merely a widened synchronous controller.20 tests pass, including
768/6144/zero runtime metadata, shared-module isolation and exact Baltic proof
factory selection. Completion proof whitelists
`dfm12.baltic_zero_spacing.controller()` only with all required manifest markers.
No experimental semantic reviewer is installed.

After Boole's final module freeze and Baltic migration/restart, the explicit
`python -m scripts.rearm_baltic_recovery_handoff --wave4-768` upgrade verified
all unrelated old pins, empty W4 ledger, current Baltic seal and live client.
Old W4 state is archived under `pre-768-async-rearm`. Watcher3075226,
start_ticks251716357, is live and waiting on Baltic3074327. Initial snapshot:
109233accepted/541active. W4 has zero jobs and is NOT launched early; all quota,
quiescence and raw accepted-audit proof requirements remain unchanged.

In the existing W4v2 root: `768-async-rearm-verification.json`,
`watcher-768-async-launch.json`, `watcher-768-async.log`.
New W4 manifest SHA256:
`fc7e87efc1aa2f04b09e5a472baf623ced59f29703c870cd8b5f867b311e22a8`.
Baltic prerequisite SHA256:
`777d016c1028b76130267a319c9aec870009afa286a68cd6d2a4fe30f712769e`.

## Baltic768 Prerequisite Upgrade

Later2026-10-04 authorization also raised Baltic to768/server. Watcher3075226
was stopped after exact saved identity verification. Boole alone migrated and
restarted Baltic as3098356. The handoff whitelists
`dfm12.baltic_concurrency768.controller()` with the effective768 marker and all
retained zero-spacing/I/O/recovery markers; unknown combinations fail closed.
W4's own768/zero-spacing/offloaded execution policy is unchanged.

After verifying the migration receipt, live client, all unrelated pins and empty
W4 ledger, `--baltic768-migration` archived old state under `pre-baltic768-rearm`
and launched watcher3099484 (start_ticks252017446). It is waiting, initially
126649accepted/188active; no early W4 launch.21 focused tests passed.
Receipts: `watcher-stop-baltic768.json`, `baltic768-rearm-verification.json`,
`watcher-baltic768-launch.json`; log `watcher-baltic768.log` in the W4v2 root.
Current W4 manifest:
`0f466e0e9cd7d79c566fbf98ac156caead2905552e50ee9218f119cc24b0dc39`.
Current Baltic prerequisite:
`96d0f0821c843e2a9ab8dc1fa43477f0073055b467f7d71c26fa2d0f1d603b33`.

## Explicit Independent Launch, 2026-10-04

**Supersedes raw-proof-before-GPU-launch policy above.** After Baltic completed
140000accepted and zero active/running jobs, user explicitly authorized starting
the independent770K W4 campaign immediately while the full Baltic raw-evidence
reread continues as a publication gate. The serial proof was around17000/140000,
with more than five minutes remaining. Exact watcher3099484 was stopped; its
partial proof is preserved as `accepted-audit-proof.serial-partial-untrusted.jsonl`
and is not trusted as a completed proof or reused without validation.

`run-independent` requires the exact explicit authorization receipt and current
manifest hashes, full Baltic controller verification, complete/quiescent status,
accepted counts matching every group target (140000total), effective_keep for
each accepted row, no repair-requested acceptance and exact fingerprint ownership.
This is not a hidden fallback in the normal run path; that path still requires
the full proof. W4 quality gates are unchanged and Baltic remains unpublished
pending the separate raw-proof/release process.

W4 launched as PID3120078,768/server,6144request maximum, zero fixed spacing and
offloaded I/O; log `runner-independent.log`. First live check:51accepted,
150active,422attempts, all eight GPUs100%utilization. No server was modified.
The durable launch intent prevents the old watcher from duplicating this run.

Separate CPU-only `verify-publication` PID3120820 rechecks all140000 rows from
the beginning under Baltic's controller lock, preserving every original check;
log `publication-proof.log`, receipt `publication-proof-launch.json`. It cannot
launch W4. Its progress still uses `handoff-status.json`; use W4 `runtime.json`,
`progress.json` and `launch.json` to distinguish live generation from proof work.
No32-worker rewrite was made after the user's immediate-launch supersession.

Authorization: `independent-launch-authorization.json`; archive:
`pre-independent-launch`. W4 manifest:
`5200e3c5ef875692f6370aeb59b1222c96c1f38a13c1fb25a27781918224b246`.
13 focused handoff tests passed before launch. The raw-evidence publication gate
is not waived, and completion of W4 does not independently clear Baltic holds.

### W4 Feeding Profile

Read-only sampling of PID3120078 found its single owner thread in commit waits
45/100 samples and page waits5/100 over5seconds. Raw requests/responses and
stage/spec files use fsync-backed atomic writes; these share the owner with
SQLite/provider/tokenizer/validation work. Actual seed lookup uses pool/seq and
exclusion indexes, not an observed full-table scan. Offloading freed the event
loop but retained a serial CPU/I/O queue. Evidence and limitations:
`docs/reports/dfm13_wave4_owner_profile_20261004.{json,md}`.
Boole owns the bounded parallel-I/O/CPU successor; ledger/provider/fingerprint
mutations must retain their single owner and durability ordering. No runtime
change or process stop was made during this profile. Baltic raw proof continues.

### Parallel-I/O16 Deployment

After coordinated tests, W4 PID3120078 was gracefully drained at2396accepted,
zero active. Boole's first parallel module launch3127608 failed before new work:
`SourceProvider(..., load(config))` matched the parallel `load` rule and created
SQLite on a different thread from later provider calls. The failed log/manifest
remain archived. Boole fixed constructor/DB owner precedence and added a regression
test; this deployment owner did not edit Boole's module.

Corrected hash `b0c44f4133bd6730fc710defede2f9edce324ed1826e6920160c888acf3b186f`
passed four module tests. `scripts.deploy_wave4_parallel_io` checked all unrelated
pins, archived both migrations, preserved every job/cursor/outcome and rechecked
`verify_independent_launch` before detached restart. No failed rows were replayed.
Live PID3128749 runs16 bounded CPU/I/O workers plus one ledger owner,768/server,
zero fixed spacing and explicit `--launch-mode independent`. Runtime metadata
records the actual workers/module; `operation-timings.json` records route-level
queue/service time. Log `runner-parallel-io16.log` is append-only and contains the
first failed PID's traceback, not a crash of the replacement.

Startup had a temporary preparation delay; then real work was verified:
1190generation preparations,2027raw-request starts,953assemblies and accepted
growth2396->2641, with86active at that snapshot. Thread-local tokenizer startup
contributes to initial cumulative timing; do not interpret it as steady-state
throughput. Parent owns the separate60s measurement. Baltic proof3120820 and
all shared servers were untouched. Manifest SHA256:
`d5d348cd0655d9584d4bfedd4aef86a679f0391d1c391ad6490b43f3c719eb44`.

### Reservation-I/O Successor

The next coordinated upgrade drained3128749 at4800accepted/zero active, preserving
all rows. Final Boole adapter `wave4_reservation_io` moves the specification-file
fsync out of the ledger owner but awaits durability before any request, and uses
an owner-published remaining-work hint with authoritative reservation checks.
It also privately installs the parity-tested fast LoopGuard, without changing
the shared streaming module. Parallel owner routing was explicitly repinned to
its strengthened constructor/global precedence version; an initial preflight
correctly refused this dependency drift before any migration or launch.

Live replacement3136702 runs `dfm12.wave4_reservation_io --launch-mode independent`.
Runtime verified768/server, zero spacing,16parallel workers,
`specification_write=parallel_durable_before_request` and
`gate_remaining=owner_published_hint_reserve_authoritative`. Startup log is clean;
parent owns the subsequent warm60s measurement. Background Baltic proof and
servers remain untouched. Receipts/log: `reservation-io-drain.json`,
`reservation-io-migration.json`, `reservation-io-launch.json`,
`runner-reservation-io16.log`; old state under `pre-reservation-io16`.
Local combined tests35passed; Boole reported54tests on final frozen adapter.

Pinned successor:
`e0c276d45caf9b4c701c8ea304661008717e2e1601b1ba8d8fbc40d0cc668c0c`.
Pinned guard:
`48843de0e8b81e4cb8d148b87d5cb5566784c4f7ecf4b3720c688ee97bb96300`.
Pinned parallel dependency:
`edb2ac48e5588d01fa7e442a9124c8549827a541107bc3298fb46cf418782426`.

### Disk/CPU Queue Follow-up

Read-only live snapshot `docs/reports/dfm13_wave4_live_queue_20261004.json`:
15989accepted,3972ledger-active conversations,83server-running requests summed
across8endpoints, zero server waiting and less than3%KV per endpoint. Ledger
active means entire conversations; server metrics can include other clients and
were sampled sequentially, so subtraction is not an exact client queue count.
The existing runtime has no exact pending-operation counters; cumulative
queue_seconds measures completed-operation waiting, not current queue depth.

At this snapshot,552713JSON writes accumulated5817service-seconds; raw begin/
finish another2633seconds. This is aggregate concurrent service time, not wall
time or a steady-state capacity estimate. Disk and CPU share the current16pool.
Boole owns a proposed separate disk128/CPU16/ledger1 successor with compact JSON,
preserved fsync and exact operation queue counters. No tokenizer128pool is
requested. Current client remains until tested/frozen successor deployment;
servers are unchanged.

### Disk128/CPU16 Deployment

Boole froze `wave4_disk_pipeline.py` at
`3f4d0a3851bc5f1111e9248d2972a324aa66a0234645232b5aa1f9f5938d7537`;
59 tests reported by Boole,26 combined tests run locally. Graceful SIGTERM was
sent only to identity-verified3136702. Existing reservations completed without
reset/replay; terminal drain18426accepted, zero active,99704attempts.

The deployment helper verified every previous implementation/input pin unchanged,
archived the old state under `pre-disk128-cpu16`, added only the new runtime pin,
updated seals/authorization hash and rechecked the independent launch gate.
New live PID3158062 runs `dfm12.wave4_disk_pipeline --launch-mode independent`.
Startup log is clean. Runtime confirms owner1/CPU16/disk128,768/server, zero fixed
spacing and compact_single_write JSON. Fsync durability is retained; no prior
evidence file is reformatted. `operation-timings.json` now distinguishes exact
pool waiting/semaphore-waiting/submitted/running counters and client HTTP contexts.
HTTP contexts include connection acquisition/response I/O, not solely server
engine-running requests; do not confuse them with vLLM running metrics.

Receipts: `disk-pipeline-drain.json`, `disk-pipeline-migration.json`,
`disk-pipeline-launch.json`; log `runner-disk-pipeline16.log` under W4v2.
Servers and Baltic background proof were not signaled or changed. Startup
configuration verification is not a steady-state throughput claim; parent owns
the subsequent warm measurement.

Post-start survival check confirmed actual inference and accepted progress for
disk-pipeline3158062, not merely process existence: all eight endpoints served
generation and review; captured generation responses4977 and decodes4213 during
startup. Subsequent snapshot accepted18426->18631,1386terminal ledger commits,
3292review results and5016active. Log remained empty. Exact counters still showed
5362owner-waiting operations: startup reservation/fingerprint/finish backlog is a
remaining serialization bottleneck, not a model-server crash. No further stop or
runtime change occurred during this monitoring.

### Disk128 Warm Measurement

Parent's 60-second measurement on 2026-10-04 is recorded at
`/tmp/dfm13-wave4-disk128-warm-current.json`: approximately3632 completed
requests/minute,16512 generated tokens/second and83689 input tokens/second.
These are aggregate shared-server counters, not W4-only throughput or acceptance
rates. Final endpoint snapshot summed149running requests and zero waiting;
KV usage ranged1.82-3.97%, averaging3.08%. All eight GPUs showed100% utilization
in the instantaneous snapshot; preemption counter delta was zero.

This remains below the previously reported5348requests/minute. CPU/disk queues
had cleared, but the ledger owner still had6078pending operations, including
4575reserves,1295claims and207finishes (the listed categories are not exhaustive).
This identifies serialized ledger work as the remaining observed queue, not
evidence of exhausted KV capacity. Boole is investigating minimal ledger
batching; no further restart is authorized yet. PID3158062 was independently
verified running with accepted19782 versus18426 at launch and an empty runner
log. No server, client or background publication-proof changes were made for
this measurement or documentation update.

### Bounded Ledger Batch Deployment

User authorized the ledger fix and restart on 2026-10-04. Only identity-verified
PID3158062 received SIGTERM; its graceful drain ended at33510accepted, zero
active and177432attempts. No job reset/replay or shared-server signal occurred.
Boole froze the successor after integration tests; local focused regression
suite31passed, including real reserve/claim/finish operations, duplicate-credit
protection, fairness and cancellation waiting for durable commit.

Runtime `wave4_batched_runtime.py` SHA256:
`bb42804a3b8f749cabc6a8b2704c7280954420cd05a27a9ece4f3734302bbfba`.
Primitive `wave4_ledger_batch.py` SHA256:
`833569d7531337e91e2548bf6c4ac4f6735bd4d23b5c981550724c469e746430`.
The deployment helper verified existing pins and the independent launch gate,
archived previous metadata under `pre-ledger-batch16`, added these two pins and
the explicit runtime marker, resealed, then launched PID3179944 detached with
`python -u -m dfm12.wave4_batched_runtime --root <W4_ROOT> --launch-mode independent`.

Maximum batch16; queued completion work receives three slots per reservation
slot when both lanes are populated. Source selections commit before ledger
allocations; futures are released only after durable commits. CPU16/disk128,
768/server, zero fixed spacing and existing audit/admission checks are retained.
Receipts: `ledger-batch-drain.json`, `ledger-batch-migration.json`,
`ledger-batch-launch.json`; log `runner-ledger-batch16.log`. Early startup recorded
11committed batches/166operations and zero failed batches; this is not a warm
throughput claim. Shared servers and Baltic publication proof remain untouched.

Operational verification subsequently confirmed33616accepted (+106 from launch),
5160active and183580attempts, with generation/review HTTP across all8endpoints.
PID3179944 remained live; log empty;691batches/11046operations committed and zero
failed batches. Receipt `ledger-batch-operational-verification.json` preserves
the exact process identity, counts and HTTP/batch snapshot.
Parent's first post-start60s measurement reported approximately3089requests/min,
16.7K generated tokens/second,20requests at the endpoint snapshot and KV below1%.
This does NOT demonstrate improved performance: startup churn versus another
bottleneck remains under Boole's investigation. Current client is left running;
no further restart or server changes are part of this deployment verification.

### Fast Admission Parser Successor

The subsequent user-authorized fix targets a measured parser hot path, not the
quality gate. `docs/reports/dfm13_wave4_admission_profile_20261004.md` records
500offline replays of a57.9KB metrics document:4.894ms original versus0.259ms
filtered (18.90x parser speed, not campaign throughput). The private successor
retains the original parser for exact KV/waiting samples, with existing signal
validation, thresholds, health checks and cooldown unchanged. Quoted-name
OpenMetrics syntax falls back to the full parser.

Local focused tests42passed; parent reported46passed. Frozen
`wave4_admission_fast.py` SHA256:
`73f9f08ffdbfa8570e13ee6297b0e8f711c6b2e42dc2de6f141fb6322047069b`.
Only verified PID3179944 received SIGTERM. Already-queued reservation iterations
continued during graceful drain; final37560accepted, zero active,197626attempts,
zero failed batches. No rows reset/replayed. Deployment preserved all inherited
pins, added the parser pin/runtime marker, archived under `pre-fast-admission`,
resealed and reran independent launch verification.

New PID3188751 runs `dfm12.wave4_admission_fast --launch-mode independent`.
Receipts: `fast-admission-drain.json`, `fast-admission-migration.json`,
`fast-admission-launch.json`; log `runner-fast-admission16.log`. Parent owns the
warm measurement after startup; no campaign-speedup claim follows from the
offline parser benchmark. Shared servers, fsync, audit gates, batch16,
CPU16/disk128 and Baltic publication proof are unchanged.

Verified post-start acceptance37663 (+103), with generation and review HTTP on
all8endpoints, empty log and zero failed batches. Durable
`fast-admission-operational-verification.json` captures process identity, a later
ledger snapshot and the complete parent measurement originally at
`/tmp/dfm13-wave4-fastadmission-warm.json`. That60s warm measurement reports
3961requests/min,11765generated tokens/s and85774input tokens/s. Final snapshot:
142running, zero waiting, KV2.17-3.98% (mean3.00%), allGPU instantaneous100%,
zero preemptions added. These counters include all shared clients. The result
remains below the earlier5348requests/min and does not establish that end-to-end
performance is fixed. Client remains running; no further changes made.

Parent's comparison against the preceding steady2990requests/min window gives
an observed approximately32% higher request completion rate (3961versus2990/min).
This is a comparison of separate shared-server windows, not a controlled causal
benchmark: request mix, other clients and startup state can differ. Low final
KV2.17-3.98% and142running requests still indicate underfeeding relative to the
configured capacity; instantaneous100% GPU utilization does not establish full
feeding. No further restart is authorized at this point; PID3188751 remains live.

Second parent measurement, `/tmp/dfm13-wave4-fastadmission-steady.json`:
4519requests/min,13040generated tokens/s and97772input tokens/s. Final snapshot
89running, zero waiting, KV1.02-2.73%, allGPU instantaneous100%, zero preemption
delta. Accepted38810 versus37560at launch (+1250). These remain shared-server
measurements rather than W4-only or controlled comparisons. Continued low KV
and limited running requests retain the underfeeding caveat despite higher
observed throughput;100% instantaneous GPU utilization is not proof of full
feeding. No runtime modifications or restart accompanied this documentation.

### Next Ledger Diagnosis: Timing Semantics

User authorized a further proven ledger fix and client-only restart, but explicitly
requires PID3188751 to remain running until its successor is tested and frozen.
Code inspection confirms current `last_batch_service_seconds` spans executor
submission through coroutine resumption: it includes executor queue wait, actual
worker elapsed time and event-loop delivery delay. It is not isolated SQLite
service time. Batched operations directly use the owner executor and bypass the
ordinary per-operation owner counters, so an empty ordinary owner queue does not
mean no ledger work. A successor profile must timestamp submission, worker entry,
worker exit and coroutine resumption separately before attributing the remaining
bottleneck. No process signals or live-pin changes accompanied this diagnosis.

### Eight-Shard Fallback Preparation

User approved whole-language process sharding if the next fix is not convincing;
parent relayed isolated batch16 elapsed3-13ms versus live76-150ms, consistent with
dispatch/GIL effects rather than proof of slow SQLite alone. Prepared CPU-only
`dfm12.wave4_shard_prepare` and `scripts/supervise_wave4_shards.py`; no live
migration or stop at this preparation stage. Boole owns the shard runtime and
global-dedup integration, separate from these files.

Partition11whole languages into8workers by remaining quota; each owns all its
language/family groups, source selections, source scopes/cursors and original
job identities. Original evidence workdirs and source campaign identity remain
unchanged. Shared `fingerprints.sqlite` retains ALL historical fingerprints,
including rejects/prior-history; atomic durable claims allow one candidate owner.
Runtime must claim globally before mirroring into the local ledger for existing
finish checks. A crash between global claim and local mirror conservatively
retains the claim; it cannot admit another candidate with that fingerprint.

Migration requires the original controller lock, verified pins and zero active/
running jobs. Independent staging is published by rename only after all eight
partitions are written/hashed; partial staging is retained but not launchable.
Prepared receipt explicitly says `launch_authorized=false`. Activation is a
separate tested-runtime-hash-gated supervisor step, not automatic from preparation.
Final CLI contract aligned with Boole's runtime (supersedes the initial index-flag
proposal): `python -m dfm12.wave4_shard_runtime --root <BUNDLE>/shard-N`;
supervisor supplies RAYON_NUM_THREADS=2, OMP_NUM_THREADS=1,
MKL_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1. Exactly one endpoint8800+N per
worker, concurrency768, so aggregate endpoint budget is not multiplied.

Supervisor keeps the original controller lock, writes `progress-redirect.json`
in the original root, and aggregates unique shard groups into bundle progress.
Child failure drains only its owned children; no auto retry. Success requires all
eight exit0, zero active and all target quotas met, not merely process exit.
Six CPU tests pass for partition ownership, cursor/quota preservation, historical
and concurrent dedup, incomplete/drifted output refusal, and aggregate/thread-cap
contracts. Runtime integration tests/freeze remain required before deployment.

Follow-up preparation checks require exactly770000target and compare aggregate
accepted, attempts, target and job counts against the original frozen ledger
before publishing the bundle. Seven preparation/supervisor-contract tests pass.
`prepared.json` hashes are explicitly a PRELAUNCH snapshot, not ongoing hashes
of mutable databases. The supervisor refuses any existing launch receipt; it
does not claim automatic resumability. A future explicit resume path must lock
the bundle and original root, verify all old child identities have exited,
validate immutable activation/runtime pins and ownership, reconcile terminal
evidence for interrupted jobs, and verify quota/global-fingerprint invariants
against current shard databases before issuing a new launch receipt. That resume
path is not implemented or authorized merely by preparing this fallback.

Preparation copies byte-identical original manifest, seal and all manifest input
pins into each shard. Activation writes `shard-runtime.json` with the prepared
receipt hash and inherited/new implementation pins, then invokes the runtime's
real partition verifier for every shard before launching any child. Startup
fixture verification remains the deployment gate, not just a synthetic partition
test or a process existing.

### Eight-Shard Deployment

After Boole's full mocked-HTTP execute fixture and33local combined tests passed
(parent reported59focused), user authorized migration. Final runtime SHA256:
`66fbde2c2b0dfb0cc7ad66c52065a66d37a1f5f2d5b9c99caa883646481bd4e1`.
Only identity-verified3188751 received SIGTERM. It drained cleanly to101542accepted,
zero active and527376attempts/jobs; original controller is stopped, not resumed.

New root: `data/dfm13/wave4/synthetic-language-shards-20261004-v1`.
`prepared.json` verifies preserved101542accepted,770000target,527376jobs/attempts,
527376source selections,44cursors and395528used-source rows. Shared fingerprint
registry contains all historical owners. Original ledger/evidence remain intact.
Supervisor3255693 launched workers3255825-3255832 after all partition verifiers
passed; `supervisor-launch.json` records exact identities. Endpoint assignments:
8800lb;8801sl;8802be;8803fa;8804sr;8805hu/sq;8806bg/bs;8807hr/sk.
Each runtime confirms one endpoint,768concurrency and native thread caps2/1/1/1.

Actual inference verified on every worker: generation AND review request contexts
active, with roughly578-648contexts per endpoint in the captured snapshot.
Aggregate accepted101945 (+403 versus frozen baseline); all logs empty. This is
launch/functionality verification, not a warm throughput claim. Later exact
per-worker accepted deltas, process identities, HTTP counters and thread caps are
saved in `operational-verification.json`. Aggregate measurement path is bundle
`progress.json`; original root `progress-redirect.json` explicitly identifies it.
Shared servers and Baltic proof were not touched. Shards remain running; no
automatic replay/resume is implied by this first launch.

Parent's first warmed60s shard measurement is preserved in bundle
`warm-measurement-60s.json` (original `/tmp/dfm13-wave4-eight-shards-warm.json`):
22666requests/min,76590generated tokens/s,500362input tokens/s, zero additional
preemptions. Final snapshot4919running, zero waiting, KV79.19-93.65% (mean89.17%).
Accepted105988 (+4446 from frozen101542baseline). All8logs remain empty. Parent
also observed near-empty ledger queues (reserve0-4, completion0-5) and CPU0-2
pending after warmup, unlike the prior thousands queued. This is substantial
observed feeding/throughput improvement, approximately5x the preceding4519/min
single-client window; shared-server counters and differing request mix prevent
treating that ratio as a controlled W4-only benchmark. Admission samples are not
a hard instantaneous KV ceiling: already admitted generation/review work can
raise usage beyond90%. Existing checks remain unchanged. No further restart.

### Authorized Runnable-Group Rebalance

User later authorized redistributing remaining runnable work to all8endpoints
after whole-language workers0-4 became blocked or terminal. New isolated
`wave4_group_rebalance.py` and `supervise_wave4_groups.py` prepare group ownership;
original pinned runtime/preparation modules remain unchanged. Keep all66groups
and historical rows for accounting, but dispatch only explicit runnable groups:
accepted below target, attempts below6x target, and no source-block reason.
No budget reset, failed-row replay, source substitution or audit-policy change.

Group source scopes are disjoint: native `language/language/family`, OpenHermes
`language/openhermes`. Each transfers to its group owner exactly once, alongside
selected specs, original job IDs/workdirs/outcomes and local fingerprints. The
complete shared fingerprint registry is snapshotted after drain. Migrator checks
row totals, target770000, and preserved group counters before publishing a new
bundle. New receipt links `predecessor_root` and original `source_root`.

User explicitly reconfirmed768TOTAL client concurrency per endpoint, not per
family: eight processes each owns one endpoint and shares its768budget across
assigned families. Native thread caps remain2/1/1/1. Four CPU tests pass covering
assignment, source scope parsing, exact history/cursor preservation and refusing
active migration. Runtime integration/freeze and launch verification are required
before declaring this rebalance active; initial preparation did not stop clients.

Deployment preparation completed with12focused tests, including actual private
execute with mocked HTTP and real ledger/global fingerprint acceptance. The
deployment agent implemented `wave4_group_runtime.py` when the runtime relay had
not produced a file; no concurrent edit of the earlier pinned shard runtime.
Exact supervisor3255693 received SIGTERM and drained all eight owned children
to exit0, preserving585425accepted, zero active and3193487attempts. Migration
PID3396652 copies that state into
`data/dfm13/wave4/synthetic-group-shards-20261004-v2`; this is an offline copy,
not a replay. GPUs are temporarily idle while retained history/state is copied;
servers are untouched. Original language-shard bundle remains preserved.

Group migration completed:585425accepted,3193487jobs and selections,44cursors,
2401351used-source rows,2949324global fingerprints preserved. Target770000 and
attempt counters unchanged. Runtime SHA256:
`25295f2b94b5a9289accfff840418391aade9084093c48922da4785fdc2768c9`.
Retained supervisor3400158 (create-time1791138509.29) launched exactly eight
children3400618-3400625. Parent's concurrent launch3400332 exited on lock
contention before any child launch; correction to the initial handoff: no signal
was actually sent to that already-gone duplicate. No further launches/signals.

Initial aggregate runtime snapshot:585425accepted (exact preserved baseline),
6144active,3199631attempts; all eight child logs empty. Per-endpoint total worker
budget768 is shared across families, never768perfamily. Progress authority is
new v2 bundle `progress.json`, with redirects in both older campaign roots.
`supervisor-launch.json` records exact process identities; `prepared.json`
records immutable migration counts and assignments. Parent owns post-start
throughput measurement; a live PID/reservation is not itself proof of inference.

Runnable endpoint assignment (other assigned groups retained only for accounting):
- 8800: bg summary-rewrite; hu openhermes.
- 8801: bg openhermes; bs math-code; hr grounded-instruct.
- 8802: bg grounded-instruct/math-code/multiturn; hr multiturn; sq openhermes.
- 8803: bs multiturn/openhermes; sq math-code.
- 8804: hu math-code/summary-rewrite; sk multiturn/openhermes.
- 8805: hr summary-rewrite; hu grounded-instruct; sk math-code; sq tool-dialogue.
- 8806: bs summary-rewrite; hr math-code/openhermes.
- 8807: hu multiturn; sk grounded-instruct/summary-rewrite; sq summary-rewrite.

Blocked/exhausted groups are not polled for work. A newly source-blocked group
also leaves the runnable set. Finishing this runnable pass does not claim the
full770000target, and no automatic failed-row replay or budget reset is enabled.

First startup window had zero HTTP while16CPU budget measurements per worker
initialized lazily. Code confirms each CPU thread constructs its own local-only
HF tokenizer at its first measure call; this avoids concurrent mutable-tokenizer
use but incurs cold initialization. The backlog cleared without intervention:
all8endpoints subsequently had generation/review HTTP, roughly492-756contexts
per endpoint;879-1700measurements completed per shard, current CPU waits0-2,
empty logs and585545accepted (+120). Parent then observed all8GPUs active
(seven100%, one72% instantaneous). No restart or code change was made; parent
owns the next30s warmed measurement. Cold startup is not a persistent deadlock.

Verified30s warmed group-rebalance measurement:23979completed requests/min,
77050generated tokens/s and524577input tokens/s. All8endpoints recorded nonzero
completions; GPU instantaneous85-100%, KV82.7-92.7%, zero waiting and zero added
preemptions. Parent artifact `/tmp/wave4-group-rebalance-active.json` is preserved
durably as active v2 bundle `warm-measurement-30s.json`. Metrics cover shared
servers, not a controlled W4-only benchmark. This verifies resumed work across
all eight endpoints; no runtime/server changes or restarts accompanied recording.

### DFM12 Resume and CPU Finalization

The final GPU pass drained at646551accepted. CPU recovery, cancelled top-up,
uncapped Luxembourgish policy, owned-server release, and same-plan DFM12 resume
are recorded in [W4 CPU Recovery and XL Resume](dfm13-wave4-xl-resume.md).
