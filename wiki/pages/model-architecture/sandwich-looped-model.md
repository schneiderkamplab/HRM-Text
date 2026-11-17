---
type: Experiment
title: Single-state sandwich recurrent architecture
description: Single-state sandwich implementation, serving contract, and matched DFM11 experiment.
status: draft
last_updated: 2026-11-15
confidence: high
sources:
  - id: looped-part1
    resource: https://arxiv.org/abs/2610.23036
    title: 'Towards Looped Models Done Right, Part I: Topology, Input Injection, Recurrent-State Design'
---
# Single-state sandwich architecture

The user requested implementation and a queued experiment on 2026-11-15.
The selected variant is the paper's input-initialized, prelude-conditioned
single-state sandwich (`dense_middle_prelude_injection`), adapted to the
existing B-width comparison. Reference code: [ifm-ai/xllm-loop](https://github.com/ifm-ai/xllm-loop),
commit `755c7b3a91081fe0f83500eabd53bd2490b8b745`. This is an independent
implementation of the published equations using the repository's existing blocks.

## Architecture contract

Compute the prelude once, initialize the recurrent state to its output, then
inject that same prelude output before every core iteration. After the last
iteration, apply the coda and one final parameterless RMSNorm. No extra
normalization or detach is inserted between core iterations.

`state <- exp(-dt * exp(A_log)) * state + dt * W(prelude)`

Here `dt = softplus(dt_bias)`. W starts as identity; dt and A start at one.
All injection parameters train. Full backpropagation traverses all iterations.
The native implementation is `models/baselines/sandwich.py`, selected by
`arch/net@arch=sandwich`; the B preset supplies width1024 and8 heads.
The split is P3 / R6 repeated7 times / C3:12 resident blocks,48 block executions.
There are166723584 block parameters,1050624 injection parameters,
268435456 embedding and268435456 head parameters:704645120 total.

This matches the comparison's block-execution budget, not exact FLOPs or runtime:
seven injection projections add work. The paper uses a different P8/R12x8/C8
shape, GQA backbone, normalization/embedding/init details, optimizer, dataset,
sequence length and schedule. This experiment retains HRM-Text gated MHA,
parameterless norms, RoPE10000, LeCun initialization and scaled embeddings.
It is an architecture comparison, not a paper reproduction or claimed optimum.

## Serving and verification

Packed exports use `SandwichForCausalLM` with explicit depth fields and logical
layer count. The vLLM adapter allocates a distinct KV cache per logical block
execution while sharing core weights. It supports unquantized TP1/PP1 causal
or PrefixLM inference. Generic HF split-weight inference and MixedLM are not
implemented for this architecture and are rejected explicitly.

Serving uses the existing plugin wrapper, eager execution, disabled prefix
caching and disabled chunked prefill. This matches the established PrefixLM
serving contract. Full-size memory and throughput remain unmeasured; small
smokes do not establish their values.

Verification and scheduling receipts live in
`logs/diagnostics/sandwich-20261115/` and
`logs/scheduler/dfm11_architecture_comparison_20261110/sandwich-20261115/`.
Verification completed:

- 21 CPU regression tests passed: explicit unroll and full-gradient comparison,
  injection initialization, export validation, existing attention adapters and
  final-checkpoint accounting. Dependency deprecation warnings are pre-existing.
- Three small compiled CUDA optimizer updates passed with finite gradients
  throughout; peak allocated150898688 bytes.
- Actual vLLM cold-prefill plus cached generation for three simultaneous prompts,
  three tokens each: all nine greedy tokens match the FP32 native reference.
  With nontrivial injection weights, maximum absolute log-probability error was
  0.0034628 (BF16 serving; fixed tolerance0.04).
- Real pretrain/FSDP small-profile CUDA suspension: two offload/restore cycles,
  zero retained GPU memory while offloaded, exact final weights, optimizer/EMA
  and per-step metrics against uninterrupted training. This was a one-GPU
  functional test, not an eight-GPU capacity qualification.
- Whole-plan dry run:17632 new rows, no missing paths, no artifact collisions.
- Wiki validation retains the prior one oversized-page error and14 unresolved
  link warnings; no new wiki regressions.

The standalone serving smoke must use the scheduler's environment:
`VLLM_USE_FLASHINFER_SAMPLER=0 FLASHINFER_DISABLE_VERSION_CHECK=1`, plugin
PYTHONPATH, and `VLLM_WORKER_MULTIPROC_METHOD=spawn`. Without the sampler setting,
FlashInfer attempts a compiler-dependent JIT (and fails if nvcc is absent from
PATH). Production scheduler serving already sets these sampler flags.

## Experiment recipe and queue

Run ID: `sandwichB-dfm11-prefixlm-targetonly-epoch1`.
One DFM11 epoch, PrefixLM, target-only loss, seed0, batch262144, GAS1,
AdamATan2 LR3e-4,5000-step warmup then flat LR, LR-auto disabled, full BP.
The objective is the default chosen to compare with the strong Transformer
PrefixLM/target-only run. It uses the same sampled epoch and training recipe.

`scripts/schedule_dfm11_sandwich.py` prepares an append-only SQLite transaction
after the final Transformer MixedLM evaluation block. Existing queue order and
claimed definitions are preserved. New boundaries are50K,100K,150K,200K,250K,
300K,350K and epoch1, each with the complete existing evaluation block.
The393732 final-step estimate is rebound to the actual exhausted checkpoint
step by `finalize_transformer48_epoch.py`; no sampled data is truncated.
Consecutive boundaries retain the same trainer via CUDA offload/resume; the
existing recovery supervisor supports disk fallback. Paths, IDs, exports,
checkpoints and W&B logging are isolated from prior experiments.

Related: [objective ablations](../current-state/2026-11-14-dfm11-objective-ablation.md),
[queued MixedLM experiments](../current-state/2026-11-15-dfm11-mixedlm.md).

## Queued state verified on 2026-11-15

The transaction completed:17632 new rows (eight boundaries and their evaluation
blocks). Readback verified all141144 prior job definitions unchanged, all eight
new train markers pending, correct terminal dependencies, no barrier/teardown
gates, and no administrative lock. The first marker waits on the final
Transformer MixedLM block; later markers use this run's own preceding block.
The Transformer PrefixLM100K→150K training remained running.
`receipt.json`, `readback.json`, the SQLite backup and `additions.tsv` in the
schedule receipt directory record the actual installed plan. W&B project is
`DFM5`; the new run appears when training starts, not merely when queued.

Parameter comparison verified from actual configurations on 2026-11-15: ordinary
B has166723584 backbone and703594496 total trainable parameters; Sandwich B
has167774208 backbone and704645120 total. Both have268435456 embedding and
268435456 output-head parameters. The1050624 difference is entirely injection
(about0.1493% of B total); recurrence adds executions, not distinct block weights.

## Queue priority revised on 2026-11-15

The user superseded the earlier placement after MixedLM: complete all remaining
Transformer48 PrefixLM/target-only boundaries first (the100K→150K boundary
was already running), then the entire Sandwich B PrefixLM/target-only epoch.
After Sandwich, preserve the other runs' prior relative order: B causal
all-token/target-only rotation, Transformer48 causal/target-only, then the
B/Transformer MixedLM rotation. Evaluations remain between all boundaries.

The reorder updated only unclaimed pending training markers and their dependency
edges. Same-run boundaries retain in-memory CUDA resume; cross-model disk
handoff metadata now names the actual preceding unfinished run. Completed
predecessor epochs need no suspended-trainer handoff. Full graph validation and
changed-job path preflight passed. Readback verified the running trainer's
unchanged definition, the exact changed-row set, and no administrative lock.
Backup, old/new order and transaction receipts are in
`logs/scheduler/dfm11_architecture_comparison_20261110/reorder-prefix-sandwich-20261115/`.

### Subsequent insertion: Ouro after Sandwich (2026-11-15)

The user's next request supersedes the immediate post-Sandwich handoff described
above: the complete [fixed-loop Ouro experiment](ouro-fixed-loop.md) now runs
between Sandwich's final evaluation and B causal/target-only100K→150K.
Transformer PrefixLM retains first priority; the remaining relative order is
unchanged. The Ouro page contains the installed transaction/readback evidence.
