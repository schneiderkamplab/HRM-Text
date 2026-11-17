---
type: Runbook
title: PrefixLM and MixedLM upstream integration
description: Scoped integration onto October 2026 upstream llama.cpp, API adaptation, qualification evidence and release gates.
tags: [mimir, llama-cpp, prefixlm, mixedlm, release]
status: draft
last_updated: 2026-10-17
confidence: high
---

# PrefixLM and MixedLM upstream integration

The standalone binary release is paused until this integration is qualified.
This supersedes the preliminary merge assessment in [the binary runbook](mimir-native-binaries.md):
the final fetched upstream master is f74e2fa6a31cc33ab4ee4ae516641cfe62df3924,
not the earlier ea0c4c2c8 observation. A remote master lookup confirmed this
pin on 2026-10-17. There are 688 upstream-only commits and eight old fork-only
commits relative to codex/mixedlm.

## Scope and history

The integration is on llama.cpp branch codex/prefixlm-upstream-20261017,
based directly on upstream, with two scoped commits:

- 3eed91acf: training-faithful Mimir tokenizer/converter and Unicode template support.
- a800a5ff3: PrefixLM/MixedLM, lifecycle rules, exact-prefix cache, extended-batch API adaptation and regression tests.

The consuming HRM-Text branch is codex/llama-upstream-integration.
Main and the old codex/mixedlm branch are unchanged. No history was rewritten
and no upstream PR was submitted.

Per the user's scope instruction, generic ggml pointer-arithmetic changes,
Vulkan SDK/Android fixes and the separate sampler/server generation-persistence
extension were not ported. Those remain recoverable from the old branch.
PrefixLM KV/context snapshots and boundary logits remain in the attention patch;
sampler serialization, retained generations across server restarts and parser
continuation follow upstream instead. These should not be advertised as features
of the new standalone build.

## Upstream attention support

The fetched upstream public enum supports only causal and non-causal attention.
HRMText's prefix metadata is retained for round trips, with an explicit comment
that PrefixLM prefill is not implemented. No MixedLM implementation is present.
Thus neither attention implementation can currently be replaced with upstream
functionality.

Upstream has introduced llama_batch_ext and llama_process, used by its CLI,
server and examples. The integrated attention implementation validates extended
batches directly. Added entry points are llama_process_prefix,
llama_process_prefix_mixed, and llama_process_mixed_lm. Legacy prefix APIs
prepare extended batches with per-sequence inferred positions. Extended callers
set positions explicitly. Ordinary encode/decode behaviour follows upstream;
both encode APIs reject PrefixLM and both decode APIs enforce continuation rules.

Unified PrefixLM retains sparse sequence IDs with a bounded number of live
sequences. Tests of ordinary causal sparse IDs now allocate upstream's required
ID range explicitly. No causal-mode batch namespace was expanded.

## Local qualification

Build: Apple M2 Max, Release, CPU/Accelerate/Metal, OpenSSL disabled.
Built CLI, server, bench, quantizer, simple/simple-chat examples and selected tests.

- HRMText PrefixLM/MixedLM suite: **2,144 checks passed**.
- Llama PrefixLM/MixedLM suite: **2,144 checks passed**.
- Both suites exercise CPU and Metal, flash attention on/off, legacy and extended
  calls, independent block-attention oracle, forks, shared capacity, state restore,
  mixed phases, adapters and invalid input.
- Upstream ordinary Llama/HRMText architecture checks: **12 passed**. BERT entries
  were skipped by that test harness; this is not an encoder qualification.
- CTest sampling, batch allocation and chat tests passed. The model-dependent
  backend-sampler CTest exit alone is not claimed as model-based qualification.
- Existing independent HF tiny-model reference: **31 steps / 130 output rows**.
  CPU max absolute error 7.152557373046875e-7; Metal without flash
  8.344650268554688e-7; both pass the original 1e-4 tolerance.
  Metal flash max error 1.0834634304046631e-4; two causal-control steps fail that
  strict threshold. All 130 top-token choices agree on each backend. No tolerance
  was relaxed. The prior recorded Metal-flash run also failed the same strict
  threshold (maximum 7.294714450836182e-4).
