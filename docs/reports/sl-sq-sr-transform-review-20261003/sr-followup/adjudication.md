# Serbian exact-case adjudication and applied proof

2026-10-03. Main independently read all five flagged full conversations and
selected **cases 32, 36, 37 and 47 only** for exclusion under the user's broad
quality-review task. This is a main-agent case judgment, not a claim that the
user personally adjudicated these four conversations. The unused SL/SQ
prepublication helper's event authority wording was corrected accordingly;
frozen SL/SQ reviews, exports, pins and receipts were not rewritten.

## Scope superseding the earlier findings

The original `report.md`, `review.json` and `receipt.json` remain frozen as
observations made before adjudication. Their five-case finding list is **not**
an exclusion allowlist.

- Case 32: English external-link titles/categories without native prose.
- Case 36: external-link blocks/category, no prose paragraph reordering.
- Case 37: a single substantive paragraph plus references/categories.
- Case 47: empty headings followed by bibliography/categories, no settlement prose.
- **Case 45 retained:** meaningful Serbian introduction, cast table and coherent
  gap answer. Wiki-table markers and an empty plot heading alone are insufficient
  grounds for exclusion. This supersedes the earlier implied exclusion remedy
  for that case, not the observation that raw markers are present.

No regex, language-wide rule, source-wide hold or additional case exclusion was
introduced. Meaningful tables/lists are not categorically rejected.

## Applied prepublication

`python -m dfm12.sr_manual_exclusion` succeeded while SR had no publication receipt,
export directory or registry entry. It acquired the same component `.lock` as
process/release and rechecked publication state before mutation. It invokes the
tested transactional helper with a separate hash-pinned SR decision loader.

Exactly four ledger statuses changed from `accepted` to
`excluded_manual_review`. Four append-only SQLite decision rows preserve the
exact original record/model-review strings, prior status, candidate/review hashes,
manual reasons, authority and frozen review pins. No model rejection was
manufactured and no input/target content was changed. Existing publisher selection
of accepted statuses excludes these rows when SR eventually releases.

Counts after application and an idempotent second invocation:

| Status | Rows |
| --- | ---: |
| accepted | 254,271 |
| excluded_manual_review | 4 |
| audit_retry_pending | 22 |
| excluded_unreviewed | 1 |
| rejected | 37,018 |

Total remains 291,316. `terminal=false`, `export_ready=false`; pending audit work
was neither cancelled nor relabeled. Case 45 and all other 12 nonexcluded rows
in the 16-case sample remain accepted.

## Actual proof and tests

[manual-exclusion-proof.json](manual-exclusion-proof.json) freezes all four
decisions and checked counts, verifies all 16 original records/model reviews
unchanged, and records case45 retention. SHA256:
`ea8ef4a198d392e9dc21c28e45f44d91e1aa6d2b098aa8e031916b1b0274f0c6`.

Prior SL/SQ handoff remains at SHA256
`17849fb5af37777c5ff062fe2592118bef643d22f39bab36742c8ce3d79cc123`.
No old artifacts were repinned. Component-lock protection also covered proof
capture; the proof records publication absence at that moment, not forever.

Tests cover exact four-ID selection, explicit case45 retention, unchanged record
and model-review strings, append-only decisions, idempotency, pending readiness,
publication/export/lock refusal, and frozen review pins. The full affected suite
passes 132 tests. No GPU, worker, training, scheduler or publication actions were
taken for this prepublication remedy.
