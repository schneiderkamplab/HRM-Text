---
type: Runbook
title: DFM12 Second Identity Interlude
description: Checkpoint-safe second thousand identity updates, non-EMA comparison and bounded parent-reviewed full-suite gate.
tags: [dfm12, identity, training, scheduler]
status: draft
last_updated: 2026-09-28
confidence: high
---
# DFM12 Second Identity Interlude

## Corrective Continuation Completed, 2026-09-28

### Full EMA Suite Authorized And Started

The user's later 2026-09-28 request supersedes the earlier lack of full-suite
authorization below; it does not change the semantic review verdict. Full
standard, DFM and EuroEval evaluation now uses the existing `eval_scheduler`
and Rich monitor, not a custom evaluation runner. Plan:
`logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928`.
Preparation helper: `scripts/schedule_identity_final_ema_full.py`.
The detached persistent-vLLM runner started as PID 2948694; monitor is in
tmux `hrm-117:8` (`identity-final-eval`, 30-second refresh).

The fresh EMA export is
`exports/dfm12_XL_identity_step2897261_ema_hf_training_tokenizer`.
Export produced 131 tensors with no dropped tensors. The preparation receipt
checks training tokenizer bytes, pretokenizer, chat template and ten token-ID
probes, with `fix_mistral_regex=false` in this export. Ordinary servers use
utilization 0.45; judged tasks use 0.30 plus the usual managed Gemma 4 E4B
judge. Both remain below the requested 0.5 server cap. Initial free-memory
gates are 90,000/93,000 MiB respectively. Existing audit/generation servers
on ports 8600-8607 were not stopped or reconfigured.

The 290-row plan retains existing suite exclusions (valeu-da and unavailable
Andersen validation), skips the unrelated report update, and contains no
training continuation. Five eval tasks had completed, eight were active and
none had failed at the initial verification. Merges, syncs and averages use
the normal scheduler actions and existing `DFM5/dfm12-xl-identity-da-en-1000`
run at fractional epoch 10.050795912217435 (20,000 total identity updates
after epoch 10), not the temporary data-packing epoch number.

Normal multilingual production was independently verified running after the
outage recovery: 539 accepts recovered; 172,367 cumulative accepted rows and
188 active requests at this check. All eight original server API PIDs remained
alive. Some Faroese source-dependent groups still report seed shortages;
resumed production does not imply every language group is unblocked.

### Full-Suite Merge Recovery

All 242 enabled GPU jobs completed, but 39 CPU merges failed due to mismatched
archive paths. See [identity full-eval recovery](dfm12-identity-full-eval-recovery.md)
for the preserved outputs, scheduler repair and remote verification.

The GAS8 fallback continuation finished at **step 2897261**, completing the
requested 10,000 updates from 2887261 including the earlier handoffs. The final
full-state checkpoint is in
`checkpoints/dfm12/XL-identity-after-gas-probe-from-step2888200/fsdp2_step_2897261`.
The supervisor recorded completion and the trainer returned zero; all eight
owned training workers exited. W&B's final log reports synchronization to the
existing identity run, not a new run. EMA decay/reset and the split mixture
were unchanged.

Recent local history windows 2895200..2896200 and 2896200..2897205 had mean
loss 0.70021/0.70085, token accuracy 0.82930/0.82926 and exact accuracy
0.42963/0.42743. These broad-mixture measures are not identity factual scores.

An EMA-only sealed composition evaluation was launched with eight workers and
no W&B logging. Output:
`data/dfm12/identity-composition-eval-2897261-ema-20260928`.
The existing adapter passed CPU preflight and 70 focused tests. Its checkpoint
and explicit post-training release receipts live under
`logs/training/dfm12_XL_identity_gas4_probe_step2888200/` as
`evaluation-training-completion.json` and `evaluation-gpu-release.json`.
The former supplements the probe supervisor's shorter completion receipt with
the verified output directory and checkpoint-state hash; it does not alter the
original receipt.

**Completed review:** the first attempt cancelled at GPU7's conservative
92 GiB free-memory load gate, not an OOM. The adapter now allows a smaller
allocator budget while retaining the overhead/headroom and half-device guards.
The retry with `--allocator-limit-gib 64` completed all 80 answers at
`data/dfm12/identity-composition-eval-2897261-ema-20260928-retry1`.
All eight workers verified their loaded EMA tensors and exited. Their sampled
peak footprints were 31,384-31,462 MiB. No shared server was changed.

Parent semantic review: Danish 31 correct / 1 partial / 8 failed of 40;
English 32 correct / 2 partial / 4 failed / 2 output-limit invalid of 40.
Both direct full rosters and leadership answers are correct, but unsupported
titles, tokenizer inheritance, architecture arithmetic and false-premise
corrections remain unreliable. Some English answers leak literal think markup.
The old 140-answer diagnostic differs, so these are not paired improvement
scores. No clean identity pass, full-suite authorization, or new training.
See the retry's `parent-review.md` for every turn's assessment and caveats.

## GAS4 Probe And Resume, 2026-09-27

**Supersedes the live PIDs below, not the split-mixture recipe:** at user
request, sole watcher3730280 preserved complete `ephemeral_step_2888200` at
`checkpoints/dfm12/XL-identity-gas4-handoff-step2888200` and stopped only the
recorded training owner. The parent stopped its duplicate watcher separately.
The preserved checkpoint retains epoch17, batch6400 and global row cursor501566.

`scripts/identity_gas_probe.py` ran bounded, no-W&B GAS4 probes under the same
43% allocator cap and48% owned-memory guard. GAS4 without checkpointing hit a
confirmed CUDA allocator OOM; peak observed owned memory was43.7%, below the
50% ceiling. GAS4 with full activation checkpointing failed PyTorch's
recomputed-tensor metadata consistency check on its first update, including
saved `[6144,1536]` versus recomputed `[1536,6144]` tensor shapes. This is a
recomputation failure, not evidence of memory qualification or speed. Neither
probe produced a valid completed three-update benchmark. No consistency check
was bypassed and no architecture repair was attempted during the interlude.

