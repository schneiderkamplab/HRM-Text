---
type: Diagnostic
title: DFM13 Baltic Disconnect and Pacing Diagnosis
description: Read-only evidence separating inherited admission pacing from pre-header transport disconnects in the384 client.
tags: [dfm13, baltic, transport, performance]
status: draft
last_updated: 2026-10-04
confidence: high
---
# Baltic Disconnect and Pacing Diagnosis

Read-only inspection of Baltic384 PID3051744; no clients, watcher, servers or
training were stopped. Boole owns the private asynchronous performance adapter.
No pacing implementation file was agreed for this diagnostic owner, so no live
or pinned code was changed.

## Why the delays remained

The0.2-second new-candidate spacing and30-second circuit cooldown are inherited
from `multilingual_quarter.AdmissionGate`, introduced for the earlier multilingual
shared-server campaign after transient disconnects permanently retired workers.
That fix kept workers alive, serialized recovery, and retained KV<=90%, zero
waiting requests and fail-closed metrics. See
[quarter production](dfm12-multilingual-quarter-production.md).

Baltic128 reused that controller. The384 successor changes only the private
worker concurrency guard and verifies a runtime manifest; it did not remove or
restore pacing. Prior source-audit off-loop/keepalive improvements were separate
clients, not changes inherited by this production controller. Raising worker
count therefore does not remove the five-new-candidates/second/server ceiling.
The30 seconds is a circuit delay, not a mandatory pause after every request.

## Measured failures

Evidence: `docs/reports/dfm13_baltic_disconnect_20261004.json`, containing exact
raw paths/hashes, bounded ledger selection, admission snapshot and server tails.
Latest30 matching disconnects among5000 recently reserved rows:28review,
2generation; all30 have null HTTP status, zero body bytes and no first token.
Elapsed time: min0.0027s, median0.5973s, max1.5817s. Raw directories are shared by
ID prefixes, so samples were matched using request metadata ID, not just folder.

All eight bounded128KiB server-log tails showed ongoing inference/access activity
and no ERROR/Traceback/OutOfMemory/EngineDead lines. This is a bounded observation,
not proof that servers never failed. Admission snapshots show repeated successful
recoveries and zero probe failures, inconsistent with interpreting every such
event as a prolonged unavailable server.

Installed aiohttp defaults to15s idle keepalive. Installed vLLM serves with
`VLLM_HTTP_TIMEOUT_KEEP_ALIVE`, default5s; sampled server PID2687881 has no override.
Current controller connectors do not override the aiohttp idle timeout. A stale
connection reuse/close race is therefore a plausible contributor. It is not proven
without TCP/reuse tracing; server access logs lack a joinable client raw ID.
Synchronous budget/tokenizer/validation and raw writes in the event loop may widen
the race and delay callbacks; this inspection does not quantify that contribution.

## Amplification and recommended interface

`Stages` sets failures[endpoint]=3 after a single aiohttp ClientError, including
ServerDisconnectedError. A finishing worker then calls gate.trip; concurrent
finishing workers can keep extending the30-second deadline while the same failure
count remains high. Recovery requires both /models and /metrics. The row remains
abort_status_unknown, correctly preventing blind replay, but endpoint health and
row disposition are conflated. Three does not mean three observed disconnects.

For Boole's isolated adapter, recommendations (not applied here):

- Use client keepalive_timeout below the verified5s server idle cutoff, e.g.2s;
  retain bounded connection pools and separate telemetry. Add connection-reuse
  tracing plus event-loop lag counters to test the hypothesis.
- Offload preparation/raw writes with isolated writer ownership; keep ledger
  reservations/commits on their single owner. Preserve byte-identical requests.
- Keep failed/partial rows terminal-unknown; a pre-header disconnect does not
  prove the server did not receive the request. No implicit failed-row replay.
- Distinguish row outcome from endpoint health. For a first disconnect, perform
  a short bounded endpoint-health recheck before fresh work. Escalate repeated
  failures in a time window or failed health checks to capped backoff; do not
  continually extend one circuit deadline for the same already-accounted event.
- Retain fail-closed metrics, KV threshold, waiting check and race-generation
  invalidation. If reducing healthy spacing, use serialized bounded permits and
  a short-lived metrics cache; do not disable admission or gate pending reviews.

No shared gate changes are authorized by these recommendations alone. A private
adapter must expose its factory/manifest marker for later completion-proof update,
with an explicit coordinated watcher pause and rearm. W4 remains128 unless the
user separately changes its concurrency.
