---
type: Technical Reference
title: Training Stability, Jacobian Growth, and Residual Scaling
description: Recurrent-depth stability diagnosis, mitigation options, and opt-in instrumentation for HRM-Text.
tags: [training, stability, gradients, jacobian, residual-scaling, recurrence]
status: draft
last_updated: 2026-09-07
confidence: medium
---
# Training Stability, Jacobian Growth, and Residual Scaling

This page separates the architectural hypothesis behind the observed XXL
gradient bursts from the operational safeguards already in use. The detailed
run chronology remains in [DFM8 XXL to DFM10 Multi-Node
Transition](/pages/model-architecture/dfm8-xxl-to-dfm10-multinode-transition.md),
and current clipping and skip semantics remain in [Optional Global Gradient
Clipping](/pages/model-architecture/gradient-clipping.md).

The Jacobian-growth explanation is plausible but not yet proven. Gradient
clipping has established that very large pre-clipping norms occur, but a global
norm alone cannot identify where amplification begins. The opt-in diagnostics
described below were added to answer that question before changing the model.

## Effective Depth in the Current XXL HRM

The XXL architecture declares 72 layers and `half_layers: true`. The model
therefore constructs 36 physical transformer blocks in each of the shared H and
L recurrent cores. With `H_cycles=2` and `L_cycles=3`, one forward pass applies:

| Path | Physical blocks | Recurrent applications | Block applications |
|---|---:|---:|---:|
| H | 36 | 2 | 72 |
| L | 36 | 6 | 216 |
| Full forward | - | - | 288 |

Only the final recurrent applications are differentiable according to
`bp_steps`. The longest direct backward path is approximately:

| `bp_steps` | Differentiable H applications | Differentiable L applications | Approximate block depth |
|---:|---:|---:|---:|
| 3 | 2 | 1 | 108 |
| 4 | 2 | 2 | 144 |
| 5 | 2 | 3 | 180 |

This is unfolded execution depth, not parameter count. The same physical
weights recur at different cycle positions, so their gradients combine
contributions from several effective depths. That sharing can make a physical
layer's parameter-gradient norm large without identifying which recurrent use
caused the amplification.

## Current Residual and Injection Equations

For pre-norm blocks, the implementation is equivalent to:

```text
x_attn = x + Attention(RMSNorm(x))
x_out  = x_attn + MLP(RMSNorm(x_attn))
```

At every recurrent application, the H or L state is first combined with an
unscaled injection:

```text
state_out = Core(state + injection)
```

There are therefore two additive residual branches per transformer block plus
one additive state injection per recurrent core application. None has an
explicit depth-aware scale or gate. Pre-normalization stabilizes each branch's
input distribution but does not force the residual branch Jacobian to be small.

## Why Jacobian Growth Is a Credible Hypothesis

For a residual map `y = x + F(x)`, backpropagation multiplies by
`I + J_F`. Along an unfolded path, the gradient contains a product resembling:

```text
product_t (I + J_t)
```

If the dominant singular value is only modestly above one at enough recurrent
uses, the product can grow much faster than linearly. A log plot that rises
with reverse layer or cycle depth is consistent with this mechanism. It is not
conclusive by itself: shared-weight accumulation, a small number of outlier
tokens, attention saturation, optimizer-state damage, or numerical overflow
can produce related plots.

The strongest confirming evidence would be repeatable local gradient-gain
ratios greater than one across successive block and cycle boundaries before a
global spike. Stable activation RMS paired with rapidly increasing backward
RMS would specifically implicate Jacobian amplification rather than exploding
forward activations.

## What Existing Safeguards Do and Do Not Do

- Lower learning rate reduces parameter movement and may reduce entry into an
  unstable region, but it does not change the instantaneous Jacobian of the
  current network. Small LR reductions need not eliminate a depth-driven event.
- Global norm clipping bounds the optimizer update after backward. It does not
  prevent an unstable backward pass, local overflow, or one bad gradient from
  contaminating every parameter direction before scaling.
- Skip-before-moments protects parameters, Adam moments, step state, and EMA
  from a detected anomalous batch. It is a containment policy, not a repair for
  recurring amplification.