Automatic fallback resumed **GAS8/no-checkpointing from the untouched2888200
checkpoint**, never probe weights. Supervisor **3733543**, trainer **3736879**
have completed real step **2888202**; W&B resumed the same
`DFM5/dfm12-xl-identity-da-en-1000` run. EMA state/decay0.9999, optimizer, LR1e-5,
GBS262144, data and final step **2897261** remain unchanged. There were9061
updates remaining at the handoff, not another10K. CPU packing verified9270
available GAS8 updates from the retained row cursor;43 focused CPU tests passed.
No foreign audit PID/server was signalled. Real training remains in progress.

Evidence is under `logs/training/dfm12_XL_identity_gas4_probe_step2888200/`:
`selection.json`, `remaining-packing.json`, `resume-preflight.json`, both
`configs/smoke-*.failure.json` and memory/log records, and `configs/train.log`.
The separate real output is
`checkpoints/dfm12/XL-identity-after-gas-probe-from-step2888200`.

## Split Identity Resume, 2026-09-27

**Supersedes the 95/5-only running recipe below:** the user authorized
**95% DFM11 / 2.5% reviewed corrective / 2.5% corrected-v4 synthetic identity**
for the remaining course, retaining the original end step **2897261**.
The original owned run stopped after preserving complete
`ephemeral_step_2887400` at
`checkpoints/dfm12/XL-identity-corrective-split-handoff-step2887400`.
Its `handoff-stopped.json` confirms the recorded supervisor and descendants
exited. No foreign process was signalled and no existing token files were edited.

Actual continuation is running under supervisor **3680240**, torchrun
**3680399**, from **2887400** with **9861** planned updates. A fresh isolated
resume view preserves full-state payloads through hard links, changing only
data cursor metadata: trainer epoch **17**, data index **16**, zero cursor.
Optimizer and EMA state are retained; EMA decay **0.9999**, no reset, constant
base LR **1e-5**, BP8, GAS8 and GBS262144 are unchanged. W&B confirms resumption
of `DFM5/dfm12-xl-identity-da-en-1000`. Subsequent evaluation/export remains EMA-only.
Live recheck observed completed step **2887809** and owned NVML memory
**32.66-33.92% per GPU**, with the 43% allocator cap and 48% owned-memory guard
active beneath the user's 50% ceiling. This is running, not completed training.

The verified mixture is `data/sampled_dfm11_identity_split_remaining9861steps`:
**2,585,002,651 rendered tokens**, including **64,625,292 corrective** and
**64,625,209 synthetic** tokens. Packing provides **10070** updates for9861.
Corrective249 targets repeat1482-1483 times; synthetic7748 targets repeat45-46
times. Heldout, development and validation files are not sampling inputs.
All synthetic target spans were reconstructed exactly from the sealed v4
training messages. Source evidence reuses the existing independent READY review
at `data/dfm12/identity-evaluation-fourth1000-20260926-preflight-final/source-review.json`;
`synthetic-source-revalidation.json` in the previous supervisor state explicitly
does not claim a newly performed independent handoff review or human gold.

Evidence: `logs/training/dfm12_XL_identity_split_remaining9861steps/` contains
`resume-preflight.json`, `launch-verification.json`, `configs/train.process.json`
and `configs/train.log`. New checkpoints are written separately under
`checkpoints/dfm12/XL-identity-split-from-step2887400`.
Mixture receipt SHA256:
`071e39d41cad0b71ef5465efd9400704ca83ad30e982cb0207ba01900629929b`.
**60 CPU tests passed** before launch. Retained failed attempts document two
fixed preparation issues: DFM11's4097 stored tokens represent4096 next-token
positions, and the supervisor CLI must pass `--spec` to its `spec_path` parameter.
No model architecture or live training-code edits followed launch.

## Corrective 10000-Step Supervisor, 2026-09-27

**Live launch update, 2026-09-27 09:39 Europe/Berlin:** the preparation-only
and earlier supervisor statuses below are superseded. Supervisor **3583634**
launched actual training under torchrun **3585802**, after a clean three-update
smoke and verified complete `step_2887264` checkpoint. Actual training resumes
the original **2887261**, not smoke weights; step **2887268** has completed.
W&B confirms resumption of `DFM5/dfm12-xl-identity-da-en-1000`. Current owned
NVML usage is **32.66-33.92% per GPU** (58.48-60.73 GiB), with the allocator
cap and live guard active. Foreign audit processes were left untouched.
Training remains in progress; no semantic improvement or completion is claimed.

The ownership monitor now follows verified launcher descendants because
TorchElastic workers create separate process groups. A subsequent normal-exit
PID lookup race is handled without treating an already-exited rank as failure.
Earlier owned attempts were stopped, retained and superseded; **47 combined
CPU tests passed** before the clean smoke and current launch. Current spec
SHA256 is `50204a9c9cce2ccd8664eb87d491e1e7ddf068a1ba12cab35cbf84c7eb3b4364`.
Evidence lives under `logs/training/dfm12_XL_identity_corrective10000steps/`:
`configs/smoke-none.completion.json`, `configs/train.process.json`, and
`configs/train.log`. No code changes or re-pinning followed this launch.

The built mixture contains **2,621,440,994 rendered tokens**, including
**131,072,051 identity tokens** from249 unique targets repeated3,005-3,006
times. GAS8 packing supplies10,211 updates for the requested10,000. Prepared
identity response-token share is4.3255%; the first10,000 packed updates contain
4.9830% identity rendered tokens and4.3248% identity response tokens. These
measured packing proportions accompany, rather than silently replace, the
authorized5% rendered-token sampling recipe. Dataset and build receipt:
`data/sampled_dfm11_identity_corrective10000steps/`. Validation and sealed
holdout rows are excluded.