- Real v1.5 CLI chat using embedded template: Q4_K_M passed on CPU and Metal;
  Q8_0 and BF16 passed on Metal. Each answered “København”.
  Upstream CLI no longer accepts -cnv; chat is its native interface.
- Server OpenAI-compatible chat: cold/warm exact-prefix requests, two concurrent
  slots and multi-turn follow-up passed. Warm cache reported prompt_n=0,
  cache_n=29, with the same response as cold generation.

Local machine-readable results: logs/upstream-integration/.
Build: logs/llama-upstream-build/. Diagnostic logs: /tmp/llama-upstream-*
and /tmp/prefix-{hrm,llama}-upstream.log.

## Linux gate and remaining work

Dispatch .github/workflows/mimir-runtime.yml on the integration branch with
core_only=true (the default on this branch). Pull requests also use this core
qualification path. This runs standalone Linux CPU Release and AddressSanitizer
builds, both PrefixLM suites, ordinary architecture checks and helper tests.
It does not run the historical app/persistence qualification workflow.
Initial CI run: https://github.com/schneiderkamplab/HRM-Text/actions/runs/38997326649.
Linux Release and AddressSanitizer both passed: five CTest suites per build,
1,072 PrefixLM/MixedLM checks for each of HRMText and Llama per build, plus
three ordinary CPU architecture cases per build. ASan used halt_on_error=1
and detect_leaks=1. CI completed successfully on 2026-10-17; downloaded test
logs are in logs/upstream-integration/linux-release and linux-asan.

Superseded (2026-10-17): the initial report described null-base pointer arithmetic
in graph sizing as a current upstream UBSan issue. Inspection of the caller,
ggml_graph_nbytes(), corrects that claim: current upstream starts its synthetic
pointer at 1024 and subtracts 1024 from the result, explicitly working around
the historical “applying non-zero offset X to null pointer” diagnostic. The old
fork instead changed the helper to integer arithmetic. This integration follows
upstream. UBSan has not been run on this pin; no current UBSan failure has been
demonstrated, and neither UBSan-clean status nor a present blocker is established.

Release status checked 2026-10-17: the standalone llama.cpp release
llama-mimir-4122b9a81 is still a draft with zero assets. The public
dfm-mimir-native-v0.1.5 release contains nine mimir-chat wrapper archives, not
the requested standalone llama-cli/server/bench/quantize distribution. Packaging
the integrated pin remains outstanding.

CUDA, Vulkan, Windows and Qualcomm runtime qualification must be repeated for
this new pin; evidence from the old pin does not automatically carry over.
The existing broad binary workflow still names the old pin and must be updated
before dispatch/publication. The native mimir-chat consumer also compiles successfully against the updated API
and generates “København.” using the v1.5 Q4_K_M model on Metal.
Apple application packages are not rebuilt or released by this integration.

Knowledge validation: uv run --no-project --with pyyaml python scripts/validate_okf.py wiki
completed with zero errors and 15 pre-existing missing-local-link warnings.
Use --no-project here to avoid installing the training project dependencies.

## Upstream published binary matrix (2026-10-17)

Verified actual assets of https://github.com/ggml-org/llama.cpp/releases/tag/b11706
against its release workflow and Snapdragon presets (both match the integrated
source files byte-for-byte). GitHub's releases/latest instead points to v0.7.0,
which currently contains only nightly-tag.txt; use the numbered build release.

- macOS: ARM64 CPU/Metal; x64 CPU (Metal explicitly disabled).
- Ubuntu x64: CPU, Vulkan, CUDA 12.8/13.4, ROCm 10.0, SYCL FP16/FP32,
  OpenVINO 2026.4.1.