- A larger batch reduces ordinary sampling noise but does not guarantee a
  smaller Jacobian. It can make rare trigger examples less dominant while also
  making each skipped or unstable step more expensive.
- EMA smooths model states after optimizer updates. It cannot stabilize the
  live backward graph and can only avoid contamination when the underlying
  optimizer update is clipped or skipped correctly.
- Reducing `bp_steps` shortens the differentiable recurrence directly and is a
  useful diagnosis. It also changes the training objective and credit horizon,
  so it is not quality-neutral.

## Residual-Scaling Options

### Fixed residual scales

Scale each residual branch explicitly:

```text
x_attn = x + alpha_attn * Attention(RMSNorm(x))
x_out  = x_attn + alpha_mlp * MLP(RMSNorm(x_attn))
```

A fixed scale makes each local Jacobian closer to identity and is simple to
reason about. A crude depth heuristic such as `1/sqrt(N)` would be about 0.053
for 360 differentiable residual sublayers at `bp_steps=5`; this number is only
an order-of-magnitude reference and is not a recommended setting. Effective
depth, recurrent sharing, gated attention, and branch statistics violate the
assumptions behind that simple estimate.

Changing the output-projection initialization is related but not identical.
The current `megatron` initializer scales attention and feed-forward output
weights by physical transformer depth. The production `lecun_normal` path does
not apply equivalent output scaling, and neither initializer accounts
explicitly for unfolded recurrent depth. Initialization scaling helps a fresh
run but cannot be introduced into an existing checkpoint without changing its
function.

### Trainable residual gates

Possible granularities are:

- one scalar for each attention and MLP branch in each physical H/L block;
- one hidden-size vector for each branch, allowing channel-specific control;
- one scalar or vector for each outer H/L recurrent injection;
- combinations of branch and injection gates.

For XXL, scalar branch gates add only 144 values. Per-channel branch gates add
`144 * 1792 = 258,048` values. Outer-loop injection gates add eight scalars or
14,336 vector values for the two H and six L applications.

To preserve an existing checkpoint exactly, a bounded positive parameterization
can initialize to one, for example `scale = 2 * sigmoid(raw_scale)` with
`raw_scale=0`. Direct unconstrained scalars are simpler but may cross zero or
grow without bound. Gates initialized at one are not guaranteed to learn lower
values: the task loss may reward larger branches, adjacent weights can
compensate for a gate, and rare instability contributes little to the average
objective. Useful gate training may require explicit regularization, a maximum
bound, or a residual-ratio penalty.

Any new trainable gate changes checkpoint schemas. Resuming requires explicit
initialization of missing gate state, compatible optimizer and EMA migration,
FSDP distributed-checkpoint handling, and matching HF export and vLLM inference
semantics. A null/default-disabled implementation must preserve old checkpoint
behavior exactly.

### Scheduled scaling from one toward 0.1

Starting at one and reducing to 0.1 over 10,000 optimizer steps preserves the
function only at the first step. At the current 262,144-token global batch, the
transition covers about 2.62B tokens. It may suppress the unstable Jacobian,
but it also continuously changes the function while the optimizer attempts to
compensate. A tenfold change can erase or distort learned residual computation,
especially when applied simultaneously to every branch and injection.

If tested on a continuation, the conservative sequence is:

1. Preserve a complete pre-change checkpoint and optimizer/EMA state.
2. Measure a baseline with the diagnostics below.
3. Try a smaller transition such as 1.0 to 0.5 on a short branch run.
4. Separate transformer residual scaling from recurrent injection scaling.
5. Compare loss, exact accuracy, gradient-gain profiles, clipping frequency,
   and held-out evaluations before considering a move toward 0.1.

This is an experimental intervention, not a safe substitute for LR reduction.

## Other Architectural and Optimizer Ideas

- Scale only L or only H branches. The deepest differentiable chain contains
  three L applications but only two H applications at `bp_steps=5`; L-only
  scaling is therefore a useful localized experiment. H carries the final
  output and may still dominate particular gradient paths.
- Scale or gate recurrent injection separately. This tests whether repeated
  `state + injection` fusion, rather than transformer residuals, is the trigger.
- Use a learned fusion such as a GRU-like update. This is more expressive but
  is a larger architecture and checkpoint-compatibility change.
