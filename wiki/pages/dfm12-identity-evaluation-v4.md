---
type: Runbook
title: DFM12 Eight-GPU Identity Evaluation
description: CPU-validated whole-conversation sharding and explicit source-review gate for step 2880261 versus 2881261.
tags: [dfm12, identity, evaluation, provenance]
status: stable
last_updated: 2026-09-26
confidence: high
---
# Eight-GPU Identity Evaluation

## Ownership and Gate

The user authorized identity correction and another 1000 updates after the
[third-run semantic review](dfm12-identity-evaluation-v3.md) found material
regressions. Boole owns corrected training data and fresh holdouts; parent and
Harvey own scheduling. This worker owns only the new evaluator, CPU tests and
independent final-data review. No GPU evaluation/training is launched here.

**Initial state, superseded by final readiness below:** source review and
actual-data CPU preflight were pending. Passing
synthetic test fixtures is not permission to launch with unresolved inherited
contradictions. The read-only ledger at
`data/dfm12/identity-v4-readonly-review-20260926-v1` records nine confirmed
contradictions among 241 candidates from all 3951 v3 training rows. Candidates
are contextual review leads, not an automatic deletion list. Strong conflicts
must be cleared in the final artifact, including inherited targets, before the
parent receives a ready disposition.

## Execution Contract

`scripts/evaluate_dfm12_identity_continuation_v4.py` is separate from all frozen
historical scripts. Current SHA256:
`f54a2ddb03edd6ce961b0481cbc2b8309c33195a06a81f1f526b2519b613aece`.
Frozen after actual-data preflight. This supersedes draft pins `bbde252c...`,
`05dd8ff6...` and `1444062f...` after development replay, inherited-wording
checks and strict sealed-v4 provenance reconstruction were implemented.

- Previous default: `checkpoints/dfm12/XL-identity-expanded-from-step2879261`,
  `step_2880261`. New root is explicit; new default tag is `step_2881261`.
- Two sequential checkpoint phases; eight independent spawn workers per phase,
  one physical GPU each, no distributed process group. The inference DCP loader
  uses `no_dist=True`. At most two concurrent checkpoint loads limit CPU/load
  pressure. Each GPU is assigned one initial whole conversation, then workers
  pull remaining whole conversations from a common queue, longest histories
  first. Neither checkpoint nor conversation histories cross workers.
- Workers explicitly override inherited CPU-only CUDA visibility, strip rank,
  master and elastic/MPI environment variables, and disable W&B. Actual launch
  requires all GPUs 0..7 free of other compute processes, with 32 GiB free before
  loading, 8 GiB before generation and a 24 GiB allocator cap per worker.
- Reuse v3's frozen validation and historical raw generation helpers. Same 16
  familiar development regressions plus 50 fresh conversations per language,
  plus all 100 v3 conversations labeled `development_v3`. The old tokenizer-led
  Gemma-weight and multi-turn role failures are therefore directly retested,
  not mislabeled as fresh evidence. There are 216 conversations per checkpoint.
  Final fresh data has 20 multi-turn cases per language, yielding 346 turns
  per checkpoint / 692 total (superseding the single-turn draft estimate of
  306 each). Both earlier
  heldouts are development-only and checked for normalized full
  user-turn/ID overlap, along with the explicit new training shards. This is
  not semantic paraphrase leakage detection.
- Non-EMA, greedy batch one per worker, 512 new tokens, context 4096, raw
  non-thinking training template, no system facts or gold assistant history.
- Each worker atomically persists each turn to its own conversation shard.
  Only the coordinator writes merged `responses.{json,md}` and summaries.
  Merge verifies checkpoint/pin identity, unique cases, exact coverage, turn
  bindings and actual generated history; malformed/empty output fails closed.
- Final `completion.json` pins the merged report hash. Length stops preserve
  `complete_with_length_stops` and exit 0, not semantic approval. Incomplete
  budget exits 3. Failures exit nonzero. The default 3600-second budget is split
  between checkpoint phases and includes loading. After 15 seconds of grace,
  only owned worker processes are terminated and reaped; external processes
  are never signalled. Partial evidence remains available.
- `identity_positive` / `full_suite_approved` remain null and
  `review_required` remains true. Parent semantic review still controls any
  conditional full-suite decision.

## Current Tokenizer Evidence

The actual baseline `train_metadata.yaml` binds
`data/dfm11_tokenizer/tokenizer.json` and `chat_template.jinja`, vocabulary
262144, `jinja_chat_template`, `enable_thinking: false`. CPU preflight records
the metadata and asset hashes and requires agreement with the corpus manifest.
This current XL runtime binding must not be confused with the historical
original HRM-Text custom 65536-token BPE claim. Mimir v1's recorded tokenizer is
Gemma 4; tokenizer reuse does not imply inherited model weights.

