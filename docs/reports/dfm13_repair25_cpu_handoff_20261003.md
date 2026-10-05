# One-Shot 31B Repair Pilot: CPU Handoff

## Current Launch Root: Eight Parallel26B Cases

Later2026-10-03: main explicitly requested all eight endpoints in parallel.
The new root is `data/dfm13/gemma26-repair25-20261003-v2`, superseding the
unlaunched sequential26B-v1 below without altering its artifacts. The runner
has eight workers, exactly one in-flight case/request per endpoint, with the
repair and two audits sequential within each case. The single-event-loop raw
writer allocates IDs synchronously and tests verify25unique IDs under eight-way
overlap.54tests pass, including sole ownership and stop/error drain. New CPU
receipt is under v2; old26B-v1 implementation pins intentionally no longer match.
The frozen31B module/root remain untouched.

Main authorized this agent's bounded launch **after Epicurus confirms26B ready**.
Confirmation is still pending; no GPU request has been launched. Coordination:
`docs/reports/dfm13_repair25_launch_coordination_20261003.md`.

```bash
python -u -m dfm12.synthetic_repair_pilot run --teacher 26b \
  --root data/dfm13/gemma26-repair25-20261003-v2 \
  --capacity-measurement data/dfm13/gemma31-capacity-measurement-20261003-v1/measurement.json
```

## Current Model Choice: Default26B, No Launch (Later2026-10-03)

The user questioned31B; main has not authorized31B bulk and the model choice is
pending. The prior31B-only commands below are historical, **not a launch
instruction**. The model-selectable successor is
`dfm12/synthetic_repair_pilot.py`, tested by
`tests/test_synthetic_repair_pilot.py`. The frozen31B module and root were left
unchanged and still pass verification.

New CPU-prepared default root:
`data/dfm13/gemma26-repair25-20261003-v1`, with25 cases and
`cpu-preflight-passed.json`. Manifest SHA256:
`0a8533e66616cae456da645df50b48596af3fef5f17d3ef37f3062f465d69469`.
Default teacher is `google/gemma-4-26B-A4B-it`, pinned revision
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`. CPU checks confirmed local snapshot
metadata/tokenizer and shard presence; this does not claim a new full-weight
hash certification.31B retains its existing verified download receipt.

```bash
# CPU verification only; safe while capacity/GPU work runs elsewhere.
python -m dfm12.synthetic_repair_pilot verify \
  --root data/dfm13/gemma26-repair25-20261003-v1

# Optional future CPU preparation for explicit31B choice, always a NEW root.
python -m dfm12.synthetic_repair_pilot prepare --teacher 31b --root NEW_ROOT
```

Preparation defaults to `--teacher 26b`. Existing roots always use their sealed
teacher; an explicit conflicting flag fails closed. All repair, strict audit
and native/source-audit requests, teacher token budgets and live endpoint
model/snapshot gates follow that teacher.32K advertised context is required
for either model; no smaller context is silently truncated or reconfigured.
75 planned payloads per teacher were CPU-measured; maximum23,047 tokens.
51 combined tests passed. The26B root also passed full4096 student preflight.

**No execution until main coordinates it.** A future run uses the successor
module's `run --root ... --capacity-measurement ...`. The sealed drained capacity
receipt is a sequencing prerequisite, not transfer of31B throughput/capacity
approval to26B. The pilot remains sequential and nonadmitting. No31B bulk,
GPU client, server change, automatic watcher or production approval was added.

User authorized a bounded repair and independent re-audit pilot for the 25
repair-recommended automated keeps in the independent balanced234 review.
**Prepared, not launched.** Wait for capacity measurement/drain and owner
coordination before borrowing the existing31B endpoints. No server launch,
restart, GPU call, sampling, upload or production approval occurred here.

## Frozen Root and API

- Root: `data/dfm13/gemma31-repair25-20261003-v2`.
- CPU receipt: `cpu-preflight-passed.json` under that root.
- Manifest SHA256: `87edf5f7a95f5a75e0008c8049a506ec258044696720ee2f5d6001ee2a73fa09`.
- Module: `dfm12/wave31_repair_pilot.py`.
- Tests: `tests/test_wave31_repair_pilot.py`.
- Input: `docs/reports/dfm13-balanced234-math-tool-openhermes-20261003/review.json`.

V1 is preserved and superseded: final v2 additionally strips inherited source
judgment metadata from fresh audits. Do not repin or run v1. Original balanced
candidates and review documents are unchanged.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.wave31_repair_pilot verify \
  --root data/dfm13/gemma31-repair25-20261003-v2
```

