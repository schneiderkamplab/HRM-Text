# 31B handoff CPU dry run

## Superseded operational status, later 2026-10-03

The results below are preserved historical CPU observations, NOT the current
launch checklist. Their missing-gate claims and launch roots are superseded by
the [current operational sequence](dfm13_31b_operational_handoff_20261003.md)
and [final root matrix](dfm13_31b_final_root_matrix_20261003.md).

- Gate1 resolved in code: transition now invokes the shared strict model,
  snapshot and advertised-context validator before its automatic76 dispatch.
- Gate2 resolved by `dfm12.wave31_balanced_run`; the preparation module still
  correctly has no run CLI. Use source-v4/execution-v2, not source subdirectories.
- Gate3 resolved for CPU packaging: the final89296 Fars capacity-v2 consumer
  exists. Actual launch authorization, shared-resource handoff and quality gates
  remain separate; this is not a claim that every live producer has drained.
- Gate4 resolved by the health-gated, eight-endpoint `latvian_p3_dispatch` and
  calibrated blind-v2 workflow. Pairing calibration remains pending.
- Fresh roots are now wave4 comparison30-v5 and Baltic comparison12-v3;
  production roots are staged-v3. Article-aware QA successors also now have
  seals and pass CPU verification; see the linked operational sequence.

One concrete capability remains missing: a configurable owned31B production/
ramp server launcher. `transition serve` intentionally forces max-seqs8;
`wave31_capacity` emits configuration but does not launch it. The raw shared
launcher retains26B model/aliases and is not a substitute. No GPU action or
frozen implementation change was made during this documentation review.

**Resolved subsequently2026-10-03:** the isolated
[server lifecycle CLI](dfm13_31b_server_lifecycle_handoff_20261003.md) implements
that missing launcher with mocked tests. The preceding observation is preserved
as history. Comparison max-seqs8 and all frozen files remain unchanged; no actual
capacity measurement, server launch or production approval is implied.

No GPU queries, HTTP requests, process launches or signals were performed.
Tests use mocked Popen, socket binding, process identities, readiness responses,
signals and cleanup. The real shared-launcher command construction and the real
transition phase ordering are exercised. No frozen implementation was modified.

## Results

`tests/test_wave31_handoff_dryrun.py` plus transition tests: **13 passed**.
Captured commands: `data/dfm13/wave4/server-command-dryrun.json` (mock GPU UUIDs
and snapshot path deliberately marked; this is NOT a live health receipt).

All eight commands use the audit environment's Python, vLLM API server, verified
snapshot argument, only `google/gemma-4-31B-it` as served alias, TP1, memory .95,
max context32768, max sequences8, batched tokens16384, native gemma4 tool and
reasoning parsers, compilation defaults (no enforce-eager), ports8800..8807 and
distinct VLLM_PORT32000..32700 in increments100. No old26B alias survives.
Mocked endpoint metadata agrees with command construction. Actual memory fit,
startup and native inference remain untested until authorized handoff.

Mocked transition order: drain checks twice; exact-owned supervisor signal;
free-GPU gate; new supervisor; eight model readiness checks;76-review client;
terminal receipt. That transition already runs76; do not launch a second client.

## Historical incompatibilities and outstanding gates (superseded above)

1. Transition readiness verifies exclusively31B IDs but **not max_model_len or
   snapshot root** before its automatic76 dispatch. Command construction is32K,
   but advertised context verification is incomplete. Fresh42 subsequently
   checks32K and snapshot; Fars does too. Owner should add the same strict
   check before76, or provide a separately reviewed guarded dispatch. Do not
   conceal this by treating mock health as real health. If transition changes,
   reseal NEW fresh successors and recheck production pins; preserve originals.
2. Balanced234 verifies78 groups successfully, but its CLI has only prepare and
   verify. There is **no run entry point**. Its wave4/Baltic subdirectories are
   not fresh-runner roots (no per-wave manifests/config contract); passing them
   to fresh.run is not a valid shortcut. Owner must supply a minimal execution
   adapter preserving frozen234 requests and strict validation before launch.
3. Fars base77640 plus delta11656 =89296 preflighted requests, zero errors or
   oversize. This is not a finalized consumer catalog. Final held-generation
   freeze, latest superseding delta/preflight, consumer prepare and hash-bound
   launch authorization remain required. The earlier delta records an unfinished
   generation tail; do not assert that tail is currently terminal without check.
4. Latvian held-source consumer7680 has clean input pins, zero blocked prompts,
   max16070 including reserve and31B request aliases. It is sequential and lacks
   its own endpoint model/context health check. Use an explicit verified health
   gate, not an alias assumption. Repair enqueue requires independently reviewed
   pairing receipts; audit completion does not certify pairing or release holds.

## Historical ordered commands (do not use as current launch recipe)

These are future operator commands, NOT executed by this dry run. Set PY to
`/home/ucloud/miniforge3/envs/hrm/bin/python` and MODEL_PATH to the ready receipt's
snapshot. HANDOFF must be the final exhaustive drain/freeze contract, not the
deferral fragment. Resolve gates1-3 above before treating this as end-to-end ready.

```bash
$PY -m dfm12.wave4_gemma31_transition inspect
$PY -m dfm12.wave4_gemma31_transition check --contract "$HANDOFF" --model-path "$MODEL_PATH"
# After explicit handoff authorization only; starts servers AND runs76 reviews:
$PY -m dfm12.wave4_gemma31_transition transition --contract "$HANDOFF" --model-path "$MODEL_PATH"
# Require comparison-terminal.json; failed jobs stay failed, never imply quality.
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/wave4/gemma31-fresh-comparison30-v4
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/wave4/gemma31-fresh-comparison30-v4 --concurrency-per-server 2
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/baltic/gemma31-fresh-comparison12-v2
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/baltic/gemma31-fresh-comparison12-v2 --concurrency-per-server 2
$PY -m dfm12.wave31_balanced_calibration verify --root data/dfm13/gemma31-balanced-calibration-20261003-v2
# STOP: balanced234 execution command is not implemented. Do not invent run CLI.
```

Following balanced234 execution and independent comparison review, held-source
consumers use the same servers without restart. Run sequentially initially so
the limits below do not accidentally add across clients:

```bash
# CPU prepare requires final freeze, final superseding delta and its preflight:
$PY -m dfm12.fars_summary_consumer prepare --root "$FARS_CONSUMER" --packets data/dfm13/wave4/fars-summary-31b-packets-v1 "$FINAL_DELTA" --preflights data/dfm13/wave4/fars-summary-31b-preflight-v1 "$FINAL_DELTA_PREFLIGHT" --freeze "$FINAL_FREEZE"
$PY -m dfm12.fars_summary_consumer run --root "$FARS_CONSUMER" --authorization "$FARS_AUTHORIZATION" --concurrency 4
# Independently verify live endpoint model, snapshot root and32K first:
$PY -m dfm12.latvian_p3_review_consumer run --root data/dfm13/latvian-p3-content-alignment-20261003-v1/consumer-v1 --endpoint http://127.0.0.1:8800/v1 --tokenizer "$MODEL_PATH" --stage p3_source_fidelity_protocol_31b --limit 7680
```

MODEL_PATH must also match the Latvian pinned tokenizer path, not merely an
equivalent model name. Consumers preserve all prior evidence and holds. There
is no production admission, upload, quota change or automatic repair approval.
Comparison limits are not permanent production throughput limits.
