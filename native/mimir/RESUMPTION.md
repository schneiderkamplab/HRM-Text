# PrefixLM control vectors, resumption and mixed phases

Follow-up: [SHARING.md](SHARING.md) supersedes this report's single-owner and
full-sequence-copy-only limits; numerical results below remain historical evidence.

Date: 2026-09-18. Working tree based on llama.cpp
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`.
This report supersedes the corresponding restrictions in [STATE.md](STATE.md).
Machine-readable evidence and source hashes: [resumption-results.json](resumption-results.json).
Detailed logs: `logs/mimir-resumption/`. Packaged patches are intentionally unchanged.

## Implemented behavior

1. **Fixed control vectors.** Existing graph helpers now work in PrefixLM mode.
   Install before prefill or after clearing all live KV. Identical reapplication,
   including partial-layer data updates, is allowed while KV is live; a changed
   effective configuration is rejected. Restore checks effective vector values
   alongside LoRA weights/scales. Nonzero synthetic vectors change logits and round-trip.
2. **Boundary logits and sampler state.** PrefixLM context/sequence snapshots now
   include the final requested logit row per sequence. `llama_get_logits_seq`
   retrieves it after restore/fork. Suffix trimming invalidates it. Each active
   sequence retains up to one vocabulary-sized float row; forks initially share it.
   Generic `llama_sampler_state_*` APIs separately preserve supported host sampler
   RNG, adaptation and history. Common snapshots also preserve recent-token history.
   Matching configuration/vocabulary is required; failed sampler loads are atomic.
   Successful chain restore invalidates borrowed child pointers. No custom-sampler
   ABI extension was added. The unreleased PrefixLM envelope is version 2; ordinary
   causal/bidirectional state formats are unchanged.
3. **Explicit server resumption.** Native `/completion` accepts `retain_state: true`
   with an explicit slot ID. At a token-budget stop, it retains KV, phase, boundary
   logits, sampler state, the already-sampled token awaiting decode, original prompt
   and emitted/withheld text bookkeeping. `resume: true` continues with the same
   original prompt/settings and an additional token budget. Slot save/restore stores
   this in one file, supports restart and destination-ID remapping, and requires
   `--slot-save-path`. Saving uses temporary-file replacement. Automatic slot selection
   and cache-pressure eviction preserve retained sessions; explicit fresh requests
   or slot erase can discard them. Erase wakes deferred work. Ordinary new chat turns
   still recompute their complete templated prefix.
4. **Mixed phases.** `llama_decode_prefix_mixed` declares exclusive prefix ends per
   newly initialized sequence. A batch can contain complete prefixes, causal answers
   following those prefixes, and answers for other live sequences. Existing attention
   masks use each sequence's boundary; no new backend kernel is needed. Split KV
   groups whole sequences when a prefix is present. The server reserves batch space
   for a pending complete prefix while admitting ongoing answers.
5. **Shared physical capacity.** Unified KV admission counts a shared cell once.
   Full forks therefore no longer consume duplicate logical capacity. Branch additions
   consume new cells; replacement cannot reclaim cells still owned by siblings. Full
   state restore preserves sharing. Ordinary answer admission uses used-cell counts
   and position deltas, avoiding a cache-wide ownership scan per generated token.
   Separate-stream copies still consume distinct physical storage.

The [library contract](../../llama.cpp/docs/development/prefix-lm.md) and public header
specify API details. Server bookkeeping remains in the stock server, not the Mimir app.

## Bounded test evidence

| Check | Result |
| --- | --- |
| Release integration, CPU + Metal | 7/7 tests; 3,948 HRM/Llama engine assertions |
| CPU UBSan integration | 7/7 tests; 1,974 engine assertions; no sanitizer diagnostics |
| Ordinary HRM/Llama architecture regression | Passed CPU/device comparisons and supported model round-trips |
| Q8 stock server, separate/unified KV, restarts and fixed controls | 154/154 checks |
| Independent HF oracle, CPU and CPU UBSan | 29/29 steps each |
| Independent HF oracle, unfused Metal | 27/29 steps; strict numerical failures below |
| Independent HF oracle, fused Metal | 26/29 steps; strict numerical failures below |

Engine coverage adds nonzero vectors and identity checks; persisted boundary logits;
stochastic continuation with default distribution sampling, Mirostat 2, adaptive-p,
DRY/XTC and penalty history; truncated sampler rejection; mixed phase rows and invalid
admission; full forks that fit physically but exceed logical capacity; capacity after
branching/replacement; and shared-state restoration. Existing state corruption,
sequence isolation, rollback, adapter, abort and ordinary attention controls remain.

Server tests preserve exact stochastic token sequences through in-memory continuation,
file restore and fresh-process restore into another slot. They check incompatible
settings/new-turn rejection, automatic slot protection, stop strings spanning the
retention boundary, text without duplication, and capacity release after consumption.
Existing template parity, concurrency, cancellation and `n > 1` tests also run.
Startup LoRA/control-vector fixtures are zero-valued integration checks; nonzero effects
are tested in the engine suite. This is not trained-adapter quality evidence.
Every real-model chat uses Mimir's checkpoint template and pinned HF tokenization.
The earlier BF16/Q8_0/Q4_K_M evidence remains in [QUALIFICATION.md](QUALIFICATION.md);
this follow-up does not claim to rerun that entire weight matrix.

### Numerical findings, without changing thresholds

The oracle threshold remains maximum absolute logit error `1e-4`.

| Case | CPU | Fused Metal | Unfused Metal |
| --- | ---: | ---: | ---: |
| New nine-token mixed prefix + answer batch | 5.96e-7 | 7.2297e-4 | 6.8754e-4 |
| Same-sized ordinary causal batch | below 1e-4 | 7.2947e-4 | 7.3984e-4 |

Both new Metal cases match all 9/9 top-token choices. The similar error in an ordinary
causal batch points toward batch-shape/backend precision, rather than a PrefixLM-only
mask error; that is an inference, not a completed kernel diagnosis. The previous
fused-Metal three-row causal continuation miss (`1.0558963e-4`, top-1 3/3) remains.
These new cases are larger deviations than the previously accepted slight exceedance.
Their tolerance policy and backend attribution remain an explicit qualification item.
CPU's independently computed full-logit agreement validates the mixed-phase mask.

## Reproduction

Use the working tree, not the older packaged patches:

```sh
cmake --build logs/mimir-engine/build --target test-llama-archs llama-server -j8
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a hrm_text -s 42
logs/mimir-engine/build/bin/test-llama-archs --prefix-lm -a llama -s 42
cmake --build logs/mimir-runtime/build -j8
ctest --test-dir logs/mimir-runtime/build --output-on-failure
cmake --build logs/mimir-runtime/ubsan -j8
ctest --test-dir logs/mimir-runtime/ubsan --output-on-failure
```

The upstream-reproducible `llama.cpp/scripts/prefix-lm-reference.py` now adds a mixed
phase case and a same-shaped causal control. Its existing dependency/revision setup
is documented in the library contract. Local reference runs reuse the prior pinned
HF float rows and concatenate the independently computed rows for these two cases.

Launch the server with the Q8 model, `-ngl 999 -c 512 -b 224 -ub 224 -np 2 -fa on`
and `--slot-save-path logs/mimir-resumption`; test both with and without `--kv-unified`.
Run `native/mimir/tests/server_e2e.py --parallel --resumption --url <url> --output <json>`
using `logs/prefixlm-comparison/venv/bin/python`. Restart the server with identical
model/configuration and run `--parallel --resume-only` against the same save directory.
Local drivers and exact commands are retained under the evidence directory.

## Remaining restrictions and priorities

| Priority | Restriction or open item | Why it remains |
| --- | --- | --- |
| Before packaging/review | Linux release, ASan/UBSan and controlled causal/bidirectional performance regression | Mac checks cannot establish Linux behavior or stable performance. New logit retention adds a vocabulary-sized copy per requested boundary; measure it. Reminder: Linux testing comes before packaging and review. |
| Before PR readiness | Numerical qualification of the new larger-batch Metal cases; API/state-format review | Preserve strict failures and decide a justified backend tolerance or correction. Review additive mixed/logit/sampler APIs and snapshot ownership contracts. |
| Integration extension | Grammar, reasoning-budget, custom and backend sampler snapshots | These contain additional grammar/parser/device state. Current APIs return unsupported, rather than resuming with reset state. Host built-in distribution/adaptive/history samplers are implemented. |
| Integration extension | Server retention only for a single native completion; no OpenAI parser or child-generation retention | Their response/parser and parent-child scheduling state needs an explicit snapshot contract. Normal OpenAI chat and multiple children work without retention. |
| Correctness rule | Complete prefix in one physical batch; no retained-prefix edits, position shifting or answer holes | Bidirectional recurrent dependencies need the whole prefix. Recompute when prefix content changes. Mixed phases do not relax completeness. |
| Correctness rule / extension | Fixed context-wide adapters and vectors; full-sequence forks; one sequence ID per input token | Existing KV depends on weights and token history. Full forks can subsequently trim answer suffixes. Dynamic per-sequence weights/shared input ownership need additional scheduling semantics. Activated LoRA also needs bidirectional activation semantics. |
| Qualified scope | Decoder token-input KV models and complete host snapshots | Encoder, recurrent/hybrid, SWA, diffusion, multi-position, embedding-output, partial-memory and device-restore paths need their own memory/mask/failure audit. |
| Deferred client work | Ordinary prompt-cache reuse, speculation, multimodal and unadapted examples | Existing replay/chunking or lifecycle assumptions remain incompatible. Explicit generation resumption does not authorize last-prefix-token replay. Multimodal remains low priority. |

Snapshots require the same model weights and compatible runtime, KV and adapter
configuration. They are not cross-version interchange or self-contained models.
Context operations remain serialized under the existing thread-safety contract.
The global backend copy-update failure path has not been fault-injected locally.
Wiki validation retains only the two pre-existing benchmark-charts errors.
No patches were regenerated and no commit, push or PR was created.
