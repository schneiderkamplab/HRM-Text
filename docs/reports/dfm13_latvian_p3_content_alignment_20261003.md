# P3 CPU content retrieval and resumable source-fidelity queue

## Method

This continues the whole-partition quality hold, not the superseded eight-row
filter proposal. It performs no 31B/26B generation, GPU work, upload, registry
admission or source-ledger mutation.

The pinned [multilingual E5-small encoder](https://huggingface.co/intfloat/multilingual-e5-small)
is used locally on CPU, at revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3`. It is a multilingual embedding
model, not an answer judge. Model files are hash-pinned in
`data/dfm13/latvian-p3-content-alignment-20261003-v1/embedding-model.json`.
Torch inference uses four threads and `CUDA_VISIBLE_DEVICES` is empty. Tokenizer
and data libraries may create additional helper threads; this is not a claim
that the process contains only four operating-system threads.

Both Latvian and English full questions use symmetric query-prefix embeddings.
Inputs longer than 480 encoder tokens are processed in complete chunks, using
weighted mean pooling; no source question or target is truncated. This long-input
pooling is a declared heuristic, not a calibrated translation-alignment model.
References are searched only within the exact source configuration. Neither
ordinal nor original/repaired target answers are used for retrieval scoring.
Content IDs break score ties, so source-array reordering cannot change the result.

Duplicate English question keys are grouped, retaining every distinct English
source answer. They are not resolved by picking one answer arbitrarily. Each
review packet includes the top five full English question groups and all their
answers. An existing independently checked manual reference is additionally
retained if retrieval misses it. No manually identified quality verdict is
placed in the reviewer prompt.

## Uncertainty

Diagnostics include top-one/top-two score margin, near ties (heuristic margin
under 0.02), numeric-anchor mismatch and reciprocal-nearest-neighbor status.
These are neither correctness probabilities nor source-ID proofs. In particular,
similar embeddings can miss negation or omitted premises. All newly retrieved
pairs remain `content_ranked_proposals_unverified`; the 20 existing manual bridges
remain separately identifiable. No additional pair is certified automatically.

Without calibrated validation, per-row correctness probability bounds remain
the uninformative [0,1]. Retrieval recall on the existing manual20 is reported
separately, with descriptive Wilson intervals. Those cases are stratified,
correlated and previously inspected: neither the intervals nor recall establish
population alignment accuracy, Latvian quality or final-answer correctness.

## Durable Queue

Initial E5-only build root (superseded as the review handoff by the fused queue below):
`data/dfm13/latvian-p3-content-alignment-20261003-v1/review-v2/`.
The earlier `review/` attempt is retained; it stopped before adding jobs because
the installed tokenizer removed a legacy special-token API. The replacement
verifies the pinned XLM-R single-sequence token framing and has a regression test.

`embeddings.sqlite` caches vectors by complete text and model/policy contract.
`review.sqlite` uses the existing `dfm12.jobs.Queue` lease/retry/event mechanism,
with custom stage `p3_source_fidelity_31b`. Job IDs hash the full immutable payload;
re-adding identical jobs is idempotent. Existing results/attempts are not reset.
The queue has no launched consumer. A future consumer must use the custom
source-fidelity result protocol, not the legacy three-score audit validator.
`Queue.claim` returns the previous attempt count; consumers pass that count plus
one to `finish`, as tested in the lease/retry regression.

`requests.jsonl` and `content-proposals.jsonl` preserve full native messages and
candidate evidence. `inventory.json` pins job/record identities. The manifest
hashes immutable packet files, not the mutable queue database. Input/code pins
prevent silently resuming with different sources or retrieval code. All payloads
target `google/gemma-4-31B-it`; no endpoint or sender is started. Audit results
must distinguish pairing, source fidelity, factual correctness, instruction
compliance and Latvian quality, with literal supporting evidence. Any future
correction remains a new full-target version requiring independent review.

Reproducible preparation command from the repository root:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
python -m dfm12.latvian_p3_content_alignment \
  --root data/dfm13/latvian-p3-content-alignment-20261003-v1/review-v2 \
  --source-packet data/dfm13/latvian-p3-english-alignment-20261003-v1/review-v2/all-candidates.jsonl \
  --cache-manifest data/dfm13/latvian-p3-english-alignment-20261003-v1/english-cache.json \
  --model-receipt data/dfm13/latvian-p3-content-alignment-20261003-v1/embedding-model.json \
  --threads 4
```

The same command resumes through cached embeddings and idempotent queue inserts.
Do not run two builders against the same root simultaneously. It is not a GPU
launcher or a review sender. The source holds remain authoritative irrespective
of embedding scores or future model suggestions.

## Fused Review Handoff

The sealed fused evidence packet is
`data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2/`.
It contains 7,680 pending jobs, zero attempts and no launched consumer. An actual
repeat preparation verified byte-identical request/inventory hashes and no
duplicate jobs; see `resume-verification.json`. The earlier `fused-review/`
prototype is preserved, but only v2 binds all candidate scores to content IDs.

The fused queue combines E5 top-five retrieval with independent character TF-IDF
top-five retrieval, restricted to source configuration. Full questions and
answers are retained. Existing positional hypotheses remain explicitly
`positional_unverified`, without a score bonus or certification. Candidate order
is content-ID order, not rank order. Duplicate questions retain alternate answers.
There are at most 11 reference groups per request, 2,365 content/positional
disagreements and 1,506 semantic/lexical top-one agreements. Neither agreement nor
small margins certify a pair. Only the previous 20 manual bridges are verified.

On the existing non-representative manual20, E5 recovers 8 top-one and 9 top-five
references; character retrieval recovers 3 top-one and 7 top-five. Their content
union recovers 11/20 (descriptive Wilson interval 0.342-0.742). Adding unverified
positional alternatives includes all 20, but this is **not** independent content
alignment evidence. These weak content results preclude automatic source pairing.
Uncalibrated per-row probability bounds remain [0,1].

```bash
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 python -m dfm12.latvian_p3_review_queue \
  --root data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2 \
  --content-root data/dfm13/latvian-p3-content-alignment-20261003-v1/review-v2 \
  --previous-packet data/dfm13/latvian-p3-english-alignment-20261003-v1/review-v2/all-candidates.jsonl \
  --english-cache data/dfm13/latvian-p3-english-alignment-20261003-v1/english-cache.json
```

The request SHA-256 is
`83aa08a1a1cb7f4c4eff52ebd52c19229d1ddf6aa466d7ab2d286b5b5004caaa`.
The five focused P3 test modules passed 35 tests. No source quality hold was
cleared, no reviewer call sent, and no GPU/server state changed.

## Native Preflight and Compatible Consumer

The executable consumer handoff is now
`data/dfm13/latvian-p3-content-alignment-20261003-v1/consumer-v1/`.
It preserves every fused record and user message, appending only a system-level
result contract. The original fused packet remains unchanged. Its 7,680 jobs
are pending with zero attempts; preparation is idempotent and does not start a
client. Request SHA-256:
`8b99dcca5039d609ff315284d6dd40d92ce97862ef87c530f0ed9b60380e8733`.

Both complete inventories were rendered using the actual cached
`google/gemma-4-31B-it` tokenizer at revision
`842da3794eaa0b77d5f08bae87a17459d91ff475`, with `enable_thinking=false` and the
generation prompt. All 7,680 rows in each inventory pass without truncation:

| Packet | Maximum input tokens | Reserved output | Maximum total | Budget |
|---|---:|---:|---:|---:|
| Fused evidence | 7,646 | 8,192 | 15,838 | 32,768 |
| Consumer protocol | 7,878 | 8,192 | 16,070 | 32,768 |

Each root contains `native-render-preflight.json` with tokenizer/request/file
hashes and `native-render-lengths.jsonl` with every job's count. These are CPU
render checks, not proof that a server is configured to the declared context.

`dfm12.latvian_p3_review_consumer` provides explicit `prepare`, `preflight`,
`enqueue-repairs` and `run` commands. Use the HRM environment, for example:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.latvian_p3_review_consumer prepare \
  --root data/dfm13/latvian-p3-content-alignment-20261003-v1/consumer-v1 \
  --fused-root data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2
```

The sequential `run` client additionally requires explicit `--endpoint`,
`--tokenizer`, `--stage` and optional `--limit` (default one). It is **not launched**.
Stages are `p3_source_fidelity_protocol_31b`, `p3_source_fidelity_repair_31b`
and `p3_source_fidelity_reaudit_31b`. Code/input/tokenizer pins and fresh per-call
full-context checks fail closed. Responses are saved under `raw/` before parsing;
lease/retry failures cannot become keeps. The client has no publication,
registry or source-hold mutation path.

The audit contract checks semantic correspondence in both directions, including
premises, choices, negation and entities, with literal EN/LV quotations. This is
not a claim of a global bijection: duplicate source questions and alternate
answers exist. The independent quality dimensions remain separate. Every model
result is stored with `pairing_certified=false` and `automatic_admission=false`.
Retrieval scores, positional alternatives and model confidence cannot substitute
for independent source identity verification.

Repairs require an external independently verified content-pairing JSONL receipt
bound to `record_sha256`, `candidate_id`, and `candidate_sha256` (canonical
`dfm12.io.digest` of the full candidate), with reviewer, method and evidence.
An audit result alone cannot enqueue a repair. The repair must return complete
messages and a literal change ledger; uncertain repairs remain holds. Every
completed proposed correction gets an idempotent fresh re-audit job, reconciled
again after restart to avoid orphaned re-audits. Re-audit sees the complete
corrected conversation, original conversation and source alternatives, not the
repair model's rationale. Even a re-audit keep does not clear source holds.

Final verification: 42 focused tests passed across the six P3 modules, including
mocked consumer response retention (no network), invalid pairing/keep rejection,
repair-receipt gating, crash-reconciliation idempotence and prepare/resume without
resetting completed jobs. The real consumer queue's repeated preparation retains
all 7,680 pending jobs, zero attempts and identical request hashes; see
`consumer-v1/resume-verification.json`.

## Bulk Pairing Gate Clarification

**Implementation update:** the gap described below is now implemented in the
separate `blind-calibrated-v2` root. Calibration remains unrun, so no pairing
certificates have been issued. See
[blind pairing handoff](dfm13_p3_blind_pairing_handoff_20261003.md) for the exact
control scope, guarded entry point and bounded terminal-disposition protocol.
Historical statements below describe the preceding proposal, not current missing
code. The sealed `consumer-v1` and fused evidence packets remain unchanged.

2026-10-03: independent verification does **not** mean a human bridge for every
row. The existing external-receipt interface does not require a human reviewer.
However, the current consumer does not implement a calibrated blind second pass
or a verifier producing those receipts. Setting `independently_verified=true`
from the first model verdict would not satisfy the intended gate. This remaining
adapter is a real implementation gap, not a permanent manual-approval policy.
No sealed consumer code or queue is changed by this clarification.

Proposed automated completion protocol, not yet executed:

1. Freeze a bounded, independently checked calibration set with true matches,
   plausible wrong alternatives, negation/entity/number/premise changes, duplicate
   questions with conflicting answers, and cases where no candidate is correct.
   Cover all four configurations. Keep evaluation controls out of prompt examples.
   A proposed initial acceptance threshold is zero false supported pairings on
   hard negatives and at least 90% recovery of clear positives; these diagnostic
   thresholds do not establish a population error guarantee. The existing 20
   inspected cases alone do not validate this protocol.
2. First 31B pass compares full LV source questions with all supplied EN
   alternatives. A separate fresh-context blind pass sees the same complete
   evidence in independently permuted order, but no first verdict, rationale,
   ranks, positional origin, manual verification flags or proposed repair.
   Both independently select a content ID or none and document literal anchors,
   alternatives and all changed/missing details. Two calls to the same model are
   operationally blind, not statistically independent; calibration and bounded
   independent spot checks remain necessary.
3. A deterministic verifier emits a versioned model-verified pairing receipt only
   when both calibrated passes select the same unique content group, their quoted
   evidence exists, and their constraint checks establish an unambiguous source
   correspondence. Bind both request/result hashes, source snapshot/candidate
   hashes, calibration receipt and verifier version. Model probability or ordinal
   agreement is never enough. Preserve duplicate-answer ambiguity explicitly.
   Source identity is separate from translation fidelity: a clearly identifiable
   damaged translation can be paired while fidelity fails and repair is required.
   If damage prevents unique identification, reject the row.
4. Pairing agreement does not establish answer correctness. Independently score
   fidelity, correctness, instructions and Latvian quality. Repair only grounded
   defects against the verified source, then re-audit the entire proposed version
   without the repair rationale. Unsupported factual claims and uncertain source
   answer keys remain rejects/holds, not forced restorations of English gold.
5. Disagreement, absent correct candidates, ambiguous identity and unresolved
   correctness receive terminal rejected dispositions with reasons. A bounded
   repair/re-audit attempt budget prevents infinite retries. Completing all 7,680
   means accounting for every row, not accepting all rows. Any later admission
   requires the versioned release checks and explicit source-hold supersession;
   the current held originals are never mutated.

The blind-check/receipt adapter and its calibration are still to be implemented
and tested before automated receipt issuance. No review/GPU call was launched.
