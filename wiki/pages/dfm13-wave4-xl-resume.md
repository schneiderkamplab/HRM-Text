---
type: Runbook
title: W4 CPU Recovery and XL Resume
description: Final W4 recovery policy, owned-server release, and DFM12 XL resume from3081500.
tags: [dfm12, dfm13, operations, recovery]
status: stable
last_updated: 2026-10-04
confidence: high
---
# W4 CPU Recovery and XL Resume

Related: [Baltic and W4 handoff](dfm13-baltic-wave4-handoff.md).

### Gated XL Resume After Runnable Work

User requested resuming the EXISTING DFM12 XL epoch after remaining GPU work,
not scheduling hypothetical DFM13 training. No active auto-resume watcher was
found for this current campaign; the historical Repo interlude watcher was for
a different checkpoint. Prepared/tested `scripts/resume_xl_after_wave4.py`, then
armed gated monitor3409168 (create-time1791139240.36). Durable state:
`logs/dfm13/wave4-xl-resume-3081500-20261004/{armed.json,watcher-launch.json,status.json}`.
Initial phase `waiting_runnable_pass`. Two focused predicate tests pass; actual
checkpoint completeness and pending scheduler row were checked before arming.

IMPORTANT additional user clarification: possible CPU salvage of structurally
invalid keep reviews remains under assessment. The watcher MUST NOT infer that
GPU work is over merely because this generation pass ends. It requires a separate
`gpu-work-complete.json` in its state root with all of:
`gpu_work_complete=true`, `all_shared_gpu_clients_finished=true`,
`remaining_gpu_work=0`, `recovery_disposition_final=true`,
`authorize_training_resume=true`, and exact absolute `campaign_root`,
`server_root`, `plan` matching the armed constants. This receipt is ABSENT at
arming. CPU-only salvage may continue after resume, but any selected GPU review
must finish before the explicit release. No blind admission or automatic replay.

Further gates: successful runnable-pass terminal receipt, zero active, all eight
owned child processes and supervisor exited; unchanged campaign/plan/stop pins;
no other detected shared clients; server running/waiting zero for30seconds;
all GPU processes belong to current ownership receipts. Unknown occupants block
without signals. The only teardown request is pidfd SIGTERM to exact server
supervisor2687874 (root `logs/dfm13/gemma26-compiled-switchback-20261003-v1`),
which performs its existing owned-session cleanup. GPUs must then be empty and
the lifecycle stopped receipt present. No foreign processes are killed.

Resume uses unchanged `logs/scheduler/dfm12_XL_epoch11_noidentity`, pending
`dfm12-xl-e11-step_3100000-train`, complete `ephemeral_step_3081500` under
`checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity`; its prerequisite is done.
Same run manifest/W&B identity and trainer settings; clear the pinned stop via
scheduler CLI, prepend hrm PATH, CUDA_VISIBLE_DEVICES0-7, detached persistent-vllm
runner. Receipt records runner identity, then monitors actual step advancement.
Watcher deadline48hours fails closed; startup progress timeout does not kill or
retry training. No DFM13 plan, source registration or new generation is scheduled.

Blocked-group remedies remain separate decisions: add pinned unique native
sources or verified nonoverlapping complete windows for source shortages; diagnose
technical contract failures and salvage only independently supported outputs for
attempt-exhausted groups. Do not reset6x budgets, repeat failed candidates or
weaken quality gates solely to reach nominal quotas. Residual semantic failures
stay excluded unless separately authorized for bounded repair/review.

Superseded release-decision hold (2026-10-04): user explicitly confirmed keeping
DFM12 and CPU-only recovery/finalization, with no additional GPU work requested.
Detached `scripts.authorize_wave4_gpu_release` PID3410170 (create-time
1791139336.86) now automatically produces the release receipt, polling every
10seconds. Its authorization and identity are recorded in the same state root as
`release-authorization.json` and `release-gate-launch.json`; log is
`release-gate.log`. It requires verified pins, successful runnable-pass terminal,
zero active, all campaign processes exited, no detected other shared clients,
owned GPU occupants only, and idle endpoints before asserting completion.
It does not signal processes or start training itself. Watcher3409168 then
performs its existing repeated idle/ownership checks and owned teardown/resume.
CPU recovery (Boole) and finalization (Tesla) do not block this handoff. No manual
flag is needed, no pinned watcher code changed, and no DFM13 training is queued.
Both processes were verified alive while still waiting for the current pass;
GPU completion has not been asserted prematurely. Gate errors/deadline remain
fail-closed and are recorded in `release-gate-error.json`.

### Final Top-Up Supersedes CPU-Only Release

