# Final endpoint gate interface

User-authorized minimal transition fix is frozen after26 passing CPU tests.
`dfm12.wave4_gemma31_transition.transition` now validates each of eight `/models`
responses before automatic76 dispatch: exactly one31B ID, absolute snapshot root
resolving to the verified local snapshot, integer context at least32768. Relative,
missing or mismatching roots, old/extra aliases, string/bool context are rejected.
Transient failures continue the existing bounded7200-second readiness wait;
they never dispatch76. No servers, GPU queries or real HTTP calls were performed.

Freeze: `data/dfm13/wave4/transition-frozen-v2.json`. The prior freeze and all old
fresh roots remain preserved. New roots are wave4 `gemma31-fresh-comparison30-v5`
and Baltic `gemma31-fresh-comparison12-v3`; authoritative completion receipt is
`data/dfm13/wave4/fresh42-successor-status-v2.json`. Require ready and verification.

Completion verified:30-v5 and12-v3 both pass, original requests/specs equal,
maxima5850/5505 including reserve. CPU worker2413899 exited successfully.
Both production-v2 roots and balanced234-v2 now report the expected pin drift in
`dfm12/wave4_gemma31_fresh.py` (new gate dependency). Preserve these originals.
Poincare must prepare a balanced successor after his execution CLI is frozen;
production successors likewise need preparation before any later authorized run.
This is explicit invalidation, not an accepted repin or an unnoticed live change.

## Interface for Boole: P3 external gate

`dfm12.wave31_endpoint_health.validate(document, snapshot, context=32768)` is
pure CPU. `check(endpoint, snapshot, context=32768)` fetches `/models` only.
CLI validates every supplied endpoint against the verified download receipt,
writes a health/command receipt and then executes the exact argv after `--`
without a shell. Any failed check aborts before consumer launch. This does not
modify P3's frozen implementation or queue. A health snapshot is not a guarantee
against a subsequent external server replacement; owned stable servers remain
required. No model/tokenizer identity is inferred from the served alias alone.

Future operator command, not executed here:

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
MODEL_PATH=$($PY -c "from dfm12.io import load; print(load('data/dfm13/wave4/gemma31-download/ready.json')['snapshot'])")
$PY -m dfm12.wave31_endpoint_health \
  --endpoint http://127.0.0.1:8800/v1 \
  --receipt logs/dfm13/p3-31b-health.json -- \
  "$PY" -m dfm12.latvian_p3_review_consumer run \
  --root data/dfm13/latvian-p3-content-alignment-20261003-v1/consumer-v1 \
  --endpoint http://127.0.0.1:8800/v1 --tokenizer "$MODEL_PATH" \
  --stage p3_source_fidelity_protocol_31b --limit 7680
```

The P3 consumer separately requires its exact pinned tokenizer path. Verify this
matches MODEL_PATH before launch. Pairing repair receipts and source holds remain
unchanged. Repeat --endpoint for all endpoints used by a multi-endpoint client.

## Coordination and ordered chain

1. Epicurus finalizes drain/Fars freeze contract. Run transition check, then
   authorized transition; it starts servers, gates all eight and runs76 itself.
2. Run fresh30-v5 then fresh12-v3 using the existing fresh CLI, bounded2/server.
3. Poincare supplies balanced234 execution CLI and verifies/reseals successor
   inputs as needed: fresh module changed solely to pin the new gate dependency.
   Do not repin existing balanced234 or pretend its old CLI has a run action.
4. Epicurus runs finalized Fars consumer with its existing snapshot/context gate.
5. Boole runs P3 with the external gate above. Start sequentially to avoid adding
   independent concurrency limits; no automatic source admission or production.

Current fresh commands after the transition's76 phase is terminal:

```bash
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/wave4/gemma31-fresh-comparison30-v5
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/wave4/gemma31-fresh-comparison30-v5 --concurrency-per-server 2
$PY -m dfm12.wave4_gemma31_fresh verify --root data/dfm13/baltic/gemma31-fresh-comparison12-v3
$PY -m dfm12.wave4_gemma31_fresh run --root data/dfm13/baltic/gemma31-fresh-comparison12-v3 --concurrency-per-server 2
```

This report communicates the frozen interface; it is not a claim that other
owners' execution/freeze work is complete. No further transition edits planned.

## Epicurus final Fars update and Baltic QA interface

Superseding the earlier missing-Fars-freeze finding: the final receipt is now
`data/dfm13/wave4/fars-summary-deferral-20261003-v1/final-freeze-receipt.json`.
It reports75216 done,37 failed,10659 explicitly deferred and zero held pending/
running. Last retry failed naturally at attempt4 (length), without reset.
Use final delta `fars-summary-31b-delta-final-v2`, not the earlier delta-v1.
Prepared consumer root is `data/dfm13/wave4/fars-summary-31b-consumer-v1`,89296
unique versions; its launch template is intentionally not authorized. Exact
run command and semantics are in
`docs/reports/dfm13_fars_summary_31b_consumer_handoff_20261003.md`.
This source-scoped freeze does not replace global drain/freeze attestation.

For Epicurus's Baltic QA consumer, the same stable interface is available:

```python
from dfm12.wave31_endpoint_health import validate, check
validate(models_document, verified_snapshot_path, context=32768)  # CPU-only
check(endpoint, verified_snapshot_path, context=32768)  # live readiness only
```

Prefer `validate` on the consumer's existing asynchronous `/models` response,
pin `dfm12/wave31_endpoint_health.py` in its new manifest, and gate every endpoint
before claiming/sending requests. Alternatively use the CLI wrapper above with
repeated --endpoint and the exact Baltic command after --. The module is frozen;
no import-time network/process/GPU side effects. No lifecycle ownership is added.
