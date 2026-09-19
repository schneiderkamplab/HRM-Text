---
type: Technical Reference
title: Mimir Apple Chat MVP
description: Shared SwiftUI Mac and iOS development app, native bridge contract, verified checks and physical-device validation gaps.
tags: [mimir, apple, swiftui, metal, mobile]
status: draft
last_updated: 2026-09-19
confidence: high
---
# Mimir Apple Chat MVP

The earlier app-packaging work item is superseded as of 2026-09-19 by the shared
SwiftUI implementation in [native/apple](../../../native/apple/README.md).
The [feasibility study](mimir-apple-chat-feasibility.md) remains historical context.

The Mac app runs bundled Q4_K_M through the patched llama.cpp Metal backend.
Unsigned iOS arm64 cross-compilation also passes. CMake's Xcode generator avoids a
Ninja dependency and embeds Metal sources in the statically linked runtime.
Models are build resources outside Git; an import-only build is available.

All chat turns use Mimir's own template, including the short app identity system
instruction. The app restores completed transcripts and recomputes the full prefix
for every turn. Native `Chat::restore_history` validates UTF-8 and alternating
completed pairs before mutation. Cancellation rolls back the partial turn and
returns the user's prompt to the composer. Saved JSON is atomic and excluded from
OS backup; unreadable archives are preserved rather than replaced.

[Validation report](../../../native/apple/MVP-REPORT.md) records Mac/iOS builds,
Swift storage/state tests, real Q4/Metal bridge tests, 73 native text checks and
8/8 native regressions. Computer Use successfully read the live Mac UI; no user
conversation is committed as test data. Physical iPhone/iPad performance, memory,
thermals and accessibility remain unqualified. The app uses 1,024 context tokens
and 128 reply tokens; F16 KV alone costs approximately 768 MiB.

The llama.cpp submodule and four candidate patches are unchanged. The current
release source manifest records the Mac-tested wrapper extension separately;
historical Linux reports are not retroactively rewritten. Hosted Apple CI is
configured for import-only builds and Swift tests but has not been observed here.

## Sidebar delay — fixed (2026-09-19)

Superseded behavior: the initial MVP did not insert a conversation when New chat is pressed or when
its first prompt is sent. `ChatStore.newChat` only clears selection; `send` inserts
into `saved.conversations` only on successful reply completion. Because the sidebar
lists that collection directly, the new chat is absent throughout first-response
generation and never appears if that first response is stopped or fails. The
initial store test explicitly expects an empty collection while generating, so
passing tests do not establish the desired immediate-sidebar behavior. This is a
confirmed UI state issue, not model latency or delayed JSON persistence; at diagnosis, no fix
had been applied. A fix should distinguish immediate conversation identity
from committing completed message pairs.

The fix creates, selects and persists an empty conversation immediately on New
chat, then updates its title when the first prompt is sent. Sending directly from
the welcome screen also inserts the entry before inference begins. Empty chats
can exist before model selection; their optional model identity is assigned on
first send, while completed conversations retain the model mismatch guard.
Stop/error keeps the same entry and returns the prompt to the composer without
saving partial messages. Empty entries can be deleted through the conversation
menu. Bounded store tests cover these transitions, reload and stable identity.

## Simulator launch verified (2026-09-19)

Built the bundled-Q4 arm64 simulator app and installed/launched it with `simctl`
on the available iPhone 16 Pro / iOS 18.4 simulator. Computer Use confirmed the
welcome screen and “On-device · Simulator CPU” ready status. This supersedes the
initial report's lack of simulator execution evidence, but does not add a generated
reply or physical-device performance result. Build/install commands are in the
Apple README.

The first launch stalled in Metal shader initialization despite requesting CPU
inference: backend registration initialized the compiled-in Metal backend. The
Apple CMake project now disables `GGML_METAL` for the `iphonesimulator` SDK only.
The rebuilt app loaded successfully; Mac and physical iOS still enable Metal.

## Keyboard layout fix (2026-09-19)

The composer now uses a bottom safe-area inset, with scrollable welcome content
and interactive scroll dismissal. An iOS-only Done button in the composer clears
FocusState, and sending also clears focus. A keyboard toolbar was tried but did
not reliably display its button in Simulator, so the dismissal control lives in
the composer instead. Mac, iOS and simulator Release builds pass. The updated
app was installed on iPhone 16 Pro / iOS 18.4 Simulator; accessibility inspection
confirmed the Dismiss keyboard control. A click-through dismissal check was
interrupted by live user window/device changes; no completed UI assertion is
claimed. Saved conversations were retained during installation.