Future execution, **not executed here**, after capacity completes and endpoints
are released by their owner:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.wave31_repair_pilot run \
  --root data/dfm13/gemma31-repair25-20261003-v2 \
  --capacity-measurement data/dfm13/gemma31-capacity-measurement-20261003-v1/measurement.json
```

The runner requires a sealed matching-model capacity measurement with all eight
final telemetry queues drained, then validates all8800..8807 model snapshots
and32K contexts. It sends one request at a time, rotating endpoints; it does not
reuse or assert a high-concurrency capacity allocation. Historical drained
evidence does not replace current operational owner coordination.

## Repair Contract

Only indexed nonempty user/assistant prose is editable. Roles, ordering, tool
definitions/calls/results and call IDs are copied unchanged. Code/JSON fences,
inline identifiers, explicit source code literals, math question constants and
boxed answers are protected. For translated code that was previously altered,
protection is based on the frozen original source, not the defective translation.
Inherited code errors must be explained accurately without silently rewriting
the code. Fact, operation and natural-language consistency remain audit duties;
lexical protections are not a substitute for semantic review.

Strict JSON parsing/schema validation, no extra indices, no blank responses,
no special chat delimiters, and full untruncated native student rendering apply
before any audit. Every assistant target must fit4096 using the existing raw
Gemma template/tokenizer, without regex-fix or truncation changes. The repair
request reserves8192 tokens; full actual31B prompt budgets are checked before
each request. Repaired audit prompts are measured again at runtime.

Exactly one repair request per case. Raw response evidence and stage state are
saved before parsing. No transport/model retries. Interrupted, failed or
ambiguous stages are not reissued on resume. A completed repair can resume its
not-yet-started audit stages without regenerating the repair. SIGTERM stops new
cases after the current bounded case drains; cancellation remains unknown, not
an automatic retry.

## Blind Re-Audit and Outputs

Fresh strict indexed review and a separate native/source-fidelity review see
only repaired messages/tools and whitelisted source/reference/scenario fields.
Neither sees the repair note, old verdict, or inherited source judgment metadata.
Both use the existing31B model in fresh stateless requests. This is procedural
separation, **not an independent model or human/native-speaker certification**.

Per-case outputs: `requests/`, `raw/`, `stages/`, `candidates/`, `outcomes/`.
Final `report.json` reports provisional keeps only. All admission/publication/
production flags remain false, including after both model audits keep a row.
Hash-bound independent review of repaired outputs remains required before any
production repair path is enabled. No automatic successor exists.

## CPU Evidence

25 cases: Baltic3math+1OpenHermes; wave4 5math+6tools+10OpenHermes.
All25 original full student renders passed. All50 baseline blind audit payloads
passed note/verdict exclusion checks. Maximum teacher prompt+reserve totals:
repair10,686; strict audit23,047; native audit5,762, all below32768.

28 tests passed across the new repair tests and existing balanced runner tests:
schema/extra-field rejection, protected tool/history preservation, restored code
literals, numeric constants, full-render overflow rejection, audit metadata
whitelisting, raw invalid-response retention, one-shot resume, cancellation,
request drift and sealed/drained capacity prerequisite. Final pinned verify
passes. CPU preparation does not demonstrate live repair quality.