`scripts/transfer_sampled_dfm11.py` identifies the Gemma 4 source and project
native template. The independent ledger's `runtime-and-facts.json` establishes
matching cached Gemma 4 vocabulary/merges, but adapted postprocessing and
template. **Do not claim byte identity with the upstream HF tokenizer/template.**
These are project Gemma-4-derived assets. No response-mask bug has been
established; contradictory inherited supervision is concrete evidence.

Independent inspection of the nine confirmed contradictions, roster addition,
and 52 other non-cleared ledger candidates also found explicit bad arithmetic
in DA source row 720, assistant index 1: six L plus two H passes called six
total passes. This needs correction as well as removing unsupported historical
layer comparisons. Final replacement text repairs the arithmetic and removes
the unsupported comparison; see final readiness below.

## Final Readiness

**2026-09-26: READY from source/evaluator review; no blocking semantic issue
found in the corrected source.** Parent may use the authorized 665500 interlude.
No GPU/scheduler action was taken by this reviewer. This is not approval of
future model outputs or the conditional full suite.

- Root: `data/dfm12/identity-corrected-da-en-20260926-v4`.
- Manifest SHA256: `b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b`.
- Receipt: `data/dfm12/identity-evaluation-fourth1000-20260926-preflight-final/source-review.{json,md}`.
- Matching-root preflight report SHA256:
  `a5b4a1256421cc24107792fd5ba682b7f3dc847e9982f0804d71a2a50b533b09`.
- Actual new root: `checkpoints/dfm12/XL-identity-expanded-from-step2880261`.
- Parent's `logs/training/dfm12_XL_identity_expanded_4000steps/spec.json`
  already matches the frozen code pin and exact deferred CLI in the receipt.

Independent checks hashed all manifest files and reconstructed every original
record from the correction ledger, validating message/record hashes, IDs and
the exact duplicate disposition. All 3951 originals reconcile to 3950 retained
records. All 62 assistant corrections (29 distinct replacements) were read;
734 user-scope prefixes add only explicit model/historical context. Nine known
contradictions, the roster addition and other non-cleared ledger candidates are
repaired. None of the superseded bad assistant strings remains as an exact
target. This does not certify all untouched original prose anew.

All fresh question variants and targets were reviewed. V4's actual schema pins
external facts and the inherited answer bank rather than copying them or
emitting heldout-turn provenance. The evaluator validates those pins against
immutable v3 copies, reconstructs every complete fresh native record from the
sealed v4 spec, and requires exact IDs/record hashes. Thus the initially noted
artifact-layout gap is resolved by strict reconstruction, not by weakening
target checks or changing the sealed corpus.

Current runtime vocabulary/merges were independently compared with cached
Gemma 4 and match; postprocessing differs as stated. Fresh target maxima are
57 DA / 45 EN tokens. All 16 regressions and all 100 old v3 development cases
are retained, including tokenizer-led weight-ancestry failures. Source/model
approval remains distinct; semantic output review is still required.

## Deferred CLI

**Operational hold, 2026-09-26, supersedes evaluator readiness above:** the
first automated GPU run failed with zero generated turns. Source-correction
review remains valid, but CPU preflight did not qualify the empty-shard report
path. Do not relaunch this frozen evaluator without a reviewed revision.

The coordinator observed two initial conversation shards with empty turn
lists. The historical summarizer used by `v3.save` divides by `len(turns)` for
an empty suite/language group, raising `ZeroDivisionError`; final error-save
also fails. Actual report status is failed, SHA256
`bfab63a19fdc2a840ee106eb07727fade35bfcaac91742dfaf9cba8e03bd0638`.
No before/after semantic inference is possible. The CPU spawn fixture wrote
completed conversations; the partial merge test did not call report save, so
this integration state was not covered.

The completed `step_2881261` checkpoint exists. Parent's phase receipt records
`scheduler_barrier_released`, so review does not delay XXL resume. No GPU action
or pinned-code/data edit was taken by the reviewer. Separate evidence is in
`data/dfm12/identity-evaluation-fourth1000-20260926/reviewer-assessment.{md,json}`.
A future version must test zero-turn incremental rendering, retain incomplete
evidence, preserve strict final coverage, and use a fresh output for an
externally coordinated retry. This failure is not a negative model assessment.

Replace only the explicit new checkpoint/corpus/spec/pin placeholders after
Boole seals the artifact and independent review clears strong conflicts:

```bash
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/evaluate_dfm12_identity_continuation_v4.py \
  --previous-checkpoint checkpoints/dfm12/XL-identity-expanded-from-step2879261 \
  --previous-tag step_2880261 --checkpoint NEW_CHECKPOINT_ROOT --tag step_2881261 \
  --heldout-root FINAL_V4_ROOT --heldout-manifest-sha256 REVIEWED_SHA256 \
  --heldout-spec metadata/FROZEN_TARGET_BANK.yaml \
  --gpus 0,1,2,3,4,5,6,7 --max-seconds 3600 \
  --output data/dfm12/identity-evaluation-fourth1000-preflight-UNIQUE --preflight-only
```

