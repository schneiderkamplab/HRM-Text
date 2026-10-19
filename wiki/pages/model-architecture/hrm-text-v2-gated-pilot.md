---
type: Runbook
title: HRM-Text-v2 Gated XL Pilot
description: Independent invocation gates, low-BP delta sharing, strict checkpoint migration and a prepared 3.8M XL continuation.
status: draft
confidence: medium
last_updated: 2026-10-19
tags: [architecture, recurrence, training, gates, experiment]
---
# HRM-Text-v2 Gated XL Pilot

## Completed Matched Control (2026-10-19)

Both runs completed step 3,820,000. This supersedes the initial warmup
observation below that the matched control had not run. Read local W&B
records with `scripts.analyze_training_log_uncertainty.records`, deduplicating
by `train/step` (latest wins). Each run has 4,000 observations at five-step
spacing from 3,800,005 through 3,820,000. Pilot records are in
`wandb/run-20261018*-hrm-v2-XL-from-3800000/*.wandb`; control records are in
`wandb/run-20261018_212824-dfm8-xl-from-dfm6-dfm7-epoch5-clean-full/*.wandb`.

Final 10K-step matched means:

| Metric | Gated pilot | Ungated control | Pilot minus control |
| --- | ---: | ---: | ---: |
| Loss | 0.7257718 | 0.7257886 | -0.0000168 |
| Token accuracy | 82.83057% | 82.82927% | +0.00130 pp |
| Exact accuracy | 48.63295% | 48.64384% | -0.01089 pp |

Paired circular block bootstrap of per-step differences, 100-step blocks
(20 observations), 10,000 draws, seed 0: 95% intervals are
loss [-0.00003535, +0.00000213], accuracy [-0.000177, +0.002778] pp,
and exact accuracy [-0.02350, +0.001269] pp. All include zero. This is a
single-seed training-log comparison, not evidence of downstream equivalence
or a held-out improvement. No meaningful training benefit established after
20K steps; no new benchmark evaluations were run for this comparison.

## Implemented Scope

Opt-in `arch/net@arch=hrm_v2`; the existing baseline remains the default.
See the [architecture plan](hrm-text-v2-plan.md) for the research context.
This first version adds no branches, DeltaNet, Muon or tokenizer changes.

Each invocation has an independent `Linear(2d, d)` with bias:

```
injection = other * (1 + alpha * tanh(W @ concat(local, other) + b))
next_local = existing_stack(local + injection)
```

Gates are token-local, full-width, and zero-initialized without consuming RNG.
There are six L gates and two H gates for H=2, L=3. XL uses d=1536:
4,720,128 parameters per gate; 37,761,024 added parameters in total. Zero
gates preserve baseline outputs for any alpha. Alpha=0 also disables learning
of gate parameters, so start increasing it immediately after resume.

## Low-BP Updates and EMA

Existing no-grad invocation boundaries are retained. Each inactive gate uses
the nearest active gate of the same H/L stack as donor. Since active calls
form a suffix, this is the first active gate. Inside AdamATan2:

1. Snapshot donor weights before the optimizer step.
2. Update active parameters normally, including their weight decay and EMA.
3. Add each donor's actual delta to its inactive targets, without an additional
   weight-decay update for those targets.
4. Copy donor moments and step counter to inactive targets. Update each target's
   own EMA from its new weights, not from the donor's EMA.

This preserves any prior differences between gates and prepares optimizer
state for later activation. It is not equivalent to exact gradients of earlier
invocations. BP8 trains all eight gates directly and needs no delta sharing.
An optimizer-skipped step also skips sharing and EMA changes.

Gate LRs equal the base LR, since each gate executes once. Existing H/L
backbone parameters keep automatic recurrence divisors. `train/gate_alpha`
and `train/lr_gates` are logged. Alpha is a checkpointed buffer, changed outside
compiled forward/backward; native inference uses its saved value. The schedule
uses absolute steps, so interruption does not restart alpha warmup.

## Prepared Experiment

Source, verified by metadata/shard extents and backbone tensor names/shapes:

```
/work/dfm/HRM-Text/incoming/mimir-xl-20261015/checkpoints/dfm15/XL-from-dfm14-epoch1
tag: step_3800000
```