Superseded on 2026-10-04 by explicit user authorization: perform one final GPU
top-up after the current runnable pass and completed CPU recovery, then finalize
and resume the same DFM12 plan. Exact-owned resume watcher3409168 and release
producer3410170 were stopped after matching PID, creation time, start ticks,
session and command line. Both exited; neither `gpu-work-complete.json` nor
`training-resumed.json` existed. No servers or campaign workers were signaled.
Receipt: `logs/dfm13/wave4-xl-resume-3081500-20261004/held-for-topup.json`.
The old watcher must not be rearmed against the old campaign completion alone.

New target735000: LB35000, other ten languages70000 each. Preserve every existing
accepted row and family acceptance floor; distribute LB's remaining quota above
those floors. Only underfilled groups receive attempt ceilings of12times their
ORIGINAL family target, not twice spent attempts or twice the new deficit.
One successor uses8independent workers,768combined generation/review requests
per endpoint, unchanged shared servers and no additional rounds without new
authorization. Boole owns completed CPU recovery and clean-keep stage/final
adapter; the new256-worker completed recovery receipt is required before sealing
successor quotas. Current GPU pass remains untouched while preparation runs.

CPU preparation files: `dfm12/wave4_topup_policy.py`,
`dfm12/wave4_topup_ledger.py`, `dfm12/wave4_topup_runtime.py`, and
`dfm12/wave4_topup_seeds.py`. Runtime is not launched or sealed yet.
Policy/ledger tests verify acceptance floors, absolute ceilings, active-state
rejection, and transactional schema rollback (six tests). Source preparation
PID3417711 completed a separate immutable inventory at
`data/dfm13/wave4/topup-seeds-20261004-v1`: added19949LB,50167SQ,49572BS exact
nonoverlapping complete-paragraph passages, at most4per parent document, each
500-2400characters, no text rewriting. Original seed inventory is retained;
all added passages require generation and audit. SQLite SHA256
`002f40b7edc7f95a91300319ef7583ac7b6e461ce77207b3bd19c7a84e834206`.
Preparation/coordination receipts and log:
`data/dfm13/wave4/topup-preparation-20261004-v1/`.

Superseded again by final user decision (2026-10-04): no GPU top-up; CPU recovery
covers the ten non-LB targets, and LB must retain ALL valid unique existing and
recoverable rows, not a35000cap. Exact supervisor3400158 received graceful
SIGTERM; final campaign receipt records646551accepted, zero active, all8exits0.
Shared servers were not signaled by the client drain. The old recovery finalizer
had been deliberately held for the735Kretarget, not crashed. The provisional
735Kselector is superseded and admitted nothing; it also stopped on an overly
strict assertion that deterministic checks must be empty, whereas a valid proof
may contain `source_turn_roles: passed=true`. Boole/Tesla own uncapped-LB CPU
finalization; it must not block the GPU handoff.

Rearmed existing same-plan watcher3427282 and automatic release producer3427284.
Derived `gpu-work-complete.json` was issued only after terminal/no-client/idle
checks. After30seconds quiescence, exact server supervisor2687874 received the
owned lifecycle teardown request. GPU process list then became empty and cleanup
completed. Scheduler3428601 launched the unchanged DFM12 plan from3081500;
torchrun3428726 and8pretrain ranks3428772-3428779 were observed. Same W&B run
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, `reset_ema_on_resume=false`, existing
optimizer/training settings. No DFM13 training or GPU top-up was scheduled.
Receipts `final-cpu-only-authorization.json`, `watcher-rearmed.json`,
`release-gate-rearmed.json`, `teardown-requested.json`, `training-resumed.json`
are under the existing resume state root. Actual step advancement remains under
the detached watcher's monitor until `training-progress-verified.json` appears.

Progress-verifier correction: the original receipt claiming3100000 was INVALID;
its loose regex matched `stop_after_step=3100000` in the logged command. Archived
as `training-progress-invalid-command-match.json`, with before/after verifier
hashes in `progress-verification-correction.json`. No training interruption or
second scheduler launch occurred. The verifier now recognizes only actual tqdm
`current/total` progress counters; tests cover command exclusion, initial3081500,
and later counter advancement (six resume/release tests pass). Read-only monitor
3430820 was launched with `monitor-progress`; a new verified receipt must name
`evidence=actual_tqdm_counter`. Initial resume/W&B startup is confirmed, but must
not be described as step advancement until that actual counter appears.

Confirmed afterward: read-only monitor observed actual tqdm counter3081505,
greater than restored3081500. Replacement `training-progress-verified.json`
records `evidence=actual_tqdm_counter` and verifier SHA256
`d324540ce3914bb666e48e50cc27d891050f2800e3743dedd485b9a7d37c3cb2`.
This is real post-resume advancement, not the command's3100000target.
