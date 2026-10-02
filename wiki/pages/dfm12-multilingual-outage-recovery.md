---
type: Runbook
title: DFM12 Production Outage Recovery
description: Explicit infrastructure-only replay with preserved generation and transactional quota accounting.
status: draft
last_updated: 2026-09-28
confidence: high
---
# Production Outage Recovery

## Authorization and Scope

On 2026-09-28 the user authorized retrying production failures caused by the
shared-server outage from Unix time `1790600890`, then restarting production.
This is a scoped exception to the normal no-automatic-replay policy, not
authorization to retry schema, truncation, repetition, or semantic failures.
The [production controller](dfm12-multilingual-quarter-production.md), its
generation/review contracts, source provider, manifest and implementation pins
remain unchanged. The accepted target remains 385,000.

Implementation: `dfm12/multilingual_outage_recovery.py`.
Recovery root: `data/dfm12/multilingual-outage-recovery-20260928-v1`.
Original root: `data/dfm12/multilingual-quarter-native-20260927`.

Only the verified owned client PID 1336576 (create time 1790579706.44,
start ticks 199717944) received SIGTERM. It drained and exited with
166,827 accepted, 326,525 counted production candidates, and zero active.
Shared Gemma endpoints 8600 through 8607 are borrowed, not owned. No server,
training process, or identity holdout worker was signalled or launched here.

## Safety and Receipts

Preparation requires the controller lock and an idle ledger, validates all
frozen pins, and seals an explicit start/end timestamp selection. Recognized
failures are transport exceptions and the explicit EngineCore-unavailable
internal-error response. Generic HTTP errors and unknown interruptions do not
qualify. Matching terminal outcome, specification, stage, endpoint, and error
evidence are required. Complete saved responses are not discarded.

Original files remain unchanged. `archive/<id>/` retains the original ledger
row and stage/request/outcome/candidate evidence. `manifest.json` and
`seal.json` pin the selection, original files, copies, and recovery code.
For review-only failures, `work/<id>/` reuses the completed generation stage,
request and candidate. Strict generation assembly and raw output are checked;
the frozen stage implementation checks request hashes before reuse.

Each existing row receives at most one authorized replay. A transaction checks
the original row, reserves quota, and writes a permanent recovery marker.
Attempts, source cursors, targets and stable row IDs do not change. Fingerprint
ownership remains present; only the same original row may reuse its preserved
fingerprint. Recovered keeps pass the unchanged strict validation before credit.
Interrupted replays become terminal, not silently retried.

Replay uses 32 clients per endpoint, the existing KV admission gate (at most
90% and zero queued requests), bounded transport handling, and a one-hour
pass deadline. Afterwards the supervisor verifies the idle ledger and frozen
pins before launching the unchanged controller at 64 clients per endpoint.
`production-resume.json` records the new exact PID and create time; a repeated
resume invocation is rejected. The controller lock remains the final exclusion
against concurrent production. Recovery progress and completion have separate
receipts; the production ledger remains authoritative.

## Validation

71 CPU tests passed across recovery, quarter ledger, and admission suites.
Coverage includes strict error selection, timestamp bounds, provenance drift,
quota rollback, exactly-once journal activation, preserved fingerprint ownership,
duplicate-launch prevention and completed-generation reuse without HTTP.

Operational status is recorded in `runtime.json`, `progress.json`,
`completion.json`, and `production-resume.json` under the recovery root.
`validation.json` records a live recheck of 18,117 original, archived and
preserved files with zero hash drift, plus unchanged quarter manifest and
implementation pins. Recovered accepted artifacts live in the new per-row
work directories; existing ledger rows point there without changing their IDs.

The sealed interval ends at Unix `1790604859.850114`. It selected 1,159 rows:
305 generation retries and 854 review-only retries. Excluded within the interval:
2,459 generation invalid outputs, 1,852 review invalid outputs, 4,959 valid
semantic rejects and 7,879 already accepted rows. Supervisor PID 2859113,
create time 1790604975.91, launched detached; `launch.json` pins the manifest
SHA-256 `292032f90a2d6996efdc378dcf81c726fee4ab52a41862220ade7a4bd234fa77`.

At handoff (Unix 1790605428), replay had 284 recovered accepts, 220 semantic
rejects, 128 invalid outputs, 3 fresh transport failures, 38 running and 486
not yet replayed. The ledger held 167,111 accepted and unchanged 326,525
counted candidates. The detached supervisor remained alive; production resume
had not yet occurred. The parent explicitly requested leaving replay and its
automatic production restart running. Shared endpoint metrics were 91.6-99.9%
KV usage, with waiting queues on seven endpoints, so admission was throttled.
These are timestamped intermediate counts, not a completion declaration.
