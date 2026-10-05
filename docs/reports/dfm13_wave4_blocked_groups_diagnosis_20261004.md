# Bounded W4 blocked-group diagnosis, 2026-10-04

Read-only ledger/evidence inspection; no GPU calls, runtime edits, budget changes,
or admissions. Root: `data/dfm13/wave4/synthetic-group-shards-20261004-v2`.
These groups exhausted the existing6x candidate budget, rather than a transient
source-shortage flag. FA/LB targets are6000 each; BE OpenHermes target15000.

## Exact ledger totals

| Group | Attempts | Accepted | Review invalid | Generation invalid | Valid nonkeep | Duplicate |
|---|---:|---:|---:|---:|---:|---:|
| fa math-code | 36000 | 601 | 29957 | 665 | 4697 | 80 |
| lb math-code | 36000 | 527 | 23674 | 4606 | 7182 | 11 |
| be openhermes | 90000 | 7624 | 15640 | 4749 | 61987 | 0 |

Acceptance per attempt:1.67%,1.46%,8.47%. Review-invalid shares:83.21%,65.76%,
17.38%. `valid` here means parsed nonkeep, NOT acceptable training content.

## Bounded sample

Seed20261004, Python Random.sample of ordered terminal-job offsets,17 FA,
17 LB,16 BE; queries restricted to these three groups. Same50 outcomes reused
for follow-up inspection, not additional random samples.

| Group | Review invalid | Accepted | Repair | Reject | Needs verification | Generation invalid |
|---|---:|---:|---:|---:|---:|---:|
| fa | 11 | 2 | 0 | 1 | 2 | 1 |
| lb | 10 | 1 | 1 | 1 | 2 | 2 |
| be | 3 | 2 | 2 | 0 | 7 | 2 |

All24 sampled review-invalid raw stage responses were finish_reason=stop and
exactly `{ "verdict": "keep", "issues": [], "reason": "" }`, rejected with
`ValidationError: '' should be non-empty`. No length-stop occurred in those24.
This is technical loss, not evidence that all these candidates deserve admission.
It cannot be extrapolated into an exact recoverable count for the whole groups.

## Concrete examples

- FA `370886ad41ea...`, LB `ca530d5a7522...`, BE `c5cdacc67ec5...`:
  complete clean-keep/empty-reason responses rejected at stage validation.
- LB `c42285b79f17...`: reviewer claims singleton input causes an error in
  `return max(values) - min(values) if values else 0`. Actual saved code equals
  the reference; singleton correctly returns0. The stated rejection reason is
  false. Its assistant also contains unnecessary meta-explanation, so this is
  not a blanket quality approval of that conversation.
- BE `1137624a9611...`: candidate asks to classify MS Paint in Belarusian and
  answers raster graphics editor. Source provenance is the equivalent English
  QA. Reviewer holds because it is unclear whether to follow source English or
  user Belarusian. That rationale confuses source provenance with learner
  instructions. Similar rationale appears in `9e87cdeee202...` and
  `f501ea8c9135...`; no broad native-fluency claim is made.
- Genuine repair targets remain: BE `1b878f54eff8...` reviewer reports anabolic
  mistranslated as analytical; `769ece1c94cc...` reports mixed fragments such as
  `de`/`getApplication`. Those are reviewer-reported defects, not independently
  certified linguistic findings in this bounded inspection.
- Generation failures sampled: FA `8132cdef9d96...` and LB `dbd5e259d0dc...`
  competing final answer boxes; LB `bdb4ec4e9ecd...` invalid text control.
  BE `bab97cc567bd...` and `647d4a172c6d...` fail pair-array length/schema:
  generated separate user-only and assistant-only objects. The reported
  “too long” is array cardinality, not proof of token-budget exhaustion.

## Minimal future fixes

1. Ensure the private clean-keep rationale adapter reaches BOTH the actual stage
   schema and final validation. Regression-test the saved complete raw response
   through the full request/stage pipeline, not just the adapter helper. Recover
   old rows only with explicit sidecars, original hashes, valid candidate/source
   checks, deterministic checks, global ownership and remaining quota; preserve
   originals and all nonkeep/unknown holds. No blanket ledger promotion.
2. Clarify reviewer context: English source is a fidelity reference; evaluate
   the localized conversation against its actual user instructions. Different
   source and target languages are expected for translation. Retain concrete
   mistranslation/code/schema checks.
3. Use existing safe deterministic code tests to inform adjudication of alleged
   execution failures, rather than trusting unsupported model assertions.
4. Generation instructions should explicitly require one paired user/assistant
   object per source turn-pair and no extra answer box in explanation fields.
   Do not weaken schema or truncate targets. Route concrete repair cases through
   a bounded targeted repair and fresh audit, not more identical generation.

Recommendations only. No attempts were refunded or budgets increased.
