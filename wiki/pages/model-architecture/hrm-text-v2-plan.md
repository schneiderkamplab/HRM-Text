---
type: Research Plan
title: HRM-Text-v2 Architecture Candidates
description: Hierarchical state, communication, expert MLPs, mixtures of L stacks and DeltaNet hybrids, with controlled ablations and serving requirements.
status: draft
confidence: medium
last_updated: 2026-10-18
tags: [architecture, recurrence, research, deltanet, residuals]
---
# HRM-Text-v2 Architecture Candidates

## Scope and Baseline

### Implementation Status (2026-10-18 Update)

The user authorized the extensions below after the earlier research-only notes.
Those earlier statements of "not authorized" are superseded for implementation,
not for changing the running pilot or adopting a feature in production.
See the [implementation and qualification record](hrm-text-v2-implementation.md)
for switches, tests, limitations, optimizer/EMA migration and operating boundaries.

| Area | Current disposition |
| --- | --- |
| V1-equivalent default | Implemented; no optional modules or extra parameters by default |
| Invocation gates, sparse MLP/MoS dispatch, metadata bias | Implemented opt-in; sparse MoS dispatches complete packed sequences |
| Independent frozen-reference specialists | Implemented training freeze policy, strict composition and router-only calibration mode |
| H/L memory branches and input-dependent residual streams | Implemented separately, opt-in |
| N-gram embeddings | Implemented causal device-resident hashed tables with native decode history |
| Muon | Implemented optional Muon/AdamW, splitting fused logical matrices and gathering FSDP matrix updates |
| Upcycling | Optimizer counters/moments and EMA retained for copied parameters/experts |
| Multi-token prediction | Deferred |
| Sparse attention / QSA | Deferred |
| DeltaNet / gated DeltaNet | Deferred |
| HF export, vLLM and production serving of new v2 features | Deferred; existing rejection of unsupported v2 export remains |
| Image input stack, audio input stack, TTS output stack, image-generation stack | Outsourced; not implemented in this v2 workstream |
| Long-context support | Outsourced to the separate long-context workstream |

Historical dense-only execution and fresh-optimizer recommendations below are
superseded by this update. Sparse execution is a correctness-tested eager
dispatcher, not yet a demonstrated GPU throughput improvement. Larger offloaded
n-gram tables and distributed specialist composition are not implied by the
CPU composition utilities.

Recorded at the user's request on October 18, 2026. These are research
candidates, not approved production architecture changes. The current training
is stable; do not frame these proposals as remedies for ongoing instability.

`models/baselines/hrm_nocarry_bp_warmup.py` already maintains separate H and L
states, updated at different frequencies with separate shared-weight stacks:

```
z_L = T_L(z_L + z_H)
z_H = T_H(z_H + z_L)
```

The inactive state is preserved during each update. Fusion is unweighted
addition. Individual transformer sublayers also have their own residual paths.
H/L state separation is therefore an existing capability, not a v2 invention.

## Gated Hierarchical Communication

Test input-dependent read gates at the H/L injection boundary. Distinguish
these activation-level controls from recurrence-aware learning-rate dividers:
the latter regulate parameter updates, not information flow during inference.
Compare gates against the current addition with identical training budgets.

## Multiple H and L State Branches

### Selected Gate Parameterization (October 18)

User decision supersedes the shared/bottleneck gate recommendation for the
planned experiment: use independent, input-dependent, per-channel gates for
each invocation, with full `Linear(2d, d)` projections including bias. The
opt-in implementation and prepared pilot are now described in the
[v2 gate experiment runbook](hrm-text-v2-gated-pilot.md); live training is unchanged.

Allocate `H_cycles` H gates and `H_cycles * L_cycles` L gates. Index L gates
by the flattened outer/inner cycle index, as existing L caches are indexed.
Gate identity supplies cycle specificity; no extra cycle embedding is needed.
Weights remain shared across tokens and examples, not across invocations.
Each gate has `2*d*d + d` parameters; total is
`H_cycles * (L_cycles + 1) * (2*d*d + d)`.
Retain the alpha-scaled bounded injection correction described below, with
zero-initialized gate projections for baseline equivalence. Changing cycle
counts requires an explicit gate initialization/migration policy.

