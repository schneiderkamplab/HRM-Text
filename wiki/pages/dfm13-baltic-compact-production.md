---
type: Runbook
title: DFM13 Baltic Compact Production
description: Authorized 26B Baltic 70K-per-language successor with compact review and preserved historical holds.
tags: [dfm13, baltic, synthetic, production]
status: draft
last_updated: 2026-10-04
confidence: high
---
# DFM13 Baltic Compact Production

## Feeding Diagnosis After 384 Resume

Read-only check on 2026-10-04: the private 384 runtime still uses the inherited
admission gate's 0.2-second per-endpoint spacing, zero waiting-request threshold,
and 30-second circuit cooldown. Increasing worker count does not remove these
limits. A roughly minute-long admission snapshot showed 67-83 new candidates on
six endpoints with one circuit recovery each, versus 191-193 on two endpoints
without a recovery. Thirty inspected recent transport errors were
`ServerDisconnectedError`; their underlying cause is not established. Do not
remove disconnect protection or replay uncertain requests on this evidence alone.

Across 13 shared-server samples, per-server mean active requests ranged from
139 to 226. GPU6 was not persistently at its earlier instantaneous low of 29.
Prefer diagnosing disconnects and synchronous event-loop source/render/durable
writes, then adjusting admission pacing, before manually reassigning clients.
No runtime changes were made for this investigation.

User authorization2026-10-04: start fresh Lithuanian and Latvian synthetic
generation toward70000 accepted conversations each, sharing existing26B
servers8800-8807 with the main384/server client. No server/training mutation.

Runner `dfm12.baltic_compact_successor` reuses the existing private Baltic quota
controller, ledger, source provider, stage transport, recovery and backpressure.
It installs the compact whole-conversation reviewer and generation constraints.
Only the private runner concurrency guard changes64 to128; imported/shared
controller code remains untouched. Generation and review are sequential within
each worker:128 workers/server means a combined cap1024 requests, not separate
generation/review pools. The existing90%-KV/waiting/spacing admission gate still
throttles starts. No source/quality gate is weakened to fill concurrency.

Root: `data/dfm13/baltic/synthetic-compact-26b-20261004-v1`.
Detached PID2885910; start_ticks249557237. `launch.json` records command and
create-time. `runner.log`, `runtime.json`, `progress.json` and
`admission-status.json` expose current state.18 focused tests passed.
Initial live confirmation:18LT and7LV new automated keeps,167active candidates;
all eight endpoints admitted requests. These are running-campaign observations,
not final counts or independent certification.

The prior `synthetic-production-staged-v3` ledger and source selections were
backed up under its controller lock after checking zero running jobs. All12392
historical attempts, source cursors, fingerprints and external work artifacts
are preserved. Its7626acceptedLV rows become `prior_quality_hold` in the new
ledger and receive zero quota credit pending exact-hash clearance. Original
ledger/artifacts were not rewritten. Poincare's3720 staged candidates comprise
1415original keeps,2239technical retry keeps and66repairs; that staging receipt
has admission=false and is NOT blanket import authorization. No held candidate
is approved merely to increase the accepted counter.

Targets retain all six families per language:20000grounded,10000summary,
15000multiturn,15000OpenHermes,6000math/code,4000tool. Existing per-group6x
attempt guards and deduplication remain. Prior accepted candidates can be
credited later only by an explicit idempotent exact-hash transaction under the
successor controller lock, with quota checks and preserved review lineage.
No automatic export/upload or training integration is enabled by this runner.

Implementation review: explicit MAX_CONCURRENCY with a private override is the
preferred future cleanup. The active successor currently uses an exact,
asserted AST change to its private execute function; shared source and other
running campaigns are not changed. Do not edit pinned dependencies during this
run. `base.verify` checks pins/ledger quotas, while the historical CLI enforced
calibration approval separately. New explicit user launch authorization replaces
that CLI prerequisite here; no calibration-passed receipt is fabricated.
Historical row/source holds remain preserved even though stale group retry/block
flags were reset for fresh work. Early compact empty-rationale/schema failures
are fail-closed and do not receive accepted credit.

### Fair Scheduling Correction

PID2885910 was gracefully drained with306new automated keeps (LT194/LV112)
and zero active jobs. Inherited12392LV-grounded attempts would otherwise delay
that group under attempts/target dispatch. Under controller.lock those attempts
were moved to durable historical accounting (metadata and fairness-offset.json)
and the successor group attempt counter reset to0. All historical jobs,
fingerprints, accepted counters and next_slot112392 remain intact. The6x
attempt cap now applies to new successor attempts; historical attempts are
reported separately, not erased.

