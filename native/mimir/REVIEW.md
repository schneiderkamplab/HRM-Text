# PrefixLM PR preparation

Historical audit snapshot. The working-tree sequence/state/adapter scope below
is superseded by [SEQUENCES.md](SEQUENCES.md) and [STATE.md](STATE.md).
Linux qualification remains ahead of packaging and human review.

The patch remains a private, uncommitted proposal against llama.cpp
`c9a5eeeb34ab8f794ea7510ca52d25da13728a5b`. This review extends the earlier
engine validation; `engine-results.json` describes the earlier source snapshot.
Current audit and measurements are in `review-results.json` and
`logs/mimir-review/`.

## API and tools

There are two existing public inference entry points: `llama_encode` and
`llama_decode`. The patch adds `llama_decode_prefix`. The commented-out
`llama_decode_with_sampler` proposal is not an exported function.

The additional entry point declares a full new prefix explicitly. Ordinary
decode continues an existing answer. Inferring the phase from token count or
position would make one-token prefixes, resets and future state restoration
ambiguous. A single decoder entry point with an explicit phase field is a
possible upstream API alternative; the semantics and admission checks would
remain necessary. This is an API discussion to settle before freezing a PR.

The engine document contains the caller audit. The new adaptations cover
llama-bench, causal perplexity/calibration and simple examples, in addition to
the existing common/server/CLI changes. Legacy examples using speculation,
parallel decoding, cache editing or implicit boundaries remain unsupported.
The core rejects incompatible calls; this is not a completed UX audit of every
example. Simple-chat's built-in formatter cannot render Mimir's full Jinja
chat template, so its Mimir end-to-end attempt failed before decoding. The
existing early-return resource cleanup also hit a Metal teardown assertion;
that separate example issue is not changed by this patch.

## Chat protocol correction, 2026-09-17

The user confirms Mimir was pretrained with its own chat template, never
without it. All Mimir chat experiments must use that exact template and the
matching tokenizer; no raw-text or substitute-template fallback is permitted.

**Superseded interpretation:** the successful `llama-simple` raw `Hello` run
is only a historical decode-execution observation and is invalid as Mimir
chat evidence. The untemplated perplexity/calibration controls likewise say
nothing about Mimir chat quality. Existing chat/HF parity tests that render
Mimir's actual template remain applicable. A client with an unsupported
formatter must be fixed or replaced before further chat experiments.

## Sequence locality

The attention rule must first require the same sequence, then allow a key when
`key_position <= query_position`, or when both positions are inside that
sequence's prefix. Sequence A's boundary must never influence sequence B.

The prototype stores the prefix boundary and next answer position on the
context's memory object. This is correct only with its enforced single-sequence
contract. It clears all memory for a valid new prefix and after execution
failure, which is safe only while no other request shares that context.

Before parallel support, put this small state alongside per-sequence memory
state and define removal, copy, keep, save/restore and failure semantics for it.
The public prefix batch already carries sequence IDs, so this need not require
another public decode function. Support for arbitrary IDs, multiple active
sequences, mixed prefix/answer batches and continuous scheduling are separate
steps. The current `n_seq_max = 1` convention uses ID 0; changing the ID check
alone would not add correct sequence-local support.

A full prefix in one physical batch is an algorithmic boundary of the current
implementation: later prefix tokens affect earlier prefix representations.
Successive causal chunks cannot produce the same KV state. Lifting it needs a
correct layer-wise/tiled bidirectional prefill algorithm, not a relaxed guard.

## Restriction priorities

From least defensible as permanent restrictions to most reasonable deferrals:

1. Unadapted ordinary callers and implicit phase assumptions. Fix the common
   paths and give unsupported tools a clear contract before a ready-for-review PR.
2. Blanket bans on fixed adapters and harmless memory operations. Adapters
   fixed before prefix evaluation, keeping the sole active sequence, and
   deleting only a causal answer suffix have no inherent PrefixLM conflict.
   They need cache-invalidation rules and tests, rather than permanent bans.
3. Context-global sequence state and ID-0-only semantics. A reasonable bounded
   prototype; sequence-local ownership is the right generic design. Full
   parallel scheduling may follow later.
4. No state persistence or prompt-cache reuse. Defensible initially because
   boundaries/phase must be serialized and bidirectional prefix KV cannot be
   reused by blindly appending to a changed prefix.
5. No speculative decoding or context shifting. These require correct answer
   rollback and prefix invalidation. Defer until the ordinary path is qualified.
6. Complete-prefix single-batch requirement. Keep until a correct alternative
   prefill algorithm exists; document its memory/length cost.
7. Multimodal, SWA, recurrent/hybrid and special positional architectures. Keep
   outside the initial full-attention decoder contract.

## Precision interpretation

Q8_0 is not FP8, and Q4_K_M is not floating-point FP4. The public
`noctrex/DFM-Mimir` repository contains BF16, F16 and Q8_0 GGUFs. Fresh BF16,
Q8_0 and Q4_K_M exports here use the pinned original BF16 source and current
converter/tokenizer fixes, avoiding assumptions about older third-party exports.

