---
type: Runbook
title: Nonadmitting 31B Capacity Measurement
description: Frozen native workload, cache-isolated pressure and measured all-eight endpoint evidence without server lifecycle or admission.
status: draft
confidence: high
last_updated: 2026-10-03
---
# Nonadmitting 31B Capacity Measurement

`dfm12.wave31_capacity_measure` provides CPU prepare/verify and a separately
authorized measurement CLI. It does not launch, restart or kill servers. Boole's
`wave31_server_lifecycle` owns those operations. No live31B calls or actual
capacity measurements were made during implementation.

Current frozen workload: `data/dfm13/gemma31-capacity-workload-20261003-v4`.
It contains32 native requests:24 balanced frozen generation requests across all
six families and both waves, plus four long held-source QA and four full Fars
requests. Actual tokenizer preflight includes output reserve, with no shortening
or truncation; maximum total32738/32768 tokens. Existing manifests, production
code and earlier workloads are preserved; v1/v2/v3 are superseded, not repinned.

## Prefix Cache and Transport

Repeated synthetic measurement prompts must not be mistaken for unique-workload
capacity: prefix-cache reuse can inflate apparent KV/throughput headroom.
Installed audit vLLM0.27.1 exposes `cache_salt` at
`entrypoints/openai/chat_completion/protocol.py:453` and validates a nonempty
string at973. `renderers/online_renderer.py:373,432` passes it into rendering;
`renderers/base.py:795,858` carries it into engine inputs. At
`v1/core/kv_cache_utils.py:579` it enters the first-block hash and thus the prefix
chain. These installed files are pinned in the workload.

The driver adds a unique per-run/per-endpoint/per-sequence top-level cache salt
to a cloned wire payload, never a nonce in input text. Frozen case/request and
wire hashes are separate, and native token IDs/counts are unchanged. This is a
conservative uncached-prefix pressure test, not an estimate of production cache
hit distribution or proof that32 repeated contents represent all production.
Current keepalive request pools and a separate metrics client match
`multilingual_quarter.py:516-519`; the earlier force-close draft is superseded.

## Measurement Contract

Use a fresh root per plateau. Explicit authorization binds the workload and
actual immutable lifecycle configuration/commands/endpoints bundle; source
audits must be drained and endpoints exclusively allocated. Read-only process,
fresh status and strict `/models` checks cover all eight ports8800..8807.
Actual max-seqs comes from both launch receipts and live argv, not `/models`.
Aggregate clients are bounded at64/server and cannot exceed actual sequence
capacity. No separate dataset client allocations may be stacked on this probe.

At least300 seconds of dispatch precedes graceful drain. Signals only stop new
local dispatch; in-flight requests finish or reach their bounded timeout.
Metrics continue through drain: sampled KV high-water, preemption/completion
counters, request errors and nearest-rank successful-request p95. Timed plateau
and drain completions, rates and latency summaries are separate; their
denominators match their actual time windows. Ownership files may grow as
descendants are discovered: snapshots remain evidence, not authorization pins;
actual PID/start ticks/argv are checked independently. Unknown
completion, reset/stale/missing telemetry, foreign traffic or missing log evidence
invalidates the plateau. Exact server-log byte ranges and OOM matches are copied
even when a server dies. Raw payloads, responses, outcomes and telemetry are
hash-indexed. No semantic quality, training admission or upload is inferred.

The measurement schema is compatible with `wave31_capacity`, but the driver
never writes selected-after-ramp-review approval or a production capacity
profile.51 focused mocked tests pass. No fabricated live evidence is used.

Later CPU recheck,2026-10-03: all v3 manifest pins still verify;32 requests and
maximum32738 tokens are unchanged. An additional mocked `run()` integration
test checks actual keepalive/per-host limits and a distinct telemetry connector;
the focused suite now passes52 tests. Only tests/documentation changed, with no
driver edit, root reseal, real measurement or GPU call.26B audits are untouched.

