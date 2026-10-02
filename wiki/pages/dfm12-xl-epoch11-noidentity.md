---
type: Runbook
title: Original XL DFM12 Epoch 11 Without Identity
description: One identity-free DFM12 epoch continuing original XL epoch 10 with rewarm, final cooldown and 50K evaluations.
tags: [dfm12, training, xl, scheduler, learning-rate]
status: draft
last_updated: 2026-10-01
confidence: high
---
# XL DFM12 Epoch 11

## Resume After DFM13 Work (2026-10-01)

The owner requested training resume from the latest ephemeral. The eight owned
DFM13 Gemma vLLM servers were stopped through supervisor PID 2682751, and all
eight GPUs were verified clear before dispatch. The existing plan's 3000000
training row already resumes `ephemeral_step_2976000`; no new plan was created.
The checkpoint records epoch 11, exact batch cursor 197478, global row cursor
62701245, GBS262144/GAS2, and preserved optimizer/EMA state.

Cleared the scheduler stop request and restarted the ordinary persistent runner
through `scripts/schedule_dfm12_xl_epoch11.py bootstrap`. Tmux session `hrm-133`
has the existing monitor in window 5, scheduler in 6, and training log in 7.
The training log is
`logs/training/dfm12_XL_epoch11/step_3000000/train_until_step_3000000.log`.
Base LR stays 3e-4 with automatic module rates, unchanged cooldown and original
DFM5 run. DFM13 investigations may continue on CPU, not by restarting servers
over this training allocation.

## 2900K Evaluation Recovery

On 2026-09-29 the 2900000 checkpoint completed, but the long-lived segment
wrapper failed during finalization: its old LR validator re-read the manifest
after the owner changed the future cosine schedule. Training itself succeeded.
The terminal-failure barrier then released training toward 2950000 while
the 2900000 evaluation remained blocked. This was not an evaluation failure.

On 2026-09-30 the wrapper was fixed to snapshot its validated run policy before
launching training. A regression test changes the manifest during training
and verifies that successful finalization still proceeds. The owner requested
a stop after complete ephemeral 2926500, recovery of the 2900000 evaluation,
then automatic continuation from that ephemeral to 2950000. Base LR remains
3e-4 (automatic H=1.5e-4, L=5e-5). The recovery must restore the terminal and
teardown barriers to pending, not leave their premature completion in place.

The owner subsequently deferred this handoff on 2026-09-30 while the new
multilingual evaluations are prepared. The exact-PID stop watcher was
cancelled before 2926500; training was left running and scheduler dispatch
remained paused. Do not assume the requested recovery has already run.

## Authorized Scope

Continue the original XL, not an identity-adapted checkpoint:
`checkpoints/dfm11/XL-from-dfm10-epoch9/fsdp2_epoch_10`.
Its checkpoint sidecar verifies step **2877261**, completed epoch 10, batch
cursor zero, world size 8, GBS 262144 and GAS2. Restore optimizer and EMA;
do not reset EMA or replace this checkpoint with an EMA-only HF export.

On 2026-09-29 the owner superseded the initial identity-included request:
**all dedicated DFM12 identity packages have repeat 0 for this epoch**.
The initial reusable repeat-10 policy was superseded later on 2026-09-29:
the owner requested registering both XL and XXL-wide identities across all
21 languages with repeat 0 in the default DFM12 source config. Other source
weights are unchanged. This is one epoch, logged as epoch **11**.

Continue project `DFM5`, existing run
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, display name
`DFM8-XL clean full from DFM6-DFM7 epoch5`, with `wandb_resume=must`.
Read-only API verification found this run finished and its internal history
counter at 2877306, 45 ahead of the optimizer checkpoint. Preserve the true
optimizer counter; do not fabricate steps or clone/backfill another run.

## Dataset Preparation

`python -m dfm12.prepare_xl_epoch11` samples additions at seed 10, repeat 0
for identity and the registered repeats for everything else. It combines
these with the already sampled DFM11 index set `epoch_0`, preserving its
inherited source weights, and deterministically shuffles complete rows.
This is a fresh mixed training epoch, not a replay of the previously consumed
DFM11 `epoch_9` selection. The inherited selections are explicitly recorded.

