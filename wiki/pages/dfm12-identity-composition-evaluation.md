---
type: Runbook
title: Sealed Identity Composition EMA Evaluation
description: CPU-prepared adapter for manual semantic assessment after the corrective 10000-step continuation.
tags: [dfm12, identity, evaluation, ema]
status: draft
last_updated: 2026-09-28
confidence: high
---
# Sealed Identity Composition Evaluation

## Executed Review, 2026-09-28

Executed after completed step2897261 from
`checkpoints/dfm12/XL-identity-after-gas-probe-from-step2888200`, overriding
the historical default root below. Final evidence and per-turn semantic review:
`data/dfm12/identity-composition-eval-2897261-ema-20260928-retry1`.
All80 turns completed, two with output-limit stops, and every worker verified
EMA before inference. The first attempt cancelled because available memory
fell below the conservative92GiB loading requirement; it did not OOM.
The successful retry used the new optional `--allocator-limit-gib 64`:
64GiB Torch cap,4GiB reserve,76GiB free before load, same8GiB generation
headroom and physical half-device guard. Default remains80GiB; the CLI only
allows budgets16..80GiB.21 adapter tests passed after this resource-only change;
frozen inference helpers, prompts, decoding and EMA handling were not changed.

Manual parent review found63 correct,3 partial,12 factual/unsupported failures
and2 incomplete answers. This is not a clean identity pass; no full benchmark
or additional training was authorized. Exact prompts, outputs and criterion
judgments are in `responses.md` and `parent-review.md`. Direct bilingual roster
recall works, but compositional identity knowledge is not fully reliable.
The old deferred command below is historical preparation, not pending work.

## Scope

`scripts/evaluate_dfm12_identity_compositions.py` is a separate adapter around
the frozen v4 evaluator. It reads the new sealed
`data/dfm12/identity-composition-holdout-20260927-v1` without editing it or
training code. There are 40 conversations, 20 DA and 20 EN, with 80 total turns.
Manifest SHA256:
`bd1181b9d37b4da3afc8dfbc7ee20599a1010dd85b60c867d712b712a369787c`.
Cases, rubric, source specification, factual authority, exclusion inventory
and runtime text assets are pinned and checked. This is a prompt-composition
holdout over known facts, not unseen knowledge or independently authored human
gold. The source manifest's unevaluated status remains its immutable seal state.

The [corrective continuation](/pages/dfm12-identity-continuation.md) must finish
before inference. Only `step_2897261` is supported, with EMA enabled and no
non-EMA option. V4 verifies every loaded trainable parameter against separately
loaded CPU EMA tensors after inference-dtype casting; absent or mismatched EMA
fails closed. The complete checkpoint and runtime tokenizer/template are bound
before workers start and rechecked by workers. No system facts, criteria or
reference answers enter model prompts. Followups use the actual generated first
answer, not a corrected or gold history.

## CPU Preparation

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
TOKENIZERS_PARALLELISM=false /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/evaluate_dfm12_identity_compositions.py --preflight-only \
  --output data/dfm12/identity-composition-eval-2897261-cpu-preflight-v3
```

Outputs are fresh-only; use a new output path to repeat preflight. Preflight
does not probe GPUs, load model/checkpoint tensors or generate answers. It
validates pinned inputs and conservative two-turn prompt/output budgets.
The earlier `cpu-preflight-v1` and `v2` are preserved but superseded: their
conservative budget accidentally counted tokenizer mapping keys rather than
input IDs. V3 explicitly unwraps the mapping, with a regression test. No
inference occurred under those intermediate preflights; actual runtime also
independently checks the full rendered prompt using the frozen v4 path.
No evaluation or model-generated answers were produced during adapter preparation.

## Deferred Command

Only after completed training and parent-confirmed release of all other owned
GPU work, create a separately reviewed release receipt with this contract:

```json
{
  "campaign": "identity-composition-evaluation",
  "step": 2897261,
  "all_owned_gpu_work_released": true,
  "owned_pids": [12345]
}
```

The PID list must name actual released owned GPU processes, not the example
number. Nonempty integer IDs are required; any still-existing PID blocks launch
(including conservative PID-reuse blocking). The adapter never signals those
PIDs or unrelated processes. The parent must also prevent new owned GPU work
from starting concurrently after release. The adapter separately requires the
training supervisor's `complete.json` binding step2897261, output checkpoint
root and `evaluation_export: EMA_ONLY`.

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/evaluate_dfm12_identity_compositions.py \
  --output data/dfm12/identity-composition-eval-2897261-ema-v1 \
  --gpu-release-receipt /absolute/path/to/parent-reviewed-evaluation-release.json
```

Default checkpoint:
`checkpoints/dfm12/XL-identity-corrective10000-from-step2887261`.
Default training receipt:
`logs/training/dfm12_XL_identity_corrective10000steps/complete.json`.
This is a future command, not a queued or executed evaluation.

## Limits and Review

Eight single-GPU workers, batch one, at most two simultaneous checkpoint loads.
Greedy generation, thinking disabled, at most512 new tokens and4096 total
context; actual full history is checked without truncation before each call.
Default deadline3600 seconds, configurable only up to7200; cleanup reaps only
workers this evaluator created. W&B is disabled. No servers or training resume.

Per GPU:80GiB Torch allocator cap plus4GiB non-Torch reserve, at least92GiB free
before load and8GiB before generation. The combined84GiB budget must fit below
50% of physical memory or launch fails. A one-second nvidia-smi monitor checks
the owned worker's actual footprint, including non-Torch allocations, and
cancels owned evaluation workers on excess or measurement failure. The guard is
sampled, not a guarantee against transient allocation spikes. Foreign audit
work is neither counted as this thread's owned work nor killed; actual free
headroom still must suffice. Future runtime fit remains unmeasured.

`responses.json`, `responses.md`, `summary.json`, per-GPU shards, memory
receipts and final `completion.json` retain evidence. Lexical heuristics are
removed from consolidated responses and are never an acceptance criterion.
Raw v4 worker shards may retain historical diagnostic fields; they are not
semantic scores. Exit0 is operational completion only, including flagged
length stops. Every answer remains pending manual semantic assessment against
the sealed rubric; `semantic_pass` stays null, training/export authorization
false. The rubric distinguishes factual correctness, completeness, unsupported
claims and invalid/incomplete outputs. No automatic training/export follows.

Verification:70 CPU tests passed across the new adapter and frozen v4 evaluator;
seven expected CPU distributed-checkpoint warnings. Tests cover source/rubric
drift, generated-history isolation, release/step guards, memory limits, no-GPU
preflight, manual-only scoring and existing all-tensor EMA verification.
