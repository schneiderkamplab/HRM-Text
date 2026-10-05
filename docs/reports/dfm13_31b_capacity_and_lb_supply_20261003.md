# Post-calibration production capacity and LB source supply

**Launcher implementation update, later2026-10-03:** the isolated
`dfm12.wave31_server_lifecycle` now supplies the previously missing owned31B
ramp/production CLI. See its [launch and measurement-driver receipt contract](dfm13_31b_server_lifecycle_handoff_20261003.md).
The next paragraph preserves the earlier gap finding. No frozen dependencies
changed; actual capacity measurements and approvals remain outstanding.

**Operational correction, later2026-10-03:** the v2 production roots and example
commands below are historical; final roots are both `synthetic31-full-staged-v3`
in the [final matrix](dfm13_31b_final_root_matrix_20261003.md). The measurement
policy remains valid, but step2 was a required owner action, NOT an implemented
configurable31B launcher. Current transition serving forces comparison max-seqs8;
the capacity emitter does not launch, and the raw shared launcher retains26B.
The [current executable sequence and missing-capability scope](dfm13_31b_operational_handoff_20261003.md)
explicitly stop before an unimplemented production server restart. No profile,
measurement, approval or frozen implementation was changed by this correction.

## Calibration is not the production ceiling

The existing bounded42generation/76review comparison and its server max-seqs8
remain unchanged. The earlier four-request/server production example was a
conservative bootstrap, NOT a permanent saturation policy. No31B production
throughput or capacity has yet been measured, so no saturation claim is made.

`dfm12.wave31_capacity` validates a separate post-calibration capacity profile
against hash-pinned all-eight-server measurements. Production runner now accepts
`--capacity-profile`; above8/server needs measured approval. Existing controller
supports up to64requests per client/server; this first profile supports aggregate
2..64/server allocated explicitly between wave4/Baltic. Server max-seqs is an
independent measured setting up to1024, never inferred from the old8-sequence
comparison config. Further controller-bound increases require measurement/tests,
not an unbounded default. No GPU/server/client changes performed in this task.

Current unapproved capacity-capable successor roots are
`data/dfm13/{wave4,baltic}/synthetic31-full-staged-v2`, retaining770K/140K and
all78groups. v1roots are superseded and preserved; never repin/resume them after
the implementation update. The v2roots have zero accepted rows and no comparison
approval. Their26B lineage/holds remain separate and unchanged.

## Measured ramp recipe after actual comparison approval

1. Finish bounded semantic comparisons and obtain genuine independently reviewed
   production approval. Capacity measurement does not replace quality approval.
2. Owner launches a NEW owned31B server lifecycle after exact-identity old-client
   drain, using the existing environment/model/context32768/utilization.95/TP1
   settings. For ramp trials vary only max-seqs/prefill settings explicitly;
   comparison servers/configuration are not silently repurposed.
3. Use a separate nonadmitting bounded workload of representative full prompts
   from every family, including long source/tool/review contexts. Start aggregate
   workers/server8, then16,32,64 if stable. Trial max-seqs16/32/64/128 as needed;
   these are candidate settings, not approved values. Use actual queued work so
   an empty producer is not mistaken for GPU capacity. No target truncation.
4. Warm up separately; measure each plateau at least300seconds. Record every
   endpoint's successful completions, elapsed time, KV high-water, preemption
   delta, request errors, OOM count, p95latency and GPU utilization. Preserve raw
   snapshots at short intervals, actual server commands/PIDs, model revision and
   aggregate worker allocations. Compare completions/minute, not busy flags alone.
5. Back off on OOM, errors, preemptions or KV above.90; never automatically kill
   unrelated work. Prefer the stable throughput plateau: increasing workers
   without useful completion gain is not saturation improvement. Choose capacity
   against the worst server/long-context workload, not average KV only.
6. Human/operator records the selected profile with measurement pins. Profile
   validation requires all8servers stable at the exact selected concurrency and
   max-seqs for5minutes, positive completions, zero preemptions/errors/OOM and
   KV high-water<=.90. No real profile/evidence is fabricated by preparation.