Harvey's externally coordinated launch uses the same arguments without
`--preflight-only`, a fresh production output directory, and explicit
`CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`. Every worker also assigns its own device,
so inheriting an empty CPU-watcher visibility string cannot disable workers.
Do not launch until the all-eight-GPU release interlude is authorized.

## CPU Verification

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_identity_continuation_v4.py \
  tests/test_dfm12_identity_continuation_v3.py \
  tests/test_dfm12_identity_continuation_eval.py -q
```

70 tests passed, including 32 v4 tests. Eight real CPU spawn workers exercise
the production queue/merge lifecycle with fake inference, including two
checkpoint phases and failure/budget receipts. Tests cover duplicate/missing
cases, incorrect checkpoint/pin/target bindings, gold/cross-case history,
context overflow, malformed output, length-stop completion without approval,
inherited CPU/torchrun environments, fresh split separation, CPU-only preflight
and actual baseline runtime asset binding. GPU loading/throughput is not
validated by these CPU tests. Frozen historical helper hashes remain unchanged.

## Completed Retry and Semantic Review

**2026-09-26: supersedes the operational hold and old evaluator pin above.**
The v4-only reporting adapter filters empty conversations from the legacy
statistics snapshot, while retaining all raw empty/partial conversations and
unanswered prompts. Historical helpers remain unchanged. Combined evaluator
CPU tests passed 74 cases after the adapter fix, including empty eight-worker
startup, partial shards, merge and failed-state reporting. Revised v4 SHA256:
`9e35252aa5f2a6e3bb75120f45a807280c2073d8e56985ba20a504b515ea288d`.
Parent owned the authorized all-eight-GPU retry launch after training was
paused; this reviewer did not launch, stop or resume any process.

Retry root: `data/dfm12/identity-evaluation-fourth1000-20260926-retry1`.
Completion is `complete_with_length_stops`: both checkpoints cover 216 unique
conversations / 346 turns. Report SHA256, matched by `completion.json`:
`879106e0f5bede511fa180c27e2dfa7de4d48bfddfd58beb6d086887a891598b`.
There are six baseline and two continued length stops; these are not implied
successful answers. The original failed artifact is preserved.

The reviewer read all paired regression, development and fresh outputs.
`reviewer-assessment.md` in the retry root records the broad comparison;
`heldout-semantic-review.md` records an explicit per-case/per-turn C/P/W ledger
for every fresh heldout (100 conversations, 140 turns per checkpoint).
Manual semantic counts, not lexical/anchor scores:

| Language | Before correct / partial / wrong | After correct / partial / wrong |
| --- | --- | --- |
| Danish, 70 turns | 39 / 4 / 27 | 38 / 11 / 21 |
| English, 70 turns | 44 / 5 / 21 | 38 / 11 / 21 |
| Total, 140 turns | 83 / 9 / 48 | 76 / 22 / 42 |

Fifteen previously correct fresh turns become wrong. Whole conversations with
all turns correct fall from 55 to 46 of 100. Some errors improve to partial or
correct answers, but material relationship errors remain/newly appear:
fresh DA case 128 T2 reverses scratch origin to Gemma weights; DA 166 reverses
organization/training leadership; DA 136 newly claims byte identity; EN 141/143
invent current tokenizer details; DA 212 and EN 213/215 corrupt historical
totals. Case indices are zero-based, turns one-based. Exact evidence, nuanced
partial judgments, coverage and limitations are in the fresh review.

**Semantic finding:** the requested improvement-without-material-regression
condition is not met. **Separate subsequent user authorization:** the user
accepted the findings and explicitly requested full evaluation of the latest
identity checkpoint. Harvey owns that isolated launch. The negative semantic
finding does not gate or cancel the authorized full evaluation and does not
authorize training/scheduler resumption. No raw report or pinned script was
changed during output review.

## Latest EMA Holdouts

The user subsequently prioritized latest-checkpoint EMA identity holdouts before
the already authorized full evaluation. Parent confirmed training paused, all
eight GPUs free, and the HF exporter complete; Harvey delays the full suite
until operational completion. This does not reinstate the semantic approval gate.

V4 now accepts `--ema --latest-only --heldout-only`; defaults remain the original
two-checkpoint, all-case, non-EMA comparison. New script SHA256:
`4769f3e418694a1ebe69551c08cfe49c4be7cfd151c100f8e9178815691217ba`.
Historical helper and production inference files remain unchanged. Latest-only
uses a local strict completion validator rather than the historical two-run
validator. Readable/JSON summaries identify EMA correctly. Combined CPU suite:
88 passed, including native CPU DCP EMA equality/failure tests and complete
eight-fake-worker EMA/non-EMA latest-only lifecycles. Actual-data CPU preflight
confirmed exactly 100 fresh conversations / 140 turns, under
`data/dfm12/identity-evaluation-fourth1000-20260926-ema-heldout-preflight1`.

EMA passes `True` to the existing inference loader. Config decay must exist;
the pinned checkpoint has decay 0.9999 and 130 EMA tensors / 1,786,773,504
parameters. Each worker independently reloads only EMA tensors on CPU and
requires exact equality of every trainable inference parameter after dtype
casting, recording source-EMA and loaded-parameter tensor hashes. Missing EMA,
coverage mismatch, nonfinite source or equality mismatch fails closed. A flag
alone is not evidence of EMA use. No production-loader modifications were made.

EMA needs a higher temporary memory allowance: FP32 model/moments/EMA alone
total about 26.625 GiB. EMA mode therefore has a 96 GiB per-worker allocator cap
and requires 104 GiB free before loading; non-EMA remains 24 GiB / 32 GiB free.
Both retain eight-GiB pre-generation headroom, two concurrent checkpoint loads,
exclusive GPU checks, raw local training template, generated histories, greedy
512-token outputs, context 4096, batch one, and disabled W&B.

Authorized detached launch: coordinator PID/PGID **2938732**, workers
**2938856-2938863**, physical GPUs 0-7. Output:
`data/dfm12/identity-evaluation-fourth1000-20260926-ema-heldout1`.
Log and pinned launch receipt:
`logs/training/dfm12_XL_identity_expanded_4000steps/identity-ema-heldout1.log`
and `.launch.json`. Native source is
`checkpoints/dfm12/XL-identity-expanded-from-step2880261`, `step_2881261`;
the HF export is not used for this holdout run. Budget is 1800 seconds for the
single phase. No training or scheduler resume is attached to this evaluator.
Old raw comparison reports and their recorded code hashes are preserved.

**Completed:** 100 conversations / 140 turns (70 DA, 70 EN), in 323.8 seconds;
status `complete_with_length_stops`, with 14 DA and 16 EN length stops. Report
SHA256 `7ecfc9c75dd5bb9a260b2ae15f686ebc16ce5c801ec5f4348234ec5191f2068d`.
All eight workers verified all 130 EMA tensors, agreeing on source EMA hash
`8b281785875f1b6966a3cff7b5cc386abf848cc9166ab729061bc4606fcdea39`
and loaded inference hash
`7631fe3b2a0d9bf991bd79ed5e6d3967ffc1c0580c4e728044376d750fe0d382`.
Observed peak allocated memory was about 29.6 GiB per worker. Coordinator and
all owned workers exited; post-completion GPU query had no compute processes.
`operational-verification.json` and `README.md` in the EMA output root preserve
the completed checks and handoff. Preliminary inspected answers still invent
weight ancestry and confuse model weight training with physical exercise;
no exhaustive EMA semantic score is claimed. Harvey may proceed with the
user-authorized full evaluation, independently of those semantic observations.
No training/scheduler restart was performed.

## 10K Same-ID Retest

On 2026-09-27 parent launched sequential EMA/non-EMA fresh-set retests of
`step_2887261` under `data/dfm12/identity-evaluation-10000-20260927/{ema,nonema}`.
Both completed 100 conversations / 140 turns. All 100 IDs, questions, targets,
languages and request bindings match the 4K step_2881261 reports. These are
reused evaluation cases, not a new unseen 10K holdout. EMA length stops fell
from 30 to 19; non-EMA fresh stops remain zero. This is an operational count,
not semantic accuracy.

`comparison.md` in that root records a selective semantic four-way comparison:
30 conversations / 42 turns per checkpoint-mode, plus two additional Danish
non-EMA provenance cases. `comparison-evidence.json` preserves the selected
IDs, exact outputs/histories and all report hashes. No overall semantic score
or exhaustive C/P/W count is claimed.

Non-EMA repairs the prior Danish 557B-token/architecture followup, local
byte-identity answer, selected layer-depth/pass questions and historical totals.
However, fresh DA case 2 now invents Gemma-weight ancestry with 96% layers and
68% units (both turns were correct at 4K); DA 48 newly affirms a false Kristoffer
training co-lead; EN 49 invents technical leader Dajiang Bai; DA/EN 64/65
regress from correct 6 L / 2 H passes. EMA shows local origin/depth gains but
continues substantial ancestry/role/arithmetic failures. The selective evidence
therefore contradicts a clean improvement-without-material-regression claim,
without estimating net accuracy. No evaluator, raw report, process, training
or scheduler change was made, and no benchmark/resume action is automated.
