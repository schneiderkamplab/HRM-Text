# Baltic QA diagnostic20: local article evidence pilot

## Completed CPU Work

Isolated root: `data/dfm13/baltic/article-lookup-diagnostic20-20261003/`.
Builder/query CLI: `dfm12.baltic_article_lookup`; tests:
`tests/test_baltic_article_lookup.py`.

The SQLite FTS5 index contains **200,471 full articles**: 123,850 LT and 76,621 LV.
It read the existing 530,330,694-byte corpora and verified both complete file
hashes against `local-sources.json`. The index occupies 948,617,216 bytes and has
SHA-256 `6680405c18b80a28d76f37232c53ccb487b1bbd679ba8610554317684a90c9b6`.
There were no network downloads, paid/model/GPU calls, source-file changes,
consumer edits or hold changes.

The authoritative pilot output is **`pilot-v2/`**, containing full native QA and
upstream packets plus full article attachments. The initial `pilot/` retrieval
draft is preserved but superseded. Title-prefix retrieval initially favored short
body documents and homonyms; the final title-length ordering and explicit topic
qualifiers improve some diagnostic matches but remain heuristic. Queries are a
transparent hand-authored bank from the sampled questions, entities and specific
claims, not an automatic production alignment model. Candidate recall must not be
confused with verified source identity.

Final inventory: **19/20 cases have search hits, 66 article references**. Only 17
cases have relevant evidence after inspection; Tuči returned an actor homonym,
Jankto returned Sioux-related prefix matches, and Rūbeža returned nothing.
These are bounded-query results, not claims that the entire Wikipedia lacks the
articles. The existing corpora are length-filtered 2023-11-01 snapshots, whereas
the LV QA card names October 2024. Exact original generation-source matches
certified: **zero**.

Each attachment preserves full text, source document ID, title, URL, source file,
snapshot, source-corpus SHA, raw source-row SHA and text SHA. Query-specific scores
are not written into shared article files. All 66 referenced attachment hashes,
full text hashes and every selected quotation/offset were verified. `assessment.json`
binds observations to candidate IDs, original record hashes and complete packets;
`assessment-receipt.json` hashes the notes and artifacts. Original source licenses
and source-holdout flags remain in the pinned source manifest; retrieval is not
permission to add article text to training.

## Sample-Bound Assessment

The categories below concern evidence usefulness for the identified claims,
not whole-conversation admission or native-speaker gold:

| Outcome | Cases |
|---|---:|
| Retrieved article supports sampled claims | 5 |
| Concrete contradiction with retrieved article | 6 |
| Partial support/context; unresolved claims remain | 4 |
| Source-internal issue or temporal uncertainty remains | 2 |
| No relevant retrieved article | 3 |

