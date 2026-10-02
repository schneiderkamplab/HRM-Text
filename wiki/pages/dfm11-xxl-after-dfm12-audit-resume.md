---
type: Runbook
title: XXL Resume After DFM12 Audit
description: Deferred GPU-release handoff from complete step 650500 and approximate epoch-three ETA.
tags: [dfm11, dfm12, xxl, scheduler, resume, operations]
status: draft
last_updated: 2026-09-25
confidence: high
---
# XXL Resume After DFM12 Audit

User authorization: continue existing XXL training only after DFM12 auditing
finishes and releases GPUs. Tesla owns the GPU-release watcher. This task
prepared the hook and plan row; **no scheduler or training was started here**.

## Deferred Hook

Tesla invokes this only after audit completion, not during a transient idle gap:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python \
  /work/mimir/HRM-Text/scripts/resume_xxl_after_dfm12_audit.py \
  --start-after-gpu-release
```

The explicit start option is the watcher's audit-completion attestation. It
independently checks no GPU compute processes, eight GPUs with >=178000 MiB free
each, no existing scheduler/training process, complete unchanged checkpoint,
unchanged prepared row, and the exact captured stop request. It refuses a
changed/new user stop. The hook has a nonblocking exclusive lock and a one-shot
startup receipt. It never kills audit, evaluation or training processes.

It clears only the captured `stop.request` through the scheduler `clear-stop`
API, then starts the existing single-node runner detached with `start_new_session`,
the required hrm environment PATH, all eight GPUs and `--persistent-vllm`.
The plan lock protects row/stop validation. No new scheduler plan or training
configuration is created. Launch failure restores a soft stop through the API.

Environment correction, 2026-09-25: the CPU-only release watcher deliberately
has `CUDA_VISIBLE_DEVICES=''`. The scheduler child now explicitly receives
`CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`; inheriting the watcher's empty value is
unsafe. The watcher environment itself stays unchanged. A mocked launch
regression test checks the actual `Popen` environment without starting anything.
Parent must refresh Tesla's training-ready script hash pin after this change.

Plan remains:
`logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`.
Same monitor:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m eval_scheduler monitor \
  --plan-dir logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725
```

New runner log: `<PLAN>/runner-after-dfm12-audit.log`.
Startup PID receipt, only after invocation: `<PLAN>/resume-after-dfm12-audit/started.json`.
This file did not exist at handoff. Watcher arming is Tesla's responsibility;
preparing this script does not itself arm or run a watcher.

## Prepared State

Executed only:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/resume_xxl_after_dfm12_audit.py --prepare
```

Using `PlanLock`, `read_plan`, `Job.with_updates`, and `write_plan`, exactly one
of **10,097** rows changed: `dfm11-e3-train-700000`.

- Failed deliberate-stop attempt 1 becomes pending attempt 0.
- Resume tag, both metadata and explicit command: `ephemeral_step_650500`.
- Checkpoint root: `checkpoints/dfm11/XXL-from-dfm10-epoch2`.
- New attempt log directory:
  `logs/training/dfm11_XXL_epoch3/from_650500_to_700000_after_dfm12_audit`.
- LR remains `3e-4`, `lr_auto=true`; the completed 635K--650K piecewise ramp
  remains unchanged. GAS 8, fixed BP 8, activation checkpointing `none`, other
  geometry/optimizer settings, and epoch-three finalization are unchanged.
- Same W&B project `DFM5`, run `xxl-restart520k-20260910`.
- `stop.request` retained byte-for-byte. No stale PID or cluster snapshot was
  deleted, no attempts history was reset, and no unrelated plan row changed.

`<PLAN>/resume-after-dfm12-audit/` preserves the complete pre-edit plan, exact
soft-stop bytes, paused training log/process manifest, and `prepared.json`.
That receipt is the hook readiness signal. It captures checkpoint sidecar and
DCP metadata hashes, shard sizes, dependency state and guarded training settings.
DCP metadata storage offsets/lengths fit all referenced shard files; the sidecar
confirms step 650500, epoch 3, world size 8, GAS 8 and completed LR ramp.

The old log reached step 650555 before SIGTERM on 2026-09-24 12:40 CEST; the
latest complete checkpoint is 650500, so approximately 55 uncheckpointed steps
are intentionally replayed. Its process manifest records return code 1 and
completion at 12:40:21 CEST. Old logs remain unchanged.

## Dependency Caveat

The direct 650K campaign teardown and its terminal barrier are both `done`,
which satisfies the existing training-release dependency. This is **not** a
claim that every 650K evaluation succeeded: the campaign has 3 done, 1 failed,
283 pending and 3 skipped rows. HF export failed; downstream rows remain
blocked. Existing terminal-barrier semantics permitted training to continue
despite that failure. No evaluation repair or status relabeling was performed.

## Estimated ETA

These are **estimates**, not exact epoch-boundary predictions or wall-clock
dates. Source evidence: epoch-two sidecar step **628132**, latest checkpoint
step **650500**, and epoch-three row cursor **13,087,991 / 235,520,711 = 5.557%**.
Linear extrapolation of observed row progress gives an epoch-three endpoint
near **step 1,030,648**, approximately **380,148 steps remaining**.

Paused `to_700000/train_until_step_700000.log` timing windows:

- Step 650100 at elapsed 703 seconds to 650500 at 2957 seconds: **5.635 s/step**.
- Step 650300 at 1849 seconds to 650500 at 2957 seconds: **5.54 s/step**.

At that recent rate, the next 700K boundary is approximately **76--78 training
hours** after release (about 77 hours). The projected epoch boundary is
approximately **24.4--24.8 training days**, about **24.6 days**, after release.
Add audit wait, queued checkpoint evaluations, export/merge time, initialization,
checkpoint overhead and interruptions. Row packing, sequence lengths and speed
can vary; do not use the configured 1.1M-step progress-bar endpoint as the exact
epoch boundary. Refresh from new checkpoints once resumed.

## Verification

Five focused tests pass in `tests/test_resume_xxl_after_dfm12_audit.py`: scoped
resume change, settings-drift rejection, busy-GPU refusal without launch, and
refusal to reprepare a pending row, and GPU visibility restoration from a CPU-only
watcher. `git diff --check` passed. Direct comparison
of the before/after plans confirmed only the named row changed and the exact
stop bytes survived. Startup path was not executed on the live machine.

Related: [multi-node scheduler safety](model-architecture/multinode-eval-scheduler-plan.md),
[LR schedule context](model-architecture/module-learning-rates.md).
Parent owns shared index/status integration.