**User-authorized, superseding earlier short-course and 0.5% proposals:**
prepare 10,000 updates from full-state `step_2887261` to **2897261**, using
**95% DFM11 / 5% final targeted identity SFT by rendered tokens**. At GBS
262144 the identity budget is **131,072,000 tokens**, not 13,107,200. Report
actual repetition and supervised-response fractions; do not silently reduce
the fraction or cap repetitions. The parent's final 560-stochastic-turn review
and sealed holdout remain prerequisites; earlier reviewed subsets are not
eligible substitutes.

EMA decay **0.9999**, active weights, optimizer state and existing EMA state
are retained unchanged. No reset or replacement of active weights by EMA is
allowed. Subsequent evaluation/export is **EMA only**. Constant base LR 1e-5,
lr_auto, no warmup/decay, BP8 and GBS262144 remain fixed. A fresh resume view
hard-links immutable checkpoint payloads and changes only copied cursor
metadata to epoch **16**, zero batch/row cursor, using data alias `epoch_15`.
Canonical source is `checkpoints/dfm12/XL-identity-expanded-from-step2881261`;
new output is `checkpoints/dfm12/XL-identity-corrective10000-from-step2887261`.

New isolated implementation:

- `dfm12/build_identity_corrective.py`: verifies final parent-packed train
  spans against exact final-answer-only labels, excludes validation, reuses
  compact-copy/packing helpers, and reports unique rows, repetitions, response
  supervision, packed coverage and hashes. No clipping or historical corpus edits.
- `scripts/identity_corrective_worker.py`: installs a **43% per-rank PyTorch
  allocator cap** before importing the trainer.
- `scripts/identity_corrective_supervisor.py`: detached receipt-gated process,
  production-resolver preflight, no-W&B three-update memory smokes with GAS8
  and checkpointing none then full if necessary; successful geometry is reused
  for the actual run. Smokes are discarded and actual training resumes the
  original full-state checkpoint, not smoke weights.

Memory policy applies to **this thread's owned processes combined**, not
foreign work. Unrelated `european_stage` audit servers may remain at about45%
per GPU. Never signal them. Launch requires at least46% actual free memory
(43% allocator plus3% margin). The live NVML guard sums only verified training
process-group usage per GPU and stops that owned group at48%, below the user's
50% ceiling. Independent review tightened this to include separately registered
thread-owned processes/groups from the release receipt's optional
`thread_owned_processes` list; launch also requires existing registered usage
at most2% per device to leave room for the allocator and driver reserve.
Foreign processes remain excluded from the owned-usage sum, but consume actual
free headroom. CUDA allocation caps do not cover all driver memory, hence both
checks are needed. This is not a measured fit claim: GPU smokes have not run.
Cleanup verifies PID/start-time/command/process-group ownership; no foreign PID
or scheduler is stopped. The original XXL scheduler remains untouched.

State: `logs/training/dfm12_XL_identity_corrective10000steps/`.
Detached supervisor PID **3561419** is armed, **waiting for final data**;
`supervisor-process.json` records its identity. At this preparation point no
GPU worker, smoke, training, W&B session or export has started.
**Superseded operational status:** PID3561419 was verified and stopped before
independent-review fixes. Parent subsequently accepted the final249train/82validation
packed corpus at `data/dfm12/identity-ema-preferences-20260927-v6-targeted-v1-packed`,
manifest `dbea914ca9495e9ba5f93bb0ab2662c1a29433c3ce23fdba5ec79bacfc32c730`,
and supplied both final-data and GPU-release receipts. Tesla's revised review
passed, with43combined CPU tests and a separate parent18-test pass reported.
Supervisor **3574035** was re-armed to build the mixture and proceed through
the gated smoke and training sequence. Spec SHA256:
`b748962f7cd18ea5870315c8be174632a8e60c8f5d9b127691aac9ca5e4e2c37`.
The old spec is retained as `spec.before-independent-review-fixes.json`.

Smoke success now requires a complete **step2887264** DCP checkpoint, epoch16,
batch24 (three GAS8 updates), positive row cursor, exact metrics for steps
2887262/2887263/2887264, finite metrics, no skipped updates, and optimizer-end
traces from all eight ranks. `smoke-*.completion.json` pins checkpoint metadata,
metrics and log hashes. Actual training still resumes **2887261**, never smoke
weights. Forced stop checkpoints are expected despite disabled periodic saves:
the source is about27GiB, so each completed smoke writes approximately that
much full-state data. Disk preflight reserves two smoke checkpoints plus25%
margin and retains failures; actual training separately reserves42 checkpoints
plus25%. Only identified CUDA OOM or an owned-memory guard breach permits the
full-checkpointing fallback. Timeout, infra, and missing-update/checkpoint
failures stop the supervisor instead of being misclassified as memory pressure.
`spec.json` pins source/config/code. Parent handoff files in that directory:

```json
{
  "packed_root": "/absolute/path/to/FINAL-parent-packed-root",
  "packed_manifest_sha256": "FINAL_MANIFEST_SHA256",
  "final_review_complete": true,
  "reviewed_stochastic_turns": 560
}
```

The above is the contract for `final-data-ready.json`, not a pre-created
approval. Packed root must have `train/`, `validation/`, and the existing parent
packer's `manifest.json`. Publish readiness only after packing and final review
are complete. The supervisor builds
`data/sampled_dfm11_identity_corrective10000steps`, then waits for
`gpu-release.json`:

```json
{
  "campaign": "identity-corrective10000",
  "retry_finished": true,
  "owned_servers_released": true,
  "gpu_launch_released": true,
  "owned_processes": []
}
```

Populate `owned_processes` with retry PID identity receipts (`pid`,
`start_ticks`, `pgid`, hexadecimal `cmdline`); any still-matching process blocks
launch. Parent/Harvey owns explicit release after its retry servers exit;
the supervisor never kills them to obtain resources. Empty list is appropriate
only when no owned processes need checking, not as a release bypass. Actual
free-headroom and same-W&B-run conflict checks are repeated before launch.
Actual training resumes `DFM5/dfm12-xl-identity-da-en-1000`; all smokes disable
W&B. No automatic DPO or evaluation campaign is started.

