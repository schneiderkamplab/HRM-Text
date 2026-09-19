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
