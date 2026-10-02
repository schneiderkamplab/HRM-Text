# Per-Dataset Repair And Export Handoff

## Final Release Update

Supersedes the earlier tail estimates and manual-review authorization gate below.
Main is terminal:174236 accepted candidates,28121 rejected,2885 needs_review.
Arena55k final:30452 accepted,8753 rejected,266 needs_review,0 unfinished.
All eight datasets have completed auditing/repairs. No main restart occurred.

User explicitly authorized filtered export/upload, replacement of prior unaudited
repositories and DFM13 integration, without requiring manual review of every row.
This is release authorization with known automated-review limitations, not a
claim of certified correctness. Existing historical readiness receipts retain
their earlier manual_quality_review_required label; do not falsify them.
The separate `scripts/dfm13_arena_authorized_release.py` validator recognizes
the explicit authorization while reusing all hold/hash/lineage/terminal checks.

Release record: `docs/reports/dfm13_arena_user_authorized_release_20261001.json`.
Full-validation receipt has suffix `_validation.json` when recheck completes.
Export owner should call `validate_release(path)` before packaging and recheck
pins before upload; any new hold invalidates this release's pinned evidence.

| Dataset | Final hold-filtered rows |
|---|---:|
|AI-ArenaEN|2339|
|Arena100k|52662|
|Arena140k|88774|
|Arena55k|30452|
|ComparIA|399|
|HelpSteer3 edit|6321|
|HelpSteer3 preference|16877|
|Expert5k|1883|
|Total|199707|

Main selections:174227 (155883 original,1773 recovered,16571 repaired), excluding
all9 current main holds. Next:25480, excluding its2 holds. Rejected/unresolved
rows and Recovery100 diagnostic are excluded. No audit ledger changed.
Main paths: `logs/arena_audit/20261001-repairs-followup-v1/terminal-filtered-readiness-v1`.
Next paths remain below; use its repaired-unheld selection.

Audit/repair ETA is now zero: done. CPU selection preparation is complete;
export/upload and integration execution belong to Poincare/parent and are not
launched by this worker. No evidence-based transfer ETA exists until that owner
starts packaging/upload and measures throughput. Do not present this handoff
as an already completed or scheduled upload.

2026-10-01, snapshots around17908509xx. Counts exclude RepoChat/Search.
Accepted means automated candidate, not certified correct. User now requests
filtered export/upload; this report does not pretend those operations are queued.
Parent coordinates export owner Poincare. No active client or server changed.

| Root/source index | Dataset | Total | Accepted candidates | Rejected | Needs review | Unfinished | Held accepted | Unheld candidates |
|---|---|---:|---:|---:|---:|---:|---:|---:|
|main/0|AI-ArenaEN|2602|2341|224|37|0|2|2339|
|main/1|Arena100k|64939|52668|11401|870|0|6|52662|
|main/2|Arena140k|98230|88775|7743|1712|0|1|88774|
|main/3|Arena55k|39471|30441|8752|225|53|0|30441|
|next/0|ComparIA|460|401|50|9|0|2|399|
|next/1|HelpSteer3 edit|7909|6321|1461|127|0|0|6321|
|next/2|HelpSteer3 preference|21377|16877|4274|226|0|0|16877|
|next/3|Expert5k|2243|1883|280|80|0|0|1883|

First three main datasets are final at the row level; Arena55k remains a moving
tail snapshot. Main classes for completed sources (original/recovered/repaired):
AI-ArenaEN2094/57/190; Arena100k45812/728/6128;
Arena140k82382/784/5609. Next classes21629/483/3370 are fully final.

## ETA And Gates

- Audit/repair done for seven datasets. Arena55k estimated5-15minutes at this
  snapshot, not a guarantee:600second timeouts and remaining bounded retries can
  extend the tail. Bookkeeping queues are empty; only ongoing stages remain.
- Existing main export-readiness guard is root-wide, so even the three completed
  datasets currently await the main controller lock/completion receipt. No
  untested source-local gate bypass is being introduced.
- Next is terminal and unlocked. Its25482 candidates have passed hash/lineage
  checks; excluding ComparIA seq49/89 leaves25480. Original and recovered
  selections are unchanged. The new3368-row repaired-unheld selection also
  passes checks with zero hold findings.
- Next receipts remain manual_quality_review_required. Export owner must bind
  the selection/holds/assessment to an explicit terminal review receipt, recording
  actual sample basis and known limitations, not asserting per-row human gold.
  User export/upload authorization does not silently fabricate that evidence.
- No upload client has been launched by this worker. End-to-end export/upload
  completion ETA is not measured or promised: it depends on owner scheduling,
  filtered artifact packaging, destination and observed transfer throughput.
  Audit completion estimates above must not be presented as upload ETAs.

## Paths For Poincare

- Main: `logs/arena_audit/20261001-repairs-followup-v1`.
- Next: `logs/arena_audit/20261001-pending-next-repairs-v1`.
- Next selections, hashes and readiness receipts:
  `logs/arena_audit/20261001-pending-next-repairs-v1/terminal-readiness-snapshot-v1`.
  Use `original-selection.json`, `recovered-selection.json`, and
  **`repaired-unheld-selection.json`**, not the held full repaired selection.
- Repaired-unheld evidence SHA256:
  `e3da91b9f214726969ad4d1e14062b8e52eb6ade4c09cca3498fcc2eaacf63a0`.
- Mandatory holds: `docs/reports/dfm13_bulk_repair_independent_holds_20261001.json`.
  Enforce by candidate hash, source identity and ledger/seq as the guard does.
- Main terminal observer output will be under
  `terminal-finalization-observer-v1/terminal-summary.json`; no export is triggered.
- Recovery100 diagnostic is excluded from this handoff, has no admission/export
  authorization, and is not being scaled after the weak semantic spot-check.
