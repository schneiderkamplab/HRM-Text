# DaLA v2 Full-Pool Audit Handoff

User scope: all26 candidate language pools (approximately24M pairs) plus clean
controls, not a100-row audit. Jason owns read-only source discovery and a pinned
manifest. This client work must not write DaLA sources or touch nl/fa production.

Prepared batch API: `dfm12.dala_batch_review.canonical(row, language, kind)`,
`request(records)`, `decisions(output, records)`. One exact-content ID per
language/original/corrupted pair serves both LA/GEC; controls have separate exact
language/text IDs. Preserve every source ordinal, original pair ID, split and hash
as an alias to the canonical ID, including aliases across splits; no split transfer.

Existing reusable implementations inspected: DaLA `scripts/audit_european_pairs.py`
(streaming `dfm12.audit_full.Database` leases/cursors), `dala/audit_v2.py` and
`dala/clean_audit_v2.py`. The old runner hardcodes12 languages,8600 ports and16K
context and sends one pair/request, so cannot be launched unchanged. The v2
producer performs isolated-edit and composition audits: the new whole-pair review
must NOT masquerade as those producer audit receipts or call `accepted()` true.

Manifest requested from Jason: `sources` entries with `component`, `language`
(explicit variant), `kind` (`pair` or `clean_control`), `path`, `sha256`, `rows`,
`split`, `receipt`, `receipt_sha256`. Pair fields: `original`, `corrupted`; optional
IDs/edits/source metadata remain in provenance rather than anchor the reviewer.
Unfinalized mutable sources require a frozen copy first, never a guessed live hash.

Batch size at most16, actual26B template<=32768 including4096 output allowance;
split oversized batches, never truncate sentences. Static output schema avoids
new grammar compilation for every set of IDs. Exact ID matching; keep valid
returned members and retry only missing/duplicate/inapplicable members. A valid
alternative/no genuine error fails noisy acceptability. Clean validity, complete
correction and meaning preservation are independently labeled. Empty rationale
is a warning, not automatic rejection. Uncertainty stays nonaccepted.

Implemented CPU-ready entrypoint:

```bash
python -u -m scripts.audit_dala_v2_batches \
  --manifest <Jason-pinned-source-manifest.json> \
  --output data/dfm13/dala-v2-full-pair-audit-20261003-v1 \
  --concurrency 16
```

It reuses Database streaming/leases, canonical-ID alias storage and16-row batch
claims. Producer backlog is bounded; SQLite has one dedicated thread, source
streaming another, token preflight uses worker threads. Every source and receipt
is hashed before its rows are dispatched. Oversized batches split recursively,
never cut text. Only missing/duplicate/inapplicable members are retried (four
attempts, matching the existing Database policy). All raw responses are retained.
SIGTERM stops new claims and drains live work; restart resumes database cursors.
The manifest defines the full population: no hardcoded100-row sample limit.
Short representative batch correctness checking must precede bulk. No DaLA audit
process has been launched here because Jason's pinned manifest is not yet supplied.
