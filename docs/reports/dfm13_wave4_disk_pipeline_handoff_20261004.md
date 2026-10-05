# W4 Disk128 / CPU16 / Ledger1

Final isolated module: `dfm12.wave4_disk_pipeline`.
SHA256: `3f4d0a3851bc5f1111e9248d2972a324aa66a0234645232b5aa1f9f5938d7537`.
Harvey owns drain/reseal/restart. Preserve all previous implementation pins and
independent-launch authorization; add the absolute new implementation pin and
`disk_pipeline_runtime_module=dfm12.wave4_disk_pipeline`.

```bash
python -u -m dfm12.wave4_disk_pipeline --root <W4_ROOT> --launch-mode independent
```

Three executors: disk128, CPU16, ledger1. Disk and CPU submitted+running bounds
are256/32; additional coroutines wait on their respective semaphores. Ledger
remains single-threaded. Existing thread-local Budget, fast guard, reservation
durability boundary, cached gate hint,768/server and zero spacing are retained.
Independent/completed launch contracts and inherited implementation pins remain
mandatory; no bypass.

Private compact JSON serialization uses one json.dumps and one handle.write,
then the unchanged atomic helper: flush/fsync temporary file, atomic replace.
Parsed content and canonical digest bindings are unchanged; file-byte hashes for
new artifacts use their actual bytes. No historical evidence is rewritten. Only
private process/stage globals, cloned RawResponseWriter begin/finish globals,
private materialize and new reservation specification writes use this writer.
Global dfm12.io and shared streaming remain unchanged.

`operation-timings.json` every5s reports exact per-operation and per-pool:
`semaphore_waiting`, `submitted` (executor queued), `running`, and
`waiting=semaphore_waiting+submitted`. Service/queue totals and completed counts
are retained. `http_inflight` counts actual HTTP request contexts by endpoint and
generate/review stage, separately from `reserved_outstanding` allocations.
No inference from ledger active to actual HTTP queued. Snapshot counters are
thread-synchronized; cancellation awaits any executing durable operation.

Focused tests include full mocked W4 HTTP pipeline, private writer isolation,
identical parsed/canonical content with old-file bytes preserved, exact40-task
queue decomposition, reservation failure/cancellation recovery, source SQLite
ownership and fast-guard parity. Seed readonly connection caching is deliberately
not included: measured warm savings0.238ms/lookup do not justify another provider
change in this disk-bottleneck patch. New process tokenizer cold-start remains
possible; measure warm throughput separately. No production speedup claim yet.
