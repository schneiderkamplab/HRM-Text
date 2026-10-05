# Current 31B operational handoff, 2026-10-03

**Launcher gap resolved later2026-10-03:** the isolated
`dfm12.wave31_server_lifecycle` now implements ramp and measured production server
lifecycles, without editing frozen dependencies. Its
[exact CLI and receipt contract](dfm13_31b_server_lifecycle_handoff_20261003.md)
supersedes the missing-launcher finding below. Historical findings are retained.
No real GPU launch or capacity measurement has occurred. Epicurus owns the
separate measurement driver; this launcher does not manufacture telemetry.

Documentation/code comparison only. No server, GPU, model request, signal,
approval or frozen implementation change. This supersedes the operational
checklist in the [historical dry run](dfm13_31b_launch_dryrun_20261003.md), not its
historical test results. The [final matrix](dfm13_31b_final_root_matrix_20261003.md)
owns the frozen production inventory.

## Ordered handoff

Commands below are conditional operator instructions, NOT executed here.
`HANDOFF` must name the owner's actual final exhaustive drain/freeze contract,
including the Slovak additive handoff listed in the matrix. Do not substitute a
deferral fragment or invent a final-ready filename. `MODEL_PATH` must equal the
verified snapshot in `data/dfm13/wave4/gemma31-download/ready.json`.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
# CPU checks, then transition ONLY after owner authorizes exact-owned release:
$PY -m dfm12.wave4_gemma31_transition inspect
$PY -m dfm12.wave4_gemma31_transition check --contract "$HANDOFF" --model-path "$MODEL_PATH"
$PY -m dfm12.wave4_gemma31_transition transition --contract "$HANDOFF" --model-path "$MODEL_PATH"
# Transition itself executes76. Require its comparison-terminal.json; do not duplicate76.
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/wave4/gemma31-fresh-comparison30-v5
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/wave4/gemma31-fresh-comparison30-v5 --concurrency-per-server 2
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/baltic/gemma31-fresh-comparison12-v3
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/baltic/gemma31-fresh-comparison12-v3 --concurrency-per-server 2
$PY -m dfm12.wave31_balanced_run verify --root data/dfm13/gemma31-balanced-execution-20261003-v2
$PY -m dfm12.wave31_balanced_run run --root data/dfm13/gemma31-balanced-execution-20261003-v2 --concurrency-per-server 2
```

Run these comparisons sequentially; terminal failed jobs are not quality passes.
Balanced source-v4 is input, execution-v2 is the run root. See the
[balanced execution contract](dfm13_balanced234_execution_handoff_20261003.md).
Independent semantic approval is still required before bulk production.

Held-source consumers do not need new servers for an authorized bounded run.
Reserve shared capacity, initially run sequentially, and use the existing pinned
authorization formats rather than creating permissive placeholders:

- Fars: `python -m dfm12.held31_capacity_consumer run --root data/dfm13/wave4/fars-summary-31b-consumer-capacity-v2 --authorization "$FARS_AUTHORIZATION" --concurrency 4`.
  [Reservation/approval contract](dfm13_held31_capacity_successors_20261003.md).
- P3: use the repeated-eight-endpoint command in the
  [P3 dispatcher handoff](dfm13_p3_blind_pairing_handoff_20261003.md): first both
  140-control stages, reconcile, then two bulk stages only after calibration
  passes; bounded repair and fresh re-audit follow. Do not use consumer-v1 or
  single-endpoint pairing run as the bulk path. Attempt budgets are not completed
  row counts. Cooperative locks do not reserve capacity from unrelated clients.
- QA: use the article-aware successor sequence below, not the no-article
  capacity-v2 policy. No earlier semantic approval transfers automatically.

## Article-aware QA coordination with Epicurus

These are actual sealed roots, not proposed names. This review called the
existing `fars_summary_consumer.verify` on both, successfully checking their
seals and all dependency/input pins:

| Root under data/dfm13/baltic | Catalog | Dispatchable | Context unresolved |
| --- | ---: | ---: | ---: |
| qa31-article-diagnostic20-consumer-v3 | 20 | 20 | 0 |
| qa31-article-full-consumer-v3 | 118866 | 118369 | 497 |

The full manifest seal is
`deedec35930f618a4fa3975ada5c9ddfa45c21d74a0c7bfa025c4e6e38c70a28`.
The article-successor report's earlier "pending completion" wording is now
superseded by these observed seals/verification; its policy remains authoritative.
The497 overflows remain `needs_review_context`, without truncation or fabricated
factual rejection. A full118866 completed model-review claim is not yet possible.
Retrieval identity remains unverified; no-hit is not automatic rejection.

```bash
$PY -m dfm12.baltic_qa31_article_consumer verify --root data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3
$PY -m dfm12.baltic_qa31_article_consumer verify --root data/dfm13/baltic/qa31-article-full-consumer-v3
# After owner grants the pinned diagnostic authorization:
$PY -m dfm12.baltic_qa31_article_consumer run --root data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3 --authorization "$QA_DIAGNOSTIC_AUTHORIZATION" --concurrency 4
$PY -m dfm12.baltic_qa31_article_consumer calibration-report --root data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3
# ONLY after new article-aware semantic approval plus bulk authorization:
$PY -m dfm12.baltic_qa31_article_consumer run --root data/dfm13/baltic/qa31-article-full-consumer-v3 --authorization "$QA_BULK_AUTHORIZATION" --concurrency 4
```

[Epicurus's article-aware protocol](dfm13_baltic_qa31_article_successors_20261003.md)
owns repair/re-audit, calibration and context disposition. This linked note is
the coordination handoff; no direct agent-message channel is available here,
and no acknowledgment or permission is implied. No consumer edit was made.

## Production capacity: historical missing launcher (now resolved above)

The entire missing-implementation discussion in this historical subsection is
superseded by the current executable sequence immediately below; it is retained
only as dated diagnosis. Its proposed/unimplemented wording is not current status.

### Current capacity workload and lifecycle

Use `data/dfm13/gemma31-capacity-workload-20261003-v4` only. Capacity workload-v1,
v2 and v3 are historical, preserved and not repinned; do not launch them. This does
not supersede unrelated balanced-execution-v2 or Fars-capacity-v2 roots.
The current driver is `dfm12.wave31_capacity_measure`; its lifecycle is
`dfm12.wave31_server_lifecycle`, with Boole's actual receipt-directory format.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
# Current CPU-only command; no GPU or HTTP calls:
$PY -m dfm12.wave31_capacity_measure verify --root data/dfm13/gemma31-capacity-workload-20261003-v4

# NOT executed: only after authorized audit/client drain and exact-owned release.
# All eight GPUs and API/internal ports must be free; root must NEVER exist.
setsid "$PY" -u -m dfm12.wave31_server_lifecycle ramp \
  --root "$NEW_RAMP_ROOT" --max-num-seqs 16 --aggregate-concurrency 8 \
  > "$EXTERNAL_SUPERVISOR_LOG" 2>&1 < /dev/null &

# ONLY after actual all-eight readiness and pinned measurement authorization:
$PY -m dfm12.wave31_capacity_measure run --root "$NEW_PLATEAU_ROOT" \
  --workload data/dfm13/gemma31-capacity-workload-20261003-v4 \
  --server-receipt "$NEW_RAMP_ROOT" --authorization "$MEASUREMENT_AUTHORIZATION" \
  --concurrency 8 --duration 300 --poll 2
```

