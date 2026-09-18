---
type: Experiment Report
title: PrefixLM Comparative Correctness Results
description: Pinned baseline, existing proposal, and phase-aware prototype comparisons against Transformers on CPU and Apple Metal.
tags: [mimir, prefixlm, llama-cpp, testing, metal, benchmarks]
status: draft
last_updated: 2026-09-17
confidence: high
---
# PrefixLM Comparative Correctness Results

**Follow-up, 2026-09-17:** the [native session runtime](mimir-native-session.md)
now implements the embedded lifecycle policy and applies the replacement
patch to the registered llama.cpp checkout. Statements below about clean
submodules and phase switching only in the comparison runner describe the
earlier experiment; they are superseded for the current working checkout.
The historical comparison artifacts remain unchanged.

## Artifacts and scope

The reproducible harness, lock file, preserved proposal, adapted proposal,
replacement library patch, and compact machine-readable results are in
`scripts/prefixlm_comparison/`. Start with its `README.md`. Full model files,
worktrees, native executables, raw logits, logs, and detailed summaries are
under ignored `logs/prefixlm-comparison/`.

The registered `llama.cpp` and `mimir` submodule checkouts remain clean. No
commits, pushes, PRs, or external comments were made. The replacement patch is
kept as `scripts/prefixlm_comparison/patches/replacement.patch`; its detached
worktree is `logs/prefixlm-comparison/worktrees/replacement`.

This tests a library prototype: the C++ runner implements explicit phase
selection with the existing attention API. The replacement patch adds the
model-capability query retained from bolgacg's proposal and recoverable size
checks before noncausal/logical batch execution. It does not implement server
prompt scheduling, cache policy, state restore, retry, or cancellation changes.
Explicit resets in the harness must not be interpreted as server lifecycle
coverage. Those remain the next implementation stage in the
[patch proposal](llama-cpp-prefixlm-patch-proposal.md).

## Pinned inputs

