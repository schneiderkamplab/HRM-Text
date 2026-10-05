# Baltic post-recovery five-minute measurement, 2026-10-04

## Scope and Recovery Exclusion

Read-only observation of `data/dfm13/baltic/synthetic-compact-26b-20261004-v1`,
new runtime PID2936091, with DaLA PID2883484 concurrently auditing at384/server.
Baltic retains128/server aggregate generation/review ceiling.
Window: 2026-10-04T03:06:30.858Z to 2026-10-04T03:11:32.161Z,301.304 seconds.
SQLite connections used mode=ro and short snapshot transactions; no client,
server, policy, cache or campaign artifact changes. This report/wiki are the
only written outputs. No direct agent-messaging channel was available: restart
coordination used main's confirmation and Boole's applied/migration/live receipts.

Boole's `data/dfm13/baltic/compact-empty-rationale-recovery-20261004-v1/applied.json`
credited13093 exact technical keeps before this window. The compact_recoveries
table held13093 rows at BOTH endpoints. Baseline22686 includes that credit;
final24124 minus22686 gives1438 genuinely new audited accepts. No recovery jump
is included in the rate. These remain automated-gate accepts, not independent
native-language certification.

## Baltic Result

- Audited accepts:22686 ->24124/140000;1438 new,286.36/minute.
- Charged candidate attempts:64006 ->67911;3905 new,777.6/minute.
- Window acceptance yield:36.82%, versus15.10% in the preceding pre-fix window.
- Earlier rate129.21/minute versus current286.36/minute, about2.22x. This is an
  observational before/after comparison under shared load, not a controlled
  causal experiment.
- Final language totals:LT12628, LV11496. Active candidates84 ->83.
- Historical7626 LV prior-quality-hold rows remain uncredited and separate.
- Fresh status deltas:1438 accepted,1976 valid-but-not-kept,391 invalid_output,
  25 review_invalid_output,66 review_abort_status_unknown,10 abort_status_unknown.
  These categories are not all semantic rejects.

| Group | Audited accepts / target | Candidate attempts | New accepts | Accepts/min | Remaining hours |
| --- | ---: | ---: | ---: | ---: | ---: |
| LT grounded-instruct | 4,009 / 20,000 | 9,701 | 252 | 50.2 | 5.3 |
| LT math-code | 1,673 / 6,000 | 2,911 | 106 | 21.1 | 3.4 |
| LT multiturn | 2,572 / 15,000 | 7,276 | 147 | 29.3 | 7.1 |
| LT openhermes | 2,123 / 15,000 | 7,276 | 108 | 21.5 | 10.0 |
| LT summary-rewrite | 1,157 / 10,000 | 4,851 | 73 | 14.5 | 10.1 |
| LT tool-dialogue | 1,094 / 4,000 | 1,941 | 72 | 14.3 | 3.4 |
| LV grounded-instruct | 3,551 / 20,000 | 9,701 | 226 | 45.0 | 6.1 |
| LV math-code | 1,463 / 6,000 | 2,911 | 85 | 16.9 | 4.5 |
| LV multiturn | 2,459 / 15,000 | 7,276 | 145 | 28.9 | 7.2 |
| LV openhermes | 1,899 / 15,000 | 7,276 | 103 | 20.5 | 10.6 |
| LV summary-rewrite | 1,020 / 10,000 | 4,851 | 57 | 11.4 | 13.2 |
| LV tool-dialogue | 1,104 / 4,000 | 1,940 | 64 | 12.7 | 3.8 |

## Conditional ETA and Six-Times Cap

Pooled remaining115876 accepts /286.36 per minute gives6.74 hours from the end
of the window. Keeping each group's measured rate gives13.19 hours to finish
ALL quotas, with LV summary-rewrite slowest; LV openhermes10.65h and LT
summary-rewrite10.14h are the next risks. Resource redistribution when faster
groups complete may shorten the tail, but is not assumed.