Actual CPU proof:32 complete native prompts, maximum32738/32768 tokens; manifest
SHA256 `2ac489ee2f440b522756276dc3807807eb4a1eba86c0a8f36c878aa421fc3fe6`.
Keepalive mirrors production; unique top-level cache salts prevent repeated
prefix reuse without changing input text/tokens. This measures conservative
uncached pressure, not ordinary production cache-hit distribution.53 focused
mocked tests passed; all32 v4 requests and pins verify. Main's earlier independent
32-request/25-test check covered v3, now superseded by the two reviewed fixes.
Ownership snapshots remain evidence, not immutable authorization pins. Timed
plateau, drain and total completions/rates/latencies are now distinct; tail
completions cannot inflate the300-second served rate.

Remaining runtime prerequisites:

1. Main completes the exhaustive source-audit/client drain and authorizes release
   of the previous lifecycle. No foreign servers or training are interrupted.
2. Owner launches the new ramp lifecycle with free devices/ports and obtains
   current all-eight readiness, exact snapshot/model, actual sequence settings,
   fresh status and readable owned logs.
3. Owner reserves endpoints exclusively and issues measurement authorization
   binding the v4 manifest and immutable configuration/command/endpoint bundle.
   Ownership snapshots are retained, with separate PID/start-tick/argv checks.
   No other clients may be stacked on the eight-request initial allocation.