The output is `data/sampled_dfm12_xl_epoch11_noidentity`, with only
`epoch_10` (zero-based) required for resuming completed epoch 10. Existing
DFM11, DFM12 and tokenized arrays are not modified. The new large token file
is written in bounded chunks under `.building`; complete metadata/index
publication and rename precede the readiness receipt.

`--budget-only` computes the identical index merge and executes the actual
Multipack sampler on CPU alongside the token copy. The independent index
hashes must match the final published indices before `--verify-ready` writes
`data/dfm12/xl-epoch11-noidentity/ready.json`. No GPU allocation is needed.

Verified budget in `data/dfm12/xl-epoch11-noidentity/run.json`:

| Quantity | Value |
| --- | ---: |
| Tokens in selected epoch | 117000690762 |
| Indexed assistant targets | 284380704 |
| Packed microbatches, 8 ranks x 16384 tokens | 895637 |
| Optimizer steps, GAS2 | 447818 |
| Unused final accumulation microbatch | 1 |
| Final optimizer step | 3325079 |

This uses the training sampler's actual drop-last behavior, not a token-count
division. Segment resumes use row cursors and preserve the same packing.

## Learning Rate

Retain XL BP8, H2/L3, GBS262144/GAS2, FSDP FP32 parameters/optimizer, BF16
compute, per-block sharding, `fsdp_reshard_after_forward=false`, no-sync
accumulation, compilation and no activation checkpointing. `lr_auto=true`;
explicit H/L/embedding/head overrides remain null.

| Phase | Absolute steps | Base LR |
| --- | --- | --- |
| Linear rewarm | 2877261 to 2900000 | 1e-5 to 3e-4 |
| Constant | 2900000 to 3250000 | 3e-4 |
| Cosine decay | 3250000 to 3325079 | 3e-4 to 1e-5 |

The original 10K rewarm was superseded by the owner's 2026-09-29 request
to rewarm until 2900000 because the data distribution also changes.
Use the existing checkpoint-anchored `lr_rewarm_steps=22739`, explicit
`lr_rewarm_start_step=2877261`, `lr_rewarm_start_ratio=1/30`,
`lr_decay_start_step=3250000`, `lr_decay_end_step=3325079`, and
`lr_min_ratio=1/30`. Clear old row-anchored cooldown and piecewise settings.
At peak, automatic H/L rates are 1.5e-4 and 5e-5; embedding/head use 3e-4.
The original final-50K cooldown was superseded on 2026-09-29 by the owner's
request to start at 3250000, giving 75079 cosine-decay steps. Updated future
segment launch policy without interrupting the first training segment;
the two schedules are identical throughout that already-running segment.
Regular checkpoints remain every 10K steps, ephemerals every 500, with epoch
checkpoint saving enabled.

## Scheduling And GPU Gate

Plan directory: `logs/scheduler/dfm12_XL_epoch11_noidentity`.
Train to 2900000, 2950000, 3000000, 3050000, 3100000, 3150000,
3200000, 3250000 and 3300000; run full evaluations between segments, followed
by the final epoch_11 evaluation at 3325079. Evaluation exports use EMA and
the unmodified training tokenizer/Gemma template (no Mistral regex fix).
Fractional epoch values are finalized from actual checkpoint row cursors.

The owner explicitly requires waiting for occupied GPUs to become free.
Do not stop unrelated audit/generation/vLLM processes. Preparation/bootstrap
may run on CPU, but training requires the ready receipt and at least
178000 MiB free on each of GPUs 0-7. Use the ordinary persistent-vLLM eval
scheduler; the bootstrap is only a readiness gate, not another GPU runner.
Evaluation failures must not prevent subsequent training after all GPU jobs
are terminal and owned evaluation servers have been released.

