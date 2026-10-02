---
type: Runbook
title: DFM12 Third Identity Continuation Evaluation
description: Fresh-holdout pins, development-set policy, and operational versus semantic completion for step 2879261 to 2880261.
tags: [dfm12, identity, evaluation, provenance]
status: stable
last_updated: 2026-09-26
confidence: high
---
# Third Identity Continuation Evaluation

## Scope

The user authorized another 500 DA and 500 EN training conversations retaining
prior training data, another 1000 updates, and 50 fresh heldout conversations per
language. Boole owns corpus preparation; parent owns scheduler/training. This
page owns only the separate evaluator and factual target-review handoff.

`scripts/evaluate_dfm12_identity_continuation_v3.py` compares non-EMA
`step_2879261` in `checkpoints/dfm12/XL-identity-expanded-from-step2878261`
against `step_2880261` in an explicitly supplied new checkpoint root. No GPU
evaluation was launched during implementation.

The historical evaluator `scripts/evaluate_dfm12_identity_continuation.py` is
unchanged, SHA256
`a0270f1073927320e00d9799d6e3e99a965307d79555445258a3144823e6af35`.
V3 imports its generation/report helpers read-only and refuses helper or
regression-source drift. The [historical outcome](dfm12-identity-extension.md)
and its exit-code-4 receipt remain unchanged historical facts.

## Evaluation Contract

- Preserve the exact previous 16 regression prompts and reference targets.
- Evaluate only 100 newly pinned heldout conversations. Old v2-r2 heldouts and
  familiar regressions are explicitly development evidence, not fresh evidence.
- Require explicit `--heldout-root`, `--heldout-manifest-sha256`, and
  `--heldout-spec` (manifest-listed relative frozen YAML path). Never infer
  the reviewed SHA from whatever currently exists on disk.
- Verify native alternating roles, 1-4 turns, 50 cases per language, record
  hashes, per-turn provenance, and targets reconstructed from frozen
  request/answer-form bindings. Reject unsafe paths and missing/extra IDs.
- Check normalized full user-turn wording and IDs against old evaluation and
  the two explicit merged training shards. This is not semantic paraphrase
  leakage detection; the builder remains responsible for atomic-question and
  family-level separation.
- Require unchanged pinned identity facts, tokenizer, and raw non-thinking
  template. A changed facts registry needs a reviewed contract change.
- Model-generated assistant history only, no system/fact priming, greedy
  batch-one decoding, 512 output tokens, context 4096 without truncating input.
- Incremental JSON/Markdown after each completed turn includes prompts, targets,
  responses, token IDs, stop reasons, dataset pins and checkpoint metadata hashes.
- Only physical GPU 7 after external coordination. Refuse another compute
  process; require 32 GiB free before load and 8 GiB before generation; cap
  PyTorch allocator at 24 GiB. Checkpoints are loaded sequentially.
- Default total model-evaluation budget is 3600 seconds, split equally between
  checkpoints. SIGALRM interrupts Python; in-flight native/CUDA calls must
  return first, and cleanup is additional. Partial coverage is not success.

## Operational Completion Is Not Approval

| Outcome | Exit | Meaning |
| --- | ---: | --- |
| `complete` | 0 | All requested turns generated to EOS; parent still judges facts. |
| `complete_with_length_stops` | 0 | All requested turns generated; length-limited text remains flagged, never assumed correct. Manual review must not be skipped as an operational error. |
| `incomplete_budget` | 3 | Time budget prevented full coverage; incomplete, not success. |
| Bad pins, checkpoint/load/runtime failure, empty/malformed generation, inconsistent tokens/stops or coverage | nonzero | Fail closed; retain available output/error evidence. |

`identity_positive` and `full_suite_approved` remain null;
`review_required` is always true. No lexical/name/number score can approve
a full suite. Semantically wrong but structurally valid answers are review
findings, not reliably detectable operational failures.

## Source Review History

The draft bank `dfm12/identity_repair_expansion.yaml` is now available, SHA256
`3134349ab47610c0fcef58b501a15f12beea9502f62afa1ce6ed2dee1c5e42c0`.
The reviewer read all 27 requests (108 brief/contrast targets across DA/EN),
their train/heldout questions, and all 50 training + 10 heldout opening families.
No blocking factual contradiction was found in this draft. It keeps strict
role bindings, original from-scratch versus continued learned weights, Gemma
format versus model weights, and historical/current numerical units separate.
The new `checkpoint_continuation` fact is explicitly attributed to the user
clarification in `authorized_context`, not invented as a historical report fact.

