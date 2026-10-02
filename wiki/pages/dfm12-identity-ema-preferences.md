---
type: Runbook
title: EMA Identity Preference Corpus and Deferred Sampling
description: Reviewed latest EMA corrections, identical-history preference exports, and a fail-closed second-pilot dependency.
tags: [dfm12, identity, ema, preferences, data, operations]
status: stable
last_updated: 2026-09-27
confidence: high
---
# EMA Identity Preferences

## Independent Corrective Supervisor Review, 2026-09-27

**Superseded for capped smoke:** revised supervisor
`19380dd581daff941e389f2e4d7db2139b777701a80361cfb4015d753241bb58`
adds full step2887264 checkpoint/cursor verification, combined registered-thread
memory accounting, and memory-only fallback. All18 revised CPU tests passed.
No remaining code blocker to capped smoke provided ownership registration is
complete and no unregistered thread GPU work starts concurrently. The release
receipt explicitly leaves foreign servers untouched. Actual smoke success is
not claimed by this CPU review; old reproduction tests are historical.

CPU review of Boole's initial corrective supervisor found two launch blockers:
smoke promotion checked only exit0 plus GPU activity, not three optimizer
updates; the NVML guard counted only the new process group rather than all
thread-owned GPU work. Infrastructure failures/timeouts also incorrectly
triggered the memory-mode fallback. These findings apply to supervisor SHA256
`c5d62f7ff69bffa4ec49cdc26e925ecc9feafff802a27d5db8ab42014bc617e3`;
subsequent fixes require a fresh review, not rollback of concurrent work.

The full-state resume path and a real small CPU DCP test preserve distinct
normal weights, optimizer moments/counters, EMA state and decay0.9999. LR is
overridden after restore to constant1e-5 with auto module scaling. The trainer
forces a full checkpoint upon reaching stop2897261 regardless of periodic
intervals. Fresh epoch16/cursor0 and final-only train-split packing are coherent.
Existing13tests and3independent probes passed; two probes reproduce the bugs,
not an approval. No GPU or training actions were performed. Detailed findings,
pins and CPU reproductions:
`data/dfm12/identity-corrective-independent-review-20260927/`.

## Reviewed Subset Handoff

The [stochastic review handoff](/pages/dfm12-identity-stochastic-review.md)
supersedes the all-unreviewed state below:140/560sampled answers reviewed,
420excluded pending. Combined280chosen rows/236pairs; currentv5 targeted131train/
34validation rows await parent repacking after Tesla's ambiguous-depth verdict
correction. The previousv4 targeted132/34rows were loader-verified and remain
preserved. V5 embeds zero warmup/noLRdecay; EMA horizon, batch choice and training
authorization remain unresolved. No new training launched.

## Independent Stochastic Review, 2026-09-27

Reviewed all 140 new sample0 chosen answers in
`data/dfm12/identity-ema-preferences-20260927-v4-stochastic-reviewed` against
the pinned facts and current-runtime correction authority. No chosen factual
blocker found; 18 retained positives were also read. Independent CPU checks
passed exact own-rollout histories, same-history DPO rejections, file and
tokenizer/template pins, final-only token labels, context limits, family split
isolation, and exclusion of all 420 unreviewed turns. Targeted training has
132 rows and 6494 supervised tokens, including inherited reviewed data.
Receipt, per-row checks and executable probe:
`data/dfm12/identity-stochastic-independent-review-20260927/`.

Case62's unscoped 16-layer response is underspecified, not an unambiguous
contradiction; its 16L/16H correction is sound. Verdict totals must not be
reported as hallucination counts. Ambiguous first weight-training prompts
remain excluded from targeted SFT and identity-deficit evidence. This is agent
review, not human certification or training approval. The immutable v4 recipe's
warmup2 conflicts with the owner's no-warmup direction; Jason/parent own its
superseding recipe separately. No GPU or training actions were performed.

## Independent CPU Packer Review, 2026-09-27

No blockers found for `scripts/pack_identity_preference_sft.py` and
`data/dfm12/identity-ema-preferences-20260927-v3-v1-packed`. All 140 rows
were verified through real `dataset_new.V1Dataset` target-only loading:
inputs equal `input_ids[:-1]`, labels equal source `labels[1:]`, the last
prompt token predicts the first answer, and prior history remains masked.
Packed/source hashes and row-ID/family split isolation passed. Real single-rank
sampling covers 108 train rows in four batches and 32 validation rows in two,
all within 4096 tokens. Supervised target counts are 5066 train and 1515
validation. Nine packer tests passed. Consumers must set `target_only=True`;
the output supplies only `epoch_0`, with repeat=1. No distributed schedule,
GPU work or training launch was authorized by this review. Receipt and
reproducible independent check:
`data/dfm12/identity-preference-packer-independent-review-20260927/`.

## Sampling Completed, 2026-09-27

