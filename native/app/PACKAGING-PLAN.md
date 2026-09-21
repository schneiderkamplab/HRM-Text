# Cross-platform package and acceleration plan

Proposed 2026-09-20. See the implementation status below; unchecked design
items are still planned, not implemented.

## First implementation status — 2026-09-20

Implemented Linux/Windows FFI plugin builds and relocatable package tooling,
CPU variants, optional dynamic CUDA/Vulkan modules, platform asset paths and
Windows available-memory probing. Added ranked initialization retries, flash-off
context retry, strict explicit selection and Settings fallback diagnostics.
Added physical iOS Metal to the Apple XCFramework builder. CPU/import-only
package CI runs on Linux/Windows; real hardware qualification is separate.

Mac static CPU and dynamic CPU/Metal real-model smoke tests pass, as do nine
native regression cases and seven Flutter tests. Optional backend absence and
missing-CPU diagnostics are exercised in fresh processes. Hosted package results and their limits are recorded in
[VALIDATION.md](VALIDATION.md); clean-host real-model acceptance remains separate.

Not yet implemented: layer-offload reduction, retry during a failing generation,
crash-relaunch recovery, model downloads/asset packs, installers,
and signing. The baseline is development packaging, not a production release.

Android ARM64 Vulkan is now compiled into the development APK; physical-device
qualification remains pending. See the validation report for build fixes and limits.

## Target

One Flutter UI and shared Mimir runtime, with one release artifact per OS and
architecture. Every package includes a portable CPU backend. Automatic mode uses
an available, qualified accelerator and falls back on recoverable failures.
Model validity and sufficient host memory remain prerequisites for CPU execution.
Exact PrefixLM is the default; MixedLM remains separately opt-in.

## Initial artifacts and backends

| Target | Initial architecture | Artifact | Accelerator candidates | Baseline |
| --- | --- | --- | --- | --- |
| macOS | arm64 | app in DMG | Metal | CPU + Accelerate |
| iOS/iPadOS | arm64 device | signed IPA, then TestFlight/App Store | Metal | CPU |
| Android | arm64-v8a | sideload APK, later Play AAB | Vulkan | ARM CPU |
| Linux | x86_64 | portable tarball, then AppImage | CUDA on NVIDIA; Vulkan on compatible NVIDIA/AMD/Intel | portable x86 CPU |
| Windows | x64 | portable ZIP, then installer/MSIX | CUDA on NVIDIA; Vulkan on compatible NVIDIA/AMD/Intel | portable x86 CPU |

Add Linux/Windows arm64 builds after those native dependencies are exercised on
arm64 hosts. Intel Mac is a separate maintenance decision because Flutter has
announced its deprecation. “All platforms” initially means all five OS families,
not every CPU architecture, driver or accelerator. Android emulator support does
not qualify a physical phone's GPU. The iOS simulator remains CPU-only.

HIP/ROCm and SYCL/oneAPI are subsequent optional desktop backends where they
improve tested coverage/performance. OpenCL and Hexagon merit phone-specific
experiments. Neural Engine, arbitrary Android NPUs and Windows NPUs are not
implicitly supported by exposing llama.cpp devices: Mimir operators, recurrent
execution, PrefixLM masks and model formats all require backend qualification.
No automatic multi-GPU splitting or remote RPC is needed for this first release.

## Original implementation checklist

The sections below preserve the initial design and baseline observations. The
status above and validation report distinguish completed work from remaining work.

## 1. Finish portable native integration

- Add Linux/Windows native runtime targets, runtime/dependency installation,
  model asset lookup, platform memory probes and relocatable library lookup.
  Current `bundledModelPath()` falls through to an Apple-style path there.
- Add a physical iOS device framework slice with Metal; current Flutter Apple
  packaging includes only Mac and simulator slices.
- Build Android Vulkan beside CPU; inspect linker dependencies and verify that
  a missing Vulkan runtime cannot prevent CPU startup. Validate 16 KiB page-size
  compatibility on the Android release artifacts and relevant devices.
- Compile baseline CPU instructions rather than host-native instructions. Use
  supported CPU dispatch/variants for speed without excluding older CPUs.
- On desktop, use llama.cpp's dynamic backend libraries so CUDA/vendor runtimes
  are optional. The current runtime forces `BUILD_SHARED_LIBS=OFF`; change that
  for dynamic desktop packaging because `GGML_BACKEND_DL` requires shared libs.
  Keep core/backends on the identical pinned source and ABI. Load from explicit
  app-owned paths. Ship redistributable runtime components, not GPU drivers.
- Keep mobile native code in the installed/signed app. Downloadable model assets
  are independent of executable backend deployment.

## 2. Make automatic selection and fallback deliberate

Replace first-enumerated-GPU selection with a small shared backend policy, used by
all callers rather than separate per-UI implementations:

1. Enumerate packaged, loadable devices and inspect memory/operator capabilities.
2. Rank qualified candidates: Metal on Apple, CUDA then Vulkan for NVIDIA,
   Vulkan initially for other desktop/mobile GPUs, CPU last. Qualification or
   measured performance can override a GPU that is slower than CPU.