**Superseded draft pin, 2026-09-26:** the reviewed source now hashes to
`0242bf5c906fdfbedf5a525bdb6470cd5051e62ff86e6a37300e305e15cd8e9a`.
The continuation opening was rephrased as a neutral comparison matching its
neutral targets. The reviewer re-read all 108 targets and 60 opening families.
No blocking factual contradiction was found. CPU `compile_spec` and
`check_lineage` passed: each language has 500 new training conversations / 950
assistant targets and 50 heldouts / 95 targets. Inherited training is 1469 DA
and 1482 EN records. Fresh plus 16 regression evaluation therefore has 206
answer turns per checkpoint, 412 total, not 100 times 190 turns.

The v3 builder records each turn's `mode` (`brief` or `contrast`) rather than
v2's `answer_forms` list. The new evaluator explicitly recognizes the
`dfm12-curated-identity-repair-v3` mode schema and reconstructs each target.
New request names also map to the existing limited role/history review flags;
the original provenance request IDs remain unchanged in reports.

These were agent reviews of source targets, not independent human/native gold
or approval of generated model outputs. The earlier pending artifact/preflight
state is superseded by the final handoff below.
Direct agent messaging was unavailable; coordination requests were sent through
the parent-facing thread.

Review complete question/answer bindings in both languages: model origin from
scratch rather than Gemma weights; tokenizer reuse is not weight initialization;
continued training does not imply this phase resets weights. Peter leads the
training team; Kristoffer Nielbo and Peter Schneider-Kamp lead DFM. Do not invent
CEO titles, team membership, historical hardware, dates, batch counts or
tokenizer provenance. XL 16/16 layers, 2 H with 3 L cycles each, 6 L + 2 H
passes and full backprop must not overwrite historical v1 truncated-five-step
claims. Old-heldout failures used to design examples are development evidence.

## Final Frozen Handoff

**2026-09-26: no blocking target factual findings; CPU preflight passed.**
No target-review or evaluator-support blocker to the parent's planned 663000
checkpoint arming. No GPU, scheduler, or training action taken by this worker.
This is not acceptance of future model outputs or the conditional full suite.

- Final root: `data/dfm12/identity-repair-da-en-20260926-v3`.
- Manifest SHA256: `af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1`.
- Final frozen bank: `metadata/identity_repair_expansion.yaml`, SHA256
  `dbfc93916f38adaae9ab0457922ddab904976a142c7fc517cb1dcf66fd7c99b8`.
- Evaluator SHA256: `fe8e8d6b6fe1a7758f900b25c61263a918988ff79c856df6d1d9684886f3b4e1`.
  No further script edits after freezing.
- Receipt/readable disposition:
  `data/dfm12/identity-evaluation-third1000-20260926-preflight/target-review.{json,md}`.

The final bank supersedes both draft pins above and adds the synthetic-text
versus copied-weights distinction. All 28 bilingual requests / 112 targets
and 60 opening families were re-read. No blocking factual inconsistency was
found; final artifact verification and target reconstruction passed.
Merged counts are 1969 DA / 1982 EN conversations, preserving earlier training
plus 500 new each. Prior heldouts remain development-only and excluded from
training. Fresh response token maxima are 123 DA / 92 EN; 512 remains the
generation cap, without implying that capped answers are complete.

CPU-only reproduction into a **fresh** preflight output directory:

```bash
CUDA_VISIBLE_DEVICES='' /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/evaluate_dfm12_identity_continuation_v3.py \
  --checkpoint NEW_CHECKPOINT_ROOT \
  --heldout-root data/dfm12/identity-repair-da-en-20260926-v3 \
  --heldout-manifest-sha256 af0b82b1dfa43012893cd54255923cf15fc5fca67627f16efacfcd0fc6f8bbf1 \
  --heldout-spec metadata/identity_repair_expansion.yaml \
  --output data/dfm12/identity-evaluation-third1000-preflight-reproduction --preflight-only
```

Deferred execution uses the same reviewed arguments with
`CUDA_VISIBLE_DEVICES=7`, without `--preflight-only`, and a fresh output
directory. Default tags: `step_2879261` and `step_2880261`.
`--previous-checkpoint` is supported. Parent coordinates the interlude;
this evaluator never starts a scheduler, training, or a full-suite job.

