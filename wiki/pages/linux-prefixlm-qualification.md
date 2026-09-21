---
type: Operational Record
title: Linux PrefixLM qualification
description: Linux qualification environment, execution evidence, and unresolved acceptance gates.
tags: [runtime, testing, prefixlm, cuda]
status: draft
last_updated: 2026-09-18
confidence: high
---
# Linux PrefixLM qualification

## Human reviewer hand-off (2026-09-18)

`native/mimir/HUMAN-REVIEW-HANDOFF.md` maps the four candidate patches and alternative
standalone persistence patch to their scope, source/history and review priorities.
It distinguishes accepted numerical limitations from pending final sanitizer execution,
intentional support limits and potential upstream cleanup. The candidate guide and
final qualification checklist link to it. No runtime or acceptance policy changed.

## Final qualification preparation (2026-09-18)

Supersedes the unresolved-acceptance and push-status statements in the historical
record below. The Linux results and runtime fix were pushed and received. The user
accepted the existing tiny CUDA and real BF16/Q8/Q4 numerical findings as nonblocking
for this PR scope; the original strict thresholds/results remain intact.
`native/mimir/FINAL-QUALIFICATION.md` records the decision and its limits.

A narrow Compute Sanitizer wrapper accepts only paired graph-update error 910 and
its matching error-clear call when explicitly enabled. Unknown diagnostics, memory
errors, missing summaries/completion and application failures reject. Raw logs and
JSON are retained. Five local policy/runner tests pass, including negative cases;
actual CUDA validation of the new wrapper is pending. Updated CI runs both engine
architectures and the backend sampler, using isolated working directories.

Four release-candidate patches fold the Linux mask/include fix into main PrefixLM
and keep generic persistence separate. `tools/package_patches.py` proves reconstruction
of the qualified Git tree and checks isolated API boundaries, without rewriting
history. The current Mac release and CPU UBSan reruns each pass 8/8 CTests. Linux final checks and
human review remain; runtime source is unchanged from the qualified Linux revision.
Use `native/mimir/release-source-manifest.json` for the updated harness/CI identity.

The 2026-09-18 Linux run follows the repository `linux-testing.md` hand-off.
Evidence and the final report belong in `logs/linux-prefixlm/`.
The received implementation passed all SHA-256 checks in
`native/mimir/decoder-results.json`; parent/submodule identities, status, diffs,
and untracked-file hashes were saved before source edits.

Use the existing Conda environment `/home/ucloud/miniforge3/envs/hrmtextllamacpp`
for prerequisites, as explicitly requested by the user. This replaces the guide's
new-venv setup for this run. The environment originally had Python 3.13.15;
Python 3.12.14, CMake, Ninja and pip were installed through Conda to match the
guide. Preserve the exact `scripts/prefixlm_comparison/requirements.lock` pins.

All eight B200 GPUs were running training at the initial inspection. The user
explicitly authorized bounded tests using remaining GPU headroom while leaving
training processes untouched. GPU 1 initially had approximately 16 GiB free;
restrict test visibility to that GPU and recheck headroom before real-model runs.
Shared-machine timings cannot establish controlled performance acceptance.

Qualification is in progress; source identity alone is not a Linux test pass.

## First verified results and portability fixes

CPU release passed eight native CTests, the eight-run session matrix, text parity,
970 PrefixLM assertions per architecture, parser/reasoning tests, explicit host
and graph-bound sampler persistence, and the 31-step independent oracle at 1e-4.
The original CPU build used Ubuntu GCC 13.3.0. CUDA provisioning also installed
Conda GCC 15.3.0; later builds record their actual compiler in CMakeCache.txt.

GCC 15 exposed a missing `<algorithm>` include in `llama.cpp/src/llama-context.cpp`
for `std::all_of` and `std::sort`. Added the direct include and reran CPU engine
checks; preserve the received manifest and use the new
`logs/linux-prefixlm/qualified-source-manifest.json` for this qualification revision.
The same include was applied to the isolated main-only tree.

Conda GCC also exposed mixed Conda OpenSSL headers/system OpenSSL libraries,
with undefined `X509_STORE_get1_objects` at server link. Configure affected
server builds with `-DLLAMA_OPENSSL=OFF`: tests use localhost HTTP, not TLS.
This is a test-build configuration change, not TLS qualification.

