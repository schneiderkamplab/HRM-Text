---
type: Runbook
title: DFM14 Remote Production Handoff
description: Independent-machine preparation and generation boundaries while this machine trains XL on DFM13.
status: draft
confidence: high
last_updated: 2026-10-06
tags: [dfm14, handoff, generation, operations]
---
# DFM14 Remote Production Handoff

## Ownership and Current State

The owner requested a portable handoff on 2026-10-06. The second machine owns
DFM14 preparation, generation, audit, repair and publication. This machine
continues XL training on DFM13. Do not pause that training, modify its scheduler
plan, use its GPU endpoints, or log dataset work to its W&B run.

DFM14 is researched, not yet an executable production campaign. There are no
DFM14 accepted-row receipts, final token counts or sampled indices to resume.
The receiver must implement and calibrate the new campaign; historical DFM12/13
launch commands are examples, not safe DFM14 launch commands.

## Read First

1. [Scope and sixteen languages](dfm14-plan.md).
2. [Concrete source candidates](dfm14-language-source-readiness.md).
3. [Six-component recipe and quotas](new-language-expansion-playbook.md).
4. [Knowledge/commonsense pilot](dfm14-knowledge-commonsense.md).
5. [Dyna additions and Matina access](dfm14-potential-additions.md).
6. [Production estimates](dfm14-production-estimate.md).

## Transfer Contract

Use a fresh checkout of the committed revision and its pinned submodules:

```bash
git clone --recurse-submodules https://github.com/schneiderkamplab/HRM-Text.git
cd HRM-Text
git submodule update --init --recursive
python scripts/validate_okf.py wiki
```

The commits must first be pushed (submodule before parent), or supplied as Git
bundles. A commit made only on the training host is not remotely available.
Record the exact parent and submodule revisions in the new campaign manifest.
Provision the receiving host's own CUDA/vLLM environment; do not copy a running
Conda environment or assume this host's absolute paths exist there. Use `uv pip`
for Python installation. Supply HF credentials through the environment/login,
never in tracked files or transfer commands.

Git contains source and planning, not downloaded corpora, model weights,
accepted exports, tokenizer caches, SQLite ledgers or sampled training arrays.
Download source payloads at pinned HF revisions on the receiving machine.
Obtain these immutable reference inputs separately before finalizing quotas:

- Danish accepted transformation baseline used by `transformation_baseline()`
  in `dfm12/prepare.py`, including its referenced files and hashes.
- Sampled repaired English-Danish OPUS token report used by `opus_budget()` in
  `dfm12/budgets.py`; stored/raw token totals are not interchangeable.
- The finalized DFM13 source inventory and source IDs/fingerprints needed to
  distinguish inherited content from genuine additions; reconstruct from
  published datasets or copy immutable release manifests and their inputs.
- Approved modernized OpenHermes seed material if used, not raw OpenHermes.
- The pinned Gemma tokenizer/template and generator model revision.

Resolve those paths from the existing manifests, record checksums, and transfer
only immutable snapshots. Never rsync a live database/WAL or the active
training scheduler into the new campaign. Source-download and adapter work
can start before all sizing references arrive, but quotas must not be guessed.

## Implementation Order on the Receiving Machine

1. Create a separate DFM14 configuration and workspace (`data/dfm14`,
   `logs/dfm14`, `exports_dfm14`). Pin sources, inspect actual rows, record
   language/script, split, provenance, access and inherited-overlap decisions.
2. Reuse adapters from `dfm12/prepare.py`, `cpu_transforms.py`, `budgets.py`,
   `opus.py`, `wave4_cpu.py` and `wave4_instructions.py` where appropriate.
   Do not mutate the inherited registries/configurations in place.
3. Adapt the generation/audit infrastructure in `multilingual_tasks.py`,
   `multilingual_calibration_v6.py`, `wave_synthetic_runtime.py` and
   `wave4_synthetic_specs.py`. Historical `wave4_synthetic_campaign.py` has
   hardcoded language, target, repository and version guards: it cannot simply
   be launched with new language names. Retain guards in a new DFM14 campaign.
4. Implement eight independent state/output shards, deterministic IDs,
   idempotent claims/writes, bounded CPU preparation and resume tests. Use many
   work chunks so later tasks can fill idle endpoints. No shared hot ledger,
   whole-language barrier or unconditional successful-request sleep.
5. Calibrate native language quality, transformations, tool conversations and
   concise non-thinking review protocols before scaling. Keep invalid reviews
   separate from semantic rejection. Audit committed generation chunks while
   remaining chunks generate; re-audit all repaired content.
6. Assign 35K/70K accepted-conversation tiers from actual instruction breadth,
   using the six-family allocations in the recipe. The separate 500K knowledge
   pilot remains proposed; do not silently add its volume to language quotas.
7. Merge baseline/recovery, deduplicate, export accepted-only, verify native
   Gemma formatting and provenance, publish, then tokenize changed sources.
   Report measured rows/tokens/repeats before final assembly or sampling.

On eight otherwise free GPUs, previous starting settings were Gemma 4 26B A4B,
0.95 memory utilization, 1024 server sequences and 384 combined client requests
per endpoint. These are calibration starting points, not hardware-independent
guarantees. Pin the exact model ID and measure five-minute throughput, active/
waiting requests, KV occupancy, GPU utilization, preemptions and accepted yield.
Only start/stop servers owned by this remote campaign.

DaLA curation is a separate workstream: coordinate its delivery and audit, do
not manufacture substitute labels or silently import evaluation pairs.

## Handoff Completion

Return versioned source manifests, all terminal audit/repair counts, accepted
exports and HF revision receipts, token accounting and unresolved shortfalls.
DFM14 work must not change the current DFM13 sample or live XL training. Any
future training transition is a separate operation, not a generation side effect.
