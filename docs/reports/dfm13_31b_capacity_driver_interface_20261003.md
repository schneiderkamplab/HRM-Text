# Capacity driver interface for main and Boole

CPU implementation complete; no live calls or approval. Executable:
`dfm12.wave31_capacity_measure`. It owns only its measurement client/artifacts,
never server lifecycle. One independently reviewed plateau per fresh root; an
operator may run successive plateaus, but the driver never approves a profile
or automatically increases capacity.

The initial proposed flat server receipt is superseded. The driver accepts
Boole's actual lifecycle DIRECTORY, directly reading `configuration.json`,
`commands.json`, `endpoints.json`, `ready.json`, fresh `status.json`, and each
`gpuN/ownership.json`. No parallel lifecycle schema or launcher is required.
See `docs/reports/dfm13_31b_server_lifecycle_handoff_20261003.md`.

All ports8800..8807 are mandatory. Read-only `/proc` checks bind PID/start ticks
and exact launch argv, actual max-seqs, port and context. Receipt fixed settings
and command must agree on TP1, memory.95, context32768, prefill16384 and the exact
snapshot. The interpreter must be the inspected audit environment. A fresh
all-eight status, unchanged supervisor and absence of stop/stopped receipts are
required throughout measurement. Every endpoint also passes strict live `/models`
health. Logs are the owned stdout/stderr streams; missing/rotated logs are unknown
OOM evidence, not zero. Byte offsets and copies of the exact measurement window
are preserved even if the server has died. This does not certify kernel/global
logs or startup events outside that window.

The separate launch authorization binds `workload_manifest_sha256` and
`server_receipt_sha256`, plus `measurement_authorized=true`, `exclusive_endpoints=true`, and
`source_audits_drained=true`. This does not stop other clients: the owner must
establish exclusivity. Initial metrics must be idle; observed extra traffic,
counter resets, stale/failed metrics or process drift invalidate the plateau.
For the bundle, `server_receipt_sha256` is
`digest(lifecycle_bundle(SERVER_ROOT, workload_manifest, N)['bundle_pins'])`:
ONLY configuration/commands/endpoints file hashes. Per-GPU ownership files can
grow as descendants are discovered; they are captured with canonical snapshot
hashes but are NOT immutable authorization pins. Actual PID/start ticks/argv
remain independently verified. Continuously refreshed ready/status observations
are also captured separately, not treated as immutable files. This supersedes
the earlier inclusion of ownership-file hashes in the authorization bundle.

Capacity is aggregate per endpoint, at most64 total owned requests per server,
not64 per dataset. All eight receive the same mixed frozen workload. Requested
duration is at least300 seconds, followed by graceful drain. SIGINT/SIGTERM
stops new dispatch and waits for bounded in-flight requests; no process is killed.
Interrupted plateaus remain evidence, never qualifying300-second measurements.

Measurement JSON uses `wave31_capacity` fields, with actual KV high-water,
preemption deltas, served completions, request errors, p95 and server-log OOM
evidence. Unknown metrics/log evidence must fail closed. Raw prompts/responses,
per-request bindings/latencies and short metric snapshots remain in the root.
No `selected_after_ramp_review` or capacity approval is generated.

## Frozen workload and transport

Final workload: `data/dfm13/gemma31-capacity-workload-20261003-v4`.
Manifest SHA256:
`2ac489ee2f440b522756276dc3807807eb4a1eba86c0a8f36c878aa421fc3fe6`.
Actual native31B CPU preparation passed32 complete requests:24 generation
requests (four per family, two from each frozen wave) and four each held QA/Fars.
Native prompt range631..24546; largest total32738 including output reserve.
The four longest serialized full Fars requests across its entire catalog measure
2250,2537,2468,2417 prompt tokens. These sources are shorter than article-aware
QA; no artificial padding was introduced. Generation preserves its frozen
thinking-off/output settings; QA/Fars preserve thinking-on/8192 output reserve.
No schema conversion, prompt nonce, truncation or request shortening is applied.

Workload-v1, v2 and v3 are superseded, not launch entry points. Their manifests and
requests are preserved, with exact former driver copies at
`superseded-driver.py`. Their old code pins are intentionally not repinned to the
current implementation. Only v4 is the current driver-compatible workload.

The first draft's force-close transport is superseded. Current request clients
match `multilingual_quarter.py:516-519`: keepalive TCPConnector with
`limit=8*N, limit_per_host=N`; metrics/health use a separate eight-connection
client. There is no transport retry or auto-resubmission within a measurement.