The prepared campaign contains 2910 rows: ten training segments and ten
full standard/DFM/EuroEval evaluation lifecycles (including merges, averages
and release barriers). The judge is `openai/gemma-4-e4b-judge`.
On 2026-09-29, the CPU readiness bootstrap was launched in tmux
`hrm-119:6` (`dfm12-xl-e11`), with the Rich monitor in `hrm-119:5`
(`dfm12-xl-monitor`). Its log is
`logs/scheduler/dfm12_XL_epoch11_noidentity/bootstrap.log`.
The bootstrap automatically executes the persistent-vLLM scheduler after
verified dataset publication; the scheduler then waits for GPU headroom.
At launch, data assembly was still running and no training had started.
Update 2026-09-29: assembly and publication completed, and `ready.json`
verifies all four index hashes against the independently packed budget.
The bootstrap entered the ordinary scheduler successfully. At 13:04 CEST,
training remained in `HEADROOM_WAIT`, with zero failed jobs; unrelated GPU
work still occupied all eight devices. The first training target is 2900000.
Sixteen focused preparation/scheduling tests passed; the plan's stable
run-policy digest and launcher pins matched its preflight receipt.
See [DFM12 status](dfm12-status.md) for publication and tokenization provenance.

## Multilingual Evaluation Recovery (2026-09-30)

The 2900000 checkpoint completed, but its segment wrapper reread the LR
manifest after training and rejected a cooldown change made during the run.
That incorrectly marked completed training failed and allowed the terminal
barrier to release the next segment without evaluation. The wrapper now
snapshots the validated policy before starting training; a regression test
covers changes made while the subprocess runs.

Superseding the original 2910-row plan, the same plan now has 6852 rows.
`scripts/extend_dfm12_multilingual_evals.py` added the following for the
original epoch_10 baseline and every existing future checkpoint:

- Forty test-only DFM tasks: acceptability and correction for English and
  nineteen additional languages, four paired shards per task, 2000 examples
  per task. Producer train/test overlap checks passed; this is not a proof
  against contamination in every inherited training source.
- 157 distinct EuroEval datasets from the reviewed multilingual registry.
  Shared Norwegian datasets run once; flagged contamination/variant cases
  and values tasks remain diagnostics outside the headline averages.
- Separate complete-coverage multilingual and expanded English averages,
  preserving historical average populations and prefixes.

See [EuroEval registry](dfm12-euroeval-multilingual-registry.md) and
[population rules](multilingual-headline-populations.md).
New jobs use the pinned cached EuroEval 18.1 interpreter, not an in-place
upgrade of the training environment. Normal EuroEval dataset authentication
is required; probing only the user's HF token incorrectly reports the private
benchmark mirrors as unavailable. All 157 dataset preflights passed using
the framework's normal credential path.

The owner's final handoff order is: finish preparations, stop at a complete
ephemeral, evaluate **only new tasks for epoch_10**, evaluate **all old and new
tasks for 2900000**, then resume from that ephemeral toward 2950000. Dispatch
was paused during preparation. The exact-process-group watcher targets
`ephemeral_step_2928000`; it validates DCP payload extents and a subsequent
training progress step before stopping. Do not use a stale earlier watcher
target as the resume checkpoint.