| Case | Candidate prefix | Outcome and evidence |
|---:|---|---|
| 0 | `00015f48af9d` | Support: Klaipėda municipality climate section contains both historical temperatures and dates. Not meteorological gold. |
| 1 | `3fbe108b9dfd` | Support: Vincas Sinkevičius opening supplies the birth date/place. |
| 2 | `82203b7bbc52` | Support: Žiogeliai (Druskininkai) supports the reserve, 1784 mention and film association; generic prefix also retrieves unrelated insects. |
| 3 | `c17a6d142324` | Source issue: Auslas article itself contains the questionable northeast-southeast axis. Recovery locates the wording, not the correct axis. |
| 4 | see bound packet | Support: church history names Jeronimas Krišpinas-Kiršenšteinas and 1670. |
| 5 | see bound packet | Source/date issue: Antakalnis says four trolleybus routes but lists five. Repair's five is defensible; current counts/routes are not verified for 2026. |
| 6 | see bound packet | Partial: LDK trade section supports honey/furs/beavers, not all added commodities or malformed Lithuanian. |
| 7 | see bound packet | Contradiction: town article says Trakų district, not the repaired Vilnius-district municipality. Disambiguation lists separate Švenčionys villages; intended village/distance remains unresolved. |
| 8 | see bound packet | Support: Romuva festival section supplies seasonal cycles and listed festivals. |
| 9 | see bound packet | Contradiction: Žiemgala article explicitly includes historical territory in Lithuania, omitted by the repair. |
| 10 | see bound packet | Partial: Hāfezs confirms the literary genre association, not the detailed rhyme account. Animal gazelle hits are irrelevant. |
| 11 | `40abf950a0cf` | Contradiction: Aļģes explicitly describes both sexual and asexual reproduction. Medical algology is a separate sense. |
| 12 | `8075043df160` | Contradiction: Chinvali source assigns slow reinforcement arrival to Russian forces, while QA switches it to Georgian forces. This is concrete entity-role reversal. |
| 13 | `c0a8fed4c3c4` | Contradiction: league and club articles identify 2. līga as third tier. Club current-status prose is date-sensitive; stadium capacity remains unresolved. |
| 14 | `ffff781dfce3` | No relevant village article; actor Tucci is not evidence. |
| 15 | `484ecf186b17` | No Rūbeža river evidence recovered; no factual conclusion from absence. |
| 16 | `31b527afc548` | Partial: Auru pagasts lists Bērzkrasti and the Zemgale category, corroborating the regional concern but not all settlement distances/details. |
| 17 | `02879ee72223` | Partial: Humašaha article supports lineage, spouses and child counts; it distinguishes Mihrimah as an aunt. Broad political-power embellishments remain unsupported. |
| 18 | `94e1faaafa00` | No relevant Jankto article: Sioux hits are homonyms. Earlier external club-history evidence remains separate and unchanged. |
| 19 | `478ae9398c34` | Contradiction: CO article includes rescuer-safety qualification omitted by repair and different medical terminology. Article also contains questionable old advice; do not blindly restore it. Missing-document prompt remains a separate defect. |

All 20 full candidate IDs and hashes are in the assessment JSON. The previous
independent review is not overwritten. Article agreement strengthens source
support, not independent truth: inherited encyclopedia errors remain possible.
The new Chinvali role-reversal finding is grounded in literal retrieved text,
not reviewer memory. No current source hold is weakened by a supported case.

## Successor Packet Adapter Proposal

This is useful enough for a **new successor**, not an in-place sealed-consumer edit.
Add `candidate_articles` with full text and the existing ID/URL/snapshot/hash fields,
and distinguish `topic_candidate`, `supporting_reference` and
`exact_generation_source_verified=false`. Include original/current QA unchanged.
Do not copy these assessment verdicts into blind reviewer prompts.

The source-aware reviewer should first reject homonyms, establish entity and date
scope, and then separately label each material claim as supported, contradicted,
not evidenced, source-disputed or time-dependent with literal offsets. Lack of a
local article is unresolved evidence, not a false-answer proof. Different article
dates must not be silently treated as the generation-time snapshot. Do not restore
unsafe or internally inconsistent source claims just to maximize source fidelity.

For the next calibration, include the Chinvali role reversal, the inherited Auslas
axis, Antakalnis's four-versus-five conflict, and the three failed-topic retrievals.
These test source use versus blind copying. Preflight the successor's full native
31B messages before launch: retaining every unrelated search hit could waste or
exceed context. Select justified full articles, or use explicitly separate complete
article review requests with a coverage ledger; never silently truncate evidence.
No successor model queue was prepared or launched by this pilot.

## Reproduction

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
# A build refuses to overwrite an existing index. Use a new root to rebuild.
$PY -m dfm12.baltic_article_lookup build --root "$NEW_ROOT" \
  --sources data/dfm13/baltic/local-sources.json
$PY -m dfm12.baltic_article_lookup pilot --root "$NEW_ROOT" \
  --packets data/dfm13/baltic/publication-holds/qa-source-fidelity-20261003-v1/calibration-requests.jsonl \
  --queries data/dfm13/baltic/article-lookup-diagnostic20-20261003/queries.json
```

Two focused tests cover full-text preservation, language filtering, title/body
query distinction, prefix matching, source hash checks, snapshot metadata and
refusal to overwrite an index. Retrieval-index implementation tests are not
semantic validation of the whole corpus.
