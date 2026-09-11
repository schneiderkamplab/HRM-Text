---
type: Runbook
title: XXL Restart from 520K
description: Preserved original trajectory and separate half-rate continuation before the sustained gradient instability.
tags: [training, stability, checkpoints, wandb]
status: draft
last_updated: 2026-09-10
confidence: high
---
# XXL Restart from 520K

User decision on 2026-09-10: stop the existing run after its next complete
ephemeral (532000), clone history through 520000, and branch from regular
step_520000. This supersedes the continued 531000 recovery attempt described
in [module learning rates](module-learning-rates.md).

The user explicitly corrected the proposed H LR to **3.75e-5**, not 3.75e-6.
L is **2.5e-5**; embeddings/head **7.5e-5**. These are half the rates used
from 500000, not half the fivefold-reduced rates used from 531000.
Clipping remains 1.0; optimizer, EMA, batch cursor, BP5, and all other training
settings are retained. This tests prevention from an earlier checkpoint,
not immediate recovery from the 530K sustained instability.

## Identities and Files

- Original run: `peter-sk-sdu/DFM5/40j5y877`; do not delete or rewrite it.
- New run: `peter-sk-sdu/DFM5/xxl-restart520k-20260910`.
- New display name: `dfm8-XXL restart520K half LR`.
- New checkpoint directory: `checkpoints/dfm10/XXL-from-520000-half-lr`.
- Preserved old stop checkpoint:
  `checkpoints/preserved/xxl_before_520k_branch_532000_20260910`.
- Clone snapshot/report: `logs/wandb_clones/xxl_restart520k_20260910`.
- Clone log: `logs/stability/clone_xxl_520k_20260910.log`.
- Stop log: `logs/stability/stop_xxl_532000_20260910.log`.
- New training log directory:
  `logs/training/dfm10_XXL_restart520k_half_lr/from_520000_to_550000`.

## Procedure and Safeguards

`scripts/stop_training_at_complete_checkpoint.py` validates complete DCP storage
ranges, preserves payloads using hardlinks, and signals only the verified
isolated torchrun process group. Scheduler stop is requested beforehand.

`scripts/clone_wandb_run_to_step.py` snapshots remote numeric training/evaluation
history through inclusive step 520000, retains original step and epoch values,
and logs to a fresh run. It rejects an existing destination, out-of-order history,
or a missing 520000 endpoint. Each metric is explicitly registered. The source
summary is deliberately not copied because it includes post-cutoff values.
Source artifacts/media remain on the original run; this clones numeric history
and configuration, not independent copies of every artifact. The local snapshot
and metric counts provide a verification basis. Training must wait for clone sync.

`scripts/branch_xxl_520k_scheduler.py` requires the completed clone report and
confirmed old training stop before changing the existing plan. It redirects
remaining 550K/600K/epoch-2 training, evaluation, export, merge, and average rows
to separate output paths and the new W&B identity, under one brief plan lock.
Completed/historical rows stay unchanged. The 550K training row resumes from
520000. It saves a pre-edit plan backup and leaves the scheduler paused so the
new run can be verified before resuming.

At initial documentation, the clone and stop watcher are in progress; a launch
or source snapshot alone is not confirmation that new training has resumed.

## Completed Handoff

The original run stopped after complete 532000 was preserved. The clone synced
102,849 rows covering 562 numeric metrics through exactly 520000. Remote
verification confirmed its last training point and all 741 values in the 500K
evaluation interval, including averages, matched the local source snapshot.

864 future plan rows were redirected; no future W&B metadata retained the old
run ID. The coordinator/worker restarted on the same plan. Training PID
1364556 resumed from 520000 under the new identity and was observed at 520015,
without out-of-order logging warnings. Local live journal:
`wandb/run-20260910_151316-xxl-restart520k-20260910/run-xxl-restart520k-20260910.wandb`.
The original 40j5y877 history/checkpoints remain unchanged.