Follow-up verification on iPhone 16 Plus / iOS 18.4 Simulator: installed the same
updated app on that device, tapped the message field and observed the software
keyboard, tapped Dismiss keyboard and observed its removal, then tapped the
message field again and observed its return. This completes the previously
interrupted dismissal/reopening check. The keyboard was left visible for the user.

## Platform send keys (2026-09-19)

macOS now handles unmodified Return as send, preserves Shift+Return for newlines,
and retains Cmd+Return as a send shortcut. Marked-text composition is passed to
the native editor, preventing plain Return from submitting during IME confirmation.
iOS keeps native multiline Return and explicit Send; Mac-only shortcuts are not
installed there. Mac, iOS and simulator Release builds passed. The Mac app was
opened, but live user interaction interrupted the keyboard smoke test before
key-by-key verification, so no completed Return/Shift+Return or IME UI test is
claimed. The existing iOS simulator installation was left running undisturbed.

### Completed live send-key checks (2026-09-19)

After the user paused interaction, Mac Return submitted a test prompt and produced
a reply. The initial Shift+Return pass-through failed to insert a newline; the
Mac handler now calls the native field editor's `insertNewlineIgnoringFieldEditor`
for Shift+Return. The repeated UI check showed a two-line draft, and Cmd+Return
submitted both lines and generated a reply. On iPhone 16 Plus / iOS 18.4 Simulator,
clicking the software Return key inserted newlines without submitting the draft.
This supersedes the interrupted basic key verification above. IME behavior remains
protected in code but untested with an actual composition input method. Only test
messages/drafts were added; existing user conversations were not deleted.

## DFM Mimir branding (2026-09-19)

The app display name, sidebar, welcome screen, assistant labels, composer and About
screen now use **DFM Mimir**, matching the model-card heading. The DFM wordmark
comes from the model card's `DFM-logo.png`; the square white-on-red Mimir head is
copied from the user's `~/sdu/talks/codex/NNF_follow_up_note/figures/assets/mimir-logo.png`.
Original assets, source hashes and provenance are recorded in
[BRANDING.md](../../../native/apple/Resources/BRANDING.md). Standard Mac/iOS icon sizes derive from the
supplied square logo. This supersedes the initial report's missing-app-icon item.

The app uses red accents; the DFM logo keeps a white backing for dark-mode contrast.
Both logos are offline bundle assets. Bundle identifier and storage locations stay
unchanged, retaining existing chats. Mac, iOS and simulator Release builds passed;
generated plists contain the DFM Mimir display name and AppIcon entries. Mac and
iPhone 16 Plus simulator welcome screens were visually inspected with both logos
present and readable. Dark-mode and physical-device visual checks were not run.

## Assistant answer mark (2026-09-19)

Assistant answer headers now show a 20-point Mimir head before “DFM MIMIR”,
reusing the bundled logo. The shared message renderer covers saved and streaming
answers on Mac/iOS. The adjacent decorative image is hidden from accessibility
so the speaker name is announced once. User headers remain text-only.

## Configurable context and replies (2026-09-19)

Superseded: fixed 1,024 context / 128 reply limits. Settings now persist custom
context and reply budgets; automatic tiers are 1,024/512, 2,048/512, 4,096/1,024,
and 8,192/2,048, chosen using current available memory and actual model file size.
Release the old context before recalculating defaults, otherwise reset counts its
own allocation and can unnecessarily reduce the tier. Manual contexts can exceed
4,096 and 8,192, subject to integer bounds and memory admission. The native wrapper
retains the training-length guard unless `allow_context_extension` is enabled.
llama.cpp and packaged patches are unchanged.

Mac/iOS/Simulator builds, Swift settings tests, real Metal bridge tests and 8/8
native tests passed. A real 4,530-token Mimir-templated prompt and four decode steps
ran in an 8,192 context with finite logits. Reported KV was 6 GiB and Metal compute
about 8 GiB, so weight size alone is a poor memory estimate. Larger-position answer
quality and physical iOS peak memory are not qualified. See the
[context report](../../../native/apple/CONTEXT-REPORT.md) for commands and limits.

