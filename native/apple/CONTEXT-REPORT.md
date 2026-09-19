# Configurable context and reply budgets — 2026-09-19

This supersedes the initial Apple MVP's fixed 1,024 context / 128 reply limits.
Settings and memory-based defaults are shared by Mac, iOS and iPadOS. The minimum
automatic values are 1,024 / 512; tiers rise to 8,192 / 2,048. Manual settings can
exceed 4,096 and 8,192, subject to memory admission and integer validation.
The native wrapper retains its training-context guard by default and adds an
explicit `allow_context_extension` opt-in, used by the app. llama.cpp and its
packaged patches are unchanged.

## Verification

On Apple M2 Max / 96 GB, using Q4_K_M SHA-256
`3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`:

- Mac, unsigned iOS device and CPU Simulator Release builds passed.
- Mac settings accepted a custom reply budget and reset to automatic defaults.
  Final iPhone 16 Plus / iOS 18.4 Simulator loaded successfully and exposed the
  context/reply controls at 4,096 / 1,024. No phone hardware run is claimed.
- Swift tests passed: old archives, custom-setting persistence, reload failure and
  recovery, budget forwarding, limit notices, automatic reset and invalid bounds.
- Real-model Metal bridge tests passed: memory rejection before huge allocation,
  recovery to 1,024, templated generation, callback dispatch, restored history,
  cancellation and recovery.
- Native CTest: 8/8 passed, including the retained default training-length guard
  and opt-in prefix/decode beyond the fixture's training length.
- Real-model extension test: 8,192 allocated context, 4,530-token Mimir-templated
  prompt, four causal decode steps beyond position 4,096, finite logits. The test
  also confirms that extension is rejected without opt-in.

The extension run reported 6,144 MiB F16 KV, 8,240 MiB Metal compute and 272.22 MiB
CPU compute, plus model buffers. These are runtime allocation reports, not measured
process peak RSS. They motivated the conservative 2 MiB/token linear estimate;
CPU additionally reserves estimated quadratic attention workspace. This is not
quality evaluation, HF parity at extended positions, or physical iOS qualification.
Automatic defaults are computed after releasing the previous allocation so pressing
reset does not count an intentionally retained old context. OS memory reclamation
and concurrent applications can still change the selected tier. Simulator uses
host free/inactive memory because the physical-iOS process allowance is not
reliable there.

## Reproduction

From the repository root, after initializing submodules:

```bash
native/apple/Tools/test-swift.sh
native/apple/build.sh macos "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
cmake --build logs/mimir-apple/macos --config Release --target mimir-extended-context-tests
logs/mimir-apple/macos/Release/mimir-bridge-tests "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
logs/mimir-apple/macos/Release/mimir-extended-context-tests "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
native/apple/build.sh ios "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
native/apple/build.sh simulator "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
```

The extended-context executable is an optional real-model Mac/Metal test; hosted
CI does not fetch weights or run this memory-heavy test. Existing Swift and native
fixture tests cover the settings and opt-in boundary without large weights.
Local log/source hashes are in `validation.json`, under `context_settings_followup`.
Linux evidence predates this wrapper opt-in; no new Linux qualification is claimed.