- Common llama.cpp base: `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.
- Existing [proposal](https://github.com/noctrex/llama.cpp/pull/1):
  `66c7c5ed26b8251a45534ecb9d173275d7ee65a1`, originally based on
  `bc3455a4a9398aad58c3b730c6e061b770677917`.
- Transformers reference: `ff2421c67f35cc83a0fbabbc2633c96734685918`.
- Mimir: `danish-foundation-models/DFM-Mimir` revision
  `2844f0178e695d7d9ce182cb660671fd34c76ce5`.
- Machine: Apple M2 Max, 96 GiB unified memory. Native runners use four CPU
  threads; GPU runs explicitly select the MTL backend and refuse CPU fallback
  when no Metal device exists.

The exact historical proposal has its own worktree/build. For the controlled
three-way comparison, its patch is also transplanted onto the common base;
only metadata enum renames and surrounding diff context are adapted. Tiny
CPU logits from the historical and adapted proposals are bit-identical
(maximum absolute difference 0). All tiny GGUF metadata variants have
identical named tensor-payload hashes.

The isolated Python environment is pinned in `requirements.lock`, including
the Transformers source archive. `prepare.py` records native binary hashes,
patch hashes, harness hashes, host information, and build commands. Each
comparison records its token-case and GGUF hashes.

## Observed results

Counts below are logit/admission check points, not benchmark accuracy scores.

| Suite | Causal baseline | Existing proposal | Replacement prototype |
| --- | --- | --- | --- |
| Tiny HRM, CPU, FP32 KV | 3/26 | 17/26 | 26/26 |
| Tiny HRM, Metal, FP32 KV | 3/26 | 17/26 | 26/26 |
| Tiny HRM, Metal fused attention, F16 KV | 3/26 | 17/26 | 26/26 |
| Real Mimir, Metal, FP32 KV | 0/21 | 18/21 | 21/21 |
| Real Mimir, Metal fused attention, F16 KV | 0/21 | 18/21 | 21/21 |

The tiny replacement additionally passes five relational checks and both
metadata-false/metadata-absent causal controls on each backend configuration.
The exact original proposal also scores 17/26 on the tiny CPU suite.

Maximum absolute replacement logit error against HF:

| Suite | Maximum absolute error |
| --- | --- |
| Tiny CPU | 7.15e-7 |
| Tiny Metal | 6.52e-4 |
| Tiny Metal fused | 6.70e-4 |
| Real Mimir Metal | 0.00650 |
| Real Mimir Metal fused | 0.00532 |

The replacement has 100% top-1 agreement for the tested real-model rows.
Acceptance tolerances were max-absolute `1e-4` for tiny CPU, `0.003` for tiny
Metal, and `0.03` for real Metal. Raw reports also retain RMSE, relative L2,
and top-1 agreement, rather than only threshold pass/fail.

## What the existing proposal gets right and wrong

The existing proposal matches the reference on intact bidirectional prefixes
and single-token answer decoding. It is retained as a useful comparison
implementation and supports keeping its capability query and cache-policy
intent.

It fails same-sequence answer chunks: the permanent noncausal override lets
earlier answer positions see later answers. In the tiny fixture, changing the
last answer token changes earlier logits by up to 0.0996, while top-1 tokens
remain unchanged. Batched versus single-token answers differ by up to 0.1082.
This demonstrates why matching generated text alone misses the defect.

In real Mimir, the existing patch passes all 18 prompt/single-token check
points and fails the three answer-chunk check points. Its maximum error
against HF is about 3.23 logits. In the English answer chunk it changes a
top-1 prediction too. The replacement's chunked versus single-token answer
logits agree within 7.63e-6 in the unfused real-model test.

The existing patch also warns and continues when a prefix exceeds physical
batch capacity. The replacement returns `-1` before KV mutation; tests check
both initially empty and already populated caches and recovery afterward.

The causal baseline correctly preserves answer causality, but its prompt
representations differ from PrefixLM. Its failures are expected controls,
not general claims that ordinary causal inference is broken.

## Real-model and performance limits

The real smoke cases use Danish, English, and a Danish multi-turn prompt,
with 27, 20, and 57 input tokens respectively. Every engine receives identical
HF-rendered token IDs and the same four answer tokens chosen by HF. The
oracle checks cached decoding against a full forward with an explicit
bidirectional-prefix/causal-answer mask.

The GGUF intentionally has no tokenizer: this isolates inference behavior.
It does not validate llama.cpp's tokenizer or Jinja rendering. Real weights
are stored as FP32 with values preserved from the BF16 checkpoint. No 4-bit
or 8-bit quantization was benchmarked. These are not DAISY/MultiWikiQA scores,
a broad quality evaluation, or a 4096-token stress test.

Per-call timings and process peak RSS are recorded in `results.json` and raw
reports. Four-token timing samples vary substantially with cold kernel/graph
preparation and are unsuitable for declaring a throughput winner. The
unfused replacement's process peak RSS was about 7.72 decimal GB with FP32
weights; RSS is not complete Metal memory accounting or an iPhone estimate.

## Instructive setup findings

- Current metadata keys include `hrm_text.hrm.prefix_lm`; the original PR
  used `hrm_text.prefix_lm`. The exact historical fixture uses historical
  header keys with identical tensor payloads. There is no runtime shim.
- The current Metal registry name is `MTL`, and this device is `MTL0`.
  Looking up a device literally named `Metal` fails despite an available GPU.
- An initial blanket F16 export was rejected by an exact-value check on
  embeddings: BF16 small values are not all representable in F16. An early
  all-F16 trial also hit an unsupported CPU F32/F16 binary operation because
  the state vector was exported as F16. Those exploratory artifacts were
  superseded by the FP32 fixture, and the failed F16 file was removed. Neither
  failure is evidence against the actual PrefixLM algorithm.
- The base Python environment's Transformers/huggingface-hub mismatch was
  avoided with an isolated uv environment. No global packages were changed.

Next: use these fixtures to implement and validate the server safeguards,
then add full-context, cancellation, prompt-cache/restore, tokenizer parity,
and longer performance/quality runs. Keep the existing proposal as a pinned
comparison throughout.
