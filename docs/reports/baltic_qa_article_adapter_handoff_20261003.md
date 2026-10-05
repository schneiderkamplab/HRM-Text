# Baltic article sidecar handoff to Epicurus

## Contract and state

CPU-only adapter: `dfm12/baltic_article_adapter.py`; verifier/hydrator:
`dfm12/baltic_article_adapter_verify.py`. No sealed consumer was edited.
Full build destination: `data/dfm13/baltic/article-adapter-full-20261003-v2`.
Build completed all 118866 packets: LT 12895, LV 105971. There are 37653 empty
retrievals, 51314 with one candidate, 11989 with two and 17910 with three;
129022 references point to 71446 unique complete articles. This is coverage,
not a relevance, pairing or factual-acceptance count. Database SHA256:
`ee4059a4690f044d4e18910c06f1520ede19f19e13198861c442e7a054d453a9`.
Only a complete `manifest.json` plus successful `verification.json` is a ready
handoff. `progress.json` alone is not completion or admission. The earlier full
v1 partial output is preserved, not ready; its uncached builder is archived there.
Full v2 verification has now PASSED: all118866 original QA bindings/messages and
all71446 full indexed article dictionaries were checked, with every packet's
article references hydrated and hashed. `verification.json` binds manifest SHA256
`da911f7c53593d89adfb9fea0607da5028c24037d23e577c7ddb899308afdbc3`.
Both CPU processes have exited successfully. This is an integrity-ready evidence
handoff, not a rendered reviewer queue or semantic admission receipt.

`evidence.sqlite` has `packets(id,language,packet,sha256)` and
`articles(id,article,sha256)`. IDs are the unchanged QA candidate IDs and original
language-prefixed article document IDs respectively. Canonical JSON hashes use
`dfm12.io.digest`. Each packet binds the sealed source packet hash and preserves
QA messages, target index, provenance and original upstream record. It excludes
the original audit request, binding/quality status and prior review decisions.
The original QA answer is a review target, NOT gold evidence.

Each packet has zero to three `candidate_articles` with article/text/corpus
hashes, URL and snapshot. `hydrate(db, packet)` verifies references and returns
complete article dictionaries, without truncation. All references explicitly
have `primary_source_identity=false`; all packets prohibit admission and exact
generation-source certification. Retrieval scores are lexical heuristics, not
probabilities. Missing, partial and wrong candidates remain possible.

The consumer must independently assess entity, date and claim relevance; never
equate rank one with the correct homonym. Full rendering/token preflight is still
required: three whole articles can exceed reviewer context. Do not silently
truncate them or treat an overflow as a factual rejection. Existing source and
training-holdout exclusions remain unchanged. Article snapshots are 2023-11-01;
the LV QA card names a later 2024-10-20 snapshot. Neither title matching nor a
successful review establishes original generation-source identity.

## Sample inspection

Sample: `data/dfm13/baltic/article-adapter-sample50-20261003-v2`.
SQLite SHA256: `4e431db560d7d1875121f991c2045beca59c625e61d8523dab52e48dbf85bccb`.
Seed 20261004 selected 25 LT and 25 LV cases from sorted IDs, excluding the
previous diagnostic20. `selection.json` records all IDs. The permissive first
matcher was revised using these SAME 50 cases; this is development inspection,
not an untouched validation sample or language-gold assessment.

Manual inspection of questions, retrieved titles and article leads found:

| Retrieval usefulness | Cases |
|---|---:|
| At least one relevant-topic article | 27 |
| Partial surrounding context only | 1 |
| Unresolved topic/term ambiguity | 2 |
| Candidates present but irrelevant | 2 |
| No candidates | 18 |

This is NOT a tally of factually correct answers. Relevant-topic articles can
still omit the required date, contain errors or accompany distracting hits.
The classification below binds to packet order `ORDER BY language,id` in that
hashed SQLite (zero-based); each packet also has its own digest:

- Relevant-topic: 0,3,4,6,7,10,11,12,14,15,16,17,20,26,28,29,30,31,33,34,35,36,37,40,42,43,44.
- Partial: 49 (Manila city supplies bay location, not a full bay article).
- Ambiguous: 24 (unspecified council term), 46 (Melnezers disambiguation).
- Irrelevant: 23 (Jaugilka village returned Jaugila river), 38 (Great Depression returned a university hall/medal).
- None: 1,2,5,8,9,13,18,19,21,22,25,27,32,39,41,45,47,48.

Concrete useful evidence: Orintaite's biography gives birth details;
Vasario 16 gives the day-of-year calculation; Subacius eldership gives its first
mention and eighteenth-century administration; Mazeikiai council 2003-2007 gives
the election date. The Rose's Name film is retrieved alongside the novel and
roses: entity/type disambiguation remains essential. Several extracted articles
have missing dates in their source text; preserving the whole stored article
does not reconstruct missing Wikipedia markup or certify factual completeness.

## Reproduction

```bash
python -m dfm12.baltic_article_adapter --root NEW_ROOT \
  --packet-root data/dfm13/baltic/qa31-full-packets-v1 \
  --article-root data/dfm13/baltic/article-lookup-diagnostic20-20261003 \
  --diagnostic data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1/calibration-requests.jsonl
python -m dfm12.baltic_article_adapter_verify --root NEW_ROOT \
  --source-root data/dfm13/baltic/qa31-full-packets-v1
```

Add `--sample` for the deterministic50. Same-root resume requires identical
input/code pins; completed IDs are skipped. Run only one writer per root.
Queries use language plus first-question tokens/entities/title matching, never
the hand-authored diagnostic query bank or candidate answer. Query work is
bounded (24 tokens, 8 rare stems, 3 articles); stored source text is not shortened.
The source inventory is 118866 QA rows and the existing index has 200471 articles.
No API, paid search, download, model or GPU calls are made.

Tests: `python -m pytest -q tests/test_baltic_article_adapter.py tests/test_baltic_article_lookup.py`
passed 8 tests. The cache-only optimization reproduced all50 sample retrieval
dictionaries exactly; sample verification also compares every stored article
against the original index row. No direct agent-message channel is exposed here; this file is
the durable Epicurus handoff, not a claimed acknowledgment.
