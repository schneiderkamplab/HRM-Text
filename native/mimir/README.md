# Mimir native session runtime

A small C++17 inference layer for embedding llama.cpp in the Apple chat
app. It owns one context and one conversation. The caller supplies tokenized,
fully rendered messages and chooses sampling and presentation. The optional [text chat layer and terminal client](CHAT.md) add native
tokenization, template rendering, greedy sampling, EOS, and streaming. Swift
packaging and the development MVP are now in [native/apple](../apple/README.md).

## Build

The supported llama.cpp revision is the pinned submodule at
`8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`, which includes the PrefixLM,
text-codec, ggml and generation-persistence changes. The earlier instructions
to apply loose patches on top of `c9a5eeeb` are superseded (2026-09-19).
On a fresh checkout, from the repository root:

```sh
git submodule update --init llama.cpp
cmake -S native/mimir -B logs/mimir-runtime/build -DCMAKE_BUILD_TYPE=Release
cmake --build logs/mimir-runtime/build -j 8
```

Link `mimir-runtime` and include `mimir/session.h`. Initialize llama backends
before loading a model. Keep backend initialization alive until all models and
sessions are destroyed. Model ownership is shared; context ownership is private.
Disable `MIMIR_BUILD_TESTS` when embedding the library. The build above targets
the host; use the Apple MVP guide for Mac/iOS bundles.

The [engine integration](ENGINE.md) owns PrefixLM phase selection, admission,
and unsafe-cache rejection. The earlier comparison replacement patch remains
a historical artifact; do not apply it together with `prefixlm-engine.patch`.

## Session contract

```cpp
std::shared_ptr<llama_model> model(
    llama_model_load_from_file(model_path, model_params), llama_model_free);
mimir::Session session(model, {2048, 1024, 4, false, GGML_TYPE_F16});

auto next = session.begin_turn(full_conversation_tokens, 128);
while (next && session.remaining() > 0) {
    // App-owned sampler and renderer. Handle EOS before displaying/appending it.
    const llama_token token = sample(next.logits);
    if (llama_vocab_is_eog(llama_model_get_vocab(model.get()), token)) {
        break;
    }
    display(token);
    next = session.append({token});
}
```

`begin_turn` takes the complete retained conversation, including prior
assistant answers and the new assistant generation header. It validates the
request before replacing the previous conversation, then clears all KV and
prefills from position zero. PrefixLM metadata selects bidirectional prompt
attention; false/absent metadata retains causal attention. Answers are always
causal. The engine synchronizes PrefixLM calls and restores its internal causal
execution mode before returning; the wrapper no longer toggles attention.

Both prefix and answer calls must fit `batch_tokens`. This first version uses
the same logical and physical batch size, so prefix splitting is impossible.
`prompt length + answer budget` must fit `context_tokens`. By default context
cannot exceed the model's trained context. `Config::allow_context_extension`
explicitly opts into larger contexts; the caller must check available memory
and accept that answer quality beyond training length is unqualified. The requested limits remain authoritative even
when llama.cpp rounds allocation sizes up. The budget counts answer tokens
submitted to `append`; callers should stop sampling when it reaches zero.

Only `request_cancel()` may run concurrently with another session method.
Run all other methods and destruction on one serialized worker. A cancellation
request is sticky until `reset()`. CPU execution supports an abort callback;
Metal cancellation may wait for the active decode to complete. A cancellation
observed before returning discards logits and clears KV. A request racing with
an already completed call can take effect on the following call. Stop/join any
cancelling task before resetting or destroying its session.

Results own their logits. The default returns only the final input position's
logits; `all_logits=true` is intended for diagnostics and can consume substantial
memory. The low-level context is not exposed, preventing accidental cache
restore, context shifting, mixed-sequence scheduling, and attention-mode changes.

