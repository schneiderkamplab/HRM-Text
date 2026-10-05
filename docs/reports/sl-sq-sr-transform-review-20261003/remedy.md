# Exact four-ID remedy and assembly handoff

2026-10-03. Explicit authorization covers cases 1, 14, 18 and 28 only.
Cases 12 and 19 remain observations, not exclusion rules.

## Publication race handled without mutation

The new `dfm12.wave_manual_exclusion` helper uses the same nonblocking component
`.lock` as `wave_repair.process` and `wave_release.release`. It checks publication
receipts, export directories (including partial exports), registry entries and
publication-state flags. Exact candidate/model-review hashes must match the frozen
review. Its SQLite decision insert and distinct `excluded_manual_review` status
transition are transactional; decisions preserve original record/review strings,
prior status, reasons and review pins. SQL triggers disallow decision updates or
deletions. Atomic count refresh matches `process` completion rules. A crash after
commit but before status refresh leaves a counts mismatch that prevents export;
an idempotent rerun recovers. Locks and all records are checked before mutation.

Both attempted live invocations refused on held component locks. SL publication
then completed, followed by SQ publication. **Zero prepublication mutations were
applied.** Published ledgers, original export files and historical publication
receipts are retained unchanged. The helper is not used to retroactively change
published quality statuses.

## Same-repository successors

Implementation: `dfm12.reviewed_transform_subset`, policy
`sl_sq_reviewed_exact4_v1`, reusing FA/HR tokenization, upload, remote verification
and locked registry promotion. Four temporary entry-level `quality_hold` fields
were installed under the registry lock before correction; no complete component
or language was held. `quality-hold.json` preserves the exact review authorization.

Root: `exports_dfm13/sl-sq-exact4-subsets-20261003-v1/`.
Each `<language>-<task>/<task>/` package includes original parent entry/publication,
source card, frozen review, an exclusion record containing both original
pre-admission and attributed published messages plus model review, and an exact
byte-subset receipt. The mapping permits only the publisher's known attribution
and admission metadata additions, not content changes. All retained lines remain
byte-identical and in original order. Source licensing and attribution are carried
forward in full. No broad regex or additional IDs are admitted to this remedy.

| Entry | Historical rows | Removed | Retained |
| --- | ---: | ---: | ---: |
| SL prefix-continuation | 60,100 | 1 | 60,099 |
| SL paragraph-reordering | 31,015 | 1 | 31,014 |
| SQ prefix-continuation | 24,997 | 1 | 24,996 |
| SQ paragraph-reordering | 22,930 | 1 | 22,929 |

New arrays use `data/dfm13/tokenized_sl_sq_exact4_subsets/<name>/<content-hash>/`;
historical arrays are never overwritten. The existing 16-worker CPU tokenizer
checks zero skipped rows and materialized lengths. Uploads use the exact parent
commit as a compare-and-swap guard and verify every attachment at the new revision.
The assembler has a scoped adapter preserving ordinary source/token checks.
Only after those checks does locked registry promotion clear that entry's own
temporary hold. Concurrent unrelated registry edits fail promotion rather than
being overwritten.

`wave_release.release` now refuses only SL/SQ prefix/reordering pairs, preventing
an old finalizer from overwriting canonical successor revisions. Denoising,
span-filling and other languages retain their existing publication behavior.

## Main/Poincare handoff

Use the successor entries from the live registry only after their scoped hold is
cleared. Old assembly/certification snapshots remain historical for these four
entries; reverify current revisions and new token roots. Unaffected SL denoising
certification is not invalidated by this scoped change. No direct agent-message
tool is available here; this report and the turn updates are the main-thread
coordination handoff, not a claim of a separately acknowledged message.

The authoritative final result is `verified-handoff.json` in the package root,
produced by the read-only `verify-successors.py` beside this report after all four
completion receipts exist. It includes remote revisions, exact counts/tokens,
attachment counts, historical preservation checks and completion hashes.

## Tests

127 tests passed: new prepublication and successor tests plus existing FA/HR
subset, assembler, wave-release and tokenizer suites. Tests include exact-ID
scope, source/export hash mapping, append-only decisions, lock/publication
refusal, rollback, crash recovery, idempotency, duplicate/missing IDs, retained
byte identity, old-finalizer protection, and unaffected-task behavior.

No GPU, training, audit-worker or frozen-production process actions were taken.

## Completed verification

All four are `accepted_uploaded`, assembler-verified and promoted; all four
temporary entry holds are cleared. Total: **139,038 retained rows and
135,872,404 tokenized tokens**, four excluded rows, zero tokenizer skips.
Twelve remote attachments per repository were verified (48 total).

| Entry | New revision | Tokenized tokens |
| --- | --- | ---: |
| SL prefix | `7b767d9ff5d5cd3144fad28edacfa188f8a1caaa` | 40,355,159 |
| SL reordering | `e8e48430ab8eadd7e3141fad477a4b06f2844690` | 42,924,776 |
| SQ prefix | `62e7c59bcc7774e266638e87cf65bcceee3bc0e8` | 18,115,633 |
| SQ reordering | `858b2ceedbd89bc90a822d04a0d66eb734841a2a` | 34,476,836 |

`verified-handoff.json` SHA256:
`17849fb5af37777c5ff062fe2592118bef643d22f39bab36742c8ce3d79cc123`.
Final proof confirms historical data hashes and original ledger record/review
hashes unchanged; historical ledger statuses remain accepted. The 150 historical
array files still exist in distinct old roots. Their legacy receipts have no
array hashes, so the proof does **not** claim before/after array-hash equality;
the correction never wrote those paths. New arrays have complete verified hashes.

The separately authorized read-only Serbian follow-up is now complete:
[16-case report](sr-followup/report.md). Five exact source-window/extraction/task
defects are observations only, with no added exclusions or holds. This completes
48 independently read examples across the three languages without altering the
frozen original 32-row report or expanding the four-ID remedy.
