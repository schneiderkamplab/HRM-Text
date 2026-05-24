# Wiki Schema

This wiki follows a compact LLM-wiki pattern: keep source observations, consolidated pages, and session digests separate. The goal is to avoid re-deriving decisions across long coding sessions.

## Page Types

- `pages/*`: consolidated semantic knowledge about the repo, dataset policy, commands, or architecture.
- `sessions/*`: chronological digests of major work sessions.
- `entities/*`: inventories of named objects such as datasets, scripts, configs, and local paths.
- `sources/*`: optional notes about external sources, papers, cards, or gists.

## Required Metadata

Each page should include:

- `Last updated`
- `Confidence`
- `Scope`

## Confidence

- `high`: verified by local command output, file inspection, or successful smoke test.
- `medium`: based on dataset cards, upstream metadata, or reasoned policy.
- `low`: estimates or assumptions that need verification.

## Supersession

If a claim becomes stale:

1. Keep the old claim if it explains context.
2. Mark it `Superseded`.
3. Link or state the replacement claim.

## Ingest Rules

- Prefer concise summaries over raw transcripts.
- Store commands that work exactly as runnable shell blocks.
- Record commands that failed only when the failure teaches something durable.
- Do not write secrets, tokens, credentials, or private user data.
- For dataset policy, separate license, copyright/provenance, and GDPR/PII concerns.

## Quality Rules

- Every operational command should mention the working directory if it matters.
- Every dataset decision should name whether it is `include`, `exclude`, `optional`, or `cap tightly`.
- Every code/script page should name the file path and its responsibility.

