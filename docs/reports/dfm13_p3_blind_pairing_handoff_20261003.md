# P3 calibrated blind pairing: CPU handoff

## Current State

The implemented coordinator is `dfm12/latvian_p3_pairing.py`, with focused tests
in `tests/test_latvian_p3_pairing.py`. Its isolated root is
`data/dfm13/latvian-p3-content-alignment-20261003-v1/blind-calibrated-v2/`.
It supersedes direct use of `consumer-v1` as the bulk execution entry point;
all earlier evidence and queues are preserved. No inference or endpoint health
request has been sent. Calibration is **pending**, not passed.

The `blind-calibrated-v1` draft is preserved but superseded: its whitelist omitted
the original translated-source question/answer, though it retained the complete
published conversation. V2 includes both views and explicitly checks repair-induced
drift. The old draft's code pin now fails closed; it is not a launch target.

Inventory: 7,680 original rows, two review requests per row, and 140 calibration
controls reviewed through both paths: **15,640 initial jobs**. Every original row
already has a disposition (`pending_calibration`). No model or manual pairing
receipt has been issued. Both entire P3 source partitions remain held.

All 15,640 requests passed the actual cached31B tokenizer/template preflight with
thinking disabled, no truncation and zero blocked requests. Maximum input is
3,588 tokens; with the 8,192-token output reserve the maximum is **11,780**, below
32,768. `native-render-preflight.json` pins the tokenizer and request hashes;
`native-render-lengths.jsonl` records each job. The sealed request SHA-256 is
`3a8a8513cfeb9445f8b928e5054fc7816fbbb7008fe17a559db096f3dc31f449`.
These CPU measurements do not claim a live server is ready.
Actual repeated preparation preserved identical request bytes and all 15,640
pending jobs with zero attempts. A full comparison of all 15,360 production
evidence views verifies unchanged current messages, original translated-source
questions/answers, and every candidate's question/answer/config. See
`resume-preservation-verification.json` for the hash-bound receipt.

## Blindness and Calibration

Both review passes receive full native conversations, original translated-source
questions/answers, and full English alternatives.
An explicit whitelist strips retrieval ranks/scores, positional origins, manual
verification flags and prior verdicts from the model input. Alternative order is
independently deterministic for each pass. The blind pass never sees the first
response. Independent here means separate, blinded executions, not statistically
independent models. Agreement is necessary but not sufficient.

The 140 controls comprise 20 known pairings, 80 wrong-reference cases, 20 cases
with the correct reference absent, and 20 synthetic duplicate-question/conflicting
reference cases. Negative cross-pairings use different inspected questions within
each of the four configurations. Synthetic conflicts are labelled only in the
external control ledger, not announced in the request. These are diagnostic
pairing controls built from 20 previously assistant-inspected bilingual anchors,
not native Latvian gold or new population validation.

The split is 84 development / 56 heldout controls (12 / 8 distinct LV anchors).
LV anchor sets are disjoint; English distractor questions can cross the split.
Therefore this is not independent source-group generalization evidence. No
control labels or examples are supplied in either model prompt. Thresholds require
all controls completed, zero falsely supported negative pairings/wrong positive
IDs, and at least 90% supported correct positives in **each** split. Both passes
must meet the aggregate gate; correlated judgments are not independent samples.
The scope limitation remains even if calibration passes. Wrong-reference controls
cover genuine topic distinctions, not exhaustive subtle entity/negation attacks.

## Receipts and Terminal Outcomes

The producer validates job/request bindings and literal quotes using the existing
consumer schema. Both passes must support the same unique candidate. Uncertain,
wrong or disagreeing matches are terminal rejects. Identical-question candidate
collisions or multiple source-answer strings are conservatively rejected as
unresolved alternatives; no arbitrary answer key is selected.

Successful receipts explicitly say `verification_kind=model_verified`,
`human_verified=false`, and describe the correlated same-model review method.
They bind both review request/decision hashes, the calibration result, candidate
content, original record and verifier code. The legacy `independently_verified`
field means the separate calibrated blind checks occurred; it does **not** claim
a human bridge or statistical independence. Prior manual bridges remain distinct
historical evidence; this producer never relabels model output as manual review.

Pairing and fidelity remain separate: a uniquely identifiable damaged translation
can be paired but require repair. Both original quality reviews must keep before
the row becomes `reviewed_candidate_not_admitted`. Otherwise one full repair
proposal is allowed, followed by a fresh re-audit that does not receive the repair
rationale. A re-audit must keep and select the same source; failures terminate.
There are at most four transport/schema attempts per job and one semantic repair
proposal per original row. Restart reconciliation restores missing re-audit jobs
idempotently. No looping repairs or automatic admission occur.

`reconcile` writes `model-pairings.jsonl`, `calibration-result.json`,
`dispositions.jsonl` and `disposition-summary.json`. Every original row is accounted
for. Completed calibration failure terminates rows as rejected; unfinished jobs
remain explicitly pending. Source-wide hold supersession and any corrected release
are separate operations, not side effects of a model keep.

## Endpoint Gate and Future Commands

**Cross-entrypoint update:** use `dfm12.latvian_p3_dispatch` for shared-eight-server
bulk execution. The older pairing `run` command below remains a one-endpoint
diagnostic API, not the recommended bulk launcher. The new adapter leaves all
sealed queue/source modules and their pins unchanged.

