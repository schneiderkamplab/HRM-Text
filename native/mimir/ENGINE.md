# Engine-level PrefixLM integration

PrefixLM attention, complete-prefix admission, phase changes, failure/abort
cleanup, and cache restrictions now live in llama.cpp. `native/mimir` remains
an embedding example and reference harness. It no longer toggles attention or
clears the old prefix before handing a new prefix to the engine.

The engine contract is documented in
[llama.cpp/docs/development/prefix-lm.md](../../llama.cpp/docs/development/prefix-lm.md).
It adds `LLAMA_ATTENTION_TYPE_PREFIX_LM`, `llama_get_attention_type`, and
`llama_decode_prefix`. Model metadata selects PrefixLM by default; explicit
causal and bidirectional overrides remain available. The implementation is
architecture-independent and tested on HRM-Text and Llama.

The working-tree implementation now supports multiple active sequences, complete
prefix batches and batched causal answers. Reset, cancellation and failure cleanup
are sequence-local. Full-sequence forks (including server shared-prefix children), fixed
ordinary LoRA/control vectors, and context/per-sequence persistence are implemented.
Mixed phases use sequence-local masks. Shared forks count physical KV cells once.
Boundary logits and supported host sampler state can be saved; native server completions
can explicitly retain, persist and resume generations. Prefix edits, answer holes,
context shifting, activated LoRA, ordinary prompt-cache reuse, speculation and multimodal
input remain unsupported. See [SHARING.md](SHARING.md) for shared input/bounded copies and
[RESUMPTION.md](RESUMPTION.md) for resumption changes,
evidence and remaining restrictions; [STATE.md](STATE.md) records the preceding work.

The packaged patches below still describe the earlier single-sequence snapshot.
Regeneration and review are deferred until Linux qualification, as requested.

## Patch layout

All patches target `c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`:

1. `patches/prefixlm-engine.patch`: complete engine/common/server integration,
   CLI attention option, existing architecture-test extensions, and documentation.
2. `patches/ggml-graph-size.patch`: independent null-pointer arithmetic fix.
3. `patches/text-codec.patch`: tokenizer export, Mistral splitting, byte fallback,
   and Unicode template trimming.

Use the [README build instructions](README.md) on a clean pinned checkout.
The engine patch includes the earlier small library replacement; do not apply
both. `scripts/prefixlm_comparison/patches/replacement.patch` and the historical
proposal/worktrees remain unchanged for comparative testing. The patch stack
has been applied to a fresh archive of the pinned base and checked against
every modified source file. No commit, push or submission has been made.

## Stock tools

Build directly from the patched submodule:

```sh
cmake -S llama.cpp -B logs/mimir-engine/build \
  -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=ON \
  -DLLAMA_OPENSSL=OFF -DGGML_NATIVE=OFF
cmake --build logs/mimir-engine/build --target llama-server llama-cli test-llama-archs -j 6
logs/mimir-engine/build/bin/llama-cli \
  --model logs/mimir-chat/mimir-text-f32.gguf \
  --ctx-size 2048 --batch-size 1024 --ubatch-size 1024
```

The CLI starts its own server and uses the same request path. For a separately
running the packaged snapshot server, explicitly use `--parallel 1` and select batch capacity large
enough for the entire rendered conversation. `--attention causal` is available
as a control; no raw phase switching is required by clients.

## Verification

```sh
ctest --test-dir logs/mimir-engine/build -R '^test-prefix-lm-' --output-on-failure
ctest --test-dir logs/mimir-runtime/build --output-on-failure
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/run_matrix.py \
  --metal --real --full-context --output logs/mimir-engine/final-matrix
```

`test-llama-archs --prefix-lm` reuses the existing generated architecture models;
no model download is required. It covers metadata defaults, explicit attention
overrides, prefix visibility, answer causality, internal answer splitting,
new-turn recomputation, capacity, prohibited memory mutations, state operations,
and prefix/answer abort recovery. The parent CTest suite also runs these tests.

Run the real-model HTTP suite against a local stock server with 256 context
and 224 logical/physical batch capacity, `--parallel 1`, and
`--slot-save-path logs/mimir-engine`:

```sh
logs/prefixlm-comparison/venv/bin/python native/mimir/tests/server_e2e.py \
  --url http://127.0.0.1:18181 --output logs/mimir-engine/server-final-e2e.json
```

It checks HF token-prompt and chat parity, full prompt processing without cache
reuse, concurrent queued requests, rejected options and oversized prompts,
stream disconnect, slot save/restore rejection, and subsequent recovery.
The server's apply-template endpoint omits BOS because server tokenization adds
it; token parity checks reproduce that composition rather than requiring the
intermediate string alone to match HF.

The later API/precision audit is in [REVIEW.md](REVIEW.md) and
`review-results.json`. Earlier results and hashes are recorded in `engine-results.json`, with detailed logs
under `logs/mimir-engine`. The existing local ASan startup blocker remains;
UBSan is tested locally and combined ASan/UBSan is configured in Linux CI.
Remote CI has not run. The original snapshot did not qualify weight quantization,
parallel scheduling or persistence; later reports linked above supersede those gaps.
Non-Apple GPU backends remain unqualified.


The later [follow-up results](followup-results.json) cover safe answer rollback
and template-verified BF16/Q8_0/Q4_K_M chat runs. Strict Metal reference
failures remain recorded; see [REVIEW.md](REVIEW.md) for the correction to the
earlier summary.