Preserve source backbone weights, optimizer moments, EMA, seed, global step,
epoch 1 and row cursor 25,161,810. Do not override resume epoch/batch counters.
Use the same transferred full DFM15 mixture:

```
/work/dfm/HRM-Text/incoming/mimir-xl-20261015/data/sampled_dfm15
```

Recommended first experiment (engineering choice, not a validated optimum):

| Setting | Value |
| --- | --- |
| Steps | 3,800,000 -> 3,820,000 (20K new steps) |
| Alpha | Linear 0 -> 1 over first 2,000 new steps, then hold |
| Base LR and gate LR | 1e-5, constant |
| H backbone LR | 5e-6 |
| L backbone LR | 1e-5 / 6 |
| BP / H cycles / L cycles | 8 / 2 / 3 |
| Global batch / GAS / GPUs | 262144 / 2 / 8 |
| Precision | FSDP FP32 parameters/optimizer, BF16 compute |
| Performance settings | Transformer-block FSDP, no reshard, no_sync accumulation, compile, FA4 |
| Checkpoints | Every 5K; ephemeral every 500 steps; final forced at 3.82M |
| W&B | DFM5, separate `hrm-v2-XL-from-3800000` run |
| Output | `checkpoints/hrm_v2/hrm-v2-XL-from-3800000` |

Preview the exact command and run CPU-only preflight (neither starts training):

```bash
cd /work/dfm/HRM-Text
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/prepare_hrm_v2_xl.py --preflight
```

Use `--mode control` to prepare an unchanged-v1 matched continuation into
`checkpoints/hrm_v2/hrm-control-XL-from-3800000` and a separate W&B run.
`--end-step 3850000` prepares a 50K initial experiment instead. To extend an
already-started experiment, resume its v2 checkpoint rather than rerunning the
initial migration command. The preview script refuses existing output directories;
its first-launch W&B setting is `never`, avoiding accidental run reuse.

Migration is explicit (`arch.gate_initialize_from_v1=true`) and currently only
supports sharded DCP v1 input. It loads every original model/optimizer key
strictly, initializing only added gates, their state and alpha. Subsequent v2
checkpoints use strict ordinary resume, even if the initialization flag remains
in saved config. Changing H/L cycle counts during v1 migration is rejected.

## Measurement and Release Gates

- 0 steps: baseline logit/loss parity; verify migrated moments/EMA and data cursor.
- 2K steps: warmup ends; check finite losses, gate learning, memory and step time.
- 5K/10K: first training trends and fixed native-inference probes, not a claim
  of statistical significance or guaranteed downstream improvement.
- 20K: initial go/no-go against the matched baseline, equal-token and GPU-hour
  comparisons. Extend to 50K if the result is promising or genuinely inconclusive.
- Compare non-EMA and EMA separately. EMA=0.9999 gives newly initialized gates
  approximately 6.9K steps of half-life; early EMA can conceal adaptation.
- Preparation alone did not authorize a run. **Superseded 2026-10-18:** the
  user authorized running both 20K experiments, stopping and later resuming
  XXL-wide. The current scheduler is draining; cooperative suspension was
  requested at 1,147,600 with a hold. Verify the suspension's regular disk
  checkpoint before stopping the owned supervisor. GPU RAM offload is not a
  substitute for that durable disk checkpoint.

CPU coverage includes exact initial backbone logits/gradients at BP2/5/8,
causal gate locality, donor delta/moment/EMA propagation, activation transitions,
checkpoint/optimizer round trips, compiled gate alpha changes and model backward,
cached prefill/decode, and two-rank CPU FSDP migration and update sharing using
the actual v2 model, including BF16 compute and GAS2/no_sync. Existing module-LR,
gradient-skip/clipping, activation-checkpointing and HF export regression tests
are also retained. The focused regression command is:

```bash
PYTHONPATH=.:eval_scheduler OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_hrm_v2.py tests/test_module_learning_rates.py \
  tests/test_gradient_skip.py tests/test_gradient_clipping.py \
  tests/test_hf_export_rope.py tests/test_hf_export_tokenizer_override.py \
  tests/test_activation_checkpointing.py tests/test_fsdp_topology.py -q
```

