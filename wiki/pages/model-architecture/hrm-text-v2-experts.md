---
type: Technical Reference
title: HRM-Text-v2 Expert Mixtures
description: Opt-in reference k-of-n MLP and L-stack mixtures, routing semantics, checkpoint upcycling and qualification boundaries.
status: draft
confidence: high
last_updated: 2026-10-18
tags: [architecture, moe, mos, recurrence, routing]
---
# HRM-Text-v2 Expert Mixtures

Later October 18 update: the dense-only and fresh-optimizer limitations in this
initial reference are superseded by the [extension implementation](hrm-text-v2-implementation.md).
Optional token/sequence sparse dispatch, metadata routing, frozen-specialist
composition and optimizer/EMA-preserving upcycling now exist. Dense reference
semantics below remain available and are still the default for mixtures.

Implements the expert candidates in the [v2 research plan](hrm-text-v2-plan.md).
The existing gate pilot and scheduler are unchanged. Default expert counts
are one: no extra routers, changed backbone keys or expert execution on the
default path. Invocation gates can independently be disabled.

## Configuration

Use `arch/net@arch=hrm_v2` with the normal size/data settings. Examples below
are architecture overrides, not complete production launch commands.

```bash
# Dense 2/2 MLP mixture in L blocks, without injection gates
arch.gates_enabled=false arch.moe_num_experts=2 arch.moe_top_k=2

# 2/4 L-stack mixture, with separate recurrent states
arch.gates_enabled=false arch.mos_num_experts=4 arch.mos_top_k=2 \
  arch.mos_state_mode=separate
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `gates_enabled` | false | Opt into H/L injection gates; supersedes the original gate-on v2 default |
| `moe_num_experts`, `moe_top_k` | 1, 1 | MLP expert count and selected contributions per token |
| `moe_levels` | L | L, H or both |
| `mos_num_experts`, `mos_top_k` | 1, 1 | Complete L-stack expert count and selected contributions per token |
| `mos_state_mode` | shared | Shared or separate L states |
| `expert_freeze_base` | false | Freeze expert 0 and its router parameters in every enabled mixture |
| `router_top1_straight_through` | true | Explicit surrogate router gradient for normalized top-1 |

Validate `1 <= k <= n`. MoE and MoS can be enabled separately or combined.
The automatic L/H learning-rate divisors remain the existing gradient-bearing
invocation counts; they are not corrected for each expert's actual routing
frequency. New routers are shared across invocations and inherit their level's
LR. Gates retain the existing per-invocation LR treatment.

## Execution and Routing

This is a correctness-first **dense-execution reference**, not an optimized
sparse dispatcher. Every expert runs in a fixed order; exactly k output
contributions are selected per token. Thus k<n does NOT reduce expert compute
or KV-cache memory. No tokens are dropped. Dense 2/2 is supported directly.
Non-selected trainable experts remain in the graph with zero task gradients;
optimizer momentum and weight decay can still update them. They are not
implicitly frozen. This differs from skipping unused experts entirely.

Router scores use current token features and FP32 computation, with optional
pre-softmax logit bias. Selected scores are softmax-normalized. Router rows and
biases start at zero without consuming RNG, and expert weights are cloned.
Ties select lower expert indices deterministically. This is reproducible but
not balanced; no load-balancing objective or exploration noise is silently
added. For frozen-reference top-1, initialize routing to give the specialist
traffic; otherwise the tied router initially selects the frozen reference.

For k=1 normalized weights are constant. The default straight-through rule
keeps forward weights exactly 0/1 but uses derivatives of the full softmax on
selected entries. It is a biased surrogate, NOT an exact top-1 derivative.
Set `router_top1_straight_through=false` for the exact, zero task-loss router
gradient. For k>1 the selected-softmax derivative is used without a surrogate.

`TopKRouter.forward(x, logit_bias=...)` accepts broadcastable external biases;
each router also has a checkpointed `logit_bias` buffer. Selection and output
weights use the same biased logits. Per-row dataset metadata is not yet wired
through the production data loader/MLPs. Router hooks can inspect weights;
there is no new automatic W&B utilization logging.

### L States and Attention

MoS routes on `z_L + z_H` token-locally. Each stack processes the COMPLETE
sequence with the original masks and positions, then output contributions are
mixed. This differs from the plan's optional example-level sparse dispatch:
no attention stack sees a token-pruned context. Response routing never pools
future tokens; prefix visibility follows the supplied PrefixLM mask.

Shared state: each expert reads the same L state; the weighted output becomes
the next L state. Separate states: each expert reads its own state; selected
tokens replace their state with that expert's output, inactive tokens retain
their previous state. H reads the weighted selected outputs. All states start
from `zL_init` and reset per forward, as in the baseline depth recurrence.

Caches are allocated per L invocation AND expert. All candidate stacks execute
on decode too, keeping their caches current even when their outputs are not
selected. This is essential for full-sequence/decode equivalence under changing
token-level selection. It is not a sparse-cache implementation.

## Upcycling and Frozen References

`models.expert_mixtures.upcycle_dense_weights(destination, source_state)`
strictly maps dense v1 or gated-v2 weights into cloned experts. It works with
an unwrapped backbone or LMHead state dict. Run before distributed wrapping
and optimizer construction. Missing original weights, unexpected source keys
and shape mismatches fail. New routers retain their initialization; new gates
remain zero for a v1 source.

This is **weight-only upcycling with fresh optimizer/EMA**, not transparent
continuation of dense optimizer state. No production DCP conversion CLI is
provided yet. `gate_initialize_from_v1=true` is rejected when expert counts
exceed one, preventing accidental use of the gate-only migration. Same-layout
expert checkpoints use normal strict checkpoint loading. Changing n, k or
state semantics requires an explicit new experiment/configuration.

Freezing uses `requires_grad=False`, not `no_grad`: activation gradients still
flow through the frozen reference. With both MoE and MoS enabled, the flag
freezes expert 0 at BOTH levels. Shared attention/H/embeddings/head are not
automatically frozen. A fully isolated FlexOlmo-style specialist recipe and
multi-specialist merge/calibration are therefore still future work.

## Verification and Remaining Gates

CPU tests exercise k-of-n selection, pre-softmax bias, frozen-reference input
gradients, upcycling equivalence, strict state round-trips, distinct-expert
cached decoding, causal isolation, low BP, and compilation/activation
checkpointing. Compile with `dynamic=False`, matching `pretrain.py`; automatic
dynamic integer specialization of BP is incompatible with grad-mode switches.
Two-rank CPU FSDP2 passes with per-block wrapping, GAS2, frozen references,
BP2/BP8, optimizer-update parity against an unsharded reference, and a DCP
model/optimizer round-trip. Router biases are one-element parameters, not
scalars, because FSDP2 rejects scalar parameters.

Validation on October 18: 48 tests passed across `test_hrm_experts.py`,
`test_hrm_v2.py`, `test_hrm_v2_schedule.py` and `test_xl_after_xxl_handoff.py`.
OKF validation: zero errors, 15 existing unrelated missing-artifact warnings.

Production CUDA/FA4 throughput and memory, distributed BF16 qualification,
full-size expert runs and expert-aware HF/vLLM export remain release gates.
Existing v2 HF export rejection stays in place. Do not send expert checkpoints
through the dense v1 exporter or describe this reference as sparse acceleration.

Code: `models/expert_mixtures.py`, `models/baselines/hrm_v2.py`,
`config/arch/net/hrm_v2.yaml`, `tests/test_hrm_experts.py`.
