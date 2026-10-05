# Coverage efficiency handoff to Poincare

Explicit user-authorized scoped change in `dfm12/wave_job_coverage.py` only;
no frozen31B modules, live workers or queues changed by this implementation turn.

Reconciliation still verifies registered component and candidate-file hashes and
constructs the exact current audit payload. It calculates the same job ID as
Queue.add: digest(['audit', payload]). Batches hold at most512 payloads/IDs; one
primary-key IN query reads only IDs, not existing multiKB payloads. Existing-only
batches never BEGIN IMMEDIATE or INSERT. There is no corpus-sized in-memory set.

Only missing IDs acquire the writer. Queue.add remains INSERT OR IGNORE, so a
concurrent insertion after the membership read is harmless and existing job
status, attempts, leases, results and history remain unchanged. Insert failures
roll back the bounded transaction. Receipt counts retain all input rows and
count only actual inserted jobs. This relies on the existing content-addressed
job-ID invariant, as the previous INSERT OR IGNORE implementation did; it does
not newly certify arbitrary externally corrupted payloads or concurrent deletion.

Six focused tests pass: exact missing coverage/failed-history preservation,
source-hash mismatch refusal, existing batch while another connection owns the
writer, competing insertion before write, rollback, and512-row batch bounds.

## Deployment boundary

PID2427821 already imported the old reconciler and remains untouched. Supervisor
2103630 imports reconcile inside main only AFTER pivot preparation/enqueue, so
its next wrapper reconciliation will load this implementation naturally. No
restart/retry/requeue was performed. Poincare owns broader CPU orchestration;
this report records the precise boundary to avoid overlapping edits.

## Bottleneck evidence

The old pass writes even existing jobs, taking BEGIN IMMEDIATE across512-row
chunks; that can contend with live audit claim/completion writers. Observed
process2427821 remains D/folio_wait_bit_common, which directly indicates a
filesystem page wait, NOT proof of SQLite lock wait. Transform release had the
same wait, and GPU feed varied despite millions queued. Both storage pressure
and serialized commit access are plausible. This fix removes unnecessary write
transactions but still reads/hashes source payloads and performs indexed reads;
no throughput gain is claimed before the next live pass is observed.

## Live intervention assessment, Unix1791045513

Ten-second/40-sample CPU-only inspection:

| Thread | nanosleep | filesystem-page wait | other |
| --- | ---: | ---: | ---: |
| audit2032197 DB thread2032216 | 34 | 2 | 4 |
| booster2111441 DB thread2111446 | 38 | 2 | 0 |
| old reconciler2427821 | 6 | 20 | 14 |

The clients have exactly one DB executor thread, shared by claim, heartbeat and
completion flush. The code uses BEGIN IMMEDIATE for claims/flushes and SQLite's
60-second busy timeout. Repeated sleeping of BOTH DB workers alongside the
reconciler's page waits is consistent with writer serialization amplified by
slow storage, but not conclusive: /proc syscall and stack access are denied,
no usable matching /proc/locks owner was visible, and strace is unavailable.
There is no demonstrated network/server fault or need to restart servers.

At snapshot, old pass77 components/2355595 rows checked, zero insertions; about
3796536 of6152131 translation rows remain. Process fd8 pointed into a later
direct-el-hr source, so progress continues. Latest monitor returned all100% GPU
utilization but window throughput14748/min, roughly half the earlier29K rate.

**Recommendation to owner: controlled CPU-only interruption/continuation is
reasonable and likely beneficial, not guaranteed.** Avoid blindly restarting the
entire wrapper: it repeats direct discovery, receipt hashing and enqueue checks
for all previously prepared data. Prefer continuation at pivot build plus one
final reconciliation with the new implementation, under the SAME advance lock.
All approved direct/institutional candidates and registered components already
exist; the final exact-coverage pass must still run before completion publication.

Safe sequence, NOT performed here:
1. Revalidate exact PID2427821 identity and parent2103630; send TERM only to the
   owned CPU child. Its active SQLite transaction rolls back on connection/process
   exit; previously committed coverage insertions remain. Do not delete WAL/locks.
2. Wait for child exit and wrapper's check=True subprocess failure/exit. Confirm
   advance-parallel.lock and institutional/enqueue locks are released; no orphan
   child. Never start a second writer merely because TERM was sent.