4. The driver collects real>=300-second all-eight telemetry and drains safely.
   The profile is selected only after reviewing errors, preemptions, sampled KV,
   OOM logs, latency and workload coverage. No approval is auto-generated.
5. Subsequent production still needs the separately reviewed capacity profile,
   measured aggregate allocations and existing semantic/comparison approvals.

Exact authorization hash construction and evidence contract:
[measurement handoff](dfm13_31b_capacity_driver_interface_20261003.md).
No live measurement, server launch or approval was performed for this update.

### Preserved historical diagnosis

Comparison max-seqs8 is intentional, not a measured production ceiling.
Current executable paths were checked:

- `wave4_gemma31_transition.serve` forcibly sets max-seqs8 and has no config/profile CLI.
- `wave31_capacity --profile ... --output ...` validates real measurements and
  emits JSON explicitly marked `not_a_launch_command`; nothing consumes that
  file to start a configured31B lifecycle.
- `scripts/serve_dfm13_shared.py` has root/client-concurrency arguments only,
  retains26B source model/alias and hardcodes1024 sequences. It cannot serve as
  the proposed measured31B launcher without an isolated adaptation.
- `wave31_production run --capacity-profile` is implemented on both staged-v3
  roots. It checks measured allocations and separate all-group quality approval,
  but does not launch or reconfigure servers. Endpoint health verifies model,
  snapshot and context, NOT that live max-seqs matches the measured profile.

Thus the client/profile leg is executable, but the documented owned server ramp
and measured restart are NOT end-to-end executable through an existing31B CLI.
Do not launch production on the max-seqs8 comparison lifecycle while claiming
that a larger profile has been applied. No production capacity measurements or
valid profile are claimed by this CPU review.

Proposed minimal follow-up, NOT implemented: `dfm12/wave31_server_lifecycle.py`
and `tests/test_wave31_server_lifecycle.py`, reusing owned lifecycle machinery without changing frozen
transition/production. It must use the pinned31B snapshot/sole alias, accept
bounded explicit nonadmitting ramp settings before measurements exist, validate
`--capacity-profile` for production, record actual settings/ownership, enforce
free-device/port checks and exact-owned cleanup, and validate endpoint health.
A narrow first adapter can keep TP1, memory.95, context32768, batched-tokens16384
and native parser/compilation settings fixed, exposing only max-seqs plus the
recorded client allocation. This avoids pretending the existing profile validator
measures an arbitrary changed prefill configuration.
A profile-only launcher would deadlock the initial ramp. Measurement workload
and real all-eight-server telemetry still must be supplied; no existing automated
ramp/measurement driver was found in the inspected31B modules.

After that capability exists and real ramp review/quality approval complete:

```bash
$PY -m dfm12.wave31_capacity --profile "$MEASURED_PROFILE" --output "$PRODUCTION_SERVER_CONFIG"
# After exact-owned comparison/ramp drain, use a NEVER-existing root:
$PY -m dfm12.wave31_server_lifecycle production --root "$NEW_PRODUCTION_SERVER_ROOT" --capacity-profile "$MEASURED_PROFILE"
# This is a blocking supervisor; launch detached as documented, then require all8 live-ready.
# Separate client commands after readiness and quality approval:
$PY -m dfm12.wave31_production run --root data/dfm13/wave4/synthetic31-full-staged-v3 --capacity-profile "$MEASURED_PROFILE" --concurrency-per-server "$WAVE4_ALLOCATION"
$PY -m dfm12.wave31_production run --root data/dfm13/baltic/synthetic31-full-staged-v3 --capacity-profile "$MEASURED_PROFILE" --concurrency-per-server "$BALTIC_ALLOCATION"
```

Each root separately requires `comparison-reviewed-approval.json`. Allocations
share one measured aggregate; held-source/other clients cannot be added on top.
[Capacity measurements and LB supply](dfm13_31b_capacity_and_lb_supply_20261003.md)
remain separate from semantic approval and finite-source yield limitations.
