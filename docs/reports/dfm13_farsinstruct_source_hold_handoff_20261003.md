# FarsInstruct source-wide publication hold handoff

User authorization supersedes the earlier seven-row-only publication recommendation:
hold all pn_sum and wiki_sum, original and repaired, pending independent 31B
full-source fidelity audit and comprehensive-summary prompt-adaptation review.
PersianQA is not held based on the four clean sampled answers.

## Poincare / controller ownership handoff

Only these localized changes were made to `scripts/advance_wave4_instructions.py`:
import `publication_hold`, then check it immediately after deriving `component`
and before `publication.json`'s uploaded fast path. Held components are recorded
as `quality_hold_source_fidelity` and skipped. No SQL/connection closing or other
controller logic was edited. Preserve this gate when integrating SQL closing work.
No direct agent messaging interface was available; this file records the handoff.

`dfm12.wave_release.release` independently calls `require_publication_allowed`
before any release I/O. Both guards use an explicit two-component constant and
cannot be cleared by deleting/modifying a receipt. Releasing the hold requires
reviewed code/policy clearance with new evidence, not merely an old model keep.

`dfm12.wave_publication_holds.mark_registry` uses the existing registry lock and
atomic writer; it marks existing affected uploads while preserving repeat,
counts, output paths/hashes and revisions. None existed at enforcement time, so
no registry content change was needed. Existing local files remain untouched.

Controller 2293017 was idle, command/cwd/starttime verified and instruction locks
acquired before SIGTERM. Its controller lock was confirmed released before the
identical detached command/environment was started as PID 2365731. The new cycle
reports both holds and continues unrelated instruction components. GPU workers
were neither signaled nor restarted. An initial broad lock probe encountered an
unrelated held lock and aborted without signaling; the successful check scoped
locks to instruction components only. The first pidfd attempt was unsupported
and also sent no signal.

Evidence and restart receipts: `data/dfm13/wave4/publication-holds/`.
Log: `logs/dfm13/wave4/advance-instructions.log`.
Focused gate tests cover missing receipt fail-closed, direct release before I/O,
already-uploaded controller bypass prevention, registry field preservation and
idempotence, and unaffected PersianQA/other components.
