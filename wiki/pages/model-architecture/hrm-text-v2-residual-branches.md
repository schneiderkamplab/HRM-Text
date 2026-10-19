---
type: Technical Reference
title: HRM-Text-v2 Residual Branches
description: Optional multi-stream residuals inside H and L transformer stacks, baseline-equivalent defaults and qualification limits.
status: draft
confidence: high
last_updated: 2026-10-19
tags: [architecture, residuals, recurrence, branches]
---
# HRM-Text-v2 Residual Branches

## Combined pilot scheduled October 19

User selected two internal residual streams in both stacks plus two H and two
L recurrent memory branches, rather than testing them individually first.
`scripts/schedule_hrm_branch_pilot.py --install` added
`hrm-branches-memory-XL-from-3800000` to the existing SQLite campaign, after
the full three-arm 3.82M evaluations and before ordinary XL 3.82M -> 3.85M.
The pilot starts from the original transferred 3.8M checkpoint, stops at
3.82M, and uses a separate same-named DFM5 W&B run and directory under
`checkpoints/hrm_v2/`. Main continuation still uses the ungated control.

Settings: input-dependent residual mixing, write-init scale 0.1, residual and
memory alpha 0 -> 1 during 3.8M -> 3.802M; invocation gates off; no MoE/MoS.
Base LR 1e-5 with automatic module division, BP8, GAS2, global batch 262144,
DFM15 and the control's optimizer/EMA-preserving dense-upcycling path.
CPU preflight validated Hydra/Pydantic configuration and full-size source
tensor mapping. GPU peak memory, compilation and training stability remain
to be measured on launch; this was queued, not immediately launched.
Pilot failure does not block the normal continuation (terminal-only barrier).
Downstream evaluation of this new fourth checkpoint is not yet scheduled.
A null combined result does not conclusively rule out either feature alone.

Later October 18 update: optional input-dependent read/write mixing and separate
H/L recurrent memories are now implemented. The static-only/pending statements
in this initial reference are superseded by the [extension record](hrm-text-v2-implementation.md).
Within-stack residual branches and cross-invocation memories remain distinct.

User request, October 18: prepare m residual branches, restricted to HRM v2.
This implementation keeps multiple residual streams **within each transformer
stack invocation**. It does not create persistent H/L recurrent memory branches
or run m copies of attention. The [v2 plan](hrm-text-v2-plan.md) separately
retains those experiments, and [MoS](hrm-text-v2-experts.md) independently
controls the number of L stacks and their recurrent states.

## Baseline Default

Supersedes the original gate-on v2 default: `arch/net@arch=hrm_v2` now defaults
to gates disabled, one MLP expert, one L stack and one residual branch. It
allocates no gates, gate buffers, routers or branch parameters in that mode.
It directly calls the v1 forward implementation. The YAML also matches v1's
BP5 / 0.2 warmup defaults and H override/Goldfish settings. Changing only the
architecture selector preserves initialization RNG, parameter/state names,
forward/backward behavior and optimizer geometry.

The gate pilot command generator now explicitly sets `arch.gates_enabled=true`
and its existing BP8 / zero BP warmup overrides. This does not alter the live
process. Existing persisted scheduler commands are not rewritten by changing
the generator; any restart of the old gate pilot must include the explicit
flag. V2 DCP loading refuses unexpected feature tensors instead of silently
discarding gates/experts/branches when they are disabled. The gate probe opts
in explicitly, including for early checkpoints with no `gates_enabled` field.

## Configuration

```bash
arch/net@arch=hrm_v2 \
arch.residual_branches=4 \
arch.residual_levels=both
```

| Setting | Default | Purpose |
| --- | --- | --- |
| `residual_branches` | 1 | Number of streams m; m=1 installs no branch modules |
| `residual_levels` | both | H, L, or both |
| `residual_alpha_max` | 1 | Maximum branch-mixing strength |
| `residual_warmup_start_step` | 0 | Absolute start of optional mixing warmup |
| `residual_warmup_steps` | 0 | Linear warmup duration; zero enables full strength at training setup |
| `residual_write_init_scale` | 0.1 | Deterministic initial write asymmetry |

