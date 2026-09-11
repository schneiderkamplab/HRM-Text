---
type: Technical Reference
title: H and L Learning Rates
description: Optional per-module AdamATan2 rates with unchanged checkpoint parameter groups.
tags: [training, optimizer, stability, learning-rate]
status: stable
last_updated: 2026-09-11
confidence: high
---
# H and L Learning Rates

## Merged Implementation (2026-09-11)

Supersedes the selective-port recommendation below: at the user's request,
the complete `origin/lr` branch was merged into main, including its other
changes and pinned submodules. Local experimental diagnostics were preserved.
AdamATan2 now uses the branch's fixed `parameter_lr_scales` mapping; the old
per-step `parameter_lrs` mechanism is superseded. Rates are rebuilt from run
config on initialization, not stored in optimizer checkpoint groups.

Canonical metrics are `train/lr_h`, `train/lr_l`, `train/lr_embeddings`, and
`train/lr_head`. The old `train/lr_H`, `train/lr_L`, and
`train/lr_embedding_head` names are deprecated compatibility aliases, not
additional optimizer settings. The combined embedding/head alias is emitted
only when those two actual rates agree. Uniform runs without overrides still
emit only the existing base `train/lr` metric. No per-step deprecation warnings
are emitted. Existing running training was not restarted.

## Pending Training-Code Review (2026-09-11)

Superseded later on 2026-09-11: regularization and its auxiliary-gradient
comparison were removed. Only default-off observational diagnostics were
retained and committed; see [update diagnostics](parameter-update-calibration.md).

The separate, uncommitted diagnostics/MLP-energy changes default to disabled:
`mlp_relative_energy_weight=0`, `experiment_metrics_output=null`,
`experiment_update_probe_interval=0`, and empty `experiment_gradient_probe_steps`.
Inspection finds unchanged tensor/loss operations in that path, with no added
probe collectives, CPU weight snapshots, timing synchronizations, or file writes.
Python conditionals, an empty energy-term list, and helper imports remain;
this is not a claim of literally zero overhead. Existing CPU tests cover block
gradient parity, unchanged CE, and probe state/RNG preservation, but do not
constitute a full eight-GPU disabled-versus-prepatch training parity test.
Training changes, their two model helpers, and their directly dependent tests
were intentionally excluded from the support-scripts/documentation commit.

## Review of origin/lr (2026-09-11)

Fetched `origin/lr` at `044eb5e`; module LR implementation is commit
`e40cbcd`. No production code was replaced during this review.
The branch uses fixed per-parameter ratios, constructed after distributed
wrapping, multiplied by the scheduled optimizer-group LR. It preserves the
single checkpoint parameter group and moment/EMA state, and applies the scaled
rate to both weight decay and adaptive updates. It adds separate optional
`lr_embeddings` and `lr_head`, defaulting to base `lr`. Existing `lr_h`/`lr_l`
commands therefore retain their intended rates. The default uniform path
remains optional, with no scale map when all overrides are null.

Recommended reconciliation: adopt this implementation rather than maintaining
two LR mechanisms, but preserve existing logging aliases `train/lr_H` and
`train/lr_L` alongside the branch's lowercase keys. Preserve
`train/lr_embedding_head` only when embedding and head rates agree; otherwise
log the separate rates without a misleading combined value. The branch alone
does not preserve those historical metric names. Port only the LR changes,
not the unrelated dataset/scheduler/submodule changes also on the branch, and
retain the local experimental diagnostics. Replace the old runtime-map tests
with the branch tests plus logging compatibility and existing-run-rate tests.

Verified directly against fetched branch source in an isolated Python process:
five CPU checks passed (ordinary and DCP optimizer-state restoration parity,
default/mapping validation, scheduled metrics, compiled optimizer versus eager
parity). No GPU smoke or production restart was performed. Fixed ratios and
scheduled-rate multiplication can differ in floating-point rounding from the
old absolute-rate calculation, so this is intended-rate equivalence, not a
claim of bitwise-identical full training trajectories. Scaling only base `lr`
in a resume command does not halve explicit module rates: scale every explicit
rate too, or add a separately specified global multiplier in future work.

