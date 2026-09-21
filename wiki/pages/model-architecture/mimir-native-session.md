---
type: Implementation Report
title: Minimal Mimir Native Session Runtime
description: Owned single-conversation PrefixLM inference, failure recovery, and CPU/Metal validation for an embedded Apple runtime.
tags: [mimir, prefixlm, llama-cpp, native, testing, metal]
status: draft
last_updated: 2026-09-17
confidence: high
---
# Minimal Mimir Native Session Runtime

**Engine follow-up, 2026-09-17:** [first-class PrefixLM integration](llama-cpp-prefixlm-engine.md) now owns the generic phase, admission, cache and failure rules in llama.cpp. Earlier wrapper-owned descriptions below are historical.

## Implementation and boundaries

`native/mimir/` contains a C++17 library with an owned llama.cpp context and
shared model lifetime. Its README documents the API, reproducible commands,
error semantics, and embedding requirements. The supported engine is
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b` plus the replacement patch preserved
in `scripts/prefixlm_comparison/patches/replacement.patch` and the separate
`native/mimir/patches/ggml-graph-size.patch` arithmetic fix.

Every new turn supplies the entire rendered/tokenized retained conversation.
The runtime validates tokens and reserves an answer budget before mutation,
then discards all previous KV and recomputes the prompt. PrefixLM metadata
selects bidirectional prefill; answer decoding is always causal. False/absent
metadata retains causal behavior. Every decode synchronizes and restores causal
attention before returning. Context limits cannot exceed the trained context.

One context carries one sequence. The public API exposes no raw context, cache
restoration, context shifting, speculative decoding, or prompt splitting.
Logical and physical batch limits are equal, with explicit input rejection.
Invalid requests preserve the existing session. Nonzero backend results and
execution exceptions clear the entire session; there is no automatic retry.
Results own their logits, avoiding borrowed-buffer lifetime errors.

All operations except cancellation require serialized access. Cancellation is
sticky until reset. CPU can abort within decode; Metal may finish the active
decode before cancellation is observed and its results discarded. Destruction
must wait for all users of the session, including cancellation producers.

This is an embedded token-in/logits-out runtime, not an HTTP server or a complete
chat app. Tokenizer/chat-template integration, sampling/EOS/streaming policy,
Swift/platform packaging, quantized weights, and device qualification remain
separate release gates.

**Superseded scope, 2026-09-17:** native tokenizer/template integration and
greedy EOS/streaming are now implemented and tested in the
[native text chat milestone](mimir-native-text-chat.md). Swift packaging,
quantization, and device qualification remain open. That milestone adds a
third saved engine patch for tokenizer and Unicode template parity.

## Source state and prior experiment

The [comparison report](llama-cpp-prefixlm-comparison.md) remains the historical
mathematical/library comparison. Its original and adapted proposal variants
are preserved and unchanged for future comparisons.

**Superseded scope, 2026-09-17:** the comparison originally kept both registered
submodules clean and phase switching only in its runner. The replacement patch
is now also applied to the registered `llama.cpp` working checkout, and the new
native session owns phase switching and lifecycle policy. The `mimir` submodule
is unchanged. No commit, push, PR, or upstream submission was made. Server
scheduling/cache integration is still not implemented or claimed.

## Validation observed on 2026-09-17

Host: Apple M2 Max, 96 GiB, macOS 26.4.1, Apple Clang 17. Release-mode testing
passed **23 runs / 3243 assertions and numerical comparison checkpoints**.
These counts include repeated lifecycle checks per configuration, not 3243
independent scenarios or model-quality measurements.

| Coverage | Result |
| --- | --- |
| Tiny HRM, metadata true/false/absent, CPU FP32 and FP16 KV | All six runs pass |
| Tiny HRM, metadata true/false/absent, Metal FP32/FP16 KV and fused FP16 KV | All nine runs pass |
| Longer tiny HRM reference on the same five backend/precision configurations | All five runs pass |
| Real Mimir short-reference parity, lifecycle failures/recovery, and 4096-context stress | All three Metal runs pass |

Longer independent HF reference cases cover 32 answer tokens, twelve turns,
chunked/single-token answers, a 127-token prefix, and the tiny model's 128-token
trained context boundary. HF cached decoding is checked against full forwards.
The maximum observed long-fixture HF logit error is approximately `9.56e-4`
across the tested paths; CPU FP32 is approximately `7.15e-7`.

Real-model tests reuse the pinned Mimir checkpoint and FP32 weight export from
the earlier comparison. Short-reference maximum error remains approximately
`0.00650`. The full-context stress test prefills 4095 tokens, appends one token,
rejects overflow without mutation, and starts a shorter new turn. All three
Metal configurations pass. This checks execution/finiteness and lifecycle at
4096 tokens; it is not HF numerical parity at that length or a language-quality
benchmark. No phone performance or memory claim follows from these tests.

Lifecycle coverage includes invalid/out-of-range tokens, empty input, oversized
prefixes, overflow-safe answer reservations, budget exhaustion, repeated and
truncated conversations, reset, owned output buffers, and configuration limits.
Tests inject backend codes `1`, `2`, `-1`, and `-3`, plus a host allocation
exception, after real KV writes in both phases. Recovery logits must match a
fresh session. Cross-thread late cancellation discards completed output; a
separate CPU test executes the real backend abort callback. Physical device
OOM and OS termination are not induced or claimed recoverable.

Clang static analysis of the session implementation and Python compilation of
the test scripts pass. The CPU CI workflow generates pinned deterministic
fixtures and includes release and combined ASan/UBSan jobs; it has been added
but has not been executed on GitHub in this session.

AddressSanitizer is **not verified locally**: it hangs before `main` while
initializing shadow memory under this host toolchain. An empty-main ASan binary
reproduces the hang, and `DYLD_SHARED_REGION=avoid` does not resolve it. Sampled
stacks and probe artifacts are retained under `logs/mimir-runtime/`.

UBSan found pre-existing undefined null-pointer arithmetic in ggml's graph-size
dry run (`incr_ptr_aligned`). A separate minimal patch uses integer-address
addition, consistent with the same function's existing alignment calculation.
The original comparison worktrees are unchanged. Sanitizer runs use
`UBSAN_OPTIONS=halt_on_error=1`; no diagnostic is suppressed.
After this fix, all eight CPU UBSan runs pass (1128 assertions/comparison
checkpoints), covering both FP32 and FP16 KV and all lifecycle/reference cases.

## Evidence and reproduction

Start with `native/mimir/README.md`. Raw reports and logs are under ignored
`logs/mimir-runtime/`; the release matrix summary records source, library,
executable, model, and case hashes plus exact commands. The compact repository
result artifact is `native/mimir/test-results.json`.

The previous comparison's original proposal remains useful for numerical
regression and benchmark controls. No claim is made that those proposal
variants expose the native session API.
