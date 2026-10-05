# Serbian terminal publication and token verification

2026-10-03. All four SR packages are now accepted/uploaded, tokenized and
independently assembler-verified. **254,288 rows, 251,293,446 tokens**.

## Retry disposition

The stale release status showed 22 `audit_retry_pending` rows, but their actual
jobs in `repair/jobs.sqlite` were already terminal. Owner
`66c9373d67ca40199c044a7f46bbc951` completed 21 jobs; one exhausted four attempts
with `ValueError: Incomplete output: length`. The earlier SR retry owner accounted
for a separate 28 jobs. No repair client for this queue was still active at
inspection, and no new GPU requests or retries were needed.

The existing finalizer PID2355940 completed the 22-row transition during this
work: 17 accepted, 4 model-rejected, 1 `excluded_unreviewed` under the existing
exhausted-output policy. It preserved all four `excluded_manual_review` rows.
No model-output failure was reset or converted into acceptance. The forensic
handoff contains every one of these 22 job IDs, attempts, owner, result/error
and final ledger status.

Final ledger: accepted254,288; rejected37,022; excluded_manual_review4;
excluded_unreviewed2; total291,316; no pending retries; terminal/export-ready.

## Publication and evidence

The existing controller published all four data files before the new evidence
attachment path was available in its loaded module. Our scoped publication
attempt detected existing uploads without attachments and refused to overwrite
them. Consequently **no duplicate data publication** was performed.

`dfm12.sr_publication_evidence` added correction evidence through four
metadata-only commits, each compare-and-swap guarded against its original parent
revision. Only README, manifest and `manual-review-decisions.json` were uploaded.
All three attachments and the unchanged remote data hash were then verified.
Original cards/manifests/publication receipts are preserved under
`exports_dfm13/sr-manual-review-evidence-20261003-v1/<task>/parent-*`.
Registry promotion uses its lock and preserves concurrent tokenization fields.
Source license and attribution remain unchanged.

| Task | Rows | Tokens | Current revision |
| --- | ---: | ---: | --- |
| denoising | 74,887 | 103,510,653 | `0d18ee8e4cb3cabc2b2c9308b1b8a0e2211aa309` |
| paragraph-reordering | 30,910 | 44,882,234 | `bc330aeabaa6140ec3a0441f7b56a2dba51cf745` |
| prefix-continuation | 109,633 | 77,131,679 | `9eed7a9cc1d6150fa306e907113b9be89955ab91` |
| span-filling | 38,858 | 25,768,880 | `5bc2f85214941b2b22fc5daa989fbd2275ef8d50` |

All remain in the existing
`schneiderkamplab/dfm13-wave4-wikipedia-sr-<task>` repositories. The component-wide
manual decision attachment is included in each package; its four decisions are
not a claim of four removals from every task. Actual exclusions by task are
one denoising, two reordering, zero prefix and one span.

## Exact scope and token checks

Every exported row was scanned. Cases32/36/37/47 are absent from all four exports.
Case45 occurs exactly once in span-filling with original messages and source
provenance unchanged. The four original manual records/model reviews remain in
the append-only ledger; no further exclusions were introduced.

Existing tokenizer PID2134027 completed all four packages with 16 CPU workers per
tokenization. No duplicate tokenizer was launched; its normal polling was
monitored. Full assembler checks passed for each current registry entry, including
publication/export/attachment pins, row counts, native tokenizer/template contract,
final-assistant labels, zero skipped rows, token array shapes/bounds and hashes.
Token arrays were not rewritten by the metadata-only evidence commits.

## Main/Poincare handoff

[verified-handoff.json](verified-handoff.json) is the current four-entry proof,
including all assembler pins, exact ID checks and retry history. SHA256:
`b72410d3ba2def6e63bca3544bd313db9cbdea37efef502eea295e5c0fce204e`.
Use the four registry entries at the metadata revisions above for the next
verified assembly. No epoch sampling or assembly materialization was performed
here. Earlier pre-attachment publication snapshots remain historical even though
their data/token content is unchanged. This report is the main-thread handoff
for Poincare; no direct messaging tool is available in this worker context.

137 affected tests passed, including real local four-family publication with
exact exclusions and case45 retention, evidence mismatch refusal, metadata-only
upload allowlists, parent-revision conflict, bad remote hashes, idempotency,
token-field preservation and the existing assembler/publication/subset suites.
No GPU/server restart, kill, configuration change or training action occurred.
