# Article-aware Baltic QA adapter handoff

Prepared CPU-only `dfm12/baltic_qa31_article_adapter.py` and focused tests.
This is an adapter proposal, not a sealed queue, launch approval or evidence
quality result. No successor root has been prepared; existing consumers, pins,
production ledgers and publication holds are unchanged.

## Retrieval interface for Boole

For each candidate, preserve the exact original/current candidate binding and
upstream record. Pass the existing consumer packet to
`attach(packet, references, allowed_corpus_hashes)`. References are JSON objects
with `path` and `sha256`, matching the pilot's full article attachments. The
allowlist must come from the verified retrieval/source manifest, not be inferred
from arbitrary attachments. The adapter verifies each complete attachment and
text hash, source corpus allowlist, language, candidate hash and unique source
identity. It copies only full article/provenance fields, excluding retrieval
assessments, scores and manual labels. Empty retrieval remains explicit.

Required article fields: language, source_document_id, title, text, url,
source_file, snapshot, source_record_sha256, text_sha256, source_corpus_sha256.
Raw-row/corpus provenance is carried forward; actual corpus and source-row
verification remains the retrieval builder's responsibility, not a claim that
the adapter has reread those corpora. No article is labeled an exact original
generation source or verified supporting reference merely because it was found.

Before a successor can be prepared, Boole's retrieval handoff needs a sealed
manifest binding candidate IDs/hashes, complete selected attachments, corpus
hashes and selection method. Record no-hit and excluded/unselected hits and why;
do not silently drop hard examples or unrelated articles to claim full coverage.
First evaluate the fresh50 retrieval pilot; the old20 are exposed diagnostics,
not fresh gold. Keep assessments separate from model packets. Coordination is
through this handoff; retrieval readiness/acceptance has not yet been confirmed.

## Reviewer contract

Same minimal four fields: reason, verdict, history_quality, factual_support.
No quote/span IDs, extraction schema or per-claim metadata constraints. The
reason must discuss material support, scope and conflicts before the verdict.
Full articles are supplied with complete original QA and the current conversation.
Homonyms, dates, missing evidence, role reversals, omissions, modality, safety,
article-internal contradictions and Lithuanian/Latvian fluency are explicit.
2023 snapshot evidence must not silently become 2024/current truth. Neither
article agreement nor original QA establishes gold. Unresolved essential claims
must be held/rejected, not invented; absence is not proof of falsehood.

Repairs may change only the final target and must not restore unsafe source
advice. Fresh review receives the whole corrected conversation, full original QA
and the same full article evidence, without previous review verdict/reason.
Existing protected-history and support-consistency validation remains in force.
Retrieval is not permission to add article text to training.

## Successor-only integration, pending retrieval

The future builder must regenerate audit_request for every selected packet using
this adapter and pin the new adapter, retrieval manifest and attachment files.
It must use the private article `engine()` for repair and fresh re-audit too;
merely changing initial requests would silently revert later stages to the old
missing-article rubric. The current capacity wrapper does NOT yet select this
engine, so it must not be used to launch article packets unchanged. A separately
versioned wrapper/successor integration is required once retrieval is ready.

Run actual31B native-template preflight with full articles plus8192 output
reserve. No truncation: over-budget packets must be explicit unresolved coverage
or receive a separately designed complete-article review plan. Do not reuse old
budgets or old semantic-calibration approval for this changed reviewer. New
source-aware calibration must measure relevance/error recall and unsafe-source
copying before bulk approval. Measured capacity remains independent of quality.

Validation: **28 focused tests passed** across the new adapter, existing Baltic
consumer and capacity successor tests. They establish interface/invariants, not
semantic reviewer reliability. No GPU requests or current-worker interruption.
