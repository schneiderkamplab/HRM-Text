# Apple MVP validation — 2026-09-19

The shared SwiftUI MVP builds for macOS and iOS and runs the real Mimir Q4_K_M
model locally on Mac using Metal. This is a development build; physical iOS
qualification and distribution preparation remain open.

## Tested environment and artifact

- Apple M2 Max, 96 GB unified memory; Xcode with Swift 6.1, macOS 15.4 and iOS 18.4 SDKs.
- Swift language mode 5, CMake Xcode generator, Release; minimum macOS 14 / iOS 17.
- Patched llama.cpp: `8f4f4ef8f3139d7d262763936f1f34e48ad46d9c`, unchanged by this app.
- Q4_K_M GGUF SHA-256: `3cf8906f4dd1349c965e7dd873e3995419d34bf846a657840a393c32c89849a5`.
- Context 1,024 tokens, reply budget 128, greedy sampling, F16 KV. Every real-model
  chat uses the model's embedded Mimir template. The app supplies a short system
  identity instruction through that template.

## Results

| Check | Result | Coverage |
| --- | --- | --- |
| macOS Release app | Pass | Bundled Q4 model, embedded Metal sources, ad-hoc signing, sandbox |
| iOS arm64 Release app | Pass | Bundled Q4 model, unsigned cross-compilation; no device execution claim |
| Swift storage tests | Pass | Unicode archive round-trip, incomplete transcript rejection, model copy/hash/deduplication, invalid GGUF magic and path validation |
| Swift conversation-state tests | Pass | Successful pair persistence, history forwarding, cancellation/error rollback, draft recovery, model mismatch guard and new chat |
| Real-model Objective-C++ bridge | Pass | Metal load, templated generation, main-thread streaming callbacks, deterministic restored follow-up, cancel-before-start, invalid history rejection and recovery |
| Native text checks with real Q4/Metal | 73 passed | Existing codec/chat coverage plus restored next-token equivalence and invalid-history rollback |
| Existing native CTest suite | 8/8 passed | Text, Jinja, reasoning persistence, HRMText/llama engine fixtures and CPU metadata variants |
| macOS UI inspection | Pass, bounded smoke | Readable window, active conversation, local response and follow-up observed through Computer Use |

UI observation preceded the final identity instruction and compact iPhone navigation
adjustment. Final source was rebuilt for both platforms; final bridge tests include
the identity instruction. Automated UI coverage, physical phone testing and a
simulator execution run are not claimed. User conversations are not test fixtures
and are not committed. A prior model identity hallucination motivated the system
instruction; factual reliability is not guaranteed by it.

Commands are in [README.md](README.md). Local logs live under
`logs/mimir-apple/`: `macos-final-build.log`, `ios-final-build.log`,
`swift-tests.log`, `bridge-tests.log`, `history-tests.log`, and `native-ctest.log`.
[validation.json](validation.json) records source and log hashes; large weights,
build products and raw local logs are excluded from Git. The new GitHub workflow
runs Swift tests and import-only Mac/iOS builds; no hosted CI run is claimed here.

Documentation validation found two pre-existing issues in the unrelated, untracked
`wiki/pages/benchmark-charts.md` (missing frontmatter and index link). They are
left untouched and excluded from this commit; no MVP-page validation error was reported.

## Review boundaries and remaining work

The app and Objective-C++ bridge are in `native/apple`. The only native wrapper
API addition is `Chat::restore_history`: it validates completed user/assistant pairs
before replacing history and clears KV for full-prefix replay. It retains the
configured system instruction. The upstream llama.cpp four-patch package is
unchanged; its Linux evidence and outstanding qualification items remain as
recorded in the existing handoff. The current source manifest distinguishes this
Mac-tested wrapper addition from the historical Linux-qualified sources.

Before distributing beyond development:

1. Run on physical iPhone/iPad: startup peak memory, repeated turns, thermal behavior,
   background/foreground cancellation, model import, restart/history and compact
   navigation. KV alone is approximately 768 MiB; weight size is not peak memory.
2. Exercise VoiceOver, larger Dynamic Type and narrow/split-screen layouts on devices.
3. Add app icons, signing/provisioning, distribution/notarization and store metadata.
4. Decide supported device/model sizes and whether to expose context/sampling controls.

MVP limits are intentional: no automatic context trimming, interrupted-generation
resume, download/update service, multimodal input, tools or cloud sync. Completed
transcripts persist; partial generations are discarded on cancellation/failure.
Imported models remain on disk, with no model-library deletion UI yet. Archive
load failure preserves the original archive and disables saving for that session;
there is no repair UI. Model identity is its GGUF hash, so changing quantization
requires a new conversation. These are app policies, not new PrefixLM engine
restrictions.