**Pending before production launch:** CUDA/FA4 and compiled mixed-precision
FSDP smoke, followed by full-size memory/throughput validation when GPUs are
available. The implementation-only stage did not touch live training; the
subsequently authorized operational handoff is described above. The regression
suite passed 87 tests; the scheduler-isolation test passed separately.

`scripts/smoke_hrm_v2_xl.py` performs five full-size compiled CUDA steps with
W&B disabled and isolated outputs. `scripts/schedule_hrm_v2_pilot.py` installs
pilot/control rows in the existing SQLite plan only after all running rows
drain and the XXL disk fallback is verified. Terminal dependencies ensure a
failed experiment does not block the control or the XXL continuation. Explicit
user stops and GPU admission still take precedence. The original 1.15M XXL
evaluation and subsequent ordinary XL continuation remain in the plan.

### Authorized Launch, 2026-10-18

The pending CUDA qualification above is now **superseded**: a full XL v2
five-step migration/compiled-FA4/FSDP/BF16/GAS2 smoke passed without W&B.
Peak allocated memory was 161,129 MiB (about 157 GiB), reserved 165,390 MiB.
The final checkpoint was complete; all eight gate matrices were finite and
nonzero (maximum absolute weights about 4.88e-5). Saved alpha was 0.0025,
as expected after five warmup steps. Log and checkpoint evidence:
`logs/training/hrm_v2/cuda_smoke/`.

XXL-wide cooperatively suspended at 1,147,600, saved a verified regular
`step_1147600`, offloaded all ranks, then its owning supervisor was stopped.
No unrelated processes were killed. The existing SQLite scheduler now has:

1. `hrm-v2-XL-from-3800000`, 3.8M -> 3.82M, W&B project DFM5.
2. `hrm-control-XL-from-3800000`, same data/cursor/settings, ungated baseline.
3. A terminal barrier, then the original XXL boundary row, resumed from
   `checkpoints/dfm14/XXL-wide-from-dfm13-step870000:step_1147600`.

Experiment failure does not block subsequent training. Existing 1.15M evals
and the ordinary XL 3.8M continuation remain downstream, unchanged. Explicit
stop requests still stop scheduling. The scheduler was launched detached with
`--backend sqlite --persistent-vllm --max-clients 64 --server-concurrency 1024`.
Runner log: `logs/scheduler/dfm10_XL_epoch9_20260831/runner-hrm-v2-pilot.log`.
Pilot/control training logs are under `logs/training/hrm_v2/<run-name>/`.
Tmux `hrm-1:5` tails the pilot; the existing monitor remains in `hrm-1:4`.

### Control Is Main XL Continuation

**Superseded 2026-10-18:** the user requested that the ungated control log to
the existing DFM5 run `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`, using
`wandb_resume=must`. Its checkpoint directory remains isolated at
`checkpoints/hrm_v2/hrm-control-XL-from-3800000`; those are ordinary baseline
checkpoints and count toward future XL training. Only the gated pilot keeps
its separate W&B identity.

The post-XXL handoff selects the highest complete control checkpoint up to
3.82M, including an ephemeral if the control stopped early, and continues
to 3.85M. It falls back to the transferred 3.8M checkpoint only if no newer
complete control checkpoint exists. The scheduler no longer forces a stale
3.8M resume override onto that handoff. Cursor, optimizer and EMA are preserved.

An environment interruption removed all live workers/scheduler and the local
SQLite authority after the pilot reached approximately 3,800,325, before its
first ephemeral. Restored the database via SQLite backup from
`state.backup.sqlite` (integrity check passed), released only its stale pilot
claim, and resumed the pilot from the complete five-step CUDA smoke checkpoint
at 3,800,005. Approximately 320 unsaved steps are replayed; alpha retains the
absolute-step schedule. W&B retains the same pilot run, so this short interval
can have repeated `train/step` points. No histories were deleted or rewritten.
Recovery runner log: `runner-hrm-v2-recovery.log` in the plan directory.
The new tmux session is `hrm-0`: monitor window 4 and pilot log window 5.

### Initial Warmup Observations

