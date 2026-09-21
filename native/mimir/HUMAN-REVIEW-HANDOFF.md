# Human review hand-off: PrefixLM and generation persistence

Prepared 2026-09-18. This document describes the release candidate for review;
it is not an assertion that upstream review or final sanitizer qualification is complete.

## Start here

The parent repository branch is `codex/prefixlm-linux-testing`. Its llama.cpp
submodule pins **`8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`**, based on
**`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`**. The runtime is unchanged from the
Linux-tested revision. Later parent commits add evidence, acceptance policy,
packaging and the final sanitizer runner, not new inference behavior.

Read these in order:

1. This document for scope and review priorities.
2. [Candidate package](patches/release-candidate/README.md) and its
   [manifest](patches/release-candidate/manifest.json) for exact patch/tree identities.
3. [PrefixLM contract](../../llama.cpp/docs/development/prefix-lm.md) and
   [generation persistence contract](../../llama.cpp/docs/development/generation-persistence.md).
4. [Linux report](LINUX-TESTING-REPORT.md) and
   [final qualification policy/checklist](FINAL-QUALIFICATION.md).

For a fresh checkout:

```bash
git clone --branch codex/prefixlm-linux-testing https://github.com/schneiderkamplab/HRM-Text.git
cd HRM-Text
git submodule update --init llama.cpp mimir
python3 native/mimir/tools/package_patches.py
python3 native/mimir/tests/test_cuda_memcheck.py
```

This verifies packaging and local policy tests, not inference or CUDA execution.
Use [linux-testing.md](../../linux-testing.md) for dependencies, fixtures and runtime
commands. Model weights, raw build logs and GPU traces are not included in Git.

## Patch boundaries

The numbered files under `patches/release-candidate/` are the review units.
Apply them in order to a separate clean llama.cpp checkout at the base above.
Do not apply them on top of the already patched submodule.

| Patch | Scope | Main review targets |
| --- | --- | --- |
| `01-ggml.patch` | Independent graph-size signed-overflow/undefined-behavior fix. | Arithmetic types and size bounds in `ggml/src/ggml.c`; preserve existing allocation semantics. |
| `02-text-codec.patch` | Mimir `spm-bpe-mistral` tokenizer selection, byte fallback, converter metadata and Unicode/Jinja text behavior. | Converter/runtime agreement, token classification, Unicode case/whitespace behavior and effects on other tokenizers/templates. |
| `03-prefixlm.patch` | Generic attention mode and complete-prefix/mixed decode APIs; sequence lifecycle, masks, shared ownership/capacity, safe copies/forks, KV/phase/logit snapshots, fixed adapters/control vectors, CLI/server integration and exact complete-prefix caching. Includes the Linux GCC include and causal-mask performance fix. | `include/llama.h`, context/batch/KV code, common prompt processing, server scheduler, tool adaptations and architecture/reference tests. |
| `04-generation-persistence.patch` | Built-in and common sampler serialization, grammar/reasoning/backend state, retained server generations, pending-token bookkeeping and OpenAI parser continuation. Supports ordinary causal decoding and integrates with PrefixLM. | Sampler/grammar/reasoning code, common sampling, server task/schema/context code and existing sampler/parser tests. |

`generation-persistence-standalone.patch` is an **alternative** to 04 for a tree
with only 01 and 02 applied. It requires no PrefixLM API. Do not apply both variants.
The codec prerequisite is useful for Mimir testing; sampler serialization itself is
not conceptually tied to the Mimir tokenizer.

Three requested capabilities stay in the main patch: exact complete-prefix caching,
ordinary custom-state parity, and live parent/child fork parity. “Parity” does not
mean a new serializer for arbitrary application objects or whole scheduler groups;
ordinary encoder/decoder modes do not provide one either. Generic sampler and saved
server-generation persistence belong exclusively to the separate fourth patch.

The parent repository's `native/mimir` wrapper/client, HTTP harness, reports, policy
runner and CI are supporting artifacts. They are not automatically part of an
upstream llama.cpp PR. Reusable engine/sampler/parser tests and the tiny independent
reference generator are already in the corresponding llama.cpp patches. Decide which
additional consuming-project evidence upstream reviewers should receive.

## Commit history versus candidate patches

The existing history is preserved:

| Commit | Purpose |
| --- | --- |
| `c3e60e59d` | ggml fix |
| `0b29d4555` | text codec |
| `b417698f5` | initial main PrefixLM implementation |
| `6f60f7472` | generic sampler/server persistence |
| `8f4f4ef8f` | Linux include and ordinary causal-mask performance fix |