Important inspected-code constraint: `hrm_nocarry_bp_warmup.py` disables
autograd for early invocations according to `bp_steps`. Independent gates at
those invocations receive no gradients, unlike a shared gate trained at later
invocations. Full coverage requires BP covering all H/L calls (8 with H=2,
L=3), or a separately designed training policy. Do not silently change the BP
schedule. Test unused-parameter handling, optimizer grouping, checkpoint
migration and inference/cache parity before enabling this experiment.

Superseded proposal (October 18): all invocation-specific H/L gates must remain eligible for
loss gradients even at lower BP settings. The above untrained-early-gate
behavior is unacceptable for this experiment. Separate backbone parameter
gradient eligibility from activation/input gradient propagation: early stack
calls must propagate activation gradients while their backbone parameters are
treated as detached for that invocation. Later calls use the original shared
trainable parameters. Do not toggle the shared parameters' requires_grad
globally or detach intermediate states, which would break gate gradients.

This preserves the intended subset of backbone parameter-gradient-producing
invocations, but is NOT the current truncated-autograd cost or gradient graph:
exact early-gate gradients require backward propagation through intervening
stack calls. It also changes which activation paths remain connected, so prove
late-backbone gradient parity separately rather than assume it. Expect extra
activation memory and backward compute at low BP; measure both. Detached-weight
functional execution must be qualified with FSDP, compilation and checkpointing
before implementation approval. Straight-through estimators or auxiliary local
gate losses would be alternative objectives, not equivalent exact gradients,
and are not selected. Tests must check every gate's gradient connectivity at
low BP with nonzero alpha (alpha=0 intentionally disables gate learning).

Selected replacement: retain truncated autograd. Inactive gates receive the
actual optimizer parameter delta of the nearest gradient-eligible gate of the
same level. Copy donor moments and step counter while inactive; retain each
gate's own EMA and update it after applying the copied delta. Do not copy gate
values wholesale, cross H/L levels, or extend the backward graph. This is an
explicit approximation, not a true early-invocation loss gradient. All gates
start at zero, so same-level donor sharing initially keeps them aligned; gates
specialize once directly trained. Independent gates use the base LR (one use
per gate), while backbone H/L matrices retain automatic recurrence dividers.

Start with two H branches and two L branches. Each update reads gated mixtures
of local and other-level branches, executes the corresponding stack once, and
writes back to local branches. The other level remains unchanged.

Keep separate two possible designs:

| Candidate | Stack execution | Hypothesis |
| --- | --- | --- |
| Multiple memory branches | One execution per existing H/L update | Preserve complementary representations across cycles |
| Independently computed branches | One execution per branch | Parallel reasoning trajectories, at substantially higher compute |

The first is the initial experiment. More stored states do not automatically
provide independent reasoning trajectories. Extra state, gates and memory
traffic have costs even with unchanged expensive-stack FLOPs.

The write rule is an independent architectural choice:

```
replacement:        r_i' = selected_new_state_i
residual addition:  r_i' = r_i + s_i * y
gated replacement:  r_i' = (1 - w_i) * r_i + w_i * y
```

Residual addition introduces an identity path around the entire stack; it is
not equivalent to the current replacement recurrence. Compare each branched
candidate with a single-branch baseline using the same gates/write rule.
Ensure controlled symmetry breaking: identical initial branches and gates can
remain redundant. Measure branch similarity, gate saturation and causal
ablation effects rather than assigning unverified semantic roles to branches.

Qwen's per-sublayer residual branching is another, separate experiment from
branching HRM's whole-stack recurrent states. Do not combine both initially.

October 18 implementation: optional [m-stream residuals](hrm-text-v2-residual-branches.md)
now exist within v2 pre-norm stacks, with learned per-channel read/write mixes
and one attention/MLP call per layer. This is a local research variant, not a
claim to reproduce Qwen's exact equations. The v2 default now matches v1
exactly; all gates, expert mixtures and residual branches require opt-in.

## Expert MLPs and Mixtures of L Stacks

User-requested additions, October 18, 2026: investigate both candidates
independently. These are research plans, not changes to the running pilot.
Routing among experts is distinct from the H/L injection gates above.

Implementation update: the [expert-mixture reference](hrm-text-v2-experts.md)
now supports configurable k-of-n MoE and MoS, shared/separate L states, and
frozen reference experts. It uses dense execution with sparse output selection;
optimized sparse dispatch and production GPU/serving qualification are pending.

