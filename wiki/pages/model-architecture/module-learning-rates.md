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

## Main Merge Schedule Compatibility (2026-09-15)

Merged origin/main through `fc35d95` with the local cosine/rewarm changes.
Both row-cursor epoch cooldown and step-based decay/rewarm are retained.
`PretrainConfig` rejects combining `lr_cooldown_checkpoint` with rewarm or
explicit step-decay bounds, rather than silently ignoring a requested schedule.
Null row cooldown preserves the existing step-based training schedule.
Both branches' operational notes below are retained; their XXL and XXL-wide
campaigns are distinct. The merge did not restart training or edit plans.

## Existing-Log Uncertainty Analysis (2026-09-15)

Follow-up: `--window-steps 10000 --trend-window-steps 20000 --block-steps 500`
adds a trailing 20K OLS slope at each complete 10K endpoint, with
Bartlett/Newey-West HAC standard errors and normal-approximation intervals.
Slope units are change per 10K steps (accuracy displayed in percentage points).
The lag bandwidth uses `--block-steps`, independently of the reporting/trend
window lengths. Holm correction jointly covers 93 adjacent metric comparisons
and 93 trend tests. Overlapping trend windows are not independent.

The full 32-row table through 320K and machine-readable results are in
`docs/xxl-wide-training-10k-trends.{md,json}`. Latest loaded history was 322155;
the incomplete 320--330K reporting window is deliberately excluded.
For 300--320K, per-10K slopes are loss -0.004361 (95% interval
[-0.007908, -0.000814]), token accuracy +0.0761 pp ([+0.0143, +0.1379]),
and exact accuracy +0.2562 pp ([+0.1712, +0.3413]). Only exact accuracy
survives joint full-report correction (adjusted p about 5.13e-7); adjusted
p for loss and token accuracy is about 0.614. The marginal intervals and
adjusted tests answer different questions. All three 280--300K trends survive.
These are conditional exploratory log trends, not held-out or causal evidence;
HAC cannot repair misspecified linear trends across spikes and phase changes.
Seven tests pass, including trend units and correlated-noise uncertainty.

`scripts/analyze_training_log_uncertainty.py` accepts quoted globs for local
W&B event files or JSONL history rows. It replaces duplicate global steps
with the last complete metric row in sorted file order, retains loss spikes,
and fails on nonfinite metric values rather than dropping them. No remote
API calls, held-out evaluations, GPU work or W&B writes are performed.

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python scripts/analyze_training_log_uncertainty.py \
  'wandb/run-*-dfm10-xxl-wide/run-*.wandb' \
  --window-steps 5000 --block-steps 500 --draws 10000 \
  --output docs/xxl-wide-training-uncertainty-block500
