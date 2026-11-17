# Changelog

## Unreleased (on main)

Main has the same data as v0.2.6.

Repository history (2026-10-22): after `sejm_interpellations` and
`kultura_bez_barier_pl` came off main, main's history was squashed again and
the open pull requests were rebuilt on it. The `v0.2.6` tag was re-pointed to
the squashed commit, whose data files are byte-identical to those of its
previous target, d74eda1; the tag message records that target. The release
tags `v0.2.0`-`v0.2.5` were deleted: they held data that v0.2.6 withdrew or
changed. Their figures and notes stay in this file and in the README. The
scripts whose inputs were only in those tags (`clean_biblioteka_nauki`,
`clean_eurlex`, `clean_govpl`, `clean_wolne_lektury`, `clean_global_voices`,
`clean_sejm_api`, `build_eltec_pol_attribution` and `clean_1000_novels`) stay
as the record of how v0.2.6 was built; their pins record which files a rerun
needs, and a pin mismatch now says the input is no longer published.

Held off main (`release: None`, no data on main): `sejm_interpellations`,
planned for v0.2.7, `kultura_bez_barier_pl`, until the scope of its licence is
answered, and `uzp_orzeczenia_pl`, v0.2.8 at the earliest (see "Removed from
main" under v0.2.6).

Release plan: v0.2.7 follows the NERGAL personal-data pass, which runs on every
source. `uzp_orzeczenia_pl` and any re-admission of `samorzad_gov_pl` or
`1000_novels` wait for v0.2.8 at the earliest.

## v0.2.6 (2026-10-22)

27 sources, 3,394,876 documents / 7,036,938,603 cl100k-proxy tokens. v0.2.6
ships before the NERGAL personal-data pass: only each source's own filters
apply (see its datasheet), and the pass runs on every source before v0.2.7.
`sejm_interpellations` and `kultura_bez_barier_pl`, both held off main, are
not in this release (see Unreleased). The README's "Changes since v0.2.5"
section at the `v0.2.6` tag has the per-source details.

Added: 12 sources, 1,097,821 documents / 637,130,408 tokens.

- `plwiki_user_talk` by Piotr Styła: 380,295 documents / 381,015,336 tokens (Hub PR #40).
- `sejm_committee_transcripts` by Piotr Styła: 613,722 documents / 112,003,155 tokens (Hub PR #37).
- `plwiki_talk` by Piotr Styła: 43,054 documents / 55,564,235 tokens (Hub PR #36).
- `ted_pl` by Piotr Styła: 14,210 documents / 39,580,791 tokens (Hub PR #32;
  rebuilt on 2026-10-22 to keep only notices whose TED buyer legal type is a
  public authority, a body governed by public law or a public undertaking,
  removing 1,320, and to remove 14 notices that reproduce third-party text:
  5 sharing a textbook passage, then 9 found by a model screen of every notice,
  two review passes per flag and a same-template search).
- `sejm_api_2011_2022` by Piotr Styła: 33,930 documents / 26,868,517 tokens (Hub PR #18).
- `nonsa` by Piotr Styła: 11,692 documents / 15,439,683 tokens (Hub PR #41).
- `studia_bas` by gzawadzki (Hub PR #19, landed by Piotr Styła): 112 documents / 2,256,009 tokens (Hub PR #44).
- `wiadomosci_statystyczne_pl` by Piotr Styła: 169 documents / 1,506,269 tokens (Hub PR #35).
- `rock_pollub_pl` by Piotr Styła: 8 documents / 1,177,858 tokens (Hub PR #33).
- `edukacja_medialna_pl` by Piotr Styła: 248 documents / 713,052 tokens (Hub PR #26).
- `open_agh_chemistry_pl` by Piotr Styła: 370 documents / 564,028 tokens (Hub PR #25).
- `open_icm_pl` by Piotr Styła: 11 documents / 441,475 tokens (Hub PR #34).

Changed: the 15 v0.2.5 sources kept total 2,297,055 documents / 6,399,808,195
tokens.

- `eurlex` is relabelled `LicenseRef-EU-Reuse-Policy` (the EUR-Lex notice grants
  CC BY 4.0 only for consolidated texts and editorial content); 572 documents
  with third-party material are dropped, and `eurlex.attribution.jsonl` gives
  each row its EUR-Lex link. 242,488 documents / 2,333,038,468 tokens (Hub PRs
  #71, #82, #173, #177).
- `parliamentary` is rebuilt from IPI PAN's speaker-labelled TEI dump: only
  official speakers are kept in the sittings and exact copies are dropped. The
  System Informacyjny Sejmu credit is given for its Sejm material as a
  precaution. 329,863 documents / 1,504,127,614 tokens (Hub PRs #108, #111).
- `wikipedia` is rebuilt from the official plwiki dump, replacing the
  SpeakLeash snapshot; each record is labelled by its contribution dates, and 42
  pages with a copyright-violation notice or deleted for one are dropped.
  1,468,647 documents / 1,226,906,115 tokens (v0.2.5: 1,171,897 documents; Hub
  PRs #68, #128, #148).
- `biblioteka_nauki` records carry the licence version and basis the Biblioteka
  Nauki API gives for each; 3 Public Domain Mark records and 4,142 rows are
  dropped after review. 37,843 documents / 590,924,796 tokens (v0.2.5: 42,071;
  Hub PRs #62, #81, #186).
- `dziennik_ustaw` no longer claims Monitor Polski, gains an ELI-address
  sidecar and gives the System Informacyjny Sejmu credit as a precaution; text
  and counts are unchanged: 35,442 documents / 486,126,575 tokens (Hub PRs
  #103, #160, #162).
- `wolne_lektury` is relabelled per document from its book's own licence, with
  credits in `wolne_lektury.attribution.jsonl`; 67 documents are dropped, 174
  are held out until their books' contents are checked, and the author's and
  translator's notes are added to 459 texts. 5,900 documents / 91,715,560
  tokens (Hub PRs #67, #99, #184, #188, #190, #191).
- `govpl` drops 188 PAP reprints, 186 other third-party texts and 12,870 press
  releases of prosecutor's offices. 74,946 documents / 68,291,645 tokens
  (v0.2.5: 88,190; Hub PRs #63, #170, #214).
- `sejm_api` cuts the "Przebieg posiedzenia" trailers, puts the 2,466
  statements they appended into rows of their own and drops 123 rows by
  speakers outside its allowlist. 39,776 documents / 30,637,660 tokens
  (v0.2.5: 38,812; Hub PRs #83, #158).
- `eltec_pol` adds author metadata and an attribution sidecar and restores the
  chapter titles. 100 documents / 21,504,056 tokens (Hub PR #187).
- `wikibooks` withholds 54 pages; each record is labelled by its contribution
  dates and the licence of imported text, and markup residue is removed. 9,041
  documents / 15,220,800 tokens (v0.2.5: 9,112; Hub PRs #127, #134, #139, #142,
  #147).
- `wikivoyage` withholds 6,330 pages, 6,326 of them text from Wikitravel; each
  record is labelled by its contribution dates, and markup residue is removed.
  7,312 documents / 14,084,102 tokens (v0.2.5: 13,645; Hub PRs #125, #133,
  #138, #141).
- `wikinews` withholds 1 page; each record is labelled by its contribution
  dates and the licence of imported text, and markup residue is removed. 23,572
  documents / 10,968,504 tokens (v0.2.5: 24,386; Hub PRs #77, #130, #132, #137,
  #146).
- `global_voices` drops 114 posts republished from partner outlets. 1,926
  documents / 3,453,918 tokens (v0.2.5: 2,040; Hub PR #66).
- `nkjp1m` is relabelled `CC-BY-4.0` per the NKJP Consortium, with an agreed
  `ATTRIBUTION.md`; text unchanged. 18,381 documents / 2,601,201 tokens (Hub PR
  #51).
- `wiktionary_examples` drops the lines quoting third-party works and is
  relabelled per record `CC-BY-SA-3.0`, `CC-BY-SA-4.0` or both, by contribution
  date. 1,818 documents / 207,181 tokens (v0.2.5: 8,639; Hub PR #50).

Withdrawn: 5 v0.2.5 sources, removed from main and, on 2026-10-21, from every
release tag that held them.

- `european_hplt_v3_pl` (1,603,974 documents / 2,555,525,652 tokens in
  v0.2.4 and v0.2.5) was removed by Arkadiusz Słota because its licence is
  unverified; it will not be re-added. The registry keeps its
  `release: "0.2.3"` entry and `make_docs.py` skips it (no stats file).
- `wikiquote` (30,363 documents / 31,896,591 tokens in v0.2.0-v0.2.5) was
  removed on 2026-10-05. The October rights audit labelled 158 of 200 randomly
  sampled pages as quoting works still in copyright; CC BY-SA covers the
  contributors' selection, not the quotes, which rest on the Art. 29 quotation
  right. As with HPLT, the registry keeps its `release: "0.2.0"` entry (with a
  `legal_note`) and `make_docs.py` skips it; `plwikiquote` was dropped from
  `src/fetch_wikimedia.py`.
- `wikisource` (632,005 documents / 801,947,427 tokens in v0.2.0-v0.2.5) was
  removed on 2026-10-05. Every row carries one CC-BY-SA-3.0 label, but the
  October rights audit found in-copyright post-war imprints among 12 checked
  rows, each released by its rights holder under its own per-page licence (CC
  BY 3.0 PL, CC BY-SA 3.0 PL, CC BY-SA 3.0, GFDL, CC BY 4.0) and needing
  attribution the rows lack. The data came through SpeakLeash with an
  undocumented selection and no title, author or page id, so it cannot be
  screened. The registry keeps its `release: "0.2.0"` entry with a
  `legal_note`, and its `traceable` text no longer claims every text is public
  domain. A rebuild from the official dump with per-page licences is planned
  for a later release.
- `samorzad_gov_pl` (Dawid Majewski, Hub PR #15, rebuilt as #46; 72,771
  documents / 41,154,506 tokens in v0.2.5) was removed on 2026-10-17 (Hub PR
  #123). Its CC BY-SA 4.0 is declared by the platform operator (KPRM) in the
  shared footer, but the texts are written by 247 publishing institutions. The
  operator's agreements with them are unpublished, no grant from them was
  found, and KPRM has not answered the question sent on 2026-10-06. Main held
  72,328 documents / 39,890,244 tokens. The registry keeps its
  `release: "0.2.5"` entry with a `legal_note`, and
  `src/clean_samorzad_gov_pl.py` stays for a re-admission.
- `1000_novels` (1,000 documents / 60,517,363 tokens in v0.2.5; released from
  v0.2.1) was removed on 2026-10-17 (Hub PR #124). The per-text screen shows
  each author and translator died in 1955 or earlier, but no row records the
  edition its text follows, so a protected preface, abridgement or editor's
  corrections cannot be ruled out. Main held 221 documents / 10,759,728
  tokens, what was left after the rights screen (Hub PRs #49, #55) and the
  dedup against `wolne_lektury` and `eltec_pol`. The registry keeps its
  `release: "0.2.1"` entry with a `legal_note`, and `src/clean_1000_novels.py`
  stays for a re-admission.

Removed from main before this release, never released:

- `fandom_pl` (Piotr Styła, Hub PR #48; 50,653 documents / 45,790,009 tokens
  from 12 wikis) was removed on 2026-10-05. Fandom's Terms of Use (revision
  2025-12-19) bar scraping, bypassing robot exclusion and AI training without
  written consent; the pages were fetched live from the wikis' APIs on
  2026-10-02. Samples also showed game text, lyrics and translated third-party
  stories under the CC BY-SA label. The registry entry, builder, test and
  ontology manifest were removed with the data.
- `openstax_pl` (Piotr Styła, Hub PR #23; 1,422 documents / 4,632,374 tokens)
  was removed on 2026-10-05. OpenStax Poland's live prefaces allow only
  non-commercial reuse and bar LLM training without its written consent, and
  its CMS lists the eight books as CC BY-NC-SA 4.0; the fetcher had hard-coded
  CC BY 4.0. The registry entry, fetcher, test and ontology manifest were
  removed with the data.
- `common_voice_pl` (Piotr Styła, Hub PR #22; 45,043 documents / 994,922
  tokens) was removed on 2026-10-05. CC0 is Common Voice's platform-level
  label: 24,709 of the sentences come from Europarl, whose European Parliament
  reuse notice requires source acknowledgement, which CC0 cannot carry, and the
  Sentence Collector sentences have no recorded sources. The registry entry,
  fetcher, contract test, ontology manifest and language audit were removed
  with the data.
- `uzp_orzeczenia_pl` (Piotr Styła, Hub PR #39) was removed from main on
  2026-10-21 until v0.2.8. Main held 34,715 rulings / 420,753,012 tokens after
  the G1 personal-data pass (Hub PR #193). That pass leaves part of the sole
  traders' firm names and addresses unmasked, and its second round of rules
  has not met its bar on the held-out sample. The registry keeps its
  `release: None` entry, and `src/build_uzp_orzeczenia_pl.py`, its tests and
  the ontology manifest stay for v0.2.8; the legitimate-interest note moves to
  `artifacts/uzp_orzeczenia_pl_legitimate_interest.md`. All three versions of
  the shard were then deleted from the repository's storage on 2026-10-21, so
  downloading it at any older revision fails with HTTP 403.
- `sejm_interpellations` (Paweł Puzio, Hub PR #24; 25,950 documents /
  28,180,895 tokens) was removed from main on 2026-10-22 until v0.2.7. It
  quotes letters from the public, some with health details, and only the
  pre-NERGAL regex scrub has run on it. Its data folder (shard, attribution
  sidecar, licence evidence, stats and datasheet) comes back with the shard.
  The registry keeps its `release: None` entry, and
  `src/fetch_sejm_interpellations.py`,
  `src/build_sejm_interpellations_attribution.py` and the tests stay; the tests
  skip while the folder is missing.
- `kultura_bez_barier_pl` (Piotr Styła, Hub PR #27; 7 documents / 126,743
  tokens) was removed from main on 2026-10-22 until the scope of its licence is
  answered: the catalogue's CC BY-SA 3.0 statement may cover only the
  foundation's accessibility pictograms, not its publications. Its data folder
  (shard, sample, attribution, decisions, review table, licence-basis evidence,
  QA, stats, datasheet and NOTICE) comes back with the answer. The registry
  keeps its `release: None` entry, and `src/build_kultura_bez_barier_pl.py`,
  `src/clean_kultura_bez_barier_pl.py`, `src/licence_basis_kultura_bez_barier_pl.py`,
  their tests and `artifacts/kultura_bez_barier_pl_ontology_manifest.json` stay;
  the tests skip while the folder is missing.

Documentation:

- `LICENSE` now says the collection licence (CC BY-SA 4.0) covers the
  selection, arrangement and our metadata, to the extent of our rights, and
  that each document keeps the licence or status in its `license` field.
- Token counts are a tiktoken (cl100k) proxy; the datasheets no longer claim a
  Llama-3 count.
- SpeakLeash is credited where text still comes through its redistribution
  (`eurlex`, `wolne_lektury`, `biblioteka_nauki`), not as the source of the
  whole collection.

Tooling and process:

- PII scrubbing moved out of the repo to SlayerLab/NERGAL (Hub PR #38);
  contextual PII masking improvements (Hub PR #28).
- Releases are tagged (Hub PR #31).
- Source PRs are separate from releases; `src/render_sample.py` renders PR data
  samples (Hub PR #42).
- `build_dynaword.py` gained `preserve_id` / `preserve_created` flags (Hub PR
  #45).
- `src/make_docs.py` no longer renders the README from a template. It
  refreshes the generated blocks of the hand-written README (the stable line of
  the header, the current release's counts, the Sources and Excluded tables
  and Results) and fails if one is missing; `src/test_make_docs.py` checks that
  the committed README is what it renders.
- The `v0.2.5` tag was re-pointed on 2026-09-29 from 02bcb0b to f71cc09, which
  corrects the v0.2.5 documentation to 20 sources, and on 2026-10-01 to
  7ae4ac7, which moves the 1000 Novels rights warning into its datasheet.
  Every Parquet file is byte-identical between the three commits.
- On 2026-10-21 every release tag was re-pointed to a new commit: its previous
  target minus the data folders of the sources withdrawn from main since
  (`wikiquote` and `wikisource` from v0.2.0, `1000_novels` from v0.2.1,
  `european_hplt_v3_pl` from v0.2.3, `samorzad_gov_pl` from v0.2.5). Every
  other file is byte-identical, so each tag's README and stats files still
  describe the release as published. Previous targets: v0.2.0 0538a97, v0.2.1
  7f60607, v0.2.2 87f5bc4, v0.2.3 79dc2b0, v0.2.4 11dcb9f, v0.2.5 7ae4ac7; each
  tag's message records its previous target and message. The withdrawn
  sources' LFS files (32 files, 7.78 GB, 5 of them held only by merged pull
  requests) were then deleted from the repository's storage, so downloading
  one at any older revision fails with HTTP 403.
- On 2026-10-22 main's history was squashed into one commit with the same
  tree, and the open pull requests were rebuilt on it. Commit ids from before
  then that no release tag reaches are no longer in a clone (some stay
  reachable only through the refs of closed pull requests); the tags
  v0.2.0-v0.2.5 were unchanged by it (they were deleted later; see
  Unreleased). The ontology manifests (`target_revision`,
  `VALIDATED_AGAINST`, `payload_uri`), the findings and the audit logs keep
  such ids as records, as do the two `src/licence_basis_*.py` scripts, whose
  bytes the manifests pin. The other scripts and datasheets now restore their
  inputs from a release tag or `main`; where the input was only in main's
  history, it predates the October 2026 rights audit and is no longer
  published, and the pins record which files a rerun needs.

## v0.2.5 (2026-08-14; tagged 2026-09-07)

- The v0.2.5 release has 20 sources (the tag was deleted after the October
  2026 rights audit; see Unreleased): `samorzad_gov_pl`, `sejm_api` and
  `wiktionary_examples` were added in this release. `sejm_api` and
  `wiktionary_examples` were previously documented as built but not released
  (`release: None` in `src/sources.py`); that was a documentation error, and
  the registry now sets `release: "0.2.5"` for both.
- Added `sejm_api` by Piotr Styła: 38,812 parliamentary-speech documents
  (2023 onward) / 36,335,587 cl100k-proxy tokens from the official Sejm API,
  `public-domain (official documents)` (Hub PR #16).
- Added `wiktionary_examples` by Katarzyna Majzel-Pośpiech: 8,639 Polish
  Wiktionary usage-example documents / 1,115,820 cl100k-proxy tokens,
  `CC-BY-SA-3.0` (Hub PR #14).
- Added the community contribution `samorzad_gov_pl` by Dawid Majewski
  (`dawidmajewski`): 72,771 Polish articles / 41,154,506 cl100k-proxy tokens
  from 246 local public institutions and one central platform tenant using the
  shared samorzad.gov.pl platform.
- Converted the published, directly collected source dataset at revision
  `d5eaefc32c3f17cfa5a01d14573f8e4ee7d43385`; retained 72,771 of 81,422
  records after dropping 6,624 short, 35 below the Polish-language heuristic
  and 1,992 exact-duplicate records.
- Preserved the human-readable publishing institution in every `author` value.
  Added a 72,771-record attribution sidecar with discovered source URLs,
  fetched final URLs, recommended attribution URLs, titles, institution names,
  license URLs and modification notices.
- Added the frozen 247-institution publisher manifest, reproducible conversion
  script, contract tests, source datasheet, NOTICE and release-time license
  evidence. The live shared footer script matched the audited SHA-256
  `b36ec507901ed443195479d8d8009386159ae59d7486ce266bfb3308043e99aa`.
- Recomputed complete-corpus totals: 4,366,651 documents and 9,676,513,980
  cl100k-proxy tokens across 20 sources (earlier drafts of this entry gave
  4,319,200 documents / 9,639,062,573 tokens across 18 sources, before
  `sejm_api` and `wiktionary_examples` were counted).

## v0.2.4 (2026-08-07)

- Expanded `european_hplt_v3_pl` (Arkadiusz Słota / `Maggio33`) from HPLT v3.0
  WDS quality bins 10+9 to **WDS bins 10-5**: +1,493,384 documents /
  2,043,141,874 cl100k-proxy tokens, 100% CC0-1.0. The source total is now
  1,603,974 documents / 2,555,525,652 tokens.
- Phone PII-scrub hardening (v12b): an independent-lens deep verification caught
  a systematic phone recall-gap (~1,900 real phone numbers) that the pipeline's
  self-report (idempotency) was structurally blind to — address-block
  suppression, `dzwoń`-label family, leading-0 landline, `+48`-paren,
  newline-over-span and foreign-UK-bare formats. Fixed and dual-independently
  verified; the residual 0.0135% is a classified clearance-tail. Phones map to a
  `[Telefon]` semantic tag (anti-poisoning, not a fake number).
- Cross-source deduplication of the expansion against the existing WDS-10+9
  shards: removed 3,038 near-duplicate documents (truncation variants);
  exact-dup 0, near-dup overlap 0.0000% (byte-verified). Resolves the
  "downstream near-dedup remains" caveat from the original release.
- Contract-revalidated the merged parquet (canonical schema, non-empty text,
  positive token counts, uniform source/license, stats-file consistency).
- Expanded contributor credit for Arkadiusz Słota (`Maggio33`) for the WDS 10-5
  expansion, PII-scrub and dedup work.
- Updated the complete-corpus release totals from per-source parquet stats:
  4,246,429 documents and 9,597,908,067 cl100k-proxy tokens across 17 sources
  (also reflects the separately-merged `biblioteka_nauki` source now present on
  main).

## v0.2.3 (2026-07-26)

- Added the community contribution `european_hplt_v3_pl` by Arkadiusz Słota
  (`Maggio33`): HPLT v3.0 Polish WDS quality bins 10+9, 110,590 documents and
  512,383,778 cl100k-proxy tokens under CC0-1.0 packaging.
- Added the reviewed `global_voices` contribution by Dawid Majewski
  (`dawidmajewski`): 2,040 documents / 3,715,020 tokens with CC-BY-3.0 and
  per-document author attribution metadata.
- Added `nkjp1m` from contributor `1am`: 18,381 documents / 2,601,201 tokens
  from the manually annotated 1-million-word NKJP subcorpus under the upstream
  version-unspecified CC-BY statement.
- Revalidated the contributed parquet against the canonical schema, non-empty
  text, positive token counts, uniform source/license metadata, and stats-file
  consistency.
- Updated the complete 16-source release totals from per-source parquet stats:
  2,710,974 documents and 6,881,277,362 cl100k-proxy tokens.
- Recomputed the full-corpus phrase-frequency report and charts. Updated the
  Arrow reporting path to use 64-bit string offsets for large row groups.
- Fixed `src/test_hplt_v3_contract.py` to resolve its fixture relative to the
  repository instead of a contributor-local Windows path.
- Added public contributor credit for Arkadiusz Słota (`Maggio33`) and Paweł
  Puzio (`ppuzio`, author of the `govpl` contribution released in v0.2.2), plus
  Dawid Majewski (`dawidmajewski`) for Global Voices Polish.
- HPLT caveat: CC0 applies to the HPLT packaging; underlying web documents can
  carry independent rights. Downstream near-dedup and web-content review remain
  recommended before training.

## v0.2.2 (2026-07-19)

- Added `govpl` — gov.pl Polish government press releases (CC-BY-SA-4.0),
  88,190 documents / 80.7M tokens, fetched directly from gov.pl across 133
  ministry/agency subsites. New scripts: `src/discover_govpl.py` (discovers each
  subsite's news-section path into the committed `src/govpl_subsites.json`
  manifest) and `src/fetch_govpl.py` (pure-stdlib crawl of that manifest).
- Stable totals after adding govpl: 13 sources, 2,579,963 docs, 6.36B tokens
  (tiktoken proxy).
- Article date range 2005-09-26 → 2026-07-19. Build dropped 24 non-Polish and
  deduped 1,926 cross-posted articles (exact sha1).

## v0.3.1-preview (2026-07-10)

- Added a separate 810-document Europeana direct-ingestion preview parquet at
  `previews/v0.3.1/europeana.parquet`. It was built from 1,000 live API records
  using per-record rights/creator metadata in 59.4 seconds; 808 retained records are Public
  Domain Mark and two are CC-BY-SA-4.0.
- The direct source gate dropped 181 non-Polish and nine OCR-garble records.
  `dsbench` found unique IDs, no empty text, no duplicate text and no eval-set
  overlap. Potential-phone matches remain warnings for manual review.
- This preview does not change v0.2.1 stable totals or promote Europeana to a
  stable source. It is the measured contract for the full rights-preserving run.

## v0.3.0-preview (in progress)

- Validated the source-policy gate on live local SpeakLeash shards: 12 reviewed
  sources sampled and cleared blocking checks; four sources remain excluded and
  two talk-page shards remain on hold pending a separate policy.
- Ran a direct Europeana 200-record rebuild probe with per-record rights and
  creator metadata: 197 Public Domain Mark and three CC-BY-SA-4.0 records
  cleared blocking validation. This is candidate validation, not a release
  inclusion.
- Biblioteka Nauki direct probe currently returns HTTP 500 and is held out of
  the preview until the upstream request is repaired and audited.

## v0.2.1 (2026-07-02)

- Released a stable metadata-schema update: `id, text, source, added, created, token_count, license, author`.
- Current release totals after parquet recount: 12 sources, 2,491,773 docs, 6.28B tokens (tiktoken proxy).
- Added `1000_novels` as a stable CC-BY-4.0 literature source.
- Added source registry entries and PR contract for future `biblioteka_nauki` and `europeana` ingestion with per-document license/author metadata. These sources are not included in v0.2.1 parquets yet.
- Credited Bart Kobyliński for source expansion work on Biblioteka Nauki and Europeana metadata/rebuild preparation.
- Kept raw SpeakLeash Europeana excluded unless a direct rebuild preserves per-record rights metadata.
- Sources: eurlex, parliamentary, wikisource, wikipedia, dziennik_ustaw, wolne_lektury, 1000_novels, wikiquote, eltec_pol, wikivoyage, wikibooks, wikinews.
- Excluded (see README): open_subtitles_corpus, europeana_eu_pl_corpus_raw_speakleash, project_gutenberg_pl_corpus.
