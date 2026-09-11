---
type: Runbook
title: Koolbardi Bilingual Synthesis Runbook
description: Installation, execution, monitoring, recovery, and finalization procedure for the resumable Gemma-native Magpie-style generator.
tags: [koolbardi, dfm11, magpie, synthetic-data, gemma-4, vllm, operations]
status: stable
last_updated: 2026-09-01
confidence: high
sources:
  - id: koolbardi-repository
    resource: https://github.com/schneiderkamplab/koolbardi
    title: Koolbardi source repository
    author: org:schneiderkamplab
  - id: magpie-paper
    resource: https://arxiv.org/abs/2406.08464
    title: "Magpie: Alignment Data Synthesis from Scratch by Prompting Aligned LLMs with Nothing"
    author: org:Magpie-Align
---
# Koolbardi Bilingual Synthesis Runbook

Koolbardi is the independent `koolbardi/` submodule used to generate,
respond to, audit, and finalize bilingual Magpie-style conversations. The
initial DFM11 campaign uses the pinned fresh Gemma 4 31B instruction model,
separate Danish and English generation lanes, and native Gemma `messages`
output. This runbook describes the implementation verified on 2026-09-01. The
dataset policy and admission requirements remain in the [DFM11 plan](dfm11-plan.md).

The ignored `external/magpie` checkout is reference-only. It is not a
submodule, runtime dependency, import, or source of training rows. Koolbardi
has its own Git history and Apache-2.0 license.

## Checkout and installation

Initialize the submodule after cloning HRM-Text:

```bash
cd /work/dfm/HRM-Text
git submodule update --init koolbardi
cd koolbardi
git status --short
git rev-parse HEAD
```

Install into the currently active Conda environment with `uv pip`. The vLLM
launcher uses the separate `audit` environment by default, so installing the
CLI and serving stack need not target the same environment:

```bash
conda activate hrm
cd /work/dfm/HRM-Text/koolbardi
uv pip install -e '.[dev]'
python -m pytest -q
koolbardi --help
```

Runtime data belongs under `data/koolbardi/` and logs under
`logs/koolbardi/` in the parent repository. Do not commit generated shards,
SQLite queues, model files, logs, or final corpora to either Git repository.

## Configuration

Use `configs/dfm11-pilot.yaml` first. It requests 10,000 accepted rows per
language and deliberately over-generates each lane. The production config
requests 500,000 accepted rows per language but remains provisional until the
pilot establishes suitable temperatures, oversampling, category balance, and
acceptance rates.

| Field | Meaning |
|---|---|
| `tokenizer_path` | Pinned tokenizer used to derive the unfinished native user-turn prefix and final rendered lengths. |
| `output_dir` | Queue and phase-shard root; relative paths resolve from the command's working directory. |
| `servers.base_urls` | OpenAI-compatible endpoints distributed across requests. |
| `concurrency_per_server` | Maximum simultaneous requests sent to each endpoint. |
| `shard_size` | Atomic retry and ownership unit. One failed row prevents the whole shard from being committed. |
| `max_sequence_tokens` | Hard final rendered-conversation limit; overlength rows are rejected, never truncated. |
| `lanes` | Language quotas, over-generation factors, complexity shares, and generation-only system conditions. |

Run commands from `/work/dfm/HRM-Text/koolbardi` when using the supplied
configs because their model and output paths are relative to that directory.
Create a new config and output directory for a new campaign; never repurpose a
completed queue with changed generation semantics.

## Start serving

The supplied launcher starts one OpenAI-compatible vLLM server per GPU on
ports 8100 through 8107. It defaults to the `audit` Conda environment, the
pinned Gemma 4 31B model, and 0.70 GPU-memory utilization:

```bash
cd /work/dfm/HRM-Text/koolbardi
CONDA_ENV=audit GPU_MEMORY_UTILIZATION=0.70 \
  scripts/launch_vllm_servers.sh
```

Override `MODEL`, `LOG_DIR`, `CONDA_ENV`, or `GPU_MEMORY_UTILIZATION` through
environment variables rather than editing the launcher. Wait for every server
to become healthy before starting workers:

```bash
for port in $(seq 8100 8107); do
  curl --fail --silent "http://127.0.0.1:${port}/v1/models" >/dev/null \
    && echo "${port}: ready" || echo "${port}: not ready"
done
```

Server logs and PID receipts default to
`/work/dfm/HRM-Text/logs/koolbardi/vllm/`. A PID receipt identifies only a
server launched by this script. Inspect it before stopping anything:

