# Linux PrefixLM qualification and causal-prefill fix

2026-09-18. Linux CPU/CUDA testing has been executed. The measured ordinary
causal-prefill regression is fixed. This is an evidence report, not a claim that
all strict numerical/sanitizer gates are green or that a PR is ready to submit.

Machine-readable results: [linux-results.json](linux-results.json).
Current implementation identity: [linux-source-manifest.json](linux-source-manifest.json).
Committed samples and diagnostics: [linux-evidence/](linux-evidence/README.md).
Raw local evidence: `logs/linux-prefixlm/`, with fixed-revision reruns in `postfix/`.

## Source and environment

The received parent was `42d2aebc7bf14230eca9bf295a5305b05de13e32`, pinning
llama.cpp `6f60f7472fead8da5289e06c9d79b47dd4763043`. All received implementation
hashes matched [decoder-results.json](decoder-results.json), which remains the
historical Mac manifest. The current gitlink and Linux manifest include two fixes:

- Add the direct `<algorithm>` include required by GCC 15 in `llama-context.cpp`.
- Select ordinary and PrefixLM causal-mask template specializations outside the
  inner mask loop. Ordinary decoding retains the original `p0 > p1` predicate;
  prefix-aware visibility is compiled only into the PrefixLM specialization.

The unchanged feature review drafts plus
[linux-causal-mask-fix.patch](patches/review-drafts/linux-causal-mask-fix.patch)
reproduce the Linux follow-up for combined/main-only builds. Standalone persistence
has no PrefixLM mask and does not take this follow-up patch. Final PR packaging
and submission were not performed.

Prerequisites were installed in the requested existing Conda environment
`hrmtextllamacpp`: Python 3.12.14, exact comparison requirements lock, CMake/Ninja,
CUDA 13.2, Compute Sanitizer and GNU time. PyTorch is 2.14.0; Transformers is pinned
to `ff2421c67f35cc83a0fbabbc2633c96734685918`. `pip check` passes. Exact versions
and model/input hashes are committed in the evidence directory.

Hardware: AMD EPYC 9655, NVIDIA B200, driver 610.57.04. Initial bounded correctness
used explicitly authorized GPU headroom. Performance ran after all eight GPUs
were verified idle. No training process was changed. CPU baseline/candidate
benchmarks both use GCC 13.3; CUDA both use Conda GCC 15.3. Optional server TLS was
disabled for affected Conda builds after mixed OpenSSL headers/libraries caused a
link failure. All HTTP tests use localhost; TLS was not qualified.

## Performance fix and validation

For the tiny 256-token ordinary-causal control, two original GPU ABBA blocks
showed +4.07% and +4.78% prefill latency, against +1.21%/+1.10% baseline drift.
Nsight graph-node traces showed identical 266-kernel launches and nearly identical
GPU spans (642.520 vs 642.615 microseconds). Direct host-mask timing then localized
most of the added 40-45 microseconds to mask construction.

| Direct mask timing, microseconds | Baseline A | Candidate B | Candidate B | Baseline A |
| --- | ---: | ---: | ---: | ---: |
| Before fix | 46.200 | 85.603 | 81.492 | 43.431 |
| After fix | 42.865 | 43.485 | 44.467 | 44.337 |

| Fixed-revision control | Candidate latency change | Baseline drift |
| --- | ---: | ---: |
| CUDA causal prefill | +0.14% | +0.31% |
| CUDA causal decode | -0.31% | +3.60% |
| CUDA bidirectional prefill | -0.03% | +1.30% |
| CPU causal prefill | +0.29% | +0.29% |
| CPU causal decode | +0.37% | -0.43% |
| CPU bidirectional prefill | -0.92% | +1.84% |

The original regression is no longer distinguishable from measured drift; this
is not a universal percentage acceptance threshold. ABBA uses identical model
bytes and flags, 25 samples per invocation, and consistently discards the first
five. CPU affinity is 16-19, four threads, GPU 0, flash off, 256-token batches.
Raw round samples and commands are committed. The tiny-model percentage does
not estimate the impact on arbitrary real models.

## Correctness coverage

| Fixed-revision rerun | Result |
| --- | --- |
| CPU release native integration | 8/8 CTests; 1,128 session-matrix checks; text parity passes |
| CPU ASan/UBSan native integration | Same coverage passes with fatal sanitizer errors enabled |
| Combined/main-only PrefixLM engine | CPU 970 checks per architecture; CPU+CUDA 1,940 per architecture |
| Ordinary HRM/Llama controls | CPU, sanitizer and CUDA pass |
| Combined parser, reasoning and host/backend samplers | CPU, sanitizer and CUDA pass; actual GPU transaction test passes |
| Q8 combined HTTP/restart | CPU and CUDA separate/unified PrefixLM and ordinary-causal modes rerun |
| Q8 ASan/UBSan HTTP/restart | Unified PrefixLM and ordinary-causal modes rerun |
| Main-only HTTP/cache | Both layouts on CPU and CUDA rerun; no sampler snapshot symbols |
| Tiny independent CPU oracle | 31/31 at unchanged maximum absolute tolerance 1e-4 |
| Tiny independent CUDA oracle | 2/31 with flash off; 2/31 with flash on, unchanged from before fix |

