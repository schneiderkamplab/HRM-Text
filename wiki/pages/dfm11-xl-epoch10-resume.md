---
type: Runbook
title: XL DFM11 Epoch Ten Resume
description: Transfer and resume the completed 2482084-step XL lineage for one DFM11 epoch.
tags: [dfm11, xl, training, resume, portability]
status: stable
last_updated: 2026-09-20
confidence: high
---
# XL DFM11 Epoch Ten Resume

## Tokenizer Regex Mismatch Found (2026-09-21)

Read-only CPU inspection of the current 2750000 HF export found
`fix_mistral_regex=true` in `tokenizer_config.json`. Production scheduled
evaluations serve this export through vLLM. In the installed hrm environment,
AutoTokenizer loads it as TokenizersBackend and prepends a regex Split to the
original space Split pre-tokenizer. `conversion/convert_to_hf.py` persists
this flag for all jinja-chat-template exports.

Training reads pretokenized NPY arrays. DFM11 additions were tokenized by
`scripts/tokenize_chat_template.py`, whose worker uses Tokenizer.from_file
without a regex patch. Its transferred source artifact at
`data/dfm11_tokenizer/tokenizer.json` has only the space Split pre-tokenizer.
Thus no fix_mistral_regex option is applied during training tokenization.

A direct CPU comparison with `add_special_tokens=False` demonstrated unequal
IDs for `Hello, world!\nNext line.`: training-tokenizer IDs begin
`[9259, 236764, 1902, ...]`, while exported AutoTokenizer begins
`[9259, 236764, 236743, 12392, ...]`. Three other short examples matched.
This establishes an actual tokenizer-behavior mismatch, not its prevalence
or its effect on benchmark scores. No training, export, or evaluation settings
were changed during this investigation.

The historical DFM6 note that enabling the flag necessarily restored the
intended training tokenizer is not established for this corpus/runtime;
the present parity result supersedes that assumption for this path. A
representative input parity audit and isolated evaluation A/B should precede
changing production flags or retokenizing training data.

## Final Epoch Cooldown Scheduled (2026-09-20)

Supersedes the constant post-2650000 LR only from step 2725000 onward.
User requested cosine decay to 1/7.5 of the current rates by the actual
epoch end: base/embeddings/head 7.5e-5 -> 1e-5, H 3.75e-5 -> 5e-6,
L 1.25e-5 -> approximately 1.666667e-6. Keep lr_auto and BP8.

`scripts/handoff_xl_dfm11_epoch_cooldown.py` updates only XL training rows
targeting 2750000 and later, under PlanLock; backup is
`plan.before-xl-epoch-cooldown.tsv`. It sets `lr=7.5e-5`,
`lr_min_ratio=0.13333333333333333`, clears both step-decay endpoints,
and uses the existing row-anchored cosine implementation. No training-code
changes. Hydra/Pydantic composition and all three cooldown tests passed.

Detached watcher PID 3354681 waits for the complete 2725000 ephemeral,
preserves its metadata as `lr_cooldown_anchor_step_2725000.json` under
`checkpoints/dfm11/XL-from-dfm10-epoch9`, and verifies the row-based LR
endpoints before stopping the captured XL group. The small anchor is outside
ephemeral cleanup patterns and remains needed for every subsequent resume.
Then it resets the active row to that checkpoint and restarts the same
scheduler/W&B run. No interruption until the boundary and no optimizer/EMA
reset. Manual stop requests abort automatic handoff. Log:
`xl-epoch-cooldown.log` in the existing plan directory; completion receipt:
`xl-epoch-cooldown-complete.json` (scheduler launch, not training-progress proof).

Cosine progress uses the fraction of remaining DFM11 epoch_9 rows consumed
since the anchor, not an estimated final global step. If this handoff is
cancelled, preserve/create the verified anchor before starting any later
row that refers to it; do not silently substitute a different row cursor.

## Second Cooldown Scheduled (2026-09-18)

Later on 2026-09-18 the user requested a temporary stop at the fully written
2610500 ephemeral. The automatic 2625000 handoff watcher PID 931623 was
terminated by exact PID and the scheduler stop was requested. The checkpoint
stop operation waits for DCP payload completeness, stops only XL group
861720, waits for scheduler 1188924 to exit, then resets the active row to
resume `ephemeral_step_2610500` with log directory
`logs/training/dfm11_XL_epoch10/from_2610500_to_2650000`. It does not clear
`stop.request` or restart anything. The second-cooldown overrides already
stored in that row will take effect at this manual resume, so the old
2625000 handoff watcher must not be relaunched.