Workspace: [DFM5 Multilingual Headlines](https://wandb.ai/peter-sk-sdu/DFM5?nw=mkrhf1q0gcj).
Existing workspaces were not edited. New metric axes use fractional epochs;
2900000 must use its saved row cursor, not a steps/token approximation.

Handoff completed: `ephemeral_step_2928000` passed shard-extent checks, then
only the training process group 3763838 was terminated. The old scheduler
exited on its existing stop request. The complete 2900000 training row was
marked done; its prematurely completed barrier/teardown were reset pending.
The 2950000 continuation now resumes from `ephemeral_step_2928000` and still
depends on the 2900000 evaluation teardown. The exact 2900000 epoch coordinate
is `10.050805366878901` (14448066 / 284380704 rows after epoch 10).
The same persistent scheduler restarted in `hrm-119:6`, with the existing
Rich monitor in window 5; the first dispatched GPU job is the new epoch-10
EMA export. No unrelated GPU processes were terminated.

Historical epoch-10 English EuroEval artifacts had an old `epoch_2` directory
name and zero step stamps. Use the provenance-checked canonical copies under
`data/eval/dfm11-xl-epoch10-english-euroeval-20260930` for the expanded English
average. Original artifacts/scores remain unchanged; do not globally bypass
checkpoint validation to accept zero-step metrics.

Startup verified: epoch-10 export completed with 131 tensors, zero dropped,
and successful training-tokenizer parity. All eight persistent vLLM servers
loaded with FA4 and 0.95 utilization. First multilingual EuroEval clients
produced successful chat requests and advancing sample counters (including
Dutch 17/342 and French 11/155); no failed plan rows at this check. The final
focused scheduler/population test set passed 61 tests.

## Multilingual Context Recovery And Counts (2026-09-30)

Greek Wikipedia exhausted retries and Faroese FoQA repeatedly failed on
oversized API prompts. vLLM's error reports a *lower bound* such as 4097,
not necessarily the actual total: saved Greek prompts reached 4908 tokens
including the 256-token answer budget. Lowering batch size cannot fix this.

For pending/future **new multilingual EuroEval** rows, opt into
`euroeval_context_policy=native_head_tail_v1`. The native proxy counts the
fully rendered prompt using the export tokenizer and the exact server chat
template. Only oversized input text is shortened in the middle, keeping
both ends and all template boundaries; output limits remain unchanged.
Structured tool prompts are not silently shortened. Every changed request
records its policy, original/retained token counts, budget and original-text
hash in `proxy_payloads.jsonl`. This is an explicit context-limited benchmark
policy, not a claim to have evaluated complete overlength documents.
Old production tasks and already completed multilingual results are unchanged.

The runner was softly stopped, preserving completed jobs. Greek Wikipedia
and FoQA failed attempts/cache were archived under their job directories,
their rows reset and moved first, and the persistent scheduler restarted.
CPU replay checked 1019 Greek requests (150 oversized, including repeats)
and 1042 FoQA requests (10 oversized, including repeats); all fitted within
4096 including output tokens. Eighteen focused integration/budget tests pass.
Use rendered-string encoding rather than `len(apply_chat_template(tokenize=True))`:
new Transformers can return a mapping rather than a token-ID list.

Production Danish epoch-10 counts: DaLA 2048, GEC-DaLA 1024. The new
provisional sample is 1000 pairs/language: 2000 acceptability examples and
2000 correction examples (the latter includes 1000 unchanged clean controls).
Each task is partitioned into four 500-example shards. Nineteen new languages
plus English therefore add 80000 examples/checkpoint, not 80000 per shard.
The owner has not requested reducing these counts; the cap is a scheduling
choice, not a benchmark-mandated sample size.

The owner's existing workspace `3fvncok3gjh` now includes the Multilingual
headline average in Headline Averages and a Multilingual Headline Metrics
section. Existing panels/selections were preserved and remote persistence
verified. Snapshots live under
`logs/wandb_workspace_specs/3fvncok3gjh-multilingual-20260930/`.

Workspace visibility follow-up (2026-09-30): the owner could not see the
average despite raw API persistence. The initial edit placed it fifth in
Headline Averages and appended the multilingual section after Hidden Panels.
`scripts/repair_multilingual_workspace_order.py` moves the existing average
panel first in both sections, gives Headline Averages five rows per page,
and moves Multilingual Headline Metrics before Training Metrics & Params
(and Hidden Panels). Panel IDs, other panels and run selections are retained.
Server-side order was verified; this is not a browser-rendering verification,
nor proof that placement was the sole cause. Do not invent an incomplete
headline value to make an empty average panel display a point.

Further check: the existing XL run has no `avg_population/*` score in its
remote summary yet. The complete-coverage average is still waiting for the
new task results. The user's suggestion that W&B omits the panel because
its metric does not exist is plausible, but browser behavior has not been
verified. API persistence alone must not be reported as visible-panel success.