## Historical Local Implementation (Superseded 2026-09-11)

`lr_h` and `lr_l` default to null (use the base `lr`). If either is set,
the scheduler applies the same warmup/cosine factor to each configured rate.
Embeddings and the output head use `lr`. Unknown parameter names fail closed.
The classification accepts wrapper prefixes and matches complete H_level,
L_level, embed_tokens, and lm_head path components.

`models/module_learning_rates.py` builds runtime parameter-to-LR overrides.
AdamATan2 uses them for both adaptive updates and decoupled weight decay.
Moment, EMA, gradient scaling, clipping, and forward/backward logic are unchanged.
The optimizer keeps its original parameter groups: checkpoint loading does not
need group splitting or moment remapping. Overrides are runtime config, not
optimizer state, and are reapplied each step after checkpoint loading. Resuming
requires retaining the LR config fields in the command/config, as with base LR.

Actual rates are logged as `train/lr_H`, `train/lr_L`, and
`train/lr_embedding_head`. The existing `train/lr` remains the scheduled base LR.

## XXL After 500K

User decision on 2026-09-09, superseding the previously scheduled uniform 1e-4:

| Parameters | Rate |
|---|---:|
| H module | 7.5e-5 |
| L module | 5e-5 |
| Embeddings and output head | 1.5e-4 |

The pending 500K-to-550K, 550K-to-600K, and final epoch-2 rows in
`logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725/plan.tsv`
use `lr=1.5e-4 lr_h=7.5e-5 lr_l=5e-5 lr_min_ratio=1`.
Resume begins at step_500000, preserving optimizer/EMA and W&B DFM5/40j5y877.
The edit used one short locked transaction; evaluations were not interrupted.

BP remains 5, not 8: two differentiable H cycles and three differentiable L
cycles. There are six L forward cycles, of which the first three are no-grad.
The LR ratio is a stability experiment, not an exact correction for cycle count.

## Verification

CPU tests cover exact equality to separate optimizer-group updates, including
weight decay/moments/EMA, old single-group state loading, schedule scaling,
unknown-name rejection, and DCP optimizer round-trip. Existing update-probe and
regularization tests also pass. All 290 named parameter tensors in the recorded
XXL probe are classified (144 H, 144 L, embeddings and head).
No new full eight-GPU training smoke was run while evaluations occupied GPUs.

## Early Production Observation

2026-09-09: after an initially unclipped phase, gradient bursts returned by
504K with the module-specific rates. Local history through 504870 shows
maximum pre-clipping norm 82.08 at 504325. Latest 500-step logged samples:
median norm 0.550, maximum 17.26, 32% clipped; mean CE 0.933 and token accuracy
78.40% remain intact. No nonfinite values were observed. Thus lower H/L rates
have not eliminated gradient bursts, although loss collapse is not observed
in this window. Metrics are sampled every five steps, not a full-step audit.

## Fivefold Reduction from 531000 (2026-09-10)

Supersedes the above rates from the resumed 531000 checkpoint onward:
`lr=3e-5 lr_h=1.5e-5 lr_l=1e-5`. All remaining scheduled training segments
use these values; clipping remains 1.0, with no optimizer/EMA reset and the
same DFM5/40j5y877 run. Sustained gradient bursts returned near 530K
(90% of logged samples clipped in a 500-step window), motivating this
containment test. Lower LR does not directly eliminate backward amplification.

The latest completed ephemeral at intervention was 531000; it was validated
against DCP metadata storage ranges and hardlinked into
`checkpoints/preserved/xxl_lr_reduction_531000_20260910` before interrupting
the exact production process group. The partially trained steps after 531000
are replayed. The existing plan's 550K training row was reset, not duplicated;
resume source is ephemeral_step_531000 and target remains 550000. Existing
W&B history ahead of the restored step can temporarily reject repeated logs.

New training log:
`logs/training/dfm10_XXL_epoch2_from_dfm8_epoch1/from_531000_to_550000_lr_div5/train_until_step_550000.log`.
Coordinator and worker were restarted on the same plan; training launch PID
1317520 has the verified reduced-rate arguments. Early stability assessment
must wait for new updates; process launch alone does not demonstrate recovery.
