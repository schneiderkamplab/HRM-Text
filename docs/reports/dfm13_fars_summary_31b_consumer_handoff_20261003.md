# Fars summary final freeze and 31B consumer handoff

## Final freeze for Tesla

Visible sealed receipt:
`data/dfm13/wave4/fars-summary-deferral-20261003-v1/final-freeze-receipt.json`.
Its companion `final-freeze-seal.json` pins the receipt. Every held generation
job's status, exact payload hash and result hash was compared against the original
snapshot plus final delta; all matched. Held generation is quiescent:

- 75216 done (generation completion, not review acceptance).
- 37 failed.
- 10659 exact receipt-authorized deferred jobs, still unfinished31B.
- Zero pending/running held-source generation jobs.

The exact last retry
`373cc6ba4631ea32a1a5f907ca0446322a966d542e169c2682ba5bab4614bae8`
finished failed on attempt 4 with `ValueError: Incomplete output: length`.
No reset, retry-budget change, cancellation or signal was applied to it.

This receipt attests only the held Fars sources. It does not attest global
producer/client freeze or authorize server lifecycle changes. Tesla was notified
when the receipt became visible. Transition code was not changed again during
this finalization; old comparison manifests/pins remain untouched.

## Final packets and preflight

Use original `data/dfm13/wave4/fars-summary-31b-packets-v1` together with
**`data/dfm13/wave4/fars-summary-31b-delta-final-v2`**. The latter supersedes
`fars-summary-31b-delta-v1`; do not concatenate both deltas. Final delta contains
11656 targets: 10659 authorized deferred originals and 997 completed corrections.
The final tail added only terminal failures/declines, no additional valid target.
Raw results and dispositions remain in the delta inventory.

Actual pinned31B tokenizer preflight passed all 89296 original-plus-final-delta
audit requests, zero errors, over-budget requests or truncations. The final delta
preflight is `data/dfm13/wave4/fars-summary-31b-delta-final-preflight-v2`; the original
preflight remains `fars-summary-31b-preflight-v1`. Native thinking-enabled Gemma4
rendering, no Mistral regex fix, planned 32768 context including 8192 output tokens.
Live server model/snapshot/context must still match before dispatch.

## Full consumer path, prepared but NOT launched

Module: `dfm12.fars_summary_consumer`.
Root: **`data/dfm13/wave4/fars-summary-31b-consumer-v1`**.
Sealed immutable catalog: **89296 unique candidate versions**, with complete
packets plus prior source-ledger record, status, repair/audit job IDs and verdict.
These historical decisions are never overwritten. Old failed/declined/structurally
invalid outputs outside the candidate set remain separately preserved and excluded;
the consumer does not manufacture replacements for them or declare them reviewed.

Stages are review, repair only after a valid repair verdict under an unchanged
prompt, then fresh-context whole-source re-audit. The fresh review receives the
corrected full target and source, not the previous reviewer verdict/reason.
Prompt mismatch remains a policy hold, never an automatic prompt rewrite.
The repair target is hash-linked to its predecessor; the re-audit hashes the
actual corrected candidate. This is separate-context review by the same31B model,
not independent-model/native-Persian certification.

The single-writer runtime ledger preserves all attempts and raw request/response
files. Claims and completions are transactional. Completed stages are reused on
resume. Timeout/disconnection and interrupted inflight calls become
`abort_status_unknown`, not rejects or automatic retries. Explicit technical
retry preserves old attempts, with maximum three attempts per stage; semantic
rejects are never retried. Other invalid outputs remain distinguishable.
Unresolved stages cannot become provisional keeps. Final states distinguish
unchanged keep, repaired keep, reject, residual defect, verification and prompt
policy holds. Every keep remains provisional, with no upload/admission path.

Defaults: four clients per server; hard maximum eight per server. Borrow only
8800-8807. Before dispatch all eight must serve exactly the verified31B snapshot
and at least32768 context. Future repair/fresh-review requests are measured with
the actual tokenizer before sending, including output reserve. No server lifecycle
operations exist in the consumer.

The root contains `launch-handoff.template.json` with **run_authorized=false**.
After the owner supplies explicit authorization for this exact manifest:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.fars_summary_consumer run \
  --root data/dfm13/wave4/fars-summary-31b-consumer-v1 \
  --authorization /path/to/owner-authorized-handoff.json --concurrency 4
```

That command was **not run**. `status` operates only on the isolated consumer
runtime under its lock. `retry-technical` requeues eligible technical failures;
unknown-completion retries additionally require `--allow-unknown` after explicit
operator investigation/authorization. Neither command touches production source
quality ledgers or resets the old26B retry.

Focused tests cover mocked end-to-end repair/re-audit, completed-stage resume,
fresh-context isolation, corrected-candidate hash linkage, timeout refusal to
auto-retry, attempt caps, publication holds and authorized deferred handoff.
No GPU requests, training changes, source-ledger changes or uploads were performed.
Final focused suite: **30 passed**. All sealed consumer input/code pins were
verified after preparation; launch authorization remains disabled.