This entry point calls Tesla's `dfm12.wave31_endpoint_health.check` before dispatch,
requiring exactly the 31B alias, the verified ready-receipt snapshot, matching
tokenizer path and advertised context >=32,768. Wrong model/context/snapshot fails
before review dispatch; the behavior is tested with mocked health responses.
The helper is hash-pinned with the coordinator and sealed consumer. See
`docs/reports/dfm13_31b_launch_dryrun_20261003.md` for server handoff constraints.
Do not bypass this gate by invoking the old low-level consumer directly.

The following commands are **not executed** and require the authorized 31B handoff:

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
ROOT=data/dfm13/latvian-p3-content-alignment-20261003-v1/blind-calibrated-v2
# Repeat once with stage p3_pairing_calibration_blind_31b; 140 requests each.
$PY -m dfm12.latvian_p3_pairing run --root "$ROOT" --stage p3_pairing_calibration_31b \
  --endpoint "$ENDPOINT" --ready "$READY_RECEIPT" --tokenizer "$MODEL_PATH" --limit 140
$PY -m dfm12.latvian_p3_pairing reconcile --root "$ROOT"
# Only after calibration passes: run first and blind bulk stages separately.
# Stages: p3_source_fidelity_protocol_31b and p3_pairing_blind_31b.
# Reconcile then creates bounded repair jobs when needed.
# Repair/re-audit stages: p3_source_fidelity_repair_31b / p3_source_fidelity_reaudit_31b.
```

Preparation itself is CPU-only:

```bash
$PY -m dfm12.latvian_p3_pairing prepare --root "$ROOT" \
  --fused-root data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2
```

CPU verification: 58 P3 and endpoint-gate tests passed, including blind input
whitelisting, heldout anchor separation, false-supported calibration failure,
disagreement rejection, explicit model receipt labels, bounded repair, unprimed
re-audit, idempotence and wrong-endpoint rejection. These are implementation tests,
not actual model quality results.

## Eight-Server Execution Audit

Concrete blocker fixed: the prepared pairing CLI previously accepted exactly one
endpoint and its consumer was sequential. Launching that command with a bulk limit
would use only one of the eight shared servers. The new P3-only dispatcher accepts
repeated `--endpoint` arguments and defaults to one worker per endpoint, eight
aggregate in-flight requests. Two per endpoint is supported only with an explicit
aggregate budget of at least sixteen. Duplicate endpoints, including the common
localhost/127.0.0.1 alias, are rejected.

`--limit` is an aggregate **attempt** budget, never multiplied by endpoint count.
For 140 control requests, four workers receive 18 slots and four receive 17.
Queue leases ensure unique claims. Retries consume budget; budget exhaustion is
not queue completion. Inspect the queue/dispositions and rerun for remaining work.
Raw responses and all existing source/repair validators are preserved. Worker
failures drain the other submitted workers before returning; no server is killed.
Every dispatch has a retained `dispatch-runs/<id>.json` receipt, plus a latest
`dispatch-receipt.json` view, recording allocations and endpoint/ready/code pins.

Sequencing checked against the real transition: it already dispatches the initial
76-case client itself, then writes `comparison-terminal.json`. Do not duplicate
that client. P3 dispatch requires this receipt to contain exactly 76 terminal
done/failed outcomes; failures are not semantic approval. The documented fresh42
and balanced234 comparisons and their independent review still belong to the
handoff owner. In particular, the inspected balanced234 module has prepare/verify
but no run entry point; this P3 change does not pretend to solve that external
execution gap. P3 must receive its capacity allocation after the planned shared
comparison phase, not merely infer availability from a live endpoint.

**Resolved later2026-10-03:** the preceding missing-execution observation is
historical. `dfm12.wave31_balanced_run` now executes the sealed balanced234
execution-v2 root (source-v4); no run command was added to the preparation module.
Use the [current operational sequence](dfm13_31b_operational_handoff_20261003.md).
This does not waive P3 calibration, transition-terminal or capacity gates.

All selected endpoints pass the strict model/context/snapshot check **before any
P3 review dispatch**. A root lock prevents duplicate P3 stages and a shared P3
budget lock prevents overlapping dispatches from different P3 roots. These locks
do not constrain unrelated Fars/fresh/wave clients: the handoff owner must reserve
the aggregate capacity or arrange cooperative locking. No claim of a global server
semaphore is made. There are no server starts/stops or frozen production edits.

Future shared-eight-server command, not executed:

```bash
ENDPOINT_ARGS=()
for port in {8800..8807}; do
  ENDPOINT_ARGS+=(--endpoint "http://127.0.0.1:$port/v1")
done
$PY -m dfm12.latvian_p3_dispatch --root "$ROOT" \
  --stage p3_pairing_calibration_31b "${ENDPOINT_ARGS[@]}" \
  --ready "$READY_RECEIPT" --tokenizer "$MODEL_PATH" \
  --transition-terminal "$TRANSITION_ROOT/comparison-terminal.json" \
  --per-endpoint 1 --max-inflight 8 --limit 140
# Then repeat for p3_pairing_calibration_blind_31b and reconcile.
# Only after the P3 calibration gate passes, dispatch the two bulk stages.
```

CPU tests cover simultaneous use of all eight workers, exact aggregate budget,
duplicate/oversubscribed endpoint rejection, shared-lock exclusion, nonterminal
transition rejection and a bad eighth endpoint preventing every dispatch. No real
endpoint, model or GPU call was made during these tests.
