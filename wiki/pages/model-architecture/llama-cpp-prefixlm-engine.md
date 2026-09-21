---
type: Implementation Report
title: Engine-Level PrefixLM in llama.cpp
description: First-class attention mode, complete-prefix decode API, shared server/CLI integration, and direct engine validation.
tags: [mimir, llama-cpp, prefixlm, engine, testing, metal]
status: draft
last_updated: 2026-09-18
confidence: high
---
# Engine-Level PrefixLM in llama.cpp

The user requires generic PrefixLM behavior in llama.cpp alongside causal and
bidirectional support. The fork now exposes `LLAMA_ATTENTION_TYPE_PREFIX_LM`,
`llama_get_attention_type`, and `llama_decode_prefix`. Unspecified attention
selects PrefixLM from model metadata; explicit causal/bidirectional controls
remain available. The implementation reuses existing attention graphs/masks.

`native/mimir/ENGINE.md` documents builds, the patch stack and test commands.
The engine's own contract is in `llama.cpp/docs/development/prefix-lm.md`.
`native/mimir/engine-results.json` retains the measured results and hashes.
The registered engine remains based on
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`; changes are local and uncommitted.

## Committed Linux hand-off (2026-09-18)

Supersedes the uncommitted-source status recorded below. Branch `codex/prefixlm-linux-testing`
now records four llama.cpp commits: ggml UB fix, text codec, main PrefixLM and generic
persistence. The parent gitlink pins `6f60f7472fead8da5289e06c9d79b47dd4763043`; the committed tree matches the tested
source manifest. `native/mimir/linux-handoff.json` lists the exact commit stack.
`linux-testing.md` now describes checkout via the pinned submodule, without applying
patches. Linux tests and final PR packaging/review are still pending.

## Ordinary decoder resumption and feature split (2026-09-18)

Supersedes the preceding PrefixLM-only server activation, server envelope version 2
and sampler-in-engine test counts below. Ordinary causal text decoding now supports
retained generation restart/remapping, including pending sampled token and OpenAI
parser continuation. Legacy prompt/KV files remain compatible but not resumable as
generations; retained files use a tagged version-3 envelope. Idle cache eviction skips
retained slots, while completed causal requests retain ordinary prompt/KV behavior.

Two review drafts separate PrefixLM from generic sampler/server persistence. Exact
complete-prefix caching, custom-state parity and live parent/child fork parity stay
in the main patch. The generic feature builds without any PrefixLM API and has an
alternate standalone application. Both application paths were byte-compared against
their source trees. Historical packaged patches remain untouched; the draft codec
prerequisite was refreshed for `spm-bpe-mistral` support.

`native/mimir/DECODER-RESUMPTION.md` and `decoder-results.json` record combined causal
118 HTTP checks, combined PrefixLM 182, standalone persistence causal 118, and
main-only 3,880 engine + 72 HTTP/cache checks. Release and CPU UBSan pass 8/8 CTests.
Host sampler continuation now runs in `test-backend-sampler --test host_persistence`,
independent of the PrefixLM engine test; CI and `linux-testing.md` invoke it explicitly.
Real chat tests retain Mimir's own chat template. Causal HTTP evidence uses HRMText,
not a claim of architecture-wide or Linux/CUDA qualification. Linux tests and final
packaging/review remain pending in the agreed order.

## Persistence and complete-prefix cache follow-up (2026-09-18)

The proposed-only grammar/reasoning/parser/cache/backend limits below are **superseded**
by [PERSISTENCE.md](../../../native/mimir/PERSISTENCE.md) and its source/evidence manifest.
Built-in grammar, reasoning-budget and backend sampler state now round-trip; OpenAI
Chat/Responses parser continuation uses text replay with stable tool IDs. Exact whole-
prefix cache hits restore KV plus boundary logits and use fresh host sampling. Partial
prefix reuse remains invalid. The generic sampler APIs apply independently of attention
mode. Ordinary encoder/decoder slot files do not serialize arbitrary application objects
or in-flight parent/child groups; existing clone/copy and live forks retain parity.

Local evidence: release 8/8 (4,280 engine checks), CPU UBSan 8/8 (2,140), HTTP 182/182,
CPU reference 31/31, graph-bound backend restore on CPU/Metal/UBSan, and bounded reasoning/
tool parser continuation. Earlier strict Metal numerical deviations remain historical
open evidence. CI now verifies source hashes and includes CPU sanitizer/backend tests
and an optional trusted CUDA lane; clean checkout cannot qualify until the modified
submodule source is recorded. Linux execution, final packaging and review remain pending.

## Shared ownership and bounded-copy follow-up (2026-09-18)

The one-owner/full-sequence-only limits below are **superseded** by
`native/mimir/SHARING.md` and `sharing-results.json`. Unified KV accepts shared input
rows after checking all owners' cached and in-batch dependencies, including future
prefix rows. Admission and saved logits cover every owner; physical capacity counts
shared rows once. Bounded `[0, end)` copies work on both layouts when they contain
the entire prefix. Answer-only ranges require already-shared preceding KV and discard
the destination's later suffix. Shortened copies invalidate boundary logits.
Separate-stream coupled rows remain an existing batch-splitter limitation; separately
restored/recomputed histories are not assumed identical without shared physical cells.

The report prioritizes grammar/reasoning-budget persistence, OpenAI parser continuation
and exact-complete-prefix caching next, distinguishing those integration gaps from
custom callback contracts, group scheduling and device-state synchronization. Broader
full-attention dense/MoE qualification is preferred over speculative support for temporal
recurrent, sliding-window or diffusion architectures without a concrete trained model.
Final evidence: release 7/7 (4,264 engine checks), CPU UBSan 7/7 (2,132), server
104/104, independent CPU/UBSan 31/31. New shared-owner oracle cases pass on Metal;
previous strict Metal failures are unchanged. Linux/sanitizer/performance qualification
still precedes packaging and final review.

## Linux qualification hand-off (2026-09-18)

The [Linux testing runbook](../../../linux-testing.md) defines CPU release,
ASan/UBSan, CUDA flash on/off, Compute Sanitizer, real-model server restart and
BF16/Q8/Q4 lanes, plus controlled baseline/candidate performance testing. It has
not been executed on Linux in this documentation turn. CUDA is an existing backend;
PrefixLM CUDA qualification remains pending. The runbook distinguishes FP32 storage,
KV and oracle outputs from potentially reduced internal arithmetic.

The hand-off now explicitly includes shared-owner/bounded-copy acceptance, the latest
4,264 release / 2,132 CPU UBSan / 104 server local counts, a 31-step oracle revision
check and shared-capacity/copy performance measurements. It separates implemented
features from recommended persistence/parser/cache follow-ups, which are not yet
positive qualification targets.

The existing `.github/workflows/mimir-runtime.yml` applies older packaged patches;
it cannot qualify the current uncommitted source. Transfer the exact source snapshot
for manual Linux testing and fix CI source preparation during subsequent packaging.
Sanitizers/performance are components of Linux qualification, not work that waits
until after it. Only packaging/final PR readiness waits for the agreed evidence.

## Current control/resumption/mixed-phase status (2026-09-18)

The earlier no-control-vector, no-logit/sampler persistence, no-server-resumption,
separate-phase and conservative logical-capacity limits are **superseded** by
`native/mimir/RESUMPTION.md` and `resumption-results.json`. Fixed control vectors use
existing graph helpers and participate in state identity. Context/sequence envelopes
now include boundary logits; generic sampler APIs preserve supported host RNG/history/
adaptation independently. Native server completions can explicitly retain and resume
at a token budget, including one-file persistence, fresh-process restore and slot-ID
remapping. Pending sampled tokens and withheld/emitted text are preserved. Retained
slots survive automatic selection/eviction. Fresh chat turns still recompute the whole
Mimir-templated prefix.

`llama_decode_prefix_mixed` supplies per-sequence prefix boundaries to existing masks;
the server can combine complete prefixes and causal answers. Unified capacity counts
shared physical cells once and uses a fast answer-append path. Prefix completeness,
invalid memory edits and changing weights under live KV remain correctness restrictions.
Grammar/reasoning-budget/custom/backend sampler persistence, OpenAI parser/child
retention, device/partial snapshots and unadapted architectures remain explicit gaps.

Final local evidence: release 7/7 (3,948 engine assertions), CPU UBSan 7/7 (1,974),
and stock-server 154/154. Independent CPU/UBSan each pass 29/29 oracle steps. New
nine-token mixed and ordinary causal batches both exceed strict Metal tolerance
(~6.9e-4 to 7.4e-4 vs 1e-4), with top-1 9/9; CPU mixed error is 5.96e-7. This is
consistent with a batch-shape/backend precision effect, not a proven kernel diagnosis.
The previous small fused-Metal causal miss remains. No tolerance was relaxed. These
new deviations need qualification, distinct from the previously accepted small miss.
Linux release/sanitizers/performance remain required **before packaging and review**.
Packaged patches remain unchanged. Wiki validation has the same two unrelated errors.

## Historical state/fork/adapter status (2026-09-18, superseded where noted above)

The previous blanket persistence, cross-sequence copying and adapter restrictions
are **superseded** by the working-tree implementation documented in
`native/mimir/STATE.md` and its `state-results.json` evidence. Existing library
context/sequence buffer and file APIs now preserve prefix boundaries and next
positions. Full-sequence forks carry that metadata and preserve branch isolation;
server shared-prefix children use the same operation. Fixed ordinary LoRA works
through the existing graph helpers and at server startup. Live KV prevents changes
to the adapter configuration; equivalent saved/restored adapters are identified by
weights/scales rather than pointer identity.

State formats distinguish PrefixLM from ordinary state without changing ordinary
formats. Header/capacity/adapter rejection precedes mutation; failed KV restore
invalidates its destination, preserving unrelated sequences for a sequence restore.
Pending stream copies flush before persistence. Global copy-update failure invalidates
the context; this backend-failure branch has not been fault-injected locally.
Position validation rejects duplicates, holes and inconsistent metadata. A sparse-ID
test found an existing KV serializer ID-bound bug: the mapping range, not the active
sequence count, is now used. Ordinary causal sparse-ID state is regression tested.

State snapshots require the same model and compatible KV configuration. They do
not save logits/sampler state or model weights. Host complete-state persistence is
supported; on-device snapshot error/commit semantics still need an audit. Server
idle-cache save/restore is separately disabled because its standard trim/replay
strategy is invalid for the last bidirectional prefix token. Prefix edits/shifting,
partial-prefix copies, mixed-phase batches, activated LoRA/control vectors, other
memory architectures, speculation and multimodal input remain outside the contract.
The detailed report ranks and explains these restrictions rather than presenting
all of them as inherent PrefixLM limitations.

Validation covers CPU/Metal, flash on/off, separate/unified KV, HRM/Llama, nonzero
synthetic LoRA, file/fresh-context/remapped/corrupt-state restoration, and stock
server forks using Mimir's chat template. The server's zero-LoRA fixture checks
integration only; it is not trained-adapter quality evidence. An initial synthetic
adapter fixture omitted explicit alpha initialization; the corrected fixture is
used for final qualification. Use the established Python 3.12 environment for the
server harness: system Python lacks `zip(strict=True)`.

Final local evidence: release and CPU UBSan integration each pass 7/7, with
3,036 CPU/Metal engine checks and 1,518 CPU UBSan checks respectively. Stock Q8
server passes 125 checks across single/separate/unified/fixed-LoRA runs. Independent
CPU, CPU UBSan and unfused Metal each pass 27/27 steps; fused Metal retains the
unchanged causal-control miss (0.0001055896 versus 0.0001). Ordinary HRM/Llama
architecture regressions pass. Wiki validation still reports only the two
pre-existing benchmark-charts index/frontmatter errors.

Linux release, ASan/UBSan and a controlled performance rerun remain the next
qualification gate, **before packaging and human review**. Packaged patches have
not been regenerated; no commit, push or PR was made.

## Current multi-sequence status (2026-09-17)

The single-sequence restriction described in earlier sections is **superseded**
by the working-tree implementation documented in `native/mimir/SEQUENCES.md`.
Prefix boundaries/next positions are sequence-local. Complete-prefix batches
and interleaved causal-answer batches reuse existing masks and KV streams;
separate prefix/answer phases avoid a new attention kernel. Unified KV supports
sparse IDs and requested shared capacity; separate KV enforces per-sequence
capacity. Invalid admission is atomic, including wildcard removal. Execution
abort/failure clears only participating sequences. Metadata follows actual
backend `seq_keep` behavior (separate streams retain unrelated sequences).

The server now supports multiple active slots, gives pending prefixes a separate
prefill batch, scopes cancellation/error cleanup to affected slots, and releases
idle PrefixLM KV to avoid retaining unusable shared capacity. A new
live-overlap test caught a scheduling stall: an empty generating slot claimed
the prefix batch. Skipping those slots while prefill is pending fixes it. The
stock Q8 Mimir suite uses the actual checkpoint template and tests overlapping
prefill and cancellation while the other sequence completes unchanged.

Core HRM and Llama checks cover both KV layouts, CPU/Metal and flash on/off.
Direct tests pass 1,652 CPU/Metal and 826 CPU UBSan checks; release and UBSan
integration suites pass 7/7 each. Independent full-forward HF evidence now
includes 27 steps; CPU/CPU UBSan/unfused Metal pass all, and fused Metal retains
only the previously measured causal-control miss. Current report and hashes: `native/mimir/sequence-results.json`.
Historical reports and patch files describe earlier snapshots; **packaging and
review remain deferred until Linux release/ASan/UBSan and the bounded performance
control**, with a reminder to the user at that boundary.

## Ownership and supported contract (historical initial scope)

The engine owns complete-prefix validation, phase selection, synchronization,
abort/error cleanup, and cache restrictions. A complete-prefix call validates
before replacing old KV, including on a new turn. Ordinary decode then accepts
contiguous causal answer chunks. Each full prefix fits one physical batch;
answer chunks may span physical batches. PrefixLM enforces requested context
capacity even when memory allocation rounds up; its usable per-sequence
capacity getter reports that limit. App wrappers no longer toggle attention.

The initial scope is token input, one sequence (ID 0), a full-attention decoder,
and contiguous positions. Invalid batches preserve the current request.
Execution failure or abort clears it completely. A fresh complete prefix is
required afterward. Public memory clear/full removal invalidate prefix state;
partial removal fails; copy/keep/shift/divide log an error without mutation.
State save/restore fail before reading/writing state. Unsupported encoder,
recurrent/hybrid, diffusion, SWA, multi-position, multi-sequence, embeddings and
adapter configurations or entry points reject explicitly.

The common prompt helper requires full-prefix input; warmup uses the same API.
The server, also used by the stock CLI, disables prompt reuse, RAM caching,
checkpoints and context shifting with a startup message. Explicit incompatible
request options, shared-prefix children, state operations, speculation,
multimodal input and adapters fail. Requests can queue with `--parallel 1`.
The scheduler submits the prefix separately from answer decoding and never
halves it for allocation retries. Cancellation clears the slot before reuse.

## Patches and historical comparison

**Superseded final architecture, 2026-09-17:** the parent project's phase-owning
native session was a validated prototype. Its generic correctness rules now
live in the engine. The wrapper retains embedding ownership, application
budgets, completed message history, and presentation/cancellation policy.

`native/mimir/patches/prefixlm-engine.patch` replaces the earlier small
replacement patch for the active integration. Apply it to the pinned base,
then the independent graph-size and text-codec patches. Do not apply both
PrefixLM patches. The three-patch stack reproduces every modified engine file
when applied to a fresh base archive.

The original proposal, adapted proposal, library-only replacement and their
[comparison results](llama-cpp-prefixlm-comparison.md) remain preserved and
unchanged. The ggml UB fix is still separate. No commit, push, PR or external
submission has been performed.

## Validation and findings

The patch extends existing `test-llama-archs.cpp` and registers two CTest cases
for HRM-Text and Llama. Local CPU/Metal fused and unfused tests cover default
metadata and explicit modes, future-prefix visibility, answer causality,
answer chunks across physical batches, capacity, invalid memory operations,
state rejection, single-token prefixes, and prefix/answer abort recovery.
Independent HF references remain in the parent harness.

The stock server suite compares both raw token completions and rendered chat
against HF, verifies complete prompt processing, serial queue isolation,
stream disconnect, rejected options/capacity/state operations and recovery.
The stock CLI is also exercised with its own server. Its server template
endpoint intentionally omits BOS and tokenization adds it; testing the combined
path gives the same tokens as HF.

Tests found and fixed two integration errors: requested capacity must not be
replaced by padded allocation capacity, and oversized-prompt errors sent before
slot assignment need explicit context/prompt counts rather than the task-only
error overload. Also, speculative HTTP options are disabled in the base schema
and silently ignored there; PrefixLM now rejects such options explicitly.

Local release and UBSan suites are recorded separately. Local ASan still hangs
before main even for an empty executable; remote Linux CI has not run. The CI
workflow applies the engine patch and exercises its direct tests in addition
to session and vocabulary-only tokenizer parity. This is a bounded engine
integration, not qualification for arbitrary architectures, GPU backends,
quantized weights, parallel scheduling or persistent prefix-state formats.

Verified final local results: 508 direct engine checks across HRM-Text/Llama
and CPU/Metal, 23 session-matrix runs with 3243 checks including three real
4096-context stress runs, 23 stock-server checks each on CPU and Metal, and
24 terminal-client end-to-end scenarios. UBSan passes seven CTest suites,
254 direct engine checks, eight session runs with 1128 checks, and 724 text
parity cases. The stock build's two registered PrefixLM CTests also pass.
The independent patch-application check reproduces all 23 modified/new engine
files from the pinned base. These counts are correctness checks, not model
quality or stable throughput measurements.

## PR-readiness assessment (2026-09-17)

The implementation is a bounded private-fork integration, not yet a complete
upstream submission candidate. Source inspection found unadapted direct
`llama_decode` calls in llama-bench, perplexity, imatrix and batched-bench.
Since automatic mode selection now requires an explicit prefix call for
PrefixLM models, those tools need deliberate semantics or an early actionable
rejection. In particular, ordinary perplexity/imatrix evaluation must not make
all scored tokens a bidirectional prefix, which would leak future tokens.

Recommended before submission: audit public API/default-mode compatibility,
move the small independent HF golden checks and key server regressions into
reproducible upstream test infrastructure, run Linux sanitizer/CI checks and
causal performance/quality controls, qualify a conventional quantized weight
format, and separate the unrelated ggml and tokenizer/template fixes. Review
the context-wide sequence-0 state design with maintainers; it should have a
clear path to sequence-local state without forcing another API redesign.

These are engineering recommendations, not known maintainer acceptance
conditions. A documented single-sequence first version can be proposed;
parallel execution, split bidirectional prefill, persistent state/cache reuse,
speculation, adapters, SWA and multimodal support need not all be implemented
before an initial PR. Full-prefix physical-batch admission is a correctness
constraint until a separate chunked algorithm is designed. The upstream
contributing guide requires an issue first, justification of new public APIs,
regression/performance checks and separate changes for unrelated fixes; it
explicitly permits focusing on CPU in the initial feature PR. Its human
review and AI-disclosure requirements also apply when moving beyond the
private fork.


## PR preparation audit, 2026-09-17

The public API has two pre-existing inference functions (`llama_encode`,
`llama_decode`) and one proposed addition (`llama_decode_prefix`). The new
prefix call declares the boundary explicitly; ordinary decode cannot infer it
safely from batch length or position. The caller inventory is now in the
engine document, with the design/restriction ranking in `native/mimir/REVIEW.md`.

**Superseded scope statement:** independent tiny HF reference generation no
longer depends on the parent comparison harness. The patch now contains
`scripts/prefix-lm-reference.py`, using the normal HRM converter with a
vocabulary-free fixture, and `test-llama-archs --prefix-reference` consumes
its full-forward logits. Local CPU, Metal fused attention and CPU UBSan pass
14 reference steps. Parent CI invokes it; remote CI is still unverified.

Stock bench now submits complete prefixes, seeds generation-only tests before
timing, rejects cached-depth tests and records attention mode. Perplexity and
imatrix explicitly select causal attention for unlabelled text and reject
non-causal/PrefixLM overrides. Simple/simple-chat have explicit prefix phases;
simple-chat still cannot format Mimir's Jinja template, and its existing early
return triggers a Metal cleanup assertion. This separate example problem is
not treated as successful Mimir chat qualification.

Sequence ownership is still context-global and restricted to sequence 0.
Moving prefix boundary/continuation state to per-sequence memory is the generic
future design; loosening ID validation alone is incorrect. Adapter restrictions
and safe causal-answer suffix removal are less intrinsic than complete-prefix
batching, prefix cache invalidation or unsupported attention architectures.

Precision provenance and measurements live in `native/mimir/review-results.json`
and `logs/mimir-review`. Fresh BF16, Q8_0 and Q4_K_M exports and a converted
FP8-weight checkpoint have finite logits and match 30/30 teacher-forced top
choices on the small reference set. They are not broad quality qualification.
The strict 0.03 FP32 logit threshold is retained: full Metal BF16 reaches 0.0347,
Q8_0 0.0817, Q4_K_M 0.8180, and Liodon FP8-to-Q8 0.3510. BF16 CPU and fused
Metal pass a 10-row subset. BF16/Q8 chunk-single differences are below 7e-6;
Q4_K_M reaches 0.02141, consistent with backend shape-dependent arithmetic but
still requiring broader precision-specific qualification.

Hugging Face format inspection found `noctrex/DFM-Mimir` GGUF BF16/F16/Q8_0,
`schneiderkamplab/DFM-Mimir-FP8` and `liodon-ai/DFM-Mimir-FP8` per-channel FP8
compressed-tensors, and `schneiderkamplab/DFM-Mimir-AWQ-FP4` grouped 4-bit integer
compressed-tensors. `schneiderkamplab/DFM-Mimir-FP4-MLX` is also affine integer
quantization, not floating FP4; direct converter invocation rejects its packed
bias/scale tensors. FP8-to-Q8 conversion does not preserve dynamic FP8
activation arithmetic. Keep format-import work separate from PrefixLM.

The causal baseline and patched builds both report PPL 1.0764 +/- 0.03067 on
the same short repeated-text control. This verifies a bounded regression case,
not actual model quality. Existing Llama/HRM causal backend/roundtrip checks and
seven parent release tests pass. Source changes remain uncommitted, historical
patch comparisons remain untouched, and the three-patch stack reproduces all
29 modified/new engine files on a fresh pinned archive.

The lab FP8 checkpoint revision `5f9640bfa7aabc5dea278998134b8e2d45f0467d`
also converts/runs and matches 30/30 top choices. Lab AWQ-4 revision
`9c189939dae024cf054a41b5944a0a3845e6795b` converts through the existing
compressed-tensors importer to dense F16 and matches 28/30 choices (maximum
logit error 1.31973). Dense conversion forfeits the original 4-bit footprint;
these results do not certify that checkpoint's language quality.

Isolated alternating baseline/patched throughput repeats remain too variable
for a performance gate (the same patched binary ranged 54-174 tokens/s on
32-token causal prefill). Numerical regression passes must not be summarized
as proof of performance parity; retain raw samples and repeat on a controlled
benchmark host. Seven release and seven CPU UBSan CTests pass on the updated
builds. The local OKF check still reports only the two pre-existing benchmark
page/index errors.


## Required Mimir chat protocol, 2026-09-17

The user confirms Mimir was pretrained with its chat template, never without.
All chat experiments must use the checkpoint's exact template and matching
tokenizer, including its generation header and special tokens. See the
[chat protocol](mimir-native-text-chat.md#required-chat-experiment-protocol).
**Superseded interpretation:** the raw `Hello` simple-example execution is not
valid Mimir chat evidence. Untemplated numerical/perplexity controls are not
chat-quality evidence either. A client that cannot render Mimir's template
must be fixed or replaced; no substitute-template fallback is allowed.


## Safe cache follow-up, 2026-09-17

**Superseded restriction:** blanket partial-removal and keep/self-copy bans
are narrowed. Causal answer suffixes may be removed, sequence 0 retained, and
sequence 0 copied to itself. Empty ranges are no-ops; finite ranges covering
the whole request clear phase state. Prefix edits, answer holes and foreign
sequence operations still reject without mutation. Continuation position is
updated only after successful KV removal. Existing memory APIs and cache
implementation are reused; no new public API or attention kernel is added.

Architecture tests now cover rollback/replay on CPU/Metal, fused/unfused
attention, and finite/open/full/empty/wildcard ranges. The independent HF
oracle adds full-forward rollback references. Native chat tests now assert
Mimir's exact template token IDs before generating answers, including the
second turn. Failures are retained in JSON reports.

**Correction to the preceding reference-pass claim:** the previous final
Metal report already failed its causal-control answer row at 0.0001055896
maximum absolute error (threshold 0.0001). The fixture weights, HF references
and error are unchanged. The previous prose overstated success; the strict
failure is retained rather than loosening the tolerance.

See `native/mimir/followup-results.json` for current results/provenance and
`logs/mimir-followup/` for detailed evidence. Sequence-local state, adapters,
parallel scheduling and Linux ASan remain unresolved.

Verified follow-up: 724 direct CPU/Metal checks, 362 direct CPU UBSan checks,
seven release and seven UBSan CTests, and causal Llama/HRM backend/roundtrip
regressions pass. All 18 independent-reference steps pass on CPU, CPU UBSan
and unfused Metal. Fused Metal passes all four rollback steps but retains the
one pre-existing causal-control tolerance failure (17/18 overall). Six
BF16/Q8_0/Q4_K_M chat runs, each fused/unfused, pass 72 checks including exact
Mimir-template token parity; the stock Q8 server passes 23 checks. The updated
three-patch stack reproduces all 29 modified/new engine files. The two
pre-existing unrelated OKF benchmark-page errors remain.


## Production PR priorities, 2026-09-17

The user considers the small fused-Metal threshold exceedance unproblematic.
For this unchanged causal-control case, treat it as numerical test calibration,
not evidence of a PrefixLM correctness defect. This does not waive wider
quantization-quality checks. Before using it as a regression gate, document a
backend/precision-aware absolute/relative tolerance supported by baseline
measurements; do not special-case the failing row or remove the reference.

This prioritization supersedes any implication that every unsupported feature
listed above must be implemented before the first PR. Production readiness
means a correct, tested, explicit support contract; feature completeness is a
separate target. The following is the recommended plan, not a claim of upstream
approval:

1. Settle the public API/default-mode contract and sequence ownership. Justify
   explicit prefix admission and preserve ordinary causal/bidirectional paths.
   Prefer prefix state following existing sequence machinery; one active
   sequence can remain the initial scheduling limit. Avoid speculative new
   abstractions or implementing a parallel scheduler merely to remove a guard.
2. Finish caller and failure-path compatibility. Main tools must either obey
   the PrefixLM contract or reject unsupported requests early and clearly.
   Audit clear/remove/keep/copy, abort/retry, stale logits after rollback,
   adapter changes and state APIs against the selected contract. Preserve
   native Mimir templates for every chat experiment.
3. Run standalone Linux x86 CPU release and ASan/UBSan plus the existing
   Apple CPU/Metal suite. Make essential numerical and server regressions
   reproducible from the llama.cpp checkout and integrate lightweight tests
   with its own CI. Parent-project CI configuration is not execution evidence.
4. Broaden templated conditional evaluation: Danish/English, multi-turn and
   long/near-limit prefixes; HF full-forward parity, answer-only likelihood
   and BF16/Q8_0/Q4_K_M drift. Separate runtime correctness from quantizer
   quality. Current 30-row/easy-answer checks are useful but too narrow to
   support broad quality claims.
5. Obtain stable performance/memory evidence. Use controlled repeated runs
   for prefix prefill, answer throughput and peak memory, with unchanged
   causal/bidirectional controls. Test realistic prefix lengths and clarify
   the physical-batch capacity limit. Existing noisy timings are inconclusive.
6. Prepare a minimal reviewed patch against current upstream, with independent
   ggml/tokenizer fixes submitted separately or declared as dependencies.
   Document supported modes, caller migration and reproducible commands.
   Discuss API/scope upstream early; human review and maintainer agreement
   remain necessary before a ready-for-review submission.

Fixed adapters are a useful next compatibility improvement, but an explicit
unsupported contract can defer them. Full parallel scheduling, persistence,
prefix-cache reuse, speculation, context shifting, split-prefix prefill,
multimodal and additional backend kernels are not automatic first-PR blockers.
CPU-first scope is consistent with upstream contribution guidance. CUDA or
other backend claims require corresponding tests; do not imply coverage.

Work order: API/state design and upstream scope discussion first; Linux
sanitizers/CI can run alongside that work; complete caller fixes next, then
broaden evaluation and stabilize benchmarks, and finally rebase/trim/review.


## Qualification order agreed 2026-09-17

The user deferred Linux execution, with an explicit reminder **before packaging
and review**, rather than a calendar reminder. Do not start rebasing, repackaging
or PR review until reminding the user and completing Linux CPU release and
ASan/UBSan tests. This supersedes the earlier work-order recommendation above.
The present work is a bounded four-case Mimir-template evaluation plus repeated
prefill/decode and process-memory measurements, documented in
`native/mimir/QUALIFICATION.md`. Parallel scheduling is still deferred: current
prefix boundaries and failure cleanup belong to the context, so concurrent
sequences require sequence-specific ownership and interleaving tests.


Bounded qualification completed on 2026-09-17: four checkpoint-template cases
(Danish Unicode, English instruction, retained multi-turn context, 480-token
prefix at configured physical capacity), 40 teacher-forced answer targets.
F32/BF16/Q8/Q4 × Metal flash on/off × single/chunk answers compare 704 logit
rows to independent HF full-forward references. F32 passes 104/104 strict
steps. BF16/Q8 preserve 44/44 top choices per mode; Q4 preserves 43/44. The old
0.03 absolute threshold is exceeded by BF16 and quantized models; failures are
retained, not relabelled as strict passes. This is bounded numerical/conditional
likelihood evidence, not general model-quality evaluation.

Stock-server measurements use the actual template, 35/160/480-token prefixes,
16 generated tokens, one warmup plus three measured rounds per format/length.
All nine template checks and all 36 complete-prefix/no-cache requests succeed;
repeated continuations are stable. Peak process RSS is 3.987/2.451/1.767 GiB
for BF16/Q8/Q4, not total unified-memory usage. Timing varies several-fold.
Tiny CPU baseline/patched causal decode measures +11.6% aggregate latency, but
unchanged baseline medians drift 5.80→7.85 ms; no causal attribution is justified.
Repeat the bounded performance control on Linux along with release/ASan/UBSan
before claiming no regression. Report: `native/mimir/QUALIFICATION.md`; harness:
`native/mimir/tests/qualification.py`, `qualification_report.py`; raw evidence:
`logs/mimir-qualification/`. No core code, patch packaging or PR review changed.

## Multi-sequence scope clarification, 2026-09-17

Inspection of the pinned checkout confirms that multiple sequence IDs per batch
and `n_seq_max` are standard library abstractions. Causal decoding supports
parallel sequences; non-causal encoding accepts multiple sequences and extracts
pooled outputs by sequence ID, while requiring the complete encoder batch to
fit `n_ubatch`. This means batched/scheduled sequences, not simultaneous
unsynchronized API calls on one context. Encoder-decoder scheduling has further
model/caller constraints and should not be described as universally identical
to decoder-only continuous batching.

The earlier rationale for keeping one PrefixLM sequence explains the current
implementation shortcut (context-wide prefix state and cleanup), not an
architectural necessity. Recommendation refined: for generic first-class
PrefixLM support, prioritize sequence-local prefix state, admission/reset and
failure isolation using the existing sequence machinery. Supporting multiple
live sequences need not require mixed prefix/answer phases in one compute
batch: separate prefix-prefill and causal-answer batches are a plausible
minimal design, still requiring implementation and interleaving tests. This
clarification does not claim that multi-sequence PrefixLM is implemented.

## Existing-feature parity scope audit, 2026-09-18

The user requested resolving API/scope before Linux qualification. In the pinned
checkout, causal decoder state APIs serialize memory globally or per sequence;
`llama_memory_seq_cp` supports cache copying/sharing (cross-stream copies require
full buffers). Compatible fixed LoRA adapters use the normal graph helpers.
BERT-style encoder graphs also use LoRA-aware QKV/FFN helpers, but their
no-cache execution has no resumable autoregressive KV session to fork. Current
context serialization writes architecture plus memory when present, not a
general saved encoder-output/embedding object. Thus an unqualified claim that
all three features exist identically for encoder-only and decoder-only models
would be incorrect.

Recommendation superseding blanket deferral as the default PR scope: include
fixed compatible adapters, full-sequence copy/fork, and context/per-sequence
persistence in generic PrefixLM support. The current guards reflect unfinished
integration, not inherent PrefixLM incompatibility. Fixed adapters should remain
constant while dependent KV is live. Full-sequence forks must carry complete
prefix KV plus boundary/next-position metadata and preserve sibling isolation.
Persistence must serialize that metadata, validate it with restored KV and
capacity, handle destination ID remapping, and reject incompatible/malformed
state without exposing usable inconsistent state. Its format/recovery work is
larger than the other two, but is a reason to sequence implementation carefully,
not automatically omit it. Suggested order: fixed adapters, full-sequence
forking, then persistence. Arbitrary partial-prefix copies and changing adapters
while retaining stale KV remain invalid. No implementation of these three
features was performed in this scope-audit turn.
