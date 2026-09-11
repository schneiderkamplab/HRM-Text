---
type: Experiment Plan
title: Regularization Alternatives from the 453K Checkpoint
description: Candidate objectives, aggregation choices, and controls for isolated stability replays.
tags: [training, stability, experiments, regularization]
status: draft
last_updated: 2026-09-09
confidence: medium
---
# Regularization Alternatives from the 453K Checkpoint

Motivation: [completed layer diagnostics](mlp-energy-replay-layer-review.md)
showed improved L block-0 residual magnitude but persistent amplification and
worsening signals elsewhere. See [training stability](training-stability-jacobian-and-residual-scaling.md)
for the original experiments. These alternatives are recorded proposals, not
newly enabled training settings or scheduled runs.

## Candidate Objectives

### Completed Coefficient Comparison (2026-09-09)

The 1e-3 replay completed through 454000 and production automatically resumed
from 496500 with its original settings and W&B identity. At review it had
reached approximately 497955. The stronger coefficient did worse over the
1000-step replay: mean CE 5.404 versus 1.603 at 1e-4 and 2.817 baseline;
token accuracy 26.93% versus 69.49% and 55.51%; clipping 94.8% versus 49.2%
and 55.6%. Final-200-step mean CE was 5.514 versus 3.286 and 6.497.
Smaller late gradient magnitudes did not imply restored model performance.
Do not promote 1e-3 to production. Results are in
`checkpoints/experiments/xxl_mlp_energy_1e3_20260909/comparison.md`.
This is one replay per setting; the nested-RMS experiment remains pending
implementation and normalization validation, not running or enqueued.

### Other Objectives

| Candidate | Question | Main risk |
|---|---|---|
| Absolute MLP residual energy with fixed per-layer reference scales | Does bounding absolute output growth prevent redistribution to other blocks? | Useful large-scale representations may be suppressed. |
| Tail-emphasizing relative MLP energy | Does the average hide a few problematic layers, cycles, or tokens? | Outliers may dominate the objective. |
| Relative attention residual energy | Is an unpenalized attention branch contributing to instability? | May reduce useful attention output without addressing the cause. |
| Attention sigmoid-gate logit penalty | Does discouraging extreme gate logits improve stability? | Saturated output gates can be functional; they are not softmax probabilities. |
| Q/K magnitude penalty | Would constraining query/key scales reduce harmful attention-score extremes? | Existing aligned-QK proxies do not establish actual attention saturation. |
| Checkpoint-anchored parameter penalty | Does restricting drift from the 453K weights prevent bursts? | The anchor already has stability problems and may limit recovery. |

For fixed-reference MLP energy, collect incoming-stream reference energies on
a fixed calibration sample at 453K, apply a denominator floor, and freeze them
for the entire replay. Specify whether references are per physical block or
per block/cycle. This removes an adaptive denominator, not the need for careful
scale calibration. It is distinct from a penalty anchored to parameter values.

For parameter anchoring, specify tensor-size and scale normalization rather
than allowing large tensors to dominate accidentally. Attention-specific
objectives should follow actual bounded-sample attention entropy/probability
measurements. Do not label sigmoid-gate saturation as attention collapse.

## Alternatives to the Arithmetic Mean

Let z_i be a nonnegative relative energy:

`mean_hidden(MLP_residual**2) / max(stopgrad(mean_hidden(stream**2)), eps)`.

The current objective averages z over supervised tokens and over differentiable
blocks/cycles. It already emphasizes large amplitude ratios quadratically;
tail emphasis below is an additional change, not the first squaring.

| Aggregator | Definition | Gradient allocation / tradeoff |
|---|---|---|
| Maximum | `max(z)` | Strongest focus, but only maximizers receive direct penalty gradients; sensitive to noise and changes in the worst location. |
| Top-tail mean | Mean of the largest fixed fraction, e.g. 10% | Covers multiple offenders; tail membership changes discontinuously, and the other elements receive no direct penalty gradient. |
| Power mean, p > 1 | `(mean(z**p))**(1/p)` | Smooth positive-energy emphasis; p=2 is a moderate starting point and approaches maximum as p grows. Handle the all-zero case safely. |
| Normalized log-sum-exp | `tau * (logsumexp(z/tau) - log(N))` | Smooth maximum; small positive tau focuses on the worst values, large tau approaches the mean. Requires scale calibration and stable evaluation. |

The normalized log-sum-exp gives zero for all-zero input, returns c if every
input equals c, and has softmax-distributed gradients. It is not the same
objective as a softmax-weighted average of the values. Temperature must be
strictly positive. A raw percentile value is not a top-tail mean and gives
sparse gradient support around the quantile; it is not the preferred first test.

Replacing a mean with a sum does not change relative emphasis when the number
of elements is fixed: it only rescales the effective coefficient.

## Choose the Aggregation Axis Explicitly

1. First comparison: retain the masked token mean within each block/cycle, but
   replace the block/cycle mean by a p=2 power mean (RMS of block/cycle energies).
   This targets the observed localization without selecting individual noisy
   tokens. It can still hide rare token-level failures within a block.
2. Separately test a token top-tail mean or token power mean if diagnostics
   show rare-token failures. Avoid simultaneously changing both aggregation
   axes in the first comparison.
3. Compare a calibrated log-sum-exp over block/cycle energies as a stronger
   smooth alternative if p=2 is insufficient.

All of these still aggregate values; the distinction is arithmetic averaging
versus concentration on the upper tail. They do not directly constrain a
Jacobian or guarantee stable recurrence.

## Distributed and Experimental Controls

### Confirmed Next Aggregator (2026-09-09)

The user selected **RMS at both levels**, superseding the first-axis-only
recommendation above for the next experiment: compute per-block/cycle RMS
over token energies, then RMS over those block/cycle values, not an outer
arithmetic mean. With equal token weighting this equals
`sqrt(mean_layer_cycle_token(z**2))`. Keep the preserved 453000 starting point
and 454000 endpoint. This selection is recorded; implementation, distributed/GAS
normalization validation, coefficient selection, and actual launch remain
pending. Do not describe it as already running or as a scheduler-enqueued task.

### Controls

2026-09-09: [actual-update calibration](parameter-update-calibration.md) is
implemented and scheduled at the 498500 production checkpoint, before the RMS
replay. Its three short matched branches measure actual optimizer updates and
instrumentation parity, not the nested-RMS objective itself.

Nonlinear aggregation changes reduction semantics. A mean of rank-local or
microbatch-local power means is NOT the power mean of the global batch.
Define the intended rank/microbatch/token/layer grouping explicitly, preserve
correct gradient scaling, and test GAS/world-size parity if claiming a global
objective. Do not silently apply the current additive-loss normalization to a
non-additive objective. A global top-k additionally needs global selection;
per-rank top-k is a different objective.

Use the same preserved step_453000 model, optimizer/EMA, exact data cursor,
LR, BP schedule, and endpoint 454000. Start with each objective alone, not a
stack of changes. Calibrate coefficients using matched auxiliary/CE gradient
norms on several fixed batches, not merely scalar loss magnitude or the same
numeric coefficient across objectives. Keep identical probe schedules and
record overhead separately. Preserve all checkpoints; disable experimental
W&B logging and recover production from its own checkpoint afterward.

Finish the existing higher-coefficient relative-energy replay first. Proposed
next priorities are fixed-reference absolute MLP energy and the p=2 block/cycle
power mean. Add a small fixed held-out CE evaluation to distinguish improved
stability from suppressed learning. A repeated baseline estimates trajectory
variation before interpreting modest improvements. One short 453K replay tests
recovery from an already problematic state, not prevention or long-run quality.