- Use stochastic or scheduled truncation of recurrent backpropagation. This
  reduces worst-case depth but changes credit assignment and may increase
  gradient variance.
- Apply per-module clipping or adaptive gradient clipping. These can stop one
  physical block from dominating the global direction, but shared recurrent
  weights make module norms mixtures of cycle-specific contributions.
- Add optimizer-native anomaly handling, including skip-before-moments,
  moment reset after repeated events, or update-to-parameter ratio limits.
  Moment reset is destructive and should be a last-resort branch experiment.
- Inspect attention logits, Q/K norms, gate saturation, and token-local maxima.
  A small set of pathological positions may be a more specific trigger than
  uniform depth amplification.

## Implemented Non-Invasive Diagnostics

The recorder in `models/stability_diagnostics.py` is disabled by default. With
`stability_diagnostics_interval: 0`, training constructs no recorder, registers
no hooks, performs no diagnostic reductions, and writes no files. The compiled
normal path sees only constant-null diagnostic arguments. On a sampled step,
the training loop performs an uncompiled shadow forward/backward before the
real step to avoid Dynamo graph breaks from Python hooks. The shadow runs under
an RNG fork, records gradients before clipping, and then discards them without
touching optimizer moments, parameters, EMA, the global step, or carry. The
real compiled forward/backward and optimizer step then run through the ordinary
path. Shadow replay is currently rejected for models with stateful carry.

Enable a sparse local record with:

```bash
stability_diagnostics_interval=1000 \
stability_diagnostics_max_tokens_per_microbatch=4096 \
stability_diagnostics_output=logs/stability/xxl.jsonl
```

The shadow replay keeps complete leading packed sequences up to
`stability_diagnostics_max_tokens_per_microbatch` in each accumulation
microbatch. This bound applies only to the extra diagnostic replay; the real
compiled optimizer step still consumes the full configured batch. Large
individual tensors, including logits and optimizer state, use a deterministic
strided sample of at most 1,048,576 elements before conversion to FP32 for
statistics. These two bounds are necessary for XXL diagnostics: an unbounded
logits statistic or an uncompiled full-microbatch FP32 cross entropy can exceed
the available B200 memory even though ordinary compiled training fits.

On 2026-09-07, the DFM10 XXL run was stopped only after the complete
`ephemeral_step_450500` sidecar, `.metadata`, and all eight rank shards were
present. The 450500-to-451000 measurement segment uses an interval of five and
a 4,096-token diagnostic replay cap, yielding 100 snapshots while leaving the
full 262,144-token global production updates unchanged. Its detailed local
record is `logs/stability/dfm10_XXL_step450500_to_451000.jsonl`: 100 records
and 456,390,354 bytes. The complete eight-rank `step_451000` checkpoint was
written before the diagnostic process exited, after which the scheduler
resumed ordinary diagnostics-disabled training from `step_451000` toward
`step_500000`.

Each sampled step records distributed aggregate statistics under explicit H/L
cycle and physical-layer names:

- activation mean, RMS, standard deviation, maximum absolute value, and
  non-finite fraction for block input, attention norm input, attention residual,
  post-attention stream, MLP norm input, MLP residual, block output, final core
  norm, embeddings, and logits;
- attention gate-logit and sigmoid-gate distributions, near-zero/near-one gate
  fractions, per-head Q/K/V RMS, aligned-position scaled Q-K score proxies,
  gated attention output, and output-projection statistics;
- SwiGLU gate, up-projection, elementwise-product, per-token RMS, and
  down-projection statistics;
- the same statistics for available backward gradients at block, residual,
  recurrent, embedding, and logit boundaries;
- cosine alignment between the incoming stream and each residual branch;
- hidden-state, injection, combined-state, and recurrent output statistics plus
  hidden/injection cosine alignment for every H and L cycle;
- residual-to-stream RMS ratios, recurrent injection-to-hidden RMS ratios, and
  block input-gradient/output-gradient RMS ratios as local backward-gain
  proxies;
- physical-layer parameter and pre-clipping gradient statistics;
- Adam first moment, second moment, and EMA statistics where present.

