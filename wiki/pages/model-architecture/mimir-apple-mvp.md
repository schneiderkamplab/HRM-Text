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
