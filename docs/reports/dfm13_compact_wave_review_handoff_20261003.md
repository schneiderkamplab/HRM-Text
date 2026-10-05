# Compact wave review: main / Poincare / Harvey handoff

Implemented `dfm12/wave_compact_review.py`, patterned after jjzha's concise
nonthinking256 reviewer, but scoped to the complete conversation and supplied
source/reference/tool evidence. No new queue, receipt framework or server code.
No edits to jjzha, shared production modules, source7, repair25 or audit-first wiki.

## Existing runner integration

```python
from dfm12.wave_compact_review import install
controller = install(controller)  # existing private wave/baltic controller
```

This replaces the indexed evidence/span reviewer with verdict/issues/reason,
preserves deterministic checks and the existing generator, and adds
`compact_verdict`, `compact_reason`, `repair_requested`, `max_repair_attempts=1`
to normal outcomes. keep alone can pass; repair/reject/needs_verification cannot.
No second model audit, native-certification gate or all-language perfection gate.
needs_verification is for named essential unavailable evidence, not generic doubt.

`scripts.run_generation_constraint_test.py` now installs this adapter. Its
unchanged bounded command after Epicurus releases26B endpoints is:

```bash
python -m scripts.run_generation_constraint_test --execute --arm constrained \
  --output data/dfm13/generation-constraints-26b-test12-20261003-v1
```

No launch performed here. `--execute` omitted is CPU-only. There are12 generation
cases with one ordinary review each. This diagnostic runner currently reports
repair_requested; it does not independently launch repair25 or another repair
client. Source holds remain outside automated acceptance.

## Poincare: one targeted repair, one blind re-audit

Use the same existing stage transport and raw capture. API:

```python
from dfm12 import wave_compact_review as compact
payload, schema = compact.repair_request(candidate, first_verdict['reason'])
# Execute ONCE through the existing stage caller; incomplete/invalid output holds.
repaired = compact.apply_repair(candidate, parsed_output, student_renderer)
blind_request = compact.request(repaired)  # no prior verdict/reason fields
```

Only assistant prose indices are editable; original user instructions, tool calls
and tool-result records are immutable. Existing repair helper checks retain code,
literals, numerical targets and full student rendering. No silent source repair.
Fresh re-audit sees full repaired messages plus original evidence, not the repair
instruction, prior outcome or full provenance metadata. Call `keeps` with the
standard audit_record for deterministic math/tool checks before accepting.
One failed/repair/reject/NV re-audit remains nonaccepted; no second repair loop.

Unchanged keeps should retain original content. Repairs must be stored separately
with original hash/lineage; do not overwrite source artifacts. Input redesign or
immutable-user/source contradictions are rejects/holds, not permission to alter
the task. This helper reuse does not change Poincare's live/frozen pilot.

## Main: minimal production progression

The existing wave/Baltic ledgers already contain full per-family targets and
recovery/dedup/backpressure. For a freshly pinned successor, install this adapter
and the model-neutral generation constraint, and pin the two modules. Use the
original target table (13 languages x70K =910K); bound dispatch attempts per group
without editing those targets. Increase the dispatch bound on the same ledger
after sampled content review. Known-bad source/candidate holds remain excluded.
This document does not claim that full successor preparation/launch occurred.

Harvey's source/schema changes remain separate. Reuse his adapter's schema and
decoder together; do not confuse compact reviewer JSON with generation schema.
No reason to rerun increasingly elaborate calibration before every batch.

## CPU verification

- 25 combined tests passed, including14 compact-adapter tests; original-user
  immutability, source/evidence retention, prior-verdict stripping, invalid verdict
  rejection and deterministic failure overriding a semantic keep.
- Existing12-case runner request/schema round trips still exact.
- Actual26B tokenizer on12 complete review requests: max1,643 prompt tokens plus
 256 response =1,899, within32,768; no truncation.
- No performance/quality improvement claim without execution. No GPU calls.
- Wiki generation section moved intact to
  `wiki/pages/dfm13-generation-constraints.md`, indexed, with historical links
  preserved. OKF validation passes after the split.
