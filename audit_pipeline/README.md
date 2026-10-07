# Shared Audit and Generation Pipeline

Use this runtime for new audit/generation clients. Do not add another campaign
scheduler or silently restore pacing/backoff. The `dfm14` module is a data adapter,
not a second runtime. It preserves existing chunk journals, IDs and receipts.

```bash
python -m audit_pipeline audit --root data/dfm14/gpu-ready \
  --output data/dfm14/audit-v1 --concurrency 256
python -m audit_pipeline generate --root data/dfm14/production-v1 --concurrency 256
```

Launch detached with `setsid`, redirect to a campaign log. Servers must already
exist. This package never starts, stops or reallocates servers. SIGTERM/SIGINT
stops new row admission, drains active rows and releases locks; rerun the same
command to resume. A hard kill can lose in-flight requests, but complete journal
entries remain authoritative and incomplete trailing lines are recovered under
the chunk lock. Do not run journal recovery against a live writer.

## Runtime Guarantees

- One process and independent HTTP pool per endpoint. Retain at most 128 idle
  connections for two seconds: the proven DFM12 European-audit pool settings.
- Rolling row queue across chunks. Never await an entire chunk before feeding
  the next one. Concurrency limits actual HTTP requests, not CPU/disk stages.
- Two row workers per request slot plus a bounded input buffer. This permits
  CPU preparation/review and durable writes to overlap network activity.
- Zero request spacing, zero retry backoff, at most one retry in the adapters.
  Telemetry sleeps do not gate dispatch. Per-request timeout remains bounded.
- Dedicated serialized CPU and disk owners per process, following the W4
  offload design. Source reads, hashing, tokenization, parsing, validation,
  JSON encoding, journal writes, fsync and progress writes are off the event loop.
  Only async networking and small scheduling/counter updates stay on it.
- Exclusive chunk locks for the whole write lifetime; one disk owner; durable
  append before progress/receipt; receipt only when all pending rows finish.
- Existing accepted rows and exhausted retry budgets are preserved. No reset of
  quality failures or quotas. Disk/manifest failures fail closed, not as rejects.
- Default review: non-thinking plain `accept` or `reject`, no JSON/schema decoding,
  max 32 output tokens. Inspect all turns/evidence, emit no per-turn report.

Historical scores/reasons are retained verbatim. New rows record the compact
policy; mixed chunks list both policies. No invented replacement scores. Changing
review policy is distinct from changing the transport and requires authorization.
Legacy source manifests stay pinned; shared runtime/review pins live separately
under `pipeline/configuration.json`.

## Reuse

Adapters implement synchronous `initialize`, `next_item`, `finish_item`, `report`
and `close` on the disk owner, `initialize_cpu` on the CPU owner, and async
`process(item, transport, cpu, disk)`. Use `cpu.call` for every CPU-bound stage and
`disk.call` for durable I/O. Never import a campaign runner to obtain transport.
Adapter errors should distinguish request/content failures from corrupt inputs
and failed storage. Only the former consume a row's retry budget.

Telemetry: `pipeline/endpoint-PORT.json` records actual HTTP inflight/peak,
requests/errors, active/buffered rows, open chunks and CPU/disk call timings.
These distinguish starvation, tails, HTTP congestion and slow preparation.

Tests: `python -m unittest discover -s tests -p 'test_audit_pipeline.py'`.
The retained historical references are `dfm12/european_stage.py` (bounded per-host
HTTP pools), `dfm12/baltic_async_io.py` (cancellation-safe owner) and
`dfm12/wave4_disk_pipeline.py` (separate CPU/disk lanes). No AST monkeypatching is
used here and historical pinned campaigns are not rewritten.
