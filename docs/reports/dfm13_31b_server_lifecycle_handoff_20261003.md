# Isolated31B lifecycle: launcher and measurement-driver contract

Implementation: `dfm12/wave31_server_lifecycle.py`; mocked tests:
`tests/test_wave31_server_lifecycle.py`. Frozen transition, production, shared
launcher and cleanup files are unchanged. No GPU probe, real HTTP request,
server/client launch or signal was performed during implementation/testing.
Actual downloaded snapshot metadata was checked on CPU through `configuration`.
Final focused suite: **42 passed** (lifecycle, existing capacity and historical
handoff tests). The actual ready receipt passed
`configuration('ramp', DOWNLOAD/'ready.json', max_num_seqs=16, concurrency=8)`
with schema `wave31-server-lifecycle-v1`, revision
`842da3794eaa0b77d5f08bae87a17459d91ff475`, context32768 and prefill16384.
`serve` was not called. OKF validation has zero errors/warnings.

## CLI

From the repository root, AFTER the owner explicitly drains/releases the previous
lifecycle. This launcher never stops or adopts old/foreign servers. All eight
GPUs and sixteen ports must be free. Each trial needs a NEVER-existing root;
even an empty existing root is refused. Do not put shell redirection inside the
new root before launch. The following commands have NOT been executed:

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
# Nonadmitting ramp trial; only max-seqs16/32/64/128 are permitted.
# Aggregate concurrency must be1..min(64,max-seqs); this records a budget,
# it does not launch clients or automatically enforce external allocations.
setsid "$PY" -u -m dfm12.wave31_server_lifecycle ramp \
  --root "$NEW_RAMP_ROOT" --max-num-seqs 16 --aggregate-concurrency 8 \
  > "$EXTERNAL_SUPERVISOR_LOG" 2>&1 < /dev/null &

# Separate fresh lifecycle AFTER actual measurements and ramp review:
setsid "$PY" -u -m dfm12.wave31_server_lifecycle production \
  --root "$NEW_PRODUCTION_SERVER_ROOT" --capacity-profile "$MEASURED_PROFILE" \
  > "$EXTERNAL_PRODUCTION_LOG" 2>&1 < /dev/null &
```

`--ready` optionally selects the verified31B download receipt; default
`data/dfm13/wave4/gemma31-download/ready.json`. There is no arbitrary model path
or alias override. Production validates the existing measured-profile protocol,
requires matching revision/snapshot, and forbids ramp overrides. A profile is
NOT required for the initial ramp; that would circularly require unmeasured
capacity to be measured already. Independent production quality approval remains
the existing client's responsibility. No lifecycle grants data admission.

Fixed settings: TP1, utilization.95, context32768, batched tokens16384,
native gemma4 tool/reasoning parsers and compilation defaults (no enforce-eager).
Only `google/gemma-4-31B-it` is advertised. GPU UUIDs, API ports8800..8807 and
internal ports32000..32700 match the established shared-eight pattern.
Normal stop is this new root's `stop.request` file or SIGTERM to its exact owned
supervisor. Cleanup uses recorded start identities and private sessions; session
discovery requires a still-live exact anchor, otherwise the inherited unguessable
owner token. No process-group/foreign PID signals are introduced. Cleanup failures
do not skip other owned sessions and surviving/uncertain PIDs remain explicit.

## Stable receipt contract for Epicurus

All paths below are under the chosen new root. These are actual runtime outputs,
not substitutes for server execution. JSON is atomically written.

| Path | Required contents / use |
| --- | --- |
| configuration.json | schema=wave31-server-lifecycle-v1, mode, sole model, resolved snapshot, revision, max_num_seqs, aggregate_client_concurrency_per_server, client_allocations, fixed settings, input/code pins, launcher_sha256 |
| commands.json | List of eight records: command (actual Popen argv), pid, endpoint, gpu_uuid, internal_port, log_path, ownership_path |
| gpu0..7/ownership.json | owner token, server_session, created_at, owned process identities (PID/create_time/start_ticks/session_id/cmdline), actual command, endpoint, GPU index |
| gpu0..7/server.log | Actual server stdout/stderr; driver may inspect startup settings, errors and OOM evidence |
| ownership.json | Aggregate list of the eight ownership records, refreshed by supervision |
| endpoints.json | sole model/source_model, snapshot/revision, mode, actual max_num_seqs, max_model_len, memory utilization, endpoint/metrics URLs, aggregate budget/allocations, supervisor identity |
| ready.json | all_eight_verified=true only after all eight strict model/snapshot/context checks; full /models documents, time, snapshot, actual max_num_seqs; admission_authorized=false |
| status.json | Current time, eight readiness flags, phase, exit codes; refreshed every10seconds |
| gpu0..7/cleanup.json | Exact cleanup actions and survivors; cleanup-error.json records exceptional cleanup failures |
| stopped.json | Completion time, only_owned_cleanup, cleanup_survivors; always disqualifies this lifecycle from active measurement |

For each endpoint, the measurement driver should bind its actual command and
ownership/log paths, verify the configured31B snapshot, exactly one served alias,
max-model-len32768, selected max-num-seqs and fixed prefill settings, then check
live endpoint health. `/models` does NOT itself prove max-seqs. Verify current
owned process identities and fresh `status.json`; an old `ready.json` alone is
not live readiness. Reject a stopped root or cleanup survivors. Raw `/metrics`
URLs are recorded per endpoint as `http://127.0.0.1:PORT/metrics`.

`measurements_generated=false` and `measured_throughput_claimed=false` are
intentional. This launcher does not synthesize completions, KV utilization,
preemption, OOM or latency measurements. Epicurus's separate driver owns the
bounded workload, raw metrics/log collection and measurement receipts. Bind the
exact lifecycle configuration/command/ownership hashes and actual time window.
No driver acknowledgment or real capacity approval is claimed here.

Model provenance uses the prior hash-verified download receipt, fresh config/index/
tokenizer-config hashes and current shard presence/sizes. It does NOT claim to
rehash60GB of weights on each trial. The canonical snapshot must match the
capacity validator's verified snapshot in production mode.
# Later Cache-Isolation Update, 2026-10-03

Following main's reported retry1 missing-cubin failures on GPUs6/7, the future
lifecycle isolates VLLM_CACHE_ROOT, TORCHINDUCTOR_CACHE_DIR, TRITON_CACHE_DIR and
CUDA_CACHE_PATH beneath each fresh root/compile-cache/GPU-UUID directory.
commands.json records these actual environment paths. This unfrozen module had
no references in the inspected data/dfm13 manifest/seal/configuration pins; no
sealed roots were changed.64 combined transition/lifecycle/capacity tests pass,
including cache paths for all eight mocked GPUs and wrapper restoration after
failure. No live launch was performed by this update. The separate main-owned
retry2 wrapper and historical final handoff contract were not edited here.