Measurement JSON interface (all8800..8807 required): `model`, `revision`,
`duration_seconds`, `servers`, each containing `aggregate_concurrency`,
`max_num_seqs`, `completed`, `kv_high_water`, `preemptions_delta`,
`request_errors_delta`, `oom_count`, `p95_seconds`. Record raw-snapshot provenance
alongside these summaries; the validator does not turn an unsupported hand-entered
summary into verified observations.

Capacity profile interface: `model`, `revision`,
`aggregate_client_concurrency_per_server`, `server_max_num_seqs`,
`client_allocations` with `wave4`/`baltic` whose sum fits the measured aggregate,
`measurements` list of `{path,sha256}`, `selected_after_ramp_review=true`, `reviewer`.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave31_capacity --profile MEASURED_PROFILE.json --output PRODUCTION_SERVER_CONFIG.json
# Owner applies the emitted server settings through its owned launcher; no launch here.
# Independently reviewed quality approval remains separately required on each root.
$PY -m dfm12.wave31_production run --root data/dfm13/wave4/synthetic31-full-staged-v2 --capacity-profile MEASURED_PROFILE.json --concurrency-per-server WAVE4_ALLOCATION
$PY -m dfm12.wave31_production run --root data/dfm13/baltic/synthetic31-full-staged-v2 --capacity-profile MEASURED_PROFILE.json --concurrency-per-server BALTIC_ALLOCATION
```

The capacity emitter writes a config, not a server launch command. The runtime
allocation receipt records requested profile pins; actual `runtime.json` and
server ownership/commands remain authoritative. Do not add comparison or other
clients on top of the measured aggregate without reducing allocations.

## Luxembourgish: measured offline alternatives

`dfm12.lb_seed_capacity` read all62,414 pinned downloaded Wikipedia documents
against the34,013existing LB seed documents. Results at
`data/dfm13/wave4/lb-seed-capacity-20261003`:

* **Zero new eligible unique documents** found under unchanged500..2400character
  window constraints. No invented additional corpus supply.
* **5,538 additional non-overlapping windows** found inside already represented
  documents. At most two additional windows/document, exact text hashes deduped
  globally against the existing windows and each other. Exact parent IDs, source
  revision/hash, offsets/endpoints and URLs retained. These are candidate views,
  not new documents and not independently verified native quality.
* **12,479 documents of300..499characters** identified but NOT admitted. Do not
  weaken full-task source sufficiency just to count them.

Original HF Wikipedia card licenses were checked at the pinned revision:
CC-BY-SA-3.0/GFDL. Candidate provenance retains CC-BY-SA-3.0; separate license
evidence receipt records both. LuxIT is existing Wikipedia-derived instruction
data, not independently novel native document supply; it was not counted again.
Unresolved parliamentary/NC-license sources were not silently admitted.

If independently screened windows are useful, an explicit bounded varied-view
policy can add these to a NEW seed inventory: parent-document identity retained;
maximum3views including original per document/family; distinct non-overlapping
evidence windows; require semantically distinct tasks/subtypes per parent where
applicable; exact and near-duplicate candidate rejection; no identical-evidence
paraphrase churn. SourceProvider currently uses distinct source IDs, so any
integration must explicitly encode view IDs plus parent caps and update provider
policy/pins rather than disguising windows as unique documents. **This study does
not modify providers or append any window to production.**

Maximum provisional LB views39,551 would lower the necessary20Kgrounded yield
from58.80% to50.57%, before further quality/near-duplicate exclusions. It does not
guarantee70Kaccepted output. Targets remain unchanged; further eligible sources
or a reviewed varied-view adapter are necessary if yield remains inadequate.

Validation:16capacity/production tests pass, including measured above-eight
profiles, aggregate allocation limits, unstable/no-evidence rejection and interval
nonoverlap. No GPU activity or production/capacity approval generated.