2026-10-18: compared 1K-step means for baseline 3.79M-3.8M against pilot
3.8M-3.804M, plus the partial window through 3,804,205. Used unsampled
baseline W&B history and local pilot records, keyed by `train/step`; retained
the latest record for 46 duplicate replayed steps. Each full window has 200
logged observations. Evidence and table: `logs/analysis/hrm_v2_warmup/`.

| Phase (complete windows only) | Loss | Accuracy | Exact accuracy |
| --- | ---: | ---: | ---: |
| Before, 10K steps | 0.72680 | 82.831% | 48.572% |
| Alpha warmup, 2K steps | 0.72283 | 82.866% | 48.609% |
| Full alpha, next 2K steps | 0.72710 | 82.810% | 48.677% |

No obvious sustained degradation on reaching alpha=1; loss/accuracy are near
baseline and exact accuracy slightly higher. This is descriptive, not causal
or statistically significant evidence: sequential data differs and the matched
ungated control has not run yet.

### Actual Gate Modulation at 3,804,500

Later October 18 default change: v2 now defaults to the v1 architecture with
no gates. This pilot remains gated; restart it with `arch.gates_enabled=true`.
The command generator and probe opt in explicitly. The live process and its
persisted scheduler row were not changed. See [default/migration safety](hrm-text-v2-residual-branches.md).

Read-only native BF16/FA4 probe, non-EMA checkpoint, alpha=1. Used 32 seeded
random complete DFM15 epoch-0 examples (7,774 tokens, lengths 26-1,204), with
the training PrefixLM masks and teacher-forced responses. No LM-head logits
or gradients were allocated. GPU 1 process was capped at 6 GiB; peak PyTorch
allocation 3,565 MiB, nvidia-smi about 4.5 GiB. Training was not interrupted;
exclude this brief shared-GPU interval from throughput comparisons.

Script: `scripts/inspect_hrm_gate_modulation.py`. Pinned checkpoint, row IDs,
per-example observations and summary: `logs/analysis/hrm_v2_modulation_3804500/`.
The sampled multiplier statistics retain all channels at up to 64 token
positions per example; the relative injection change uses all observed tokens
and is `sqrt(sum((gated-original)^2)/sum(original^2))`.

| Invocation (execution order) | Mean multiplier | Mean absolute modulation | Relative injection change |
| --- | ---: | ---: | ---: |
| L1 | 0.923 | 44.33% | 51.22% |
| L2 | 0.900 | 13.58% | 19.77% |
| L3 | 0.836 | 17.03% | 22.40% |
| H1 | 1.055 | 6.69% | 4.59% |
| L4 | 1.055 | 7.80% | 1.71% |
| L5 | 1.031 | 5.46% | 1.28% |
| L6 | 1.047 | 5.67% | 1.17% |
| H2 | 0.987 | 2.19% | 1.19% |

L1 multiplier 5th/95th percentiles are 0.152/1.770; only 0.84% of its sampled
elements are near tanh saturation (absolute modulation >0.95), versus zero
for the others. Per-channel modulation standard deviation across sampled
tokens is 1.38 percentage points for L1, 3.80/4.12 for L2/L3, and 0.99-2.23
for the remaining gates. This indicates substantial channel reweighting with
smaller input-dependent variation, not evidence yet of beneficial semantic
routing. Strongest effects are in the first L sweep. Short-example, small-sample
evidence only; no measured task improvement or matched-control overhead yet.

### Matched Probe at 3,805,000

2026-10-18: repeated the same probe on non-EMA `step_3805000`, alpha=1,
verified identical 32 row IDs and seed. Artifacts:
`logs/analysis/hrm_v2_modulation_3805000/`. Probe exited successfully without
interrupting training. Variation below is the mean per-channel standard
deviation of the multiplier across sampled tokens, in percentage points;
it pools within-example and between-example variation, not a semantic-routing
or causal input-sensitivity measurement.