Supersedes the startup-only status below. Manual-v2 finished all 400 sampled
conversations / 560 answers with all eight workers complete. Completion status
is `complete_with_length_stops`: 513 answers ended at EOS and 47 hit the
512-token generation limit. These are unreviewed candidates, not verified
preference additions. No SFT, DPO training, or full evaluation was launched.
Receipt: `data/dfm12/identity-ema-stochastic-20260927-manual-v2/samples/completion.json`.
The bound responses SHA256 is
`a9f16885642ef9946f43137846688803716c2e77d0a52668082bb9be175a4982`.

## Manual Co-resident Override, 2026-09-27

**Supersedes the pilot dependency for this new run only.** The user explicitly
authorized immediate all-eight-GPU EMA step2887261 temperature sampling alongside
the existing audit, capped below half of each GPU's physical memory. No pilot
receipt was forged or altered. Watcher3481575's exact argv and lack of a GPU
launch receipt were checked, then only that PID received SIGTERM; it is gone.
The old spec is unchanged, and its pinned source files are archived under
`identity-ema-stochastic-20260927-queue-v1/frozen-code` with `watcher-stop.json`.

Active root: `data/dfm12/identity-ema-stochastic-20260927-manual-v2`.
Detached sampler PID/PGID: **3490113**; receipt `launch.json`, log
`generation.log`, incremental outputs `samples/`. Spec SHA256:
`53b856de9236a472d80a46a4e6decc455a55c34e71cc6a34e66ec92d42d7de22`.

The first manual-v1 attempt (PID3488810) failed before checkpoint loading because
`gpu_status` still rejected any other compute PID. That artifact is preserved.
The fix adds explicit `allow_occupied=True` only for co-resident worker probes;
real free memory and all compute PIDs are retained, and the exclusive default
still refuses occupied GPUs. All first-attempt workers exited before retry.
The active run also archives its pinned source files under `frozen-code/`.

Launch verification receipt: `launch-verification.json`. All eight workers were
running with verified EMA weights;12 sampled conversations and27 generated turns
were already persisted. Worker PIDs by GPU0..7:3490230,3490231,3490235,3490236,
3490239,3490245,3490248,3490250. Maximum observed owned GPU memory was31402MiB;
minimum current free memory across GPUs was65220MiB, with no guard failures.
These are startup observations, not completion or semantic-quality approval.

The explicit `--manual-co-resident` preparation mode records the user override,
all real GPU snapshots and fresh code pins. Torch allocation is capped at80GiB
per worker, with4GiB non-Torch allowance and8GiB free headroom required beyond
that budget before loading (92GiB free). The combined84GiB owned-process budget
is below50% of the observed183359MiB physical memory. Actual per-process GPU
memory, including non-Torch allocations, is polled every2seconds, with receipts
under `samples/shards/continued/memory-gpu-*.json`. Exceeding the owned budget or
losing8GiB free cancels only the owned sampling worker/phase. This process monitor
is sampled, not a hardware-enforced instantaneous cap; Torch's80GiB allocator
limit plus the below-half process budget leaves additional margin.

The evaluator now accepts a guarded report-level `required_free_mib` override
only for explicit EMA manual co-residency, with validated allocator/non-Torch/
headroom limits and physical-half budget. Its ordinary104GiB EMA default is
preserved. Real headroom is rechecked inside the load semaphore, and the original
per-generation8GiB guard remains. EMA loading and all-parameter verification are
unchanged. Audit processes remain visible in actual GPU readings and are never
stopped. No W&B, training or benchmark is launched.

83 CPU tests passed, including unchanged default, invalid override rejection,
physical-half validation, actual process-memory accounting and headroom failures.
New evaluator SHA: `96656afd01dd02974e97e55a1c6f535cc0d0842896624a8d18dad261fd54e5ab`.
New sampler SHA: `6dc88744124275cbdbfbfd994a6271b7f45f4fda111352cb6d5794a7302323e3`.
Earlier hashes and watcher descriptions below are historical, not the active run.

## Scope and Review

Only step2887261 EMA responses are inputs. No non-EMA data, system-message
interventions, training, or full evaluation is authorized by this queue.
Historical evaluator and raw response artifacts remain unchanged. See the
[identity evaluator](/pages/dfm12-identity-evaluation-v4.md) for inference provenance.

The complete reviewed revision is
`data/dfm12/identity-ema-preferences-20260927-v3-reviewed`.
Its manifest SHA256 is
`ffe454b2e629f5b1cee21ab54a44b5d2a1e4ba54e411c4b29088e1b47980f5a7`.
All 100 conversations / 140 turns were read, with individual reasons and
fact references in `review-ledger.json` and exact histories, original responses,
and chosen answers in `review.md`. This is assistant semantic review, not a
claim of independent human signoff or measured semantic accuracy.

| Export | Train | Validation | Total |
| --- | ---: | ---: | ---: |
| Chosen SFT | 108 | 32 | 140 |
| DPO pairs | 87 | 27 | 114 |

The 114 pairs are 82 `factual_correction`, 24 `completeness`, four `precision`,
and four `style`. There are also 26 `verified_positive` SFT examples without
fabricated rejected partners. Factual correction includes removing unsupported
claims, not only demonstrably false statements. A rejected answer is not
necessarily a hallucination: case98's approximately70B historical total is a
precision preference, while cases54/55/87/95 are style preferences.
Use top-level `preference_kind` to filter a factual-correction experiment.