All12 groups project to meet their quotas before the existing6x candidate
attempt limits at these observed per-group yields. This supersedes the earlier
rough109K capped-yield projection for the pre-fix window; it does not change the
cap or guarantee140K completion. Tightest relative margin is LV summary-rewrite:
57/279=20.43% observed versus16.28% required on remaining budget. At unchanged
yield its uncapped budget-end projection is12287 against10000 target; actual
quota admission stops at target. Future yield declines, schema/transport errors,
source exhaustion, changed DaLA contention or a runtime interruption invalidate
the time extrapolation. Audit is included; export/upload and independent release
review are not included.

## Shared Endpoints

Start/end utilization: seven GPUs100% and GPU3 98% initially; seven100% and GPU5
96% finally. These are instantaneous samples, not a five-minute utilization mean.
Shared success counters increased31105 requests,6194.1/minute, across both
clients. No preemption counter increased. Request counts are NOT Baltic-only.

| Port | Shared completed delta | Running start -> end | Waiting start -> end | KV percent start -> end |
| --- | ---: | ---: | ---: | ---: |
| 8800 | 3980 | 324 -> 130 | 56 -> 0 | 66.6 -> 26.9 |
| 8801 | 3682 | 48 -> 381 | 0 -> 0 | 10.1 -> 77.4 |
| 8802 | 3751 | 16 -> 394 | 0 -> 0 | 3 -> 78.3 |
| 8803 | 4157 | 359 -> 299 | 0 -> 0 | 73 -> 59.0 |
| 8804 | 3834 | 343 -> 118 | 0 -> 0 | 67.9 -> 24.6 |
| 8805 | 3571 | 76 -> 389 | 11 -> 0 | 16.5 -> 78.2 |
| 8806 | 4019 | 383 -> 56 | 0 -> 0 | 77.9 -> 11.5 |
| 8807 | 4111 | 385 -> 165 | 0 -> 0 | 79.2 -> 34.1 |

The endpoint load remains uneven despite high utilization. Baltic starts are
spaced0.2s per endpoint, pause on shared waiting or KV>90%, and hit technical
circuits: recoveries increased from0 to22 across endpoints during this window.
Four endpoints were in circuit_cooldown at each admission snapshot, with0
probe_failures. The final stored admission snapshot also saw43 waiting on8802
about5 seconds before the direct final scrape reported0. This demonstrates
bursty shared load and admission throttling, not proof that increasing the128
ceiling alone would help. No concurrency change was attempted.

## Main DaLA Audit

Main progress.json snapshots have their own timestamps and are not perfectly
aligned with the Baltic interval. Snapshot mtimes1791083145.8401353 ->
1791083462.2994401 span316.459 seconds:

| State | Start | End |
| --- | ---: | ---: |
| done | 13152168 | 13519965 |
| failed | 60179 | 62128 |
| pending | 164238 | 170476 |
| running/claimed rows | 74352 | 89536 |

Main completed367797 additional done rows and1949 failed rows:369746 terminal
rows,70103/minute by receipt interval. These are audited DATA ROWS, not HTTP
requests; one batch request covers multiple rows, and claimed rows are not
simultaneously active GPU requests. Full scope35211311, terminal13582093,
remaining21629218 gives a conditional5.14-hour remaining first-pass ETA if that
rate and scope persist. Producer_done=false, so pending+running alone is NOT
the total remaining scope. Technical recovery and later decisions are excluded.
Start progress receipt lagged its direct metric sample by45s; final lagged30s.

## Evidence Paths

- Baltic runtime/progress/admission: campaign root above.
- Exact recovery receipts: compact-empty-rationale-recovery-20261004-v1.
- Main progress: `data/dfm13/dala-v2-baseline-batch-audit-20261004-v1/progress.json`.
- Measurement source: read-only groups/jobs/compact_recoveries snapshots and
  all8 localhost8800..8807 /metrics start/end; nvidia-smi utilization samples.
- No runtime stop, restart, quota migration or production admission was performed.