Completed: 2610500 passed the DCP completeness check; the captured training
group and scheduler exited, the resume row is pending from that ephemeral,
and the scheduler stop request remains present. No automatic restart occurred.

User-authorized restart on 2026-09-18 at 17:04 CEST: cleared the stop and
relaunched the same persistent-vLLM scheduler (PID 1183374), logging to
`runner-resume2610500.log`. Training verified restoration at step 2610500,
epoch 10, skip_batches 256832. The existing monitor and 15-minute watchdog
remain running. The active row includes the second-cooldown overrides;
the obsolete 2625000 handoff watcher remains disabled.

The initial cooldown below remains historical and completed at 2550000.
The user approved a second cosine window, 2625000--2650000, with base
LR 1.5e-4 decreasing to 7.5e-5, then held constant. With BP8 and lr_auto,
H decreases 7.5e-5 to 3.75e-5 and L 2.5e-5 to 1.25e-5.

`scripts/handoff_xl_dfm11_cosine_2625k.py` updates the existing XL rows for
2650000 and later under PlanLock with explicit schedule overrides. It leaves
the initial shared launcher intact, preserving earlier segment history.
Backup: `plan.before-xl-second-cooldown.tsv` in the existing plan directory.

Detached watcher PID 931623 waits for a fully written
`ephemeral_step_2625000` (DCP metadata and payload extent checks), then
soft-stops the scheduler and terminates only the captured XL training group.
It resets that row to the verified checkpoint and restarts the same scheduler
with persistent vLLM. Optimizer, EMA, global step and W&B run are preserved.
Current training is not interrupted before this boundary. The resumed log
directory is `logs/training/dfm11_XL_epoch10/from_2625000_to_2650000`.

Handoff log: `xl-second-cooldown.log` in the plan directory. The
`xl-second-cooldown-complete.json` receipt means the scheduler was relaunched,
not proof that training subsequently progressed; check the existing 15-minute
watchdog and training log. Manual stop requests or identity/exit-check failures
abort rather than force a restart. No XXL training rows are changed.

## Data and Checkpoint

Source: `ucloud@ssh.cloud.sdu.dk:6977`, `/work/dfm/HRM-Text`.
Destination: `/work/mimir/HRM-Text`. DFM11 was already transferred and
validated; see [DFM11 portability](dfm11-portability.md). Reuse
`data/sampled_dfm11` (103,214,604,702 tokens per epoch, ten index sets).
The selected `epoch_9` has 235,520,711 rows. Source and destination tokenizer
and Gemma-native template SHA256 hashes match.

`scripts/transfer_xl_dfm11_resume.py` copies the complete eight-shard
`checkpoints/dfm10/XL-from-dfm9-epoch8/fsdp2_step_2482084` checkpoint,
including DCP metadata, sidecar, source config, and source architecture file.
Every checkpoint file is SHA256-verified against the source. Completion is
recorded in `logs/transfer_xl_dfm11/complete.json`; do not infer completion
from directory existence. Local W&B run archives are copied under
`logs/transfer_xl_dfm11/wandb`, not synced or replayed.

Transfer completed on 2026-09-15: all checkpoint hashes matched, and 1,456
local W&B history files plus their associated run files were archived.

The original endpoint is a step checkpoint with the exhausted DFM10 row
cursor. A local `fsdp2_epoch_9` symlink and separate
`checkpoint_state_epoch_9.json` provide an epoch-boundary resume with the
same weights, optimizer state, EMA, and step 2,482,084. The source step
sidecar is preserved unchanged. The epoch alias starts trainer epoch 10
at row zero of DFM11 index `epoch_9`. No serialized carry is required.

## Prepared Command

Activate the normal training environment, then run:

```bash
bash scripts/resume_xl_dfm11_epoch10.sh
```

The transfer request initially prepared this without launching it. The later
scheduling request inserted it into the existing plan as described below;
it is not a second independent training process. The script preserves XL
32 layers, hidden 1536, 12 heads,
H2/L3 recurrence, BP8, GBS 262144, GAS2, FP32 FSDP parameters and optimizer,
BF16 compute, per-block wrapping, no-sync accumulation, and no forward
resharding. Activation checkpointing stays off. Optimizer/EMA are restored.
Regular checkpoints are every 10K, ephemerals every 500, and epoch saving
remains enabled. Output: `checkpoints/dfm11/XL-from-dfm10-epoch9`.