| Outcome | State after the call |
| --- | --- |
| Invalid tokens, oversized input, zero/oversized budget | Previous session remains usable; no backend call |
| Successful new turn | Old KV discarded; full prompt recomputed; answer budget reserved |
| Successful answer | Position advanced; answer budget reduced |
| Any nonzero backend result | All KV cleared; a fresh turn is required; no automatic retry |
| Cancellation or backend abort | All KV cleared; `reset()` is required |
| C++ exception during execution | All KV cleared; exception propagates |

Backend return codes are retained in `Result.backend_code`. Initialization
failures throw. CPU/Metal allocation failures reported normally by llama.cpp
are handled; process termination by the OS or a backend assertion is outside
this library's recovery contract. `ready()` means a turn is initialized; inspect
`remaining()` separately to determine whether its answer budget is exhausted.

## Tests

Generate the original fixtures using the pinned environment described in
[`scripts/prefixlm_comparison/README.md`](../../scripts/prefixlm_comparison/README.md).
The historical PrefixLM proposal and its baseline comparisons remain intact.
Then run:

```sh
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/long_reference.py \
  --model logs/prefixlm-comparison/fixture/hf \
  --output logs/mimir-runtime/long-fixture
ctest --test-dir logs/mimir-runtime/build --output-on-failure
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/run_matrix.py --metal --real --full-context
```

Omit `--metal --real --full-context` for the CPU matrix. Real-model tests require
the existing pinned real-model export and reference fixtures. The matrix covers
FP32 and FP16 KV without flash attention, plus Metal flash attention with FP16 KV.
All runs are serial; reports, command lines, source/library/model hashes, and
logs are saved under `logs/mimir-runtime/matrix`. These are correctness tests,
not stable throughput benchmarks.

The longer tiny-model oracle independently checks cached HF decoding against
full forwards. It covers 32 answer tokens, twelve turns, and the trained
128-token context boundary. The real-model full-context test executes a
4095-token prompt and one answer token, checks rejection beyond capacity, and
starts a shorter new turn. That stress test checks execution and finiteness;
it does not establish HF numerical parity at 4096 tokens.

Failure tests inject nonzero decode results and a host allocation exception
after real KV writes, then compare recovery logits against a fresh session.
This exercises the session's cleanup independently of whether a device happens
to exhaust memory. A CPU test also exercises the actual backend abort callback.
It does not deliberately exhaust the machine's physical memory.

For AddressSanitizer and UndefinedBehaviorSanitizer:

```sh
cmake -S native/mimir -B logs/mimir-runtime/sanitize \
  -DCMAKE_BUILD_TYPE=Debug -DGGML_METAL=OFF \
  -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
cmake --build logs/mimir-runtime/sanitize -j 6
UBSAN_OPTIONS=halt_on_error=1 logs/prefixlm-comparison/venv/bin/python native/mimir/tests/run_matrix.py \
  --build logs/mimir-runtime/sanitize --output logs/mimir-runtime/sanitize-matrix
```

On the tested macOS 26.4.1/Xcode Clang 17 host, AddressSanitizer hangs while
initializing shadow memory before `main`, including for an empty-main probe.
`DYLD_SHARED_REGION=avoid` did not fix it. Use `-fsanitize=undefined` alone in a
separate build for local UBSan testing; do not interpret the ASan startup hang
as a completed test. Linux CI includes a combined ASan/UBSan job.

UBSan identified null-pointer arithmetic in ggml's graph-size dry run, before
model execution. `patches/ggml-graph-size.patch` changes the existing offset
calculation to integer-address arithmetic, consistent with its alignment
calculation. It is separate from PrefixLM and is not applied to the historical
comparison worktrees. Run UBSan with `halt_on_error=1` so diagnostics fail tests.

The CPU CI workflow generates the fixtures rather than downloading model
weights. Local Mac testing is separate from CI. Remaining release gates are
validated deployable weight quantization, Apple device packaging and
measurements, and app integration. Native tokenizer/template parity and the
terminal EOS/streaming path are covered in [CHAT.md](CHAT.md).
