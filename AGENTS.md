# Agent Operating Notes

This repo uses a lightweight LLM wiki under [`wiki/`](wiki/index.md). Before doing substantial work, read:

1. [`wiki/index.md`](wiki/index.md) for the page map.
2. [`wiki/schema.md`](wiki/schema.md) for how to update the wiki.
3. The task-relevant page under [`wiki/pages/`](wiki/pages/).

## Wiki Update Rule

When you make or discover durable project knowledge, update the wiki in the same turn. Durable knowledge includes:

- dataset/source policy decisions
- commands that worked or failed
- dependency/build decisions
- model architecture adaptations
- source-filter changes
- known risks or blockers

Use confidence markers:

- `Confidence: high` for verified local commands, inspected files, or direct tool output.
- `Confidence: medium` for source-card metadata or reasoned integration decisions.
- `Confidence: low` for estimates and unverified assumptions.

If new information contradicts an existing page, do not silently overwrite it. Mark the old claim as superseded and add the new claim with date/context.

## Current High-Level State

- FlashAttention 4 is installed/adapted for B200; FlashAttention 3 was not viable on this machine.
- Training data work is organized around `data/downloads/datasets`, `data/filtered_sources`, `data/converted_sources`, `data/tokenized_mixed`, and `data/sampled`.
- Only Danish DynaWord is intended as raw continuation data. Common Pile has been removed from the downloader manifest.
- Sapient FLAN/Tasksource are denied by default, with narrow allow overrides for selected reasoning/commonsense/science tasks.
- `data_io/tokenizer` must be run from `data_io/tokenizer`, where `Cargo.toml` lives.

