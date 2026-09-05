---
type: Runbook
title: DFM11 Folketing Error-Correction Repair
description: Deterministic filtering, task-aware full audit, and rejection-removing finalization for the DFM10 Folketing OCR-correction source.
tags: [dfm11, folketing, error-correction, audit, filtering, vllm]
status: draft
last_updated: 2026-09-04
confidence: high
---
# DFM11 Folketing Error-Correction Repair

## Deterministic Rebuild

The rebuild examined all 3,105,440 rows from the pinned
`schneiderkamplab/dfm10-folketingets-dokumenter-error-correction` revision
`741da1387a126900ec96e13fb065d5cd7f9f89b6`. It retained 2,548,956 rows
(82.1%) after proving that every complete source/target relationship is exactly
explained by 1-8 declared synthetic OCR substitutions.

| Deterministic result | Rows |
|---|---:|
| Retained | 2,548,956 |
| Target contains non-Latin OCR artifacts | 430,322 |
| Fragmented target lines | 99,828 |
| Index or dot-leader target | 26,197 |
| Low alphanumeric density | 122 |
| Target too short | 15 |

The deterministic intermediate is
`exports_dfm11/dfm11-folketingets-dokumenter-error-correction-repaired`.

## Superseded Generic Audit

A generic 5,000-row instruction-data judge retained only 3,012 rows (60.24%).
Most rejections incorrectly treated the intentionally sparse 1-8 character
corrections as response mismatches. That judgment is superseded for this task.
A task-aware audit of the same sample used strict JSON-schema constrained
decoding and retained 4,885/5,000 rows (97.7%) with zero judge errors.

## Full Audit

The user strengthened the sample gate to a full audit of all 2,548,956
deterministic survivors. Four audit-owned Gemma 4 26B A4B vLLM servers run on
GPUs 0-3, ports 8100-8103, at 64 concurrent requests per server. The judge is
explicitly told that the deterministic validator already proved the sparse
corrections. It evaluates only:

- coherent Danish;
- acceptable residual OCR quality;
- complete, non-list/non-index text;
- usefulness as a training example.

Each GPU writes a separate append-only `.partial` decision file under
`logs/dfm11_folketing_error_correction/full_audit/workers/partition_*/`.
Completed row IDs are loaded on `--resume`, so server or client interruption
does not discard completed judgments. A synchronized exit of the previous
Koolbardi-owned servers interrupted the first attempt after approximately
12,000 decisions; audit-owned replacement servers were started and the run
resumed successfully.

Run or resume the audit with:

```bash
setsid bash scripts/run_dfm11_folketing_error_correction_full_audit.sh \
  > logs/dfm11_folketing_error_correction/full-audit-launcher.log 2>&1 < /dev/null &
```

The launcher requires all four health endpoints before starting clients. It
uses strict JSON-schema decoding and bounded retries for URL, HTTP, connection,
timeout, and decoding failures.

Detached vLLM launches from the `audit` Conda environment must explicitly set
`CUDA_HOME=/home/ucloud/miniforge3/envs/audit` and prepend that environment's
`bin` directory to `PATH`. CUDA 13.2 and `nvcc` are installed inside the Conda
environment; detached shells otherwise make FlashInfer look only for the absent
`/usr/local/cuda` and server startup fails. On 2026-09-04, all four audit-owned
servers received an external `SIGTERM`. Their clients preserved completed
decisions, and the servers were relaunched with the explicit CUDA environment.
Transport-error decisions accumulated during the outage are removed and
retried by the existing `--resume` path before finalization.

After the 2026-09-05 cluster power interruption, the full-coverage retry found
24 rows that repeatedly consumed the original 256-token response budget before
emitting their constrained JSON verdict. The audit response ceiling is now
1,024 tokens. This does not relax the JSON schema or acceptance criteria and
only materially affects difficult rows that need the additional generation
budget.

## Finalization Contract

**Updated, 2026-09-04:** automatic finalization is disabled. The audit stops
after writing decisions; no audited package may be materialized or tokenized
until explicitly requested. A later finalization requires exactly 2,548,956
unique decisions and zero unresolved judge errors. It then builds
`exports_dfm11/dfm11-folketingets-dokumenter-error-correction`, omitting every
row whose full-audit verdict has `keep=false`. The deterministic intermediate
is not mutated, and each output shard is atomically replaced only after it is
fully written.

Finalization is an explicit opt-in by setting `FINALIZE_ON_COMPLETE=1` when
launching the full-audit script. Do not set it during the current audit.

**Superseded later on 2026-09-04:** the user explicitly approved complete
materialization, Hub publication, tokenization, and DFM11 integration after the
full audit. A detached post-audit pipeline now waits for the active clients,
resumes any unresolved audit rows, requires complete unique coverage and zero
judge errors, and then performs those stages. It does not mutate the
deterministic intermediate.

The upload package is
`exports_dfm11/dfm11-folketingets-dokumenter-error-correction`; publication is
to `schneiderkamplab/dfm11-folketingets-dokumenter-error-correction`, followed
by remote file and manifest verification and revision pinning. Tokenization
adds the package to `data/tokenized_dfm11_additions` using the Gemma 4 native
template and a 4,096-token limit.

DFM11 excludes the inherited
`folketingets-dokumenter-error-correction__` prefix and selects the replacement
`dfm11-folketingets-dokumenter-error-correction__` prefix at repeat one and
`max_per_file: 75000`. The 13 source shards therefore contribute at most
975,000 broadly distributed rows per epoch, closely implementing the intended
one-million-row family cap. The complete upload reservoir remains available;
the cap is sampling policy, not destructive publication filtering.

The post-audit command is:

```bash
setsid bash scripts/run_dfm11_folketing_error_correction_post_audit.sh \
  > logs/dfm11_folketing_error_correction/post-audit.log 2>&1 < /dev/null &
```

The current node lacks `data/tokenized_dfm10`. Consequently, the pipeline can
finish package publication, tokenization, and replacement configuration but
must defer physical construction of the final `data/tokenized_dfm11` union
until that base store is restored.

Initial throughput after warm-up was approximately 105 rows/s across four
B200s, corresponding to about 6.7 hours wall time and 27 B200 GPU-hours if
sustained. Final counts and measured throughput must replace this estimate when
the run finishes.
