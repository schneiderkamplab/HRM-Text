# TODO5 Scheduler Interface

## Current Future-Row Installation

Ten future-only Talemaader successor averages are now installed via
`scripts/schedule_todo5_future_averages.py`; receipt under
`data/dfm13/todo5-future-averages-20261006/installed.json`. No historical writer
was installed; parent already synchronized raw67+average67 and applied five
historical workspace panels. Existing TODO3 raw sync is idempotent against its
receipt. All new successor averages depend transitively on native Talemaader
merge, use strict DaLA plus v2 grade, and gate subsequent training. Twenty
scheduler tests passed. Current3154500 resume row unchanged; scheduler stopped.
Await separate expanded Danish/English/DFM-suite version handoff from Poincare.
Older blocked-installer notes below are history; do not execute the combined
historical-sync installer now that history has already been synchronized.

## Logging Decision Hold

Parent explicitly stopped historical-sync installation pending the user's
logging-only-fix versus defer decision. No TODO5 rows have been installed.
The correct finalized payload is now `prepared-future-compatible-v2.json`,
whose67-point input hashes validate; earlier stale-payload blockers are resolved.
The existing TODO3 Talemaader sync row still points to its historical writer;
parent requested waiting briefly before altering the plan. It must be replaced
or safely gated before reaching3200 if history appends remain disallowed.

Prepared local alternative: executable `scripts/talemaader_v2_local_publish.py`
validates completion/manifest/rows/point/sample bindings, refuses conflicting
sidecars and writes only `merged_metrics_v2.json` plus `local-published.json`.
No W&B import/call or `synced.json` write in that path. Seven local-publish and
TODO5 scheduler tests pass. This can replace the pending sync row's executable
without breaking baseline dependencies; not applied while user decision pending.
Future successor wrapper `scripts/todo5_future_average` additionally requires
finite strict DaLA before existing v2 logger dispatch. No shared logger edits.

## Latest CPU Verification

Workspace commands are now implemented in the pending installer, not a manual
future TODO: historical remote67-point verification -> fresh prepare -> apply
after backfill sync; population remote complete3150 verification -> fresh
prepare -> apply after baseline averages. CPU REPORT bridges are
`todo5_workspace_historical` and `todo5_workspace_populations`; source/mapping
pins are recorded per row. Baseline waits for historical patch, WAIT3200 waits
for population patch. No other layout or history changes. Twenty-three
scheduler tests pass including mocked workspace command order. Installation
still awaits Poincare's strict-DaLA future guard and regenerated payload pins;
latest validation continues to reject stale logger hash.

Future-logger review: opt-in Talemaader namespaces now discover exactly one
valid checkpoint-matched v2 sidecar. Before scheduling, require a finite strict
DaLA metric in the future logger too: `talemaader_only` intentionally permits
available-metric historical averages and currently does not enforce strict
DaLA presence. Keep that historical policy intact; apply the guard specifically
to future collection. Legacy rows must stay explicitly legacy and warn if the
old idiom grade is absent, never act as the successor/replacement series.
Estimated scheduler completion is5-10 minutes after the owner's logger guard
and final regenerated payload are ready; no training changes authorized here.

Scheduler adapter now implemented: `scripts/schedule_todo5_average_sync.py`.
Twenty scheduler tests pass, covering ordering, unchanged training/cleanup and
failed-sync blocking baseline. Installation command after payload refresh:
`/home/ucloud/miniforge3/envs/hrm/bin/python scripts/schedule_todo5_average_sync.py install`.
Uses the finalized `averages/prepared-talemaader-only-v2.json` path, validates
all67 points/input hashes, and pins its own bridge, implementation and payload.
**Not installed:** validation detected stale input hash for
`scripts/log_dfm5_headline_averages.py`. Poincare must regenerate the prepared
payload after logger changes settle; do not patch the hash to bypass validation.
Future logger command and explicit-step/high-water resolution remain separate
pending handoffs. No training row or runtime was changed.

Later update: deferred sync now exists. Exact CLI (run from repo root):
`/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.prepare_talemaader_v2_averages --sync-prepared <final-payload.json> --paused-step 3200000`.
It validates payload/input hashes, all rejudge sidecars, original run identity,
and absence of a training process; lock/intent/receipt protect against replay.
An uncertain prior attempt requires inspection rather than automatic retry.
Rejudging `completed.json` exists. Combined tests now35 passed. Still await
Poincare's finalized payload path/hash and future-version collection mapping;
do not install a guessed payload or mutate the installed Talemaader bridge.
The earlier missing-sync-CLI blocker below is superseded.

Sync records W&B's final internal step. Parent must check this high-water mark
against resumed training's explicit steps; preserving the training row does
not justify ignoring that writer-ordering constraint. No sync was executed.

`scripts/prepare_talemaader_v2_averages.py` now exists; combined preparation and
scheduler tests pass (27). It is explicitly preparation-only: it writes hashed
rows/coverage and does not implement a W&B sync CLI. Its new scalar namespaces
are `headline_avg_semantic_v2` and `suite_avg_semantic_v2`. Await the owner's
deferred sync executable and future collection mapping before installing the
additional gate. Its default population manifest includes the new13; historical
output therefore must retain missing coverage rather than publish complete34-
language scores. No new13 backfill is implied by preparing these coverage rows.

Read-only live check: train3200 RUNNING, entire training row identical to the
TODO3 v2 pre-install backup; all2,388 TODO3 additions and sync are PENDING.
No plan edits or W&B calls during this continuation.

Preparation only; no TODO5 plan changes or W&B calls made. The corrected TODO3
schedule remains installed. Scheduler owner awaits Poincare's versioned-average
command and artifacts; Boole owns workspace3fvncok3gjh inspection.

## Required Ordering

`train3200 -> Talemaader v2 sync -> historical average backfill sync -> new
3150 baseline evaluations/averages/cleanup ->3200 evaluations/averages/cleanup
-> next training`.

Backfill considers the67 historical checkpoints but uses only metrics actually
available at each checkpoint, recording coverage/counts rather than inventing
new13 results. The34-language populations become valid only at the new3150
baseline and later. Missing prerequisites or fatal backfill errors must not
produce a successful sync receipt. No concurrent training/W&B history writer.

## Handoff Needed From Poincare

- Exact CPU sync argv, output path, completion/failure receipt semantics and
  original DFM5 run identity; waiting must detect terminal failure.
- Versioned metric namespaces and population manifests with hashes, including
  mapping for each affected future average row. No silent historical redefinition.
- Available-metric denominator/coverage records for historical points, without
  requiring unavailable new13 metrics or claiming complete34-language history.
- Future collection CLI compatibility with the scheduler's existing AVERAGE
  dispatch, or a dedicated executable bridge without a live runtime restart.

At3200K there are five pending average rows: `headline_avg_v3` (atomic v3),
the20260930 multilingual manifest, semantic-v1 multilingual manifest,
`headline_avg_semantic_v1` plus `suite_avg_semantic_v1`, and the new DFM13
multilingual manifest. Equivalent rows continue through final3641017.
Preserve old namespaces if retained intentionally; only new namespaces adopt
new definitions. Change affected pending average metadata under PlanLock only
after an explicit mapping is available. Keep current training row and pins
identical, reread live statuses under lock, archive before/after receipts, and
test that sync failure blocks baseline and training while terminal cleanup
continues to run.

The extra CPU sync will use a new scoped bridge through the existing REPORT
`python_bin` hook if needed. Do not modify the already-installed Talemaader
bridge or its source hash. No guessed executable or placeholder row is installed.