The existing windowed cosine scheduler uses:

| Setting | Value |
| --- | --- |
| `lr` | `3e-4` (verified source base LR) |
| `lr_auto` | `true`; all explicit module LR overrides null |
| `lr_decay_start_step` | `2525000` |
| `lr_decay_end_step` | `2550000` |
| `lr_min_ratio` | `0.5` |

Superseded on 2026-09-16: the original 2482084--2532084 decay window.
The user deferred decay because enabling auto module rates already reduces
H/L learning rates. That revision used 2500000--2550000 and was itself
superseded later on 2026-09-16 by the user's final choice: hold initial auto
rates through 2525000, then cosine-decay through 2550000. All scheduled
segments use the shared launcher. The active segment ending at 2500000
is unaffected; the revised window takes effect on its next resume.

Base/embedding/head LR decays from 3e-4 to 1.5e-4 over that 25K-step
window, then stays at 1.5e-4. H decays from 1.5e-4 to 7.5e-5 and L from
5e-5 to 2.5e-5 at BP8. There is no rewarm or row-anchored cooldown.
The previous XL run had uniform module rates; applying `lr_auto` is the
explicitly requested policy change, not a reproduction of its old H/L rates.

`training_total_steps=2875816` is an approximate progress-bar endpoint:
2482084 + floor(103214604702 / 262144). Packing changes the exact endpoint;
`epochs=10` and exhaustion of index `epoch_9` determine completion, not this
estimate. The explicit cosine window is independent of this estimate.
Keep BP warmup ratio 0.2, already fully elapsed at the resumed step; zero
would divide by zero in the existing BP schedule.

## W&B Continuity

Project `DFM5`, run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, display name
`DFM8-XL clean full from DFM6-DFM7 epoch5`. Use `wandb_resume=must` to avoid
silently creating another run. The existing remote run was verified present
and finished. No cloning, backfilling, or metric writes were performed.

Its internal history counter was 2,482,131, 47 steps beyond the checkpoint
because of evaluation logging. Resuming the correct optimizer step may lose
the first few W&B training log points until the counter is surpassed. Do not
fake the optimizer step to suppress this warning. The local archive remains
read-only evidence; it must not be blindly synced over the remote run.

Validation: Hydra/Pydantic config composition, BP8 module-rate calculation,
cosine endpoints/hold behavior, NPY headers/shapes, tokenizer hashes. Full GPU
restore is deliberately deferred to the actual training launch.

## Scheduled Handoff and Monitoring

On 2026-09-15, `scripts/schedule_dfm11_xl_epoch10.py insert --apply --plan-dir
logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`
inserted 2,909 rows under `PlanLock`. The previous TSV is preserved as
`plan.before-xl-dfm11-epoch10.tsv`. No running job was modified or stopped.

Order: finish current XXL DFM10 epoch two and its evaluation teardown;
train/evaluate XL DFM11 epoch ten; then resume the existing XXL DFM11
epoch-three campaign. `dfm11-e3-train-650000` now depends on
`dfm11-xl-e10-epoch_10-campaign-teardown-dfm10-epoch2` (the historical suffix
comes from the cloned evaluation template; it evaluates XL epoch ten).

XL pauses at global 2,500,000 then every 50,000 steps. Reserved boundaries
extend to 2,900,000, not an asserted epoch endpoint. The segment wrapper
updates each evaluation's fractional epoch using the DFM11 row cursor,
skips boundaries beyond the actual epoch end, and releases the final
`epoch_10` evaluation at epoch 10.0. Each release preserves the standard,
DFM and EuroEval shard plan, per-task merges/syncs/averages, batch sizes,
0.95 ordinary / 0.85 judged utilization, and the established
`unsloth/gemma-4-E4B-it` judge. Terminal evaluation barriers prevent failed
metrics from indefinitely blocking the subsequent training segment.

The detached singleton watchdog runs every 900 seconds and writes
`xl-handoff-watch.log` in the plan directory. Initial PID: 1272952.
It reports current training counters/log age, XL startup, failed rows,
and manual stop state. It can reset at most three clearly transient
network launch failures, only before training progress and with a verified
resume checkpoint. It never kills jobs, changes LR, clears a manual stop,
or retries arbitrary CUDA/OOM/code errors. Such errors remain visible in
the log for inspection; this is not a general autonomous repair agent.

