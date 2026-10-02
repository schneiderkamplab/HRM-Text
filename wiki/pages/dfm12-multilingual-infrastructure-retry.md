---
type: Runbook
title: DFM12 Multilingual Infrastructure Retry
description: Additive stage-aware retries of quarantined pilot transport failures, bounded owned servers and a physical half-GPU memory ceiling.
tags: [dfm12, multilingual, quarantine, infrastructure, retry]
status: draft
last_updated: 2026-09-27
confidence: high
---
# DFM12 Multilingual Infrastructure Retry

## Scope and Evidence

The user authorized retrying infrastructure failures from the completed
`data/dfm12/multilingual-quarantine700-20260927-v2` run. The frozen source has
700 outcomes: 287 reviewed, 37 audit-invalid and 376 generation-invalid.
Exactly 298 generation errors are transport failures: 296 ClientConnectorError
and two ServerDisconnectedError. The other 402 outcomes are not retry targets.
JSON serialization, full-schema validation, length stops, semantic validation
and reviewer-evidence failures are not infrastructure and are never retried.
The existing failed calibration and quarantined status remain in force; see
[reviewer calibration](dfm12-multilingual-calibration.md).

New root: `data/dfm12/multilingual-quarantine700-20260927-infra-retry-v1`.
`frozen_source/` copies and pins all source evidence, including original raw
requests/responses and outcomes. Source files and the copied snapshot are
hash-verified. Nonselected outcomes remain byte-identical. `retry-manifest.json`
pins implementation, source/input files, tests and the exact selected slots.
No accepted dataset, training tokens, export, bulk gate or successor authorization
is produced: admission and bulk remain false even if both reviewers keep a row.

## Retry Semantics

`dfm12.multilingual_quarantine_retry` is an additive client; the original
`multilingual_quarantine_pilot.py` and source root are unchanged. Up to three
calls per affected stage are durably journaled under `stages/`. Successful
stage receipts are reused on resume, not regenerated. Valid existing candidates,
primary audits and reviewer outputs are preserved. A successful new candidate
receives the usual two independent audit stages, still in quarantine.

The allowlist includes connection refusal/reset, disconnection, timeout,
incomplete HTTP payload and HTTP 429/502/503/504. HTTP 400/500 and generic errors
are not blindly classified as infrastructure. An indeterminate interrupted
request without a terminal receipt is retained as unknown and not reissued;
the retry budget is never reset by restarting. Immutable attempt receipts and
the root lock prevent concurrent writers. Completed retry outcomes are hashed.

Eight workers share rotating endpoint leases, one active request per endpoint.
Endpoint model/context health is checked before each call. An infrastructure
failure opens a 60-second endpoint cooldown. If no healthy/occupied endpoint
exists for 45 seconds, a global circuit break suspends dispatch and preserves
pending work rather than failing hundreds of slots against one dead server.
The client has a six-hour bound. Raw responses precede parsing/validation.

## Owned GPU Budget

The latest user restriction is a maximum of half the physical GPU memory for
this work, with no concurrent identity training. The dedicated server module
`dfm12.multilingual_retry_servers` requires all eight GPUs free and unoccupied
ports 8600-8607 plus internal ports 31000,31100,...,31700. It serves cached
`google/gemma-4-26B-A4B-it` from the existing pinned snapshot in audit conda,
one server per GPU, utilization 0.40, context 8192, max sequences 8, batched
tokens 4096, eager mode, all multimodal limits zero, and the FlashInfer sampler
disabled. CPU compile workers are capped at two per server (16 total).

Physical GPU usage includes CUDA/context overhead, not only tensor allocations.
The supervisor records per-GPU current and peak usage, stops at 48% before the
50% ceiling, and stops its own work if a foreign GPU process appears. It uses
inherited ownership tokens, process creation/start ticks, session IDs and pidfds;
cleanup signals only verified owned processes, never unrelated jobs. It has a
20-minute startup and seven-hour lifetime bound, cleans up on client completion,
failure or stop request, and writes `server-release.json` plus a lifecycle-local
`release.json`. It never starts or resumes training.

## Validation and Status

32 CPU tests passed across retry and unchanged quarantine tests, with no skips,
recorded in `data/dfm12/multilingual-quarantine-retry-tests-20260927.xml`.
Coverage includes actual 298-slot selection, non-infrastructure exclusions,
stage reuse, three-call budget across restarts, unknown inflight requests,
candidate/audit preservation, locks/no overwrite, circuit breaking, exclusive
endpoint leases and memory configuration. CPU preparation passed with 298
generation retry slots and zero initially selected audit-stage retries.

**Historical dedicated launch blocked at preparation:** the recheck found European campaign
supervisor 3549360 owning servers 3549860-3549867 on ports 8600-8607. Their
EngineCore PIDs are 3550200,3550179,3550165,3550186,3550198,3550172,3550212,3550156,
using 85986 MiB of 183359 MiB per GPU (about 46.9%). They are not owned by this
retry task. At that point no retry server/client had been launched, and none of
those foreign processes was signalled.