3. Under advance-parallel.lock, execute the existing wrapper's remaining pivot
   build, sealed-pivot enqueue, NEW reconcile and final marker publication in the
   same order. Preserve checksums and exact coverage; do not fabricate the marker.
   Poincare can own this minimal explicit continuation; no frozen31B changes.
4. Compare existing monitor's completion rate and idle fractions before/after,
   while audit clients and servers remain untouched. Pivot indexing still reads
   6.59M English-leg pairs, so I/O pressure may persist; improvement is unproven.

No signal, restart, new worker, attachment or live DB write was performed during
this assessment. If a stage-aware continuation is unavailable, keep the current
pass rather than launching an overlapping full wrapper.

## Authorized continuation launched

User subsequently authorized the scoped CPU-only handoff. New entry point:
`scripts/resume_wave4_parallel_after_coverage.py`; PID2446844 detached with
`python -u -m scripts.resume_wave4_parallel_after_coverage --authorization
data/dfm13/wave4/coverage-continuation-authorization.json`.
Log: `logs/dfm13/wave4/coverage-continuation.log`.
Status: `data/dfm13/wave4/coverage-continuation-status.json`.

Authorization pins code and exact child2427821/parent2103630 identities. Before
the one permitted child SIGTERM, the script verifies every approved extraction
hash, requested component registration and sealed preflight linkage. It waits
up to600seconds for both old processes, without escalation, then acquires the
original advance lock and probes released institutional/enqueue locks. Pivots,
enqueue, new read-first exact reconciliation and final marker follow in order.
No marker on failure. No audit clients/servers are signaled. Existing SQLite
history/artifacts remain. Nine continuation/coverage tests pass.

Poincare: this process now owns CPU parallel continuation; do not concurrently
resume the old wrapper. Frozen31B preparation/assembly is unchanged.

### Exit-check recovery

PID2446844 verified all extraction inputs and delivered the one authorized SIGTERM
to2427821. Parent2103630 exited through subprocess check=True as expected. The
continuation then failed because psutil.NoSuchProcess was not caught by its
exit-check helper. No further signal was delivered and no final marker written.
The helper now handles that exact exception (regression tested).

Both original PIDs were independently absent before launching successor2448161.
Its authorization-v2 pins the prior authorization/log and sets already_stopped;
it refuses to signal and requires both old identities absent, verifies extraction
again, then acquires original locks and resumes pivots. Log:
`logs/dfm13/wave4/coverage-continuation-v2.log`. Ten focused tests pass. Original
authorization/log preserved. This correction touches no frozen31B implementation.

Verified actual progress: status pivot_build at1791045864, PID2448161 detached;
all203 direct and21 institutional receipts checked (640 evidence pins). Logs
show INDEXED English legs; anchors.sqlite grew to1079410688bytes. Both old CPU
PIDs absent, audit2032197/2111441 unchanged/live. No completion marker yet.

### Pivot manifest verification

Completed manifest covers all297 requested non-English pairs:226 have117240
candidate pairs,39 skip pivots because direct supply is at least1000,32 have no
unambiguous pivot supply.45 unique English-leg inputs match the previously
fully verified extraction hashes; per-pair input pin lists agree. These are
bidirectional pair records, not117240 accepted rows (potential234480 directions
before preflight/audit). No acceptance or quota completion is inferred.

At the first enqueue snapshot,7 components/3915 ready pairs were registered,
219 components remained; PID2448161 was live in pivot_enqueue. New read-first
reconcile follows only after all enqueue calls return. Completion marker absent.

All32 zero-pivot pairs involve sk and also have zero prepared direct/institutional
rows. Counterparts:be,bg,bs,ca,cs,da,de,el,es,et,fa,fi,fo,fr,hr,hu,is,it,lb,lt,lv,
nb,nl,nn,pl,pt_pt,ro,sl,sq,sr,sv,uk. English-sk is additionally unavailable outside
the non-English pivot manifest. This is a genuine current APPROVED-supply gap,
not proof of absent public corpora: en-sk inventory has institutional sources
still in license_review, and no approved English-sk leg. Reviewing eligible
corpus/version evidence is the appropriate follow-up, not manufactured pivots.

Guards: preflight may reduce117240; registered-component count omits an active
partial enqueue; new reconciliation must complete before marker; same-English
anchor does not prove sense/language equivalence, so both directions and both
leg provenance require audit. Combined direct/pivot token budgets remain later
accepted-only selection work. No process intervention or feature change here.
