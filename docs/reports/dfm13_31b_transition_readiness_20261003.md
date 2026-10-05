# 31B transition readiness: read-only snapshot

## Draft inventory for owner review

Generated inventory (not authorization):
`data/dfm13/wave4/handoff-inventory-1791057751957038611/contract-draft.json`
and sibling `process-inventory.json`. Includes22 historical/current exact process
identities, seven source/calibration queue paths,14 current receipt hashes,
model metadata pins, exact old supervisor, and existing Fars authorization.
Both CPU-complete and producer-frozen attestations are false; the existing
readiness function rejects this draft as expected. Missing required receipt:
Slovak `audit-finalization.json`, not HF publication completion.

Live enqueue-capable controllers captured:2355940,2365731,2607843,2638570.
Publication-only2121810/2143813 are separately listed, not GPU-drain blockers;
Monitor2111503 is a client-restart producer and is included in the freeze gate
(corrected after checking ensure_wave4_client/ensure_wave4_booster). It must be
stopped before freeze. Historical exited client identities remain
evidence. Process churn requires another scan at actual freeze. Receipt hashes
are snapshots: refresh after genuine freeze into a NEW final contract.

Concrete check blocker discovered while collecting identities: existing
`wave4_gemma31_transition.alive()` catches OSError/ProcessLookupError but the
identity helper raises `psutil.NoSuchProcess` for exited PIDs (reproduced with
2032197). The transition owner must fix this narrow exception handling before
checking a drained inventory, with any dependency changes handled explicitly.
No transition-code edit or repin was performed in this inventory task.

The exited-PID blocker is now resolved through the isolated CLI
`dfm12.wave4_gemma31_transition_exited`. It privately loads the unchanged pinned
transition module and catches only psutil.NoSuchProcess around its alive check.
All identity comparisons, readiness gates and shutdown behavior remain original;
AccessDenied is not treated as exit. Nine focused tests pass. Use this successor
module for the check/transition commands below. Active fresh-comparison-v5,
Baltic-fresh-v3 and balanced-execution-v2 manifests pin the original module, so
that module and the shared identity helper were deliberately left unchanged.
No sealed root was repinned. Owner should pin the successor file separately in
the final handoff receipt inventory.

## Later terminal snapshot, 19:55 UTC

Read-only inspection at Unix1791057353 supersedes the queue counts below:
first audit10739087 done/19364 failed; repair audit51526 done/4123 failed;
repair generation83547 done/58 failed/10659 authorized deferred31B.
Neither Wave4 queue has pending or running jobs. This alone is not a producer
freeze: Slovak materialization can still enqueue recoveries.

The current additive loop synchronously calls `release(..., upload=True)` inside
the per-pair selection loop, before processing later pairs. Main reports HF
create quota retry blocking this call; code confirms that publication can block
remaining selection. Tesla owns the decoupling fix. Do not wait for HF quota
reset to release GPU capacity. Publication backlog is a separate CPU/network
obligation, not a source-audit drain obligation.

At this snapshot23 additive pair receipts exist; en-sk and nl-sk still record
157 and108 pending components respectively, despite terminal underlying queues.
These receipts need fresh ledger materialization, not an assumption that all
those components need GPU calls. Finish selection across every requested pair,
drain any newly enqueued recoveries, then attest selection/recovery completion
independently of upload status. Freeze every enqueue-capable producer and drain
clients before the existing transition check. A surviving publisher is outside
the GPU gate only when demonstrably unable to enqueue GPU jobs. No final
authorization was created and no process was signaled by this inspection.

Observed 2026-10-03 19:51-19:52 UTC. This is NOT a freeze contract or release
authorization. No signals, server changes, GPU requests, queue writes or repins.

## Live queues

Read using SQLite mode=ro, grouped by stage/status. Independent snapshots are
not an atomic cross-database freeze.