Candidate 03 folds the last commit into the main feature. Candidate 04 is generated
against that corrected main tree. Cherry-picking only `b417698f5` would omit the
Linux fix. The package tool reconstructs the qualified combined Git tree exactly,
including file modes, and checks the main-only/standalone public API boundaries.
It does not rewrite branches or prove behavior by itself.

Earlier files under `patches/` and `patches/review-drafts/` are historical evidence.
Do not combine them with the candidate stack or add the Linux fix twice.

## What deserves the closest review

### 1. PrefixLM semantics and state ownership

The complete prefix is bidirectional; answers are causal. Each new chat request
includes the full retained conversation and generation header. A prefix must fit
one physical batch, including every recurrent invocation. First-call guessing or
chunking it as ordinary causal prefill would silently change model behavior.

Review per-sequence boundaries in mixed batches, shared input owners and complete
future-prefix dependency validation. Equal token IDs or equal history lengths do
not prove interchangeable KV. Shared rows and full forks must count physical cells
once; replacing one owner cannot reclaim cells still used by another. Bounded
answer copies require established shared dependencies, not merely matching positions.

Review mutation ordering and failure behavior: invalid admission should preserve
existing state; execution failure clears affected sequences. Full-context restore
and cross-stream copy failures have broader invalidation rules documented in the
contract. Check empty/self operations, sparse IDs, suffix trimming, ID remapping,
cancellation and the validity of saved boundary logits after each operation.

The context/memory operations are serialized by the caller. PrefixLM decode
synchronizes before returning. Adapter fingerprints detect accidental mismatch;
they are not authentication or a replacement for selecting identical model weights.

### 2. Ordinary-mode regression and API design

Confirm that causal/bidirectional behavior and their existing formats stay intact.
The Linux performance fix selects the prefix-aware mask specialization outside the
inner loop; ordinary causal execution retains its original visibility predicate.
Do not reintroduce a per-cell map lookup into ordinary attention during cleanup.

Review API names, return/error contracts and whether the new enum/entry points fit
upstream conventions. The supported-client audit is in the PrefixLM contract:
several tools explicitly reject PrefixLM or force causal calibration semantics.
Not every example has a polished user-facing rejection message. Avoid interpreting
model metadata as universal support across every llama.cpp client.

### 3. Snapshot and resumption boundaries

Library KV snapshots and sampler snapshots are different layers. Sampling may have
already selected a token not yet decoded; resumption must preserve that pending token
rather than sample twice or replay the last bidirectional prefix token causally.
Audit sampler RNG/history/adaptation, grammar stacks/partial UTF-8/lazy triggers,
reasoning delimiter/budget state, and graph-safe backend restore. Attached contexts
must be synchronized before sampler snapshot/restore.

Audit malformed/truncated input, length bounds, matching configurations and whether
restore preserves or clears state at the documented failure point. Snapshots require
the same runtime/model/vocabulary/configuration; old development formats are rejected,
not migrated. Legacy ordinary prompt/KV slot files remain usable but are not complete
retained generations. The tagged server envelope is version 3; sampler format SMP2
and common sampler bundle version 2 are separate version domains.

Review idle-slot eviction protection, explicit-slot admission, replacement/consumption
of stale retained metadata, save/rename behavior and fresh-process remapping. OpenAI
parser replay preserves logical tool IDs, not the original network connection:
streaming deltas/native text are incremental; nonstream messages and final Responses
objects are cumulative. Each request has fresh transport IDs/framing. The original
prompt and parser/sampling configuration must match.

### 4. Exact-prefix cache behavior

Only the identical complete token prefix hits. Changed or extended prefixes require
full evaluation. A hit restores boundary logits and starts a fresh sampler with prompt
history; it is not retained-generation continuation. Cache-enabled requests use host
sampling on both hits and misses. `n > 1` follows normal prefill/fork scheduling rather
than the cache fast path. Review invalidation and retained-generation interaction.

## Evidence and accepted limitations

The [Linux report](LINUX-TESTING-REPORT.md) records CPU release and ASan/UBSan passes,
actual B200 CUDA execution, isolated main/generic builds, BF16/Q8/Q4 tests and
restart/remapping. Initial HTTP coverage was 1,775 checks; 894 affected checks were
rerun after the mask fix. These are overlapping executions, not unique test counts.
The ordinary causal-prefill overhead fell from roughly 4–5% to 0.14%, within measured
drift on the controlled tiny-model benchmark. This is not a universal performance
claim. Latest local preparation reruns pass 8/8 macOS release and 8/8 CPU UBSan CTests.