```

Window size is configurable. Alternatively, `--ranges 300000:305000
315000:320000` compares explicit non-overlapping intervals, start exclusive
and end inclusive. Default automatic windows omit the unfinished final
window. `--block-steps` controls dependence blocks separately from window
size; the circular block bootstrap converts it to observation counts using
median logging cadence. Reports expose coverage/gaps and BP ranges; JSON
also records observed LR ranges. Inputs must describe the same training run.

Full-history outputs are `docs/xxl-wide-training-uncertainty{,-block500}.{md,json}`:
64 complete 5K windows through 320K, 189 adjacent-window metric comparisons.
100-step versus 500-step blocks detected 60 versus 59 improvements after
Holm adjustment across each report's 189 tests. With 500-step blocks, counts
by destination range were 31 (<=100K), 6 (100--150K), 5 (150--200K),
9 (200--250K), 8 (250--300K), and zero (300--320K).

The exploratory longer-gap comparison, saved as
`docs/xxl-wide-training-uncertainty-recent.{md,json}`, compares 300--305K
with 315--320K. Loss difference was -0.008164 (marginal 95% interval
[-0.013566, -0.002889]), token accuracy +0.1395 percentage points
([+0.0482, +0.2318]), exact accuracy +0.3838 pp ([+0.2313, +0.5328]).
All three pass adjustment within that three-test report, but this post-hoc
comparison is NOT protected against selection across previous monitoring
or all alternative intervals. It supports cautious descriptive evidence of
small cumulative progress, not a confirmatory generalization claim.

Assumptions/limits: step-weighted logged means, different batches and changing
weights, approximately stationary local dependence. Strong learning trends,
BP/LR transitions and spikes violate stationarity; intervals in those windows
are descriptive, not calibrated certainty. Independent bootstrapping of the
two windows does not capture cross-boundary covariance. Holm cannot repair
those assumptions or repeated peeking. 100/500-step sensitivity is not proof
that longer-range correlation is absent. Five tests passed, covering block
means, correlated-series uncertainty, reproducibility, Holm, and configurable
CLI windows/ranges. Current training and scheduler were not changed.

## Resume-Relative Rewarm (2026-09-15)

Prepared, not enabled in the current scheduler. `lr_rewarm_steps=0` disables
the feature and preserves existing schedules. For a new DFM11 stage that
rewarm-scales the base from 3.75e-5 to 7.5e-5 over 2000 optimizer steps:

```bash
lr=7.5e-5 lr_auto=true \
lr_embeddings=null lr_head=null lr_h=null lr_l=null \
lr_rewarm_steps=2000 lr_rewarm_start_ratio=0.5 \
lr_rewarm_start_step=null lr_min_ratio=1 \
lr_decay_start_step=null lr_decay_end_step=null
```

This is only the LR portion of a future resume command, not a full training
launch. On first use with an older checkpoint, the anchor resolves to the
loaded global step. Linear rewarm begins at `lr * lr_rewarm_start_ratio`,
reaches `lr` after the requested steps, then holds. At BP8/H2/L3 all effective
module rates follow that same multiplier. Explicit module overrides still
win. This feature neither resets optimizer/EMA nor modifies BP warmup or
dataset epoch offsets; these must be configured separately for continuation.

Every new checkpoint sidecar stores `lr_rewarm` with its anchor, duration,
starting ratio and base LR. Resuming with the same rewarm configuration and
a null anchor restores that anchor, even after the rewarm has finished. It
does not restart the ramp at every scheduled segment or interruption. To
deliberately start another rewarm from a later checkpoint that already has
rewarm metadata, supply a new explicit `lr_rewarm_start_step`. Conflicting
saved settings fail unless an explicit anchor is supplied. Old sidecars
without rewarm metadata require an explicit anchor if a previous rewarm
must be reconstructed rather than initiated at the loaded checkpoint.

Rewarm requires a checkpoint resume. It supersedes the original global-step
`lr_warmup_steps` schedule. An optional subsequent explicit cosine window is
supported only when its start is at/after rewarm completion. Stale/overlapping
or incomplete decay bounds fail; without explicit decay, `lr_min_ratio=1`
is required. Thus copied prior cooldown arguments cannot silently suppress
rewarm or trigger another decay.

Implementation is isolated in `models/lr_rewarm.py`, with checkpoint binding,
sidecar persistence, and dispatch in `pretrain.py`. Fourteen rewarm tests
passed, including real PretrainConfig defaults, actual sidecar roundtrip,
restart mid-ramp/after-ramp, update_lr integration, auto scaling, and cosine
handoff; the 31 module-LR tests also passed. No GPU training or W&B logging
was launched. Distributed resume performance was not benchmarked.

## BP8 Throughput Check (2026-09-14)

Observed BP8/GAS8 throughput is about 5.2--5.3 seconds/update with device
usage 133--136 GiB (snapshot, not peak). This supersedes the ramp note's
unmeasured-fit status for GAS8 only. GAS4 at unchanged global batch remains
untested at BP8; a same-checkpoint, no-W&B timing/memory/parity replay is the
recommended first throughput experiment, not a production change. Details
and the independent recurrent-level wrapping candidate are in `docs/optimize.md`.

## Epoch-End Cosine Cooldown from 600K (2026-09-13)

Supersedes constant LR for the final scheduled epoch-2 segment. Its command
keeps `lr=7.5e-5 lr_auto=true`, sets `lr_min_ratio=0.5`, and adds
`lr_cooldown_checkpoint=checkpoints/dfm10/XXL-from-520000-half-lr/checkpoint_state_step_600000.json`.
BP8/GAS8 and other training/evaluation settings are unchanged. Only the pending
`campaign-dfm10-finish-epoch2` command was edited under PlanLock with a backup.

`models/epoch_lr_cooldown.py` implements the optional schedule. The 600K
checkpoint supplies the starting global row cursor; the sampled epoch's
index-array length supplies the end. Base LR is multiplied by
`0.5 + 0.25 * (1 + cos(pi * progress))`, where progress is the fraction of
remaining epoch rows consumed. This is cosine in dataset progress, not in an
estimated step count: it does not assume the 630K safety limit is the actual
epoch boundary. At the anchor the multiplier is 1; at the end it is 0.5.
The final optimizer update may precede the final row slightly if a partial
GAS group is dropped, so its LR approaches the floor rather than guaranteeing
that a particular numbered step equals it. No dataloader behavior was changed.

At BP8, base/embedding/head LR goes from 7.5e-5 to 3.75e-5, H from
3.75e-5 to 1.875e-5, and L from 1.25e-5 to 6.25e-6. Preserve the same
anchor option on intermediate resumes; the original regular 600K metadata
must remain available. A missing cursor, mismatched dataset or resume before
the anchor fails rather than silently restarting decay. Default null preserves
the original step-based LR schedule. Current training was not interrupted.

## Scheduled BP6/7/8 Ramp (2026-09-11)

Supersedes the two-segment schedule below. The existing XXL plan now has:

| Resume | Stop | Fixed BP | GAS | Auto H LR | Auto L LR |
|---|---|---:|---:|---:|---:|
| step_550000 | step_575000 | 6 | 8 | 3.75e-5 | 1.875e-5 |
| step_575000 | step_600000 | 7 | 8 | 3.75e-5 | 1.5e-5 |
| step_600000 | epoch_2 (630K upper stop) | 8 | 8 | 3.75e-5 | 1.25e-5 |

Each uses equal BP min/max, nonzero warmup ratio 0.2, base `lr=7.5e-5`,
`lr_auto=true`, no module overrides, and unchanged 262144-token global batch.
The first waits for the existing 550K eval teardown; the second requires the
first training row to succeed. Existing 600K evaluations and the final epoch
evaluation are retained; no 575K eval was added. `stop_after_step=575000`
saves a regular checkpoint even though 575K is not a 10K checkpoint boundary.
Current training and all unrelated rows were left unchanged under PlanLock;
backup: `plan.tsv.before_bp_ramp_*` beside the existing plan.

The current checkpoint metadata contains a global row cursor and no carry.
GAS8 changes local microbatch tokens from 8192 to 4096; resume must select
`row_cursor` mode to preserve dataset position. The future 550K checkpoint
must retain that metadata. Full GPU memory and stability at BP6/7/8 are not
yet measured; GAS8 is a memory precaution, not a guarantee of fit.

Launch preflight exposed a bug in pulled main `c1fbfd0`: auto LR indexed
`config.arch` as a dictionary, but `PretrainConfig` supplies `ArchConfig`.
The helper now normalizes Pydantic architecture configs with `model_dump()`
while still accepting dictionaries; regression tests cover BP6/7/8.

## Future XXL Segments Use Auto Rates (2026-09-11)

After fast-forwarding main to `c1fbfd0`, the existing plan
`logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`
was updated in one short PlanLock transaction. Only the pending
`campaign-dfm10-train-600000` and `campaign-dfm10-finish-epoch2` command
fields changed. They now specify `lr=7.5e-5 lr_auto=true`, with no explicit
H/L/embedding/head overrides. The running 520K-to-550K row is unchanged.
At BP5 (two H and three L backward calls), derived rates match the current
explicit rates: H 3.75e-5, L 2.5e-5, embeddings/head 7.5e-5. Checkpoint,
W&B, resume, clipping and other settings were preserved. A timestamped
`plan.tsv.before_lr_auto_*` backup resides beside the plan.

## Automatic Backward-Count Scaling (2026-09-11)

Auto scaling defaults to `lr_auto=true`. Explicit `lr_embeddings`, `lr_head`, `lr_h`, and
`lr_l` values always win (including zero). Auto fills only null values; with
auto off, null values inherit the base LR. This supersedes the initial
same-day implementation that rejected explicit overrides with auto enabled.
At the user's subsequent request on 2026-09-11, true replaced the initial
false default in both Hydra config and the training schema. Use
`lr_auto=false` for legacy uniform-LR behavior. Future launches with unset
module rates now use auto scaling; the running process and scheduler command
strings were not changed. Explicit module rates remain authoritative.

For `baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel`, use the
current step's `bp_steps` to count gradient-bearing calls:

```text
H_backward = min(H_cycles, bp_steps - 1)
L_backward = min(H_cycles * L_cycles, bp_steps - H_backward)
embedding_lr = head_lr = scheduled_base_lr
H_lr = scheduled_base_lr / H_backward
L_lr = scheduled_base_lr / L_backward
```

The L count is capped at the actual number of recurrent calls. Positive
cycle counts and BP >= 2 are required. Unsupported architectures fail rather
than silently using these semantics. No-grad forward calls, activation
checkpoint recomputation, and gradient accumulation microbatches are not
additional divisors. This counts gradient-bearing uses per recurrent block,
not its number of transformer layers. AdamATan2 normalizes gradients, so this
is an explicit LR heuristic, not a proof of equal parameter update norms.

Ratios refresh before each optimizer update when BP changes, including the
first update after resume. They retain the single checkpoint optimizer group
and existing moments/EMA. Compiled optimizer graphs may recompile at BP
transitions. Effective-rate logs use the same BP value as training and inherit
warmup/cosine scaling. With H=2, L=3 and lr=3e-4, BP5 gives H=1.5e-4 and
L=1e-4; BP8 gives H=1.5e-4 and L=5e-5. Embeddings/head remain 3e-4 before
any common schedule multiplier.

Validation: 21 module-LR tests passed, including explicit-over-auto precedence,
auto-off inheritance, zero overrides, and actual HRM backward hooks
with lightweight replacement blocks across cycle/BP combinations, compiled
optimizer BP-transition parity, schedule scaling, and legacy checkpoint
restoration. No distributed GPU smoke or W&B logging was performed.

## Merged Implementation (2026-09-11)

### Scheduled Cosine Cooldown (2026-09-11)

Verified completion, 2026-09-15: supersedes the pending-handoff status in
the historical scheduling notes below. The 275K and 320K handoffs completed;
the current segment resumed from `step_320000`. At logged step 327095,
BP8 rates were embeddings/head 3.75e-5, H 1.875e-5, and L 6.25e-6,
confirming completion of the 320K--325K cosine and retention of its floor.
Before committing these changes, the combined module-LR, rewarm and
training-log analysis suites passed all 52 tests. No training was interrupted
and no scheduler configuration changed during this commit preparation.

Third cooldown scheduled 2026-09-15: at the completed regular `step_320000`
checkpoint, restart with `lr=7.5e-5 lr_auto=true lr_min_ratio=0.5
lr_decay_start_step=320000 lr_decay_end_step=325000`. At BP8 the final rates
are embeddings/head 3.75e-5, H 1.875e-5, L 6.25e-6, held through epoch end.
Only the 350K-target and final training rows are updated. The parameterized
`scripts/handoff_xxl_wide_cosine_275k.py` handles the safe handoff; output is
`logs/scheduler/dfm10_XL_epoch9_20260831/cosine_320k_handoff.log`.
320K is a regular checkpoint boundary, so no ephemeral tag is published there;
the watcher explicitly uses `--checkpoint-tag step_320000`. Its initial
ephemeral-tag watcher was stopped and corrected before reaching the boundary.
This is a scheduled transition, not yet a verified completed handoff.

Second cooldown requested 2026-09-13: supersedes the constant floor after
275K. `scripts/handoff_xxl_wide_cosine_275k.py` waits for complete
`ephemeral_step_275000` (sidecar plus DCP storage extents), stops only the
captured XXL-wide torchrun group, waits for the soft-stopped scheduler to exit,
then resets the active 300K-target row to resume that checkpoint. It restarts
the persistent scheduler without resetting any evaluation results. Its log is
`logs/scheduler/dfm10_XL_epoch9_20260831/cosine_275k_handoff.log`.

The 300K, 350K, and final training rows use `lr=1.5e-4 lr_auto=true
lr_min_ratio=0.5 lr_decay_start_step=275000 lr_decay_end_step=300000`.
The currently running process retains its previous settings until the handoff.
At BP8, embedding/head LR falls from 1.5e-4 to 7.5e-5, H from 7.5e-5 to
3.75e-5, and L from 2.5e-5 to 1.25e-5. The new floor is held beyond 300K.
Plan backup: `plan.tsv.before_cosine_275k_300k`. This records scheduling,
not confirmation that the future handoff completed.

Production startup correction: the 200K resume failed before training because
auto LR indexed a Pydantic `ArchConfig` as a dictionary. Earlier tests used
dictionary fixtures and missed this integration error. The helper now converts
Pydantic architecture configs with `model_dump`; a regression test uses the
actual `pretrain.ArchConfig`, including optimizer scale initialization.
All 31 tests passed. Only failed row `xxlw-train-250000` was reset, retaining
the completed 200K checkpoint/evaluations and all cooldown settings.

Supersedes the constant-rate rollout below after 200K: all four pending
XXL-wide training segments now specify `lr=3e-4 lr_auto=true lr_min_ratio=0.5
lr_decay_start_step=200000 lr_decay_end_step=250000`. The optional absolute
step window replaces the original warmup/whole-run decay schedule when set;
before its start LR stays at base, and after its end it stays at the floor.
Both bounds must be supplied with start < end. Null bounds retain the old
schedule. It does not change total steps, BP warmup, optimizer state, or EMA.

At BP8/H2/L3, base/embedding/head rates are 3e-4 at 200K, 2.25e-4 at 225K,
and 1.5e-4 at 250K. H goes from 1.5e-4 to 7.5e-5 and L from 5e-5 to
2.5e-5. All stay at those floors in subsequent segments. The current
150K-to-200K segment remains untouched. Plan edits used PlanLock and backup
`plan.tsv.before_cosine_200k_250k_20260911`.

Thirty module-LR tests pass, including cosine endpoints, midpoint, floor
clamping, invalid bounds, and propagation to auto H/L rates. No GPU training
or W&B logging was launched during these tests.

Scheduled rollout on 2026-09-11: the four pending XXL-wide training segments
resuming from 200000, 250000, 300000, and 350000 in
`logs/scheduler/dfm10_XL_epoch9_20260831/plan.tsv` now use `lr=3e-4
lr_auto=true`, with all four explicit module LR arguments removed. This
supersedes their earlier fixed-override command configuration. At their BP8,
H=2, L=3 settings the effective rates are unchanged: embeddings/head 3e-4,
H 1.5e-4, L 5e-5. The base `train/lr` metric will change from 2e-4 to 3e-4;
the module LR metrics remain comparable. The active 150K-to-200K command and
all non-target rows were verified unchanged. Editing used PlanLock with a
backup `plan.tsv.before_auto_lr_from_200k_20260911` alongside the plan.

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