## Model profiles and 32,768 context (2026-09-19)

Superseded: the previous 8,192 automatic ceiling and mandatory manual memory
admission. The v1 profile now permits 1,024–32,768; automatic tiers extend to
16,384/32,768. Manual choices bypass the estimate, with an allocation-risk note.
The training-context label comes from GGUF (4,096 for v1), not a UI constant.
Versioned JSON profiles configure context/reply policy, memory coefficients,
threads and system instruction. Actual weight size remains file-derived.
Profiles can be embedded with `build.sh`'s third argument or imported in settings,
and persist with the selected model. New bundled weights retain their new SHA
identity; old profile overrides apply only to matching identities. Switching
weights resets custom limits to automatic defaults.

Mac/iOS/Simulator builds, Swift profile tests and real Metal bridge tests pass.
No full 32,768 generation or physical-device qualification is claimed. See
[model profiles](../../../native/apple/MODEL-PROFILES.md) for the new-model workflow
and exact evidence. llama.cpp and the native wrapper are unchanged by this update.

## Distribution readiness (2026-09-19)

Recommended first channels: Developer ID signed/notarized Mac download and iOS
TestFlight, followed by App Store release. Existing builds remain development
artifacts (ad-hoc Mac signing, unsigned iOS). Public packaging needs distribution
signing, release versioning, and device qualification; App Store submissions also
need store metadata/privacy disclosures and review.

