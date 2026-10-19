---
type: Reference
title: Full XL Control Serving Parity
description: Independent production and Mimir2 exports of the 3.82M control, tokenizer corrections and compiled full-weight generation comparison.
status: draft
confidence: high
last_updated: 2026-10-19
tags: [mimir2, inference, parity, tokenizer, vllm]
---
# Full XL Control Serving Parity

## Purpose and artifacts

The user requested a direct comparison before interpreting the gated/control
3.82M evaluation. Source: control `step_3820000`, EMA, under
`checkpoints/hrm_v2/hrm-control-XL-from-3800000`. Independent exports:

- Production converter and `hrm` environment:
  `exports/hrm_control_step3820000_ema_parity_hf` (packed HRM-Text).
- New exporter and `mimir2` environment:
  `exports/mimir2_control_step3820000_ema_hf` (split Mimir2, every v2 feature off).

Evidence: `logs/analysis/mimir2_control_3820k_parity/` contains `report.md`,
`export_comparison.json`, `summary.json`, full `prompts.json`, and each run's
JSON and log (`v1`, `mimir2`, `v1_mimir2_env`). Script:
`scripts/compare_mimir2_control.py`, modes `prepare`, `worker`, `summarize`.
No W&B writes, production process termination, or scheduler interruption.

## Actual export defects found and fixed

The initial Mimir2 export did not assign BOS/EOS/PAD when loading the raw
Gemma tokenizer. It also relied on runtime `fix_mistral_regex=True`. Merely
copying the production tokenizer JSON did not solve the second issue:
Transformers skips the legacy patch for a model config carrying a sufficiently
new `transformers_version`, unlike the production export without that field.
Thus identical raw tokenizer files could produce different effective pipelines.

Superseded: copying raw tokenizer files or passing the flag alone is sufficient.
Correct behavior is to materialize the **effective production tokenizer** with
its pretokenizer into the new export and check round-trip behavior. The exporter
now requires `--tokenizer-reference` for Gemma-template exports and checks that
preprocessing survives save/reload. Special IDs are BOS=2, EOS=106, PAD=0.
Both queued Mimir2 exports (pilot and control) were repaired before any of their
566 comparison rows ran. We did not alter the production tokenizer or its policy.
This preserves production behavior; it does not independently establish that
the historical regex policy is linguistically optimal.

## Full-weight results

After canonical packing/name normalization, all **131 tensors**, comprising
**1,786,775,040 elements**, are bit-identical. Architectural fields agree:
1536 hidden size, 16 physical layers per stack, H=2/L=3, PrefixLM, ordinary
RoPE, embedding scale, normalization, vocabulary and context limit. Mimir2's
128 `num_hidden_layers` is expanded KV slot accounting, not 128 physical layers.

Both serving paths used BF16, FA4, `enforce_eager=False`, torch.compile and
CUDA graphs, a 512-token smoke context, 512 MiB KV cache, at most two active
requests, greedy decoding and up to 64 output tokens. Prompts are 26-109 tokens.
Nine cases cover English/Danish arithmetic and summaries, JSON, Python, multi-turn
recall, a tool call and a tool-result follow-up. Tokenized prompts match in both
actual environments.

| Measurement | Result |
| --- | ---: |
| Identical complete generated sequences | 9 / 9 |
| Identical generated token IDs | 176 / 176 |
| Mean generated-token absolute logprob difference | 0.00320486 nats |
| Maximum generated-token absolute logprob difference | 0.0562680 nats |
| Maximum generated-token probability difference | 2.98608 percentage points |
| Maximum matched full-prefix logprob difference | 0.608202 nats |

The full-prefix diagnostic feeds the same baseline continuation into both
bidirectional prefills. It is **not** a causal likelihood/perplexity measurement.
The largest difference is on a very low-probability token (about -21 nats).
Generated-token differences are smaller, but not zero.

An additional control ran the original HRM-Text model in the new `mimir2`
environment: generated tokens, generated logprobs and all full-prefix diagnostic
logprobs were identical to the production environment. The remaining differences
are therefore between model execution implementations, not this environment
change. BF16/compiled-operation rounding is a plausible explanation, not yet
isolated by a matched FP32/eager experiment.

This establishes full-weight export parity and sampled greedy behavioral parity,
**not bitwise numerical equivalence or equal benchmark scores**. Near-tied
decisions or longer contexts could differ. Both tool-call probes deliberately
used only the end-of-turn stop token; both emitted the same valid call followed
by a degenerate tool-response tail. Do not count that as successful tool-protocol
handling. All test processes exited and released their GPU allocations.

## Scheduled downstream comparison (2026-10-19)

Superseded: the two-arm schedule published Mimir2 control results to the main
XL run. Before any comparison rows started, it was expanded to three arms:

| Arm (3.82M EMA) | W&B DFM5 run ID |
| --- | --- |
| Ungated control, production HRM-Text HF export | `dfm8-xl-from-dfm6-dfm7-epoch5-clean-full` |
| Same control weights, Mimir2 HF export | `hrm-control-3820000-mimir2-export` |
| Gated pilot, Mimir2 HF export | `hrm-v2-XL-from-3800000` |

All use compiled persistent vLLM (no eager), identical task definitions and
batch sizes: 173 inference shards per arm, eight standard and thirteen core
DFM tasks including IFEval-DA; no EuroEval in this matched comparison.
The production HRM export is served in the same `mimir2` environment, whose
HRM implementation was independently smoke-tested above, to avoid confounding
model architecture with dependency versions. Main-run control values cannot
be overwritten by Mimir2 control publication.

Installed by `scripts/schedule_hrm_3820k_export_comparison.py --install` into
the existing `logs/scheduler/dfm10_XL_epoch9_20260831` SQLite plan, under a
released administrative lock, with a database backup. Adds 282 rows, including
173 inference shards and their merges/publication. The existing terminal-only
inference barrier now includes all three arms before ungated XL continuation
to 3.85M; failed inference and unfinished publication do not strand training.
Current XXL-wide 1.15M work was not interrupted.

### Related pages

### Full-suite expansion (2026-10-19)

Superseded by explicit user request: the 173-shard restricted comparison above.
`scripts/expand_3820k_full_evals.py --install` expanded each arm to the complete
1.15M task inventory, preserving its existing core jobs and W&B destination.
Each arm now has 1,047 inference jobs: 85 standard, 667 DFM, 32 DFM IFEval-DA,
261 ordinary EuroEval and two batched EuroEval IFEval jobs. The earlier 1,045
count accidentally omitted the latter two. Total across arms: 3,141 inference
jobs. All corresponding publication/merge rows and nine average rows per arm
are included (2,196 rows per arm). The terminal training handoff waits only
for inference to terminate, not successful publication. Compiled non-eager
serving and isolated output roots remain unchanged.

- [Mimir2 serving limits](mimir2-vllm.md)
- [Gated/control evaluation schedule](hrm-text-v2-gated-pilot.md)
