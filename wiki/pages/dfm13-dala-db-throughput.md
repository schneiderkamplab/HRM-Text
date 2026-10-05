---
type: Runbook
title: DaLA Audit SQLite Throughput
description: Deployed bounded memory and batched SQL optimization preserving audit policies and leases.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, dala, sqlite, performance]
---
# Deployed and Progress Verified

**2026-10-04 deployment supersedes the not-deployed preparation state below.**
After explicit user approval, only owned client PID2883484 received SIGTERM.
It gracefully drained to zero running jobs and exited. Code and predecessor
config pins were reverified, then the same DB resumed detached as PID3067757,
concurrency384, cache16384MiB, requested mmap16GiB, status interval60seconds.
No servers, unrelated processes, finalizer or assembly were changed.

Effective cache is16GiB. **Effective mmap is2,147,418,112 bytes**, just below2GiB,
because this SQLite build reports `MAX_MMAP_SIZE=0x7fff0000`. No rebuild is needed
or performed. The runtime receipt records requested versus effective settings.
The new config hash is
`e4946a1cb801c7693928d286e1225f4aba92b4aae348bc1e312bc3129cd6dc53`.

Verified done jobs increased31,552,624 ->31,599,508 (**46,884 new completions**).
Claims, source ingestion and result commits are active. This verifies progress,
not an end-to-end speedup claim. See the
[deployment receipt](../../docs/reports/dala-db-throughput-20261004/deployed.json),
and the audit root's `db-upgrade-launch-20261004.json`, `database-runtime.json`,
`resume-db-upgrade-20261004.log`. The code/adapter hashes remain as reviewed.

## Preserved Predeployment Evidence

User authorized a scoped optimization of `scripts/audit_dala_v2_batches.py`.
Main client PID2883484 was left running. No GPU jobs, live DB mutations,
finalizer or assembly changes. Parent owns the explicit code-pin upgrade.
The [upgrade receipt](../../docs/reports/dala-db-throughput-20261004/upgrade.json)
records code/config pins, tests and a live read-only measurement.

## Changes

- Writer cache/mmap are configurable; defaults preserve512MiB/2GiB. Proposed
  settings are16GiB each. The guard reserves75% of effective available memory,
  considering both host MemAvailable and finite cgroup limit minus usage.
  Startup records requested and effective SQLite pragmas in database-runtime.json.
- Reporting scans the covering status index, not the wide jobs table for every
  completed owner. Endpoint completion counts are explicitly null/not-collected,
  not zero. Source/job counts remain exact within a read transaction. Interval
  defaults to60seconds; final/drained reports use the same cheap query.
- Claim and finish update batches use executemany, preserving exact attempt,
  owner, status, expiry and1800-second lease predicates. Error escaping/result
  serialization remain unchanged. No valid negative/uncertain decision is reset.
- Source inserts use executemany in one transaction for aliases, records,
  quarantine and cursor. Duplicate-source counters retain their original meaning;
  cursor advancement cannot leave aliases behind or vice versa.

29 focused tests pass, including existing adapter/finalizer tests plus old/new
SQLite equivalence for claims, expiry/exhaustion, stale owners, duplicates,
rollback, Unicode errors, query plans and memory guard. Existing shared
`dfm12.audit_full.Database` was NOT edited.

## Observed Benefit and Remaining Work

One live read-only indexed status query took17.24seconds. The prior runner
recorded113.79seconds maximum for the old owner aggregate, averaging roughly
57seconds across286 reads. This is not a controlled benchmark or a claimed
end-to-end throughput multiplier. Even the status index has31million entries;
the lower reporting frequency avoids repeatedly competing with writes.

At measurement:31,175,202 done,224,044 failed,194,109 pending,84,960 running;
31,678,315 source rows loaded,60 sources ingested,35,211,311 total baseline rows.
About3.81million rows lacked terminal decisions (~11% of scope), including
unloaded rows. A short controlled drain/upgrade may help, but do not restart if
the parent finds remaining work too small to repay drain/startup cost.

## Approved Upgrade Procedure

The command below was subsequently launched with explicit approval as recorded
above. For future upgrades, first drain only the owned audit client; do not
stop shared servers. Recheck the config hash after drain and require the reviewed
runner hash. Keep the same output DB and immutable review adapter/prompt. Example
arguments (launch detached with the existing parent-owned log/receipt procedure):

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.audit_dala_v2_batches \
  --manifest data/dfm13/dala-v2-audit34/manifest.json \
  --output data/dfm13/dala-v2-baseline-batch-audit-20261004-v1 \
  --concurrency 384 --db-cache-mib 16384 --db-mmap-gib 16 \
  --status-interval 60 \
  --extend-from-config-sha 27f7e0dd21569c6eb88796442b835b272833f79cdf798532316326fa4ec28743
```

Do not use upgrade-local-ids for this optimization: adapter semantics did not
change. The explicit predecessor config hash gates the runner/settings change.
Check database-runtime.json for SQLite's effective mmap ceiling after startup;
the platform may cap it below the request. Cache/mmap ceilings are not eager RAM
allocations and do not alter GPU memory.

## Why Not Eight Databases Now

SQLite still has one writer per DB; eight independent ledgers could parallelize
write ownership on a future campaign. Splitting the current35million-row ledger
would require migrating dedup identities, aliases, cursors, leases and evidence
while audits/finalizers depend on those IDs. It is not justified as a tail fix.

For a new campaign, partition deterministically by canonical audit ID across
eight fixed DB owners, not by current endpoint or language. Identical payloads
must reach the same shard; keep source aliases/split provenance separately and
merge terminal receipts with exact coverage checks. Each DB owns its leases and
bounded queue; one manifest binds shard count/hash rule/model/schema. Aggregate
memory budgets across all eight writers rather than granting16GiB twice to each
independently. Benchmark disk/WAL bandwidth first: more DBs cannot fix saturated
shared storage. No migration or new ledger framework was implemented here.