Branch strength is checkpointed per stack and updated by
`compute_train_extra_args`, including every MoS stack copy. Fresh native models
start at alpha=0 until that setup method is called. Loaded checkpoints use
their saved alpha. Separate from invocation-gate alpha and warmup.

The first implementation supports **pre-norm only** for branched levels.
Post-norm configurations fail early rather than silently change normalization.
The unbranched path continues to support the original norm settings.

## Read, Update, Write

Each stream has width d. Starting from the stack input x, create m copies.
Before each attention/MLP sublayer, read a per-channel normalized mixture:

```text
read_weights = softmax(alpha * read_logits, over branches)
input = sum_j read_weights[j] * streams[j]
update = sublayer(norm(input))
write_weights = m * softmax(alpha * write_logits, over branches)
streams[j] = streams[j] + write_weights[j] * update
```

Attention and MLP each execute once per block. They have independent read/write
parameters. At stack exit, a learned normalized per-channel readout combines
streams before the original final normalization. Streams then cease to exist;
the combined output is the normal d-wide recurrent state.

These read/write parameters are static across tokens and input-dependent only
through the streams they mix; they are NOT the earlier input-dependent H/L
injection gates. Parameters are shared across recurrent invocations of a stack.
They inherit the level's recurrence-aware learning rate.

Read logits and final-readout logits initialize to zero. Write logits favor
one stream slightly, rotating across sublayers, without consuming RNG. Writes
have mean weight one. Consequently, initial uniform reads reproduce the dense
stack algebra while the streams acquire different representations. Read
parameters can then learn nonuniform mixing. At alpha=0 all streams remain
equal. Holding alpha at zero also blocks new mixer gradients.

For m>1, baseline equivalence is numerical rather than bitwise because of
different reductions and rounding, especially in BF16. Exact default parity
comes from leaving m=1 on the original implementation. No extra transformer
weights are cloned for branches; mixer parameters add `4*m*d` per block plus
`m*d` for the stack readout. Residual storage and mixing bandwidth increase
with m even though attention/MLP invocation counts and KV-cache dimensions do
not. No measured GPU speed or memory claim yet.

## Composition and Migration

MoE can replace the MLP inside a branched block. MoS can clone a branched L
stack, with its own mixer parameters. The number of residual branches is not
the number of experts. Existing attention masks, sequence positions and cache
layout are preserved. Branched blocks/cores retain the TransformerBlock and
Transformer types used by FSDP wrapping and activation checkpointing.

`upcycle_dense_weights` accepts dense v1 or gated-v2 weights, preserves original
backbone keys, and initializes only the new branch modules. This is an explicit
weight-only operation before wrapping/optimizer creation, with fresh optimizer
and EMA. The gate-only `gate_initialize_from_v1` migration rejects branching.
Same-layout checkpoints use normal strict model loading. Existing v2 HF/vLLM
export rejection remains; branch-aware serving needs separate qualification.

## Validation

CPU tests cover m=1/2/3/4, alpha=0/1 initial forward/backbone-gradient parity,
asymmetric streams, one attention call per layer, level selection, alpha
schedule, learned mixing, causal decode-cache parity, optimizer round-trip,
compilation and activation checkpointing. Compilation uses `dynamic=False`,
as production training does. The exact-default test compares v1/v2 optimizer
and EMA updates at BP2, BP5 and BP8 with zero tolerance.

October 18 final regression run: 70 tests passed across residual branches,
expert mixtures, invocation gates, pilot scheduling and XL handoff tests.
Two-rank CPU FSDP2 coverage includes three residual branches combined with
MoE/MoS, frozen references, GAS2, BP2/BP8, optimizer-update parity and DCP
round-trip. The disabled-gate DCP test confirms that old gated checkpoints
cannot silently load as the new default. OKF validation has zero errors and
15 existing unrelated missing-artifact warnings.

Production CUDA/FA4 and BF16 memory/throughput remain untested. This change
does not authorize a new experiment or modify the running gate pilot.

Code: `models/residual_branches.py`, `models/baselines/hrm_v2.py`,
`tests/test_residual_branches.py`.