| Gate | Relative injection change, 3,804,500 -> 3,805,000 | Variation, 3,804,500 -> 3,805,000 |
| --- | ---: | ---: |
| L1 | 51.22% -> 52.01% | 1.38 -> 1.42 pp |
| L2 | 19.77% -> 20.76% | 3.80 -> 4.03 pp |
| L3 | 22.40% -> 24.46% | 4.12 -> 4.31 pp |
| H1 | 4.59% -> 6.39% | 2.23 -> 2.32 pp |
| L4 | 1.71% -> 1.71% | 1.56 -> 1.64 pp |
| L5 | 1.28% -> 1.19% | 1.10 -> 1.15 pp |
| L6 | 1.17% -> 1.36% | 1.14 -> 1.18 pp |
| H2 | 1.19% -> 1.25% | 0.99 -> 1.03 pp |

Input-dependent variation increases modestly in every gate (about 3-6%).
Most injection changes increase, especially L3 and H1; L4 is nearly unchanged
and L5 decreases. Strong L1 channel reweighting still dominates its much
smaller token-dependent variation. Two nearby checkpoints on a small sample
do not establish a sustained trend or useful downstream improvements.

Native inference loads the new architecture and saved gate strength. HF/vLLM
export is deliberately rejected until gate-aware serving is implemented and
qualified; never send these checkpoints through the ordinary v1 exporter.
Use native evaluation for the pilot, not the current persistent-vLLM campaign.

## Final Gate Inspection and Downstream Comparison (2026-10-19)

### Reauthorized vLLM comparison (2026-10-19)

The user has now reauthorized both 3.82M EMA evaluations, explicitly using
vLLM **without eager mode**. This supersedes the cancellation below, but does
not activate the archived native child plan. Both checkpoints were exported
CPU-only using `scripts/export_mimir2_dcp.py`, selecting stored optimizer EMA
for parameters and original checkpoint buffers, with strict Mimir2 loading:

- `exports/mimir2_v2_step3820000_ema_hf`: pilot, gates enabled and saved alpha.
- `exports/mimir2_control_step3820000_ema_hf`: ungated control, same architecture backend.

`scripts/schedule_mimir2_3820k.py --install` installed 566 rows in the existing
SQLite authority for `logs/scheduler/dfm10_XL_epoch9_20260831`. This consists of
346 inference shards (173 per checkpoint), 176 CPU result exports, 42 merges
and two terminal barriers. Scope remains eight standard and thirteen core DFM
tasks per checkpoint, not EuroEval or the extended multilingual suite.
Preparation receipt: `logs/scheduler/mimir2_control_3820000_vllm/preparation.json`.

Servers use the isolated `mimir2` Python/CUDA environment, FA4/FLASH_ATTN,
no `--enforce-eager`, disabled prefix caching/chunked prefill, and the explicit
Gemma4 native chat template. Non-judged utilization is 0.90; judged tasks keep
0.65 plus their existing Gemma4 E4B judge configuration. Persistent shared
servers and the existing 64-client/1024-server limits are retained.

Both publish at step 3,820,000 / epoch 11.913198350886034 in DFM5. Pilot uses
`hrm-v2-XL-from-3800000`; control uses
`dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`. No partial-population headline
averages are manufactured. After the existing XXL evaluation boundary, these
run before the pending XL continuation to 3.85M. A terminal inference barrier
allows training to continue even on exhausted evaluation retries; unfinished
publication/merges do not block training. Existing 1.15M and 3.85M evals stay.

Qualification: tiny BF16 combined-feature HF/vLLM parity passed with actual
torch.compile, piecewise prefill and full decode CUDA-graph capture. This is
not yet full-size performance qualification; first full-size startup remains
subject to scheduler retry and memory admission. The native archived plan
remains inactive and running production claims were not interrupted.

**Scheduling decision superseded later in this turn:** the user explicitly
cancelled scheduling the two 3.82M evaluations. No comparison rows were ever
installed in the production SQLite plan. The activation watcher was stopped
and its unchanged temporary scheduler drain request cleared. The prepared
child TSV is archived as `plan.prepared-not-scheduled.tsv`, not runnable
`plan.tsv`. The existing full 1.15M XXL and 3.85M XL evaluations, publication,
averages and subsequent training remain unchanged. Do not activate the native
comparison without a new user request. The inspection/smoke evidence below
remains valid; the scheduling description records preparation only.