3. Try a bounded model/context configuration; where supported, retry a smaller
   offload or disable an unsupported optimization such as flash attention.
4. On a recoverable backend failure, free the failed context, try the next
   candidate, then CPU. Recompute automatic memory defaults for that device;
   do not silently change explicit user limits. Do not retry corrupt models,
   invalid profiles or cancellation as GPU failures.
5. Expose the actual device, partial CPU execution where measurable, and fallback
   reason. Keep explicit CPU/device selection for reproducible testing; an
   explicitly selected unavailable device should produce an actionable error.
6. If generation fails mid-turn, discard the partial answer and KV, retain the
   transcript and retry once from the templated prompt. Never append a second
   backend's output to a partially emitted answer.

Driver crashes and OS OOM kills cannot be caught by this in-process library.
For the first release, persist a pending-attempt marker and offer/perform a safe
CPU launch after an abnormal termination; clear it after successful work and
invalidate it on backend/driver changes. Desktop worker-process isolation is an
optional later step if uninterrupted recovery from driver crashes is required.
Normal cancellation/background termination must not permanently blacklist a GPU.
CPU fallback is not a promise to run a model that exceeds available system RAM.

## 3. Make model delivery independent of app updates

Preserve an offline bundle option, but also offer a smaller app plus resumable
model download/import. Verify model hashes, write atomically, retain old weights
until replacement succeeds, and reserve space for updates. Share the same
versioned model profile/chat template across packages. The current Q4_K_M model
is about 1.17 GB, so it should not be needlessly downloaded on every UI update.
For Play distribution, plan an asset pack or explicit model download instead of
assuming the current model-in-debug-APK layout is suitable for the store.
Backend preferences/capabilities can extend the profile without hardcoding each
future Mimir model into the UI. Add notices/licenses and checksummed manifests.

## 4. Qualify packages, not just builds

CI builds on macOS, Linux and Windows. Test the extracted/installed artifacts on
clean hosts with no compiler/SDK and, separately, without a GPU runtime. Include
missing backend DLLs/shared objects, insufficient VRAM, rejected operators,
invalid user settings, cancellation, compaction, restart and upgrade persistence.
A bounded injected-failure suite should verify retry order and transcript safety.

Run real hardware tests on NVIDIA (CUDA and Vulkan), AMD/Intel (Vulkan), at least
one Adreno and one Mali phone, an iPhone/iPad, and Apple Silicon. A Linux server
can qualify native CPU/CUDA and whatever GPUs it actually has; it cannot qualify
Windows loaders/drivers or phone GPUs. Use an idle allocated GPU for measurements.

All chat tests use Mimir's template. Use a fixed representative set covering
short replies, recall, a long prompt, cancellation and compaction. Compare CPU
and accelerated logits with documented precision-specific tolerances; test
Q4_K_M, Q8_0 and BF16 where supported. Measure prefill/first-token latency,
decode rate and peak RAM/VRAM. Test exact PrefixLM and the optional MixedLM path
separately. Reuse existing Linux evidence, but do not call new release artifacts
or MixedLM qualified merely because the earlier CUDA PrefixLM build passed.
Record unsupported combinations explicitly. Run the existing release/sanitizer
procedures before final Linux packaging/review.

## Priority and milestones

1. **Portable CPU packages + fallback policy:** Linux/Windows runnable bundles,
   Apple device slice, shared selection/retry diagnostics and fault tests.
2. **Broad GPU coverage:** Metal, desktop CUDA/Vulkan and Android Vulkan;
   hardware correctness and packaged dependency tests.
3. **Release candidates:** relocatable desktop installers, Android APK,
   device iOS build, model delivery, checksums and CI release manifests.
4. **Distribution:** signing/notarization, TestFlight/App Store, Play and Windows
   store credentials when the user is ready. Build/validation can proceed first;
   actual iOS device distribution still needs provisioning/signing.
5. **Additional optimizations:** HIP/SYCL, qualified OpenCL/Hexagon and additional
   CPU architectures. Avoid delaying baseline packages for every specialty SDK.

Completion means each advertised package installs cleanly, selects a verified
accelerator when usable, generates correct templated responses, and runs on CPU
when acceleration is absent or a recoverable accelerator failure is injected.

## References and current evidence

- [Current integration](README.md), [validation](VALIDATION.md),
  [backend evidence](../mimir/BACKENDS.md), [MixedLM evidence](../mimir/MIXEDLM.md).
- [Flutter supported platforms](https://docs.flutter.dev/reference/supported-platforms).
- [llama.cpp build/backends](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).
- [Play Asset Delivery](https://developer.android.com/guide/playcore/asset-delivery).


## Release descriptions for every version

Every patch, minor and major release must have self-contained user instructions,
not just changes since the last release. Follow the
[release-description policy](releases/README.md) and
[coverage template](releases/TEMPLATE.md). Store the published text in
`releases/VERSION.md`; verify it against the shipped source and artifacts, then
read the GitHub description back after publishing. Include API/headless setup,
model/context controls, network/feedback consent, installation and platform limits
for that version. Historical notes must not claim subsequently added features.
