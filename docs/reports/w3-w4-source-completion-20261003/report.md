# W3/W4 source completion audit

Snapshot: **2026-10-03 19:13 UTC**, rolling metadata reads. Scope is the selected
inventory in `config/dfm13_baltic_sources.json`, `dfm12/wave4_cpu.py:SOURCES`,
native Wikipedia sources and requested translation meshes, not every exploratory
lead in research pages. No network probes, payload rehashes, GPU requests, queue
writes, resets or publication changes. `snapshot.json` contains source-specific
preflight counts, registry entries, metadata hashes and observed process commands.
`snapshot.py` reproduces this bounded metadata comparison from the repository root.
Registry publication/tokenization flags were inspected, not independently rehashed
or remotely reverified in this task. A prepared row is not an accepted row.

## Remaining external access blockers

| Source | Prepared / queued / published | Existing evidence and remaining work |
|---|---|---|
| MatinaAI/matina_persian_text_corpus | 0 / 0 / 0 | Last authenticated receipt: HTTP403, 17/17 payload files missing. Bounded local plan selects 11 files, all absent; 1,015,840,100 compressed bytes. |
| Targoman/TLPC | 0 / 0 / 0 | Last authenticated receipt: HTTP403, 62,593 non-card files missing. Bounded plan selects 64 site shards, all absent; 135,813,056 compressed bytes. |

Both source licenses are already owner-approved; the remaining blocker is account
access, not another approval request. The implemented local adapter still needs
real payload/schema validation after access exists. No active downloader is needed
while the gate remains unchanged. Existing DaLA/shared-cache investigation found
no verified authorized copy within its stated bounds. No repeated403 probe was made.
See `dfm13_persian_access_recheck_20261003.md`,
`dfm13_persian_local_preparation_20261003.md`, and
`dfm13_persian_local_copy_search_20261003.md` in the parent reports directory.

## Unfinished work not currently owned by a release process

| W3 source/component | Audit-ready rows | Current disposition |
|---|---:|---|
| Europarl_lt transforms | 54,503 | In original queue manifest, absent from registry and ordinary transform publisher allowlist; source redistribution/attribution review unresolved. |
| Europarl_lv transforms | 63,450 | Same. |
| baltic_lt_finepdfs transforms | 53,744 | In original queue manifest, absent from registry; underlying document rights screening unresolved. Database license does not settle individual document rights. |
| baltic_lv_finepdfs transforms | 48,756 | Same. |
| **Total** | **220,453** | Prepared/queued inventory, not a claim of 220,453 accepted rows. |

These are genuine remaining source-specific release-work items, not missing
downloads or forgotten preparation. No dedicated live release owner was found.
The current `BALTIC_TRANSFORM_COMPONENTS` publisher covers Wikipedia/ParlaMint,
not these four. The minimal next work is to resolve the existing source-specific
evidence requirements, then reconcile their actual terminal audit outcomes and
implement/enable scoped accepted-only publishers. Do not turn the old readiness
hold strings into automatic approval or repeat the GPU audits blindly.

## Zero-row and no-supply cases

- **Aya Albanian is covered:** the historical `sqi` component has zero rows, but
  `CohereLabs--aya_dataset-sq-tosk` selects 120 `als` train rows and publishes 113.
  Do not count the retained zero-row alias as an uncovered dataset.
- **BLKT paragraph reordering is genuinely unavailable under current structure:**
  60,000 attempts failed `not_enough_distinct_paragraphs`; zero reordering candidates.
  Its other three tasks publish 48,201 rows. Do not manufacture paragraph boundaries.
- **W3 translations:** all 43 requested pairs have candidate supply and all 43
  have published registry entries; 4,517,264 audit-ready candidate pairs in the
  existing manifest. Small supply is not missing coverage or a quota promise.
- **W4 base translations:** 308 requested pairs; 275 have supply, 33 Slovak edges
  have none in the original frozen mesh. Its 416 nonempty components are all
  registered. Existing exact-coverage receipt checked 6,269,371 rows, added zero
  jobs and reports complete coverage. This audit reused that evidence rather than
  repeating its whole-payload scan.
- **Slovak additive successor:** 30 nonempty components, 1,910,015 candidate pairs
  (784,241 direct EN-SK plus 1,125,774 pivots). Enqueue is still incomplete and
  actively owned; not a dropped-source gap. After combining its prepared supply
  with the base mesh, only **ca-sk, fo-sk, nn-sk** remain zero. These are genuine
  no-supply edges under the selected approved sources/exact-English joins, not
  proof no corpora exist. Further source discovery is needed to fill them; no
  repeat inflation, license relaxation or synthetic substitution is implied.