The final root matrix and operational handoff now explicitly name workload-v3
and the new owned lifecycle, with the exact CPU verify command. Workload-v1/v2
are historical only. Runtime still requires main's exhaustive audit drain and
release, actual all-eight owned31B readiness, exclusive allocation, hash-bound
measurement authorization and real>=300-second evidence before profile review.

**V4 supersession after independent review,2026-10-03:** the earlier active-v3
instructions are historical. V4 fixes mutable ownership-file pinning and the
plateau-versus-drain completion denominator.53 focused tests pass, including
ownership growth and known timed/tail rate examples. The32 requests remain
byte-identical tov3 and all actual native preflights/pins verify. V3's exact
driver was archived, not repinned. The final matrix and operational commands now
point at v4; no GPU work, actual capacity evidence or approval was introduced.

Exact commands, bundle hash construction, source bindings and limitations:
`docs/reports/dfm13_31b_capacity_driver_interface_20261003.md`.
Held QA inputs are described in [Baltic QA31 Consumer](dfm13-baltic-qa31-consumer.md).

## Source Drain Check

Read-only2026-10-03 19:51 UTC inspection found58110 pending first audits,
3428 running and59 repair re-audits running. Baltic queues were terminal;
10659 Fars generation jobs remained explicitly deferred31B, not completed.
Slovak additive enqueue is complete but its final completion receipt is absent;
the old waiting-main-freeze label is stale because the combined manifest exists.
Live enqueue-capable controllers and clients still require an actual owner
freeze/drain contract before transition. This snapshot grants no release or
capacity approval. Exact conditions and the existing check/transition commands:
[transition readiness](../../docs/reports/dfm13_31b_transition_readiness_20261003.md).

Later19:55 UTC: both Wave4 queues are terminal except the authorized10659
deferred31B jobs. The additive controller still interleaves synchronous HF
publication with selection; a reported HF quota retry therefore blocks later
materialization. Tesla owns decoupling. HF upload completion must not gate GPU
release: require complete selection, drained resulting recoveries and frozen
enqueue-capable producers, with publication tracked separately. Terminal queue
counts alone do not establish that freeze; no transition was executed here.

Owner-review inventory now exists at
`data/dfm13/wave4/handoff-inventory-1791057751957038611/contract-draft.json`
with both attestations false, plus exact process evidence in its sibling JSON.
It fails closed as intended. An additional executable-check blocker was found:
transition `alive()` does not catch the identity helper's `psutil.NoSuchProcess`
for exited clients. Resolve explicitly before final handoff checking; no code
change or repin was made by this inventory pass. See the readiness report above.

Superseding fix: isolated `wave4_gemma31_transition_exited` catches only
NoSuchProcess around the privately loaded original alive check. Nine focused
tests pass; pinned original transition/identity modules and frozen roots remain
unchanged. Use the successor CLI for final check/transition. Monitor2111503 is
a client-restart producer, not a passive observer; corrected draft inventory
requires its exit before freeze. Neither correction grants freeze authorization.

## Executed Handoff, 2026-10-03

Supersedes the pending-freeze state above: main reports exact-owned freeze of
2111503,2355940,2365731,2607843,2642708 after proof that all410 Slovak components
were terminal. Main's final contract is
`data/dfm13/wave4/handoff-final-20261003.json`; its check passed and main launched
`dfm12.wave4_gemma31_transition_exited` detached with setsid. Log:
`logs/dfm13/wave4/gemma31-transition-20261003.log`.

Read-only confirmation found both contract attestations true and the actual
`logs/dfm13/wave4-gemma31-comparison/release-request.json`, binding contract SHA256
`770d60d6c305fd11c977f472f329745e427771650b1188d94bb387a648c294fb`
and exact old supervisor1856648. Its queue evidence has no pending/running work;
10659 Fars jobs remain authorized deferred31B, not completed reviews. At this
inspection neither launch.json nor comparison-terminal.json existed: transition
was initiated, not yet proven31B-ready or comparison-complete. No capacity or
semantic approval is implied. HF publishers and unrelated CPU tokenizers remain
outside this freeze; no process actions were taken by this documentation pass.

### First Startup Failure and Standalone Retry