Replacement client PID2888565, start_ticks249577188, uses the same pinned code
and root; launch-fairness.json and runner-fairness.log record the restart.
128/server remains a combined upper bound, not claimed achieved occupancy.
Inherited0.2-second start spacing (five new candidates/second/server), KV and
waiting checks remain unchanged. No server/main-audit/training process changed.

### Bounded Generation Schema Probes, 2026-10-04

`scripts.smoke_baltic_generation_schema` replays one previously malformed
generation per language/family without changing production or admitting rows.
`data/dfm13/baltic-schema-smoke-20261004-v1` obtained 11/12 full-schema and
native-assembly successes using JSON schema instead of JSON-object transport.
The remaining response finished with `stop` but contained an unterminated JSON
string. A second same-selection arm with `include_reasoning=false` obtained
11/12 schema successes and 10/12 native assemblies (empty text and an invalid
text control caused the two failures). These are selected failure replays with
stochastic generations, not population acceptance rates or a controlled estimate
of the transport change's benefit. No semantic audit or training admission was
claimed for these smoke outputs.

The unexpected malformed JSON motivated a separate enforcement test:
`scripts.probe_vllm_schema_enforcement` supplied an exact schema conflicting with
the user prompt. All eight servers enforced it both normally and with
`include_reasoning=false` (16/16). Thus a globally disabled grammar/reasoning
parser bug is **not established**, and no server or production request flag was
changed on that hypothesis. Receipt:
`data/dfm13/schema-enforcement-probe-20261004-v1.json`.

Fourth-wave770K generation is now [queued behind verified Baltic completion](dfm13-baltic-wave4-handoff.md).
The detached watcher does not alter this running campaign or infer success from
PID exit. Compact repair verdicts remain unaccepted holds, not automatic repairs.

## Post-Recovery Measured Rate, 2026-10-04

After Boole's technical recovery/runtime migration, observed PID2936091 for
301.304 seconds,03:06:30.858-03:11:32.161 UTC. Recovery table count stayed13093
at both endpoints, so its one-time credit is excluded from throughput.
Audited accepts22686 ->24124:1438 new,286.36/minute; charged candidate attempts
64006 ->67911:3905 new,36.82% acceptance yield. These are automated-gate keeps,
not native-quality certification;7626 historical LV holds remain uncredited.

Conditional remaining ETA:6.74 hours pooled,13.19 hours for all family quotas at
unchanged per-group rates (LV summary-rewrite tail). Unlike the earlier pre-fix
window's approximate109K capped projection, all12 groups now project to reach
quota within6x candidate budgets if measured yields persist. The weakest margin
is LV summary-rewrite20.43% observed versus16.28% required on remaining budget.
The cap remains enforced; no guarantee, quota change or admission is implied.

Shared endpoints completed31105 HTTP requests during the window,6194/minute;
start/end GPU utilization96-100%, no new preemptions, but endpoint occupancy and
KV remained uneven. Baltic active84 ->83 despite128/server ceiling; repeated
technical circuit cooldowns and shared waiting checks constrain dispatch.
Main DaLA progressed369746 terminal data rows over its separate316.46-second
receipt interval,70103 rows/minute, implying conditional5.14 hours to remaining
first-pass scope. Rows are not HTTP requests; producer remained unfinished.

Full per-language/family table, GPU samples, recovery exclusion and limitations:
[post-recovery measurement](../../docs/reports/dfm13_baltic_post_recovery_rate_20261004.md).
Measurement was read-only; only report/wiki written. Clients, servers and the
guarded W4 watcher were not stopped or changed.

## Isolated Streaming Guard CPU Prototype

New `dfm12.calibration_loop_guard_fast` leaves the live pinned streaming module
unchanged. It filters viable repeated-block sizes with rfind on the tail's last
character, preserves ascending checks and the identical eight-block comparison,
and retains whitespace/escape/tail/reason semantics. Real saved104-stream replay
(19724 deltas) matched every decision/state. Five-run CPU medians: guard138.30ms
to7.89ms, strict JSON decode plus guard194.68ms to63.49ms. This is a replay
microbenchmark, not a measured production speedup or proof of the entire live
CPU bottleneck. Seeded random/boundary/state/order tests accompany the prototype.
No runtime bindings, pins, processes or server state were changed. Boole/main
can evaluate a controlled private successor; exact evidence and integration
scope: [guard handoff](../../docs/reports/dfm13_loop_guard_fast_handoff_20261004.md).
