# Arena Readiness Classification Handoff

Implemented in the existing `scripts/dfm13_arena_export_readiness.py`; no second
guard, export, admission, upload, server action or active repair change.

## Selection API

Keep `prepare(ledger, selection_path, output, manual_review, ...)` and
`enforce(receipt_path)`. Each selection entry contains `seq`, `kind` and
`candidate_sha256`. Kinds are:

| Kind | Ledger | Required proof |
| --- | --- | --- |
| `original` | Original audit `jobs` | Original completed keep, source file/row hashes and identity |
| `recovered` | Repair `accepted` | Unchanged source row, original technical failure, exactly one matching completed `retry_audit` keep |
| `repaired` | Repair `accepted` | Repair decision, completed correction, content-only target change, exactly one matching completed fresh re-audit keep |

Ordinary original keeps imported into a repair accepted table must still be
selected from their original audit ledger, not mislabeled as recovered.
The default kind remains `repaired` for the existing repair-only interface.

All paths check source file hashes, source identity/line and original audit row
hashes. Repair paths additionally verify the sealed plan/source lineage and
immutable input snapshot, accepted-record provenance, completed-stage request
hash/attempt identity/raw-response locator, and absence of conflicting final
dispositions. Repairs preserve the complete row except designated assistant
target content, including history, tools, target index and metadata.
These checks validate ledger evidence; they do not independently certify the
model's semantic judgment or replay the model.

Holds remain enforced by candidate hash OR ledger/seq OR source identity, on all
three paths. There are now eleven holds, including next-repair seq49 and seq89.
Their assessment paths are pinned too. A copied ledger does not waive holds;
it needs the corresponding sealed manifests/plan/input-snapshot context. Do not
invent an empty hold set or silently relabel a ledger lineage when taking snapshots.

## Terminal Review

New receipts use version `dfm13-repaired-export-readiness-v2`, report counts by
classification, and bind the selected ledger evidence hash. `enforce` rechecks
the evidence, pins, holds, source bytes and terminal state.

Nonterminal/locked roots return `terminal_review_required` unless already
blocked by a hold. Repairs require a matching completion receipt, disjoint
final tables covering all input rows, no inflight attempts and a released
controller lock. Original audit roots require all source jobs terminal and a
released lock. No result grants export/upload authorization.

Manual review receipts must bind exact `selection_sha256`, `holds_sha256` and
`assessment_sha256`, identify `reviewer`, and set `approved`, `terminal_review`
and `whole_target_reviewed` to true. Sample-based review is supported without
requiring manual gold for every row:

```json
{
  "review_scope": "sample",
  "sample_basis": {
    "method": "source-stratified sample, recorded in the bound assessment",
    "reviewed_count": 10,
    "population_count": 1000,
    "limitations": "Small sample; no population accuracy certification."
  }
}
```

Here `whole_target_reviewed` refers to full targets in the reviewed sample, not
an assertion that all1000 rows were manually labeled. Population count must
match the selection size. The receipt always records `quality_certified:false`.
Old readiness receipts must be regenerated because implementation/hold pins
changed; do not repin old approvals as if they covered the new evidence.

## Verification

45 focused tests passed: classification/guard31, repair driver7, technical
review-only recovery7. Coverage includes recovered-keep proof failures, source
identity/line/hash drift, modified history/tools, conflicting outcomes, holds,
sample-review scope and live-lock/terminal rejection.
Read-only actual next-ledger checks validated recovered seq21 and repaired seq49;
the latter is now blocked by its independent hold. Neither check approved output.

The live128/server repair clients were untouched. A separate proposed256/server
plan is prepared but not applied in main repair `migration-256-preparation-v1/`.
The live driver has no dynamic resizing or graceful-drain API; any future
owned-client interruption must preserve unknown attempts, release its lock,
archive ledger/plan/seal and refresh downstream pins before a single-writer resume.
The subsequently scheduled interruption watcher was cancelled before execution:
the original max3 accounting would exhaust an interrupted third attempt into
technical `needs_review`. A separately bounded infrastructure-recovery allowance
is required before any such migration. Main remains128/server; no active repair
client or server was signalled.