**38 CPU tests passed** across corrective training, parent packer and adaptation:
5% arithmetic, EMA/optimizer preservation, production config validation,
receipt gates, old-subset rejection, exact packed masking/spans, tiny fixture
mixture, co-resident headroom and foreign-process cleanup safety. Actual final
counts, mixture hashes, GPU fit and launch remain pending final-data/release
receipts. Launch logs and completion receipts, not this armed status, establish
execution.

## EMA-Only Preference Follow-Up, 2026-09-27

Supersedes earlier recommendations to compare or export non-EMA identity
models: the user requires EMA only. Do not propose system-message changes;
system messages already exist in deployment.

Use latest identity checkpoint `step_2887261` EMA answers, including good
answers and hallucinations, to build a shared fact-verified preference corpus.
Preserve exact prompts and conversation histories. Verify chosen corrections
against approved identity facts; record original answers, corrections and
evidence. Correct sampled answers can be chosen only after verification.
Do not fabricate rejected answers for prompts with no observed bad answer.
The chosen side supplies targeted corrective SFT; chosen/rejected pairs supply
DPO. Split by prompt/conversation family before augmentation, and reserve new
holdouts because previous probes now inform development. Training itself is
not authorized by this preparation request.

The user authorized the second multilingual pilot first, then stochastic
answer collection with the latest EMA checkpoint. Proposed collection uses
four seeded samples per prompt at temperature 0.7 and top-p 0.9, retaining
greedy answers as a baseline. Sampled correctness is not assumed. Start only
after pilot completion and release of its GPU resources; do not terminate
unrelated audits or resume training. Calibration failures must remain visible
and must not silently admit unverified multilingual examples.

## Authorized Scope

### Independent Preference Corpus Review, 2026-09-27

Independent CPU review accepted the pinned preparation subset at
`data/dfm12/identity-ema-preferences-20260927-v1`: 42 chosen SFT rows and
37 DPO pairs (train 34/30; validation 8/7). All chosen answers were inspected
against the identity registry and current XL/tokenizer correction notes.
Exact generated-history continuity passed for all 140 source turns; the
remaining 98 turns are unreviewed and excluded. Token-level checks passed for
all exported rows, including final-only loss masks. Earlier generated
assistant errors remain context and must not receive SFT loss. Partial-answer
preferences are not all factual-error corrections; reused families remain
development material, not a fresh benchmark. This is coding-assistant review,
not human signoff or a training launch. Receipt and per-answer review:
`data/dfm12/identity-ema-preferences-independent-review-20260927-v1/`.

**Coverage superseded later on 2026-09-27:** Jason completed all 140 reviews.
Independent review of the remaining 98 chosen answers accepted the final
`data/dfm12/identity-ema-preferences-20260927-v3-reviewed` corpus: 140 SFT
rows and 114 DPO pairs, with no unreviewed turns. Train counts are 108/87;
validation counts are 32/27. All 140 final-answer tokenizations and 114
source/rejected pair bindings passed, along with 13 package hashes and four
checkpoint metadata pins. Manifest SHA256:
`ffe454b2e629f5b1cee21ab54a44b5d2a1e4ba54e411c4b29088e1b47980f5a7`.
Approval is scoped to preparation, not training launch; masking and evaluation
caveats above remain. Per-turn verification and receipt:
`data/dfm12/identity-ema-preferences-independent-review-20260927-v3/`.

The user authorized another 1,000 XL updates, step 2878261 to 2879261,
with 95% DFM11 replay and 5% expanded DA/EN identity material. The source is
the [v2-r2 identity expansion](dfm12-identity-extension.md), not superseded v2.
The second mixture is `data/sampled_dfm11_identity_da_en_second1000steps`,
seed 20260927: 262144511 rendered tokens, identity fraction 0.0500004404.
Packing provides 1003 optimizer steps; the requested 1000 consume 260601527
nonpadding tokens with identity fraction 0.0498815381.

`scripts/schedule_identity_continuation.py` is a new adapter, leaving the first
interlude script and canonical XL checkpoint untouched. It uses the same W&B
run `DFM5/dfm12-xl-identity-da-en-1000`, constant base LR 1e-5 with lr_auto,
no warmup/decay, global batch 262144, GAS 2, full BP and unchanged optimizer.
Output: `checkpoints/dfm12/XL-identity-expanded-from-step2878261`.

## Resume Semantics

The production resume resolver reads sidecar metadata before explicit resume
overrides. The source step has batch 2000 and row cursor 629152; overriding
resume_batch alone would skip the new dataset. The adapter hard-links immutable
DCP payloads into its own `resume/` root and changes only the copied sidecar:
step 2878261, epoch 12, batch 0, row cursor 0. It retains the step tag and proves
resolution with `pretrain.resolve_resume_state`. Training uses epochs=12 and
the fresh zero-based dataset `epoch_11`.

This intentionally replaces the builder receipt's suggested `epoch_11`
checkpoint alias with an equivalent zero-cursor step-tag view. The difference
is explicit in `spec.json` and `resume/fresh-dataset-transition.json`.
Neither the source checkpoint metadata nor weights/optimizer state is reset.

## Handoff and Review

State root: `logs/training/dfm12_XL_identity_expanded_2000steps`.
Preflight pins script/data receipts, hashes mixture outputs, checks source scope,
packing and fresh cursor, and resolves Hydra config before requesting any stop.
Supervisor 2704399 was armed for XXL `ephemeral_step_661500` after preflight;
it records PID, process start ticks, argv and PGID, preserves the complete
checkpoint, then signals only the verified training process group. Teacher
cleanup is separately required. GPU release precedes scheduler restart.
Handoff completed at 10:27:47 Europe/Berlin: scheduler PID 2706070, segment
PID 2706085, torchrun PID 2706086. XXL 661500 is preserved under
`checkpoints/preserved/xxl-before-identity-expanded-ephemeral_step_661500`.
Actual training advanced to 2878265; the eight-rank log confirms
`start_epoch=12, skip_batches=0, resume_mode=batch, row_cursor=None`, and W&B
resumed the original identity run. This is launch evidence, not completion.
**Completion update:** the second 1,000 updates finished at step 2879261.
The final sidecar records batch 2000 and row cursor 633110, exactly matching
the fresh mixture packing receipt. W&B synced the same identity run with final
base LR 1e-5. The segment entered `identity_evaluation`; quality assessment and
conditional full evaluation remain pending, not approved by training loss.

