---
type: Technical Reference
title: Training Stability, Jacobian Growth, and Residual Scaling
description: Recurrent-depth stability diagnosis, mitigation options, and opt-in instrumentation for HRM-Text.
tags: [training, stability, gradients, jacobian, residual-scaling, recurrence]
status: draft
last_updated: 2026-09-09
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

## Initialization and Checkpoint Editing Assessment, 2026-09-08

The XXL LeCun initializer uses input/attention-output standard deviation
`1/sqrt(1792) = 0.02362` and MLP-output standard deviation
`1/sqrt(4864) = 0.01434`. It preserves linear fan-in variance but adds no
residual-depth attenuation. The existing Megatron alternative uses 36 physical
blocks after `half_layers` and gives both output projections standard deviation
approximately 0.002784, reducing attention output initialization by 8.49x and
MLP output initialization by 5.15x. It does not explicitly account for recurrent
reuse. The size config's comment that LeCun worked better is an existing
empirical preference, not proof that it is optimal for this XXL trajectory.
Changing `init_type` while restoring every trained weight does not repair a
checkpoint. Initialization can bias the trajectory but the late probe cannot
establish that initialization caused the instability.

Qualification of earlier causal wording: observed large streams and saturated
sigmoid output gates establish scale and saturation, not their necessity or
sufficiency for the collapse. Sigmoid saturation itself reduces the local gate
derivative. Attention output gates are distinct from softmax attention entropy,
which was not measured. Large streams also reduce some RMSNorm derivatives.
Likewise, global clipping bounds the gradient presented to AdamATan2, not the
subsequent parameter-update norm. Update/parameter ratios and optimizer moments
must be measured to determine actual damage after a burst.

Candidate disposable-checkpoint experiments, in order of increasing disruption:

- Attenuate selected `mlp.down_proj.weight` matrices by 0.9 or 0.75, then 0.5
  only if justified. With these bias-free layers this exactly scales the MLP
  branch output at that instant. It changes the model function and can regrow
  during training. Compare layer-0-only, L-only, and H/L interventions on known
  bad batches plus benign held-out batches.
- Attenuate selected `attn.o_proj.weight` matrices similarly. Treat MLP and
  attention edits independently to identify the operative mechanism.
- Scale only Q and K slices of the fused gate/Q/K/V projection: scaling each
  by sqrt(t) multiplies attention scores by t (RoPE is linear). This preserves
  weight layout but changes attention. Softmax entropy should be measured
  before deciding whether this is appropriate. Editing sigmoid gate rows can
  reopen shut channels and is not automatically stabilizing.