Earlier v1 and v2-partial artifacts remain preserved at 42 reviewed / 98
unreviewed. They are superseded for coverage by v3-reviewed, not silently rewritten.

## Data Contract

`scripts/prepare_dfm12_identity_preferences.py` validates source completion,
all eight workers' EMA verification, source SHA, case bindings and tokenization.
The source is `data/dfm12/identity-evaluation-10000-20260927/ema/responses.json`,
SHA `c35216ad479e26c1542a266664922b6f74b6a371b6c975ce993ea53af506b787`.
`facts.json` retains the approved identity ledger; `authority-supplement.json`
records current XL runtime bindings, profile scope and checkpoint-continuation
authority separately from historical v1 claims.

Every preference uses the SAME exact input messages and generated history on
both sides. Corrections were individually authored against the actual question
and history, not automatically copied expected targets. Earlier hallucinated
assistant messages are context only. `chosen-sft-tokenized` masks every prompt
token with -100, including previous assistant turns; only the final chosen
completion is supervised. Raw SFT ingestion must honor `message_loss_mask`;
ordinary all-assistant-loss ingestion would wrongly supervise bad history.

All 25 prompt families are assigned before augmentation: 20 train and five
validation, with language siblings and followups together. Incorporated former
holdouts and all stochastic descendants are explicitly DEVELOPMENT data.
`future-evaluation-policy.json` excludes these families from future sealed
evaluation. No new sealed evaluation set has been created in this task.

## Historical Pilot Queue (Superseded)

Queue: `data/dfm12/identity-ema-stochastic-20260927-queue-v1`.
Spec SHA256: `5171ebfc8ed67be9f41396108722b9060578d7c6f62a4e4d195c96d8fb79b443`.
CPU watcher PID/PGID **3481575**, launch receipt `watcher-launch.json`, log
`watcher.log`, live state `watch-status.json`. The watcher has empty
`CUDA_VISIBLE_DEVICES`; it cannot launch generation before the dependency gate.

The parent-confirmed dependency is
`data/dfm12/multilingual-second-indexed-v3-20260927`.
At arming its completion was **blocked**, `gpu_released:false`,
`successor_authorized:false`. Old blocked roots are preserved and cannot satisfy
this queue. No GPU generation was launched. No further pilot tuning is performed
by this task. An unrelated audit release is insufficient.

Poincare or parent must write a fresh, explicit queue-bound handoff at
`poincare-second-pilot-release.json` inside the queue. The required fields are:

```json
{
  "schema": "identity-ema-after-pilot-release-v1",
  "queue_spec_sha256": "5171ebfc8ed67be9f41396108722b9060578d7c6f62a4e4d195c96d8fb79b443",
  "producer": "poincare",
  "purpose": "second_pilot_completed_and_gpu_released",
  "authorized": true,
  "time": "ACTUAL_NUMERIC_TIMESTAMP",
  "pilot_root": "ABSOLUTE_CONFIRMED_V3_ROOT",
  "completion": {"path": "ABSOLUTE_V3_COMPLETION_JSON", "sha256": "ACTUAL_HASH"},
  "release": {"path": "ABSOLUTE_RELEASE_RECEIPT_WITHIN_V3_ROOT", "sha256": "ACTUAL_HASH"}
}
```

This is a schema example, NOT an authorization receipt. Completion must actually
be complete and affirm GPU release; release evidence must affirm
`only_owned_servers:true`. Both require numeric timestamps after queue creation,
with release after completion. The watcher then independently requires all eight
GPUs to have no compute processes and at least104GiB free each. Missing,
blocked, stale or mismatched evidence fails closed before GPU probing.
Changing to another pilot root requires a newly reviewed queue, not mutation of
this pinned spec. No direct agent-messaging API was available; coordination is
through the parent-confirmed root and this durable handoff contract.

After valid release only: eight independent EMA workers, two concurrent loads,
96GiB allocator budget, existing8GiB generation guard, temperature0.7/top_p0.9,
four seeded whole-conversation samples per case, at most512 new tokens per turn
and4096 context tokens. CPU preflight binds400 conversations /560 turns; existing
greedy source is the baseline. Generation is bounded to3600 seconds, queue wait
to86400 seconds. Deadline/incomplete output is not success. New samples remain
UNREVIEWED and are not automatically added to SFT/DPO. Differing rollout histories
must never be paired, even when their final user question is the same.

The queue never kills unrelated processes and never resumes training or starts
a benchmark. `launch.json` is created only if actual GPU generation starts;
`watcher-launch.json` records CPU queue startup only.

## Verification

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_identity_preferences.py \
  tests/test_dfm12_identity_continuation_v4.py -q
```

79 CPU tests passed. Full140-turn build passed exact source-template and prompt
token matching plus final-only loss masking. Coverage, family splits, sampling,
preference kinds, stale/wrong dependencies and blocked-pilot no-launch behavior
are tested. The stochastic GPU path has not run while the pilot is blocked.
Frozen evaluator SHA remains
`4769f3e418694a1ebe69551c08cfe49c4be7cfd151c100f8e9178815691217ba`.