### Borrowed Endpoint Authorization Supersedes Launch Block

On 2026-09-27 the user explicitly authorized borrowing healthy ports 8600-8607
and clarified that the half-memory ceiling covers this thread, not unrelated
European audit allocations. The dedicated-server path was not launched.
`dfm12.multilingual_retry_borrow` instead launched detached CPU supervisor
3559116 (start ticks 191042347) and CPU client 3559128 (start ticks 191042475,
session 3559128). Both identities and the supervisor implementation hash are
durable in `borrow-launch.json` and `borrowed-client-process.json` in the retry
root. Actual progress reached 67 of 298 selected slots; this is execution,
not merely a queued plan. Consult `retry-progress.json` for current counts.

There is no additional owned GPU allocation. The eight GPU engine PIDs listed
above remained the only compute processes at the first progress check. Borrowed
servers must never be stopped, restarted or signalled by this task. The bounded
supervisor owns only the CPU client session plus token-verified descendants;
cleanup checks exact PID/start ticks and writes `server-release.json` with
`owned_teacher_pids: []` and `borrowed_teacher_cleanup_attempted: false`.
Health checks, endpoint rotation and circuit breaking remain active in the
client if foreign servers disappear. No training is launched or resumed;
the parent owns subsequent identity training coordination. All results remain
quarantined with admission disabled.

### Terminal Result and Training Gate

The retry finished all 298 selected slots successfully at the infrastructure
level. Of those, 234 reached completed review, 44 failed non-infrastructure
audit validation and 20 failed non-infrastructure generation validation.
Zero remaining selected outcomes contain infrastructure errors. Completed
review is not admission or necessarily a reviewer keep decision.

Selected-slot breakdown (reviewed / audit-invalid / generation-invalid):

| Language | Reviewed | Audit-invalid | Generation-invalid |
| --- | ---: | ---: | ---: |
| fo | 35 | 4 | 5 |
| is | 34 | 8 | 3 |
| nb | 33 | 5 | 2 |
| nl | 35 | 7 | 3 |
| nn | 34 | 4 | 1 |
| pl | 30 | 11 | 2 |
| sv | 33 | 5 | 4 |

| Task family prefix | Reviewed | Audit-invalid | Generation-invalid |
| --- | ---: | ---: | ---: |
| grounded | 119 | 22 | 0 |
| math | 4 | 0 | 1 |
| multiturn | 52 | 7 | 13 |
| openhermes | 3 | 1 | 0 |
| summary | 55 | 14 | 2 |
| tool | 1 | 0 | 4 |

Combined additive-root totals are 521 reviewed, 81 audit-invalid and 98
generation-invalid; 357 would be kept by both audits, but admitted rows and
training tokens remain zero. Final verification preserved the frozen original
700 and the 402 nonselected outcomes.

`server-release.json` confirms client exit zero, no owned survivors, no owned
teacher PIDs and no borrowed-teacher cleanup. Both CPU PIDs were absent at the
post-release check. The requested sequencing gate is
`logs/training/dfm12_XL_identity_corrective10000steps/gpu-release.json`, campaign
`identity-corrective10000`, with completion/release hashes and an empty owned
process list. It does not claim that foreign servers were released or that GPU
capacity is unrestricted. Subsequent training must independently enforce its
headroom and thread-memory limits; this task did not launch training.

### CPU Review of Remaining Invalid Outcomes

The additive report
[non-infrastructure assessment](../../data/dfm12/multilingual-quarantine700-20260927-infra-retry-v1/noninfra-review-v1/assessment.md)
examines all 81 audit-invalid and 98 generation-invalid rows. Its companion
`report.md` has per-language/task cause matrices and verbatim examples;
`inventory.json` preserves full raw response text, evidence paths and hashes.
No pinned files or original outcomes were changed, no requests retried, no GPUs
used and no admission gates weakened.

Audit failures are review contract/budget failures, not 81 proven bad candidates:
57 quote failures, 2 tool pointer/span failures, 8 local context overflows,
5 inconsistent issue flags, 1 missing issue, 5 overlong explanations and
3 invalid literal translations. Of the 59 quote/pointer cases, 41 have a first
rejected quote exceeding 240 characters. Generation failures include 33 empty
strings, 12 malformed JSON responses despite stop finishes, 17 role-order
failures, 31 tool/clarification provenance failures, 3 length stops and 2
unexplained abort stops (not transport-authorized retries). These are first
failure counts, not exhaustive semantic labels.

Raw inspection also found punctuation-only content, English output in NB/NN
tasks and an unsupported reservation-success claim. Thus parser/contract fixes
cannot imply semantic acceptance. Recommendations are limited to isolated
contract fixtures, concise indexed evidence prompts, reviewer-budget preflight,
subtype-specific tool calibration and native-reviewed contrastive controls.
The current failed calibration and quarantine remain unchanged.