## Prepared and Published Source Counts

W3 registry: **69 packages**, 65 `accepted_uploaded`, four quality-held; all69
have tokenization recorded. Published-but-held is not eligible admission.

| W3 source | Audit-ready | Registry rows / state |
|---|---:|---|
| LT Aya | 910 | 802 accepted |
| LT QA | 13,841 | 12,895 published, source-fidelity hold |
| LV QA | 118,505 | 105,971 published, source-fidelity hold |
| LT summary | 2,012 | 1,740 privacy-reviewed accepted; old generic hold superseded |
| Latvian P3 | 20,204 | 7,680 across two license packages, source-fidelity hold |
| Baltic EuroBlocks | 179 | 166 accepted |
| LT Wikipedia / LV Wikipedia | 58,265 / 72,832 | 52,058 / 64,701 accepted across four tasks each |
| LT ParlaMint / LV ParlaMint | 58,265 / 59,781 | 53,759 / 53,317 accepted across four tasks each |
| LT BLKT | 51,510 | 48,201 accepted across three tasks; terms/evidence publisher completed |

W4 registry: **96 packages**, all `accepted_uploaded` and tokenization recorded:
44 Wikipedia task packages, 15 instruction packages, 37 translation packages.
Translation publication is live, so this count is a snapshot, not final coverage.

| W4 instruction component | Audit-ready | Published rows |
|---|---:|---:|
| Croatian canonical | 455 | 448 |
| Aya FA / HU / SR / SQ-tosk | 1,567 / 98 / 152 / 120 | 1,490 / 83 / 136 / 113 |
| EuroBlocks BG / HR / HU / SK / SL | 261 / 51 / 4,227 / 874 / 197 | 245 / 48 / 3,984 / 859 / 185 |
| Kapibara SQ | 4,581 | 4,124 |
| LuxIT LB | 46,070 | 42,138 |
| Fars farstail / parsinlu_comp / persian_qa | 7,266 / 600 / 6,299 | 7,140 / 581 / 6,236 |
| Fars pn_sum / wiki_sum | 82,022 / 45,584 | Not published by current finalizer; source-fidelity holds |

| W4 Wikipedia | Audit-ready | Current published rows, four tasks combined |
|---|---:|---:|
| BE | 240,707 | 211,603 |
| BG | 291,316 | 259,730 |
| BS | 131,530 | 111,348 |
| FA | 291,316 | 234,956 |
| HR | 240,203 | 203,247 |
| HU | 291,316 | 248,822 |
| LB | 66,042 | 56,636 |
| SK | 208,469 | 177,562 |
| SL | 220,758 | 187,569 |
| SQ | 105,668 | 88,935 |
| SR | 291,316 | 254,288 |

FA/HR/SL/SQ/SR values reflect current corrected registry subsets, not old exports.
No selected nongated instruction or Wikipedia source lacks preparation coverage.
Research-only alternatives such as NAAB, PerSpellData or the Latvian source-map
repository are not silently promoted to approved work, nor declared completed.

## Already Owned or Staged Work

Observed live owners: main W4 audit2032197 and booster2111441; W4 selection2143812;
W4 translation publisher2143813; W3 translation publisher2121810; tokenizer2134027;
W4 transforms2355940 and instructions2365731; Slovak additive2542233 and completion
watcher2520116. Repair-audit workers turn over; the exact current command/PID is
captured in `snapshot.json`. No process was signaled or duplicated.

QA/P3/Fars quality holds and synthetic generation are **unfinished, explicitly
tracked work**, not external-access blocks or permission to bypass the reviewer:
the Baltic article-aware QA consumer has118,866 cases preflighted,118,369
dispatchable and497 context-unresolved. Fars final preflight covers89,296
original+delta requests (77,640 original plus11,656 delta), not final keeps.
The31B QA/Fars/synthetic successors are staged for the coordinated model handoff;
no matching live consumer process was found during this check. Old LV synthetic
7,626 automated keeps remain quality-held; they are not published acceptance.
Preserve these owners/handoffs rather than starting duplicate consumers.

**Bottom line:** two genuine gated-source access blockers; four known Baltic
rights/release-work items with no live publisher; three remaining Slovak
no-supply edges. The much larger W4 translation and31B quality/synthetic backlogs
are already tracked, not undiscovered datasets. No new authorization prompt or
operational change was made.