The tested iOS 18.4 SDK is now too old for App Store Connect uploads: Apple requires
iOS/iPadOS 26 SDK or newer from April 28, 2026. Upgrade the release toolchain before
TestFlight/App Store handoff; this does not itself require raising the deployment
minimum. Sources: [SDK requirement](https://developer.apple.com/news/?id=ueeok6yw),
[Developer ID](https://developer.apple.com/developer-id/),
[TestFlight](https://developer.apple.com/testflight/).

## Mac shutdown ordering (2026-09-19)

Quitting the SwiftUI app could SIGABRT in `ggml_metal_rsets_free`: global Metal
cleanup ran while SwiftUI still retained the loaded engine/model buffers. The
app delegate now delays termination until engine cancellation, worker draining
and model/context release complete. New work is rejected after shutdown starts.
Real Metal exit tests deliberately retain the engine until process exit; idle,
pending-load and active-generation cases all pass. Mac/iOS/Simulator builds and
Swift/bridge tests pass. Live Cmd-Q inspection was blocked by the locked Mac.
See [the report](../../../native/apple/MVP-REPORT.md#mac-exit-crash-fix--2026-09-19).

The user deferred both release-toolchain installation and developer-account setup.
Provisional toolchain/CI edits were removed; Xcode 16.3 remains selected. The SDK
upgrade requirement above still applies before TestFlight/App Store submission.

## Compaction and completed Cmd-Q verification (2026-09-19)

Superseded: the locked-screen limitation on live Quit verification. Cmd-Q with a
loaded model terminated the Mac app process, with no new crash report. Existing
idle/loading/active exit tests still pass after compaction added codec ownership.

Automatic compaction now summarizes older complete turns near 90% context usage,
aiming for 75%; every size check uses the exact Mimir template/tokenizer. The full
transcript remains intact. Separate persisted summary/coverage is committed only
with a successful answer, so cancellation/failure does not replace prior memory.
Settings independently control compaction and summary visibility. Off mode sends
full history again. Mac UI verification demonstrated compaction of a 1,024-context
chat and showing/hiding its summary. All three Apple builds, Swift tests and real
Metal compaction/cancellation tests pass. See
[the report](../../../native/apple/COMPACTION-REPORT.md) for limitations, including
oversized individual turns and lossy summary quality. No llama.cpp changes.


## Mac selectable-text scrolling hang (2026-09-19)

A live scroll hang in the long compaction test consumed one CPU core; the main
thread sample remained in SwiftUI selection-overlay/layout updates. Mac message
and summary text now use a shared native selectable NSTextView with width-aware
measurement; iOS keeps SwiftUI text. Repeated scrolling, selection/copy and window
resizing passed in the same saved conversation. The post-fix sample showed normal
event-loop waiting and 0.3% CPU. All Apple builds and Swift tests passed. See the
[follow-up evidence](../../../native/apple/COMPACTION-REPORT.md#mac-scrolling-hang-follow-up-2026-09-19).


## Context indicator and compaction activity (2026-09-19)

The app now displays exact tokenizer/template counts for the effective completed
conversation against its configured context. During generation it displays the
prepared input count; after completion/cancellation it recomputes the saved
conversation count. Draft text, reserved reply budget and the streaming answer
are excluded. Counting runs on the engine worker and ignores stale UI callbacks.
Both activity indicators distinguish compacting from thinking, with an explicit
transition after summary preparation. All Apple builds, Swift tests and real
Metal count/compaction tests pass; the restored Mac chat displays its count. See
[the report](../../../native/apple/COMPACTION-REPORT.md#context-usage-and-activity-status-2026-09-19).

## Inline summary presentation (2026-09-19)

Supersedes the summary panel above the transcript. The latest summary is now an
inline card before the turn that triggered compaction, only when visibility is
on. A separate optional display position persists with summary metadata; original
messages remain unchanged. Older summaries without this metadata appear after
the last covered turn. Earlier summary revisions are not archived.

Summary text streams through the native bridge as cumulative UTF-8 snapshots,
resetting for each compaction pass. The visible card follows generation. Pending
previews are never persisted and are discarded on cancellation/failure; the prior
saved summary survives. See the
[report](../../../native/apple/COMPACTION-REPORT.md#inline-streamed-summary-2026-09-19).

## Native speed baseline (2026-09-19)

A Release benchmark now calls the app's native Chat path directly, with the same
Q4_K_M model, profile system instruction, Mimir template, Metal/flash attention,
F16 KV, four threads and 8,192 context. After one warmup per case, three repeated
64-token outputs gave median first-text/streaming/total times of 0.44 s / 15.16
tokens/s / 4.59 s for a 102-token prefix and 7.47 s / 6.24 tokens/s / 17.64 s for a
1,617-token prefix. Short-prefix streaming ranged 5.46–41.97 tokens/s, so this is
not a stable optimal-throughput baseline. Outputs were identical per case.
Other desktop work remained active. The measurement excludes UI and compaction;
it establishes native latency but cannot quantify app overhead or explain the
variance. See [method and results](../../../native/apple/NATIVE-PERFORMANCE.md)
and [raw sample metrics](../../../native/apple/native-speed-results.json).


## Native speed rerun after competing Metal workload stopped (2026-09-19)

Superseded: using the initial native speed run as a baseline without GPU
competition. After the user stopped another Metal process, the identical benchmark
returned median streaming of 43.75 tokens/s (102-token prefix) and 36.63 tokens/s
(1,617-token prefix), respectively 2.89× and 5.87× faster. First-text medians were
0.26 and 3.85 seconds; longer-prefix first-text latency still ranged 3.14–7.97 s.
Outputs matched the previous run exactly. This supports contention as a major
contributor, without proving the remaining latency's cause. Both result sets are
preserved in the [native performance report](../../../native/apple/NATIVE-PERFORMANCE.md).

## Mac icon disappearance investigation (2026-09-19)

The reported missing icon was not reproduced after opening the current Mac app
by its full build path. The bundle contains AppIcon.icns/Assets.car and correct
CFBundleIconFile/CFBundleIconName entries. Both NSWorkspace's file icon and
NSRunningApplication's running-process icon returned the white Mimir head on red
background; exported images were visually inspected. The in-app sidebar and
assistant logos were visible as well. Direct Dock UI inspection timed out, so
this does not establish the prior cause or prove every Dock/cache state fixed.
No source workaround or system-wide icon cache reset was applied. LaunchServices
also retains the old mac-xcode build with the same bundle identifier; use
`logs/mimir-apple/macos/Release/MimirChat.app` for current development verification.

## Explicit running Dock icon (2026-09-19)

Supersedes the earlier icon lookup as sufficient verification: the user's Dock
screenshot still showed a generic icon despite correct NSWorkspace and
NSRunningApplication icon results. Those APIs therefore did not establish the
visible Dock tile's state. The Mac app delegate now explicitly assigns the
bundled AppIcon.icns to NSApp.applicationIconImage after launch. This targets the
running Dock tile without resetting global caches or changing iOS assets.
Mac Release build passes. Direct Dock UI automation remains unavailable, so the
visible Dock outcome still requires observation rather than another icon lookup.
