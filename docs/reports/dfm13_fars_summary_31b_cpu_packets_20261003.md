# Held Fars summaries: CPU-only 31B packet preparation

## Gate interface for Jason / BalticQA ownership

Fars-specific gates live in `dfm12.wave_publication_holds`:
`publication_hold(component)` returns a status or None;
`require_publication_allowed(component)` raises before release I/O.
`wave_release.release` calls the latter. `advance_wave4_instructions` checks the
former before uploaded detection **and before process()**. The explicit constant
contains pn_sum and wiki_sum only. Do not silently extend that Fars constant:
`mark_registry()` deliberately requires its receipt's components to equal it.
Compose a separate Baltic gate/receipt in relevant Baltic publisher/controller
entry points, or explicitly generalize dispatch while retaining source-specific
receipt validation. PersianQA must remain outside this Fars hold.
No direct agent messaging interface was available; this is the shared handoff.

## Preparation contract

`dfm12.fars_summary_packets` snapshots accepted/accepted_repair ledgers with
read-only SQLite transactions, then independently snapshots held-source jobs
from the shared repair queue. Every completed generation is recorded, including
declined or structurally invalid corrections. Structurally valid corrected targets
not already present with the same parent/messages are staged for 31B review.
All nonassistant messages must match exactly; rendered token counts from the
old answer are removed rather than misrepresented as measurements of a repair.
Full ledger status/job links and queue payload/result/status/attempt/owner/lease
are preserved in the separate snapshot, not modified in production.

This is NOT an atomic cross-database snapshot and does not capture future job
completions. Logical deduplication handles already-materialized repair outputs.
New completions after this snapshot require another separately pinned delta;
finishing this packet batch cannot establish that all repairs were reviewed.
Generation `done`, audit `done`, and accepted ledger counts are distinct.

The first frozen population contains 77640 distinct targets: 58648 pn_sum and
18992 wiki_sum. This includes 3965 completed generation outputs absent from the
accepted-ledger candidate set (120 pn_sum, 3845 wiki_sum). Completed generations
were classified as 31981 already-materialized identical targets, 3965 additional
structurally valid candidates, 21766 protected-message/role changes, and 14189
declined corrections. These are structural classifications, not semantic verdicts.
The same queue snapshot retained 13723 pending and 257 running generations;
neither group is a reviewed target. Snapshot totals differ from the earlier
read-only recommendation below because workers continued normally.

The 3965 additional targets join back to ledger states as follows: 2867
repair_pending, 974 reaudit_pending, 120 repair_rejected and 4 excluded_unreviewed.
Thus not all are missing only ledger materialization, and **120 already carry
a prior rejection**. All retain their old state/job links in `ledger_snapshot`;
31B preparation does not overturn it. The packet staging label
`generated_unreviewed_26B` denotes a 26B-produced target awaiting this new 31B
review, not proof that no earlier 26B audit exists. Consumers must use the
preserved queue/ledger evidence rather than treating that label as audit history.

Packets include full final candidate and exact original Parquet row (including
upstream target, explicitly not gold), source file hash/index, content hashes,
and a 31B-only audit request. Full source prompt must match the canonical prompt.
The original converter preserved FarsInstruct's comprehensive-summary prompt;
there is no evidence justifying silently weakening it to headline generation.
Template mismatch is a distinct reviewer flag blocking keep; adaptation needs
source-semantic justification, versioning and separate approval.

Repair requests can only be constructed for a valid repair verdict without
prompt mismatch. Fresh re-audit uses the full corrected target/source in a new
context, with no earlier verdict/reason supplied. No repair or audit is executed
by this CPU preparer. All packets prohibit admission/publication. Tokenizer and
context preflight remain required against the actual pinned 31B model before
dispatch: full prompt plus 8192 output tokens, no silent truncation.
Full source here means the complete supplied upstream record. If that upstream
article is itself truncated, preparation cannot recover unseen original text.
Review must not pretend missing source content was inspected.

Run bounded resumable batches (single CPU process; maximum 10000 per call):

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.fars_summary_packets prepare \
  --root data/dfm13/wave4/fars-summary-31b-packets-v1 --limit 2000