## Idle GPU authorization and CUDA findings

Superseded (2026-09-18, later in the same session): the initial shared-training
constraint no longer applies. The user reported all GPUs free and authorized
performance tests; `nvidia-smi` confirmed all eight GPUs at 0 MiB / 0% utilization.
GPU 0 is reserved within this run for controlled performance; correctness uses
other devices. External future occupancy must still be checked.

Combined CUDA engine and host/GPU sampler checks pass with actual B200 offload.
The tiny default CUDA oracle fails 29/31 steps with flash both off and on;
max absolute errors are 0.00233555 and 0.00232470 respectively, with all 130
row top-token choices matching. Preserve the strict 1e-4 threshold and failures.
Compute Sanitizer's sampler test passes. Both engine tests return 99 due to
reported CUDA graph update API errors; investigate separately from kernel memory
errors and do not relabel the default lane as a pass.

## Further measured evidence

Combined real-model HTTP matrices pass 577 CPU and 668 CUDA checks, including
Q8 separate/unified PrefixLM and ordinary-causal restarts, BF16/Q4 restarts,
and fixed zero LoRA/control-vector integration. Main-only HTTP/cache passes
72 checks on each backend; both main-only libraries have no exported
`llama_sampler_state_*` symbols. CPU standalone persistence passes 118 checks.

Default CUDA memcheck reports `cudaErrorGraphExecUpdateFailure` from
`cudaGraphExecUpdate` and the subsequent error-clear call. The existing CUDA
backend explicitly handles this by destroying/recreating the graph. Separate
`GGML_CUDA_DISABLE_GRAPHS=1` diagnostic runs pass sampler and both engine suites
with zero Compute Sanitizer errors; default-lane failures remain preserved.
Disabling TF32 and forcing cuBLAS F32 did not resolve strict tiny-oracle failures.

CPU ABBA control timings show candidate changes of +0.35% causal prefill,
+1.29% causal decode, and +0.23% bidirectional prefill. Baseline drift is
+2.11%, +1.68%, and -1.52%, respectively; this is inconclusive for small
regressions. Raw 25-sample invocations discard the first five consistently.

The standalone ownership benchmark observes 257 physical cells for four
shared owners at prefix length 256 plus one answer, versus 1028 independent
cells. Allocated KV capacity is unchanged between shared/independent unified
runs; logical sharing reduces occupancy, not the preallocated buffer.
Copy measurements flush deferred transfers; separate-stream copies still
transfer full buffers. See `logs/linux-prefixlm/ownership-summary.json`.

## Completed feature isolation and performance observations

Both isolated main-only backends pass their engine invariants, ordinary controls,
and 72 HTTP/cache checks each; the CUDA tiny oracle retains the combined failure.
Standalone persistence passes parser/reasoning, host and graph-bound samplers,
ordinary controls, and 118 HTTP/restart checks per backend. Combined sanitizer
HTTP passes all 150 unified PrefixLM and ordinary-causal checks.

CUDA ABBA causal prefill is +4.07% and +4.78% slower in two complete blocks,
with baseline drift +1.21% and +1.10%. Causal decode is approximately unchanged;
bidirectional prefill is -0.37% and -1.28%. Preserve the repeated prefill slowdown
as an unresolved finding rather than applying an invented acceptance threshold.

Standalone Nsight Systems and CLI Conda installs failed dependency resolution
against pinned CUDA 13.2 (available packages require CUDA 12.9 or 13.4).
The installed toolkit already includes a compatible Nsight Systems 2026.1.1 CLI:
`$CONDA_PREFIX/nsight-compute-2026.1.1/host/target-linux-x64/nsys`.
Use it without upgrading the qualification environment's CUDA toolkit.

Nsight graph-node traces show identical 266-kernel launch composition and nearly
identical median steady GPU spans (642.520 us baseline, 642.615 us candidate).
Median graph-launch API times are 15.518/15.789 us. The uninstrumented wall-time
regression is therefore still unexplained; host-side mask work is a possible
investigation target, not an established cause. Preserve both ABBA blocks and
`profile-nodes-*.nsys-rep`/SQLite/CSV evidence. No performance fix was made.

## Direct causal-mask timing follow-up