Later update from main: CPU handoff and exact-owned old-server shutdown
succeeded. First serve PID2646237 failed with EADDRINUSE; transition parent
2645634 terminated before executing the76 comparisons. Main subsequently found
no LISTEN sockets and successfully tested plain binds on all16 required ports.
Those observations do not establish the cause of the earlier bind conflict.

Main launched a standalone serve retry using the fresh
`logs/dfm13/wave4-gemma31-comparison/servers-retry1` root, with log
`logs/dfm13/wave4-gemma31-comparison/server-supervisor-retry1.log`.
The original launch.json now exists but is not evidence that the first serve
became healthy. The transition's automatic comparison step did not run. After
all-eight retry health is verified, main will manually run the exact comparison
client once;76 comparisons remain unexecuted as of this update. Preserve both
attempts' receipts/logs. No other server changes, GPU requests or process actions
were performed by this documentation pass.

### Retry1 Compile Failure and Cache Isolation

Main reports retry1 failed compilation on GPUs6/7 with missing CUDA cubin files
in the shared cache; the owned supervisor cleaned up all its servers. Main added
per-GPU, per-run VLLM_CACHE_ROOT, TORCHINDUCTOR_CACHE_DIR, TRITON_CACHE_DIR and
CUDA_CACHE_PATH to the isolated transition-exited wrapper and launched retry2.
This does not yet prove retry2 health or comparison completion.

Focused mocked tests now exercise distinct GPU cache directories, unchanged
command/other environment, and restoration of the wrapper's command helper on
both normal return and startup failure. The future wave31_server_lifecycle now
has equivalent root/compile-cache/GPU-UUID isolation and records the four actual
environment paths in commands.json. No reference to that lifecycle file was
found in data/dfm13 manifest/seal/configuration pins before its edit. The live
retry2 wrapper was not modified by this test/lifecycle pass.64 combined focused
tests passed; no GPU requests or process actions were performed here.

The final handoff contract's old wrapper hash is historical evidence for the
executed freeze/initial transition, not a valid pin for the changed retry2 wrapper.
Do not rewrite that contract or original sealed roots. A future authorization
must bind the actual successor code; the future lifecycle already records its
launcher hash when creating a fresh configuration receipt. Cache isolation is a
startup mitigation, not measured capacity approval or proof of semantic quality.

### Retry2 Healthy and Comparison76 Completed

Main confirmed all eight retry2 endpoints passed exact31B snapshot and32768
context health checks. Compilation and CUDA graphs remain enabled; per-GPU
caches were retained. The observed serve PID2651445 command was:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.wave4_gemma31_transition_exited serve \
  --root logs/dfm13/wave4-gemma31-comparison/servers-retry2 \
  --model-path /home/ucloud/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/842da3794eaa0b77d5f08bae87a17459d91ff475
```

Main manually launched the76 audit client at8/server after health. Read-only
inspection now confirms jobs.sqlite has76 done and no other statuses; client
completion.json records76 done and0 request_errors at1791059070.2521636.
Client owner receipt records PID2655271. Log:
`logs/dfm13/wave4-gemma31-comparison/client.log`.
The equivalent existing client invocation is recorded below for reproducibility,
NOT an instruction to rerun completed work (manual launch did not leave a
client-command.json, so exact shell argv was not independently recovered):

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.european_stage \
  --database data/dfm13/wave4/gemma31-quality-comparison/jobs.sqlite \
  --stage audit --output logs/dfm13/wave4-gemma31-comparison/client \
  --concurrency 8 --max-concurrency 8 \
  --endpoint http://127.0.0.1:8800/v1 --endpoint http://127.0.0.1:8801/v1 \
  --endpoint http://127.0.0.1:8802/v1 --endpoint http://127.0.0.1:8803/v1 \
  --endpoint http://127.0.0.1:8804/v1 --endpoint http://127.0.0.1:8805/v1 \
  --endpoint http://127.0.0.1:8806/v1 --endpoint http://127.0.0.1:8807/v1
```

This supersedes the earlier unexecuted-comparison state. Technical completion
is not semantic approval or a production capacity measurement. This update made
no cache, server, GPU-request or process changes.

