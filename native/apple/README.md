# DFM Mimir MVP for Apple devices

Shared SwiftUI app for Apple Silicon Mac, iPhone and iPad. It embeds the patched
llama.cpp runtime with Metal and optionally bundles a Mimir GGUF for offline first
launch. There is no inference server, login, analytics, model downloader or network
entitlement. This is a development MVP, not a signed/notarized App Store release.

## Branding

The app uses **DFM Mimir**, matching the model card: the supplied Mimir head mark
is the app icon and sidebar/welcome identity, and the Danish Foundation Models
logo appears on the welcome and About screens. Both original logos are bundled
offline. See [asset provenance](Resources/BRANDING.md). Saved-chat locations and
the app's bundle identifier are unchanged.

## Included

- New chat appears in the sidebar immediately, including before its first reply.
  Empty conversations persist and can be deleted; the first prompt supplies the title.
- Streaming text replies, Stop, new conversations, local history, delete confirmation
  and system sharing of a selected conversation.
- Model import through the system file picker. Imports are copied into app storage
  off the main thread, identified by SHA-256 and checked by the runtime for HRMText,
  PrefixLM and a usable vocabulary/template. A different model cannot silently continue
  a chat saved under another model hash.
- Full-conversation prefill through **Mimir's GGUF chat template** for every turn.
  A short system instruction identifies Mimir and asks it to use the user's language.
  No raw untemplated chat path or ordinary causal prompt-cache reuse is introduced.
- Atomic storage of completed turn pairs. A stopped/failed reply does not enter saved
  history and returns the user's message to the composer. Corrupt archives are left
  untouched; an unsaved-session notice is shown. Storage is excluded from OS backup.
- Model/llama.cpp license notices and accessible, selectable message text.

The first version deliberately uses greedy sampling, a **1,024-token context** and
**128-token reply limit**. It does not silently trim old messages. At capacity, start
another chat. No image/audio input, tools, attachments, cloud sync or automatic model
updates are included. Replies may still be inaccurate, including identity statements.

## Message keyboard behavior

On macOS, Return sends, Shift+Return inserts a newline, and Cmd+Return also sends.
Return used to confirm active IME composition is left to the text system.
On iOS/iPadOS, Return inserts a newline and the visible Send button submits;
Done dismisses the keyboard. The Mac-only send shortcuts are not installed on iOS.

## Build

Requires full Xcode (SwiftUI, Mac/iOS SDKs), CMake >=3.25 and the initialized
`llama.cpp` and `mimir` submodules. No external Swift package or Ninja is required.
The CMake project creates an Xcode project and statically links the native runtime,
including embedded Metal shader sources. Models and generated build output stay out
of Git.

From the repository root:

```bash
git submodule update --init llama.cpp mimir
native/apple/build.sh macos "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
open logs/mimir-apple/macos/Release/MimirChat.app
```

Pass a corrected GGUF from the existing Mimir conversion/qualification workflow.
The local Q4_K_M is the default tested artifact; this command does not download weights.
Omit the model argument for an import-only app. The model is copied into the bundle
as `Mimir.gguf` with a generated `Model.json` containing its SHA-256 identity. Current
Mimir model licensing is Apache-2.0; replacing the bundled model also requires checking
its own license/provenance and updating the bundled notice if necessary.

```bash
native/apple/build.sh ios "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
native/apple/build.sh simulator   # import-only simulator build
```

The iOS command builds **unsigned** for arm64 with iOS 17 minimum. For physical-device
installation, open `logs/mimir-apple/ios/MimirApple.xcodeproj`, select the MimirChat target,
choose your development team under Signing & Capabilities, select your device and run.
Mac minimum deployment target is macOS 14. Mac builds use ad-hoc signing and App Sandbox.
Distribution certificates, provisioning, notarization and App Store metadata
are not provided. Simulator builds use CPU; this is not evidence of phone performance.

### Try it in Simulator

No signing team or physical device is needed. Build specifically for the simulator;
the unsigned `iphoneos` bundle cannot run there:

```bash
native/apple/build.sh simulator "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
xcrun simctl list devices available
# Boot a listed iPhone/iPad UUID, or select one in the Simulator app.
xcrun simctl boot <device-uuid>
xcrun simctl bootstatus <device-uuid> -b
xcrun simctl install <device-uuid> logs/mimir-apple/simulator/Release-iphonesimulator/MimirChat.app
xcrun simctl launch <device-uuid> dk.sdu.mimir.chat
open -a Simulator
```

Skip `boot` if the chosen device is already booted. Subsequent launches can use
the Mimir icon on the simulator's home screen. The bundled model works offline;
the simulator uses host CPU inference and does not validate real-device Metal,
memory pressure or thermal behavior.

Memory is materially larger than weight file size. Mimir's recurrent KV expansion
alone uses about 768 MiB at this context size with F16 KV, plus weights, graph buffers
and application memory. Real iPhone/iPad peak memory, thermal behavior and sustained
throughput still need physical-device measurements. Do not promise compatibility from
successful cross-compilation alone.

## Tests

```bash
native/apple/Tools/test-swift.sh
logs/mimir-apple/macos/Release/mimir-bridge-tests "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
```

Swift tests exercise local storage and app state with temporary archives and a test
bridge. The native bridge test uses the real Q4 model on Metal, its template and system
instruction: generation, main-thread callbacks, completed-history restore, cancellation,
invalid history and recovery. The existing native text test also compares a restored
transcript's next generated tokens to uninterrupted continuation.

The [Apple workflow](../../.github/workflows/mimir-apple.yml) compiles import-only Mac
and iOS apps and runs Swift storage/state tests without downloading large weights.
Real-model/device evidence is separate; see [MVP-REPORT.md](MVP-REPORT.md).

## Implementation boundaries

- `Sources/`: SwiftUI presentation, serialized app state and local storage.
- `Bridge/`: Objective-C++ adapter; serial background inference queue, main-thread
  callbacks and the runtime's thread-safe cancellation operation.
- `../mimir/`: reused native text/session implementation; the small `restore_history`
  addition validates completed turn pairs before replacing state. Full transcript
  replay on the next turn naturally uses PrefixLM, not a disk KV snapshot.
- `../../llama.cpp`: unchanged, pinned to the Linux-qualified PrefixLM implementation.

UI/backend calls are serialized; only cancellation crosses the worker boundary.
Changing model releases the previous runtime before loading the next to bound peak
memory. A failed import/load can be recovered by selecting the bundled model again.
Completed transcripts survive app restart; a currently generating partial reply does not.