Superseded in part (2026-09-18, later diagnostic): the preceding profile left
host attribution unresolved. An LD_PRELOAD wrapper now directly times
`llama_kv_cache::set_input_kq_mask` without changing either tested library.
ABBA median mask times are 46.200 / 85.603 / 81.492 / 43.431 us
(baseline/candidate/candidate/baseline; 20 retained samples per invocation).
The approximately 39 us increase accounts for most of the 40-45 us wall-time
prefill regression and localizes the cost to host causal-mask construction.

The main patch added a PrefixLM condition inside the `p0 > p1` future-token
check at `llama.cpp/src/llama-kv-cache.cpp:1723`. Ordinary causal contexts pass
`prefixes == nullptr`, so they do not execute prefix-map lookups, but the new
condition changes the hot-loop code. A separate ordinary-causal specialization
selected outside the loop is a plausible remedy; it has not been implemented or
benchmarked. Other standard-path additions are attention-mode decode dispatch,
batch-size validation, and the whole-sequence splitter flag. PrefixLM retained
boundary logits and owner-state validation are bypassed in ordinary decoding.
Evidence: `mask-profile-summary.json`, `mask-*.csv`, and `profile_mask.cpp` under
`logs/linux-prefixlm/`.

## Initial qualification complete (historical)

All requested available CPU/CUDA correctness lanes, isolated feature builds,
real-model HTTP/restart matrices, sanitizer lanes, and bounded performance
measurements were executed. Both CPU and CUDA now have six completed real-model
request-performance configurations (BF16/Q8/Q4, separate/unified), each with
short/medium/near-limit/mixed requests, snapshot save/restore, and resource data.
CPU release and ASan/UBSan native matrices each pass 1,128 checks in eight runs.
The OKF validator reports zero errors/warnings on this checkout.

The final report is `logs/linux-prefixlm/REPORT.md`; machine-readable aggregate
results are `logs/linux-prefixlm/results.json`. Qualification is not a blanket
pass: strict CUDA logits, real-model precision thresholds, default memcheck API
errors, and the causal-mask performance regression remain explicit open findings.
The only product-source edit is the required `<algorithm>` include. No numerical
threshold, feature implementation, training process, commit, or published PR was
changed as part of this testing run.

## Causal-mask fix and committed Linux report

Superseded (2026-09-18, fixed-revision follow-up): the earlier statements that
no performance fix was implemented and that the mask regression remained open.
The initial results above remain the historical pre-fix record.

The fixed implementation selects a prefix-aware template specialization outside
the mask loop and restores the ordinary causal `p0 > p1` predicate. It also adds
`<algorithm>` explicitly for GCC 15. Direct mask ABBA medians are now
42.865 / 43.485 / 44.467 / 44.337 us. CUDA causal-prefill latency is +0.14%
against +0.31% baseline drift; CPU is +0.29% against +0.29% drift.

Fixed combined/main-only CPU/CUDA and sanitizer engine/native lanes were rerun,
as were 894 passing HTTP/restart checks. All nine BF16/Q8/Q4 oracle comparisons
have exactly the same error rows as before the fix. A causal-only diagnostic
compiled against the pristine base and fixed candidate finds identical errors
on CPU and both CUDA flash modes, establishing that the tested causal numerical
failures predate PrefixLM. This does not establish the cause of every PrefixLM
numerical difference. Default memcheck still reports handled graph-update API
errors; graph-disabled diagnostic lanes pass with zero errors.

The durable report is `native/mimir/LINUX-TESTING-REPORT.md`, with
`linux-results.json`, `linux-source-manifest.json`, and compact samples and
diagnostics under `native/mimir/linux-evidence/`. The old Mac decoder manifest
and feature patch drafts remain historical. The additive
`linux-causal-mask-fix.patch` applies after the main feature draft, including in
the combined build. CI and the Linux guide now verify the Linux source manifest.
Strict numerical acceptance and graph-update sanitizer policy remain open.
Fix/report commits are authorized by the user; pushing is left to the user.

Concurrent engine tests write a hardcoded `test-prefix-state-<arch>-<seed>.bin`
in the current directory. Use isolated working directories for concurrent lanes.
Two post-fix HRM lanes initially returned 255 from colliding state files; both
isolated reruns pass all 970 checks. Original failures remain in the report data.
