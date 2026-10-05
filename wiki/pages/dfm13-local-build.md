---
type: Runbook
title: DFM13 Local Transfer and Build
description: Transfer the remote DFM12 base and admitted DFM13 additions for XXL-wide continuation.
tags: [dfm13, data, transfer, sampling]
status: stable
last_updated: 2026-10-05
confidence: high
---
# DFM13 Local Transfer and Build

## Completion Verified (2026-10-05)

The pending-build/startup statements below are superseded by the completed
2026-10-02 handoff in `logs/dfm13_build/continuation.log`. The three-epoch
build passed validation, 3,491 jobs were appended to the existing plan, and
training advanced beyond restored step 754208. Scheduler PID 3992530 launched
the continuation; no new W&B run was created.

Each epoch contains 252,427,901 rows, including 248,438 added occurrences.
Token totals from `data/sampled_dfm13/build-receipt.json` are:

| Index set | Tokens |
| --- | ---: |
| epoch_0 | 107,001,314,620 |
| epoch_1 | 107,000,399,369 |
| epoch_2 (active training epoch 3) | 107,000,619,452 |

This local corpus uses the frozen October 2 registry at
`data/dfm13_build/sources.json` (SHA256
`1d9c708e05083ed1e3e7f8446984aa9a017d4e08f7ad9633a4b9eba969c53c8e`).
Later remote registry additions pulled into Git do not modify these sampled
files or the active training corpus. Do not treat this snapshot as identical
to the subsequently expanded remote DFM13 release.

## Automatic Training Handoff

User authorized monitoring through sampling and automatic continuation on
2026-10-02. `scripts/continue_dfm13_xxl_wide.py watch` is detached as PID
3974901; log `logs/dfm13_build/continuation.log`. It waits for the build's
completion receipt, checks all three epochs' array lengths, token-pointer
bounds, sequence lengths and token totals, then appends to the existing
`logs/scheduler/dfm10_XL_epoch9_20260831` plan under PlanLock and starts its
persistent-vLLM runner. It waits for training to advance beyond the resume
step before declaring successful startup. Failed build processes are retried
at most three times; live transfers/coordinators are not duplicated.

Correction: the checkpoint sidecar records **754208**, not the last tqdm
display of 754205. Resume `epoch_2` at exact saved step 754208, trainer epoch 3,
DFM13 `epoch_2` indices from row zero. Preserve optimizer/EMA and W&B
`DFM5/dfm10-xxl-wide`. Destination:
`checkpoints/dfm13/XXL-wide-from-dfm11-epoch2`.

All prior model/performance/LR overrides are inherited: XXL_wide, fixed BP8,
GBS 262144, GAS4, full-world FSDP2 FP32 parameters, BF16 compute,
reshard-after-forward false, no_sync accumulation, no activation checkpointing,
compile enabled, base LR 3e-4 with automatic recurrence dividers, existing
completed 505K rewarm anchor, no optimizer upcast or EMA reset. Only dataset,
epochs=3, destination and progress-total estimate change. Progress total uses
resume step plus 1.05 times sampled tokens/GBS, not three DFM13 epochs.

Training/evaluations alternate at 800K, 850K and subsequent full 50K boundaries.
The copied successful 650K campaign preserves judge, batch, vLLM, scoring,
merge and average settings. Evaluation epochs are updated from actual saved
row cursors as `2 + cursor/DFM13_epoch_2_rows`. Completion of epoch_3 skips
unreachable future boundaries and releases the final epoch evaluation.
Three CPU tests cover merge offsets, fractional epochs and final-epoch skips;
Hydra config preview succeeded without running training or logging W&B.

To cancel the automatic pre-launch handoff, create
`data/dfm13_build/cancel-continuation`. This does not cancel transfer/build.
After launch use the normal scheduler/training stop procedure. Build and
training are not yet reported complete.

Transfer priority update (2026-10-02): user requested DFM12 transfer immediately.
Coordinator PID 3966937 was SIGSTOP-paused (not its tokenizer children) to
prevent competing rsync writers. A detached transfer supervisor now copies
the complete remote `data/sampled_dfm12/`, including all ten index sets, into
`data/dfm13_build/remote/sampled_dfm12/`. Log:
`logs/dfm13_build/transfer_dfm12.log`. It SIGCONTs the captured coordinator
only on successful rsync; on failure the coordinator remains paused.
This supersedes the three-index-only transfer scope below; the DFM13 merge
still builds three epochs. Subsequent coordinator rsyncs reuse these files.

User requested transfer, tokenization and sampling from
`ucloud@ssh.cloud.sdu.dk:2850`, root `/work/mimir/HRM-Text`.
Remote DFM13 was not sampled. The authoritative registry is frozen locally at
`data/dfm13_build/sources.json`, including its pending-audit list for provenance.
Only the 13 `additions` are admitted: eight audited Arena/HelpSteer sources,
worked MATH at repeat 5, four structured jjzha sources at repeat 1.
IMDb and CroCo pending-audit candidates are not staged or trained.

`scripts/build_dfm13_remote.py` runs the CPU-only pipeline with an exclusive
build lock. Rsync uses port 2850, partial transfer support, and a 512 MiB/s
bandwidth ceiling. Original absolute provenance paths remain unchanged in the
frozen registry; transferred artifacts live under `data/dfm13_build/remote`.
Each admitted source is verified against its registered SHA256. The remote
Gemma tokenizer and chat template were byte-hash verified against local DFM11.

Tokenization uses the existing native chat tokenizer with 16 workers, thinking
disabled, 4096-token examples, and existing target-message-index handling.
Sampling uses one concatenation worker, registered repeats, and long-context
drop rather than further truncation. No inherited DFM12 data is retokenized.

Canonical `data/sampled_dfm12` tokens, metadata and epoch_0--epoch_2 index sets
are transferred from the remote machine. This preserves its exact inherited
occurrences (106,799,766,039 average tokens/epoch) instead of approximating its
mix from local source trees. The base token file is about 909 GB decimal.
Only three inherited index sets are needed for the intended continuation.

The merge copies tokens sequentially in bounded chunks and shuffles row
indices with seeds 0, 1, 2. Added token pointers are offset; inherited token
pointers and row multiplicities are preserved. Index lengths and token bounds
are checked; final metadata is published last. Permutation memory is roughly
2 GB plus memory-mapped pages. A small CPU fixture verified offsets, token
totals and all three epoch outputs before launch.

Outputs:
- `data/tokenized_dfm13_additions`
- `data/sampled_dfm13_additions`
- `data/sampled_dfm13` (three index sets; epoch_2 is for training epoch 3)
- `data/dfm13_build/complete.json` (written only after successful completion)

Launch/resume from repository root:
```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u scripts/build_dfm13_remote.py
```

Initial detached process PID 3966937; log `logs/dfm13_build/build.log`.
All source transfers and tokenizer/template parity checks passed; tokenization
started. Completion and final counts remain pending. This pipeline does not
launch training. The intended subsequent checkpoint is XXL-wide DFM11
`epoch_2`, step 754205, retaining optimizer/EMA and the existing W&B run.