**Evaluation outcome, 2026-09-26:** both checkpoints completed all 116
conversations / 206 generated turns. Previous checkpoint: 30 length stops;
continued checkpoint: 2. The report status is `complete_with_length_stops`,
which returns exit 4 under Jason's evaluator contract. Therefore the segment
recorded the evaluation failure, released the terminal barrier, and the
scheduler launched XXL from ephemeral 661500 at 11:20:13 Europe/Berlin.
No full-suite rows were inserted, no positive assessment was inferred, and
the parent-approval countdown was not opened for this non-success report.

Final `responses.json` SHA-256:
`7806cbc84daecaa1ac587069315f01842ea99b2313f06ad9a279d5adc8e3bc2d`.
Qualitative inspection of all 16 regression answers shows corrected DA
training-team leadership, responsive EN namesake explanation, and explicit
16-layer depths in EN architecture. DA architecture no longer disclaims
knowledge of its layer counts, but adds a lengthy unsolicited identity preamble.
These observations are not an exhaustive semantic pass of the heldout set.
Two continued heldout English `heldout_lead_assignment` cases still invent
prior conversation context and emit `<think>` text under non-thinking rendering,
reaching 512-token caps. Their IDs are
`00ce9d93f1cd9ea4f0eaddb22f673c2126fe17ca96b1615f7fd513280e9482fa`
and `217399ad5f9165ed32b717796993e7886f4224e99f3c571662bb315ea7f18167`.
Uncued prompt ambiguity should be considered in parent review; neither the
length-stop reduction nor lexical anchor scores constitute full-suite approval.
The first supervisor attempt failed closed on evaluator source drift, without
stopping training; its traceback is retained in the append-only supervisor log.

Jason's `scripts/evaluate_dfm12_identity_continuation.py` evaluates previous
and continued checkpoints, non-EMA, 16 regressions plus 100 heldout conversations
each (206 assistant turns per checkpoint). It uses generated assistant history,
not gold history, and the raw non-thinking training template, without a Mistral
regex fix. Targets are reporting-only. There is no heuristic auto-approval.
Readable report: `data/dfm12/identity-evaluation-second1000-20260926/responses.md`.
The sibling JSON is the assessment pin. Internal evaluation budget is 3600
seconds; the supervising process timeout is 3900 seconds with owned-group cleanup.

After successful complete evaluation, `phase.json` publishes a report hash and
a 900-second parent review deadline. The parent can atomically write
`parent-assessment.json` in the state root:

```json
{
  "decision": "approve_full_suite",
  "assessor": "parent",
  "rationale": "Explicit qualitative review of the generated comparison",
  "checkpoint_step": 2879261,
  "report_sha256": "SHA256_OF_RESPONSES_JSON"
}
```

Only explicit matching approval inserts the standard + DFM + EuroEval campaign
before XXL resumes. Negative/no approval, timeout, failed/incomplete identity
evaluation, or failed training release the terminal barrier to resume XXL.
No quality result is inferred from lexical scores. An approved campaign reuses
the existing 290-row template, persistent vLLM, utilization/judge settings and
native Gemma template; it remaps IDs/dependencies, checkpoint paths, exports,
logs and W&B identity. It sets `no_ema=true`. Its GPU-terminal barrier/teardown
does not depend on successful merges or averages. Explicit insertion CLI:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/schedule_identity_continuation.py \
  insert-full-eval --spec logs/training/dfm12_XL_identity_expanded_2000steps/spec.json