```

Each call verifies sealed snapshot, source and implementation hashes. Work is
transactional in `packets.sqlite`; completed rows are skipped, errors are explicit
blocked records. A crash before a batch commit cannot create partial completed
rows. The initial population snapshot is full, while packet expansion is bounded.
All **77640 packets** are now CPU-prepared with **zero blocked records**:
58648 pn_sum and 18992 wiki_sum. `progress.json` reports zero remaining within
this frozen snapshot; all rows remain unreviewed by 31B. The completion receipt
`cpu-complete-receipt.json` seals the packet database separately from the input
snapshot/manifest. This is CPU packet completion, not live queue completion.
Focused packet/gate/Fars selection tests: 15 passed. No GPU or server changes.

## Unclaimed 26B generation: recommendation, not executed

**Superseded by subsequent explicit user authorization:** conditional deferral was
implemented, tested and executed. The original recommendation below is retained
as historical context; see the execution section following it.

Read-only snapshot at Unix time 1791041519 found 16852 pending held-source
generation jobs (16850 wiki_sum, 2 pn_sum), all attempts=0 and owner=NULL, plus
268 wiki_sum running. There were 68765 completed held-source generations and
33081 completed held-source audits; these totals are neither paired success
counts nor unique accepted examples. Queue activity continues after this reading.

Deferral can safely avoid waste if implemented as one short `BEGIN IMMEDIATE`
compare-and-set transaction against exact frozen job IDs/payload hashes, requiring
stage=generate, status=pending, attempts=0, owner IS NULL and no live lease.
Set status=deferred31B, retain the payload/row/counters and append an event plus
external receipt. `Queue.claim` selects only pending jobs, and lease recovery
touches only running jobs, so the new state is not implicitly reclaimed. Exclude
running jobs and retry-pending work; never delete rows or decrement attempts.
Races are resolved by the conditional UPDATE: jobs claimed first remain untouched.
Any later resume requires a deliberate policy, since ordinary process() does not
understand deferred31B as terminal. Other eligible audits/generations stay eligible.

**No live queue mutation or cancellation was performed.** The source-wide hold
currently skips ledger materialization and new re-audit scheduling, while existing
26B generation workers can still finish claimed/pending jobs. Queue terminal status
must not be described as completed quality review. Deferral requires owner
coordination before execution, as requested.

## Authorized Deferral Execution and 31B Readiness

`dfm12.fars_summary_deferral` proposed 10863 exact job/payload versions and
conditionally deferred **10659**. Another **204** were skipped after their claim
state changed. The transaction requires stage=generate, status=pending,
attempts=0, owner=NULL, an unchanged inactive lease and byte-identical payload
matching the proposal hash. It changes only status to `deferred31B`, appending
one authorization event per job. Payloads, results, errors, attempt counters and
existing events are retained. Running/unrelated jobs are never modified.

Receipt root: `data/dfm13/wave4/fars-summary-deferral-20261003-v1`.
`proposal.json` preserves complete original job rows; `receipt.json` distinguishes
applied and skipped IDs. Both are sealed. A committed event records proposal and
payload hashes so a crash before external receipt writing can be recovered
idempotently. These jobs are **unfinished31B**, never completed reviews.

The actual `wave4_gemma31_transition.readiness` now accepts an optional
`deferred31B_authorizations` mapping from exact database path to receipt directory.
All four proposal/receipt/seal paths must be hash-pinned in the handoff contract.
The queue path, exact ID set, payload hashes, untouched attempt/owner/lease fields
and matching authorization events are checked in a read transaction. Arbitrary
deferred jobs, pending jobs and running jobs still block readiness. Producer/client
freeze and all existing contract checks remain mandatory. Deferred counts remain
separate from done counts. `handoff-contract-fragment.json` supplies the new
fields only; it is NOT a complete handoff authorization or producer-freeze claim.

The transition module is stable with the scoped check; Tesla was notified to
prepare new comparison roots. Old prepared comparison manifests/pins were not
edited. Tests across deferral, packets, preflight, transition and publication
gates: **25 passed**.

## Completion Delta and Actual Tokenizer Preflight

`data/dfm13/wave4/fars-summary-31b-delta-v1` holds **11656** additional packets:
10659 authorized deferred originals and 997 structurally valid corrections
completed after the old snapshot. Zero packet preparation errors. The inventory
also preserves 1631 declined corrections, 685 protected-message changes, three
new terminal failures and three changed nonterminal states. At delta snapshot
time five held generation jobs overall were still nonterminal; later observation
found three running on attempts 2-4 after prior length failures. These were not
eligible for never-claimed deferral and remain untouched. Their final outcomes
need another delta; do not infer complete coverage from the packet count.

`dfm12.fars_summary_handoff` does not send requests. Its delta preserves old roots,
job payloads/results and hashes, deduplicating targets against the original
snapshot. A later delta made against that same original snapshot **supersedes**
this delta; do not concatenate both without content deduplication.

Actual CPU tokenization completed for all **89296** audit requests using verified
`google/gemma-4-31B-it` snapshot
`842da3794eaa0b77d5f08bae87a17459d91ff475`, original native template,
`enable_thinking=True`, and `fix_mistral_regex=False`. All fit a planned **32768**
token context including **8192** reserved output tokens, with zero errors,
oversized requests or truncations. Four CPU workers per preparation process
were used; at most eight across the two simultaneous batches.

Sealed results are in `fars-summary-31b-preflight-v1` and
`fars-summary-31b-delta-preflight-v1` beneath `data/dfm13/wave4/`.
Live endpoint model/context still must be verified before dispatch. Future
corrections and fresh re-audits require their own content-specific measurements.
No 31B semantic review, GPU request, server stop, export or hold clearance occurred.
`execution-verification.json` records final observation and artifact references.
At the final verification (Unix time 1791042894), only one held generation job
remained running: `373cc6ba4631ea32a1a5f907ca0446322a966d542e169c2682ba5bab4614bae8`,
attempt 3. It remains a legitimate nonterminal blocker, not an authorized deferral.
Maximum measured prompt-plus-output totals were 11696 (original) and 10860
(delta), below the planned context limit.