- Ubuntu ARM64: CPU, Vulkan, CUDA 13.4; Ubuntu s390x: CPU.
- Linux ARM64 Snapdragon: OpenCL GPU and Hexagon NPU (release command overrides
  the preset's OpenCL OFF to ON).
- Windows x64: CPU, Vulkan, CUDA 12.4/13.4, ROCm 10.0, SYCL, OpenVINO 2026.4.1.
- Windows ARM64: CPU, Vulkan, CUDA 13.4, Adreno OpenCL. No Windows Hexagon
  package appears in this release.
- Android ARM64: generic CPU; Snapdragon OpenCL GPU plus Hexagon NPU.
- Additional assets: six CUDA runtime archives, web UI, Apple XCFramework
  built for macOS and iOS devices (not simulator).

These are published packages, not evidence that our PrefixLM/MixedLM execution
has been qualified on each accelerator. Reusing upstream packaging is preferable
to maintaining an independent matrix; hardware validation remains separate.

## Reused release workflow (2026-10-17)

Supersedes the earlier nine-target standalone packager: HRM-Text's
.github/workflows/llama-binaries.yml now derives build jobs, UI build and archive
assembly from the pinned upstream workflows. Regenerate with
`python3 native/binaries/sync_upstream_release.py`; `--check` detects drift.
Source checkout is pinned to the fork's full SHA, including in UI builds and
local composite actions. All upstream targets are retained except s390x, whose
upstream-specific runner is unavailable. Matrix fail-fast is disabled.

Manual dispatch accepts publish=false (default, Actions artifacts) or true
(draft upload followed by prerelease publication once every build passes).
Tags use mimir-<source-sha>; assets keep upstream's llama-<tag>-bin-* names,
Windows CPU/backend merge and separate CUDA runtimes. SOURCE.txt and SHA256SUMS
are added. The old mimir-chat publisher no longer handles standalone releases.
Standalone TLS follows upstream, not the Apple app's OS-only networking policy.
See native/binaries/LLAMA.md for operation and package limitations.

The generator passed YAML parsing, pinned-checkout/dependency validation and
deterministic regeneration checks. Cross-platform execution remains a CI gate;
successful packaging must not be confused with GPU/NPU inference qualification.

## Release warning fix (2026-10-17)

Initial matrix run 39003251048 failed Linux CPU x64/ARM64, macOS x64 and generic
Android builds on the same two signed/unsigned token-count comparisons in
decode_prefix_lm. Upstream enables LLAMA_FATAL_WARNINGS; earlier qualification
did not. The run was cancelled before publication to replace the source pin.

Fork commit 4f2e25bcf bounds the token count by INT32_MAX before converting it,
compares capacities without narrowing, and uses the checked signed count for
both loops. No attention semantics changed. The local strict Release build
passed for CLI, server, benchmark, quantizer and test-llama-archs. The Linux core
qualification workflow now also sets LLAMA_FATAL_WARNINGS=ON. Release jobs are
regenerated from the updated fork pin; no compiler warning suppression is used.
Both local CTest PrefixLM suites (HRMText and Llama) passed after this rebuild.

### Strict Linux qualification follow-up

Run 39003866775 exposed another warning in the PrefixLM test: GCC rejects a
copied range-loop pair under -Werror=range-loop-construct. Commit 1c979346d
uses a const reference; production runtime code is unchanged. Local strict
test compilation and both PrefixLM suites passed after the adjustment.

The ASan job also stopped during compilation on GCC 13 libstdc++ regex internals
with -Werror=maybe-uninitialized, before exercising our tests. ASan qualification
now uses Clang; the ordinary Release job retains GCC. Both retain fatal warnings,
and sanitizer flags and leak detection remain enabled. This is a compiler
selection change, not evidence that GCC ASan execution passed. Release matrix
39003864987 had no failed jobs at this check, but is superseded by a fresh run
against the updated test/source pin so distribution and qualification match.

### Shared-library ASan startup limitation

Run 39005079691: GCC Release passed. Clang ASan passed all five CTest suites
and all three ordinary architecture cases, then llama-cli --help aborted with
an ODR violation for httplib::detail::RegexMatcher RTTI. The duplicate globals
are in libllama-server-impl.so and libllama-common.so. Upstream's vendor target
builds cpp-httplib STATIC and links it into both shared libraries.

ASan qualification now uses the supported BUILD_SHARED_LIBS=OFF configuration
to give each executable a single copy. This does not disable ODR checks, fatal
warnings, leak detection or ASan. It does not establish shared-package ASan
startup cleanliness: that upstream linkage limitation remains unresolved.
Release qualification and published package linkage remain unchanged. No fork
runtime changes or release-matrix restart are needed for this CI-only adjustment.

Follow-up run https://github.com/schneiderkamplab/HRM-Text/actions/runs/39005968713
passed both GCC shared Release and Clang static ASan qualification on 2026-10-17.
Both jobs passed the five CTest suites, three ordinary architecture cases and
CLI/server/benchmark startup checks. ASan retained halt_on_error=1:detect_leaks=1.
The shared-library ASan limitation above is not superseded by this static result.
At 05:35 UTC the release matrix 39005077796 had 22 successful jobs, no failures,
and eight CUDA/ROCm jobs still running; publication remained pending.

### Publication recovery

All 30 build/preparation jobs in run 39005077796 passed. The publish job assembled
the platform archives and SHA256SUMS, then uploaded the 5,002,927,742-byte
release-packages Actions artifact (12094347352). GitHub returned HTTP 403
Resource not accessible by integration on release creation; no binary build failed.
An authenticated maintainer-created draft for mimir-1c979346d targets the exact
build workflow commit c40ce8cb28d3de9c737daf9f74ed11fc82671761. Only the publish
job was rerun, reusing all successful build artifacts. Outcome still pending.
Future generated workflows overwrite their assembled Actions artifact on retry
and explicitly distinguish static ASan qualification in release notes.

Publication completed manually on 2026-10-17:
https://github.com/schneiderkamplab/HRM-Text/releases/tag/mimir-1c979346d
contains all 35 upstream-format archives (upstream b11706 names with our tag,
excluding only s390x), SOURCE.txt and SHA256SUMS: 37 assets total. Every archive
and SOURCE.txt matched GitHub's uploaded SHA-256 digest against the checksum file.
The release is public and marked prerelease. Linux Release and static ASan
qualification passed in run 39005968713.

The publish retry uploaded the real assets but also downloaded the previous
release-packages artifact, then attempted to upload that aggregate ZIP (>2 GiB).
The Actions workflow therefore remains failed at publication even though all
30 build/preparation jobs succeeded. Recovery removed the aggregate entry from
SHA256SUMS, verified all actual assets, and published using maintainer credentials.
Generated workflows now exclude release-packages from artifact downloads.
No binaries were rebuilt or altered during recovery. Monitoring can stop.

## Downloaded archive validation (2026-10-17)

Tested actual release mimir-1c979346d downloads, not replacement local binaries.
Checksums matched for macOS ARM64, Ubuntu CPU x64, Ubuntu CUDA 12.8/13.4 x64,
their two CUDA runtime archives, and Ubuntu Vulkan x64. Test model was official
v1.5 Q4_K_M, SHA256 82f73664e33a0369d047c69d9cdfe23082028d5539c8a2fbad8d5dbc6256e106
(identical on Mac and dfm). Chat used the embedded template in CLI/server.

- macOS 27, M2 Max: packaged CLI and server passed on CPU and Metal. Both server
  runs answered the Danish capital question with København and an English
  follow-up with Copenhagen. CLI/server/benchmark help and quantizer usage passed.
- The local test-llama-archs harness loaded the downloaded macOS libraries via
  DYLD_LIBRARY_PATH; DYLD_PRINT_LIBRARIES confirmed libllama, common and ggml
  CPU/BLAS/Metal came from the extracted archive. HRMText and Llama each passed
  2,144 PrefixLM/MixedLM checks. This exercises the packaged implementation,
  although the test executable itself is locally built.
- dfm: Ubuntu 24.04, x86_64 AMD EPYC 9655, eight NVIDIA B200 GPUs. Packaged
  Ubuntu CPU CLI/server passed the same real-model chat and startup checks,
  using two threads and nice priority 10. Temporary servers were shut down.
- Both packaged CUDA versions loaded with their matching runtime directories
  in LD_LIBRARY_PATH and enumerated all eight B200s. This includes CUDA 13.4
  despite nvidia-smi reporting CUDA UMD 13.3. No inference compatibility claim
  follows from successful enumeration alone.
- Vulkan initially lacked libvulkan.so.1. Ubuntu libvulkan1 1.3.275.0-1build1
  was downloaded and extracted into the test directory, without installing or
  changing system packages. All plugin dependencies then resolved, but NVIDIA
  ICD initialization failed: could not obtain vkCreateInstance through
  vk_icdGetInstanceProcAddr; the loader reported no drivers. No Vulkan device
  was exposed. Host driver configuration needs investigation outside training.

All GPUs remained at 100% utilization with roughly 164-167 GiB occupied during
these checks. No GPU inference or benchmark was launched on dfm, and training
was not paused or modified. CUDA inference and performance qualification remain
pending a coordinated idle window. Local evidence: logs/release-smoke/;
remote files: /home/ucloud/mimir-release-smoke/. The smoke harness and JSON
responses are retained there. These short correctness checks are not speed
benchmarks, especially with concurrent training on dfm.

### GPU headroom experiments (2026-10-17)

The earlier decision to defer all GPU inference was superseded by explicit user
permission to use available memory headroom. Sequential tests used physical B200
GPU 1 (UUID GPU-14fd8b70-0529-1716-1700-fce6cc64f3d9), with approximately
18,216 MiB initially free. A process-group guard sampled memory every two seconds,
limited additional usage to 4,096 MiB, required 10,000 MiB remaining free, and
imposed a 300-second deadline per experiment. Training was not paused or
reconfigured; shared GPU utilization means these are correctness experiments,
not controlled performance measurements.

- Released CUDA 12.8 x64 binaries and matching runtime passed actual Mimir v1.5
  Q4_K_M CLI inference and two-turn server chat using the embedded chat template:
  København, then Copenhagen. Context/batch/microbatch 1,024, GPU layers 99,
  two CPU threads. Peak observed extra GPU allocation: 2,297 MiB.
- CUDA 13.4 x64 device enumeration succeeded earlier, but actual inference now
  **fails** on driver 610.57.04 (CUDA UMD 13.3): CUDA reports “the provided PTX
  was compiled with an unsupported toolchain” from
  ggml_cuda_kernel_can_use_pdl / cudaFuncGetAttributes. CLI aborted before
  generation; peak extra allocation 37 MiB. Enumeration is insufficient evidence
  of compatibility. Use the tested 12.8 archive on this host; do not change the
  training host driver merely to qualify this archive.
- A diagnostic test-llama-archs executable built from exact fork revision
  1c979346d and linked against downloaded Linux libraries exposed an HRMText
  parity failure with CUDA 12.8: batched causal answer versus single-token
  answer after the same prefix, NMSE 8.63247055533e-6 versus the unchanged 1e-6
  limit (original tests/test-llama-archs.cpp line 1477, diagnostic line 1478).
  Peak extra allocation 719 MiB. The temporary harness only added call-site
  diagnostics; released libraries and test tolerance were unchanged. This
  blocks full CUDA regression qualification despite the real-model chat pass.
  Kernel precision versus PrefixLM-specific behavior remains to be isolated.

Evidence is retained under logs/release-smoke/cuda-*-results locally and
/home/ucloud/mimir-release-smoke on dfm, including memory samples and harness
logs. The diagnostic executable is not part of the published archives.

The Llama architecture suite subsequently passed all 2,144 PrefixLM/MixedLM
checks (CPU plus the single visible CUDA GPU, flash attention off/on), with
829 MiB peak additional memory. All guards completed without triggering. After
tests, GPU 1 returned to 164,404 MiB used / 18,216 MiB free, the original training
process 24237 was still running, and no experimental server/test process remained.
This narrows the observed regression to HRMText in this test set, but does not
establish whether its cause is architecture-specific arithmetic or prefix logic.