### Capacity Launch After Balanced Comparison

Rechecked after retry2 success: workload-v4 has no wave31_server_lifecycle pin
and still verifies all32 requests. Its manifest remains
`2ac489ee2f440b522756276dc3807807eb4a1eba86c0a8f36c878aa421fc3fe6`.
The future lifecycle already contains tested per-GPU compile-cache isolation;
no adapter or frozen-workload repin is needed. At this check its source SHA256 is
`bd51dc4e1ad59bcae6ffebd4bae43c41f62099e09f54eb942f96a5af14592b14`.

After balanced GPU calls drain, the owner must release the exact-owned retry2
lifecycle before starting a fresh ramp root. Existing retry2 receipts are not
the capacity driver's lifecycle bundle: do not fabricate configuration.json or
adopt those processes. Use existing wave31_server_lifecycle ramp with
max-num-seqs16 and aggregate-concurrency8, then wait for all-eight readiness.
The existing documented capacity run uses concurrency8/duration300/poll2 and
requires owner authorization bound to workload-v4 and the new immutable bundle.
Independent CPU semantic review may continue during measurement; other GPU
clients must not share the endpoints. No real measurement or lifecycle action
was performed for this CPU recheck.

### First Real Measurement Launched

### Bounded Repair25 CPU Follow-up (2026-10-03)

Latest bounded concurrency update: explicit all-eight request supersedes the
sequential26B-v1. New `data/dfm13/gemma26-repair25-20261003-v2` is pinned with
eight workers, one case/request per server;54tests pass including raw-ID
uniqueness and stop/error drain. No bulk admission. Main authorized launch only
after Epicurus confirms26B readiness; confirmation remained pending at this
CPU handoff and no GPU client had launched. Original outputs stay unchanged.

Later same-day model-choice update supersedes the31B-only launch assumption:
main reports user questioning31B, no31B bulk authorization and default26B while
choice is pending. `dfm12/synthetic_repair_pilot.py` supports explicit26b/31b,
defaults new preparations to26b, and refuses switching a sealed root in place.
New `data/dfm13/gemma26-repair25-20261003-v1` passed25-case CPU preflight;
75 request budgets per teacher and51combined tests passed. The original31B
module/root remain unchanged and verify successfully. No GPU client was
launched; execution awaits main coordination. The handoff below records the
current model-specific commands and distinguishes capacity-drain sequencing
from cross-model capacity approval.

User authorized a one-shot repair and fresh re-audit of the25 independently
repair-recommended balanced keeps, after capacity measurement. New isolated
`data/dfm13/gemma31-repair25-20261003-v2` is CPU-prepared and pinned, not launched;
v1 is preserved/superseded after tightening blind-audit metadata removal.
`dfm12/wave31_repair_pilot.py` protects native tool structure, exact code/literals
and full4096 student targets. Fresh strict and native/source audits see no old
verdict or repair reason; same31B passes remain provisional, not independent
certification or production approval. All25 preflights and28tests pass.
Future command, capacity-drain prerequisite and exact receipt:
`docs/reports/dfm13_repair25_cpu_handoff_20261003.md`.
No GPU client or server action was performed by this preparation.

### First Measurement Launch Evidence

Main subsequently launched the cache-isolated ramp at
`logs/dfm13/gemma31-capacity-ramp-cacheisolated-20261003-v1` (PID2669751),
max-num-seqs16, aggregate allocation8/server. Its local status receipt confirms
all eight ready and no exited server processes. Main issued
`data/dfm13/gemma31-capacity-authorization-20261003-v1.json` and launched actual
measurement PID2674820, concurrency8, duration300, poll2, using workload-v4.
Output root: `data/dfm13/gemma31-capacity-measurement-20261003-v1`.
Log: `logs/dfm13/gemma31-capacity-measurement-20261003-v1.log`.

At the initial read-only observation the client was alive, the log empty and
the measurement root contained only its lock: no dispatch/completion evidence
or measured capacity result was yet claimed. Endpoints are exclusive until
measurement and drain complete. This monitoring pass used only local files and
process listing, with no endpoint calls, signals or other GPU work.