All ranks collect the same keys. Finalization verifies that key sets agree,
then uses distributed sum/max reductions. Rank zero writes one locked,
flush-and-`fsync` JSONL record. This avoids concurrent writers and retains the
full detail without creating thousands of W&B panels. Each record also retains
the epoch, batch position, BP depth, LR, global batch, accumulation,
distribution and precision modes, and active clip/skip thresholds. Statistics
from gradient-accumulation microbatches are pooled into the optimizer-step
record.

An enabled diagnostic step costs approximately one additional uncompiled
forward/backward pass (including all configured recurrent applications and
distributed gradient communication). Sparse intervals are therefore intended;
the disabled path remains the production default.

Compact maxima are logged as `stability/*` on sampled steps. Setting
`stability_diagnostics_wandb_detailed=true` additionally logs every detailed
value under `stability_detail/*`; use this only for short diagnostic branches
because the key count is large.

### Interpretation limits

The input-gradient/output-gradient RMS ratio is a vector-Jacobian-product
amplification proxy for the actual loss direction, not a spectral norm or full
Jacobian estimate. Parameter statistics refer to physical shared layers, while
activation and boundary-gradient statistics retain recurrent cycle identity.
FA4 does not expose the full attention-logit matrix. The recorder therefore
uses Q/K norms and aligned-position scores as non-invasive conditioning proxies;
materializing all logits would replace the production attention behavior and
is intentionally not part of this instrumentation.
Distributed values aggregate all tokens and ranks, so maximum absolute values
should be consulted alongside RMS and non-finite fractions. Activation
checkpointing may repeat forward-side observations during recomputation; use a
non-checkpointed diagnostic branch when exact observation counts matter.

## Findings from the 450500-to-451000 DFM10 XXL Capture

The 100 snapshots establish severe but finite internal ill-conditioning. They
do not support BF16 overflow, optimizer corruption, or a simple monotonic
increase over this 500-step interval. All 11,492 recorded
`nonfinite_fraction` series remained zero. Parameter, EMA, and Adam-state RMS
values remained finite and stable, while gradients were extremely heavy-tailed
and strongly correlated with the production run's pre-clipping gradient norm.

| Diagnostic | Median | p90 | Maximum |
|---|---:|---:|---:|
| Activation maximum absolute value | 284,672 | 659,456 | 675,840 |
| Boundary-gradient maximum absolute value | 2.84 | 1,096 | 105,984 |
| Parameter-gradient maximum absolute value | 181 | 74,868 | 37,864,220 |
| Maximum local block gradient-gain proxy | 149 | 1,436 | 12,836 |
| Maximum recurrent gradient-gain proxy | 54.7 | 263 | 3,974 |
| Maximum residual-to-stream RMS ratio | 46.4 | 52.8 | 56.0 |

The core boundary values look deceptively healthy because every recurrent core
ends in RMS normalization. H and L core outputs have RMS approximately 1.0,
and recurrent combined-state RMS is approximately 1.26 to 1.37. Before that
final norm, however, the median RMS of the last L block output is approximately
1,848 in L cycle 0, 4,323 in cycle 1, 3,863 in cycle 2, and 3,144 to 3,310 in
cycles 3 through 5. The corresponding H values are approximately 225 and 87.
The final normalization therefore bounds the value crossing a recurrent
boundary but does not prevent extreme residual-stream growth inside a core.

The growth is primarily associated with residual branches, especially MLP
branches near the beginning of a physical core. The median peak MLP
residual-to-stream ratios include 46.4 for L cycle 0 layer 0, 17.9 for L cycle
5 layer 0, 17.6 for L cycle 4 layer 0, and 13.6 for H cycle 0 layer 0. Recurrent
injection is not the leading suspect: its ratios are stable near one and its
hidden/injection cosine values are small and mildly negative.

Backward amplification is likewise localized rather than uniform. Median
layer-0 input-gradient/output-gradient RMS ratios are 24.7 for H cycle 0, 12.1
for H cycle 1, 63.2 for differentiable L cycle 3, 52.7 for L cycle 4, and 41.9
for L cycle 5. Most later L layers have ratios near one. Physical H layer 0
dominates parameter gradients: its gradient RMS has median 0.209, p90 136, and
maximum 32,236, compared with median 0.0228 for H layer 1 and 0.00696 for L
layer 0. Global clipping limits the eventual update norm, but it acts after
this distortion and cannot restore a balanced gradient direction.