**Prefix cache finding:** installed audit vLLM0.27.1 accepts nonempty top-level
`cache_salt` in `entrypoints/openai/chat_completion/protocol.py:453,973`.
`renderers/online_renderer.py:373,432` and `renderers/base.py:795,858` propagate it
to engine inputs. `v1/core/kv_cache_utils.py:579` includes the salt in the first
block hash, which propagates through the prefix chain. These four installed
source files are pinned by the workload. The lifecycle interpreter must match
the inspected audit environment.

Each wire request uses a unique hash of run UUID, endpoint port and sequence as
cache_salt. Frozen case/request hashes and salted wire hash are recorded
separately; raw captures contain the exact salted payload. Tests verify unique
salts, unmodified messages and identical native token IDs/counts. This is a
**conservative cache-isolated pressure ramp**, not a claim about production's
normal prefix-cache hit distribution or content/output diversity. Repeating32
prompts without that distinction would overestimate unique-workload capacity.

Raw metrics are sampled, not continuous KV tracing. Compatibility fields
`completed` and `p95_seconds` cover successful completions DURING the timed
plateau only. `plateau_completed`, `drain_completed`, `total_completed` and their
three `*_completed_per_second` fields have matching, explicit time denominators.
Drain and total latency/finish-reason summaries are separate. Server completion
counter reconciliation uses the TOTAL, including drain, not plateau-only counts.
The exact first dispatch-stop timestamp is captured independently of polling.
Full300 seconds must elapse before drain; early stop cannot count drain time
toward300, nor divide drain completions by plateau duration. Telemetry continues
during drain. Logs, outcomes, raw
requests/responses and telemetry receive an `evidence-index.json` with hashes,
bound from the measurement seal. Missing evidence sets a required validator
field null, rather than leaving an apparently passing profile-compatible record.

## Executable handoff

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave31_capacity_measure verify \
  --root data/dfm13/gemma31-capacity-workload-20261003-v4
# NOT executed: only after source-audit drain and actual owned31B readiness.
$PY -m dfm12.wave31_capacity_measure run --root NEW_PLATEAU_ROOT \
  --workload data/dfm13/gemma31-capacity-workload-20261003-v4 \
  --server-receipt OWNED_LIFECYCLE_DIRECTORY --authorization APPROVAL_JSON \
  --concurrency 8 --duration 300 --poll 2
```

Subsequent bounded plateaus require new roots and explicit reviewed scheduling;
no automated ramp, server restart, ownership cleanup or admission occurs here.
`measurement.json` is compatible with `wave31_capacity` measurement inputs, but
profile selection, allocations and reviewer approval remain an independent
human/owner decision.51 focused mocked tests passed, including lifecycle schema,
counter parsing, validator compatibility, graceful early drain, errors, log
rotation, exact salt bindings and native context. No real measurements, live
HTTP requests, GPU launches, server signals or training edits occurred.

## CPU Recheck

Later2026-10-03, the final v3 workload was reverified against all manifest pins:
32 requests, four in each of six generation families plus four held-QA and four
held-Fars requests; maximum total32738 tokens. Manifest hash remains
`d25efc145f55ea2fd6236ae3593039bb243760af7711dc8faaf74c59dd3938ac`.
No driver/source changes or reseal were needed. Added a mocked `run()` integration
test asserting actual keepalive connector settings, per-host concurrency and
separate metrics pool, with proper connector closure. The focused suite now
passes **52 tests**. Existing unique-salt, wire/frozen hash, unchanged token IDs,
graceful drain and lifecycle tests remain passing. Test measurements exist only
as explicitly synthetic pytest fixtures, not real capacity evidence. No live
HTTP/GPU work was launched while26B audits remain busy.

## Independent Review Corrections

Later2026-10-03, Boole identified mutable ownership-file pins and a throughput
window mismatch. Both are fixed in the v4 successor above. Authorization now
pins only configuration/commands/endpoints; captured ownership snapshot hashes
remain evidence, while PID/start ticks/argv are checked independently. Adding
descendants therefore does not invalidate a healthy lifecycle authorization.

Completion events are partitioned at the exact first dispatch-stop/deadline.
Timed-plateau completion count, rate and p95 exclude drain completions. Drain
and end-to-end counts/rates have their own denominators, and total server-counter
reconciliation still includes all completions. Post-drain evidence-finalization
time is separate from the served-rate window.

Focused suite: **53 passed**, including ownership growth without pin drift and
an exact300-second/tail example verifying all three served-rate denominators.
Actual32-request native CPU preparation and full pin verification passed forv4;
`requests.json` is byte-identical tov3. The oldv3 driver was archived with its
original pinned hash, and its manifest was not repinned. No GPU/HTTP measurements
or new approval were performed. Earlier v3 verification statements above are
historical and superseded as active launch instructions.
