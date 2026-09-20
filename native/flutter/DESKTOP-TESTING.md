# Portable desktop acceptance checks

These checks qualify a particular archive/source revision and driver combination.
A CI-produced CPU/import-only archive is a development artifact, not GPU evidence.

## CPU package

1. Download the Linux or Windows artifact from the `Mimir Flutter desktop packages`
   workflow. Extract the outer Actions artifact and then the tar.gz/ZIP inside it.
   Verify the SHA-256 sidecar and retain the included source/model/file manifest.
2. Keep the complete extracted directory together. Move it to another directory
   (also test a path containing spaces) and launch `dfm-mimir` / `dfm-mimir.exe`
   from a different working directory. On Linux, use a supported desktop with GTK3;
   the Ubuntu 22.04 build does not promise portability to every distribution.
3. For import-only packages, open Model and settings and import the same Mimir
   GGUF used for the reference run. Confirm the actual device is CPU and the
   context/reply limits follow the profile. A package with bundled weights should
   load them without a network request.
4. Send a short arithmetic prompt, a name/city memory prompt and a recall prompt.
   The app must use Mimir's own GGUF chat template. Stop a longer reply, send a new
   short prompt, and verify the cancelled reply was not committed to history.
5. Reopen the app and verify the transcript. Test compaction with a bounded long
   conversation and the MixedLM toggle/reuse flow separately from exact mode.
6. With Python available, run `tool/check_desktop_runtime.py EXTRACTED_DIRECTORY`.
   It starts the packaged C ABI from another working directory and tests a copy
   with CPU backend libraries absent. Python is a test dependency, not an app
   dependency. Also execute the full app on a clean host without build SDKs.

## GPU package

Build on the target OS using `tool/package_desktop.py --model MODEL --backends
cpu,cuda,vulkan` after installing the matching SDKs. The SDKs are build-time
requirements; end users need suitable GPU drivers. Do not substitute a Mac
MoltenVK test for Linux/Windows Vulkan driver qualification.

Run the CPU checks on an idle allocated NVIDIA machine (CUDA and Vulkan) and
on AMD/Intel machines for Vulkan. Record GPU, driver, backend/device selected,
app and llama commits, model hash/quantization, context, reply budget, flash mode
and whether MixedLM was enabled. Compare representative logits against CPU with
the established precision-specific tolerances; measure first-token latency,
decode speed and peak RAM/VRAM. Include Q4_K_M, Q8_0 and BF16 where supported.

Repeat without optional GPU libraries/driver access: Automatic should use CPU,
while explicit device selection must fail clearly. The injected native policy
test covers failed initialization followed by CPU success, cleanup between
attempts, strict explicit selection, invalid input and cancellation. Actual
allocation/driver errors still require hardware checks.

Run the existing [Linux release/sanitizer procedure](../../linux-testing.md)
before final production packaging/review. Prior CUDA PrefixLM results do not
qualify this package or the optional MixedLM approximation. GPU crashes, OS
memory kills, mid-generation backend migration and reduced offload retries are
not handled by this first initialization-fallback implementation.