## Third-Run Semantic Review Handoff

On 2026-09-26 the existing automation's
`logs/training/dfm12_XL_identity_expanded_3000steps/spec.json` fixes the new
checkpoint root as `checkpoints/dfm12/XL-identity-expanded-from-step2879261`,
tag `step_2880261`, compared with the previous root/tag documented above.
Its output is `data/dfm12/identity-evaluation-third1000-20260926`.
This supersedes any placeholder new-root names in preflight examples, not
the frozen corpus or evaluator pins. Both final pins were rechecked unchanged.

At the initial monitoring check training had reached step 2879910; the
evaluation directory did not yet exist. This is a pending review, not an
evaluation outcome. Existing automation owns the GPU launch. Do not run a
second evaluator or alter pinned scripts, scheduler state, or training.

The reviewer will inspect all 16 familiar regressions and all 100 fresh
heldout conversations for both checkpoints, including every generated-history
turn (206 turns per checkpoint). Record missing coverage explicitly if the
bounded evaluator stops early. Read incremental artifacts provisionally and
pin the final report hash only after completion. Write the separate
`reviewer-assessment.md` beside the completed report; never rewrite its
responses or machine approval fields.

Review dimensions, separately for DA and EN:

- From-scratch origin versus Gemma tokenizer/template reuse, synthetic text
  versus copied weights, and continued learned weights versus reinitialization.
- Organization leaders versus Peter's training-team lead role, exact member
  identities, and unsupported titles or historical claims.
- Architecture, module passes versus layers, current full backpropagation
  versus historical truncated backpropagation, and numerical units/provenance.
- Paired improvements and regressions across actual multi-turn histories;
  valid paraphrases count as correct without exact target matching. Distinguish
  unsupported assertions from omissions or a failure to elicit an answer.
- Length stops remain reviewable but do not establish an unseen conclusion.
  Report coverage and stopping behavior separately from factual quality.

The recommendation must explicitly judge whether improvement is clear without
material factual regression; uncertainty stays explicit. Parent review owns
the conditional full-suite decision, never lexical heuristics or operational
exit zero. Old heldouts remain development evidence. Poincare's revised pilot
evidence/calibration contract is separate; any coordination here is CPU-only
and does not authorize a new 31B launch.

## Third-Run Semantic Outcome

**2026-09-26: completed CPU semantic review recommends against advancing to the
conditional full suite.** The evaluator finished `complete_with_length_stops`.
All 412 generated answers were compared: 116 conversations / 206 turns per
checkpoint, 103 turns per language. Case-ID and coverage checks passed.
Final `responses.json` SHA256:
`02f5b0d93f785c45967f0616bb9066ebb19b7e8e6bd07dbd002ce3df02a74b1e`.
The prior pending-review state above is superseded by this outcome.

Own readable and structured reviews are
`data/dfm12/identity-evaluation-third1000-20260926/reviewer-assessment.{md,json}`.
The readable report covers all 16 regressions and all 100 fresh heldouts with
paired case/turn evidence. This is agent semantic review, not independent
human gold or lexical-score approval.

There are genuine improvements in scratch explanations, context/dataset units
and some role bindings. However, Danish familiar architecture recall regresses
to denying known facts; fresh Danish answers invent a team leader and a
Copenhagen department. Fresh English tokenizer-led openings now assert Gemma
weight fine-tuning (cases 107/111/115 T1), and 115 T4 changes correct Peter-only
training leadership to Kristoffer/Peter co-leadership. Numerical architecture
and historical facts remain unreliable in both languages. This fails the
condition of clear improvement without material factual regression.

Length stops were one before and two after; their visible text was reviewed
without assuming an unseen ending. Parent's separate operational
`review_deferred_resume_training` decision was not a semantic rejection and
was not modified by this reviewer. XXL resume need not await this review;
no GPU/scheduler action, pinned-code alteration or full-suite launch was taken.

## Test Commands

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_identity_continuation_v3.py \
  tests/test_dfm12_identity_continuation_eval.py -q
```

38 tests passed on CPU: explicit pins, development/training separation,
target bindings, malformed-output rejection, length-stop completion without
approval, incomplete-coverage failure, CPU-only preflight, persisted errors,
historical preservation, and original generation/history/stop tests. Fixture
success is not approval of model output. The tests include the final sealed
corpus and source-role/origin/history guards. OKF validation passed without
errors or warnings.
