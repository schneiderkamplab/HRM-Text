# Empty-Rationale Technical Recovery

New isolated modules: `dfm12.compact_keep_rationale` and
`dfm12.compact_keep_recovery`. Shared reviewers, QA consumers and running pins
are unchanged. CPU preparation PID2924947 opens the source ledger read-only.

Prepared root: `data/dfm13/baltic/compact-empty-rationale-recovery-20261004-v1`.
Campaign: `data/dfm13/baltic/synthetic-compact-26b-20261004-v1`.

Only current production review failures completed>=1791078108 with complete raw
generation/review and exact keep/empty-issues/empty-reason qualify. Candidate
reassembly/native checks, original request contents, source/spec hashes, unchanged
deterministic gates and exclusive fingerprint ownership are verified. Prior-quality
holds are excluded. No rationale is fabricated. The private future validator
permits empty rationale only for clean keep; nonkeep still requires a reason.

## Parent-Coordinated Apply

1. Pause the handoff watcher and drain the controller. Apply acquires
   `controller.lock`, requires zero running jobs and zero active slots, and never
   signals clients or servers itself.
2. Make the watcher/completion proof use
   `dfm12.compact_keep_recovery.controller()` for the explicit migrated manifest.
   Its validator handles old strict keeps, future private-schema keeps, and
   receipt-backed recovered keeps by rechecking the original raw evidence.
   Do not bypass completion proof or edit the original failed review stage.
3. Write coordination JSON: absolute `root`, exact `prepared_manifest_sha256`,
   `watcher_paused:true`, `recovery_aware_handoff_ready:true`.
4. Run apply and migration while drained:

```bash
python -m dfm12.compact_keep_recovery --action apply \
  --output data/dfm13/baltic/compact-empty-rationale-recovery-20261004-v1 \
  --coordination <parent-coordination.json>
python -m dfm12.compact_keep_recovery --action migrate \
  --output data/dfm13/baltic/compact-empty-rationale-recovery-20261004-v1 \
  --coordination <parent-coordination.json>
python -m dfm12.compact_keep_recovery --action verify \
  --root data/dfm13/baltic/synthetic-compact-26b-20261004-v1
```

Each row transition and quota increment commit atomically, without changing
attempts/cursors or decrementing active slots. Original ledger outcomes are
archived in `compact_recoveries`; original raw/stage/request/outcome files remain
unchanged. Accepted artifacts preserve messages/tools/provenance. New outcomes
point to hash-bound recovery receipts. A crash before commit may leave an
uncredited accepted artifact; identical files are reusable, different ones fail.
Quota-full or fingerprint drift fails rather than overcredits.

Migration archives the old manifest/seal, pins the two new modules and updates
manifest/seal/ledger metadata under the controller lock. Filesystem and SQLite
sealing is not one transaction: keep the watcher paused until verification passes.
No automatic restart occurs. Re-arm watcher with the new pins and resume using:

```bash
python -u -m dfm12.compact_keep_recovery --action run \
  --root data/dfm13/baltic/synthetic-compact-26b-20261004-v1
```

Same128/server runtime settings. No semantic repair or NV promotion is included.
Nine focused tests,24 combined with shared-review regressions, passed.

## Applied and Resumed (2026-10-04)

The earlier preparation-only status is superseded: authorized apply credited all
13,093 rows, increasing accepted9,369 to22,462. Migration and verification passed.
`coordination.json`, `applied.json`, `migration.json`, and `runtime-launch.json`
in the prepared root record the handoff. Private runtime PID2936091 is detached
at128/server; log `logs/dfm13/baltic-private-empty-rationale-20261004-v1.log`.
First live check22,472 accepted/172 active. The migrated W4 factory validated an
actual recovered ledger row successfully. Original files and unrelated clients
remain untouched. Harvey/parent owns watcher re-arm using the new manifest pins;
no duplicate watcher was launched here.
