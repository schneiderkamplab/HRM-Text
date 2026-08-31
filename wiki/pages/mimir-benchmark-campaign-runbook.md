---
type: Runbook
title: Mimir Benchmark Campaign Runbook
description: Production and recovery procedure for verifier-backed IFEval, BoolQ, DROP, and event/coreference training data.
tags: [mimir, dfm10, generation, audit, vllm, operations]
status: draft
last_updated: 2026-08-30
confidence: high
---
# Mimir Benchmark Campaign Runbook

## Scope and gates

`config/mimir_benchmark_campaigns.json` defines the first production targets:
200,000 accepted IFEval rows, 100,000 BoolQ-entailment rows, 200,000 DROP
reasoning rows, and 300,000 event/coreference rows. Candidate requests are
grounded in the immutable Mimir passage inventory and retain row-level source
provenance. Evaluation questions are not used as generation seeds.

The deterministic verifier runs before the independent model audit:

- IFEval checks every required/forbidden word, count, prefix/suffix, section,
  order, or JSON-key constraint.
- BoolQ fixes balanced labels before generation and requires a byte-exact
  evidence span from the passage. Negative examples must be direct
  contradictions according to the independent audit.
- DROP executes the declared arithmetic program, requires every operand string
  in the passage, and checks exact agreement with the target.
- event/coreference fixes answer positions before generation. Pair variants
  require two examples, different assigned positions, and invariant correct
  answer text across the controlled swap.

All accepted rows additionally require a five-dimension Gemma 4 31B audit with
minimum score 4/5, normalized-exact benchmark decontamination, prompt
deduplication, and Gemma-native rendered length at most 4,096 tokens.

## Preparation and execution

Prepare the deterministic 990,000-request, 1,024-shard manifest with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python \
  scripts/prepare_mimir_benchmark_campaigns.py
```

Run one Gemma 4 31B server per GPU with the shared atomic queue:

```bash
cd /work/dfm/HRM-Text
RUN_ID=20260830_full_v1_schemafix \
PATH="/home/ucloud/miniforge3/envs/audit/bin:/home/ucloud/miniforge3/envs/hrm/bin:$PATH" \
setsid bash scripts/run_mimir_benchmark_campaigns_8gpu.sh \
  > logs/mimir_benchmark_campaigns_launcher_20260830_schemafix.log 2>&1 < /dev/null &
```

The production defaults are concurrency 64, model length 8,192, maximum 128
sequences, and GPU-memory utilization 0.70. The runner uses one persistent
server per B200 and dynamically claims the next shard with atomic `mv`. Each
shard runs generation and audit twice; successful append-only records are
reused, so retries fill failures rather than regenerating accepted rows.

The active log root is recorded in
`data/mimir_benchmark_campaigns/current_run_log_root.txt`. Queue state is under
its `queue/{pending,running,done,failed}` directories. Generated rows and audits
are under `data/mimir_benchmark_campaigns/{generated,audits}`; completion markers
are written only after both phases finish.

## Recovery and validation

Terminate the recorded runner PID with `TERM`; its trap kills exact campaign
clients and the eight server process groups. Do not kill unrelated vLLM
processes. Relaunch with a new `RUN_ID`; completed data markers and successful
JSONL records remain authoritative.

The first launch on 2026-08-30 was stopped after about 7,800 generations. It
showed healthy BoolQ structure but inconsistent return keys for IFEval, DROP,
and event/coreference. That prompt is superseded. The literal schema version
preserves 920 already-valid BoolQ rows and retries only requests without a
successful generation.

Before final building, run normalized-exact decontamination with the existing
Mimir benchmark manifest, then invoke `scripts/mimir_benchmark_campaigns.py
build`.

**Superseded, 2026-08-30:** the initial rule made every configured campaign
quota a hard release gate. The production decision is now to retain and
publish every validated accepted row after all 1,024 shards complete, even if
one or more target quotas are short. Quotas remain visible in
`accepted/summary.json` as `target_shortfalls`. Structural verification,
independent audit acceptance, exact decontamination, prompt deduplication,
Gemma-native 4,096-token validation, package validation, and remote file parity
remain hard gates.

The detached finalizer is
`scripts/finalize_mimir_benchmark_campaigns_when_ready.sh`. It waits for all
request/generated/audit shard triplets, performs the gates above, builds and
validates four independent packages, uploads only those packages to the
`schneiderkamplab` namespace, verifies their remote file sets, refreshes the
receipt-backed export inventory, then tokenizes the accepted sources and
rebuilds the DFM10 union under `data/.dfm10-union.lock`. Its log path and PID
are recorded under `logs/mimir_benchmark_campaigns_finalize_*` and
`data/mimir_benchmark_campaigns/finalizer.pid`.