L attention is also heavily saturated. Across L cycles, the pooled median
fraction of sigmoid gates near zero is approximately 0.984 to 0.993, while a
small subset of early layers and cycles is frequently near one. Problematic L
blocks have query RMS around 25, key RMS around 17, value RMS around 28,
gate-logit RMS around 30, and an aligned-position scaled Q-K score proxy around
5,400 to 5,990. The proxy is not the full attention matrix, but the combined
Q/K scale and binary gate behavior are strong evidence of poor attention
conditioning.

The shadow diagnostics track production instability rather than creating an
isolated artifact. In log space, parameter-gradient maximum absolute value and
boundary-gradient maximum absolute value correlate with production global
gradient norm at approximately 0.81. Parameter-gradient and boundary-gradient
maxima correlate with production loss at approximately 0.63 and 0.67. The
diagnostic interval includes a production event at step 450550 with global
gradient norm about `5.01e9`, clipping coefficient about `2.0e-10`, loss 9.87,
and accuracy 0.011. Neighboring windows also contain large events, so the
mechanism is bursty and batch-sensitive rather than unique to the diagnostic
replay.

The evidence supports a refined mechanism:

1. Unscaled residual branches produce very large internal streams, especially
   in L and especially around early physical blocks.
2. Final RMS normalization hides this growth at recurrent-core boundaries.
3. Saturated gates and very large Q/K scales worsen conditioning in L
   attention.
4. Earlier differentiable recurrent applications amplify the actual loss
   gradient, with H cycle 0 and L cycles 3-5 layer 0 acting as bottlenecks.
5. Rare batch-dependent triggers turn this latent conditioning problem into
   million- or billion-scale pre-clipping production gradients.

This does not establish a Jacobian spectral norm: the recorded gain is for the
actual loss-direction vector-Jacobian product. Products of per-layer RMS ratios
must not be interpreted as compositional end-to-end Jacobian gains because
gradient directions change and recurrent weights are shared. The shadow also
uses only complete leading packed sequences up to 4,096 tokens per
accumulation microbatch, so it can miss a trigger elsewhere in the full
production batch.

The least invasive next discriminator is a short replay from the same
checkpoint and data cursor with `bp_steps=3` or 4. If the recurrent and
parameter-gradient tails contract substantially, unfolded depth is causal.
The next architecture experiment should scale MLP residual branches before
recurrent injection, initially with a moderate fixed value such as 0.5 in a
disposable branch. Compare L-only against H-and-L scaling because L has the
largest internal streams while H physical layer 0 has the largest parameter
gradients. Per-module clipping, adaptive gradient clipping, and
skip-before-moments remain containment mechanisms rather than fixes for the
underlying conditioning.

### Controlled BP-depth replay at step 452500

On 2026-09-07, production stopped only after `ephemeral_step_452500` had a
complete sidecar, DCP metadata, and all eight nonempty rank shards. Two
disposable ten-step runs resumed that identical checkpoint and data cursor with
fixed `bp_steps=3` and `bp_steps=4`. Both used `WANDB_MODE=disabled`, disabled
regular and ephemeral checkpoint intervals, and wrote only local diagnostics
under `logs/stability/bp_depth_replay_452500/`. Production then resumed from
the untouched `ephemeral_step_452500` with the normal 2-to-5 BP schedule and
diagnostics disabled.

| Measurement across ten steps | BP 3 | BP 4 |
|---|---:|---:|
| Parameter-gradient max-abs median | 0.0776 | 0.0763 |
| Parameter-gradient max-abs maximum | 0.1539 | 0.1541 |
| Boundary-gradient max-abs median | 0.000392 | 0.000396 |
| Maximum local block-gain median | 44.3 | 62.4 |
| Maximum local block-gain maximum | 64.1 | 74.6 |
| Maximum recurrent-gain median | 0.773 | 0.773 |
| Activation max-abs median | 253,440 | 255,488 |
| Residual-to-stream ratio median | 26.7 | 26.1 |

