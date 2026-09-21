# Experimental MixedLM

MixedLM is opt-in and defaults off. It approximates full PrefixLM by freezing
older prompt representations. It is not numerically or behaviorally equivalent
to exact PrefixLM, and it does not extend the model's trained context window.

## Algorithm and API

The llama.cpp branch is `codex/mixedlm`, based on PrefixLM commit
`8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`.

Set `llama_context_params.mixed_lm = true` when creating a PrefixLM context.
Process the initial complete prompt with `llama_decode_prefix`. On the next
turn, call `llama_decode_mixed_lm` with tokens beginning at the previous prompt
boundary: the previous assistant answer, its closing chat-template tokens, and
the new user prompt plus assistant header. The previous answer's causal KV is
removed and these suffix tokens are recomputed bidirectionally, attending to
all frozen older keys. Subsequent answer tokens use ordinary `llama_decode`.
The suffix becomes part of the frozen prompt for the following turn.

No attention kernel changes are needed: only suffix queries execute under the
existing PrefixLM mask, with the extended prefix boundary. Older queries never
see the new suffix. Shared sequence admission counts retained physical KV cells
once and requires identical dependencies for shared input rows. A full
`llama_decode_prefix` call refreshes the entire sequence, even in MixedLM mode.

The caller must ensure the frozen tokens are unchanged. The shared Mimir Session
checks exact token-prefix equality using the model's chat template. Edited
history, different conversations, model/settings reloads, cancellation, errors,
actual compaction and mismatching templates trigger a full refresh. Counting
tokens does not discard the cache. Requests for every prompt logit also refresh
fully so their output-row contract stays intact.

This is a library API and Flutter setting, not a llama-server CLI option. Rebuild
all clients because the context parameter structure changes. MixedLM snapshots
use PrefixLM state version 3; exact mode keeps version 2. Cross-mode restoration
is rejected. The Flutter archive saves the setting and transcript, not KV;
a restarted app begins with a cold complete-prefix evaluation.

## App control

Flutter: **Model and settings → MixedLM mode**. Switching reloads the native
context. Off remains exact PrefixLM. The SwiftUI client is unchanged and keeps
its exact default. The full transcript remains available in either mode.

## Local evidence — 2026-09-20

Apple M2 Max, 96 GiB RAM. DFM-Mimir Q4_K_M GGUF SHA-256:
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
Every real-model chat uses Mimir's own chat template.

- Eight native CTest cases pass: HRMText and llama tiny-model engine tests,
  session tests for PrefixLM/causal/absent metadata, text, Jinja and reasoning.
- Engine coverage includes flash attention on/off, an independent blockwise
  bidirectional oracle, repeated extensions, causal answers, opt-in rejection,
  bad positions without mutation, shared-cell capacity, snapshot round trips,
  incompatible restore rejection, full refresh, and abort recovery.
- Session coverage includes token-prefix mismatch, invalid-budget preservation,
  all-logit refresh, reset/cancellation and non-PrefixLM rejection.
- Flutter: six host unit/widget tests and static analysis pass. The real-model
  Settings toggle/reload/reuse/persistence flow passes on Android API 36 and
  iOS 18.4 simulators. macOS release and iOS simulator app builds pass with
  Xcode 27.0.
- Real Q4_K_M CPU exact/MixedLM and Metal MixedLM C ABI smoke tests pass:
  multi-turn reuse, intervening counts, edits, conversation changes, malformed
  history, cancellation/recovery, streamed compaction, reuse after compaction,
  and destruction during generation.

Illustrative time to first token from the CPU smoke runs:

| Turn | Exact | MixedLM | Frozen tokens reused |
| --- | ---: | ---: | ---: |
| First arithmetic question | 1.19 s | 1.13 s | 0 |
| Remember a name and city | 1.55 s | 0.44 s | 83 |
| Recall the name and city | 1.92 s | 0.46 s | 110 |

Metal MixedLM took 0.13–0.15 s on the two cached turns. These are smoke-test
observations with concurrent build/test activity, not controlled speed claims.
The later recall turn also has slightly different history because earlier
answers differ.

**Observed quality regression:** after answering “2 + 2”, exact mode answered
“Husk navnet Freja og byen Odense. Svar kort.” with “Freja og Odense er husket.”
MixedLM on both CPU and Metal instead repeated “2 + 2 = 4.” It subsequently
answered the recall question with “Freja fra Odense.” Functional correctness of
the approximation does not imply equivalent instruction-following quality.

## Reproduction and limits

Configure `native/runtime` with `-DMIMIR_BUILD_TESTS=ON`, build its test targets,
and run CTest. The existing fixture directory is configured with
`MIMIR_FIXTURE`; generate it using the [PrefixLM comparison tooling](../../scripts/prefixlm_comparison/README.md)
when testing a fresh checkout. The engine tests generate their own tiny models.

Run the real-model C ABI check with:

```sh
python3 native/runtime/tests/smoke.py /path/to/MimirRuntime /path/to/model.gguf \
  native/app/assets/profile.json cpu --mixed-lm --report mixed-cpu.json
```

Omit `--mixed-lm` for the exact baseline; use `metal` for a Metal build. Local
reports are in `logs/mixedlm-{cpu,exact-cpu,metal}-smoke.json` and are not shipped.

Existing PrefixLM architecture/backend limits still apply. A complete new suffix
must fit a single physical batch (`n_ubatch`). There is no automatic periodic
full-refresh policy. Long-chat quality, BF16/Q8 mixed-mode comparisons, physical
mobile devices, CUDA/Vulkan MixedLM and Linux sanitizer runs remain unqualified.
Previously recorded exact PrefixLM backend evidence is not MixedLM evidence.
