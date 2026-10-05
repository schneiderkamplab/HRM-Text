# Held-source 31B capacity successors

CPU-only handoff for Poincare's final root matrix. No GPU requests, server
changes, active-worker interruption, or in-place seal updates were performed.

| Consumer | Successor under data/dfm13 | Candidates |
| --- | --- | ---: |
| Fars summaries | wave4/fars-summary-31b-consumer-capacity-v2 | 89296 |
| Baltic QA bulk | baltic/qa31-full-consumer-capacity-v2 | 118866 |
| Baltic QA exposed diagnostic | baltic/qa31-diagnostic20-consumer-capacity-v2 | 20 |

Each successor preserves its predecessor manifest, dependencies and immutable
catalog content, adds the new runner/capacity-validator pins, and creates no
runtime ledger. Predecessor roots remain unchanged. Launch templates remain
disabled. Use these successor links in the matrix; the old roots are historical,
not repinned. No real measured 31B capacity approval was created.

Runner: `python -m dfm12.held31_capacity_consumer run --root ROOT
--authorization APPROVAL --concurrency N [--capacity-profile PROFILE]`.
`verify --root ROOT` verifies all pins. The default is four clients/server;
without a measured profile the ceiling remains eight. Diagnostics always cap
at eight. Bulk can exceed eight only through existing `wave31_capacity.validate`:
five-minute all-eight-endpoint evidence, exact model/revision, positive completed
requests, KV <= 90%, zero errors/preemptions/OOM, and explicit ramp review.
The existing aggregate ceiling is 64, not 64 per consumer. Actual throughput at
larger allocations has not yet been measured for these consumers.

Approval must bind the successor manifest and model and set `run_authorized`.
Baltic bulk still requires the existing completed diagnostic semantic approval.
For measured capacity it must additionally provide `capacity_reservation`:

```json
{
  "profile_sha256": "HASH_OF_REAL_APPROVED_PROFILE",
  "wave": "wave4",
  "exclusive_wave_allocation": true,
  "other_clients_within_remaining_allocations": true,
  "scheduler_owner": "RESPONSIBLE_LAUNCH_OWNER"
}
```

Use `baltic` for Baltic QA. N must fit that wave's allocation. This reserves
the existing allocation rather than adding new clients atop it. Cooperative
successors hold a process-lifetime wave lock under
`data/dfm13/held31-capacity-reservations`; external/frozen production clients do
not honor that lock. The scheduler owner must stop scheduling that same wave's
other clients and account for all remaining clients before signing approval.
This is not automatic enforcement against arbitrary external clients. There is
no adaptive increase or lifecycle management. Runtime records the profile hash,
allocation, reservation and aggregate in `capacity-runtime.json`.

The stage lifecycle is copied unchanged from the pinned Fars engine, with only
the admission cap moved to the new wrapper and engine-local adapter bindings.
An AST parity test covers that entire lifecycle; existing Baltic protected
history, source support, calibration and fresh re-audit tests also pass.
Focused suite: **32 passed**. No claims of semantic certification or publication
permission are made; all existing source holds remain active.