```bash
pid=$(cat /work/dfm/HRM-Text/logs/koolbardi/vllm/gpu0.pid)
ps -fp "$pid"
```

## Run the pilot

The three phases are intentionally explicit. `init` creates the configuration
receipt and instruction shard queue idempotently. Eight workers then claim
shards atomically through SQLite WAL transactions:

```bash
cd /work/dfm/HRM-Text/koolbardi
CONFIG=configs/dfm11-pilot.yaml

koolbardi init "$CONFIG"
scripts/run_phase_workers.sh "$CONFIG" instruction 8
koolbardi status "$CONFIG"
```

The launcher detaches workers and returns immediately. Wait until status has
no `instruction` tasks in `pending` or `running` state. Then enqueue and run
response generation:

```bash
koolbardi advance-queue "$CONFIG"
scripts/run_phase_workers.sh "$CONFIG" response 8
koolbardi status "$CONFIG"
```

After every response shard is done, enqueue and run semantic audits:

```bash
koolbardi advance-queue "$CONFIG"
scripts/run_phase_workers.sh "$CONFIG" audit 8
koolbardi status "$CONFIG"
```

`advance-queue` is idempotent and sees only atomically renamed upstream JSONL
files. It is safe to call again, but the pilot should complete one phase at a
time so counts and failures remain easy to interpret. Worker logs and PID
receipts default to `/work/dfm/HRM-Text/logs/koolbardi/workers/`.

## Status and recovery

Inspect queue counts at any time:

```bash
koolbardi status configs/dfm11-pilot.yaml
```

Each API request retries with bounded exponential backoff. A task failure
requeues the complete shard until `servers.max_retries` is exhausted. Shard
output is written to a temporary file, flushed, fsynced, and atomically
renamed, so a crash cannot expose partial output to the next phase.

Do not reset a running claim merely because it is slow. First verify that its
worker PID is absent and no matching process remains. Then reset claims older
than a chosen threshold:

```bash
koolbardi reset-stale configs/dfm11-pilot.yaml --age-seconds 3600
```

Restart the relevant `run_phase_workers.sh` command afterward. Existing done
shards and queue rows remain intact. A `failed` shard exhausted its configured
attempts; inspect its queue error and worker/server logs before intervention.

## Finalize and inspect

Finalize only after every audit shard is done:

```bash
koolbardi finalize-dataset configs/dfm11-pilot.yaml \
  --output ../data/koolbardi/dfm11-pilot/final.jsonl
```

The finalizer accepts only positively audited rows, removes normalized exact
instruction duplicates, rejects conversations exceeding the configured native
rendered-token limit, applies deterministic per-language quotas, and writes:

- `final.jsonl`: native user/assistant `messages` plus provenance and audit
  metadata;
- `final.jsonl.report.json`: configuration hash, rejected count, and per-lane
  row/token totals.

The generation-only condition remains in top-level `magpie_system_prompt`
metadata but never appears as a training message. Check exact row balance and
rendered-token balance. A lane below target is a pilot result, not permission
to duplicate or translate rows. The current CLI has no automatic top-up
command; calibrate a new campaign or implement a receipt-preserving top-up
before production.

## Stop Koolbardi servers

Do not use a broad `pkill` on a shared evaluation or generation node. The
launcher creates one process group and PID receipt per Koolbardi server. For
each receipt, verify the command and port, terminate that process group, and
confirm that its endpoint disappeared:

```bash
LOG_DIR=/work/dfm/HRM-Text/logs/koolbardi/vllm
for receipt in "$LOG_DIR"/gpu*.pid; do
  pid=$(cat "$receipt")
  ps -o pid,pgid,args -p "$pid"
  kill -- "-$pid"
done

for port in $(seq 8100 8107); do
  curl --fail --silent "http://127.0.0.1:${port}/v1/models" >/dev/null \
    && echo "${port}: still running" || echo "${port}: stopped"
done
```

Only run `kill -- "-$pid"` after `ps` confirms that the receipt still belongs
to the expected `vllm serve`/`conda run` process group. A stale PID may have
been reused by an unrelated process.

## Admission boundary

Successful finalization does not by itself make the data admissible to DFM11.
The current implementation does not yet complete embedding-neighbor
deduplication, protected-evaluation matching, category-aware caps, specialized
math/code/exact-format verification, human-readable stratified review, or Hub
publication validation. Complete those gates from the DFM11 plan, record their
receipts, and freeze the pilot findings before launching the provisional
million-row production config.
