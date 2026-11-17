---
type: Experiment
title: Fixed-loop Ouro-style Transformer on DFM11
description: Matched four-loop architecture, final-loop target-only loss, and insertion after Sandwich B.
status: draft
last_updated: 2026-11-15
confidence: high
sources:
  - id: ouro-paper
    resource: https://arxiv.org/abs/2510.25741
    title: Scaling Latent Reasoning via Looped Language Models
  - id: ouro-release
    resource: https://huggingface.co/ByteDance/Ouro-1.4B/blob/574fa66cb8bf5abdc979642d01cf2b79b16bfab1/modeling_ouro.py
    title: ByteDance Ouro-1.4B released implementation
---
# Fixed-loop Ouro-style Transformer

On 2026-11-15 the user requested an Ouro-style architecture and an experiment
immediately after Sandwich B. They explicitly selected **fixed four loops with
the matched final-loop objective**, rather than the paper's adaptive-exit and
multi-loop loss. This page describes that adaptation, not a full Ouro reproduction.

## Architecture and objective

Native class: `models/baselines/ouro.py:Ouro`, selected with
`arch/net@arch=ouro`, `arch/size@arch=B`. Twelve physical blocks at width1024,
eight heads, are reused four times:48 logical block executions. There is one
state, initialized from token embeddings. No input injection, prelude/coda,
learned exit gate, intermediate-loop loss, or truncation of backpropagation.

The released implementation was inspected at revision
`574fa66cb8bf5abdc979642d01cf2b79b16bfab1`; source snapshots are under
`logs/diagnostics/ouro-20261115/reference/`. Each block applies learned RMSNorm
before attention and before the FFN, and separately to each sublayer's output
before residual addition. One shared learned RMSNorm is applied after each full
stack pass; this normalized state is fed into the next loop. The four block
norms and loop norm are shared across loops along with the block weights.
This normalization arrangement is separate from the Sandwich architecture's
prelude/core/coda topology.

For comparison with existing runs, retain HRM-Text gated MHA, scaled embeddings,
LeCun initialization, RoPE10000, SwiGLU and the existing tokenizer. These differ
from some released Ouro details. The block-execution count is matched; exact
FLOPs, runtime and optimizer dynamics are not asserted identical. Learned
normalization adds50176 parameters over ordinary B, for703644672 total:
166773760 backbone,268435456 embeddings,268435456 LM head.

PrefixLM attention is bidirectional within each prompt, causal for answer
queries, and isolated across packed examples. Only answer labels contribute to
cross-entropy, at the fourth loop, using the existing LMHead loss normalization.
All four loops receive gradients through the recurrent computation.

## Export and serving

`conversion/convert_to_hf.py` writes a packed `OuroFixedForCausalLM` export with
explicit physical depth, recurrence and logical depth. This distinct class avoids
confusion with vLLM's released-checkpoint `OuroForCausalLM`. The plugin in
`evaluation/vllm_plugins/ouro_fixed_vllm.py` uses distinct KV caches for each
logical block execution and shared layer weights. It loads learned norm weights
as well as attention/MLP weights. No approximation via cross-loop KV sharing.

Initial supported serving scope is unquantized TP1/PP1, causal or PrefixLM,
eager mode, disabled prefix caching and chunked prefill. Generic HF split exports
are rejected. Small compiled GPU training and actual multi-request cached
serving are verified before queue insertion. Full-size memory/throughput are
not yet measured; small smokes do not establish production capacity.

## Experiment and placement

Run ID: `ouroB-dfm11-prefixlm-targetonly-epoch1`, W&B project `DFM5`.
DFM11 sampled epoch0, one epoch, seed0, batch262144, GAS1, AdamATan2,
LR3e-4 with5000 warmup steps then flat, LR-auto disabled, full BP. Checkpoints,
exports, control roots and W&B identifiers are isolated from all existing runs.

`scripts/schedule_dfm11_ouro.py` inserts eight boundaries at50K,100K,150K,
200K,250K,300K,350K and epoch end, with the full existing eval blocks.
The final-step estimate393732 is rebound to the actual exhausted checkpoint,
not enforced as a data cutoff. CUDA offload/resume preserves one continuous
trainer across evaluation pauses. The first boundary depends on Sandwich's
final eval work/aggregates in terminal mode; Sandwich's previous pending
successor is rewired to Ouro's final block. The remaining queue order is retained.

Receipts: `logs/scheduler/dfm11_architecture_comparison_20261110/ouro-20261115/`.
Verification: `logs/diagnostics/ouro-20261115/`.

Related: [Sandwich B](sandwich-looped-model.md),
[objective ablations](../current-state/2026-11-14-dfm11-objective-ablation.md).

## Verification results (2026-11-15)

- 24 CPU tests passed, including independent untied unroll with summed gradients
versus shared weights, no future-answer leakage, final-loop target-only loss,
invalid-depth/export rejection and existing architecture/export regressions.
- Three compiled CUDA optimizer updates passed with finite gradients; peak
allocated150353920 bytes in the small fixture.
- Actual vLLM multi-request prefill plus three cached generated tokens for each
of three prompts: all nine greedy tokens match native FP32 inference. Learned
norm weights were perturbed from one to exercise their export/loading.
Maximum absolute log-probability error0.0155273, below the fixed0.04 tolerance.
- The real pretrain/FSDP small one-GPU profile completed two CUDA offload/restore
cycles with zero retained GPU memory while offloaded. Final model weights,
optimizer/EMA and every per-step metric match uninterrupted training exactly.
- Whole-plan dry run passed:17632 new jobs, one existing pending successor gate,
no missing paths, no artifact collisions and no dependency cycles.
- Wiki conformance retains the existing one oversized-page error and14 unresolved
link warnings; no new documentation regressions.

The serving smoke uses the scheduler's native-sampler settings
`VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1` and
`VLLM_WORKER_MULTIPROC_METHOD=spawn`, with the plugin path exported.

## Installed queue verified

Insertion completed on2026-11-15:17632 new jobs, all eight Ouro train markers
pending, and only the existing `btarget-dfm11-step_150000-train` gate changed.
All other158775 prior definitions remained unchanged. Database dependency
readback confirms Transformer PrefixLM through epoch1 → Sandwich through epoch1
→ Ouro through epoch1 → the remaining runs in their prior relative order.
The active Transformer150K marker was unchanged and no administrative lock was
left. Full graph/path validation, transactional backup and readback receipts are
in the schedule directory above. W&B creates the run when training starts.
