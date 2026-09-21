---
type: Implementation Plan
title: Safe PrefixLM Support in llama.cpp
description: Source audit and staged plan for preserving HRM-Text prefix attention in native chat inference.
tags: [mimir, hrm, llama-cpp, prefixlm, inference, apple]
status: draft
last_updated: 2026-09-17
confidence: medium
---
# Safe PrefixLM Support in llama.cpp

**Execution update (2026-09-17):** The library comparison stage has now run on
CPU and Metal with synthetic HRM and real Mimir weights. See
[comparative results](llama-cpp-prefixlm-comparison.md); server integration
remains pending. Statements below about no execution describe the initial
investigation.

Follow-up: [concrete revision of the existing patch](llama-cpp-prefixlm-patch-proposal.md)
identifies the hunks to retain and narrows the proposed API surface.

## Scope and inspected revisions

The requested submodules were added at repository-root paths:

| Path | Remote | Inspected commit |
| --- | --- | --- |
| `mimir` | `https://github.com/schneiderkamplab/mimir.git` | `0a01ea0fa6b770ca564108f41c1187c8fbba44b0` |
| `llama.cpp` | `https://github.com/schneiderkamplab/llama.cpp.git` | `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b` |

`mimir` currently contains only LICENSE. It does not contain a model reference
implementation. The Transformers HRM-Text sources were inspected at
`ff2421c67f35cc83a0fbabbc2633c96734685918`:
[model](https://github.com/huggingface/transformers/blob/ff2421c67f35cc83a0fbabbc2633c96734685918/src/transformers/models/hrm_text/modeling_hrm_text.py),
[configuration](https://github.com/huggingface/transformers/blob/ff2421c67f35cc83a0fbabbc2633c96734685918/src/transformers/models/hrm_text/configuration_hrm_text.py).
The actual class spelling is `HrmTextForCausalLM`.

This is source investigation and an implementation proposal, not a validated
runtime change. Neither submodule's source was modified. No model inference,
backend benchmark, or parity test was run in this investigation.

## Reference behavior

`HrmTextForCausalLM.forward` delegates to `HrmTextModel.forward` and applies
the output projection. Prefix attention lives in the model's mask creation,
not the output head. The generation-specific `create_masks_for_generate`
hook repeats the same first-iteration rule.

On the initial forward, with `config.prefix_lm=True`, positions whose
`token_type_ids` are 1 share one bidirectional block. Other positions retain
causal attention. With absent token types, the reference remains causal;
the config flag alone does not turn all attention bidirectional. Subsequent
cached generation is causal.

For the intended chat contract, all tokens in the fully rendered conversation
are the prefix. For a contiguous prefix ending at exclusive position P, the
allowed attention relation is:

```text
same_sequence(query, key)
AND valid_key(key)
AND (key_position <= query_position
     OR (query_position < P AND key_position < P))
```

This is a specialization of the reference's token-type block overlay. An
arbitrary mixture of token types is outside the first implementation's scope.
Prior assistant turns become part of the new prefix when a new user message
is appended. Such a turn needs a fresh prefill under the existing demo's
contract; it is different from resuming generation of the same answer.

The recurrent L/H computation and cache layout already exist in llama.cpp.
Each attention invocation has its own cache slot, while repeated passes share
weights. Mimir's 16 layers per stack, H=2, L=3 give 128 slots. Preserve that
layout and its embedding scaling, parameterless RMS norms, gated attention,
RoPE, and SwiGLU; attention policy should not rewrite the architecture.

## Source audit

Paths below are relative to the llama.cpp submodule.

| Location | Finding and implication |
| --- | --- |
| `conversion/hrm_text.py:37` | Already serializes `hrm_text.prefix_lm`; supports both per-stack and expanded HF config layouts. No weight-format redesign needed. |
| `src/models/hrm-text.cpp:14` | Reads the flag but explicitly leaves PrefixLM unimplemented. |
| `src/llama-kv-cache.cpp:1555` | Existing causal/noncausal mask implementations preserve sequence isolation and exclude empty KV cells. Reuse this machinery. |
| `include/llama.h:1011` | Public `llama_set_causal_attn` already supports phase switching. |
| `src/llama-context.cpp:1202` | Switching causal mode requests scheduler reservation; graph compatibility also compares this flag in `src/llama-graph.h`. |
| `src/llama-context.cpp:1736` | Noncausal batches already assert that physical batch capacity covers the entire input batch. Validate before this assertion and return a recoverable error. |
| `src/llama-graph.cpp:2632` | Fused attention accepts the explicit KQ mask. CPU and Metal still need parity tests; do not assume a CUDA FlashAttention limitation applies here. |
| `tools/server/server-context.cpp:441` | `can_split` currently allows ordinary completion prompts to split. Prefix prompts need an indivisible path. |
| `tools/server/server-context.cpp:3098` | Generated tokens enter a batch before pending prompts; the context-wide attention switch cannot express mixed phases safely. |
| `tools/server/server-context.cpp:3184` | Existing unsplittable-prompt admission checks offer reusable structure. Aggregate physical batch size also needs checking. |
| `tools/server/server-context.cpp:3217` | Longest-common-prefix reuse and shifted chunk reuse must be bypassed for fresh prefix requests. |
| `tools/server/server-context.cpp:1647` | RAM prompt-cache save/load is a separate path; disabling only request `cache_prompt` is not a complete cache policy. |
| `tools/server/server-context.cpp:3730` | Retry logic halves batches after KV allocation failure. A prefix must never be split by this recovery path. |
| `common/common.cpp:2201` | `common_prompt_batch_decode` can divide a prompt, including separating its final token. Audit callers before claiming general tool support. |
| `tests/test-llama-archs.cpp:330` | There is already a small HRM fixture, but it does not set PrefixLM metadata. Extend existing test infrastructure. |

## Existing patch assessment

[noctrex/llama.cpp PR 1](https://github.com/noctrex/llama.cpp/pull/1) was open
and unmerged when inspected, at head
`66c7c5ed26b8251a45534ecb9d173275d7ee65a1`. It overrides causal masking for
every HRM call, disables some prompt-cache paths, and only warns on split
prefill. Its reported DAISY parity is encouraging but was not reproduced here.

Use it as prior art, not as a production-ready cherry-pick:

- Permanently noncausal attention is equivalent to causal decoding only when
  one new answer token per sequence is evaluated and no future cached cells
  are visible. Teacher-forced answer chunks and speculative verification
  violate that assumption.
- A warning after choosing split prefill permits incorrect outputs. Earlier
  chunks cannot see later prefix tokens; fixing the mask alone cannot recover
  their higher-layer representations.
- Prompt-cache defaults do not cover all restore/reuse paths, scheduler phase
  mixing, rollback, or allocation-retry splitting.

**Clarification (2026-09-17):** Mixed request phases across distinct sequences
are not inherently incorrect in the external patch when each generated
sequence contributes one token and no future KV cells are visible. Sequence
isolation is preserved. Phase separation is required by our chosen explicit
context-wide switch; it is not evidence of cross-sequence leakage in the old
patch. See the follow-up proposal for the same-sequence answer-chunk failure.

## Recommended staged implementation

### 1. Establish an independent numerical baseline

Create a reproducible tiny HRM checkpoint with nontrivial deterministic
weights, matching HF and GGUF files, and saved token IDs. Pin Transformers and
record dtype, attention backend, model revision, and conversion command.
Compare existing causal inference first to isolate conversion or recurrence
defects from PrefixLM defects.

Extend the existing HRM architecture test where appropriate; keep the
cross-runtime fixture generator/comparison harness in the parent project's
scripts/tests. Avoid a parallel model implementation masquerading as an
independent oracle. Use actual pinned Transformers with the prefix mask
explicitly activated in both direct-forward and generate tests.

### 2. Prove the two-phase library path before server integration

For one sequence on a clean context:

1. Tokenize/render the entire conversation and validate its prompt length
   against both logical and physical batch capacities and context capacity.
   Include the assistant generation marker in the prefix.
2. Set noncausal attention, submit the entire prefix in one `llama_decode`,
   and retain its last-position logits for sampling the first answer token.
3. Restore causal attention on success, error, cancellation, or exception.
   Initially synchronize at the phase boundary until asynchronous behavior
   has been verified.
4. Decode answer tokens causally, retaining the recurrent KV state. A causal
   answer chunk must match token-by-token answer evaluation.
5. If prefill aborts or fails, clear affected sequence state and restart the
   whole prefix; never continue from a partially evaluated prefix.

Use the existing switch and mask implementation. Do not set an unconditional
`causal_attn=false` override in the KV cache. No new Metal kernel is expected
for this initial path; that remains to be validated.

### 3. Add a bounded, explicit supported mode

Expose model PrefixLM capability (a small public getter is one option), and
select the chat mode deliberately. Keep low-level causal decode semantics
available for HF parity and raw causal evaluation. At high level, `auto`
can select prefix chat from model metadata; retain explicit causal override.
Do not infer prefill from token count, empty cache, or position zero alone.

Represent request state as fresh prefix, answer generation, or failed/reset.
Centralize admission and phase handling so an embedded app and server can use
the same contract. Initially support only one active sequence, full-prefix
prefill, and ordinary causal decoding. Reject unsupported mixed prefix/answer
batches or mixed token-type requests instead of silently approximating them.

Perform all length/state checks before KV mutation or graph execution.
Oversized noncausal decode must produce a clear error rather than reach the
existing assertion. Full-prefix capacity is constrained by both `n_batch`
and `n_ubatch`; increasing only the former is insufficient.

### 4. Integrate server/chat lifecycle conservatively

Reuse unsplittable-prompt scheduling and enforce physical batch capacity.
Prefill and generation must be separate decode calls. For the first release,
serialize requests or explicitly reject parallel configurations, disable
speculation, and prevent allocation recovery from shrinking a prefix batch.
Do not silently discard a request's explicit unsupported option.

Clear and re-prefill on each new chat request. Cover request cache reuse,
RAM prompt caches, slot restore, checkpoint reuse, shared-prefix child slots,
and shifted chunk reuse. Disable automatic context shifting initially; trim
complete conversation turns at the caller and re-prefill, or return a context
limit error. Prompt truncation must be deliberate and visible to the caller.

Exact complete-prefix cache reuse or resuming an unchanged answer can be safe
with matching tokens, positions, model, adapters, attention mode, and phase;
defer that optimization until state validation and serialization are tested.
Audit CLI and embedding clients separately; do not label every llama.cpp tool
PrefixLM-capable merely because the server path works.

### 5. Broaden only after correctness is established

Add CPU and Metal fused/unfused attention parity, then weight and KV
quantization. Evaluate Danish/English quality and device memory/latency.
Keep quantization differences separate from attention correctness.

Later, multiple requests can be grouped by phase, with full prefixes fitting
each physical batch. General mixed batches, speculative decoding, and packed
prefix/answer scoring need explicit per-sequence prefix boundaries/mode
metadata and tests. Do not implement them by turning off causality globally.

True chunked bidirectional prefill requires attention/layer execution that
preserves full-prefix visibility at every recurrent invocation. It is a
separate algorithmic project, not the current token-wise ubatch loop with a
different mask. Do not promise bounded-memory long-prefix support in v1.

## Acceptance tests

| Test | Required outcome |
| --- | --- |
| Prefix future visibility | Changing a later prefix token affects earlier prefix states/logits in a nondegenerate fixture and matches HF. |
| Answer causality | Changing a later answer token cannot change earlier answer logits. |
| Direct forward vs cached answer | Full HF prefix-plus-causal-suffix logits match llama.cpp full prefix followed by causal answer chunks. |
| Causal control | Absent/false PrefixLM metadata and explicit causal mode retain existing results. |
| Capacity boundaries | Prefix lengths at and above each capacity are accepted or cleanly rejected as specified; never silently split. |
| One-token prefix | It is recognized by phase, not misclassified as generation. |
| New chat turn | Clearing and rebuilding matches a fresh-context run, even when most text matches the preceding request. |
| Error and cancellation | No partial prefix survives; causal mode is restored; the next request matches a clean context. |
| Sequence isolation | Foreign or stale KV cells cannot influence output; any advertised multi-sequence path matches isolated runs. |
| Backend and graph reuse | Switching phases repeatedly on CPU/Metal preserves results; fused/unfused paths agree within measured precision tolerances. |
| Real checkpoint | Exact tokenizer/template token IDs and unquantized logits on short Danish/English examples precede quality tests of quantized variants. |

Record maximum/RMS logit error and top-k agreement; establish precision-aware
tolerances from the causal baseline. Greedy text alone is insufficient, and
near-tied logits need margin-aware interpretation. Require the tiny tests to
detect both known bad implementations: causal prefill and noncausal answer
chunks. Report admission/cache tests separately from numerical tests.

First deliverable: a verified CPU/Metal single-sequence two-phase harness,
followed by server lifecycle guards. The app should depend on that validated
contract rather than the current experimental all-noncausal patch.

Related: [Apple chat feasibility](mimir-apple-chat-feasibility.md).