The MLX FP4-labelled checkpoint is 4-bit affine integer quantization, group
size 64, with packed uint32 weights and scales/biases. Direct conversion fails
on those tensors. The AWQ FP4-labelled checkpoint also describes integer
4-bit grouped weights, in compressed-tensors format. Neither is NVFP4/MXFP4. The lab AWQ checkpoint converts successfully to dense
F16 through the existing importer; retaining a 4-bit footprint would require
subsequent GGUF quantization. The tested dense conversion matches 28/30
reference top tokens. Both lab and Liodon FP8-to-Q8 conversions match 30/30.
The FP8 checkpoints use per-channel FP8 weights and dynamic per-token activation
quantization. Conversion through `--fp8-as-q8` dequantizes those weights and
requantizes selected tensors to Q8_0; remaining matrices use the requested
BF16 output. It does not reproduce the original FP8 activation quantization.

Precision comparisons retain the strict 0.03 FP32-reference threshold. Report
quantized drift and same-model chunk/single consistency separately. Matching
30 teacher-forced top tokens is a smoke check, not evidence of unchanged
language quality. BF16 backend-specific drift also requires a justified
precision-specific tolerance before adding a stable regression gate.

## Remaining PR qualification

The independent tiny Transformers oracle now belongs to the patch and uses
the stock converter and existing architecture-test executable. The parent CI
runs it, including the sanitizer job; remote CI has not run locally.

Local CPU UBSan and CPU/Metal checks do not replace Linux ASan, other backend
qualification, a representative conditional PrefixLM quality evaluation, or
review of the per-sequence API/state design. The ggml UB fix and tokenizer/
Unicode changes remain separate patches. Do not interpret short synthetic
perplexity or throughput comparisons as broad production qualification.


Representative precision results (30 teacher-forced output rows on Metal,
FP32 KV, unfused attention):

| Weight path | Maximum absolute logit error vs HF FP32 | Top-token agreement |
|---|---:|---:|
| Original BF16 -> GGUF BF16 | 0.03471 | 30/30 |
| Original BF16 -> GGUF Q8_0 | 0.08169 | 30/30 |
| Original BF16 -> GGUF Q4_K_M | 0.81804 | 30/30 |
| Lab FP8 -> GGUF Q8_0/BF16 | 0.35101 | 30/30 |
| Lab AWQ integer-4 -> dense F16 | 1.31973 | 28/30 |

All rows are finite. Strict FP32-reference failures remain visible in the raw
reports. On the 10-row CPU/fused subset, BF16 maximum errors are 0.02643 and
0.01398 respectively. These are different execution paths, not evidence that
0.03 is a universal BF16 tolerance.

The repeated throughput check is inconclusive: the same patched executable
ranged from 54 to 174 tokens/s on 32-token causal prefill across isolated runs.
Keep the raw baseline/patched samples, but do not claim either a speedup or a
resolved performance-regression gate from these measurements. Repeat on a
controlled benchmark host before calling performance qualified.


## Safe cache operations and template-verified chat, 2026-09-17

**Superseded restriction snapshot:** the blanket partial-removal and keep/self-
copy bans described above have been narrowed. The engine now permits deleting
only a causal answer suffix, retaining sequence 0 and copying it to itself.
Full removal accepts finite or open-ended ranges; empty ranges are no-ops.
Prefix edits and answer holes still fail before any mutation. The next answer
position changes only after successful removal. No new cache implementation,
attention kernel or public API is added. Per-sequence ownership, adapters and
parallel scheduling remain separate unresolved work.

The existing engine tests cover rollback/replay logit equality, full-answer
rollback, finite/full/wildcard/empty ranges, and failed-edit preservation on
CPU/Metal with fused/unfused attention. The independent Transformers oracle
now also checks replay against full-forward answer logits.

The native chat harness now checks exact Mimir-template token IDs against HF
before free-running conversation and short-answer probes. It saves failed
reports as well as successful ones. This tests actual templated chat rather
than attributing chat validity to a raw-token execution smoke test.

**Correction to earlier reference summary:** the earlier final Metal report
already contained a failing causal-control answer row (maximum absolute error
0.0001055896 against 0.0001). Its value and fixture weights are unchanged in
this follow-up. Describing that entire suite as passing was incorrect. The
failure remains visible; no threshold was relaxed to make it pass.

Current measurements, patch hashes and remaining limitations are recorded in
`followup-results.json`; detailed logs are under `logs/mimir-followup/`.

Verified follow-up: 724 direct CPU/Metal checks, 362 direct CPU UBSan checks,
7/7 release and 7/7 UBSan CTests. The independent oracle passes 18/18 steps
on CPU, CPU UBSan and unfused Metal; fused Metal passes all rollback steps
but remains 17/18 overall due to the unchanged causal-control threshold.
Six templated BF16/Q8_0/Q4_K_M chat runs pass 72 checks, and the stock Q8
server passes 23 checks. The updated patch stack reproduces all 29 engine files.


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


## Hold point before packaging and review (2026-09-17)

User instruction: remind them to run Linux CPU release and ASan/UBSan tests
**before packaging and review**. This is a workflow prerequisite, not a timed
reminder. Complete and record those results before rebasing/repackaging or PR
review. The bounded Apple evaluation/performance report is `QUALIFICATION.md`.
