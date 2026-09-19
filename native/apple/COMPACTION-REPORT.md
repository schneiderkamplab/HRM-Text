# Conversation compaction — 2026-09-19

Settings expose two independent, persisted controls:

- **Automatically summarize older turns** (default on).
- **Show compaction summary** (default off). When on, the saved summary appears in
  a selectable, scrollable panel above the transcript. Hiding it changes only UI.

Turning automatic compaction off sends the original full transcript, ignoring its
saved summary for inference. This may hit the context limit. The summary remains
saved so it can be inspected and reused after re-enabling compaction.

## Behavior and boundaries

The bridge uses the exact GGUF chat template and tokenizer to count the system
instruction, effective history, new prompt and reserved reply. Above 90% of the
context allocation it attempts to reduce usage toward 75%. It summarizes oldest
complete pairs in chunks that fit, incorporating an existing summary when present.
It prefers keeping two recent pairs verbatim, then one; it can summarize the last
old pair if that is required for the new prompt/reply to fit. Summary generation
uses the same local model and its own chat template with a budget of
`min(256, context / 8)` tokens. Summary text is reference material in an ordinary
user/assistant pair, never promoted to the system instruction.

Full original messages remain saved and displayed. A separate summary and covered
message count are committed atomically with the successful new answer. Stop or
failure rolls back that candidate memory as well as the partial answer. Invalid
saved coverage is rejected. No token/KV persistence or llama.cpp changes are needed.
The additional tokenizer/model ownership is released by the existing exit drain.

Summaries are lossy and may contain model errors. There is no retrieval over omitted
turns, and repetitive re-summarization may lose details. A very large individual
old pair that cannot fit the summarization prompt, or a new prompt/reply that cannot
fit even after summarizing, produces an actionable capacity error rather than
silently truncating original text. Increase context or reduce reply budget in that
case. Settings visibility does not affect the model's effective history.

## Evidence

- Mac, unsigned iOS and Simulator Release builds passed with Xcode 16.3; release
  toolchain/account work remains deferred at the user's request.
- Swift tests cover preserving original messages, summary persistence, reuse,
  cancellation rollback, off mode and both preferences across restart.
- Real Q4_K_M Metal bridge tests compact a 30-turn history inside a 1,024 context,
  continue from the resulting summary, reject over-capacity full history when off,
  and cancel during summarization without committing memory. Existing generation,
  history restore and shutdown tests pass.
- Live Mac test used two prompts containing 500 repetitions of `ord` to exceed a
  1,024-token allocation. The first turn specified Odense and vegetarian food.
  Compaction produced a visible summary retaining those facts and a new answer.
  Toggling visibility removed the panel while leaving the original transcript.
  The summary and visibility setting survived Cmd-Q and relaunch. Memory-based
  context/reply defaults were restored after the small-context test; summary
  visibility was left enabled for inspection.
- Cmd-Q on the loaded Mac app terminated its process without creating another
  MimirChat crash report (six reports before and after). This completes the earlier
  locked-screen check. Separate idle/loading/active-generation process-exit tests
  still pass with the additional codec ownership introduced here.

Reproduce automated tests after the normal Mac build:

```bash
native/apple/Tools/test-swift.sh
logs/mimir-apple/macos/Release/mimir-bridge-tests "$PWD/logs/mimir-review/mimir-q4_k_m.gguf"
for scenario in exit-idle exit-loading exit-active; do
  logs/mimir-apple/macos/Release/mimir-bridge-tests "$PWD/logs/mimir-review/mimir-q4_k_m.gguf" "$scenario"
done
```

See `validation.json` for final source and local log hashes. This small test set
establishes mechanics and cancellation, not broad summary-fidelity evaluation.


## Mac scrolling hang follow-up (2026-09-19)

The live app beach-balled while scrolling the long compaction-test transcript.
A three-second process sample placed all 1,747 main-thread samples in SwiftUI
layout/graph updates, including `SelectionOverlay.updateNSView`, alignment updates
and NSTextField font invalidation. CPU usage was approximately 99%. This implicates
the selectable-text layout path; it does not establish a general macOS defect.

Mac message bodies and the summary now share a read-only, selectable `NSTextView`
representable. It measures wrapped text at the proposed width and changes attributed
text only when content/font changes. iOS retains SwiftUI selectable text. The
model, compaction algorithm and saved conversations are unchanged.

The hung process was terminated and the rebuilt app reopened the same saved chat.
Six alternating three-page up/down scrolls with the summary visible remained
responsive. Answer and summary text selection/Command-C worked; narrowing and
restoring the window reflowed the transcript. A subsequent three-second sample
placed 2,594 of 2,598 main-thread samples waiting in the event loop; observed CPU
usage was 0.3%. Mac, iOS and Simulator Release builds and Swift tests passed.
This is a focused regression check on macOS 26.4.1, not exhaustive OS qualification.
Raw process samples stay local; their hashes are recorded in `validation.json`.

## Context usage and activity status (2026-09-19)

The header shows `Context used/limit`, using the loaded model's tokenizer and chat
template (including the system instruction). At rest it counts the effective
completed transcript: summary plus uncovered turns when compaction is enabled,
full transcript when disabled. During generation it shows the prepared input
count, then refreshes after completion or rollback. Unsent composer text, reserved
reply budget and an in-progress answer are excluded. The denominator is the
configured context, not a hard-coded training limit; an over-limit transcript is
reported honestly. Counts are recomputed off the UI thread on model load, chat
selection and compaction-setting changes. Stale callbacks cannot overwrite a
newer chat's count. Unavailable counts appear as a dash.

Both the header and pending-answer indicator say “DFM Mimir is compacting…” during
summarization, switching to “DFM Mimir is thinking…” when the final input is
prepared, before answer generation. The full transcript and saved summary format
are unchanged.

Validation: Mac/iOS/Simulator Release builds and Swift store tests passed. Real
Q4_K_M Metal tests cover a valid empty-conversation count, full versus compacted
history counts, and a prepared-input notification after summarization with a
positive count within the configured 1,024-token context. Existing generation,
cancellation and summary-reuse checks pass. Live Mac inspection confirmed the
counter on the restored conversation. Evidence hashes are in `validation.json`.