Five focused campaign tests passed (dependency order, untouched running
rows, fractional epoch calculation, and early epoch completion).

## 1K-Window Statistical Check (2026-09-16)

`docs/xl-dfm11-epoch10-1k-statistics.{md,json}` records 32 complete windows
anchored at 2482084, ending at 2514084. The partial tail is excluded. Use
`scripts/analyze_training_log_uncertainty.py` with explicit contiguous
1000-step ranges, `--block-steps 100 --trend-window-steps 1000 --draws 100000`,
and both local 20260916 W&B histories for this XL run. No remote writes or
GPU work are involved.

None of the 93 adjacent-window metric changes or 96 within-window HAC
slopes survives joint Holm correction at 0.05. This does not establish
no learning: first-to-last means improve from 0.99429 to 0.91722 loss,
77.1546% to 78.6263% token accuracy, and 30.1656% to 31.8140% exact accuracy.
Those endpoint differences are descriptive, not tested by the adjacent-window
comparisons. The 1K tests have limited power against gradual improvement.
Reported significance is exploratory and does not adjust for all prior
repeated monitoring; see the generated report's assumptions and caveats.

## Isolated 2750K Training-Tokenizer Evaluation (2026-09-21)

Training was stopped after verifying the complete DCP payload and sidecar for
`ephemeral_step_2785500`. The existing plan now runs a full extra 2750K EMA
evaluation before resuming the same production W&B run from that ephemeral.
The row-anchored LR cooldown, optimizer state, and dataset cursor are unchanged.

`scripts/schedule_xl_2750k_tokenizer_comparison.py` prepares an isolated export
`exports/dfm11_XL_epoch10_step_2750000_ema_hf_training_tokenizer`.
Weights are immutable hardlinks; tokenizer/config files are independent copies.
Only `fix_mistral_regex=false` differs from the original export. The underlying
tokenizer JSON matches the training tokenizer exactly. Installed Transformers
was checked for token-ID parity on ten plain/chat-formatted probes and for an
identical pre-tokenizer to the raw training loader. All three suites use this
export; the original export and main-run metrics are not modified.
All eight live vLLM `/tokenize` endpoints also passed the known discriminating
probe against raw training IDs; evidence is in
`tokenizer-comparison-2750k/live_server_tokenizer_validation.json` in the plan.

The new W&B run in `peter-sk-sdu/DFM5` is
`dfm11-xl-2750k-training-tokenizer-20260921`, named
`DFM11 XL 2750K EMA training tokenizer (no regex fix)`.
The 290 inserted rows retain the existing 242 enabled GPU eval jobs, merge,
sync, and atomic averaging settings. The unrelated DFM5-L report is skipped.
Fractional evaluation epoch remains `9.67792158626763`.

Training depends on the new terminal GPU-job barrier and server teardown, not
successful merges/averages, so exhausted eval failures do not strand training.
Resume log: `logs/training/dfm11_XL_epoch10/from_2785500_to_2800000/`.
A detached CPU-only comparison watcher writes `comparison.{json,md}` under
the plan's `tokenizer-comparison-2750k/` directory when results settle, marking
missing results explicitly. Its comparison does not write to W&B.

Monitor-only readability update: Rich running/ready labels put task, shard,
and checkpoint/EMA before the long model prefix. Job IDs display their suffix;
blocked dependencies are shortened and Task has reserved column space. This
is presentation only; full IDs in the plan, scheduling, and evals are unchanged.

### Paired Tokenizer Replay (2026-09-21)

`scripts/replay_xl_tokenizer_probe.py` replayed 30 distinct validation examples
per task (seed 2750000, first saved prompt per example) from AngryTweets,
Life in the UK, and English HellaSwag. Both variants used the same live EMA
server with explicit token IDs. Every rendered prompt was checked against
the server's chat tokenization, with additional chat/completions spot-checks.
There were no production setting changes or W&B writes.