All 894 fixed-revision HTTP/restart checks pass. All nine real-model oracle
comparisons have identical error rows before and after the fix. Exact exit
statuses and counts are in `linux-results.json`. The initial complete
HTTP matrix passed 1,775 checks: combined CPU 577, combined CUDA 668, sanitizer
150, main-only 72 per backend, standalone persistence 118 per backend. This
includes BF16/Q8/Q4, fixed zero LoRA/control vectors, fresh-process restore/remap,
OpenAI parser continuation and exact-cache checks. The mask fix reruns affected
Q8 layouts/modes and BF16/Q8/Q4 logit comparisons; standalone persistence code is
unchanged, so its original results are retained rather than relabelled as reruns.

Two initial post-fix HRM engine invocations (main-only CPU and ASan/UBSan)
returned 255 while concurrent lanes shared the hardcoded temporary state filename.
Both isolated-working-directory reruns pass all 970 checks. Original failures
and retry commands/statuses are retained. Run concurrent engine lanes in separate
working directories to avoid this harness collision.

The engine suite covers shared prefix/answer owners and physical capacity,
owner ordering, full-context shared-state restore, atomic duplicate/divergent
owner rejection, complete-prefix copies on both layouts, answer-only copies
with shared history, rejected incomplete/incompatible copies, empty/self no-ops,
and invalidation of unavailable boundary logits. Separate-KV shared input
remains intentionally unsupported. These checks are not replaced by HTTP tests.

## Numerical findings that remain open

Tiny CPU release/sanitizer maximum absolute error is 8.34465e-7, with all 130
row top-token choices matching. CUDA reaches 0.00233555 unfused and 0.00232470
fused, also with 130/130 top-token agreement. Both shared-owner oracle rows fail
the strict threshold. All fixed-revision error rows are retained; no tolerance
was relaxed.

A new causal-only reader, using public APIs common to both revisions, was compiled
against the pristine base and the fixed candidate. For the three causal-control
rows, **baseline and candidate report identical errors** on CPU and both CUDA
flash modes. This establishes that those causal numerical failures predate the
patch. It does not prove every PrefixLM numerical discrepancy has the same cause.
Disabling TF32 and forcing cuBLAS F32 did not eliminate the strict failures.

Real-model BF16/Q8/Q4 comparisons against the HF FP32 reference retain the
existing 0.03 maximum-error threshold. Original maximum errors range from
0.0564-0.1276 for CUDA BF16, 0.2265-0.2709 for CUDA Q8, and 1.5796-1.5998 for CUDA
Q4. Top-token agreement is 88/88 for BF16, 86/88 for Q8, and 83-86/88 for Q4.
CPU maxima are 0.0648/0.2865/1.4065. Per-case RMS, top-token and NLL evidence is
committed. Quantization/precision acceptance requires an explicit decision;
these threshold failures are not silently converted to passes.

## Sanitizer findings

CPU ASan/UBSan passes. CUDA sampler memcheck passes. Default CUDA engine memcheck
returns 99 with 16 CUDA API errors per architecture: `cudaErrorGraphExecUpdateFailure`
from graph update and the subsequent error-clear call. The existing backend
explicitly catches this condition and recreates the graph. No invalid device
memory accesses were reported in these runs.

Separate `GGML_CUDA_DISABLE_GRAPHS=1` diagnostics pass both engine suites and the
sampler with zero errors. The fixed revision repeats both configurations. The
normal graph-enabled nonzero result remains recorded; the diagnostic run does
not replace it. A documented sanitizer policy for this handled API condition is
still needed before claiming an entirely green default lane.

## Capability measurements and remaining work

Before the mask fix, both backends completed BF16/Q8/Q4 separate/unified request
measurements: short, medium, near-limit and concurrent mixed templated prompts,
plus snapshot save/restore, RSS and GPU memory. These are candidate capability
measurements, not comparisons against a nonexistent baseline PrefixLM API, and
are clearly distinguished from the fixed-revision ABBA results.

Ownership measurements at 32/128/256 tokens and 2/4 owners confirm that four
shared owners at 256+1 rows occupy 257 physical KV cells instead of 1,028.
Unified buffer allocation is unchanged; sharing reduces occupancy, not reserved
capacity. Copy timings include deferred-transfer flushing. Separate streams
still copy full buffers. RSS measurements are process high-water values.

The performance fix and this report can be committed. Remaining qualification
work is to diagnose/agree acceptance for strict CUDA numerical differences and
real-model precision drift, and document the graph-update sanitizer handling.
No additional new regression was exposed by the mask specialization. This
report does not claim GitHub CI execution or final upstream review approval.