The project owner accepted two numerical findings as nonblocking for this PR scope:

- Tiny CUDA errors reach about 0.0023 against a strict 1e-4 limit, with all 130 top
  choices matching. Tested causal baseline/candidate errors are identical; this does
  not establish the cause of every PrefixLM discrepancy.
- BF16/Q8/Q4 exceed the shared 0.03 FP32-reference limit. Measured errors and token
  differences remain recorded; no universal tolerance or model-quality guarantee
  is asserted.

These are explicit acceptance decisions, not rewritten green results. Reviewers may
challenge the rationale. New regressions do not inherit acceptance automatically.
Use [release-source-manifest.json](release-source-manifest.json) for current harness/CI
identity, [linux-results.json](linux-results.json) for measurements and
[linux-evidence/](linux-evidence/README.md) for committed diagnostics. Earlier source
manifests refer to their original revisions and are intentionally not refreshed.

## Known issues, restrictions and cleanup before final submission

- **Final sanitizer execution is pending.** The new graph-enabled CUDA runner has
  five passing local policy/process tests but has not yet been validated with real
  Compute Sanitizer output. It keeps API reporting on and allows only paired handled
  graph-update error 910 reports when explicitly enabled. Unknown formats, memory
  errors, other API failures, missing summaries and application failures reject.
  Review this gate carefully: its raw `--error-exitcode 0` is safe only through the
  wrapper's final classification, never as a standalone CI acceptance command.
- **Graph-enabled findings remain visible.** The previous default engine memcheck
  returned nonzero for the upstream handled graph-update fallback; no invalid device
  accesses were reported. Graph-disabled diagnostics passed but do not replace the
  final graph-enabled check. Do not globally suppress API errors to obtain a green run.
- **Temporary test filename collision.** Architecture tests use a shared filename
  derived from architecture/seed. Run parallel lanes in separate working directories
  (the new wrapper does). Upstream cleanup could use unique filenames; do not label
  the original collision failures as runtime defects or erase them from the evidence.
- **No blanket platform claim.** This evidence covers Mac CPU/Metal and Linux CPU/B200.
  Final candidate Linux CPU sanitizers and runner checks are listed in the final
  checklist. No GitHub workflow run, iOS deployment or exhaustive architecture/backend
  qualification is claimed. Optional server TLS was disabled on the Linux Conda build.
- **Intentional model/memory limits.** The qualified PrefixLM contract excludes encoder,
  hybrid/recurrent-memory, SWA, diffusion, multi-position and embedding-output paths.
  Full host snapshots are supported; partial/device snapshots need separate rollback
  guarantees. Shared input rows require unified KV; separate-stream bounded copies
  may copy a full buffer before trimming metadata.
- **Intentional integration limits.** No incremental/partial prefix cache reuse,
  context shifting, speculation or multimodal integration. Activated LoRA is excluded;
  fixed LoRA/control vectors are supported with live-mutation restrictions. Server
  retained generations exclude parent/child groups and Anthropic transport. Arbitrary
  custom state remains caller-owned. These are not implied decoder-parity omissions.
- **Final editorial/API cleanup remains a review decision.** Review public names,
  serialization versions, error messages and the size of server-context additions.
  Confirm upstream test placement and documentation fit; there is no promise that
  maintainers will accept the current API unchanged. Native project docs and historical
  reports contain superseded instructions: use the candidate guide for application.
- **Refresh artifacts after any code change.** The package generator pins exact commits.
  Update its revision inputs deliberately, regenerate hashes/patches and rerun affected
  checks; do not edit a patch alone or assume old evidence qualifies a changed tree.

All implementation work was AI-assisted under user direction. A human submitter must
understand and own the code, maintenance and upstream communication. This hand-off is
review material; it does not create or submit a PR.

## Requested reviewer outcome

Confirm the four scopes and independent generic persistence boundary; identify any
correctness/API blockers with affected files/tests; distinguish required cleanup from
future features. Complete the bounded checks in [FINAL-QUALIFICATION.md](FINAL-QUALIFICATION.md)
and record their exact revision/results. Only then decide whether the candidate is
ready for final PR packaging and submission.
