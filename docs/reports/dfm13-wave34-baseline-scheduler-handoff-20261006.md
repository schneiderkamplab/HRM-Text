# TODO3 Scheduler Handoff to Tesla and Parent

## Current Status: Corrected V2 Installed

On 2026-10-06, after refreshed semantic coverage pins and60 combined tests,
installed2,388 rows under PlanLock from
`data/dfm13/wave34-eval-baseline-20261006-v2/`. Its `installed.json` and
`post-install-validation.json` are authoritative. Training3200 unchanged and
RUNNING; all additions PENDING at verification. No GPU launch or W&B write.
Old teardown dependencies preserved; terminal barriers handle failures. DFM
templates match DaLA/GEC family and EuroEval templates match category, retaining
batch/concurrency/server settings. Tests cover failed-task cleanup and prevent
future training before fresh cleanup and required averages. Existing21 source
datasets unchanged; new13 LA averages use corrected semantic metric bindings.
This supersedes the withdrawn-v1 state below, whose artifacts remain intact.

## Current Status: Withdrawn Pending Semantic Fix

Later on 2026-10-06, parent identified that unconditional merge calls the
semantic helper without support for the new13 languages. Pending corrected
aliases, end-to-end tests and semantic population manifest, all2,388 newly
installed rows were withdrawn under PlanLock and the ten dependency changes
restored. Every removed row was PENDING with zero attempts. Live statuses and
training were preserved; no evaluation started. Receipt:
`data/dfm13/wave34-eval-baseline-20261006/withdrawn-pending-semantic-fix.json`.
The installation account below is historical, not current scheduling status.
Reinstallation must use a fresh preparation directory and corrected upstream
receipt; never replace the archived installation evidence.

Installed 2026-10-06 under PlanLock: 2,388 new rows and ten existing dependency
extensions. Current training3200 row remains byte-equivalent at the parsed-job
level and RUNNING; scheduler runtime and training commands were not changed.
No GPU launch, runner restart or W&B call. Fourteen focused tests passed.

Authoritative artifacts: `data/dfm13/wave34-eval-baseline-20261006/installed.json`,
`post-install-validation.json`, `plan-before-install.tsv`, `coverage-ready.json`
and `coverage-registry.json`. Coverage: 26 DaLA tasks (four shards each), 84
EuroEval datasets at3150K,3200K,...3600K,3641017. All new rows were PENDING
at post-install verification. The interface discussion below records preparation
history; dispatcher readiness is now satisfied by the isolated executable
`scripts/talemaader_v2_scheduler_sync` through the existing `python_bin` hook.
Only the new sync row records this bridge's source path/hash; training pins were
not modified. `sync --wait` handles the owner's locally available checkpoint
manifest and fails on `failed.json`; no missing historical results are fabricated.

Known provenance limitation: upstream EuroEval dataset revisions are recorded
in the pinned coverage registry, but the existing named-dataset runtime does
not itself enforce HF revisions. Do not describe that execution as revision-
enforced without a separate runtime check. Coverage/access preflight was passed.

## Dependency Contract

`train3200 -> Talemaader sync --wait -> new baseline3150 evals -> new complete
baseline averages AND baseline teardown -> wait/export3200 -> old+new eval3200
-> averages AND fresh teardown -> train3250`, repeated through epoch end.

3200 export deliberately serialized after baseline to avoid competing checkpoint
server lifecycles. Current train row stays exactly unchanged. Old job commands,
metadata and statuses stay unchanged; only unattempted future dependency edges
are extended. New future rows use `dfm13-xl-` prefix and correct checkpoint tags
so existing segment completion updates actual display epoch. VALEU is forbidden
in all new task inputs and is not cloned from historical campaigns.

The new average requires a distinct population ID and complete coverage, uses
the original DFM5 run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, and reads old
plus new result roots. Existing average populations are not overwritten.

## Tesla TODO2 Interface Required

Coverage registry JSON matches the existing multilingual extension structure:
`dfm` task list (`name,suite,config,language,shards,max_tokens`), `euroeval` task
list (`dataset,language,languages,category`), `headline_manifest` absolute path,
optional `euroeval_bin`. Lists contain NEW tasks only; duplicate existing names
fail closed. Distinct new population manifest may reference old+new metrics.

Readiness receipt must contain `status:passed`, `coverage_ready:true`,
`registry_sha256`, and `pins` mapping absolute actual config/population/dependency
paths to SHA256. Population parser is reused; all input hashes are checked under
PlanLock again immediately before any install. Coverage receipt must include
the real task/data preflight, not merely the scheduling mock tests.

## Talemaader TODO1 Interface Required

Reserved CPU REPORT row `dfm13-xl-wave34-talemaader-v2-sync` has
`report_kind:talemaader_v2_sync`, no GPU requirement, no automatic retries and
depends on the running3200 training row. Exact argv:
`/home/ucloud/miniforge3/envs/hrm/bin/python scripts/rejudge_talemaader_v2.py sync
--wait --output logs/rejudge_talemaader_v2` (absolute paths in metadata).

At inspection the script was not present. Also existing scheduler `run_report`
ignores `metadata.command` and always runs the comparison report. A narrowly
scoped `talemaader_v2_sync` dispatcher is required; installing a command-only
REPORT row now would NOT execute sync. Installer therefore refuses until script
and scoped dispatcher are present. No shared runtime edit was made. Parent must
coordinate this dispatch capability and whether the live runner imports it fresh;
do not restart or interrupt training merely to load new dispatch code. The sync
implementation must await/verify completion and preserve original run identity.

## Preparation and Installation

Implementation: `scripts/schedule_dfm13_wave34_baseline.py`.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m scripts.schedule_dfm13_wave34_baseline prepare \
  --registry /actual/tesla-coverage.json --readiness /actual/tesla-ready.json
# Report/review preview BEFORE installation; only after both interfaces are ready:
$PY -m scripts.schedule_dfm13_wave34_baseline install \
  --registry /actual/tesla-coverage.json --readiness /actual/tesla-ready.json
```

Control root: `data/dfm13/wave34-eval-baseline-20261006`.
Installer reloads current live rows under PlanLock; it does not install stale
preview statuses. It writes an exact backup/intent and then uses atomic plan IO.
It refuses attempted future evals, wrong run/tokenizer, duplicate coverage,
coverage drift, cycles/dangling edges and late installation after train3200.

Read-only real-plan graph smoke:10,892 existing rows; mock one-task coverage
produced10,981 rows across3150K,3200K,...,3600K,3641017. This is graph testing,
NOT ready coverage and NOT an installed preview. Future original lifecycle rows
were already `done`; these are preserved. New independent barriers/teardowns
cover all old+new evaluation work and gate subsequent training. Skipped existing
tasks remain skipped. No live plan files were written.
