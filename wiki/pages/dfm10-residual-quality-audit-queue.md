---
type: Runbook
title: DFM10 Residual Quality-Audit Queue
description: Ordered, resumable post-reconciliation audits over active DFM10 training representations.
tags: [dfm10, data-quality, audit, operations]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM10 Residual Quality-Audit Queue

The post-reconciliation audit backlog is encoded in
`config/dfm10_residual_quality_audits.yaml` and launched by
`scripts/run_dfm10_residual_quality_audits.sh`. The detached campaign uses
`logs/data_audits/dfm10_residual_quality_20260830` and keeps its atomic ordered
state in `state.json`. It waits first for the active Mimir generation/audit
campaign and then for the combined English/Danish MedQuAD campaign. It also
requires at least 170,000 MiB free on every GPU and does not stop or reuse
either predecessor's vLLM processes. Once available, it starts eight persistent
Gemma 4 26B-A4B judge servers and reuses them across all stages.

## Ordered stages

1. 17 active Sapient provenance families, 500 exact tokenized examples each
   (8,500 total);
2. native tool/agent data, including 100 examples from every Terminal task and
   deeper samples from DOLCI, Glaive, ToolACE, xLAM, and DeepDive;
3. 5,000 accepted Folketing error-correction examples;
4. seven retained borderline Danish sources (2,359 currently eligible rows at
   the configured caps);
5. retained borderline English sources, including 20 examples from each
   Natural Instructions task (19,113 current samples across 670 strata);
6. the six currently unfinished persona/Mimir packages after they become
   materialized and receive `uploaded` admission status.

**Superseded stage-6 finalization dependency (resolved 2026-08-31):** persona chats and answer-contract
calibration have since reached uploaded status. The four benchmark campaigns
(BoolQ, DROP, event/coreference, and IFEval) remain work in progress. The
current `run_mimir_benchmark_campaigns_8gpu.sh` runner generates and audits its
1,024 shards but deliberately does not finalize them. A detached
`finalize_mimir_benchmark_campaigns_when_ready.sh` process now waits behind it
and performs exact decontamination, validated-row building, packaging, upload,
remote verification, tokenization, and locked union integration. Campaign
quotas are informational rather than blocking, but all quality and publication
validations remain fail-closed. Stage 6 remains blocked until the four remote
verification receipts promote the packages to `uploaded`.

All six packages subsequently reached `uploaded`, so this dependency no longer
blocks the residual audit. The paragraph above is retained as the historical
ordering constraint that governed the campaign.

Preparation and auditing are resumable. Each stage merges atomically before
the next stage starts, and a stage that cannot satisfy its source-count gate is
marked blocked and retried rather than silently auditing a partial corpus. In
particular, the native-tool stage requires all 29 Terminal source
configurations and all 13 repaired DOLCI token tasks; the union presently has
27 Terminal tasks, so that stage will wait for the missing two configurations.
Worker failures receive three resumable wrapper attempts. The queue is
serialized deliberately so later lower-priority audits cannot consume GPUs
before higher-priority coverage is complete.

The Sapient stage samples random-access token arrays rather than scanning the
318.75M exported gzip rows. This both audits the representation visible to
training and avoids unnecessary filesystem pressure. OpenMathInstruct2,
QReCC-II, and SciBench are sampled from their active repaired replacements.

## Active launch

The runner was relaunched with the final lock-safe implementation as detached
PID `2492064` on 2026-08-30. The current runner waits for both
`run_mimir_benchmark_campaigns_8gpu.sh` and
`run_dfm10_medquad_da_8gpu.sh`, in that order as established by their existing
GPU waits.
Its current processes and PID are operational state rather than a permanent
identity; the lock and receipts under the run root are authoritative after a
restart.

On 2026-08-31, the first post-predecessor launch exposed an invalid CUDA root:
the conda toolkit headers live under
`/home/ucloud/miniforge3/envs/audit/targets/x86_64-linux`, not directly under
the environment prefix, while its internal `cicc` compiler lives under the
environment's `nvvm/bin`. FlashInfer therefore failed to compile its
fused-MoE kernel. The runner now exposes both paths, prewarms the shared
FlashInfer cache on GPU 0 before launching the remaining servers, and fails
immediately if a server process exits during startup.

The first stage-1 production pass completed all 8,500 rows but retained one
retryable malformed/truncated JSON judgment for an AMPS Mathematica example.
Because the quality gate is fail-closed, the wrapper exhausted its three
resumable attempts and shut down rather than merging 8,499 decisions. Valid
partition rows remain intact. The runner now allows 1,024 judge-output tokens
instead of 512; resumable loading removes only the judge-error row and retries
it before merging and advancing to stage 2.

