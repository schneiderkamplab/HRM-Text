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
