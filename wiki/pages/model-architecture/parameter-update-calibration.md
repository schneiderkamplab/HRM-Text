---
type: Experiment Plan
title: Actual AdamATan2 Update Calibration
description: Default-off parameter-update measurements and matched short replays before a nested RMS objective.
tags: [training, stability, diagnostics, experiments]
status: draft
last_updated: 2026-09-09
confidence: high
---
# Actual AdamATan2 Update Calibration

This follows the [regularization replay review](mlp-energy-replay-layer-review.md)
and precedes the [nested RMS experiment](mlp-energy-regularization-experiments.md).
Raw auxiliary gradient magnitude alone does not characterize AdamATan2 updates.

## Implementation

`+experiment_update_probe_interval=N` enables CPU snapshots of local parameter
shards immediately before the real optimizer step. Default zero does not
allocate snapshots or perform additional collectives. It requires
`+experiment_metrics_output=...`; output is a rank-zero-only
`<output>.updates.jsonl` file, never a new W&B metric.

Each named parameter tensor records pre/post weight RMS, actual update RMS,
and update/weight norm ratio. Updates include decoupled weight decay and are
measured after clipping/skip decisions. Skipped optimizer steps have zero
updates. Global squared sums and element counts are reduced before calculating
RMS. Replicated copies cancel in these ratios. No full parameters are gathered
on GPU. CPU copies and synchronization have overhead when enabled.

These are per-parameter, hence physical-layer measurements. A shared parameter
has one optimizer update, not a separate update for each recurrent cycle.
This does not attribute updates independently to CE, regularization, and decay.

## Scheduled Short Comparison

Supervisor launched on 2026-09-09, waiting for fully written production
`ephemeral_step_498500`. Production was still running when scheduled.

- Archive: `checkpoints/experiments/xxl_update_calibration_20260909`.
- Supervisor log: `logs/stability/xxl_update_calibration_20260909_supervisor.log`.
- Three branches start from the preserved shared `step_453000` and end at
  `step_453010`: zero-penalty control with only the final update measured;
  zero-penalty baseline measured every step; mean-energy `1e-4` measured every step.
- All use full eight-GPU XXL, original optimizer/EMA and batch cursor, disabled
  W&B, separate checkpoints, and no shadow-gradient/layer probes.
- The supervisor validates and preserves 498500 before stopping production,
  and resumes production from that checkpoint with its existing output path,
  settings, and `DFM5/40j5y877` identity after success or ordinary failure.
- Each short branch has a 30-minute timeout. Machine loss or SIGKILL still
  requires manual recovery using the archived production command.
- `update_comparison.md` is generated after all branches finish. No results
  were available when this entry was written.

CPU tests verify bitwise unchanged weights, gradients, optimizer moments, EMA,
and RNG across three steps with measurement enabled. The related 29-test suite
passed. Full-scale numerical/control results remain pending; comparison of
summary statistics is not a full bitwise checkpoint comparison.

Nested RMS is not yet enabled or launched. Its global GAS/rank normalization
and coefficient calibration remain separate prerequisites; the short update
comparison must not be described as the RMS replay.

## Completed Comparison (2026-09-09)

All three branches completed and production resumed automatically from 498500
(PID 3081123), subsequently observed at 499290. Experimental checkpoints and
`update_comparison.md` remain in the archive; no experimental W&B logging.

The largest observed update/weight ratio was about 0.154% in the baseline
(H block-2 MLP down projection), versus 0.425% with the mean-energy 1e-4
penalty (L block-0 attention output projection). This is not evidence that
the penalty universally reduces adaptive updates.

The two zero-penalty controls were not numerically identical: final-step
maximum absolute differences were 1.17e-5 in weight RMS, 5.66e-6 in update
RMS, and 2.66e-4 in update/weight ratio. CPU parity passed, but full-scale
parity cannot be claimed. Investigate replay variation versus measurement
effects before interpreting smaller between-objective differences. Nested
RMS remains unlaunched.

## Production LR After 500K (2026-09-09)

Superseded later on 2026-09-09 by [module-specific rates](module-learning-rates.md):
H 7.5e-5, L 5e-5, embeddings/head 1.5e-4. The uniform change below records the
earlier decision, not the current pending training commands.

By user request, the existing scheduler plan now uses `lr=1e-4` for the
500000-to-550000, 550000-to-600000, and final epoch-2 training segments,
superseding `1.5e-4` from this boundary onward. The first resumes from
`step_500000`. `lr_min_ratio=1`, clipping 1.0, optimizer/EMA state, and W&B
`DFM5/40j5y877` are unchanged. The edit was performed under the plan lock;
ongoing 500K evaluations and historical commands were not modified.

Recovery caveat: the manual plan lock coincided with coordinator request
timeouts and worker heartbeat fencing during the 500K evals. The worker
exited and its unfinished jobs returned to pending. Avoid holding the plan
lock across interactive tool round trips on a live cluster: use one short
locked read-modify-write transaction. GPU worker recovery uses the existing
coordinator/plan and preserves completed results; do not start an independent
training process while that coordinator is scheduling evaluations.
