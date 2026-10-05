# Read-only wave4 operational audit

Observation Unix1791044742..1791044881,2026-10-03. No process signals, queue
writes, retries, GPU requests, frozen31B edits or new workers. Moving snapshots,
not admission or completion claims.

## Queue snapshot

Read-only SQLite at1791044769:

| Stage | Done | Failed | Pending | Running | Deferred31B |
| --- | ---: | ---: | ---: | ---: | ---: |
| Source audit | 5080100 | 6329 | 3641183 | 3584 | 0 |
| Repair generation | 83547 | 58 | 0 | 0 | 10659 |
| Repair audit | 37403 | 40 | 0 | 0 | 0 |

219 registered components,8731196 audit jobs. Aggregate sealed ready-row totals
match: direct6151923, institutional208, Wikipedia2378641, Fars141771, Aya1937,
Croatian455, EuroBlocks5610, LuxIT46070, Kapibara4581. Aggregate equality is not
per-payload coverage proof. All sealed requested parallel components registered.

Audit clients2032197 (64/server),2111441 (320/server), monitor2111503 are live.
Recent failures include invalid JSON escapes from completed responses, not an
auth/server outage. Error-event counters count attempts, not unique failed rows.
Monitor1791044688 showed100% GPU utilization and29429 requests/minute aggregate;
1791044808 showed0% on all eight and12549/minute window rate. Booster completions
continued increasing: feed is bursty despite3.645M outstanding rows. Rough current
backlog range2.1..4.8 hours at those observed rates, excluding pivots/retries and
changing workload. Requests include retries; this is not a drain-time promise.

## CPU supply

- Direct finished:330 inventory pairs,203 approved/all203 receipts;181 requested
  direct pairs,22 bridge-only,127 pivot-required.8857309 candidate pairs total,
  6151923 requested/queued.
- Institutional extraction finished:all21 approved pairs have receipts;9
  requested pairs/208 rows,12 bridge-only;1678001 total candidates.
- Supervisor2103630 waits for child2427821, now performing coverage reconciliation
  inside institutional, not waiting for missing downloads. At25 components/
  359748 rows checked, zero new jobs; approximately5792383 rows remained in this
  pass. Subsequent log advanced through direct-bg-fi/fr, so it is moving.
- The wrapper next builds pivots, enqueues them, reconciles again, then writes
  parallel-preparation.json. No final marker or pivot outputs exist yet.45
  English-leg files contain6587248 pairs to index.258 non-English pairs have
  fewer than1000 direct rows and qualify for pivot joins;126 have no direct rows.
  Final row yield is unknown until exact joins/ambiguity rejection, not a quota.

## Actionable findings

1. Investigate storage/commit stalls before increasing concurrency. At1791044881
   institutional2427821 and transform release2355940 were in folio_wait_bit_common.
   Coverage performs millions of INSERT OR IGNORE checks,512-row transactions,
   on the live audit DB. This is a plausible contributor to bursty feed, not a
   proven lock-owner diagnosis. Observe DB-worker commit latency/filesystem I/O.
2. Do not duplicate the active CPU chain. All approved extraction is complete.
   Coverage safeguards earlier incomplete enqueue history, but the wrapper also
   reconciles later. Any optimization belongs to its owner after this pass and
   must retain exact coverage proof. No precise CPU ETA from file counts alone.
3. Selection2143812 and translation release2143813 wait downstream of the final
   preparation marker. Preserve that guard; do not freeze incomplete pivot input
   or forge completion. Pivots are the main remaining unknown supply.
4. Transform release2355940 is active. Aggregate status1791043436 is stale;
   newer log shows Croatian export completed, HU/LB/SK audit-retry tails. Empty
   stale status objects do not mean zero source supply. Instruction watcher
   2365731 reports15 components uploaded/integrated, one empty Aya-sq, two held
   Fars summaries. Those holds await31B, not new26B retries.
5. Matina/TLPC remain separate gated-access blocks. No repeated403 requests or
   claimed completion warranted. Full source objectives remain unchanged.

Evidence: mode=ro audit/repair SQLite; translations/institutional inventory,
progress and receipts; parallel-stage.json; advance-parallel/instructions/
transforms/selections logs; audit-booster status/metrics/errors; monitor/latest;
process identities/wait channels. Inspected advance_wave4_parallel, wave4_cpu,
wave_job_coverage, baltic_pivots and european_stage without edits.
