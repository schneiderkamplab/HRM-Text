---
type: Technical Reference
title: HRM v2 Opt-in Implementation and Qualification
description: Architecture switches, state-preserving upcycling, metadata routing, specialist composition and Muon boundaries.
status: draft
confidence: high
last_updated: 2026-10-20
tags: [architecture, recurrence, experts, optimizer, testing]
---
# HRM v2 Opt-in Implementation and Qualification

## EMA load preservation verification (October 19)

The shared `AdamATan2.load_state_dict` override saves incoming EMA tensors
before PyTorch's parameter-dtype casting and restores them in the configured
EMA dtype afterward. This is not v2-only. CPU spot checks verified exact EMA
values and the subsequent parameter/optimizer update for FP32 parameters with
default EMA dtype and BF16 parameters with explicit FP32 EMA. The command
`python -m pytest tests/test_v2_extensions.py -k 'upcycl or roundtrip' -q`
also passed all eight selected tests (including distributed upcycling).
This supports the current same-layout resume paths, not arbitrary optimizer
group reordering, changed sharding layouts or custom load hooks. Loading adds
temporary EMA copies; it does not add per-step copies or recover precision
already lost in a checkpoint. Current FP32-parameter/FP32-EMA runs should
retain the same EMA values as the ordinary loader.