- Estimate per-matrix spectral norms and attenuate exceptional singular modes
  or constrain norms during training. A large mode can encode useful content,
  so magnitude alone is insufficient grounds to remove it. Spectral control
  has precedent in [sigmaReparam](https://arxiv.org/abs/2303.06296).
- Blend selected problematic matrices toward an earlier stable checkpoint,
  or apply an EMA rollback, after matched forward/loss and gradient tests.
  Interpolation can break co-adapted features and a stable batch window does
  not establish that the underlying checkpoint is robust.

Edits must operate on an isolated checkpoint with explicit EMA and optimizer
semantics. Applying the same edit to EMA avoids mixing two different model
functions. Multiplying weights by alpha does not imply multiplying optimizer
moments by alpha and alpha squared: that rule applies to particular gradient
rescalings, not arbitrary function-changing weight edits. Existing-moment and
selective-reset variants require comparison; neither preserves the trajectory.
Bias-free V/output or SwiGLU-up/down inverse rescalings can approximately
preserve the function and change parameter conditioning, but they also preserve
the mathematical input-output Jacobian and cannot eliminate its amplification.

For a fresh run, compare depth-scaled initialization with small trainable
residual gates, and consider explicit attention-scale control. Small/zero
initial residual gates have precedent in
[ReZero](https://arxiv.org/abs/2003.04887); that evidence does not establish
optimal scales for this recurrent HRM. A gate initialized to one preserves the
current function initially but needs constraints or supervision to reliably
shrink. None of these interventions is enabled in production.

## Optional Loss Regularization Proposal, 2026-09-08

Proposed only; no production loss or weights have been changed. Add separately
weighted penalties for MLP residual magnitude, attention sigmoid-gate logits,
and Q/K scale. Start with MLP outputs and assess known burst-producing batches
plus benign held-out batches. Apply only to already differentiable recurrent
applications, average across layers/cycles, mask padding, accumulate statistics
in FP32, and gradually ramp coefficients. Record auxiliary and language-model
gradient magnitudes separately. Export and inference need no changes.

The initial thresholded proposal uses
`mean(relu(RMS(residual)/(stopgrad(RMS(stream))+eps)/threshold - 1)^2)`.
Detaching the denominator avoids a direct gradient encouraging stream inflation,
although this does not prevent indirect compensation over training.

Simpler continuous alternatives are `mean(residual^2)` for absolute branch
energy, `mean((RMS(residual)/(stopgrad(RMS(stream))+eps))^2)` for relative
energy, `mean(gate_logits^2)` for sigmoid gates, and per-head `mean(Q^2 + K^2)`
for attention scale. They require no hinge threshold but still require a
coefficient and a choice of normalization. They penalize useful computation as
well as pathological extremes, so compare small coefficients first. Penalizing
logits gives a corrective gradient even for saturated sigmoids; it is not the
same as directly encouraging softmax attention entropy. Maximizing sigmoid
entropy after saturation can have weak corrective gradients.

Weight L2 and decoupled weight decay are simpler alternatives. Existing
training already uses weight decay 0.1. Penalizing distance from a reference
checkpoint discourages all changes, including useful rotations; penalizing
weight magnitude encourages small norms but cannot directly control alignment,
spectral concentration, residual activation tails, or products across recurrent
applications. These alternatives must be assessed against actual weight-growth
measurements rather than inferred from activation magnitude alone.

### Measured Weight Change: XXL 140K to 160K

Compared actual model weights (not EMA) in
`checkpoints/dfm8/XXL-1epoch/fsdp2_step_{140000,160000}` with
`scripts/compare_checkpoint_weight_growth.py`. It reads matching DCP tensor
chunks on CPU without optimizer state and splits fused projections into gate,
Q, K, V and MLP gate/up components. Detailed results for all 577 parts are in
`logs/stability/xxl_weight_growth_140k_160k.json`.

| Parameter group | Pooled RMS change |
|---|---:|
| All weights, including LM head | -2.58% |
| H core | -2.47% |
| L core | -2.07% |
| Attention sigmoid gate | -2.60% |
| Query | -2.09% |
| Key | -2.16% |
| Value | -2.24% |
| Attention output | -2.13% |
| MLP gate | -2.37% |
| MLP up | -2.33% |
| MLP down | -2.17% |
| LM head | -5.46% |

Only 11 of 577 parameter parts grew in RMS, all in L. The largest increase
was L layer 3 MLP down (+1.88%). Yet that matrix's relative change norm was
0.962 and its checkpoint-to-checkpoint cosine was 0.546. This illustrates how
substantial changes in direction can coexist with nearly constant or declining
weight norms. These measurements contradict global norm growth as the simple
explanation for instability in this interval. They do not rule out growth of
particular singular values or activation-producing alignments, and they do not
measure the later 450K regime. Plain weight decay already applies; stronger
weight-magnitude penalties remain experiments rather than a demonstrated fix.

### Available Checkpoint for a Matched Regularizer Replay

Checkpoint inspection selected `step_451000` in
`checkpoints/dfm10/XXL-from-dfm8-epoch1` as the closest preserved checkpoint
before the proposed 453400-453500 burst. Its sidecar records the exact batch
cursor 721664 in epoch 2 and global row cursor 113351658. All 9,577 DCP storage
entries reference present files with sufficient lengths. No preserved 452500,
453000, or 459000 checkpoint was found under checkpoints or stability outputs;
the 452500 replay directory contains diagnostics, not saved training state.

The concrete first comparison is baseline versus relative-MLP-energy
regularization from 451000 through 454000, using BP=5 and identical resume
settings/data. Do not jump the data cursor directly to 453000: intervening
updates affect whether the burst occurs. The historical burst is an observation,
not a guaranteed deterministic replay outcome; establish it in the new baseline
before attributing an absent event to regularization. A common unmodified
451000-to-453000 prefix can be computed once and checkpointed for both branches
if the intended intervention starts at 453000. This is a proposed experiment;
checkpoint inspection itself did not interrupt training or launch replays.

### Shared-Prefix Replay Implementation (2026-09-08)

The proposed replay above is now implemented and launched. Production was
stopped only after `ephemeral_step_487500` was complete, with all DCP storage
ranges validated. The production snapshot and experimental initial `step_451000`
are preserved under
`checkpoints/experiments/xxl_mlp_shared_prefix_20260908/`. Immutable DCP payloads
are hard-linked, not duplicated; deleting the original checkpoint directory
cannot remove these preserved links. Do not modify checkpoint payloads in place.
The archive is outside production's ephemeral-pruning directory.

The opt-in setting is `+arch.mlp_relative_energy_weight=0.0001`, default **zero**.
The calculation lives in `models/stability_regularization.py`; explicit tensor
returns propagate it through the differentiable HRM cycles and LMHead. There
are no forward hooks, new parameters, or checkpoint schema changes. Inference
and evaluation do not activate it. With zero weight the established tensor
forward path is retained. Diagnostics and the active regularizer currently
require separate replays.

For each supervised, non-padding token the objective measures mean-square MLP
residual divided by detached incoming-stream mean-square (FP32, denominator
floored at `1e-6`). It averages across blocks within each differentiable cycle,
then across differentiable cycles; no-grad recurrent applications do not
contribute. Prompt-only and padding positions are excluded using raw labels,
independently of optional Goldfish dropping. The token divisor is all-reduced
in the same way as CE; ordinary GAS scaling applies to both losses. The original
`train/loss` remains **CE only**, alongside `train/mlp_relative_energy` and
`train/mlp_regularization_loss`. A small scalar penalty is not by itself proof
of a small auxiliary gradient.

The supervisor `scripts/run_mlp_shared_prefix_experiment.py` executes:

1. Preserve the production checkpoint, stop its isolated torchrun group, and
   await the explicit `READY` preflight marker (20-minute timeout).
2. Replay 451000 to 453000 without regularization into `prefix/`, saving a
   regular branching checkpoint including optimizer/EMA and exact data cursor.
3. Replay 453000 to 454000 into `baseline/` with weight zero.
4. Replay the identical branching checkpoint into `regularized/` with weight
   `1e-4`, saving a separate final checkpoint at 454000.
5. In a `finally` recovery path, resume production from its preserved **487500**
   checkpoint to 500000 with the original LR, BP=5, clipping, and W&B identity.
   Never continue production from an experimental branch.

All experimental torchruns use `WANDB_MODE=disabled`, `WANDB_DISABLED=true`,
and null W&B run/resume IDs. Production alone resumes `DFM5/40j5y877`.
The supervisor is detached and logs to
`logs/stability/mlp_shared_prefix_20260908_supervisor.log`; experiment stage
logs, captured commands, and benchmark metric histories are under its archive.
`production_resume.log` there will contain the restored main training output.
The existing scheduler is only waiting on future production checkpoints; none
of the experimental paths satisfy its checkpoint waits.

Preflight: 22 CPU tests passed, including checkpoint preservation helpers,
existing diagnostics, detached
denominator gradients, mask behavior, cycle averaging, unchanged evaluation,
zero-option parity, and compiled energy gradients. Both full eight-GPU XXL
three-step smokes from 451000 passed using the production FSDP/GAS settings.
Peak allocated memory was approximately 144.7 GiB baseline versus 149.6 GiB
regularized. The first CE losses were 6.93987 and 6.93984 respectively: replay
already starts in a poor state **without** regularization. Small compiled
numerical differences remain, and subsequent instability makes a three-step
outcome unsuitable as evidence of benefit. The weighted penalty was ~0.0013;
the first regularized gradient norm remained very large. These are feasibility
checks, not a positive stability result.

`scripts/summarize_mlp_shared_prefix_experiment.py <archive> --wait` generates
`comparison.json` and `comparison.md` after both branches finish, with full-run,
historical-burst-window (453400-453500), and final-200-step summaries. Metrics
are sampled at log interval five, not every optimizer step. A detached instance
has been started. Historical burst reproduction and improvement remain
unverified until the branch results are reviewed. The nominal 4,000-step
campaign is roughly three hours plus startup/checkpoint I/O; each stage has a
four-hour timeout. Recovery covers Python errors/timeouts, not machine failure
or SIGKILL; the preserved checkpoint and recorded resume command support manual
recovery in those cases.

### Matched Branch Diagnostics Augmentation (2026-09-08)

User approved augmenting the comparison before either branch started. The
running prefix remains unchanged. The original supervisor was frozen and then
replaced by a verified adopter of the **same** prefix process (PID 2309654).
The replacement supervisor (PID 2365338) logs to
`logs/stability/mlp_shared_prefix_20260908_supervisor_v2.log`. It retains the
same production recovery snapshot and command; no prefix steps were rerun.

The earlier five-step-only branch history and lack of layer/component probes
are **superseded for the two branches**, not for the already-running prefix:

- `steps.jsonl`: rank-zero, flushed after every optimizer step, containing CE,
  accuracy, exact accuracy, pre-clipping norm, clipping indicators, LR, BP,
  epoch/data cursor, and training-versus-probe timing. The regularized branch
  additionally reports raw relative energy and its weighted loss every step.
  Metrics are also retained in the final `metrics.json` benchmark history.
- `layers.jsonl`: existing detailed per-layer/cycle recorder every 50 steps,
  including MLP/stream ratios, activation and gradient RMS/gain, attention
  proxies, and parameter/optimizer statistics. Both branches explicitly use a
  **CE-only** shadow backward for comparable layer gradients. No auxiliary
  gradient is mixed into these layer records.
- `steps.jsonl.gradients.jsonl`: separate CE and weighted-auxiliary gradients
  at steps **453001, 453400, 453500, 453950**, including norms, norm ratio,
  cosine, raw residual energy, supervised-token count, and per-rank input
  hashes. Baseline probes use the same candidate auxiliary weight `1e-4`, but
  this does not add it to baseline training.

Layer probes use complete leading packed sequences from each current
microbatch with nominal budget 1024 tokens. A single sequence can exceed the
budget (up to the 4096-token training context); sequences are not truncated.
The separate gradient comparison uses only the **first** such microbatch on
each rank. Therefore its norms describe the matched diagnostic subset, not the
full production batch or the threshold used for production clipping. Saved
fingerprints allow confirming that the subset is identical between branches.

`models/experiment_diagnostics.py` holds the telemetry and component-gradient
logic. The pretraining options are default-off:
`+experiment_metrics_output=<path>`,
`+experiment_gradient_probe_steps=[...]`, and
`+experiment_gradient_probe_weight=0.0001`.
Shadow passes require empty incoming gradients and stateless carry, preserve
Torch CPU/CUDA RNG, do not advance the loader, do not clip or step the optimizer,
and clear temporary gradients even on exceptions. CE gradients are copied to
CPU before the auxiliary backward, avoiding a second full gradient copy on
GPU. Full-world FSDP norms account for this repo's summed-gradient convention;
hybrid FSDP component probes are explicitly unsupported. The actual training
objective and coefficient are never mutated for a probe.

CPU tests verify unchanged parameters, optimizer/EMA, RNG, input batch, step,
carry, and the subsequent training update. The combined focused suite has 24
passing tests. A two-step eight-GPU `diagnostics_preflight/` is scheduled after
the shared-prefix checkpoint and **before** baseline, exercising both layer
and component probes. It does not save a new checkpoint or log to W&B. Failure
aborts the comparison and triggers the same production-recovery path rather
than silently running unmatched diagnostics. GPU preflight results are pending.

The comparison writer now reports median training-only time and total probe
overhead separately. The original benchmark step-time series includes probes
and should not be used alone to infer regularizer compute cost. Rank zero is
the sole writer for each telemetry file; branch directories are distinct.

### Replay Status at 22:17 on 2026-09-08

The shared prefix completed and saved 453000. The eight-GPU diagnostic
preflight subsequently passed; its earlier pending status is superseded.
Baseline reached 453280 with all eight GPUs active. Over its latest 100 steps,
median CE was 0.9797, maximum gradient norm 0.3883, and no steps were clipped.
The historical burst window (453400-453500) had not yet been reached.
The preflight's matched-subset auxiliary/CE gradient-norm ratio was 0.02286
and cosine -0.00519, at weight 1e-4. This is one diagnostic subset, not evidence
of long-term benefit. The regularized branch had not yet started.

### Completed Shared-Prefix Results (2026-09-09)

Both 1000-step branches completed and saved independent `step_454000`
checkpoints. Production automatically resumed from its preserved 487500 at
the original checkpoint path and W&B run `DFM5/40j5y877`, with no auxiliary
loss or experimental diagnostics. It reached approximately 495985 at review.
Results are in the experiment archive's `comparison.md` and `comparison.json`.

| Whole branch statistic | Baseline | Relative-energy weight 1e-4 |
|---|---:|---:|
| Mean CE loss | 2.8171 | 1.6034 |
| Mean token accuracy | 55.51% | 69.49% |
| Mean exact accuracy | 16.46% | 20.84% |
| Steps clipped | 55.6% | 49.2% |
| Maximum pre-clipping norm | 8.78e13 | 2.53e9 |
| Median training-only seconds/step | 2.594 | 2.629 |

In the final 200 steps, mean CE was 6.497 versus 3.286 and token accuracy
14.72% versus 49.49%. Clipping affected 98% versus 100% of these steps: the
regularized branch also became unstable. At the final single step, CE was
7.622 versus 1.631; neither the favorable final sample nor the whole-branch
mean demonstrates a complete fix. In the historical 453400-453500 window,
baseline/regularized clipping fractions were 20.8%/2.0%, with mean CE
1.014/0.984. Burst timing changed compared with the original run.

All four component-probe input hashes matched across branches. Matched-subset
relative energy at 453400 fell from 13.40 (baseline) to 1.245 (regularized),
and at 453500 from 50.52 to 0.979. Initial auxiliary/CE gradient norm ratio
was about 2.29% with near-zero cosine in both branches. At 453950 the
regularized ratio was 4.97% and cosine -0.071, versus 0.56% and +0.009 in
baseline. These are bounded-subset probes, not full-batch norm estimates.

Interpretation: promising reduction in residual energy and damage from
instability in this matched replay, with about 1.35% measured training-only
overhead. It did not eliminate bursts or final-window degradation. This is
one pair of numerically sensitive trajectories, without held-out evaluation;
repeat the comparison on another segment and inspect layer diagnostics before
changing production or attributing all improvement causally to the penalty.

### Higher-Coefficient Replay Scheduled (2026-09-09)

User approved a second intervention from the **same preserved 453000** prefix
to 454000, this time with relative-energy coefficient **1e-3** (tenfold). The
runner now supports `--branch-source <completed-prefix> --branch-weight 0.001
--prepared`, running only the new branch without recomputing prefix or baseline.
The original baseline and 1e-4 results remain untouched for comparison.

The detached supervisor (PID 2908504) is waiting for production's fully written
`ephemeral_step_496500`. It validates and preserves that checkpoint, stops only
the production torchrun group, runs the new branch without W&B, and resumes
from **496500** into `checkpoints/dfm10/XXL-from-dfm8-epoch1` under the same
`DFM5/40j5y877` run with original LR 1.5e-4 and no auxiliary loss. The scheduler
has only future production checkpoint waits active, so this experiment's
separate paths do not release eval jobs.

Archive: `checkpoints/experiments/xxl_mlp_energy_1e3_20260909/`.
Supervisor log: `logs/stability/mlp_energy_1e3_20260909_supervisor.log`.
Branch log once launched: `regularized/train.log` under the archive.
Per-step metrics, every-50-step layer probes, and component probes at 453001,
453400, 453500, and 453950 match the earlier schedule. Component probes now
use weight **1e-3** to measure the actual new auxiliary gradient; compare their
recorded coefficients when interpreting gradient norms against the old probe.

A detached three-way comparison writer uses `--reference-root` pointing at the
old archive and writes **only into the new archive**. It reads coefficients
from captured commands, not hardcoded labels. Results are pending; the earlier
1e-4 stability findings do not establish that a stronger penalty will be better.

### Layer Diagnostics Review of the Completed Pair (2026-09-09)

See [the focused layer-diagnostics review](mlp-energy-replay-layer-review.md)
for the completed pair's remaining issues, evidence, and measurement limits.

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