### Terminal Measurement and26B Default

Measurement-v1 is terminal, not crashed: measurement.json/seal and the client log
record1730/1730 total completions (1666 during the300-second plateau),72.47 seconds
drain, evidence_complete=true, zero request errors/OOM/preemptions. Maximum
sampled KV30.38%; per-server plateau p95 spans25.05-31.40 seconds. Six requests
finished at length. The last progress snapshot on8807 was stale203/204; the
terminal record reconciles204 there. Capacity/admission/publication remain false.

31B was a bounded comparison and capacity experiment, NOT an approved production
replacement. Benefit over26B has not been established;26B remains default bulk.
No additional ramp is planned. The owner-executed
[safe26B switch-back procedure](../../docs/reports/dfm13_26b_switchback_20261003.md)
checks exact supervisor identity, uses its stop.request and verifies owned
cleanup before a fresh compiled26B replicas launch. The procedure was prepared,
not executed here; unrelated HF publishers and CPU tokenizers are untouched.

### Authorized26B Switch-back Executed

Later main delegated execution. Verified no matching active GPU clients, all8
running/waiting metrics zero, and exact31B supervisor2669751 identity. Requested
owned cleanup; stopped receipt confirms only_owned_cleanup=true and zero
survivors. Verified GPUs and all16 ports free, then launched26B supervisor2687874
via `python -u -m scripts.serve_dfm13_26b_isolated --root logs/dfm13/gemma26-compiled-switchback-20261003-v1`.
This isolated wrapper reuses the established replicas entry point and adds only
per-run/GPU cache paths; two focused tests pass. Original launchers and sealed
roots are unchanged. Launch receipt/log use that root prefix with -launch.json
and .log suffixes. Actual argv/environment on all8 child servers verified
max-seqs1024, memory.95, context32768, compilation enabled and all four cache
variables isolated by GPU UUID. Startup is in progress; health is not yet
claimed. No bulk clients, training or unrelated process changes were performed.

Switch-back readiness subsequently confirmed on all8 endpoints8800..8807:
google/gemma-4-26B-A4B-it, exact snapshot4d7ae4984b7db7de8f8457170b3f1a419ee76d52,
32768 context. Actual server settings remain compiled/graphs enabled,
max-seqs1024 and memory.95. Receipt:
`logs/dfm13/gemma26-compiled-switchback-20261003-v1/switchback-ready.json`,
including all model documents, per-GPU cache environment, supervisor identity
and prior zero-survivor cleanup.26B supervisor2687874 remains serving; no bulk
client was launched by this switch-back task. This supersedes startup-pending.

### Repair25 Terminal Result (2026-10-03)

Superseding the repair preparation/waiting status above, the authorized26B
repair client PID2695189 completed in fresh immutable root
`data/dfm13/gemma26-repair25-20261003-v3`:25/25 terminal,37 raw HTTP responses,
six re-audited cases and three provisional keeps.18 repairs failed protected
content checks (13 code/JSON,5 numerical answer); one failed repeated-text-loop
without retry. These are validator outcomes, not independent semantic findings.
No admission/publication/bulk approval is granted. Independent inspection is
pending.55 focused tests passed; post-run pinned verification returns25.
V2 is preserved and fails closed on its old implementation pin; do not relaunch
it or patch its seal. V3 narrowly permits the known served alias only alongside
the canonical selected model with identical snapshot/context. No client is
currently live. See the [launch/result handoff](../../docs/reports/dfm13_repair25_launch_coordination_20261003.md)
for PID, log and per-case evidence paths.

### Content Review Follow-up

The [bounded content review](../../docs/reports/dfm13_repair25_content_review_20261003.md)
supersedes independent-inspection-pending for the six materialized repairs.
Of three automated keeps, BE magnet has no material issue found; LT NLP and
SL carrots retain language defects. Failed outputs include missing code/JSON
and malformed box syntax, not merely equivalent formatting. No artifacts or
admission flags changed. This selected repair cohort does not establish general
bulk quality rates: continue independently authorized bulk with existing gates,
but do not enable this experimental repair path for automatic admission.