Serving execution limits are documented in the [Mimir2 vLLM reference](mimir2-vllm.md#eager-and-sparse-execution-limits-2026-10-19):
sparse MoS currently requires eager, dense MoS and no-MoS do not; vLLM MoE
currently computes every expert and masks outputs rather than using optimized
sparse kernels. Do not infer sparse speedups from `moe_sparse=true` in serving.

## Scope

This implements the October 18 extension request from the
[v2 plan](hrm-text-v2-plan.md). No running pilot, scheduler, checkpoint, data
directory or W&B run was modified. Qualification here is CPU and two-rank Gloo;
production B200 speed/memory and long training quality remain unmeasured.

The default `config/arch/net/hrm_v2.yaml` disables gates, experts, memory branches,
residual branches and n-grams. Default forward delegates directly to v1, with
the same state keys, initialization RNG, gradients, AdamATan2 updates and EMA.
Selecting Muon is a separate training option, not part of the default.

## Switches

All architecture options below are under `arch` and present in the v2 YAML.

| Feature | Opt-in settings |
| --- | --- |
| Gates | `gates_enabled=true`; existing gate alpha warmup |
| Sparse token MLP dispatch | `moe_num_experts=N moe_top_k=K moe_sparse=true` |
| Sparse complete-sequence L stacks | `mos_num_experts=N mos_top_k=K mos_sparse=true` |
| Sparse sequence routing | `mos_sparse_routing=first_token` or `prefix_mean` (PrefixLM only) |
| Metadata bias | `moe_metadata_bias` / `mos_metadata_bias`: category-indexed arrays of N logits |
| Bias decay | `routing_bias_decay_start`, `routing_bias_decay_end`; zero end means constant bias |
| Frozen-reference specialist | `expert_freeze_base=true specialist_training=true` |
| Router-only calibration | `specialist_router_calibration=true` |
| H/L recurrent memories | `h_memory_branches=M l_memory_branches=M` |
| Recurrent-memory warm-in | `memory_warmup_start_step`, `memory_warmup_steps` |
| Dynamic within-stack residuals | `residual_branches=M residual_input_dependent=true` |
| N-grams | `ngram_orders=[2,3] ngram_buckets=4096` |
| N-gram warm-in | `ngram_warmup_start_step`, `ngram_warmup_steps` |
| Dense-state migration | `upcycle_from_dense=true` |

Warmup starts are absolute optimizer steps. Set them to the continuation boundary
for a warm-in, not zero on an already-trained checkpoint. Effective alphas are
checkpoint buffers. New modules initialize without altering the default model.

## Migration

`models/v2_checkpoint.py` supports dense-to-v2 expansion from DCP and unsharded
checkpoints through the regular `pretrain.py` resume path. Destination expert
keys map to their original dense matrices. Every inherited optimizer slot,
including `step`, momentum/second moments and `param_ema`, is cloned. Copies do
not alias one another. New routers/gates/memory/n-gram parameters keep fresh
state. Run-config LR settings remain authoritative. Missing original weights,
slots and shape mismatches fail rather than silently resetting training.

`models.expert_mixtures.upcycle_training_state` provides the same operation for
CPU model/optimizer objects. The older `upcycle_dense_weights` helper is only
for deliberate weight-only operations and tests, not training continuation.
This supersedes earlier fresh-optimizer/fresh-EMA guidance for upcycling.

Legacy numeric optimizer IDs are supported for the repository's single ordered
parameter group. Ambiguous multi-group numeric layouts are rejected. Named
optimizer state is preferred. A normal v2 checkpoint with matching keys is
resumed normally even if the migration flag was left enabled. Switching optimizer
families is not a transparent resume and is rejected by the training loader.

The BF16-parameter migration test exposed PyTorch's generic optimizer loader
downcasting FP32 EMA slots. `AdamATan2.load_state_dict` now preserves incoming EMA
before that cast, honoring an explicitly configured EMA dtype. Muon inherits
this behavior. This fixes checkpoint loading, not live in-memory training; no
running process or historical checkpoint was modified.

## Sparse Execution

MLPs gather selected tokens and scatter weighted expert outputs. No capacity
limit or overflow dropping is applied. All experts are called in fixed order;
an empty expert receives a zero-length tensor and obtains zero gradients.
Variable-size dispatch is outside compiled graphs; inner models can still be
compiled/checkpointed. This prioritizes correctness, not a fused-kernel claim.

Sparse MoS routes each complete packed example using its original first-token
embedding, independent of later answer tokens. It preserves positions, PrefixLM
prefix/causal lengths, sequence boundaries and complete attention contexts.
It does NOT route individual tokens through attention stacks. Each inactive
expert executes one zero-contribution dummy sequence to maintain collective
order across FSDP ranks. This costs something, but not a full unselected batch.
It may limit specialization when examples share the same first token; metadata
bias can distinguish training domains. For PrefixLM, opt into `prefix_mean` to
pool original instruction-prefix embeddings, excluding every response token.
This supports content-dependent routing even with a common BOS token and is
rejected for causal-only attention, where it would expose future prefix tokens.

The original dense MoS mode remains token-local full-context output mixing.
Thus sparse and dense MoS routing are different policies, although identical
upcycled experts emulate the same initial model. Superseded (2026-10-19): sparse
MoS originally required packed metadata and rejected KV-cache serving. It now
supports batched native cached inference with per-cache-slot fixed prompt
routes, including slot reuse, plus Transformers cached/beam generation and
eager vLLM serving. Native packed training preserves zero-contribution dummy
execution for idle experts to maintain distributed collective ordering.
New v2 HF/vLLM export was deferred as of 2026-10-18.
The HF portion is superseded on 2026-10-19 by the separate
[Mimir2 Transformers implementation](mimir2-transformers.md), with strict
consolidated-weight conversion and CPU parity tests. Production export guards
remain intact. The blanket vLLM deferral is superseded by the later
[Mimir2 vLLM integration](mimir2-vllm.md); full-size qualification and the
explicitly unsupported serving features remain deferred.

Use transformer-block FSDP wrapping for features that access parameters outside
the H/L module forward (gates, stack routers and recurrent memories). Incompatible
recurrent-level wrapping is rejected. Distributed validation does not establish
performance on large or multi-node mixtures.

## Metadata and Specialists

October 20 addition: `+data.routing_categories=true` passes per-token source
labels in otherwise unchanged packed batches. Unlike homogeneous sampling,
this does not reorder data or change the resume cursor. It is used by the
[biased MoE/MoS pilots](biased-expert-pilots-20261020.md), with a pinned sidecar.
The default remains off; the homogeneous sampler protections below remain.

Enable `+data.homogeneous_categories=true` only on v2. Each sampled `epoch_N`
must contain an aligned integer `category_id.npy`. The deterministic sampler
round-robins category-homogeneous global microbatches while preserving sampled
row order within a category. It uses a virtual consumed-row cursor, replayable
without reading token contents. Categories with fewer examples than world size
can lose their final incomplete global batch, as empty ranks are not trained.
Do not change sidecars, category meanings or seed during a resume. Changes to
sampler mode/world size/local microbatch size require an epoch boundary.

`scripts/build_routing_categories.py DATASET TOKEN_RANGES.json` builds immutable
sidecars from source token ranges, checks instruction/response ownership, and
refuses to replace existing sidecars. It does not infer domain labels or rewrite
the production sampled dataset. Input ranges refer to `tokens.npy` offsets.

Metadata produces additive logits BEFORE top-k selection and softmax. It is
passed explicitly through the forward, so activation-checkpoint recomputation
uses the same bias. Bias decays linearly if configured, and is disabled in eval
mode. No mutable global routing context or answer-derived metadata is used.

Independent specialists freeze the entire common backbone, embeddings/head,
reference expert and reference-router row. Only non-reference expert parameters
and router rows train. Frozen weights still propagate activation gradients.
The first composition implementation supports MoE OR MoS, not nested mixtures.

`models.specialists.compose_specialists(destination, sources, optimizer,
source_optimizers)` assembles N two-expert branches into reference + N specialists.
It requires exact common-reference and optimizer/EMA equality, validates shapes,
and clones specialist weights and optimizer state. Training-only logit biases
must be removed first. CPU full-state objects are required; gather/export before
composition rather than interpreting FSDP-local slices. This is a FlexOlmo-style
experiment, not a reproduction claim or a guarantee of calibrated routers.

Router-only calibration freezes every non-router parameter, including the
reference-router row. Use a bias-free mixed-domain calibration set, and measure
expert usage and quality after composition. No calibration data or GPU run was
created by this implementation.

## Memory and N-grams

### Contextual multi-head memory (October 20)

Opt in with `ngram_heads=4 ngram_contextual_gate=true` alongside
`ngram_orders=[2,3]`. Defaults remain one head and no gate, preserving the
previous implementation and its state layout. Each order concatenates
independently polynomial-hashed, split-width heads, so increasing heads does
not multiply table parameters. Hidden size must be divisible by head count.
The gate is per-channel sigmoid of learned projections of RMS-normalized
token context and retrieved memory. This is a Qwen/Engram-inspired variant,
not an exact reproduction of either architecture. Injection remains before
recurrence, not Qwen's second-layer placement.

Zero tables preserve the initial function even with alpha enabled. Tables
receive gradients once alpha is positive; gate learning begins as tables
become nonzero. Native cached decoding retains the existing explicit
position-reset semantics. CPU tests cover identity, table/gate gradients,
multi-head budget, packed isolation, causality and cached/full parity.

**Qualification update (2026-10-20):** the serving-deferral statements in the
checklist below are superseded by [Engram preparation](engram-preparation-20261020.md):
HF and vLLM implementations and CPU tests now exist. GPU engine parity, CUDA
graph replay and XL memory/time remain unmeasured because all GPUs were busy.
The historical checklist remains the pilot acceptance criteria.

Before scheduling an Engram pilot:

- Extend Transformers config/conversion/model and vLLM cached decoding:
  current serving does not support this variant, and vLLM rejects n-grams.
- Verify checkpoint/optimizer/EMA upcycling, native/HF/vLLM logit parity,
  packed prefill and independent-request decoding.
- Benchmark XL FSDP compiled memory and step time with the proposed tables;
  test checkpoint save/resume before a 20K run.
- Measure per-order/head occupancy and collisions on actual pilot tokens,
  and gate/contribution statistics after warm-in.
- Use the same 3.80M starting state and data as control, absolute 2K warm-in,
  separate outputs, all other experimental features disabled.

At XL width 1536, two orders with 65536 buckets have 201,326,592 table
parameters regardless of head count; contextual query/key projections add
4,718,592. Tables remain GPU-resident. CPU offload is deferred.
No pilot or production configuration was changed.

Recurrent H/L memory branches persist across depth invocations within one model
forward. They are separate from per-expert L states and from within-stack residual
streams. Each update reads a token/channel-dependent branch mixture, executes
the stack once, and performs a warm-in gated replacement. Alpha zero replaces
all branches, emulating v1. H and L are updated independently; general multiple
L branches and separate MoS L states cannot be combined yet.

Dynamic residual-stream mixers add token-local per-channel gain terms to static
branch logits. They still execute one attention and one MLP per layer. No token
pooling or cross-example communication is introduced.

N-grams use trainable hashed tables for configurable orders, added once to token
embeddings before recurrence. Tables are zero-initialized; alpha warm-in controls
their contribution. Position discontinuities reset eligibility, preventing
packed-example leakage. Native caches retain only the required previous token
IDs/positions and are owned by each request cache. No future tokens are read.
Hash collisions are intentional capacity sharing. These are device-resident
parameters; giant host-offloaded lexical tables/prefetching are not implemented.

## Muon

Select top-level `optimizer=muon`; `adam_atan2` remains default. Tunables:
`muon_momentum=0.95`, `muon_ns_steps=5`, `muon_lr_scale=1.0`. Base/module LR and
EMA scheduling still apply. Muon LR is not calibrated by this implementation;
do not silently replace a production optimizer with the same numerical LR.

Hidden G/Q/K/V projections and gate/up projections are split into logical
matrices. Output/down projections are individual matrices. Embeddings, head,
routers, gates and other auxiliary parameters use ordinary AdamW, not Muon.
The optional optimizer therefore deliberately differs from default AdamATan2.
Muon uses Nesterov momentum, quintic Newton-Schulz updates and rectangular shape
scaling following the [author's implementation](https://github.com/KellerJordan/Muon).
Our iteration runs FP32 for correctness-first qualification, not its BF16 kernel.

FSDP gathers each complete logical update, computes the matrix operation, then
redistributes it. It never orthogonalizes arbitrary local shards. This is
communication/workspace-intensive and is NOT an efficient distributed-Muon claim.
Optimizer state, EMA, per-module LR factors and inactive-gate donor updates work
through the existing checkpoint/training interfaces.

## Validation

Final October 18 result: **154 passed**, 29 dependency/checkpoint warnings, in
61.81 seconds. This includes exact default v1/v2 optimizer/EMA equivalence,
FP32 EMA retained on BF16 parameters, DDP-prefixed source checkpoint names and
rank-dependent sparse MoE+MoS dispatch under two-rank CPU FSDP. OKF validation:
zero errors, 15 pre-existing missing local-artifact link warnings.

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 /home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_v2_extensions.py tests/test_activation_checkpointing.py \
  tests/test_hrm_v2.py tests/test_hrm_experts.py tests/test_residual_branches.py \
  tests/test_module_learning_rates.py tests/test_gradient_skip.py \
  tests/test_fsdp_topology.py tests/test_hrm_v2_schedule.py \
  tests/test_xl_after_xxl_handoff.py --disable-warnings --tb=short --show-capture=no
```

Combined compilation and composable activation checkpointing exposed a tensor
recomputation metadata mismatch for some new v2 features. Those feature-bearing
blocks now opt into explicit non-reentrant checkpoint calls, retaining module
names and the existing FSDP block boundaries. V1/default-v2 and the current gate
pilot retain their original checkpoint implementation. The failing cases are
retained as compilation-plus-checkpoint regression tests.

Tests live in `tests/test_v2_extensions.py` plus the existing v2, experts,
residuals, LR and checkpoint tests. Coverage includes default equivalence,
upcycled moments/EMA, sparse token output/gradient parity, packed sparse-stack
context, causal n-gram boundaries and cached decoding, branch warm-in,
metadata bias/sampler resume, specialist freezing/drift rejection, compilation
with activation checkpointing, Muon resume and two-rank CPU FSDP migration.

CPU tests do not certify FA4 sparse-dispatch throughput, CUDA graph behavior,
full-size Muon workspace, distributed expert composition or downstream quality.
Those require separately approved experiments; the live gate pilot is untouched.