Repeated the same 32-row non-EMA probe at `step_3820000`; row IDs match the
3,805,000 probe exactly. Alpha=1 and peak allocation was 3,565 MiB, within
the 6 GiB process cap. Evidence: `logs/analysis/hrm_v2_modulation_3820000/`.

| Gate | Relative injection change, 3.805M -> 3.82M | Token variation, 3.805M -> 3.82M |
| --- | ---: | ---: |
| L1 | 52.01% -> 61.55% | 1.42 -> 2.24 pp |
| L2 | 20.76% -> 32.64% | 4.03 -> 6.57 pp |
| L3 | 24.46% -> 39.19% | 4.31 -> 7.32 pp |
| H1 | 6.39% -> 13.21% | 2.32 -> 4.36 pp |
| L4 | 1.71% -> 2.39% | 1.64 -> 2.85 pp |
| L5 | 1.19% -> 1.78% | 1.15 -> 2.27 pp |
| L6 | 1.36% -> 2.02% | 1.18 -> 2.24 pp |
| H2 | 1.25% -> 1.91% | 1.03 -> 1.69 pp |

The gates have adapted substantially; lack of training improvement is not
explained by remaining at identity. First-sweep channel reweighting dominates;
the pooled token variation is not proof of semantic specialization. L1 has
7.80% of sampled modulation elements above 0.95 absolute tanh output, up from
0.84% at 3.8045M; other gates have none. Raising gate LR solely to make gates
move faster is not supported by this evidence. Short-example sampling limits
generalization, and teacher-forced injection changes are not downstream gains.

Prepared `scripts/schedule_hrm_v2_downstream.py`: 388 child rows, consisting
of 173 inference shards and 21 merges per checkpoint. Both use EMA, native
inference, identical prompts/scorers and the cursor-derived epoch
11.913198350886034. Standard: eight full benchmarks. DFM: DaLA, GEC-DaLA,
PIQA-da, MultiWikiQA, Talemaader, WMT en-da, GovReport, NordjyllandNews,
HumanEval, MBPP, Danish citizen tests, Andersen modernization and IFEval-DA.
EuroEval/tool protocols and the extended multilingual inventory are excluded
from this native comparison, not silently treated as equivalent to production.
The existing complete 1.15M XXL and 3.85M XL campaigns remain unchanged.

Snapshots hard-link immutable DCP payloads and copy configs into
`logs/scheduler/hrm_v2_control_3820000_native/checkpoints/{v2,control}`.
Only these copied configs remap transferred tokenizer/template paths and set
`gates_enabled=true` for the pilot predating that explicit option. Originals
are untouched. Native EMA generation smoke passed with eight nonzero pilot
gates, alpha=1, no control gates, identical prompt token IDs, and answers
`A` / the Danish name for Copenhagen. Receipt: child
directory `smoke.json`. No W&B writes during the smoke.

The new exclusive `eval_native_plan` action drains shared servers and uses
the existing per-GPU executor for native shards, retries and merge/sync. The
outer continuation depends on a terminal barrier, so failed comparison jobs
cannot strand training. The child plan can be monitored separately. Installation
requires the current scheduler to drain; intended order is 1.15M evaluation,
the matched native comparison, XL control continuation to 3.85M, then its full
evaluation and the existing continuation to 3.9M. Pilot metrics use its separate
DFM5 run; control metrics use the existing main XL DFM5 run. No incomplete
headline population averages are fabricated for this narrower comparison.

`scripts/activate_hrm_v2_eval_after_drain.py` waits on the actual runner
lifetime lock, verifies no claims remain running, installs the prepared rows,
and execs the SQLite runner with the original environment and 64 clients.
It consumes only the unchanged drain request it observed; a newer user stop
is never cleared. Activation/runner log lives in the child plan directory.

## Code Map

- `models/baselines/hrm_v2.py`: forward gates, alpha schedule and donor mapping.
- `models/gate_updates.py`: copied deltas, donor optimizer history and target EMA.
- `models/v2_checkpoint.py`: strict v1 DCP migration.
- `config/arch/net/hrm_v2.yaml`: opt-in architecture configuration.
- `scripts/prepare_hrm_v2_xl.py`: isolated pilot/control command and preflight.
- `tests/test_hrm_v2.py`: CPU and CPU-distributed regression checks.
