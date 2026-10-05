# Baltic Synthetic Publication Attribution Handoff

Later2026-10-04: six Europarl-conditional packets have a scoped v2 successor.
The additional official-per-sitting-fetch requirement is superseded by actual
source-link/attribution evidence, not a fabricated license. See
`docs/reports/baltic-europarl-scoped-reuse-resolution-20261004.md` and require
the successor `handoff.json` before publication. Historical findings follow.

CPU preparation completed2026-10-04; no GPU, registry, upload or sealed-payload
changes. Tesla owns uploads. No direct agent-message tool is available; parent
can relay this handoff. Executed process3484722 exited successfully.

Root: `exports_dfm13/baltic-source-attribution-20261004-v1`.
Machine-readable handoff: `handoff.json` in that root. Each child is a standalone
HF package with unchanged `data/train.jsonl`, README, original export manifest,
source inventory, captured Europarl terms and hash-bound `attribution.jsonl`.
No token arrays or private audit databases are copied into public packages.

## Ready Now

| Proposed canonical HF repo under schneiderkamplab | Rows | Manifest SHA256 |
|---|---:|---|
|dfm13-multilingual-openhermes-lt|15,000|bd74b62a785384be485585819a8531bbabc0f6ce8604c27ffaf3abb08e7bdb66|
|dfm13-multilingual-openhermes-lv|15,000|a74c4d493ffa324f8528e88cbc13ca0d8fb893327bd72b7cd6b3eeb0a40912a3|

Explicit user OpenHermes authorization is recorded; the inherited DFM8 card
has no blanket license declaration, so none was invented. Every seed retains
its original row ID, constituent label, messages, ordinal and input-file hash.
Both gzip payload hashes were verified. This is project authorization, not a
claim that source-specific upstream terms have been replaced. Tesla should
upload only these two child folders and verify `publication-manifest.json`
attachments remotely; the external parent handoff is not training data.

## Metadata Complete, Existing Europarl Condition Remains

| Package suffix | Total rows | Wikipedia | Scenario-only | Europarl unresolved |
|---|---:|---:|---:|---:|
|grounded-instruct-lt|20,000|13,802|0|6,198|
|multiturn-lt|15,000|4,892|7,645|2,463|
|summary-rewrite-lt|10,000|6,542|0|3,458|
|grounded-instruct-lv|20,000|10,604|0|9,396|
|multiturn-lv|15,000|5,197|5,848|3,955|
|summary-rewrite-lv|10,000|4,942|0|5,058|

The six packets contain30,528 Europarl-derived rows,45,979 Wikipedia rows and
13,493 scenario-only rows. No rows were dropped or rewritten to call them ready.
The specific existing evidence gap is verified official per-sitting attribution
and adaptation scope under Parliament terms. OPUS archive LICENSE defers to
original-source terms; it is not a CC grant. Existing report:
`docs/reports/baltic-source-rights-20261003/report.md`, with captured terms and
sitting-membership evidence. This task did not make new legal findings or
attempt blocked website access. The old concern about intentionally corrupted
denoising tasks does not itself characterize these synthetic tasks; nevertheless
the item-link/scope evidence has not been completed for these exact exports.

Wikipedia attribution uses the actual pinned local source inventory, article
URL/document ID and source hash, with contributor/changes notice and the recorded
CC-BY-SA3.0/GFDL terms. It does not pretend an archive URL is a verified official
Europarl sitting page. DynaWord/DynaInstruct license approval and OpenHermes
authorization are recorded without extending them into an invented third-party
Europarl grant. Resolving that exact condition is the remaining decision/evidence
step; there is no honest CPU-only ETA for obtaining new external permission.

## Verification

- Eight packets /120,000 conversations. Four math/tool packages were outside
  this task and untouched.
- All data SHA256s equal sealed original output pins. Original export manifests
  copied byte-for-byte and checked against original registry pins.
- Every attributed source was found by pool/source ID in the original read-only
  seed database; original fields match, allowing only the added generation flag.
- All four underlying local document-file hashes checked, both inherited
  OpenHermes gzip hashes checked, captured Europarl evidence hashes checked.
- Every attribution row binds exact conversation ID and canonical row hash.
- Sealed registry/completion/source-proof hashes remained unchanged before/after.
- Seven focused tests passed: unknown/hash-mismatched/missing-attribution sources
  fail closed; OpenHermes authorization does not invent a blanket license;
  Europarl readiness remains distinct from Wikipedia and scenario readiness.

Implementation: `scripts/package_baltic_source_attribution.py`.
Tests: `tests/test_package_baltic_source_attribution.py`.
Preparation requires a fresh external root; it never overwrites frozen packages.
No publication, integration promotion or broader rights clearance is claimed.
