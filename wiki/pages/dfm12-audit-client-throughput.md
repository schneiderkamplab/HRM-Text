---
type: Runbook
title: DFM12 Audit Client Throughput
description: Investigation and mitigation of HTTP client feeding stalls in the European audit campaign.
status: draft
confidence: medium
last_updated: 2026-09-27
tags: [dfm12, audit, performance]
---
# DFM12 Audit Client Throughput

Related: [European preparation and campaigns](dfm12-european-cpu-preparation.md).

## Observed Bottleneck

The eight-server client reported approximately 6,000 completed rows/minute,
low sampled GPU KV occupancy, and many more client in-flight requests than
requests actually running in vLLM. Main-thread CPU was about 80%; its SQLite
thread was about 2%. Host ptrace restrictions prevented attaching py-spy, even
with sudo. Do not claim a captured production stack profile.

Installed httpcore's `_assign_requests_to_connections` scans the complete
connection pool and repeatedly enumerates idle connections. The client shared
one pool across eight origins, with a maximum of 8192 retained connections.
A local reproduction of idle bookkeeping measured approximately 10.08 ms per
operation for 800 connections versus 0.174 ms for 100 connections. This is a
synthetic reproduction, not a measured fraction of production CPU time.

## Implemented Mitigation

`dfm12.european_stage` now creates an independent HTTP pool per endpoint,
retaining at most 128 idle connections each and expiring them after two seconds
(vLLM's installed idle timeout defaults to five seconds). Active connection
ceilings remain tied to the configured maximum; adaptive request budgets remain
in effect. Eight tests passed, including mocked multi-endpoint completion and
pool isolation. Audit prompts, models, scoring gates and committed results are
unchanged.

The previous client drained, released leases, and its supervisor cleaned up
owned servers. Restart at 09:18:24 uses eight servers at utilization 0.45,
initial concurrency 96 each, supervisor PID 3569635, and logs under
`data/dfm12/european-expansion-20260926/audit-pools-20260927-091824/`.
Live validation is required before claiming the bottleneck resolved.

## Live Validation

The first 4.52 minutes committed 60,580 audits: **13,406 rows/minute**, versus
approximately 5,600--6,000/minute in recent pre-change windows. This is a rolling
corpus, not a randomized matched-input benchmark. The former feeding gap is no
longer present: final snapshot running requests were 103--119/GPU versus
106--120 client in-flight. KV occupancy was 77--87%. Earlier measurements in the
same window showed 81--90% occupancy. One cumulative preemption occurred across
all eight servers, and zero transport retries were recorded. Model/schema errors
remain separately recorded (2,587 attempts); pool changes do not relax validation.

These observations support the shared HTTP pool as a major feeding bottleneck.
Keep per-endpoint bounded pools; do not replace them with a shared pool merely
to increase the nominal concurrency. The audit remains running under PID 3569635.

## Completion and Servers-only Restart (2026-09-28)

The running-state note above is superseded: the audit completed with 14,394,514
successful decisions and 44,620 terminal request failures, no pending leases.
Read-only aggregation of `result.keep=true`, grouped by `payload.record.language`,
found **12,169,124 accepted rows**. This is the European expansion queue only,
not the independent DaLA audit or all inherited DFM12 data.

At the owner's request, restarted only eight vLLM servers on ports 8600--8607
at utilization 0.45. All eight passed `/v1/models` readiness. No clients were
launched or restarted; training was left untouched. Server API PIDs 2712010--
2712017 and ownership/logs are in
`data/dfm12/european-expansion-20260926/servers-only-20260928-153557/`.

Later on 2026-09-28, the owner requested utilization **0.8**, superseding 0.45
for these shared servers. Exact owned process trees were stopped and restarted
with their original environments and ports 8600--8607; clients were untouched.
All eight passed `/v1/models` readiness. Ownership and logs now live under
`data/dfm12/european-expansion-20260926/servers-only-20260928-193205/`.
Other settings remain 1,024 maximum sequences, 16,384 batched tokens and
16,384 context. Each server reports 89.6 GiB available KV memory and 426,696
KV tokens. This larger allocation must be considered before colocating training.
