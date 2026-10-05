# Baltic QA31 full-source consumer handoff

## Scope and immutable evidence

New isolated module: `dfm12.baltic_qa31_consumer`.
Published scope: **118866 conversations**, comprising **12895 Lithuanian QA** and
**105971 Latvian QA**. Jason's source-wide holds remain active.

The preparer validates Jason's exact hold receipt hash
`92a1796b8e48e57c888ce018c278ed8ccfc4e6252b1885944a0df01d7ffd28cb`,
published file hashes, every binding's ordinal/candidate ID/canonical record hash,
upstream provenance/file hash/row index and final supervised target index.
All full upstream records are retrieved from pinned local files, not reconstructed
from summaries. The full published record, original audit and quality label are
preserved outside model requests. No Jason file, published export, source ledger,
registry entry, gate or remote repository is modified.

**Evidence limit:** upstream LT consists of QA pairs and upstream LV of generated
conversations. Neither supplies the primary Wikipedia articles. Upstream answers
are not gold, and alignment is not factual verification. Missing essential factual
evidence requires hold/reject, not inventions or confident corrections from memory.

## Quality and repair policy

The reviewer examines the entire conversation, every assistant turn, premises,
referents, geography, numbers, relationships, safety, native-language quality and
instruction compliance. It distinguishes introduced/inherited defects and avoids
style-only penalties. The four output fields are reason, verdict, history_quality
and factual_support. Reason precedes verdict; no fragile exact-quote/span schema.

Only the final supervised assistant target may be repaired. All earlier messages
(including assistant history), roles and tools are protected. Bad earlier history
cannot be laundered through a cleaner final answer: hold/reject it. A repair verdict
requires acceptable protected history and no unresolved essential evidence.
Fresh re-audit reads the whole corrected conversation plus original QA in a new
context, without the earlier reviewer reason/verdict. At most one semantic repair
is attempted; residual defects remain needs-review, rather than an endless loop.

The consumer instantiates the Fars engine privately with Baltic-specific adapters.
It does not monkeypatch imported global modules or edit the pinned Fars engine.
It inherits transactional claims/completions, separate raw responses and attempts,
hash-linked parent stages, completed-stage resume and explicit technical retries.
Unknown-completion calls are not automatically retried or treated as semantic
rejects. Maximum three technical attempts per stage; no counter resets.
All keeps remain provisional: no admission, export, upload or hold-clearing path.

## Roots

- Full source-bound packets: `data/dfm13/baltic/qa31-full-packets-v1`.
- Actual31B tokenizer preflight: `data/dfm13/baltic/qa31-full-preflight-v1`.
- Diagnostic consumer: `data/dfm13/baltic/qa31-diagnostic20-consumer-v1`.
- Full consumer: `data/dfm13/baltic/qa31-full-consumer-v1`.

Both consumer catalogs are now sealed:20 diagnostic conversations and118866 full
conversations. All118866 actual-tokenizer measurements passed, with zero errors,
oversized prompts or truncations. Largest full prompt plus8192 output reservation:
LT9825 tokens, LV17084 tokens, within the planned32768 context.
Input/code/catalog pins were reverified after finalization. The handoff receipt is
`data/dfm13/baltic/qa31-full-packets-v1/consumer-handoff-receipt.json`.

Preflight uses verified Gemma4-31B snapshot
`842da3794eaa0b77d5f08bae87a17459d91ff475`, raw native template, thinking enabled,
`fix_mistral_regex=False`, full prompt plus8192 output tokens against planned32768.
No truncation or silently dropped long conversations. Repairs and fresh re-audits
need new content-specific measurements at runtime. Live endpoint model, exact
snapshot and context must still be verified before dispatch.

## Calibration and launch gates

The diagnostic catalog contains Jason's same20 historical sample identities;
it is deliberately exposed and repair-stratified, not a fresh holdout. Only IDs
are taken from diagnostic preparation. Prior audit decisions, assessment labels
and reference judgments never enter model requests. Semantic assessment remains
pending until the owner permits diagnostic GPU requests and reviews outcomes.
No claim that this reviewer is calibrated or reliable is made from CPU tests.

Both consumers require explicit manifest-bound `run_authorized:true` handoff.
The bulk consumer additionally requires a `calibration_approval` path in that
handoff. That receipt must contain `approved:true`, the exact model,
`diagnostic_root`, the frozen `report` path/hash (`report_sha256`), and a substantive
`semantic_assessment`. All20 matching diagnostic jobs must be semantically terminal;
technical failures cannot masquerade as calibration completion. The report must
match the pinned diagnostic manifest and current reviewer implementation.
This is an owner-reviewed gate, not automatic approval from model verdict counts.

Commands available after owner handoff (NOT executed during preparation):

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.baltic_qa31_consumer run \
  --root data/dfm13/baltic/qa31-diagnostic20-consumer-v1 \
  --authorization /path/to/diagnostic-handoff.json --concurrency 4
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.baltic_qa31_consumer calibration-report \
  --root data/dfm13/baltic/qa31-diagnostic20-consumer-v1
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.baltic_qa31_consumer run \
  --root data/dfm13/baltic/qa31-full-consumer-v1 \
  --authorization /path/to/bulk-handoff-with-calibration-approval.json --concurrency 4
```

The shared endpoint gate requires all eight8800-8807 servers to serve the verified
31B snapshot at >=32768 context; no fallback to26B or unverified aliases. Default
four clients/server, hard maximum eight. No server lifecycle actions exist.
Disabled launch templates are emitted in sealed consumer roots.

CPU tests cover binding mismatch, complete population join, all-history input,
blind-label separation, protected message preservation, uncertain-evidence and
history-failure rejection, fresh-review isolation, private engine globals and
fail-closed calibration. GPU semantic validation is still required.
Final focused CPU suite: **18 passed**, including a mocked multi-turn
review/repair/fresh-review/resume execution. OKF validation: zero errors/warnings.
Both launch templates remain disabled. No GPU requests or server changes.
