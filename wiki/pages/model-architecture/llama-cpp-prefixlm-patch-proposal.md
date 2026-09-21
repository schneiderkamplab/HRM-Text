---
type: Design Proposal
title: Retaining and Improving the Existing PrefixLM Patch
description: Hunk-by-hunk disposition and a smaller phase-aware replacement for the existing HRM PrefixLM proposal.
tags: [mimir, llama-cpp, prefixlm, patch, correctness]
status: draft
last_updated: 2026-09-17
confidence: medium
---
# Retaining and Improving the Existing PrefixLM Patch

**Engine follow-up, 2026-09-17:** [first-class PrefixLM integration](llama-cpp-prefixlm-engine.md) now owns the generic phase, admission, cache and failure rules in llama.cpp. Earlier wrapper-owned descriptions below are historical.

**Follow-up (2026-09-17):** A library prototype and three-way comparison are
now implemented in `scripts/prefixlm_comparison/`. See the
[measured results](llama-cpp-prefixlm-comparison.md). The historical design
below remains useful; server integration is still proposed, not implemented.

This is a local patch design, not an upstream submission or an applied diff.
It refines the [initial investigation](llama-cpp-prefixlm-plan.md). The baseline
remains llama.cpp `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`. The existing
[proposal](https://github.com/noctrex/llama.cpp/pull/1) was rechecked at
`66c7c5ed26b8251a45534ecb9d173275d7ee65a1`; it is still open and unmerged.

## Revised integration boundary (2026-09-17)

The user requires app-independent PrefixLM functionality to live in the
llama.cpp patch, at the same architectural level as causal and bidirectional
attention. **Superseded as a final architecture:** the parent project's
`native/mimir` phase-owning wrapper is a validated prototype and regression
harness, not the intended permanent owner of inference correctness.

The next engine milestone must represent PrefixLM explicitly in the public
attention contract, with an explicit per-sequence prefix boundary or equivalent
request metadata. It must not infer the phase from batch size or make all
attention noncausal. Core attention, prefix admission, sequence state, graph
reuse, and safe failure/reset behavior belong in llama.cpp. Common prompt
processing and CLI/server scheduling must honor the same contract, including
cache reuse/restore, context shifting, and retry behavior. Unsupported paths
must reject before state mutation. Ordinary causal and bidirectional modes
must retain their existing behavior. Merely adding an attention enum value
would be insufficient: current initialization reduces the selection to a
causal boolean.

For a contiguous prefix ending at P, attention permits a key when it belongs
to the same valid sequence and either key_position <= query_position or both
positions are below P. Prefix completeness must still be enforced: an explicit
mask alone does not make token-wise split bidirectional prefill correct.
The initial implementation can require the entire prefix in one physical
batch and reject unsupported scheduling combinations explicitly.

Native tokenizer/template fixes remain engine/common changes. Existing generic
samplers and text utilities should be reused rather than moved into a
Mimir-specific subsystem. UI, conversation persistence/presentation, and
product choices such as answer length belong in the app; interpreting their
requests safely belongs in the runtime. The final thin embedding layer should
not toggle raw causal state or repair engine cache invariants itself.

This revised scope is recorded, not yet implemented. Preserve existing
comparison fixtures and the historical proposal while moving the generic
behavior into the fork and extending regressions at the engine boundary.
Keep the unrelated ggml graph-size UB fix as a separately reviewable change.

## What to retain

| Existing hunk | Disposition | Replacement detail |
| --- | --- | --- |
| `include/llama.h`: `llama_model_is_prefix_lm` | Keep the API and name | Describe model capability; do not imply `llama_decode` automatically selects the correct phase. Document full-prefix prefill separately. |
| `src/llama-model.cpp`: return `hparams.hrm_prefix_lm` | Keep the implementation | The flag defaults false, and HRM metadata already loads it. |
| `src/models/hrm-text.cpp`: remove obsolete unsupported comment | Keep the intent, revise wording | Say callers select noncausal prefill and causal decoding explicitly. Do not point to a permanent KV-mask override. |
| `src/llama-context.cpp`: detect split prefix | Keep the constraint, replace the warning | Reject an oversized noncausal call with `-1`, before execution. Apply the constraint to the selected attention mode, not every call to a prefix-capable model. |
| `src/llama-kv-cache.cpp`: override `causal_attn=false` | Drop this hunk | Use the existing `llama_set_causal_attn` switch at a known phase boundary; leave the mask implementation unchanged. |
| Server startup: disable prompt caching | Keep and extend | Also bypass RAM prompt-cache creation/restore and incompatible checkpoint/context-shift paths. |
| Server request launch: force `cache_prompt=false` | Keep and extend | Clear the selected slot's KV and prompt bookkeeping before constructing each fresh request, including after a restored state. |

Retain the author's attribution for reused code/ideas. The posted DAISY and
MultiWikiQA comparisons are useful external evidence and regression targets,
but were not independently reproduced here. Preserve matching rendered prompt
bytes/token IDs and reasoning settings when reproducing them.

## Why change the attention hunk

The old patch is correct under narrower assumptions than a general inference
runtime: complete prefix, one new answer token per sequence per call, and no
stale future KV cells. Sequence isolation remains in place. A prefix for one
sequence mixed with one answer token for another is not inherently wrong.

The concrete counterexample is an answer batch `[a0, a1]` for the same
sequence. The old override lets `a0` attend to `a1`, even if the caller requested
causal attention. This breaks teacher-forced answer scoring and speculative
verification. It also changes ordinary low-level causal inference merely
because a model supports PrefixLM, unlike the Transformers reference.

For the replacement, a completed prefix lives in KV; answer chunks are then
evaluated causally. This handles the answer-batch counterexample without a
new attention kernel or a per-token mask API.

## Replacement patch series

### Patch A: capability and safe existing primitive

Retain the getter in the two public/model files. In `llama_context::decode`,
replace the input-size assertions with ordinary invalid-input checks before
the batch allocator or memory execution can process the request:

```cpp
// Design sketch: integrate with the existing input validation.
if (batch_inp.n_tokens <= 0 ||
    uint32_t(batch_inp.n_tokens) > cparams.n_batch) {
    LLAMA_LOG_ERROR("%s: invalid batch size\n", __func__);
    return -1;
}
if (!cparams.causal_attn &&
    uint32_t(batch_inp.n_tokens) > cparams.n_ubatch) {
    LLAMA_LOG_ERROR("%s: non-causal input must fit in one physical batch\n", __func__);
    return -1;
}
```

Keep lower-level invariant checks as appropriate after allocation; the public
call should not abort for this ordinary capacity error. Review memory-less
`encode` delegation separately so its behavior is not accidentally changed.

Do not add a new public prefill API, new batch fields, a prefix-length map,
or another attention implementation for the first patch. Existing callers
can explicitly use the switch. The capability getter does not alter their
default causal behavior.

Extend the existing HRM fixture to cover metadata true, false, and absent,
including save/reload. Existing saver code already retains the metadata;
there is no missing-format feature to implement.

### Patch B: bounded server/chat integration

Use the generic model capability getter in the server, not an HRM-specific
HTTP request field or architecture check. Select prefix chat automatically
when the flag is true. Causal A/B experiments can use the existing metadata
override `--override-kv hrm_text.prefix_lm=bool:false`; document this as an
explicit diagnostic override. Do not add another CLI mode in the first patch.

**Superseded key spelling (2026-09-17 execution check):** The override above
matches the historical PR, not the current pinned base. Its current spelling
is `--override-kv hrm_text.hrm.prefix_lm=bool:false`. The benchmark distinguishes
these metadata layouts explicitly; weight tensor payloads remain identical.

The server already records `server_batch::token::is_prompt` and `id_slot`.
Promote these from statistics-only data to checked scheduling invariants:

1. For a prefix request, clear its old prompt and KV state and disable reuse.
   Render/tokenize the whole conversation, including the generation marker.
2. Make its prompt indivisible in `server_slot::can_split`. Admission requires
   `prompt_tokens <= min(n_batch, n_ubatch)` and enough context for an answer.
   Reject excess with a client-visible error before filling the batch.
3. Initially evaluate one complete prefix per prefill call. Do not append it
   to a call containing generated tokens. Other requests may remain queued;
   later scheduling improvements need not change the attention contract.
4. Derive the call's phase from its actual tokens and validate homogeneity.
   Slot state alone is insufficient: prompt construction changes it to
   `SLOT_STATE_DONE_PROMPT` before `llama_decode` runs.
5. Noncausal mode applies only to that complete-prefix call. Generated-token
   calls are causal. A scoped guard restores the server's causal invariant on
   every exit, including exceptions, and synchronizes at the phase boundary
   for the initial implementation. Reuse the local RAII style in mtmd helpers
   without adding a dependency from the server to a multimodal helper.
6. On any prefix error/abort, clear affected KV and prompt bookkeeping. The
   retry loop may free idle slots and retry the identical whole prefix, but
   must never halve it or advance past a partially processed prefix.

Conceptual call flow, not a compilable helper declaration:

```text
validate complete prefix and available capacity
clear old sequence state
enter noncausal scope
    decode entire prefix once
    synchronize
leave scope, restoring causal mode
if unsuccessful: discard prefix state and report error
otherwise: sample from final-prefix logits, then decode answers causally
```

For the first tested server configuration, use one active slot and ordinary
text completion. Reject speculative configurations, multiple-completion
child tasks, aLoRA prefix splitting, and unsupported embedding/multimodal
requests. Expose restrictions clearly at startup/request admission rather
than silently approximating behavior. Static features can be enabled later
after independent tests; the core low-level causal API remains general.

At startup, normalize automatically enabled caching/context-shift defaults
with one clear diagnostic, following existing server conventions. Reject
explicit per-request unsupported behavior. Specifically cover:

- Both request/default `cache_prompt`, shifted chunk reuse, and RAM cache.
- Prompt checkpoints and partial restore. A new request always discards
  restored state in this first version; slot restore should be rejected
  rather than advertised as a useful optimization.
- Context shifting. Stop at context capacity; a caller can trim old turns
  and submit a fresh prompt. Do not silently trim within the engine.
- Allocation fallback and cancellation. Both must preserve the complete
  prefix invariant, clear failed state, and restore causal mode.

This is deliberately conservative, not a claim that exact-prefix caching or
concurrent requests are mathematically impossible. Phase-homogeneous batches
can later handle multiple sequences, provided every prefix fits the physical
batch intact and sequence isolation is verified.

The current CLI starts/connects to a server in
`tools/cli/cli-context.cpp`, so it should inherit the server path. Test that
integration. Standalone tools using `common_prompt_batch_decode` or direct
`llama_decode` do not automatically gain prefix semantics; leave their causal
behavior unchanged and document the explicit library recipe.

### Patch C: regression and reference evidence

Extend existing `tests/test-llama-archs.cpp` and server completion/slot tests;
reuse their infrastructure rather than introducing another test executable.
Keep the pinned-Transformers comparison harness outside the llama.cpp core.

Tests must distinguish the old patch, the unmodified causal baseline, and the
replacement, using actual model inference with deterministic nonzero weights:

| Regression | Unmodified runtime | Old mask override | Replacement expectation |
| --- | --- | --- | --- |
| Server reads future prefix tokens | Missing | Works if prefix is intact | Matches HF prefix mode |
| Explicit causal `[a0, a1]` after prefix | Causal | `a0` can see `a1` | Batched logits match token-by-token decode |
| Prefix exceeds physical batch capacity | Causal chunking allowed | Warning then incorrect split | Clean rejection, no partial KV |
| New turn shares old prompt text | Causal reuse | Main reuse disabled | Fresh full prefill, including RAM/restore paths |
| Prefix decode allocation fails | Retry may split | Retry may split | Whole-prefix retry or failure with clean state |
| Capability true, caller requests causal | Causal | Forced noncausal | Remains causal |

Add one-token prefix coverage (phase cannot be inferred from batch size),
exactly-at-capacity and above-capacity calls, fresh-context equivalence after
errors, and sequence-isolation checks before widening concurrency support.
An invalid call must leave the previously valid KV state untouched when
rejected during admission; a failure during prefix execution must clear the
affected sequence before reuse. These are different recovery cases.

Compare unquantized logits against pinned HF with explicit `token_type_ids`,
then compare CPU/Metal, fused/unfused attention, and only then quantized model
and KV variants. Test both direct forward and `generate`. Establish numeric
tolerances from matched-precision baselines, and check that the tests actually
fail with both known wrong attention modes. Do not assert exact text identity
across near-tied logits as the sole acceptance criterion.

## Scope and validation status

The proposed initial runtime changes are concentrated in the original
proposal's public/model files, `src/llama-context.cpp`, and the server. The KV
mask file, GGUF conversion, HRM graph, and Metal kernels need no proposed
changes. Tests and usage documentation accompany the runtime patch.

No implementation diff has been applied and no numerical claims were tested
in this turn. A local Transformers import probe failed because the installed
Transformers expects `huggingface-hub>=0.30.0,<1.0` but the environment has
`huggingface-hub==1.3.2`. Use an isolated, pinned test environment for the HF
oracle; do not repair the user's base Python environment as part of the patch.

The design keeps the original patch's small scope wherever possible, while
making incomplete prefill and accidental noncausal answer evaluation explicit
errors instead of implicit assumptions.
