# W4 Parallel I/O Handoff

Final isolated module: `dfm12.wave4_parallel_io`, initial16 workers. No pinned
shared dependencies edited; live process/pins remain deployment owner's scope.

Explicit manifest fields: `parallel_io_runtime_module=dfm12.wave4_parallel_io`,
`parallel_io_workers=16`, and absolute module SHA256 in `implementation_pins`.
Preserve all existing handoff/independent-launch receipts when resealing.

```bash
python -u -m dfm12.wave4_parallel_io --root <W4_ROOT> --workers 16 --launch-mode independent
```

The CLI verifies the existing `verify_independent_launch` contract, or for
`--launch-mode completed`, the original successful140K Baltic completion proof.
Base W4 verification still runs; no bypass. Runtime metadata reports the new
module,16 independent workers and one ledger owner.768/server, zero fixed
spacing, KV/queue guards, keepalive and retry/no-replay policy unchanged.

Independent raw/stage/request/outcome JSON writes, formatting/validation,
materialization and Budget.measure run in bounded pool16 (32 queued/running
parallel calls maximum). Each worker lazily owns its own Budget/tokenizer; no
mutable tokenizer is concurrently shared. SQLite, SourceProvider, fingerprint
claims and gate remaining callbacks stay on one thread. Calls are awaited;
cancellation waits for an executing durable operation before cleanup. Per-job
raw begin/finish and stage writes retain sequencing. No FULL fsync weakening.

`operation-timings.json` updates every15s and on exit, with per-operation
count, aggregate queue wait, aggregate service and maximum queue wait. Those
measurements distinguish owner contention from disk/format/tokenization cost.
No measured production speedup claimed before deployment. Reserve still writes
the durable specification on owner; if its service dominates after this change,
consider a separately tested split/batched reservation, not an unmeasured crash
boundary change in this release. Original recovery/unknown semantics preserved.

Tests exercise real SQLite single ownership, full W4 execute with mock HTTP
generation/review/raw capture/acceptance, all installed closure routes,
writer.finish versus ledger.finish, independent I/O blocking without owner
starvation, thread-local budgets, cancellation durability and unknown no-replay.
Deployment/pin ownership: Harvey. No worker stopped by this implementation task.

## Initial Deployment Failure and Correction

Initial deployed PID3127608 exited before useful throughput measurement:
the SourceProvider constructor lambda also called `load`, which incorrectly
selected the independent pool. SQLite then rejected owner-thread use/close.
This supersedes the initial tests-only readiness claim. Constructor/verification
names now take owner precedence over nested helper calls. Full mocked W4 test
now creates a real SQLite connection in SourceProvider and uses/closes it during
execution.37 focused/regression tests passed after correction. Corrected module
SHA256: `b0c44f4133bd6730fc710defede2f9edce324ed1826e6920160c888acf3b186f`.
That intermediate hash is superseded by final constructor-dependency precedence
and explicit nested-load regression SHA256
`edb2ac48e5588d01fa7e442a9124c8549827a541107bc3298fb46cf418782426`.

## Corrected Live Measurement

Harvey restarted corrected PID3128749. Independent saved snapshots cover60.084s
after warmup, under `data/dfm13/wave4/parallel-io-steady-measure-20261004-v1`;
`report.json` binds before/after hashes. No live edits or restart during measurement.
Generation requests:1,547, mean3.76ms service/1.82ms queue. Budget measurement:
2,987, mean3.82ms service/0.98ms queue. The large cumulative generation/Budget
times were startup dominated, not evidence of repeated steady tokenizer loads.

Owner reserve:1,547 calls,37.78s aggregate service,24.42ms/call and121.47ms
mean queue. Owner callbacks:3,093 calls,13.31s service; finish4.97s; claims3.38s.
Total owner service approximately59.49s/60.084s, near saturation. Independent
I/O queue means approximately1-2ms.296 materializations completed in this window;
raw-response finishes3,011 are local callback counts, not server throughput proof.

Next targeted work should reduce owner reservation/callback work, not expand the
independent pool or change prompt semantics. Measure provider/DB/spec-fsync
subcomponents before splitting durable specification writes; consider a maintained
remaining-work hint for admission callbacks while retaining atomic reserve checks.
Do not batch or weaken FULL commits without separate crash/recovery tests.