BP 3 exposes only the final differentiable L application's layer-0 hotspot:
`L/cycle_005/layer_000` has median local gain 44.3. BP 4 adds the preceding
differentiable application, where `L/cycle_004/layer_000` has median gain 62.4
and `layer_001` has median gain 9.08; the final L application's layer-0 median
remains 44.2. H-cycle gain profiles are nearly unchanged. This is direct
evidence that each added differentiable L application introduces another
localized amplification site.

The sampled slice itself was benign. Production-gradient norms reported by the
disposable runs were approximately 0.27 at step 452505 and 0.25 at step 452510,
with no clipping, and loss/accuracy were nearly identical between BP 3 and BP
4. The resumed production BP=5 path processed the same data and reported
gradient norms 0.27015 and 0.25409 at those two steps, also without clipping;
W&B confirms `bp_steps=5`. Thus the extra differentiable paths barely affect
the aggregate gradient on these benign batches even though they add local
amplification sites. Consequently, the experiment supports depth-dependent
local amplification but does not quantify suppression of the rare gradient
tail. A stronger causal
test must replay a data slice known to contain a burst, or capture substantially
more matched BP-depth steps. It would be incorrect to compare the absolute tail
statistics from this benign slice directly with the earlier burst-heavy
450500-to-451000 interval and attribute the whole difference to BP depth.

Production provided an immediate contrasting event after the replay. Steps
453400 through 453500 formed a concentrated BP=5 burst: 20 of 21 logged points
were clipped, median pre-clipping gradient norm was approximately `1.05e5`, and
the maximum was `5.36e6`. Median loss rose from 0.999 in the preceding 100 steps
to 1.18, median token accuracy fell from 0.772 to 0.736, and median exact
accuracy fell from 0.288 to 0.207. From 453505 through 453760, all three quality
metrics recovered to medians 0.996, 0.774, and 0.284, while gradient-norm median
returned to 0.239. Six of those 52 later logged points still clipped and the
largest gradient norm was 21,708. This rapid onset and recovery strengthens the
batch-dependent-trigger interpretation and shows that the underlying
instability remains present despite apparently healthy medians.

By step 458860, the resumed BP=5 run had worsened from isolated events into
repeated collapse/recovery cycles. Across 453505-458860, 34.6% of logged points
were clipped, six gradient norms exceeded one million, and the maximum was
`1.80e8` at step 456000. The most recent 500-step window had median gradient
norm 136, 78.8% clipping, median loss 1.274, median token accuracy 0.723, and
median exact accuracy 0.148. Individual 100-step windows still briefly recover
to gradient norm approximately 0.24 and loss approximately 1.0, but unstable
windows now recur frequently and can persist for several hundred steps. Treat
the current trajectory as actively unstable rather than healthy with rare
outliers.

Superseding operational status on 2026-09-08: the trajectory subsequently
entered a sustained recovery. Through step 472100, the latest 2,000-step window
had zero clipped logged points, median/p90/p99 gradient norms
`0.225/0.244/0.290`, maximum gradient norm approximately 1.0, median loss
0.971, median token accuracy 0.777, and median exact accuracy 0.296. The latest
500-step values were similar. This establishes current local stability, but it
does not invalidate the earlier mechanism or guarantee that another
batch-triggered burst will not recur.

## Recommended Experiment Order

1. Capture sparse diagnostics during an ordinary stable region and through at
   least one naturally occurring spike, without architecture changes.
2. Identify the first H/L cycle and physical layer where backward RMS or maxima
   separate from the stable baseline; also check whether forward activations,
   branch ratios, injection ratios, or attention/MLP alignment move first.
3. Reproduce a short interval from the same checkpoint and data cursor at lower
   `bp_steps`. A strong depth-dependent reduction would support the Jacobian
   hypothesis.
4. Test fixed L-only residual scaling on a disposable branch, followed by
   injection-only scaling. Do not combine interventions until each effect is
   measurable.
5. Test bounded trainable scalar gates before vector gates. Compare both
   stability and whether gates actually move without harmful compensation.
6. Only after parity, checkpoint migration, export, and evaluation tests should
   a scaling mechanism be considered for a production continuation or fresh
   model.

No residual or injection scaling has been enabled in the production model as
of 2026-09-07.