| Queue/stage | Done | Failed | Pending | Running | Deferred31B |
| --- | ---: | ---: | ---: | ---: | ---: |
| Wave4 first audit | 10677809 | 19104 | 58110 | 3428 | 0 |
| Wave4 repair audit | 51286 | 4061 | 0 | 59 | 0 |
| Wave4 repair generate | 83547 | 58 | 0 | 0 | 10659 |
| Baltic first audit | 5187552 | 6469 | 0 | 0 | 0 |
| Baltic repair audit | 17636 | 1453 | 0 | 0 | 0 |
| Baltic repair generate | 28683 | 57 | 0 | 0 | 0 |
| Baltic LT summary privacy | 1946 | 0 | 0 | 0 | 0 |

At the user's observed 35K/min, the first-audit backlog represents roughly two
minutes of throughput, NOT a transition ETA: tails, further repair enqueueing,
selection/materialization and producer freeze remain. Failed is terminal
technical state, not a quality pass. Future31B comparison jobs are not26B drain
obligations. Held Fars jobs remain unfinished31B work.

## Concrete remaining conditions

- Audit clients2032197/2111441 and repair-audit client2593547 are live. All
  pending/running jobs must drain, including newly enqueued recovery work.
- Slovak additive producer2542233 remains live. Its410 components are enqueued;
  both main freeze inputs and combined-audit-manifest.json exist. The handoff's
  `waiting_main_component_freeze` label is stale, not evidence of missing files.
  At inspection21 pair receipts existed; en-sk listed157 pending components.
  Additive completion.json is absent. Main CPU completion alone is insufficient.
- Main selector2607843 has a complete cycle:275 ready pairs,33 without supply,
  no selector in-flight work. It is still live and can run another cycle.
  Instruction2365731 and transform2355940 controllers remain live; instructions
  show15 uploaded, one empty and two Fars source-fidelity holds; all11 transforms
  show uploaded. Translation publishers2121810/2143813 remain live. Inventory
  enqueue-capable producers separately from CPU-only publishers; do not mistake
  a status snapshot for a producer freeze.
- Final owner contract must attest actual CPU completion and producer freeze,
  pin completion receipts, inventory relevant queues and exact process identities,
  and include the existing hash-bound Fars deferral authorization. Only its
  exact10659 authorized jobs may be exempted from26B terminal status. No generic
  pending/deferred exemption, and no requirement to finish held31B work on26B.
- No final contract was found in the checked top-level Wave4/transition roots.
  The older handoff-readiness snapshot and deferral fragment are NOT substitutes.

The old supervisor1856648 matches its recorded PID/start-time/argv identity and
is alive.31B download ready.json records all files verified; the existing
transition model metadata/shard-existence check succeeds. No full shard rehash
was performed in this inspection. Capacity workload-v4 remains the current
CPU-prepared workload; no measured capacity approval exists.

## Existing executable path

`HANDOFF` below must be the actual final owner-issued contract, not an invented
filename. Set MODEL_PATH to the snapshot in gemma31-download/ready.json:
`/home/ucloud/.cache/huggingface/hub/models--google--gemma-4-31B-it/snapshots/842da3794eaa0b77d5f08bae87a17459d91ff475`.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave4_gemma31_transition inspect
$PY -m dfm12.wave4_gemma31_transition check --contract "$HANDOFF" --model-path "$MODEL_PATH"
# Only after drain/freeze and explicit owned-release authorization:
$PY -m dfm12.wave4_gemma31_transition transition --contract "$HANDOFF" --model-path "$MODEL_PATH"
```

Transition rechecks readiness while holding the exact supervisor pidfd, requests
its graceful shutdown without escalation, requires free GPUs, and launches the
bounded comparison lifecycle. It runs76 comparison jobs itself; do not duplicate
them. Semantic approvals and the separate real capacity ramp remain subsequent
gates, not prerequisites to release26B after its work is properly drained.
See [operational sequence](dfm13_31b_operational_handoff_20261003.md).
