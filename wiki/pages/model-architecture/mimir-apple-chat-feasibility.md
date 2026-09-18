---
type: Technical Reference
title: Mimir Apple Chat Feasibility
description: Verified runtime constraints and proposed validation path for an offline iOS, iPadOS, and macOS Mimir chat app.
tags: [mimir, apple, inference, metal, mobile]
status: draft
last_updated: 2026-09-17
confidence: medium
---
# Mimir Apple Chat Feasibility

## Verified state on 2026-09-17

The public [DFM-Mimir repository](https://huggingface.co/danish-foundation-models/DFM-Mimir)
at revision `2844f0178e695d7d9ce182cb660671fd34c76ce5` reports
`gated: false`, Apache-2.0 metadata, and 1,786,775,040 serialized BF16 values.
Its config has width 1536, 12 KV heads, head dimension 128, 16 layers per
stack, H=2, L=3, PrefixLM enabled, and a 4096-token context limit.
The roughly 1B description excludes the two large vocabulary matrices; see
[XL parameter accounting](xl-parameter-and-export-size.md).

[llama.cpp PR 27625](https://github.com/ggml-org/llama.cpp/pull/27625)
merged on 2026-09-16 and is included in release b11003. The inspected
`src/models/hrm-text.cpp` still explicitly lacks PrefixLM prefill. The PR
discussion links a separate proposed PrefixLM patch; it is not evidence that
the merged implementation supports that behavior.

The recurrence expands to 16 * 2 * (3 + 1) = 128 attention/cache slots.
For batch one, FP16 K/V storage at 4096 tokens is
2 * 128 * 4096 * 12 * 128 * 2 = 3,221,225,472 bytes (3 GiB), before weights,
activations, allocator overhead, or app memory. At 2048 tokens it is 1.5 GiB.
Quantized caches can reduce this, but quality, kernel compatibility, and
actual peak memory require device measurements. Weight-only 4-bit payload
is approximately 0.89 decimal GB before quantization metadata and any
higher-precision tensors; this is not total runtime memory.

## Proposed implementation and acceptance gates

The follow-up [llama.cpp PrefixLM plan](llama-cpp-prefixlm-plan.md) records
the added submodules, pinned Transformers reference, existing phase-switch
API, and the concrete batching/cache safeguards required before app work.

SwiftUI can share app structure across iOS/iPadOS/macOS. Evaluate embedded
llama.cpp with Metal first because architecture support now exists. Correct
PrefixLM prefill, full-prompt batching, and cache invalidation across chat
turns are acceptance gates, not optional optimizations. Under the existing
demo's all-prompt-bidirectional contract, appending a user turn changes the
old prompt representations; ordinary causal prefix-cache reuse is invalid.

MLX Swift is an alternative if implementing the model and prefix attention
there is simpler than adapting llama.cpp. The inspected MLX Swift LM model
factory had no hrm/mimir registration. Core ML is a separate conversion and
profiling effort if Neural Engine use becomes a requirement; Metal GPU
acceleration alone meets an on-device acceleration goal.

Start with a Mac inference harness, compare unquantized logits/tokenization
and multi-turn behavior against Transformers, then evaluate weight/cache
quantization. Measure time to first token, decode speed, peak memory, and
sustained thermal behavior on actual phones before declaring support.
Candidate initial targets are Apple Silicon Macs and recent phones/tablets
with at least 8 GB RAM; these are proposed targets, not verified compatibility.

Keep model artifacts versioned independently of conversations: revision,
architecture/runtime version, tokenizer, chat template, context limit,
quantization, checksum, and license notices. Future weights can be data-only
updates when the architecture is supported; architecture changes may need an
app update. Literal app bundling supports offline first launch; an optional
download/update path supports later releases.

No Apple-device Mimir throughput or memory benchmark was performed for this
assessment, and no runtime was implemented.
