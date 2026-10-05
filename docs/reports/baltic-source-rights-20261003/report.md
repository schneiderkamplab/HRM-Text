# Baltic source rights: scoped release and remaining decision

2026-10-03. No GPU requests, queue resets, audit writes, server/process signals,
or original source modifications. Existing positive audits were reused. This is
a conservative evidence-based publication decision, not legal certification.

## FinePDF: two LT documents and one LV article released

The parquet schema has no document-license column; source candidate licenses are
null. The dataset's ODC-By notice is a database license, not permission for every
document. Full source rows and original publisher PDFs were inspected separately.

| Exact document | Primary evidence | Existing audit outcomes |
|---|---|---|
| GAMLEC Lithuanian game rules, V04, Sylvie Schoch / consortium | Publisher PDF page2 explicitly applies CC BY4.0 to the work; same notice in pinned original parquet text | Four accepted tasks |
| CEMIVET Lithuanian VET factsheet | Publisher PDF page1 explicitly applies CC BY4.0; same notice in original parquet | Three accepted; reordering rejected, excluded |
| Brivere and Levinska, Latvian history escape-games article, DOI10.17770/er2021.1.6497 | Original publisher PDF page1 explicitly applies CC BY4.0; exact source URL/ID/ordinal and article identity checked | Denoising and prefix accepted; other two tasks excluded |