| Candidate | Expert unit | Initial scope | Hypothesis |
| --- | --- | --- | --- |
| MoE (multiple MLPs) | Independent feed-forward networks inside transformer blocks | Replace selected L-block MLPs first; consider H separately | More parameter capacity at approximately fixed active MLP compute |
| MoL-stacks (mixture of L stacks) | Independent complete L transformer stacks, including attention and MLPs | Shared H stack and one L recurrent state, selecting an L expert per invocation | Specialized recurrent transformations rather than only specialized feed-forward layers |

### MoE Pilot Design

Start with a small expert count and token-level top-1 routing; compare top-2
only as an explicit extra-compute experiment. Keep attention and the H/L
recurrence unchanged. Decide whether routing may depend on invocation index,
and measure routing separately for each cycle and language/task family.
Specify load balancing, capacity/overflow handling, deterministic inference
routing and packed-example isolation. Do not silently drop overflow tokens.

For checkpoint continuation, clone the pretrained MLP into every expert and
use normalized routing weights. Identical experts then emulate the original
MLP mathematically (verify numerical parity), but router task gradients cannot
initially distinguish identical experts. Specify controlled symmetry breaking
and load balancing; test expert collapse and inactive-expert starvation.
A dense-to-expert alpha blend is optional, not free: retaining both paths adds
compute during warm-in. Define optimizer/EMA migration and recurrence-aware LR
handling explicitly, including experts selected only in no-grad invocations.

### MoL-Stack Pilot Design

Start with two complete L experts and one shared H stack. Route once per
example per L invocation, preserving the existing single L state and update
rule. This is different from multiple stored L-state branches or executing all
stacks and averaging their results. Top-1 activates one stack per invocation;
top-k executes multiple stacks and must be charged for that extra work.

The router must not use future response tokens: consider invocation embeddings
and a prompt-only summary for an example-level decision. Any hidden-state
pooling requires a causality audit. Dispatch whole examples while preserving
PrefixLM masks, packed boundaries and position indices. Token-level routing
through whole attention stacks is a separate design because it changes which
tokens can attend to each other; do not treat it as ordinary MLP dispatch.

Clone the pretrained L stack into experts for initial functional equivalence,
then define controlled specialization, load balancing and low-BP training
coverage. A decode request may require separate KV caches per expert and
invocation; specify cache ownership and stable routing before serving.
One active expert does not imply unchanged memory or speed: all resident
parameters, optimizer states, dispatch, fragmented batches and communication
must be measured. Do not assume the current LR divisor remains appropriate
when each expert receives a different number of gradient-bearing calls.

### Metadata Bias and Independently Trained Experts

October 18 clarification supersedes the sparse-first/shared-L-state defaults
above as requirements: retain both 1/2 sparse and 2/2 dense mixtures, and both
shared and expert-specific L states. With separate states, specify reads,
writes, inactive-state retention and H's combination rule. Dense 2/2 executes
both experts; distinguish its extra compute from a matched-compute variant.

User-reported prior successful dense-to-2/2 MoE recipe: add metadata-conditioned
positive/negative biases to router logits BEFORE softmax, using the biased
scores both for expert selection and output weighting. This is not an additive
perturbation to already normalized weights. Unequal mixture weights create
unequal expert updates even from identical copies; after specialization, the
input-dependent router can learn useful preferences. Validate with metadata
bias removed. Bias magnitude, schedule and metadata definitions still need
specification; do not invent them from this qualitative report.

Investigate a FlexOlmo-style independent-specialist variant: each training
branch contains the same frozen reference expert and one trainable cloned
specialist with its router parameters. Train branches on their respective
data, then assemble the reference plus the independently trained specialists.
The specialist is trainable; the common reference is frozen. Keep shared
embeddings, head, normalization and non-expert backbone parameters identical
and frozen in the initial HRM experiment so branches remain composable.
Frozen weights do not imply no-grad execution: retain activation gradients
where required by downstream trainable components and the selected BP policy.

