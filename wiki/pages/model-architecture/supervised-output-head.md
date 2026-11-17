---
type: Experiment
title: Supervised-position output heads and Embla performance follow-up
description: Skip ignored output projections without changing the training objective, with matched before/after measurements.
status: draft
last_updated: 2026-11-16
confidence: medium
---
# Supervised-position output heads

The final vocabulary projection and cross-entropy need only positions whose
labels contribute to the loss. Context tokens still traverse every transformer
or recurrent block and retain their influence on supervised predictions. This
is an implementation optimization, not a change to target-only supervision.
The user explicitly approved it for standard and looped Embla and requested
before/after target-only benchmarks for Transformer48 and B.

Embla uses `arch.embla_target_head_only`; the shared HRM/Transformer `LMHead`
uses `arch.target_head_only`. Both default false for compatibility. The shared
head applies Goldfish masking before selecting positions, preserves packed
sequence metrics and distributed valid-token normalization, and retains full
logits for inference. Its data-dependent compaction is outside Dynamo; CUDA projection/loss is compiled dynamically;
the core retains its configured compilation. Empty local supervision contributes
zero loss/gradients safely. Embla supports the same ignored-label compaction and
keeps its softcap and metrics intact.

CPU tests cover loss, metric and parameter-gradient parity, ignored labels,
all-ignored batches, Goldfish masking, and inference. The combined suite passes
71 tests. GPU before/after qualification completed under
`logs/diagnostics/embla/round2-qualification/`.

## Compute accounting

The old frozen256-batch sample has66,905,390 shifted token positions, of which
23,242,578 (34.74%) are supervised under target-only masking. Removing head work
for the remainder reduces modeled Embla matrix FLOPs. Against the **historical
all-position-head Transformer48 ledger**, nonlooped PrefixLM Embla changes from
0.9877x to0.7405x; four-loop Embla from1.0051x to0.8403x. This supersedes an
unqualified claim that the previously recorded executed-FLOP match still holds
after the output-head optimization. Architecture dimensions are not silently
resized to consume the saved work. Future fair comparisons should apply the
same optimization where applicable and report actual compute separately from
nominal architecture sizing. Applying the same head saving to the target-only
Transformer baseline changes the estimated ratios to approximately0.8866x for
nonlooped Embla and1.0061x for looped Embla. User clarification: computing irrelevant outputs
is not required for fairness.

Receipt: `logs/diagnostics/embla/round2-target-head-compute.json`. This remains
an engineering matrix-FLOP ledger, not a hardware instruction measurement.

## Other performance candidates

- Batched FA4 varlen local attention caches prompt/document metadata once per
  forward; up to two calls cover bidirectional prompt and causal suffix groups.
  Packed output/gradient tests passed, with4.10x isolated PrefixLM-window speedup.
- ReLU² query tiles32 instead of16 passed parity and improved isolated timings;
  sparse tiles remain32 because larger candidates were slower or exceeded B200
  tensor-memory limits. Failed candidates are recorded in `round2-tiles.json`.
- Stack-free compiled residual mixing was slower for the common single-query
  case (0.78x), though faster for three queries (1.33x). It remains disabled.
- GAS2 and GAS4 are being compared with the same262144 global batch. Any adopted
  GAS change requires packing/epoch-length verification; do not infer fit from
  allocated memory alone.

The campaign requests one temporary cooperative pause, currently326700, and
restores the same Transformer trainer from memory after tests. No second recovery
supervisor is created. Existing qualification history remains under
[Embla optimized kernels](embla-optimized-kernels.md).

## Completed qualification and activation (2026-11-16)

This supersedes the in-progress status above. All 24 pending Embla training
boundaries now select v8 GAS2 configs, with supervised-position heads, batched
FA4 windows and ReLU query tiles32. Residual fusion remains disabled. The queue
includes causal/all-token, standard PrefixLM/target-only and four-loop
PrefixLM/target-only, in that order. Global batch remains262144. Metadata replay
found395170 complete updates and one dropped partial microbatch; finalization
binds the actual epoch-end checkpoint. Eight-rank warm update times were about
2.68s,2.61s and4.69s respectively. These combine several optimizations, not just
the head. Exact live CUDA offload/restore passed two cycles and645 tensor checks.

The shared Transformer/B head remains opt-in, not activated in production.
An initial uncompiled projection/loss trial increased memory and was rejected;
compiling that portion resolved it. Final matched12-update real-data tests used
all eight ranks and the mean of updates7–12:

| Architecture | Full head s/update | Selected head s/update | Peak allocated GiB, full → selected |
|---|---:|---:|---:|
| Transformer48 PrefixLM/target-only |0.2922|0.2572|89.96 →81.65|
| B PrefixLM/target-only, full BP8 |0.2839|0.2684|87.76 →79.45|

B selected-head timings ranged0.245–0.311s in that window; do not substitute its
fastest updates for the matched mean. These are short performance measurements,
not sustained epoch or quality results. Receipts and all timings:
`logs/diagnostics/embla/shared-head-steady-benchmark/throughput.json` and sibling
rank receipts. Original trials remain preserved. The second temporary pause
at326900 ended with the original trainer restored from memory, generation9.
Queue activation receipt: `logs/diagnostics/embla/round2-qualification/queue-activation.json`.
