---
type: Research
title: Applying Embla mechanisms to HRM-Text
description: Mechanism-level efficiency assessment and measurement requirements.
status: draft
last_updated: 2026-11-16
confidence: medium
---
# Applying Embla mechanisms to HRM-Text

The architecture comparisons are described in [Embla experiments](embla-experiments.md).
No HRM architecture or existing run is changed by this assessment.

## Highest-value adaptations

**Grouped-query KV projections** reduce cache memory without removing recurrent
updates. For width1024, eight query heads and head dimension128, changing eight
KV heads to two reduces stored K/V by four. Per logical layer at BF16, 32K tokens
use 128 MiB with eight KV heads versus 32 MiB with two. Forty-eight logical
executions therefore use 6 GiB versus 1.5 GiB, before allocator/metadata overhead.
These are cache-size calculations, not measured throughput or training-memory
reductions. Retraining is required; grouping existing heads is not an exact
checkpoint conversion.

**Local/global attention** bounds local attention work and cache lengths. A
window128 cache is 512 KiB per layer for eight KV heads, or128 KiB for two.
Global layers preserve distant access. HRM's recurrent passes can propagate
local information, but long-range reasoning quality must be evaluated rather
than inferred from theoretical receptive fields.

**KV bridges within a recurrent invocation** can reuse projections across several
attention sublayers, as Embla's sparse decoder does. The producer must precede
its consumers and carry the same document/prompt visibility rules. This is a
real architectural change: consumer queries may differ but the keys/values are
fixed functions of the producer state.

## Recurrence-specific distinction

Reusing KV *across* HRM iterations freezes part of the recurrent state. HRM's
current attention normally recomputes keys and values from updated hidden states.
Fixed caches would change that algorithm, not merely optimize its implementation.
Compare fixed caches, caches refreshed every iteration, and periodic refresh as
separate future ablations; do not label them checkpoint-equivalent.

The new looped Embla experiment intentionally uses fixed encoder-derived decoder
KV. Decoder Q/O, experts, routing and residual mixtures still execute each loop;
KV projection executes once. Training retains gradients from every consumer back
to the cached producer. No additional inverse-loop LR rule is applied.

## Mechanisms requiring measurements

- Squared-ReLU full attention retains quadratic arithmetic; bounded-memory kernels
  remove quadratic storage, not the underlying score computation. Long-context
  viability needs measured prefill time and training throughput.
- Sparse selection itself scores candidate keys. Savings depend on selector reuse
  across sparse layers, top-k size and kernel efficiency. Counting only selected
  softmax attention overstates the saving.
- MoE trades active matrix work for larger weights, routing, dispatch and load
  balancing. B200 grouped GEMM performance and distributed parameter traffic must
  be measured at our batch sizes; phone inference results are not evidence here.
- Engram adds a large trainable table and optimizer state. It may improve lexical
  memory efficiency, but is not a free long-context mechanism and the table does
  not replace sequence context.
- Early decoder prefill is valid only when all decoder KV are derived from the
  first half. For PrefixLM the entire prompt must first be encoded bidirectionally.
  Target-only training still needs every answer prediction; last-token-only
  execution cannot be used for training those examples.

## Required evidence before an HRM follow-up

Measure tokens/s, peak allocated/reserved memory, prefill/decode latency, KV cache
bytes and quality separately. Probe4K/16K/32K/64K/128K/256K, record failures and
OOMs without silently shortening inputs. A successful256K allocation is not
proof of256K reasoning quality. Prioritize GQA plus local/global attention, then
within-iteration KV bridges; keep Engram, MoE and cross-iteration cache freezing
as separately attributable changes. GPU measurements are still outstanding.

## Measured qualification update (2026-11-16)

The first full-size recipe did not fit with GAS1. Residual recomputation,
chunked CE and GAS4 preserved the global batch and architecture while making
nonlooped PrefixLM training fit. The native real-data check measured roughly
12–14s per optimizer step, versus0.3–0.4s in the other architecture smokes.
Thus matrix-FLOP matching does not imply matching elapsed time in the present
PyTorch implementation. A GPU profiler found masked-key gradient scatter
contention (91% of device time); distributing masked destinations fixed the
pathology, but substantial throughput work remains. Do not port this execution
path wholesale into HRM under a claim of improved training efficiency.

Earlier full-dimension inference probes passed32K context for both nonlooped and
looped models. Longer probes hit imposed40s deadlines or the30% allocator cap;
none establish long-context quality or the dedicated-GPU maximum. These results
supersede the blanket statement that all GPU measurements were outstanding;
quality and optimized-kernel throughput remain unmeasured.

## Optimized-kernel follow-up (2026-11-16)

The historical12–14s native timing above is superseded by the
[qualified optimized kernels](embla-optimized-kernels.md): causal/prefix steps
now take about2.99/3.20s, and four-loop steps5.73s in short eight-rank checks.
FA4 windows and fused ReLU²/indexed attention materially narrow the execution
gap. This still does not establish an HRM efficiency or long-context quality
advantage; the mechanisms and model recipes remain distinct.
