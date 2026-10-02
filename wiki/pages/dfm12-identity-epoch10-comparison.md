---
type: Report
title: Final Identity EMA Versus Epoch 10
description: Aggregate comparison, inspected protocol failures, and generation campaign pause.
tags: [dfm12, identity, evaluation]
status: draft
confidence: high
last_updated: 2026-09-28
---
# Final Identity EMA Versus Epoch 10

Compare EMA epoch_10 at step 2877261 with final identity EMA step 2897261.
Baseline metrics: `logs/releases/DFM-Mimir-v1.5/evaluation_results.json`.
Identity metrics: `logs/scheduler/dfm12_XL_identity_step2897261_ema_full_20260928/remote-recovery-verification.json`.
See [archive recovery](dfm12-identity-full-eval-recovery.md) for sync verification.

## Aggregates

Recomputed for both checkpoints using the same `SECTION_KEYS`, `SUITE_KEYS`
and `section_average` in `scripts/log_dfm5_headline_averages.py`.
Values below are percentages; differences are percentage points.

| Average | Epoch 10 | Identity | Difference | Metrics |
|---|---:|---:|---:|---:|
| Danish headline | 70.02 | 69.70 | -0.31 | 18 |
| English headline | 77.25 | 75.53 | -1.73 | 15 |
| Math/code headline | 64.09 | 62.46 | -1.63 | 4 |
| Standard suite | 80.72 | 80.59 | -0.14 | 8 |
| DFM suite | 65.98 | 66.42 | +0.44 | 31 |
| EuroEval suite | 68.69 | 66.36 | -2.33 | 18 |

These are observed scores, not a controlled estimate of training damage.
Baseline uses `fix_mistral_regex=true`; identity uses false, matching training.
[Detailed EuroEval investigation](dfm12-identity-euroeval-regression-review.md)
documents matched inputs, the four largest declines, and older controlled
tokenizer evidence. ScaLA Danish remains particularly unexplained. Current
EuroEval raw answers were removed by normal cache cleanup, preventing current
per-answer attribution without a new replay.

Other declines include MBPP 65.76 to 63.66, PIQA-DA 74.07 to 72.22,
HumanEval+ 53.66 to 51.83, and GSM8k 89.54 to 87.94. HumanEval stays 73.17;
MATH rises 49.90 to 50.48, GEC-DaLA exact match 91.99 to 94.24, and
DFM IFEval-DA prompt-strict 65.99 to 68.95. Do not confuse HumanEval+ with
HumanEval or the distinct standard and DFM implementations of shared tasks.

## Protocol Failures Found In Both Checkpoints

### DFM Winogrande

The score improves 3.63 to 13.18, rather than regressing. Its zero-shot prompt
requires `ANSWER: A/B` with only 64 output tokens. Missing parsed answers
exactly match length stops: 2418/2534 at epoch 10, 2122/2534 for identity.
Many outputs start `<think>` and never reach an answer. Both nominal shards
repeat the same 1267 IDs; logs warn that sharding arguments are unused.
The resulting 2534 observations are not independent examples.

Standard Winogrande instead uses five examples and letter-only instructions.
Its 1267 prompts match across checkpoints, with no invalid answers: correct
counts 1048 to 1039 (36 losses, 27 gains), accuracy 82.72 to 82.00.

### Generative Talemaader

Accuracy is 1/808 at epoch 10 and 2/808 for identity. This is dominated by
judge output truncation, not established semantic accuracy. The judge must
explain before emitting `GRADE: C/P/I`, but its server defaults to 64 output
tokens. Missing grades: 806 baseline and 805 identity. Judge outputs exactly
64 tokens: 807 and 806 respectively. The server incorrectly reports `stop`
even for truncated outputs. Relevant code: judge launch in
`eval_scheduler/eval_scheduler/runtime.py` and response construction in
`scripts/transformers_openai_server.py`.

For `dtm_438` (tage tyren ved hornene), both answers correctly explain direct,
courageous confrontation; both judges truncate before a grade. For `dtm_206`
(skomager, bliv ved din laest), the identity judge explicitly agrees with the
reference, then truncates before a grade. Genuine errors also exist:
`dtm_541` (skide groenne grise) is incorrectly explained by both checkpoints.

Next steps, not executed: matched-tokenizer baseline or crossover with retained
responses; rejudge saved idiom answers with sufficient output budget; correct
Winogrande sharding and compare under an explicit matched answering protocol.
No scorer changes, GPU evaluation launches, or W&B writes in this review.

## Temporary Production Pause

At user request, exact controller PIDs 2876769 (original seven) and 3934004
(new twelve) received SIGTERM after command-line verification. Both drained
in-flight work and exited; both `progress.json` files report `phase=drained`
and `active=0`. Final accepted counts: **217458** original seven and **7420**
new twelve. Campaign roots are
`data/dfm12/multilingual-quarter-native-20260927` and
`data/dfm12/european-synthetic-tenth-20260928`; each has a timestamped pause
receipt. Shared vLLM servers and unrelated CPU work were left untouched.
Resume only on a subsequent instruction, preserving ledgers and accepted rows.