FlexOlmo uses a frozen public model as an anchor and domain-informed router
embeddings trained independently and assembled at merge time; see the
[primary paper](https://arxiv.org/abs/2507.07024) and
[Ai2 description](https://allenai.org/blog/flexolmo).
Our metadata-logit-bias recipe is a proposed adaptation, not a claim about
FlexOlmo's exact algorithm. Preserve a common reference-router score across
branches: independently learned pairwise softmax probabilities alone do not
guarantee calibrated competition among all specialists after merging.
Compare assembled routing before and after optional router-only calibration,
and test bias-free deployment, expert removal and mixed-domain inputs.

Start with MLP experts to minimize shared-interface drift. Extending independent
training to whole L stacks is a separate hypothesis: recurrent state and
attention/cache compatibility, especially with per-expert states, must be
validated rather than assumed from FlexOlmo. Neither the reference nor its
combination with specialists automatically guarantees baseline-quality output.
No implementation or live-training change is authorized by this plan addition.

### Comparisons and Acceptance

Test dense baseline, MLP-MoE and MoL separately before combining them. Report
total versus active parameters, actual FLOPs, tokens/second, GPU-hours and
peak memory, along with matched-token quality. Measure expert utilization,
routing entropy, specialization and causal expert-ablation effects; no
semantic role is assumed from expert identity. Qualify FSDP/DDP unused
parameters, GAS, checkpoint/resume and EMA, activation checkpointing,
compilation, native decode, HF export and vLLM support before production use.
Expert parallelism is a later scaling option, not a prerequisite for a small
single-node pilot. No priority relative to the independent Muon trial is
changed by adding these candidates.

## DeltaNet and Gated DeltaNet Token Mixing

DeltaNet maintains a key-value associative matrix per head, updating the
prediction error rather than simply accumulating values. With memory S:

```
S_bar = alpha_t * S_previous
S_new = S_bar + beta_t * (v_t - S_bar @ k_t) @ transpose(k_t)
output = S_new @ q_t
```

Here the final outer product uses column vectors. Alpha is the retention gate;
beta controls the targeted update. Plain DeltaNet omits the decay. This is
runtime sequence state, not optimizer updates to persistent model weights.
Efficient chunkwise kernels avoid naive serial training over tokens.

Test a hybrid retaining full-attention layers for direct retrieval. Fixed-size
sequence memory reduces decode-state growth but compresses history and can
lose independent associations. Do not assume constant total training memory.

Sequence recurrence and HRM depth recurrence are distinct axes. Before any
implementation, specify state ownership per layer/head/H-L invocation,
packed-sequence resets, prefill/decode equivalence and whether state persists
across reasoning cycles. Naively sharing the sequence state across repeated
stack invocations risks double-counting tokens or changing causal semantics.
Our PrefixLM prompt visibility also needs an explicit design: an ordinary
causal DeltaNet is not a drop-in replacement for bidirectional prefix mixing.

Sources: [DeltaNet parallelization](https://arxiv.org/abs/2406.06484),
[Gated DeltaNet](https://arxiv.org/abs/2412.06464).

## Other Qwen Candidates

The specific architectural reference is
[Qwen3.8-Next](https://arxiv.org/abs/2608.30320), not a claim that every Qwen3.8
release uses every component below. Its reported ingredients include sparse
attention, gated multi-branch residuals, off-accelerator n-gram tables, sparse
MoE and Muon-based optimization. Treat reported benefits as source-model
results, not established HRM outcomes.

| Candidate | Potential HRM research question | Main qualification |
| --- | --- | --- |
| Qwen Sparse Attention (QSA) | Can block selection reduce long-context attention costs while preserving retrieval? | Indexer, distillation/adaptation, PrefixLM masks and kernel support |
| N-gram embedding tables | Can lexical capacity be added cheaply outside repeated reasoning blocks? | Host/device bandwidth, prefetching and distributed ownership; loss improvement need not imply benchmark improvement |
| Sparse MoE | Can model capacity grow without proportionally increasing active FLOPs? | Routing and communication costs across recurrent executions |
| Muon | Does optimizer choice improve convergence at matched compute? | Split logically distinct fused matrices; retain appropriate AdamW groups and test recurrence-aware LR policy |
| Multi-token prediction | Could auxiliary future-token supervision and speculative decoding improve efficiency? | Separate training objective and inference implementation; not yet designed for HRM |

All five entries are explicitly retained as optional v2 ideas at the user's
request, not requirements to combine into one design or changes to live training.

### N-gram Capacity and Factual Knowledge

Hypothesis, not an established HRM result: learned n-gram tables could improve
representations of entities, terminology and frequently observed factual
associations, relieving some backbone memorization pressure. They are learned
vectors, not an explicit fact database or retrieval system. They cannot supply
unseen or updated facts and can also reinforce repeated misinformation.
Measure factual QA for frequent versus rare entities, paraphrased questions,
and compositional questions at matched compute, not just training loss.

### Checkpoint-Compatible Warm-In Candidates

October 18 recommendation: for a low-risk first architectural experiment,
warm in single-state gated H/L communication; for a larger capacity experiment,
consider gated multi-state memory. This is an engineering judgment, not evidence
that either delivers the largest quality gain. N-gram augmentation is the more
direct factual-capacity experiment, with potentially significant table and
distributed-update infrastructure costs.

Keep baseline fusion exactly at warm-in factor alpha=0:

```
input_L = z_L + (1 + alpha * tanh(g_L(z_L, z_H))) * z_H
input_H = z_H + (1 + alpha * tanh(g_H(z_H, z_L))) * z_L
```

Use causal, position-local gates; copy existing weights unchanged. Ramp alpha
from zero, preserving the original normalization and stack update rules. Zero
alpha also blocks gate gradients, so do not hold it there expecting gates to
learn. With a zero-initialized final gate projection, avoid also zeroing all
upstream gate features. Verify baseline logits, loss and carry behavior before
training, then compare a continuation control at equal tokens and GPU-hours.

For branched state, specify an exact baseline-emulating read/write rule first;
extra branches alone do not ensure checkpoint compatibility. Warm in a bounded
correction to the baseline path and provide controlled symmetry breaking.
For n-grams, use an additive alpha-scaled projected lookup path. DeltaNet
replacement can be blended with attention but needs new weights trained and
temporarily both mixers executed; it is not the lowest-risk warm-in experiment.
Muon is an optimizer change, not a function-preserving architectural gate.
These suggestions do not alter the previously agreed independent Muon trial
or authorize changes to ongoing training.

### Muon Experiment Requirements

Muon approximately orthogonalizes a momentum-derived matrix update, rather
than constraining the trained weight matrix itself to be orthogonal. Its
matrix geometry differs from AdamW's elementwise second-moment normalization.
Use the [author's explanation](https://kellerjordan.github.io/posts/muon/)
and [reference implementation](https://github.com/KellerJordan/Muon) to pin
the exact variant, momentum convention, shape scaling and weight decay.

Start with hidden attention/MLP matrices on Muon and embeddings, output head,
normalization gains and other unsuitable parameters on AdamW. Establish
logical matrix boundaries explicitly for fused Q/K/V or gate/up weights.
Orthogonalizing arbitrary FSDP-local slices is not equivalent to applying
Muon to the global logical matrix: qualify a distributed implementation or
gather/compute/redistribute strategy, including communication and workspace.

Retune Muon LR independently; existing AdamW numerical LR values and automatic
H/L dividers are not a validated Muon recipe. In particular, ideal polar
normalization removes uniform positive rescaling of an update, but does not
remove the effects of recurrent gradient directions or the need for an
explicit per-module step scale. Compare divider policies experimentally.

Measure convergence per token and per wall-clock hour, optimizer-state and
temporary memory, checkpoint/resume consistency, GAS/distributed parity and
benchmark quality. Treat switching an AdamW-trained checkpoint to Muon as a
separate experiment requiring explicit optimizer-state handling, not a
transparent resume. No optimizer switch is approved for the current run.

User-confirmed experimental ordering: test Muon on the unchanged HRM
architecture first, separately from branching, gating and DeltaNet changes.
The objective is better learning per token or GPU-hour, not repairing an
instability in the currently stable run. Retain a tuned AdamW control and
report optimizer workspace as well as persistent state memory.

## Evaluation Order and Acceptance Gates

1. Establish the stable current architecture's reproducible quality/throughput
   baseline. Record optimizer, LR dividers, BP/H/L cycles and compute budget.
2. Test single-state gated fusion, then 2H/2L branches at matched update rules.
3. Independently test a DeltaNet/full-attention hybrid, including retrieval and
   PrefixLM correctness before large training.
4. Consider sparse attention, lookup capacity, MoE and optimizer changes as
   separate ablations, combining only candidates with measured benefits.

Use multiple seeds where feasible; report both equal-token and compute-aware
comparisons. Include language modeling, instruction following, math, code,
tool use and long-context retrieval. Measure peak training memory, step time,
prefill/decode throughput and cache footprint. Keep architecture configurations
versioned and opt-in. HF export, vLLM/native inference, packed boundaries and
checkpoint/resume parity are acceptance gates, not follow-up polish.