At the original 10-token cap, fix-on versus fix-off correct counts under
the inspected EuroEval label extraction rules were 19/30 versus 18/30,
21/30 versus 14/30, and 24/30 versus 21/30 respectively. AngryTweets macro F1
was 0.6403 versus 0.5862; both variants always gave valid labels, but fix-off
chose neutral 20 times versus 14. On UK, fix-off produced literal `<think>`
reasoning on 15/30 cases, all truncated at 10 tokens; fix-on always gave a
bare letter. On HellaSwag, two fix-off replies were `assistant: b/c`, which
the prefix scorer interprets as `a`. Neither concealed letter was correct
in these two samples, so this does not explain their accuracy gap by itself.
Small samples are diagnostic, not substitutes for benchmark scores.

All prompts, raw responses, finish reasons, and conditional 64-token replays
are saved in `logs/eval/xl_2750k_tokenizer_replay/generations.jsonl`.
`report.md` and `summary.json` in that directory contain per-sample comparisons
and counts. The standard EuroEval cache removes responses after non-debug runs;
zero `failed_instances` alone does not prove well-formed answers because its
classifier also accepts label prefixes and approximate string matches.

### DFM Winogrande Diagnosis (2026-09-21)

Read-only inspection of both complete 2750K Inspect archives establishes that
the low DFM scores are not the standard five-shot Winogrande scores. The DFM
config explicitly sets `fewshot=false`, requests `ANSWER: A/B`, and the upstream
task sets `max_tokens=64`. Per 1267 unique samples, fix-on has 565 correct,
238 wrong completed answers, and 464 `<think>` continuations truncated without
an answer. Fix-off has 711 correct, 262 wrong completed answers, and 294 such
truncations. Completed-answer conditional accuracy is 70.36% versus 73.07%;
this is selection-biased and not a replacement score. Of the net 146 additional
correct answers, 131 come from changed completion/truncation status and 15
from samples with complete answers in both variants.

An independent bug: both nominal DFM shards contain all 1267 identical sample
IDs, with identical per-ID scores within each variant. The upstream installed
`inspect_evals/winogrande` function does not accept shard arguments. The merged
2534 count double-counts the dataset, understating uncertainty; the point
accuracy is unchanged in these runs. No evaluation/scorer/plan changes were
made during this diagnosis. Fix sharding and reject overlapping sample IDs
in merges before future reruns; separately version any changed prompting or
generation budget to preserve benchmark comparability.

W&B visibility repair: English EuroEval HellaSwag in the isolated tokenizer
run had summary values but no queryable history metric. Explicitly defining
each saved task metric with `step_metric=euroeval/epoch` and re-logging its
`merged_metrics.json` restored the remote point: accuracy 68.0078125 at epoch
9.67792158626763. Verified by `scan_history` afterward. No workspace edits or
eval reruns were needed; the `.last` summary key was not itself proof of the
cause. Danish HellaSwag's 74.375 versus 74.6875 scores really are close.

EuroEval suite-average diagnosis (2026-09-21): `run_average` appends the
checkpoint tag to `euroeval_log_root`, but cloned XL rows write actual EuroEval
results under the inherited `epoch_2` child. Consequently the averaging reader
looks in a nonexistent `step_2750000/step_2750000` directory and emits EuroEval
count zero, no new suite value. Main-run summary retains a stale suite value.
Reading the correct checkpoint-specific parent gives 18 metrics and 2750K
suite averages 0.6904859324755198 (fix on) and 0.670111826539951 (fix off).
These are local recomputations only, not synced by this diagnosis. Historical
XL epoch-10 averages and future average input roots need repair; headline
averages that include EuroEval are affected as well.

Resolution (2026-09-21, supersedes the pending-repair statement above):
`backfill_external_eval_to_wandb.py` now recovers a nonexistent duplicated
checkpoint suffix using only its checkpoint-specific parent, and rejects
EuroEval artifacts carrying a different train step. Regression tests cover
the fallback, valid roots, mismatched steps, and avoiding campaign-wide fallback.
The running scheduler loads this helper for future averaging subprocesses;
no scheduler, training, or evaluation restart was required.

Recomputed and synced all completed post-epoch-9 points (2500K, 2550K, 2600K,
2650K, 2700K, 2750K), plus the isolated 2750K training-tokenizer comparison.
Each has 18 EuroEval metrics. Both `suite_avg_v3` and `headline_avg_v3` were
logged atomically with explicit per-metric epoch axes and the original
fractional epochs. Main-run EuroEval averages are respectively 0.585735,
0.611873, 0.625129, 0.671606, 0.657055, 0.690486; comparison is 0.670112.
These corrective history rows do not delete older incomplete average rows.