Primary documents:
- [GAMLEC PDF](https://gamlec.eu/wp-content/uploads/2021/07/GAMLEC_Z%CC%8CaidimoTaisykle%CC%87s.pdf)
- [CEMIVET PDF](https://cemivet.eu/wp-content/uploads/2022/08/Factsheet-for-the-VET-schools-and-teachers_LT.pdf)
- [Latvian article PDF](https://journals.rta.lv/index.php/ER/article/download/6497/5538)
- [Article attribution/DOI](https://journals.rta.lv/index.php/ER/article/view/6497)

The browser PDF endpoint failed for the LV article, but a normal direct HTTP GET
returned200/application-pdf; pypdf verified its page-one notice. No access bypass.
Notably, FinePDF extraction omitted that license footer. Publisher-wide openness
or the paper's presence on an academic domain was not used as a substitute.

All three permit adaptations under their explicit [CC BY4.0 terms](https://creativecommons.org/licenses/by/4.0/legalcode.en).
The separate [ODC-By database terms](https://opendatacommons.org/licenses/by/1-0/)
and FinePDF attribution are retained. Full licenses, original rights-bearing PDFs,
source/author attribution, modification notices and exclusions accompany each
package. These grants are exact-document only, not domain or language approval.

### Actual publication

| HF repository suffix under `schneiderkamplab/` | Rows | Tokens | Revision |
|---|---:|---:|---|
| dfm13-wave3-finepdfs-lt-exact-ccby-v1-denoising | 2 | 4,789 | 483dd2568ae064919cce5169d640994dd6a9e960 |
| dfm13-wave3-finepdfs-lt-exact-ccby-v1-paragraph-reordering | 1 | 3,220 | 25dca7321be06274e67a2765ccd6064a51a28133 |
| dfm13-wave3-finepdfs-lt-exact-ccby-v1-prefix-continuation | 2 | 2,426 | 21067cf396db0ee85e8ee3a2fb4b30ea227f5b74 |
| dfm13-wave3-finepdfs-lt-exact-ccby-v1-span-filling | 2 | 2,431 | 583cbd3936ac6ebb06af11ceeb75d8bf5bc40a42 |
| dfm13-wave3-finepdfs-lv-exact-ccby-v1-denoising | 1 | 3,374 | 2b7d3f1a7fb96c7c25ee30dad7f210adf9109450 |
| dfm13-wave3-finepdfs-lv-exact-ccby-v1-prefix-continuation | 1 | 1,704 | 8bfefb1ad9647c92122b67d9ec7db90ba9ef6b71 |

**9 rows,17,944 actual tokenizer tokens;74 remote attachment hashes verified.**
Six registry entries are `accepted_uploaded`; the existing CPU watcher completed
tokenization. `verified-handoff.json` independently compares all nine messages
and original provenance with sealed candidates and checks tokenizer receipts.
No broad hold was cleared. No empty rejected-task package was invented.

Preparation roots:
`exports_dfm13/finepdfs-exact-ccby-20261003-v1` and
`exports_dfm13/finepdfs-lv-exact-ccby-20261003-v1`.
LT:53,744 scanned candidates,53,736 rights-unverified exclusions,7 accepted,
1 audit exclusion. LV:48,756 scanned,48,752 rights-unverified exclusions,2 accepted,
2 audit exclusions. These are source-candidate counts, not a population estimate
of infringing documents or quality failures. Other positive audits remain preserved.

### Excluded rights patterns

SANS/OUCH examples explicitly use BY-NC-ND terms: not admitted. Other examples
merely discuss CC images or attach a CC notice to one image, not the whole text.
Several education/IASC documents carry NC or NC-SA terms; they are not included
under an unrelated prior Matina/TLPC approval. The large remainder is unassessed
at document level, not affirmatively judged restricted. No automatic CC regex
admission was implemented.

## Europarl LT/LV: evidence supports reuse, scope not cleared

Both local OPUS v8 archives were inspected. Their LICENSE files defer to original
source terms; they do not grant CC/public-domain rights. Archive hashes and
README/LICENSE files are preserved in `evidence-europarl/`. The current
[European Parliament legal notice](https://www.europarl.europa.eu/legal-notice/en)
was captured successfully by normal HTTP GET. It permits attributed reuse,
including commercial redistribution, with an additional complete-item/source-page
link for partial reproduction; item-specific conditions and retained source
indications still matter. It is not an explicit general CC adaptation license.
The [Europarl producer page](https://www.statmt.org/europarl/) identifies the origin
and requests citation but its lack of known restrictions is not an affirmative
grant beyond the original terms.

The pinned records are grouped sitting text with `license:null`. LT row URLs link
to the whole OPUS archive; LV row URLs link to the generic corpus homepage.
Neither is currently a verified per-sitting Parliament attribution link.
Attempts to inspect two corresponding official sitting pages returned202/empty
or browser challenge, not a usable item-specific terms/content verification.
No anti-bot or download restriction was bypassed. Candidate inputs deliberately
alter text for denoising/reordering; their applicability under the general reuse
notice should not be assumed from permission to reproduce an excerpt.

**No Europarl data was published or re-audited.** LT54,503 and LV63,450 audit-ready
rows remain untouched. The narrowest next release scope is unchanged prefix text:
LT19,081 and LV19,172 candidates (38,253 before existing positive-audit filtering).
The other79,700 candidates remain outside that proposed narrow scope.

**Bounded decision:** should the first Europarl release be restricted to verbatim
prefix-continuation excerpts, with complete-sitting links and attribution verified
before publication, leaving the other three task families held; or should the
project first obtain explicit clarification covering the deliberately altered
exercise forms? A project inclusion decision is not itself a grant of third-party
rights. No request to the rights holder was sent and no blanket approval was made.

## Implementation and checks

`dfm12/finepdf_rights_subset.py` reuses repository IO/hash/lock helpers, the exact
audit payload identity and strict audit validator. Whitelists bind document ID,
source file hash, row ordinal, URL, language and independently captured evidence.
Only completed exact positive original audits pass. Missing/changed/pending/
rejected audits cannot become raw acceptance. Full original messages are retained.
Builds use fresh atomic staging; source archives/queues/ledgers are read-only.
Publication checks local pins, verifies every returned HF attachment at the exact
commit, then updates only the six named entries under the registry lock. Existing
tokenization fields survive a same-content publication rerun.

15 focused tests pass;21 pass including existing BLKT publisher regressions.
Coverage includes exact-document versus domain grant, LT/LV separation, changed
provenance, bad scores, changed histories, absent evidence, remote hash failure
before registry admission and preserving unrelated registry entries.

Reproducible commands (build requires a fresh output root; published roots stay
immutable):

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m pytest -q tests/test_finepdf_rights_subset.py tests/test_dfm12_blkt_publish.py
$PY -m docs.reports.baltic-source-rights-20261003.verify
```

`capture.py`, `capture_lv.py` and `capture_europarl.py` record the bounded primary
evidence. Frozen evidence roots must not be overwritten. Further expansion needs
new document-specific evidence and a new scoped version, not a relaxed domain rule.