```

Normally the segment invokes that insertion itself when it sees approval;
do not race the CLI against the segment. Duplicate or late insertion is refused.
Evaluation epoch is approximately `10 + 2000*262144/103214604702`, in nominal
DFM11 token units, never synthetic replay epoch 12. Full-suite duration is not
covered by the 15-minute review timeout; normal scheduler terminal handling
governs an approved campaign.

## Validation

Fifteen CPU tests passed across the scheduler adapter and evaluator at arming.
Checks cover constant LR/span, zero-cursor overrides, report-bound explicit
approval, XXL release after training failure, actual 290-row campaign remapping,
non-EMA settings and 116-case/206-turn evaluator inventory. Evaluator CPU
preflight loaded no model and verified DA/EN target maxima 182/130 tokens.
Live phase and actual training progress must be read from the state-root
receipts and `xl/train_until_step_2879261.log`; armed is not completed training.

## Fourth Interlude Preparation

On 2026-09-26 the user authorized steps 2880261 through 2881261, with
trainer epoch 14 and a fresh zero-based dataset epoch 13. Source checkpoint
root is `checkpoints/dfm12/XL-identity-expanded-from-step2879261`; the new
output is `checkpoints/dfm12/XL-identity-expanded-from-step2880261` and state
root is `logs/training/dfm12_XL_identity_expanded_4000steps`. The same 95/5
mixture policy, optimizer/EMA state, identity W&B run and constant base 1e-5
with lr_auto apply. Boole owns v4 corpus preparation; Jason owns evaluation.
Preparation is not launch authorization until those artifacts are frozen and
the pinned CPU preflight passes. The fourth-campaign launch is verified below.

The reusable scheduler now accepts `evaluation_gpus` as a comma-separated
list of unique physical indices 0..7. Its backwards-compatible default is
`"7"`; the fourth campaign must explicitly select `"0,1,2,3,4,5,6,7"` for
Jason's all-GPU evaluator. Training allocation remains all eight GPUs.

**Superseded for the fourth campaign only:** the idle 900-second review gate
above is replaced by explicit `review_mode: "deferred"`. Evaluation still runs
before XXL resumes, but semantic review does not hold GPUs idle. Successful
evaluation writes `review-deferred.json` with the report hash and checkpoint
step; failures also release the scheduler barrier. No full suite is approved
automatically. A later positive parent assessment requires a separate safe
handoff; late insertion into a released barrier is rejected. Legacy campaigns
retain the bounded review default. The old 2K full suite remains unapproved.

Resume-view reuse verifies its source sidecar hash and copied state. Immediately
before signalling XXL, the handoff repeats artifact preflight and checks both
the original spec hash and stop-request ownership. Arming rejects already
written targets and non-500-step boundaries. The combined scheduler and v4
evaluator suite passes 56 CPU tests, including GPU allocation validation and
deferred-review barrier release without sleep or automatic approval.

The final corpus is `data/dfm12/identity-corrected-da-en-20260926-v4`, manifest
SHA-256 `b750f605d951fc22740d483fe4e913265427b3b711af44fbfc35490c2d3d476b`.
Its mixture `data/sampled_dfm11_identity_da_en_fourth1000steps` uses seed
20260929 and has 262144160 rendered tokens, identity fraction 0.0500004082,
and 1003 available optimizer steps. The requested 1000 steps consume
260661030 nonpadding tokens, identity fraction 0.0498578825, and stop at row
cursor 638617. Boole reported 89 preparation tests passing and hash verification.

The state-root `spec.json` pins the mixture, source sidecar, epoch-13 arrays,
training/evaluation scripts and relevant configuration. Its CPU dry-run passed;
`preflight.json` records production resolver step 2880261, start epoch 14,
skip_batches 0 and row cursor 0. Canonical source metadata remains unchanged.
The evaluator preflight artifact is
`data/dfm12/identity-evaluation-fourth1000-20260926-preflight/responses.json`:
216 conversations and 346 turns per checkpoint, including 16 regressions,
100 v3 conversations explicitly labelled development, and 100 fresh heldouts.
The live evaluation root will omit the `-preflight` suffix. The total evaluator
budget is 3600 seconds, with a 3900-second supervising deadline.

**Launch verified, 2026-09-26:** Jason's final source review cleared all 62
assistant edits, 734 scope clarifications and the deduplication; parent approved
the operational configuration. Review receipt:
`data/dfm12/identity-evaluation-fourth1000-20260926-preflight-final/source-review.md`.
Frozen evaluator SHA-256:
`f54a2ddb03edd6ce961b0481cbc2b8309c33195a06a81f1f526b2519b613aece`.
This source readiness is not approval of future generated answers or full eval.

Detached supervisor PID 2893025 was armed while XXL was at 665475, targeting
the still-unwritten boundary 665500. It preserved the completed checkpoint in
`checkpoints/preserved/xxl-before-identity-expanded-ephemeral_step_665500`,
repeated final preflight and stopped only verified XXL group 2809831.
Scheduler PID 2894099 resumed with all GPUs and persistent vLLM enabled.
The identity segment PID 2894131 launched at 20:05:39 Europe/Berlin; the actual
eight-rank resume log reports step 2880261, epoch 14, skip_batches 0,
resume_mode=batch, row_cursor=None. The original W&B identity run resumed.
Actual training advanced through 2880280, confirming launch beyond warmup.

Current log:
`logs/training/dfm12_XL_identity_expanded_4000steps/xl/train_until_step_2881261.log`.
The scheduler stop request is cleared. Plan state has the identity job running,
its terminal barrier pending, and XXL pending with resume tag
`ephemeral_step_665500`. Evaluation follows training on all eight GPUs; deferred
human review does not delay automatic XXL resumption. Training and evaluation
are still in progress, not completed or semantically accepted.

**Superseded operational status, 2026-09-26 20:30:** identity training finished
at step 2881261. The first eight-GPU comparison failed during startup reporting:
worker snapshots can contain a conversation with zero completed turns, while
the historical summary divides reference-token F1 by the group's turn count.
This raised `ZeroDivisionError` before a complete comparison. The historical
single-GPU helpers must remain frozen; fix the v4 reporting adapter and add
zero-turn/partial-worker regression tests. Preserve the failed output root.
The failure barrier worked: XXL automatically resumed from preserved 665500.
Do not describe this reporting failure as an identity-quality result.

**User-directed pause, 2026-09-26 20:35:** user requested training paused and
the retry comparison on all eight fully released GPUs. The scheduler stop
request remains set; exact XXL process group 2905330 was terminated after
verifying completed checkpoint 665500. Scheduler 2894099 exited. No unrelated
GPU processes were signaled. The interrupted `dfm11-e3-train-700000` row was
reset from failed to pending under PlanLock, with resume tag 665500 unchanged;
the previous plan is preserved as `plan.before-user-pause.tsv` in the fourth
interlude log root. Do not automatically resume training after this standalone
comparison; the previous automatic-resume policy is superseded by this pause.

The v4-local reporting fix preserves empty in-progress conversations in raw
evidence but excludes them from legacy statistics until a turn exists. Its
36-test suite passed; historical evaluator helpers remain unchanged. Parent
launched standalone retry PID 2910284 on GPUs 0-7 after confirming all GPU
training processes exited. Output:
`data/dfm12/identity-evaluation-fourth1000-20260926-retry1`; log:
`logs/training/dfm12_XL_identity_expanded_4000steps/identity-evaluation-retry1.log`.
The process receipt pins evaluator SHA-256
`9e35252aa5f2a6e3bb75120f45a807280c2073d8e56985ba20a504b515ea288d`.
Eight workers use whole-conversation queues, two concurrent checkpoint loads,
and a 24-GiB allocator limit each. This standalone process has no training
resume action. The failed original comparison is retained separately.

**2026-09-26, full-suite approval and EMA correction:** the standalone smoke
completed all 346 turns per checkpoint. Parent review found persistent
wording-sensitive identity errors, including inverted leadership attribution
and a Danish answer denying L/H modules; it is not a clean semantic pass.
Evidence and the decision are in
`data/dfm12/identity-evaluation-fourth1000-20260926-retry1/parent-semantic-verdict.md`.
The user accepted the shortcomings and explicitly requested the full suite.
The full suite must use **EMA step_2881261**, not the non-EMA weights used for
the diagnostic smoke. The initial proposed non-EMA full-suite setting is
superseded; no full-evaluation runner had started at the correction check.
Use distinct EMA export/results paths and keep XXL training and its original
scheduler paused. Smoke findings must not be presented as EMA findings.

**Superseding sequence, 2026-09-26:** the user requires EMA identity holdout
evaluation before the full suite. No full-suite runner or evaluation worker
was launched. The isolated plan is prepared at
`logs/scheduler/dfm12_XL_identity_step2881261_ema_full_20260926/plan.tsv`:
290 rows, 286 pending and 4 skipped (including the unrelated DFM5-L report).
All dependencies are internal and acyclic; there are no training rows. Standard,
DFM and EuroEval shards retain their batches, merges/W&B sync, atomic averages,
0.95 ordinary / 0.85 judged utilization, and Gemma E4B judge. Every row selects
EMA (`no_ema=false`) and W&B `DFM5/dfm12-xl-identity-da-en-1000`, fractional
epoch `10.010159182443488 = 10 + 4000*262144/103214604702`.

Fresh EMA export completed at
`exports/dfm12_XL_identity_step2881261_ema_hf_training_tokenizer` (131 tensors,
none dropped). Exporter was called with `ckpt_use_ema=true`. Only the new export's
forced tokenizer flag was changed to `fix_mistral_regex=false`: raw tokenizer
JSON, pre-tokenizer and ten plain/chat token-ID probes match training; the chat
template is byte-identical. `export-validation.json` records hashes and parity.
No non-EMA export or outputs were reused; no production code changed.

The new isolated plan has its own `stop.request` and
`hold-for-ema-identity.json`; do not clear it until the parent confirms Jason's
EMA holdout evaluation completed and releases full evaluation. No tmux monitor
or runner has been started for this plan. The original training plan and stop
request were verified byte-for-byte unchanged against `preflight.json` pins.
Full-suite authorization is an explicit user override, not a semantic pass.

**Automatic sequencing update:** the user subsequently authorized automatic
full-suite launch after the EMA identity evaluation completes operationally,
without waiting for another parent semantic approval. The isolated plan stays
stopped until that prerequisite is satisfied. The new CPU watcher
`scripts/launch_identity_ema_suite_after_holdouts.py` checks a completion-bound
report hash, explicit EMA selection, frozen evaluator and corpus hashes,
exact pinned preflight cases, all conversation turns (at least 140 per
checkpoint), latest checkpoint step 2881261 and GPU release. Semantic failures
do not block this explicitly authorized suite; operational failures do.
It pins the isolated plan/export and original training pause, refuses duplicate
launches, and uses a bounded deadline. Only the isolated stop request may be
removed. Training never resumes through this watcher. A detached persistent
vLLM runner and current-session tmux monitor are created only after validation.
Eleven CPU tests passed, including rejection of missing worker EMA verification.
The watcher also requires eight complete worker receipts with independently
verified loaded EMA parameters; an EMA label alone does not release the suite.

**Watcher armed:** detached PID 2943404 has verified process identity and phase
`waiting_for_ema_holdouts`. Configuration and process/status receipts are in
the isolated EMA plan directory: `ema-holdout-watcher.json`,
`watcher-process.json`, `watcher-status.json`, and `watcher.log`.
It watches `data/dfm12/identity-evaluation-fourth1000-20260926-ema-heldout1`,
launched separately by the parent as PID 2938732, and pins the 100-case / 140-turn
latest-only preflight under `identity-evaluation-fourth1000-20260926-ema-heldout-preflight1`.
Frozen evaluator SHA-256:
`4769f3e418694a1ebe69551c08cfe49c4be7cfd151c100f8e9178815691217ba`.
The full suite remains held while evaluation runs. After validated completion
and GPU release, the watcher starts only the isolated EMA runner with all eight
GPUs and persistent vLLM, plus tmux window `identity-EMA-full` in `hrm-114`.
Its completion wait is bounded at two hours and GPU release at five minutes;
failure leaves the suite stopped and writes `watcher-failure.json`.
No additional semantic approval is required. The original training pause is
pinned and never cleared. At this arming check, no full-evaluation runner exists.

**2026-09-26 EMA holdout outcome:** all 140 answers completed; parent semantic
review finds unreliable identity recall, substantially worse than non-EMA.
EMA invents organization leaders and a fictional team, confuses model-weight
training with weightlifting, and hallucinates architecture/provenance. It hit
the output limit on 30/140 answers versus 0/140 for non-EMA on the same fresh
holdouts. DA/EN anchor recall was 41.8%/45.3% versus 64.8%/72.8%; these are
mention diagnostics, not semantic accuracies. All eight workers verified every
trainable parameter against stored EMA, so no accidental non-EMA load occurred.
EMA lag at 0.9999 is plausible but not proven as the sole cause. Detailed review:
`data/dfm12/identity-evaluation-fourth1000-20260926-ema-heldout1/semantic-verdict.md`.
The independently user-approved full EMA suite subsequently launched as PID
2947193 with monitor `hrm-114:7`; training remains paused. General benchmark
performance must be assessed separately from this identity failure.

**Superseded by immediate user stop, 2026-09-26 21:18:** the full EMA suite is
now paused, not running. The isolated plan's `stop.request` remains present.
Exact runner 2947193 and its 34 captured descendants received SIGTERM after
PID/start-ticks/command/PGID verification. All exited; no SIGKILL or unrelated
process signal was needed. Stopped API-server PIDs: 2947253, 2947336, 2947354,
2947500, 2947515, 2947590, 2947597, 2947664. Stopped GPU EngineCore PIDs:
2952177, 2951903, 2951905, 2951889, 2951891, 2952386, 2951914, 2952188.
The complete 35-PID ownership/signal ledger is
`logs/scheduler/dfm12_XL_identity_step2881261_ema_full_20260926/user-stop-20260926.json`.
No GPU compute process, evaluation runner or launch watcher remained afterward.

The pre-stop plan is preserved as `plan.before-user-stop-20260926.tsv` in that
directory. Under PlanLock, only interrupted rows
`identity-4000-ema-full-eval-600329` through `600336` were reset to pending;
attempt counters, logs, partial artifacts and all completed results were kept.
Final counts: 39 done, 4 skipped, 247 pending, zero running/failed. The original
XXL plan and its stop request remain byte-for-byte unchanged and paused.

The user had authorized a further 6000 identity updates, step 2881261 to
2887261, with a fresh epoch-15/zero-based-14 mixture, unchanged 95/5 policy,
base 1e-5 lr_auto and preserved optimizer/EMA. **Scheduling and execution are
now explicitly deferred pending clarification.** Only read-only orchestration
inspection occurred before the stop override: no continuation helper, spec,
training row, comparison row or autolaunch process was added. Preserve CPU
preparation owned by other agents, but launch neither training nor evaluation
without the next instruction. No new full benchmark is implicitly authorized
after that future training.

**Superseding START6K authorization, 2026-09-26 21:23:** the user explicitly
authorized immediate identity training without waiting for the stopped full
suite. A new, separate training-only plan was created:
`logs/scheduler/dfm12_XL_identity_next6000steps_20260926/plan.tsv`.
It contains exactly one all-eight-GPU training row, no dependencies on the
full suite, no evaluation rows, no automatic full benchmark and no XXL resume.
Both older plans and their stop requests were hash-verified unchanged.

Dataset: `data/sampled_dfm11_identity_da_en_next6000steps`, seed 20260930,
receipt SHA-256 `a7ca26d092333b56d259a00abaff2fde598a637bc02a6ba315e749bc8262b346`.
The same corrected v4 manifest is retained. Full output/tokenized-source hashes
and epoch-14 aliases were checked. There are 6019 available optimizer steps;
6000 requested steps consume 1563845355 nonpadding tokens, with identity fraction
0.0498557282 and final row cursor 3824362. Rendered identity fraction is
0.0500001163. No data-generation or tokenizer policy was changed.

State: `logs/training/dfm12_XL_identity_next6000steps`. The new isolated resume
view links unchanged DCP payloads from
`checkpoints/dfm12/XL-identity-expanded-from-step2880261/step_2881261`,
with only copied sidecar epoch=15, batch=0 and row cursor=0. Canonical source
metadata was hash-verified unchanged. Output:
`checkpoints/dfm12/XL-identity-expanded-from-step2881261`, target step 2887261.
`spec.json`, `preflight.json`, `resolved-config.json` and
`resume/fresh-dataset-transition.json` preserve exact configuration and pins.
Production CPU resume resolution passed; base LR remains 1e-5 with lr_auto,
no warmup/decay, BP8, GAS2, unchanged optimizer and EMA=0.9999, no reset.
Historical scripts/specs were not generalized or modified for this launch.

Detached scheduler PID 2985947 started the single training row at 21:23:56;
torchrun PID 2985951 uses all eight GPUs. The actual trainer reports epoch 15,
skip_batches=0, batch-mode resume and row_cursor=None. At 21:24:24 W&B resumed
`DFM5/dfm12-xl-identity-da-en-1000`. Launcher receipt:
`logs/scheduler/dfm12_XL_identity_next6000steps_20260926/runner-process.json`.
Training log: `logs/training/dfm12_XL_identity_next6000steps/xl/train_until_step_2887261.log`.
The post-6000 EMA/non-EMA holdout comparison is requested but **not yet queued**;
do not describe it as automatic. The current plan ends after training.
Actual optimizer progress through step 2881275 is verified in the log and
`launch-verified.json` in the new plan directory; this is not just a queued job.

**Completion verified 2026-09-27:** all 6000 additional updates finished on
2026-09-26 at 23:37:27 CEST, step 2887261. The scheduler recorded status 0 and
exited one second later. Final regular sidecar reports 12000 microbatches and
row cursor 3824362, matching the packing receipt. Elapsed launch-to-completion
was about 2h13m31s. W&B reported successful sync to the existing identity run.
Last logged batch metrics (not segment averages): loss 0.69059, accuracy
0.83112, exact accuracy 0.44073. No post-6000 identity holdout results exist at
this check, so improvement in EMA identity recall remains unmeasured. Other
GPU processes were present and were not disturbed.

**2026-09-27 follow-up measurement launched:** user reported all eight GPUs
free; a fresh process query confirmed this. Parent launched
`scripts/run_identity_10000_holdouts.sh`: sequential EMA then non-EMA of
step 2887261, each using all eight GPUs and the same 100 fresh conversations /
140 turns, greedy generation, 512 output tokens, unchanged local training
template and verified EMA loading. Outputs:
`data/dfm12/identity-evaluation-10000-20260927/{ema,nonema}`. Log:
`logs/training/dfm12_XL_identity_next6000steps/holdouts-ema-nonema.log`.
The launcher refuses existing output directories and stops on operational
failure. No W&B logging, training resume or full benchmark is attached.

**Follow-up measurement completed, 2026-09-27:** both modes finished all 140
answers and released all GPU processes. Relative to 4K, EMA DA/EN anchor recall
rose from 41.84/45.32% to 49.66/49.98%, and output-limit hits fell 30 to 19.
Non-EMA changed from 64.80/72.84% to 60.61/73.55%, with zero length stops at
both checkpoints. These are diagnostics, not semantic accuracy. Answer-level
review finds partial EMA recovery but persistent fabricated teams/architecture;
non-EMA retains strong direct roster answers but regresses on some Danish
provenance and cycle arithmetic. Neither gets a clean semantic pass. Detailed
evidence: `data/dfm12/identity-evaluation-10000-20260927/parent-review.md`.
No additional training or full benchmark was launched.