Stages 1-5 subsequently completed with zero judge errors. Stage 6 initially
failed its preparation uniqueness gate because raw-package sample IDs used the
common `data/` directory plus shard-local row numbers, which collide across
multiple `train-*.jsonl.gz` shards. This is superseded by full relative shard
paths in raw-package sample identities. The correction affects only stage-6
sample preparation; completed tokenized-source stage receipts remain valid.

## Completion, 2026-08-31

The campaign is complete. All stages merged atomically with zero remaining
judge errors:

| Stage | Audited rows | Usable rows |
|---|---:|---:|
| Sapient packages | 8,500 | 7,059 |
| Native tool and agent data | 5,900 | 5,589 |
| Folketing error correction | 5,000 | 3,127 |
| Borderline Danish | 2,359 | 1,690 |
| Borderline English | 19,113 | 16,287 |
| Completed WIP packages | 6,000 | 5,853 |

Stage 6 completed all 6,000 deterministic samples after the shard-aware
identity fix. The runner exited normally and tore down all eight persistent
judge servers. The authoritative judgments, summaries, partitions, and atomic
receipts remain under the campaign run root.

## Repair recommendations from the residual audit

The generic judge is useful for triage but is not itself a row-level admission
oracle. In particular, it often treated a valid intermediate DeepDive tool call
as an incomplete final answer, and it rejected 42.6% of sampled OpenMath direct
answers versus 22.6% of CoT answers partly because it expected a derivation from
the direct-answer contract. Repairs must therefore be task-aware.

Recommended order and approximate resource budget on this eight-B200 node:

| Priority | Action | Estimated engineering/CPU wall time | Estimated GPU work |
|---:|---|---:|---:|
| 1 | Tighten Folketing error-correction gates: reject normalized no-ops, negligible edits, remaining OCR corruption, and truncated targets; then repeat the 5,000-row audit. Do not regenerate all 3.1M rows. | 4-12 hours plus review | 0.2-0.8 B200 GPU-hours for the validation audit; full regeneration would cost roughly 780-1,550 GPU-hours and is not recommended |
| 2 | Build a Natural Instructions task denylist from the audit: exclude the 48 tasks with at least 50% sampled failures, re-audit the 74 tasks in the 25-49% band at 100 rows/task, and retain the cleaner tasks. | 2-4 hours | 0.2-0.8 B200 GPU-hours, normally under 10 minutes wall time after server startup |
| 3 | Retire legacy Tidsskrift BT, EUR-Lex BT/summary, and DOAB BT in favor of grounded replacements; deterministically remove truncation/contract failures from DynaWord BT and verify Kænguruen/Multi-Zebra answers. | 2-4 hours | 0.2-1.0 B200 GPU-hours for a Danish delta audit |
| 4 | Re-audit DeepDive and repaired DOLCI with a trajectory-aware rubric that sees whether a target is an intermediate tool call or final response. Keep deterministic native-schema validation authoritative. | 3-6 hours | 0.4-1.6 B200 GPU-hours; broad regeneration is not indicated |
| 5 | Re-audit Sapient math by `direct`/`cot` contract. Keep existing symbolic/final-answer verification authoritative, drop QReCC-II if a full task-aware audit confirms its 47% defect rate, and downweight rather than regenerate enormous AMPS/DMMath families. | 4-8 hours | 2-8 B200 GPU-hours for stratified audits; a complete LLM audit of the largest families is not economical |
| 6 | Apply deterministic contract checks to ASSET, IF-SFT, AESLC, CoEdIT, Tulu algebra, and other one-pass English sources; re-audit only rejected/borderline strata. | 4-8 hours | 1-4 B200 GPU-hours |
| 7 | Run known-answer and schema verification over the Mimir answer-contract, DROP, event/coreference, and IFEval packages. Their 97.6% aggregate usability does not justify regeneration. | 2-4 hours | 0.2-1.0 B200 GPU-hours for confirmation |

The minimum practical cleanup is priorities 1-4 plus deterministic verification
in priority 7. It is approximately one to two engineering days and roughly
1-5 B200 GPU-hours, excluding token-tree rebuild and DFM10 resampling. Bulk
LLM regeneration of all rejected rows would be substantially more expensive
and would erase useful provenance without evidence that regeneration improves
the source.

Inspect the durable list with:

```bash
python scripts/dfm10_residual_audit_queue_state.py status \
  --run-root logs/data_audits/dfm10_residual_quality_20260830
```

Follow the runner with:

```bash
tail -f logs/data_audits/dfm10_residual_quality_20260830/runner.log
```

Relaunching the same command is safe after the old runner exits. The runner
holds `runner.lock`, recognizes merged stage receipts, resumes partition
outputs, and resets stale in-progress state to pending.
