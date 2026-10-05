# W4 Bounded Ledger Group Commit

Read-only live diagnosis: parent reports3,632requests/min and16,512generation
tokens/s in the latest warm60s, versus earlier5,348requests/min. Disk128 did not
remove serial owner saturation; thousands of reservations queued ahead of
fingerprint claims and terminal finishes. No live process stopped or pins edited.

Recommendation: cap each owner batch at16 operations; coalesce existing queued
requests without waiting for a full batch. Schedule claims/finishes ahead of
reservations between batches, with bounded fairness to prevent starvation.
Do not release operation futures, write/send newly reserved candidates, or publish
quota hints until commits succeed. A worker ceiling increase alone cannot reduce
per-operation durable commit cost.

Prepared primitive: `dfm12.wave4_ledger_batch.execute_batch(ledger, provider,
operations, max_batch=16)`. Existing transaction statements become SAVEPOINTs
inside an outer owner-thread transaction. Commit source selections FIRST and
ledger SECOND, preserving original lineage-before-allocation ordering. FULL
synchronous mode unchanged. Source commit followed by failed ledger commit may
retain source selections, as before; never rewind them or return uncommitted
allocations. Restore ledger cache snapshots on rollback, refresh/publish only
after finishing the batch. Fingerprint-only batches may omit provider.

Five CPU tests passed: invisible partial batches; complete rollback; source
commit/ledger failure; batch bounds; actual private Ledger.reserve quota limits
and interrupted-allocation recovery with no specification files/HTTP calls.
Actual reservation batch uses one ledger COMMIT rather than one per row.

NOT DEPLOYMENT READY: no queue coalescer/fairness scheduler or runtime migration
is installed. Next required tests cover the actual source adapter, mixed
claims/finishes, cancellation of queued futures and starvation bounds before
Harvey may review a sealed successor. Current live client remains unchanged.

## Superseding Tested Runtime Handoff

The prototype-only status above is superseded by isolated
`dfm12.wave4_batched_runtime`, retaining disk128/CPU16/ledger1 and all prior
contracts. Max16 operations/batch;3 completion selections per1 reserve when
both queues have work. One owner executes the complete batch; caller results
release only after source then ledger commits. Cancelled callers wait for commit
completion; any unobserved allocation retains original unknown/no-replay recovery.

Tests now cover real private Ledger reservations (32 allocations/two ledger
COMMITs), duplicate claims (one winner), repeated finishes (one quota credit),
installed AST closure contexts, bounded fairness, and cancellation awaiting
commit. Combined regression suite67 passed, plus the added cancellation test.
No production throughput claim before restart measurement.

Harvey: add `batched_runtime_module=dfm12.wave4_batched_runtime` and pins:
- Runtime SHA256 `bb42804a3b8f749cabc6a8b2704c7280954420cd05a27a9ece4f3734302bbfba`.
- Helper SHA256 `833569d7531337e91e2548bf6c4ac4f6735bd4d23b5c981550724c469e746430`.

Command: `python -u -m dfm12.wave4_batched_runtime --root <W4_ROOT> --launch-mode independent`.
Runtime reports committed batch/operation totals, failed batches, current batch
operations and reserve/completion scheduler queue lengths separately from disk/CPU
queues and HTTP in-flight contexts. Existing base/independent proof verification
and dependency pins remain mandatory. Deployment/drain ownership remains Harvey.
