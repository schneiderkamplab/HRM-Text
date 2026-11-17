---
license: cc-by-sa-4.0
language:
- pl
pretty_name: Polish DynaWord
task_categories:
- text-generation
size_categories:
- 1M<n<10M
tags:
- polish
- pretraining
- dynaword
configs:
- config_name: default
  data_files:
  - split: train
    path: data/*/*.parquet
---

# Polish DynaWord

A continuously developed corpus of human-written Polish text, **openly licensed
or official**, a Polish edition in the [Dynaword](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword)
family (Enevoldsen et al., [arXiv:2508.02271](https://arxiv.org/abs/2508.02271)).

[![Model Pulse](https://modelpulse.ifsp.dev/badge/dataset/SlayerLab/polish-dynaword.svg)](https://huggingface.co/spaces/tardellirs/model-pulse?dataset=SlayerLab/polish-dynaword)

> **v0.2.6 stable** · 3,394,876 documents · **7.04B tokens**
> (tiktoken proxy) · 27 sources
> Updated: **2026-10-22**. v0.2.6 ships before the NERGAL personal-data pass;
> the pass runs on every source before v0.2.7
> ([Personal & sensitive data](#personal--sensitive-data)).

> **main, not a release (2026-10-22)** · 27 sources · 3,394,876 documents ·
> **7.04B tokens**: the same data as v0.2.6. Three registered sources are
> [held off main](#held-off-main).
> Cite the `v0.2.6` tag, not main.

> **v0.3-dev experimental track** · quality/diversity workflow, source-gate
> validation and candidate-data audits. This is development work, not a released
> corpus version, and it does not replace the v0.2.6 stable parquets.

> **Europeana validation artifact (2026-07-10)** · a separate reproducible
> 810-document direct-ingestion sample stored under the legacy path
> `previews/v0.3.1/europeana.parquet`. It is not a full dataset release.

## Releases

### Stable releases

| version | status | documents | tokens | notes |
|---|---|---:|---:|---|
| `v0.2.6` | stable release | 3,394,876 | 7.04B | Adds 12 sources and withdraws five; the 15 v0.2.5 sources it keeps are relabelled, filtered or rebuilt. Ships before the NERGAL personal-data pass. |
| `v0.2.5` | previous stable | 4,366,651 | 9.68B | Adds community-contributed `samorzad_gov_pl` (institution-level author attribution and a URL-bearing attribution sidecar), `sejm_api` and `wiktionary_examples`. |
| `v0.2.4` | previous stable | 4,246,429 | 9.60B | Expanded `european_hplt_v3_pl` to WDS bins 10-5 (+1.49M docs / 2.04B tok); phone PII-scrub hardening (independent dual-lens) + cross-source dedup (zero-overlap). |
| `v0.2.3` | previous stable | 2,710,974 | 6.88B | Adds community-contributed `european_hplt_v3_pl`, `global_voices` and `nkjp1m`. |
| `v0.2.2` | previous stable | 2,579,963 | 6.36B | Added community-contributed `govpl`: 88,190 docs / 80.7M tokens. |
| `v0.2.1` | previous stable | 2,491,773 | 6.28B | 12-source corpus with `license` and `author` metadata columns; added `1000_novels`. |
| `v0.2.0` | previous stable | 2,490,773 | 6.22B | Provenance-first corpus from 11 open/official sources. |

The figures above are the releases as published. The tags `v0.2.0`-`v0.2.5`
were deleted after the October 2026 rights audit: they held data that v0.2.6
withdrew or changed ([Withdrawn since v0.2.5](#withdrawn-since-v025),
[Changes since v0.2.5](#changes-since-v025)). Their notes stay below and in
`CHANGELOG.md`; `v0.2.6` is the earliest release that can be loaded.

![Stable dataset size by version](artifacts/dataset_size_by_version.png)

### Development and validation artifacts

| name | type | scope | notes |
|---|---|---|---|
| `v0.3-dev` | experimental development track | workflow and candidate audits | Quality remix, legal-source caps, source QA, deduplication and direct-upstream ingestion. Not a corpus release. |
| `Europeana validation artifact 2026-07-10` | reproducible sample | 810 documents / 140,042 tokens | Stored at the legacy path `previews/v0.3.1/europeana.parquet`; preserves per-record rights and creator metadata. Not a corpus release. |

### Version details

#### v0.2.6 — current stable

**27 sources, 3,394,876 documents / 7,036,938,603 cl100k-proxy tokens:**

- adds 12 sources, 1,097,821 documents / 637,130,408 tokens:
  `plwiki_user_talk`, `sejm_committee_transcripts`, `plwiki_talk`, `ted_pl`,
  `sejm_api_2011_2022`, `nonsa`, `studia_bas`, `wiadomosci_statystyczne_pl`,
  `rock_pollub_pl`, `edukacja_medialna_pl`, `open_agh_chemistry_pl` and
  `open_icm_pl`;
- keeps 15 of the 20 v0.2.5 sources, 2,297,055 documents / 6,399,808,195
  tokens, each relabelled, filtered or rebuilt
  ([Changes since v0.2.5](#changes-since-v025));
- withdraws five v0.2.5 sources: `european_hplt_v3_pl`, `wikisource`,
  `1000_novels`, `samorzad_gov_pl` and `wikiquote`
  ([Withdrawn since v0.2.5](#withdrawn-since-v025));
- leaves out `sejm_interpellations` and `kultura_bez_barier_pl`, both
  [held off main](#held-off-main).

v0.2.6 ships before the NERGAL personal-data pass. Only each source's own
filters apply (see its datasheet); the pass runs on every source before v0.2.7.

#### v0.2.5 — previous stable

Added three sources, bringing the complete release to **20 sources,
4,366,651 documents / 9,676,513,980 cl100k-proxy tokens**:

- `samorzad_gov_pl`: **72,771 documents / 41,154,506 cl100k-proxy
  tokens** from 246 Polish local public institutions and one central platform
  tenant. The contribution preserves the publishing institution as `author`,
  discovered and fetched article URLs in an attribution sidecar and the verified
  platform-wide CC-BY-SA-4.0 basis.
- `sejm_api`: **38,812 documents / 36,335,587 cl100k-proxy tokens** of
  parliamentary speeches (2023 onward) from the official Sejm API,
  `public-domain (official documents)`
  ([PR #16](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/16)).
- `wiktionary_examples`: **8,639 documents / 1,115,820 cl100k-proxy tokens**
  of Polish Wiktionary usage examples, one document per headword,
  `CC-BY-SA-3.0`
  ([PR #14](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/14)).

Documentation correction: the v0.2.5 release has all 20 sources. Earlier
copies of this card counted only 18 (4,319,200 documents / 9,639,062,573
tokens) and listed `sejm_api` and `wiktionary_examples` as not released.

#### v0.2.4 — previous stable

Expanded `european_hplt_v3_pl` from WDS bins 10+9 to **WDS bins 10-5** (added
quality bins 8/7/6/5 and further WDS-9 shards): **+1,493,384 documents /
2,043,141,874 cl100k-proxy tokens**, 100% CC0-1.0. Includes a phone PII-scrub
hardening pass (v12b) verified by two independent lenses (a systematic
recall-gap masked by pipeline self-report was caught pre-release), and
cross-source deduplication against the existing WDS-10+9 shards (exact-dup 0,
near-dup overlap 0.0000%, byte-verified) — resolving the "downstream near-dedup
remains" caveat from the original release.

#### v0.2.3 — previous stable

Community expansion release. Adds `european_hplt_v3_pl` from
[PR #5](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/5)
and `global_voices` from
[PR #7](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/7),
plus `nkjp1m` from
[PR #8](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/8).
The complete 16-source release contains **2,710,974 documents /
6,881,277,362 cl100k-proxy tokens**, summed from the released per-source parquet
statistics.

#### v0.2.2 — previous stable

Added `govpl` from
[PR #9](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/9):
88,190 Polish government press releases collected directly from 133 gov.pl
ministry and agency subsites.

#### v0.2.1 — previous stable

Introduced the canonical eight-column release schema:
`id, text, source, added, created, token_count, license, author`. Added
`1000_novels` from
[PR #1](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/1)
and recomputed all release statistics from parquet files.

#### v0.2.0 — initial stable corpus

The provenance-first baseline: 11 reviewed open or official sources,
2,490,773 documents and 6.22B proxy tokens.

#### v0.3-dev — experimental quality workflow

Candidate-only work on a better-balanced training mixture: legal-source caps,
temperature sampling, source QA, deduplication and direct-upstream ingestion.
It is not a replacement for the stable corpus.

#### Europeana validation artifact — 2026-07-10

A separate reproducible 810-document Europeana sample preserving per-record
rights and creator metadata. It does not change stable-release totals.
`v0.3.1-preview` remains only as the legacy storage-path label.

## What this dataset contributes
The raw texts come from upstream publishers, official sources and existing open
corpora; `eurlex`, `wolne_lektury` and `biblioteka_nauki` come from SpeakLeash's
redistribution. **The value added here is the curation, not the bytes**,
following the Dynaword methodology:

1. **License review per source** — each source vetted for a *traceable* legal
   basis (a licence, the public domain or official-document status, documented
   in its datasheet); sources that fail the review are **excluded with a stated
   reason** (see table below), not silently kept. This is the core editorial
   work.
2. **Filtering & normalization** — minimal, reproducible gates (short-doc,
   non-Polish, exact cross-source dedup, OCR garble) applied uniformly to one
   clean schema: `id, text, source, added, created, token_count, license, author`.
3. **Documentation** — a datasheet per source (Gebru et al. 2021) + this card,
   so provenance and licensing are auditable rather than assumed.
4. **Reproducibility & versioning** — `src/` rebuilds the corpus from sources;
   new sources and removals are tracked in the CHANGELOG.

Credit for the underlying texts belongs to their authors and upstream sources,
and to SpeakLeash as the redistributor of `eurlex`, `wolne_lektury` and
`biblioteka_nauki`; this release does not claim ownership of them (see
Disclaimer).

## Contributors

| contributor | contribution | release / PR |
|---|---|---|
| [Kacper Wikieł](https://huggingface.co/kacperwikiel) | Project maintainer; corpus curation, source and license review, release engineering, documentation, validation and reproducible build workflow. | all releases |
| [Bart Kobyliński](https://huggingface.co/bartoszkobylinski1) | Added `1000_novels`; expanded Biblioteka Nauki and Europeana ingestion with per-document license and author metadata. | `v0.2.1`, [PR #1](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/1) |
| [Paweł Puzio](https://huggingface.co/ppuzio) | Built `govpl`: subsite discovery, direct ingestion pipeline, dataset artifact, contract tests and documentation. Added `sejm_interpellations` (held off main, not yet released); contributor guidance, PII scrubbing and its move to SlayerLab/NERGAL; registry-driven release totals, release tags and the source-PR/release split. | `v0.2.2`, [PR #9](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/9); [#17](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/17), [#20](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/20), [#24](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/24), [#28](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/28)–[#31](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/31), [#38](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/38), [#42](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/42) |
| [Arkadiusz Słota](https://huggingface.co/Maggio33) | Built & expanded `european_hplt_v3_pl`: HPLT v3 WDS 10+9 (PR #5) then WDS 10-5 expansion (+1,493,384 docs / 2.04B tok), modular cleaning pipeline, phone-recall PII-scrub (v12b, independent dual-lens), cross-source dedup-vs-base (zero-overlap), validation and documentation. | `v0.2.3` (PR #5), `v0.2.4` |
| [Dawid Majewski](https://huggingface.co/dawidmajewski) | Added the reviewed Global Voices Polish corpus; built `samorzad_gov_pl` with direct acquisition, institution attribution, licensing evidence, release artifact and reproducible conversion; prepared its de-identified upstream v0.2. | `v0.2.3`, [PR #7](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/7); `v0.2.5`, [PR #13](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/13); [PR #15](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/15) (merged via [#46](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/46)) |
| [1am](https://huggingface.co/1am) | Added `nkjp1m`: the manually annotated 1-million-word NKJP subcorpus, direct fetch/build pipeline, source documentation and release artifact. | `v0.2.3`, [PR #8](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/8) |
| [Piotr Styła](https://huggingface.co/PiotrSty) | Corpus preparation and contribution of `sejm_api`: parliamentary speeches from the official Sejm API with speaker attribution and immutable `PiotrSty/sejm-speeches-corpus` v1.0.1 provenance. Added 11 sources released in v0.2.6 (`sejm_api_2011_2022`, `open_agh_chemistry_pl`, `edukacja_medialna_pl`, `ted_pl`, `rock_pollub_pl`, `open_icm_pl`, `wiadomosci_statystyczne_pl`, `plwiki_talk`, `sejm_committee_transcripts`, `plwiki_user_talk`, `nonsa`) and `kultura_bez_barier_pl` (held off main, not yet released); `uzp_orzeczenia_pl`, held off main until v0.2.8; landed `studia_bas` and the `samorzad_gov_pl` v0.2 update; `build_dynaword` `preserve_id`/`preserve_created` flags. | `v0.2.5`, [PR #16](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/16); `v0.2.6`, [#18](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/18), [#25](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/25)–[#27](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/27), [#32](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/32)–[#37](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/37), [#39](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/39)–[#41](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/41), [#44](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/44)–[#46](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/46) |
| [Katarzyna Majzel-Pośpiech](https://huggingface.co/KateMajzel) | Added `wiktionary_examples`: usage examples extracted from the Polish Wiktionary dump, one document per headword. | `v0.2.5`, [PR #14](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/14) |
| [gzawadzki](https://huggingface.co/gzawadzki) | Added `studia_bas`: peer-reviewed socioeconomic and public-policy articles from Studia BAS. | `v0.2.6`, [PR #19](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/19) (merged via [#44](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/44)) |

Contributions are credited when they add a verifiable dataset artifact, pipeline,
validation, documentation or release work. A merged discussion with no resulting
files is not listed as a data contribution.

## Guiding principles
1. **Open & traceable licensing** — every source is *openly licensed* or outside copyright, with a
   documented legal basis (see each datasheet's "traceable basis"), not a vague "public domain".
   A few sources have a contested legal status rather than a licence; their datasheets describe it.
2. **Reproducibility** — `src/build_dynaword.py` rebuilds the corpus from sources.
3. **Documented** — a datasheet per source under `data/<source>/`.
4. **Extensibility** — versioned; new sources via PR.

## Sources
| source | description | license | documents | tokens |
|---|---|---|---:|---:|
| [eurlex](data/eurlex/eurlex.md) | EUR-Lex (EU legal acts, Polish) | `LicenseRef-EU-Reuse-Policy` | 242,488 | 2,333.0M |
| [parliamentary](data/parliamentary/parliamentary.md) | Polish Parliamentary Corpus (Sejm/Senat) | `public-domain (official documents)` | 329,863 | 1,504.1M |
| [wikipedia](data/wikipedia/wikipedia.md) | Polish Wikipedia | `CC BY-SA (3.0, 4.0 or both per record, by contribution date)` | 1,468,647 | 1,226.9M |
| [biblioteka_nauki](data/biblioteka_nauki/biblioteka_nauki.md) | Biblioteka Nauki | `per-record upstream license` | 37,843 | 590.9M |
| [dziennik_ustaw](data/dziennik_ustaw/dziennik_ustaw.md) | Dziennik Ustaw (Polish primary legislation) | `public-domain (official documents)` | 35,442 | 486.1M |
| [plwiki_user_talk](data/plwiki_user_talk/plwiki_user_talk.md) | Polish Wikipedia user-talk pages (ns 3) | `CC BY-SA (3.0, 4.0 or both per record, by contribution date)` | 380,295 | 381.0M |
| [sejm_committee_transcripts](data/sejm_committee_transcripts/sejm_committee_transcripts.md) | Sejm committee transcripts (terms 9-10) | `public-domain (official documents)` | 613,722 | 112.0M |
| [wolne_lektury](data/wolne_lektury/wolne_lektury.md) | Wolne Lektury (school readings) | `per-record Wolne Lektury licence (public domain, LAL 1.3, CC BY-SA 3.0 PL/3.0/4.0)` | 5,900 | 91.7M |
| [govpl](data/govpl/govpl.md) | gov.pl — Polish government press releases | `CC-BY-SA-4.0` | 74,946 | 68.3M |
| [plwiki_talk](data/plwiki_talk/plwiki_talk.md) | Polish Wikipedia talk pages (ns 1+5) | `CC BY-SA (3.0, 4.0 or both per record, by contribution date)` | 43,054 | 55.6M |
| [ted_pl](data/ted_pl/ted_pl.md) | TED Polish public-procurement notices | `TED notice status, no licence granted` | 14,210 | 39.6M |
| [sejm_api](data/sejm_api/sejm_api.md) | Sejm API parliamentary speeches (2023 onward) | `public-domain (official documents)` | 39,776 | 30.6M |
| [sejm_api_2011_2022](data/sejm_api_2011_2022/sejm_api_2011_2022.md) | Sejm speeches 2011-2022 (terms VII-IX, attributed) | `public-domain (official documents)` | 33,930 | 26.9M |
| [eltec_pol](data/eltec_pol/eltec_pol.md) | ELTeC-pol (European Literary Text Collection, Polish) | `CC-BY-4.0` | 100 | 21.5M |
| [nonsa](data/nonsa/nonsa.md) | Nonsensopedia (Polish satirical wiki, content namespaces) | `CC BY-SA 3.0` | 11,692 | 15.4M |
| [wikibooks](data/wikibooks/wikibooks.md) | Polish Wikibooks (open textbooks) | `CC BY-SA (3.0, 4.0 or both per record, by contribution date, plus the licence of imported text)` | 9,041 | 15.2M |
| [wikivoyage](data/wikivoyage/wikivoyage.md) | Polish Wikivoyage (travel guides) | `CC BY-SA (3.0, 4.0 or both per record, by contribution date)` | 7,312 | 14.1M |
| [wikinews](data/wikinews/wikinews.md) | Polish Wikinews | `CC BY (2.5, 4.0 or both per record, by contribution date, plus the licence of imported text)` | 23,572 | 11.0M |
| [global_voices](data/global_voices/global_voices.md) | Global Voices Polish | `CC-BY-3.0` | 1,926 | 3.5M |
| [nkjp1m](data/nkjp1m/nkjp1m.md) | The manually annotated 1-million word subcorpus of the National Corpus of Polish | `CC-BY-4.0` | 18,381 | 2.6M |
| [studia_bas](data/studia_bas/studia_bas.md) | Studia BAS — peer-reviewed socioeconomic and public-policy articles | `CC-BY-3.0-PL` | 112 | 2.3M |
| [wiadomosci_statystyczne_pl](data/wiadomosci_statystyczne_pl/wiadomosci_statystyczne_pl.md) | Wiadomosci Statystyczne. The Polish Statistician (GUS) | `CC BY-SA 4.0` | 169 | 1.5M |
| [rock_pollub_pl](data/rock_pollub_pl/rock_pollub_pl.md) | ROCK Politechnika Lubelska - Polish academic books | `CC-BY-SA-4.0` | 8 | 1.2M |
| [edukacja_medialna_pl](data/edukacja_medialna_pl/edukacja_medialna_pl.md) | Edukacja Medialna - Polish media-literacy lessons | `CC-BY-SA-3.0` | 248 | 0.7M |
| [open_agh_chemistry_pl](data/open_agh_chemistry_pl/open_agh_chemistry_pl.md) | Open AGH - four Polish chemistry textbooks | `CC-BY-SA-4.0` | 370 | 0.6M |
| [open_icm_pl](data/open_icm_pl/open_icm_pl.md) | OPEN ICM Polish open-access publications pilot | `per-record CC BY or CC BY-SA` | 11 | 0.4M |
| [wiktionary_examples](data/wiktionary_examples/wiktionary_examples.md) | Polish Wiktionary usage examples | `CC BY-SA (3.0, 4.0 or both per record, by contribution date)` | 1,818 | 0.2M |
| **total** | | | **3,394,876** | **7,036.9M** |

Each document's `license` field gives its own licence or status; the label above
summarises the source.

### Withdrawn since v0.2.5

These v0.2.5 sources are not in v0.2.6, and no release tag holds them: the
earlier tags were deleted ([Releases](#releases)).

| source | v0.2.5 documents | v0.2.5 tokens | reason |
|---|---:|---:|---|
| `european_hplt_v3_pl` | 1,603,974 | 2,555.5M | Licence unverified: HPLT's CC0 covers its packaging, not the crawled pages. It will not be re-added. |
| `wikisource` | 632,005 | 801.9M | Its single CC BY-SA 3.0 label also covered in-copyright post-war imprints that carry their own per-page licences. A rebuild from the official dump is planned for a later release. |
| `1000_novels` | 1,000 | 60.5M | Its rights screen ([PR #49](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/49), [PR #55](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/55)) kept the public-domain texts, but no row records the edition its text follows, so a protected preface, abridgement or editor's corrections cannot be ruled out. Withdrawn on 2026-10-17 ([PR #124](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/124)). |
| `samorzad_gov_pl` | 72,771 | 41.2M | Its CC BY-SA 4.0 is the platform operator's footer, not a grant from the 247 institutions that wrote the texts. Withdrawn on 2026-10-17 ([PR #123](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/123)). |
| `wikiquote` | 30,363 | 31.9M | Most of its pages quote works still in copyright, and its CC BY-SA label covers only the contributors' selection. |

### Changes since v0.2.5

The 15 v0.2.5 sources in v0.2.6 total 2,297,055 documents / 6,399.8M tokens.

- `eurlex` is relabelled `LicenseRef-EU-Reuse-Policy`: v0.2.5 labelled it
  `CC-BY-4.0`, but the EUR-Lex notice grants CC BY 4.0 only for consolidated
  texts and editorial content, not the acts themselves, and excludes
  third-party material. The 92 documents carrying the IASB notice and
  480 more found by a row review (third-party credits, UN ECE regulations,
  European Parliament stubs) are dropped, and `eurlex.attribution.jsonl` gives
  each row its EUR-Lex link. 242,488 documents / 2,333.0M tokens
  ([PR #71](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/71), [PR #82](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/82), [PR #173](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/173), [PR #177](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/177)).
- `parliamentary` was rebuilt from IPI PAN's speaker-labelled TEI dump: only
  official speakers are kept in the sittings and exact copies are dropped. The
  System Informacyjny Sejmu credit is given for its Sejm material as a
  precaution. 329,863 documents / 1,504.1M tokens
  ([PR #108](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/108), [PR #111](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/111)).
- `wikipedia` was rebuilt from the official plwiki dump, replacing the SpeakLeash
  snapshot. Each record is labelled CC BY-SA 3.0, 4.0 or both by its
  contribution dates. The 35 pages that carry plwiki's copyright-violation notice
  are dropped, and so are 7 pages that plwiki deleted for a copyright
  violation. 1,171,897 → 1,468,647 documents, 707.2M → 1,226.9M tokens
  ([PR #68](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/68), [PR #128](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/128), [PR #148](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/148)).
- `biblioteka_nauki` keeps its text from the SpeakLeash redistribution. Each
  record now carries the licence version and licence basis the Biblioteka Nauki
  API gives for it. 3 records under the Public Domain Mark and 4,142 further
  rows were dropped after review. 42,071 → 37,843 documents, 673.5M → 590.9M tokens
  ([PR #62](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/62), [PR #81](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/81), [PR #186](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/186)).
- `dziennik_ustaw` no longer claims Monitor Polski, which it never included. A
  sidecar gives each row its ELI address, and the System Informacyjny Sejmu
  credit is given as a precaution. Its text and counts are unchanged:
  35,442 documents / 486.1M tokens ([PR #103](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/103), [PR #160](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/160), [PR #162](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/162)).
- `wolne_lektury` is relabelled per document: v0.2.5 labelled every document
  `CC-BY-SA-4.0 / Wolna Sztuka 1.3`, which is wrong. Each now carries the
  licence its own Wolne Lektury book states (4,383 public domain, 1,467 LAL 1.3,
  50 CC BY-SA 3.0 PL, 3.0 or 4.0), with its credits in
  `wolne_lektury.attribution.jsonl`. 67 documents are dropped (63 eltec_pol
  novels, 2 with no usable licence, 2 whose translation is not free), 174
  printed in two later editors' selections are held out until the books'
  contents are checked, and the author's and translator's notes are added at
  the end of 459 texts.
  5,900 documents / 91.7M tokens
  ([PR #67](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/67), [PR #99](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/99), [PR #184](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/184), [PR #188](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/188), [PR #190](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/190), [PR #191](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/191)).
- `govpl` drops 188 PAP reprints, 186 other third-party texts and 12,870 press
  releases of prosecutor's offices. 88,190 → 74,946 documents, 80.7M → 68.3M tokens
  ([PR #63](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/63), [PR #170](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/170), [PR #214](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/214)).
- `sejm_api` cuts the "Przebieg posiedzenia" trailers, puts the 2,466
  statements they appended into rows of their own and drops 123 rows by speakers
  outside its allowlist. 38,812 → 39,776 documents, 36.3M → 30.6M tokens ([PR #83](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/83), [PR #158](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/158)).
- `eltec_pol` adds author metadata and an attribution sidecar and restores the
  chapter titles: 100 documents / 21.5M tokens ([PR #187](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/187)).
- `wikibooks` withholds 54 pages: 51 by the rights review and 3 with
  `{{GFDL-tekst}}`. Each record is labelled by its contribution dates and the
  licence of imported text, and markup residue is removed. 9,112 → 9,041
  documents, 15.6M → 15.2M tokens ([PR #127](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/127), [PR #134](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/134), [PR #139](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/139), [PR #142](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/142), [PR #147](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/147)).
- `wikivoyage` withholds 6,330 pages: 6,326 with `{{Atrybucja}}` (text from
  Wikitravel), 2 with `{{Import}}` and 2 by the rights review. Each record is
  labelled by its contribution dates, and markup residue is removed.
  13,645 → 7,312 documents, 17.1M → 14.1M tokens ([PR #125](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/125), [PR #133](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/133), [PR #138](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/138), [PR #141](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/141)).
- `wikinews` withholds 1 page. Each record is labelled by its contribution
  dates and the licence of imported text, and markup residue is removed.
  24,386 → 23,572 documents, 12.1M → 11.0M tokens
  ([PR #77](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/77), [PR #130](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/130), [PR #132](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/132), [PR #137](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/137), [PR #146](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/146)).
- `global_voices` drops 114 posts republished from partner outlets.
  2,040 → 1,926 documents, 3.7M → 3.5M tokens ([PR #66](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/66)).
- `nkjp1m` is relabelled `CC-BY-4.0` per the NKJP Consortium and ships an
  agreed attribution file; its text is unchanged ([PR #51](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/51)).
- `wiktionary_examples` dropped the lines quoting third-party works and is
  relabelled per record `CC-BY-SA-3.0`, `CC-BY-SA-4.0` or both, by contribution
  date. 8,639 → 1,818 documents, 1.1M → 0.2M tokens ([PR #50](https://huggingface.co/datasets/SlayerLab/polish-dynaword/discussions/50)).

## Held off main
These registered sources (`release: None`) have no data on main and are in no
release (see `CHANGELOG.md`):

- `sejm_interpellations`, until v0.2.7: it quotes letters from the public, some
  with health details, and waits for the NERGAL pass.
- `kultura_bez_barier_pl`, until the scope of its licence is answered.
- `uzp_orzeczenia_pl`, until v0.2.8: the personal-data pass leaves part of the
  sole traders' firm names and addresses unmasked.

## Method
Only **human-authored** text — no synthetic, machine-translated, or auto-transcribed
data. Gates are intentionally minimal (drop short docs, non-Polish, exact duplicates,
OCR garble); heavy quality filtering and mix-weighting are left to downstream training.
Evaluation-set decontamination is applied/marked separately. Schema:
`id, text, source, added, created, token_count, license, author`. The `license`
and `author` columns are per-document metadata when upstream exposes them; older
sources use the source-level license and an empty author field.

Cross-source deduplication covers some pairs of sources only. Wolne Lektury
drops a document when at least 0.9 of its 5-word shingles are in one ELTeC
novel; below that, both copies stay. Both tomes of Helena Mniszek's
*Trędowata* (0.7588 and 0.6473 against the same, shorter ELTeC text) are
therefore in both `wolne_lektury` and `eltec_pol`; the pairs are listed in
`data/wolne_lektury/wolne_lektury.eltec_pairs.tsv`.

## v0.3 quality roadmap and current status

The v0.2.x raw corpus is intentionally provenance-first, but its token mix is too
heavy in legal/parliamentary language for natural general pretraining. The v0.3
workflow therefore separates **source inclusion** from **training mix**:

- cap `eurlex + parliamentary + dziennik_ustaw` to roughly **10-20%** of training
  tokens combined;
- use source-level temperature sampling (`sqrt`, alpha `0.5`) instead of raw
  token-proportional sampling;
- add traceably licensed contemporary/natural Polish: open web, academic prose,
  cultural heritage text, guides, technical documentation/blogs, Q&A, and
  dialogue/instruction data;
- run aggressive exact, normalized, and near-duplicate removal;
- reserve the final **5-15%** of training for higher-quality sources rather than
  the largest sources;
- evaluate per-source perplexity and style contamination, not only global loss.

Current v0.3 source-ingestion status:

- `biblioteka_nauki`: included with its text from SpeakLeash's redistribution
  and each document's licence and author from the Biblioteka Nauki API.
- `europeana`: prepared in the source registry as a direct-upstream rebuild
  target with per-record rights statements and creator metadata; raw SpeakLeash
  Europeana remains excluded.
- Europeana release policy: split conservatively at pre-1929 records for
  US-sensitive downstream reuse, and keep later/unknown records separately
  labeled or held until their US rights status is checked.
- `european_hplt_v3_pl`: WDS bins 10-5 shipped in v0.2.4 and v0.2.5, then the
  data was removed from main because its licence is unverified: HPLT packaging
  is CC0, but the underlying crawled web documents can carry independent rights.
  It will not be re-added.
- `1000_novels`: a per-text rights screen kept the texts in the public domain in
  Poland, but no row records the edition its text follows, so the source was
  withdrawn from main on 2026-10-17. Re-admission, per text with the edition
  identified, is tracked for v0.2.8.

Current review artifacts:

- `configs/source_candidates_v0_3.json` — candidate decisions and license policy.
- `artifacts/source_license_review_v0_3.md` — source-by-source license review.
- `artifacts/source_candidate_audit_v0_3.md` — generated Hugging Face metadata audit.
- `artifacts/training_mix_v0_3.md` — example 1B-token training mix with legal sources capped at 15%.
- `artifacts/bartek_source_ingestion_plan_2026-07-02.md` — PR contract for
  Biblioteka Nauki and Europeana ingestion.

## Excluded sources (transparency)
Sources we reviewed and **deliberately left out** — part of the curation:

| source | reason |
|---|---|
| `open_subtitles_corpus` | Derivative of copyrighted film/TV dialogue; OpenSubtitles uploads largely unlicensed. Same copyright lesson as Danish Gigaword's OpenSubtitles (paper 2508.02271). Not openly licensed. |
| `europeana_eu_pl_corpus_raw_speakleash` | Aggregated items with mixed per-record rights (PD / CC-BY-NC / rights-reserved). The raw SpeakLeash redistribution is excluded; only a direct rebuild preserving per-record rights metadata may be included. |
| `project_gutenberg_pl_corpus` | Only 31 PL books (4.3MB) — PG is ~99% English; Polish PD literature already covered by wolne_lektury (so near-redundant after dedup). Dropped to avoid the PD-in-EU per-work check (PG claims PD-in-US only) for negligible token gain. |

## Personal & sensitive data
The corpus is built from text that its upstream sources already published under
open licences or as official public record. It names **public figures acting in
a public capacity**, for example:
- parliamentary speakers, from [PPC](https://clip.ipipan.waw.pl/PPC) (the Polish
  Parliamentary Corpus) and the Sejm API;
- authorities named in legal acts (EUR-Lex);
- people described in encyclopedic articles (Wikipedia).

The corpus can also hold personal data about private persons, which our filters
do not fully remove.

**v0.2.6 ships before the NERGAL pass.** Only each source's own filters apply
(see its datasheet). The [NERGAL](https://huggingface.co/SlayerLab/NERGAL)
personal-data pass runs on every source before v0.2.7.

**Your rights.** If the corpus holds data about you, you can ask us to:
- tell you what it holds (GDPR Art. 15);
- correct it (Art. 16);
- remove it (Art. 17);
- restrict its use (Art. 18).

You can also object to its processing (Art. 21).

Write to **takedown@fabryka.ai**. Name the record by its source and record id,
by a link, or by a phrase from its text.
- We answer within one month. For complex or numerous requests we may extend
  this by two months, and we tell you why within the first month.
- We ask for proof of identity only when we cannot otherwise tell that the
  request is yours.
- You can also complain to the President of the Personal Data Protection Office
  (UODO).

Removal follows the notice-and-takedown procedure below.

## Disclaimer & legal
- **Provenance in good faith.** Per-source licences are reproduced *as documented
  by the upstream sources*, to the best of our knowledge. We make no independent
  legal warranty about the copyright status of any individual document.
- **Publication basis.** Each source is published on its own basis, given in its
  datasheet: a licence, the public domain, the status of an official document or
  another basis the datasheet states.
  We do not rely on the text-and-data-mining exception to publish any source.
- **Acquisition dates.** Datasheets give the date a source was fetched where we
  recorded it; it is not recorded for every source.
- **No ownership claim.** This release is a *curated, license-reviewed, documented
  aggregation*. We claim no ownership of the underlying texts; rights remain with
  the original authors/rightsholders under their respective licenses.
- **Provided "as is"**, without warranty of any kind, express or implied. This is
  not legal advice.
- **Your compliance is yours.** Downstream users must satisfy the licence of each
  document themselves, as its `license` field and its source's datasheet give
  it, including attribution. See
  [Training models on this dataset](#training-models-on-this-dataset).
- **Copied text in Wikipedia.** The Wikipedia build drops pages that carry
  plwiki's copyright-violation notice, but it cannot detect a paste without one.
  In a hand-checked sample of 80 pages, 2 contained text copied or closely
  paraphrased from a copyrighted source: about 2.5%, with a 95% upper bound of
  12.9% for each licence label. Both pages are dropped; others like them remain
  and are removed on notice (below). Method and sample:
  [data/wikipedia/wikipedia.md](data/wikipedia/wikipedia.md).
- **Notice-and-takedown.** Anyone can ask us to remove a record: a rightsholder,
  a source, or a person the text is about. Write to **takedown@fabryka.ai**. Name
  the record by its source and record id, by a link, or by a phrase from its
  text, and give the reason.
  - We acknowledge the request within 5 working days.
  - We **disable** a substantiated request **within 7 days**. The record leaves
    `main`. Its id and text hash go on a blocklist, so no later build brings it
    back.
  - We then **remove it from every earlier public revision** on the Hub,
    including tagged releases. We aim to finish within 30 days, with Hugging
    Face's help where history has to be rewritten. Old commits and tags stay,
    but the removed files can no longer be downloaded from them. We cannot
    reach copies that were downloaded before.
  - We record each removal in [takedown/register.md](takedown/register.md),
    without personal data.
  - The procedure is in [takedown/PROCEDURE.md](takedown/PROCEDURE.md).

## License & attribution
The collection (selection, arrangement and our metadata) is released under
**CC BY-SA 4.0**, to the extent of our rights. Each document keeps the licence or
status in its `license` field; the collection licence does not change it, and it
does not cover third-party works in official documents or third-party statements
in parliamentary texts. Attribution is due to each upstream source (see the
datasheets). A source withdrawn after an objection is recorded in the CHANGELOG.
A single record removed on request is listed in
[takedown/register.md](takedown/register.md); see Notice-and-takedown above.

### Training models on this dataset
CC licenses apply only to uses that require permission under copyright or related
rights; they do not restrict uses permitted by statutory exceptions. The ShareAlike
condition applies when adapted material is shared publicly, and including a work
unchanged in a collection does not by itself create adapted material. In our
understanding, and in the view of several commentators, training a model does not
by itself make the model adapted material of the training texts, so ShareAlike
does not apply to model weights or adapters merely because they were trained on
such texts; this has not been tested in court. The assessment may differ where a
model or adapter contains and can reproduce protected portions of training texts,
or where an output reproduces protected expression from them, literally or in
recognisably adapted or translated form; sharing such a model or output then
requires a basis (the license of the reproduced text, with its conditions, or a
statutory exception), and whether ShareAlike also applies in that case is
unsettled. Creative Commons has published guidance for those who choose to comply
with CC licenses in all cases, stating that it does not take a position on whether
and when copyright applies; it recommends that models and outputs based on
ShareAlike material be shared under the same license, while noting that this will
almost certainly lead to overcompliance. The Free Art License 1.3 has its own
copyleft conditions, for derived works (§ 2.3) and for incorporation into a larger
work (§ 4), and their application to models is likewise unsettled. Datasets
derived from individual documents (paraphrased, summarised or machine-translated
versions) and retrieval datastores containing the texts are outside this
assessment: sharing them may amount to sharing the texts or adaptations of them;
embedding indexes and new databases built from this dataset may need a separate
assessment.

If you want to minimise licensing risk for a model trained on this dataset, you
can exclude documents whose license field indicates CC BY-SA or the Free Art
License. If you include them and ShareAlike or the Free Art License's copyleft
does apply to what you share, it is not enough to share it on terms that merely
do not restrict the rights granted: CC BY-SA requires a Creative Commons license
with the same License Elements (this version or later) or a BY-SA Compatible
License, and the Free Art License requires the same or a compatible license.
Attribution obligations attach to the individual licensed texts (creator,
copyright and license notices, indication of changes); crediting the dataset (for
example "Training data: Polish DynaWord, <link>") helps only if the link leads to
a resource that actually contains the information required for each text. Check
what the dataset provides for each document: the license and source fields may
not include every required notice (for example, author names are missing for
some older sources). License metadata may contain errors; filtering reduces, but
does not eliminate, this risk.

Models may reproduce portions of training texts, literally or in recognisably
adapted or translated form. Where an output reproduces protected expression from
a text and sharing it requires permission, it is subject to that text's license
(including attribution); facts, ideas, commonplace phrases without original
expression and uses covered by statutory exceptions (such as quotation) are not;
shortness alone does not make a fragment unprotected.

Removing a text from the corpus does not remove it from models already trained.

## For general-purpose model providers
What a provider of a general-purpose AI model may need for its copyright policy
and its public summary of training content (AI Act, Art. 53(1)(c) and (d)). Those
obligations rest with the model provider. This card is not a compliance
guarantee.

- **Name and version:** Polish DynaWord `v0.2.6`,
  <https://huggingface.co/datasets/SlayerLab/polish-dynaword>, loaded with
  `revision="v0.2.6"`.
- **Size and acquisition:** documents and tokens per source in [Sources](#sources).
  Each datasheet under `data/<source>/` gives the date the source was fetched
  where we recorded it; it is not recorded for every source.
- **Content:** human-written Polish text under open licences (Creative Commons,
  the Free Art License), public-domain works and official documents
  (legislation, parliamentary records, public-procurement notices). It contains
  personal data from public sources
  ([Personal & sensitive data](#personal--sensitive-data)).
- **Licence per document:** the machine-readable `license` field. Each
  datasheet gives the source's basis for publication.
- **Text-and-data-mining reservations:** we did not check machine-readable
  reservations (for example in robots.txt) systematically, and the corpus does
  not record them per document.
- **Filters and personal data:** the gates in [Method](#method) and each
  source's own filters, described in its datasheet. v0.2.6 has not had the
  NERGAL personal-data pass; it runs on every source before v0.2.7.
- **Withdrawn sources and change history:**
  [Withdrawn since v0.2.5](#withdrawn-since-v025) and `CHANGELOG.md`.
- **Removal requests:** the notice-and-takedown procedure under
  [Disclaimer & legal](#disclaimer--legal), with the public register in
  [takedown/register.md](takedown/register.md).

## Reproduce
```bash
python3 src/build_dynaword.py --all --speakleash-dir <speakleash_zst_dir> --out .
python3 src/make_docs.py
```

## Results

### Corpus phrase frequency (normalized by tokens)

Raw counts and token-normalized shares are regenerated from the current Parquet files with `src/pattern_frequency_report.py`.

- Total token count (tiktoken proxy): **7,036,938,603**

| Pattern | Count | Share of all tokens |
|---|---:|---:|
| `w roku` | 457,031 | 0.0065% |
| `klasyfikacji` | 169,748 | 0.0024% |
| `ustawa` | 664,616 | 0.0094% |
| `artykuł` | 3,423,411 | 0.0486% |
| `parlament` | 1,284,768 | 0.0183% |
| `rozporządzenie` | 1,515,578 | 0.0215% |
| `w pobliżu` | 81,258 | 0.0012% |
| `mieszkańców` | 337,033 | 0.0048% |
| `Dz.U.` | 979,489 | 0.0139% |

### Per-source shares

| source | pattern | count | share of source tokens |
|---|---|---:|---:|
| `biblioteka_nauki` | `w roku` | 24,639 | 0.00417% |
| `biblioteka_nauki` | `klasyfikacji` | 7,192 | 0.00122% |
| `biblioteka_nauki` | `ustawa` | 45,001 | 0.00762% |
| `biblioteka_nauki` | `artykuł` | 84,189 | 0.01425% |
| `biblioteka_nauki` | `parlament` | 29,217 | 0.00494% |
| `biblioteka_nauki` | `rozporządzenie` | 18,331 | 0.00310% |
| `biblioteka_nauki` | `w pobliżu` | 2,783 | 0.00047% |
| `biblioteka_nauki` | `mieszkańców` | 30,702 | 0.00520% |
| `biblioteka_nauki` | `Dz.U.` | 31,913 | 0.00540% |
| `dziennik_ustaw` | `w roku` | 33,096 | 0.00681% |
| `dziennik_ustaw` | `klasyfikacji` | 10,896 | 0.00224% |
| `dziennik_ustaw` | `ustawa` | 77,376 | 0.01592% |
| `dziennik_ustaw` | `artykuł` | 27,773 | 0.00571% |
| `dziennik_ustaw` | `parlament` | 42,338 | 0.00871% |
| `dziennik_ustaw` | `rozporządzenie` | 166,383 | 0.03423% |
| `dziennik_ustaw` | `w pobliżu` | 1,087 | 0.00022% |
| `dziennik_ustaw` | `mieszkańców` | 8,025 | 0.00165% |
| `dziennik_ustaw` | `Dz.U.` | 158 | 0.00003% |
| `edukacja_medialna_pl` | `w roku` | 1 | 0.00014% |
| `edukacja_medialna_pl` | `klasyfikacji` | 1 | 0.00014% |
| `edukacja_medialna_pl` | `ustawa` | 31 | 0.00435% |
| `edukacja_medialna_pl` | `artykuł` | 167 | 0.02342% |
| `edukacja_medialna_pl` | `parlament` | 0 | 0.00000% |
| `edukacja_medialna_pl` | `rozporządzenie` | 0 | 0.00000% |
| `edukacja_medialna_pl` | `w pobliżu` | 0 | 0.00000% |
| `edukacja_medialna_pl` | `mieszkańców` | 10 | 0.00140% |
| `edukacja_medialna_pl` | `Dz.U.` | 0 | 0.00000% |
| `eltec_pol` | `w roku` | 108 | 0.00050% |
| `eltec_pol` | `klasyfikacji` | 1 | 0.00000% |
| `eltec_pol` | `ustawa` | 153 | 0.00071% |
| `eltec_pol` | `artykuł` | 174 | 0.00081% |
| `eltec_pol` | `parlament` | 95 | 0.00044% |
| `eltec_pol` | `rozporządzenie` | 35 | 0.00016% |
| `eltec_pol` | `w pobliżu` | 246 | 0.00114% |
| `eltec_pol` | `mieszkańców` | 214 | 0.00100% |
| `eltec_pol` | `Dz.U.` | 0 | 0.00000% |
| `eurlex` | `w roku` | 39,642 | 0.00170% |
| `eurlex` | `klasyfikacji` | 57,321 | 0.00246% |
| `eurlex` | `ustawa` | 30,329 | 0.00130% |
| `eurlex` | `artykuł` | 1,774,561 | 0.07606% |
| `eurlex` | `parlament` | 779,474 | 0.03341% |
| `eurlex` | `rozporządzenie` | 1,200,341 | 0.05145% |
| `eurlex` | `w pobliżu` | 5,754 | 0.00025% |
| `eurlex` | `mieszkańców` | 9,389 | 0.00040% |
| `eurlex` | `Dz.U.` | 914,962 | 0.03922% |
| `global_voices` | `w roku` | 146 | 0.00423% |
| `global_voices` | `klasyfikacji` | 4 | 0.00012% |
| `global_voices` | `ustawa` | 148 | 0.00428% |
| `global_voices` | `artykuł` | 913 | 0.02643% |
| `global_voices` | `parlament` | 348 | 0.01008% |
| `global_voices` | `rozporządzenie` | 23 | 0.00067% |
| `global_voices` | `w pobliżu` | 90 | 0.00261% |
| `global_voices` | `mieszkańców` | 463 | 0.01341% |
| `global_voices` | `Dz.U.` | 1 | 0.00003% |
| `govpl` | `w roku` | 3,228 | 0.00473% |
| `govpl` | `klasyfikacji` | 514 | 0.00075% |
| `govpl` | `ustawa` | 4,562 | 0.00668% |
| `govpl` | `artykuł` | 1,659 | 0.00243% |
| `govpl` | `parlament` | 3,611 | 0.00529% |
| `govpl` | `rozporządzenie` | 4,024 | 0.00589% |
| `govpl` | `w pobliżu` | 649 | 0.00095% |
| `govpl` | `mieszkańców` | 12,715 | 0.01862% |
| `govpl` | `Dz.U.` | 2,921 | 0.00428% |
| `nkjp1m` | `w roku` | 109 | 0.00419% |
| `nkjp1m` | `klasyfikacji` | 9 | 0.00035% |
| `nkjp1m` | `ustawa` | 79 | 0.00304% |
| `nkjp1m` | `artykuł` | 153 | 0.00588% |
| `nkjp1m` | `parlament` | 216 | 0.00830% |
| `nkjp1m` | `rozporządzenie` | 20 | 0.00077% |
| `nkjp1m` | `w pobliżu` | 77 | 0.00296% |
| `nkjp1m` | `mieszkańców` | 159 | 0.00611% |
| `nkjp1m` | `Dz.U.` | 2 | 0.00008% |
| `nonsa` | `w roku` | 522 | 0.00338% |
| `nonsa` | `klasyfikacji` | 100 | 0.00065% |
| `nonsa` | `ustawa` | 70 | 0.00045% |
| `nonsa` | `artykuł` | 3,009 | 0.01949% |
| `nonsa` | `parlament` | 307 | 0.00199% |
| `nonsa` | `rozporządzenie` | 14 | 0.00009% |
| `nonsa` | `w pobliżu` | 316 | 0.00205% |
| `nonsa` | `mieszkańców` | 1,167 | 0.00756% |
| `nonsa` | `Dz.U.` | 0 | 0.00000% |
| `open_agh_chemistry_pl` | `w roku` | 6 | 0.00106% |
| `open_agh_chemistry_pl` | `klasyfikacji` | 9 | 0.00160% |
| `open_agh_chemistry_pl` | `ustawa` | 0 | 0.00000% |
| `open_agh_chemistry_pl` | `artykuł` | 3 | 0.00053% |
| `open_agh_chemistry_pl` | `parlament` | 0 | 0.00000% |
| `open_agh_chemistry_pl` | `rozporządzenie` | 0 | 0.00000% |
| `open_agh_chemistry_pl` | `w pobliżu` | 17 | 0.00301% |
| `open_agh_chemistry_pl` | `mieszkańców` | 0 | 0.00000% |
| `open_agh_chemistry_pl` | `Dz.U.` | 0 | 0.00000% |
| `open_icm_pl` | `w roku` | 19 | 0.00430% |
| `open_icm_pl` | `klasyfikacji` | 9 | 0.00204% |
| `open_icm_pl` | `ustawa` | 30 | 0.00680% |
| `open_icm_pl` | `artykuł` | 121 | 0.02741% |
| `open_icm_pl` | `parlament` | 34 | 0.00770% |
| `open_icm_pl` | `rozporządzenie` | 4 | 0.00091% |
| `open_icm_pl` | `w pobliżu` | 0 | 0.00000% |
| `open_icm_pl` | `mieszkańców` | 27 | 0.00612% |
| `open_icm_pl` | `Dz.U.` | 14 | 0.00317% |
| `parliamentary` | `w roku` | 174,916 | 0.01163% |
| `parliamentary` | `klasyfikacji` | 10,872 | 0.00072% |
| `parliamentary` | `ustawa` | 444,839 | 0.02957% |
| `parliamentary` | `artykuł` | 176,400 | 0.01173% |
| `parliamentary` | `parlament` | 297,729 | 0.01979% |
| `parliamentary` | `rozporządzenie` | 104,305 | 0.00693% |
| `parliamentary` | `w pobliżu` | 4,584 | 0.00030% |
| `parliamentary` | `mieszkańców` | 73,641 | 0.00490% |
| `parliamentary` | `Dz.U.` | 23,615 | 0.00157% |
| `plwiki_talk` | `w roku` | 2,632 | 0.00474% |
| `plwiki_talk` | `klasyfikacji` | 630 | 0.00113% |
| `plwiki_talk` | `ustawa` | 1,365 | 0.00246% |
| `plwiki_talk` | `artykuł` | 75,408 | 0.13571% |
| `plwiki_talk` | `parlament` | 1,241 | 0.00223% |
| `plwiki_talk` | `rozporządzenie` | 464 | 0.00084% |
| `plwiki_talk` | `w pobliżu` | 421 | 0.00076% |
| `plwiki_talk` | `mieszkańców` | 2,297 | 0.00413% |
| `plwiki_talk` | `Dz.U.` | 289 | 0.00052% |
| `plwiki_user_talk` | `w roku` | 2,439 | 0.00064% |
| `plwiki_user_talk` | `klasyfikacji` | 1,213 | 0.00032% |
| `plwiki_user_talk` | `ustawa` | 1,379 | 0.00036% |
| `plwiki_user_talk` | `artykuł` | 1,211,479 | 0.31796% |
| `plwiki_user_talk` | `parlament` | 2,043 | 0.00054% |
| `plwiki_user_talk` | `rozporządzenie` | 618 | 0.00016% |
| `plwiki_user_talk` | `w pobliżu` | 568 | 0.00015% |
| `plwiki_user_talk` | `mieszkańców` | 2,755 | 0.00072% |
| `plwiki_user_talk` | `Dz.U.` | 234 | 0.00006% |
| `rock_pollub_pl` | `w roku` | 22 | 0.00187% |
| `rock_pollub_pl` | `klasyfikacji` | 150 | 0.01273% |
| `rock_pollub_pl` | `ustawa` | 21 | 0.00178% |
| `rock_pollub_pl` | `artykuł` | 173 | 0.01469% |
| `rock_pollub_pl` | `parlament` | 25 | 0.00212% |
| `rock_pollub_pl` | `rozporządzenie` | 19 | 0.00161% |
| `rock_pollub_pl` | `w pobliżu` | 4 | 0.00034% |
| `rock_pollub_pl` | `mieszkańców` | 3 | 0.00025% |
| `rock_pollub_pl` | `Dz.U.` | 12 | 0.00102% |
| `sejm_api` | `w roku` | 2,002 | 0.00653% |
| `sejm_api` | `klasyfikacji` | 125 | 0.00041% |
| `sejm_api` | `ustawa` | 10,937 | 0.03570% |
| `sejm_api` | `artykuł` | 749 | 0.00244% |
| `sejm_api` | `parlament` | 14,159 | 0.04621% |
| `sejm_api` | `rozporządzenie` | 1,088 | 0.00355% |
| `sejm_api` | `w pobliżu` | 85 | 0.00028% |
| `sejm_api` | `mieszkańców` | 2,689 | 0.00878% |
| `sejm_api` | `Dz.U.` | 4 | 0.00001% |
| `sejm_api_2011_2022` | `w roku` | 2,592 | 0.00965% |
| `sejm_api_2011_2022` | `klasyfikacji` | 50 | 0.00019% |
| `sejm_api_2011_2022` | `ustawa` | 8,934 | 0.03325% |
| `sejm_api_2011_2022` | `artykuł` | 1,079 | 0.00402% |
| `sejm_api_2011_2022` | `parlament` | 11,246 | 0.04186% |
| `sejm_api_2011_2022` | `rozporządzenie` | 689 | 0.00256% |
| `sejm_api_2011_2022` | `w pobliżu` | 71 | 0.00026% |
| `sejm_api_2011_2022` | `mieszkańców` | 2,109 | 0.00785% |
| `sejm_api_2011_2022` | `Dz.U.` | 4 | 0.00001% |
| `sejm_committee_transcripts` | `w roku` | 6,980 | 0.00623% |
| `sejm_committee_transcripts` | `klasyfikacji` | 282 | 0.00025% |
| `sejm_committee_transcripts` | `ustawa` | 19,420 | 0.01734% |
| `sejm_committee_transcripts` | `artykuł` | 13,837 | 0.01235% |
| `sejm_committee_transcripts` | `parlament` | 18,245 | 0.01629% |
| `sejm_committee_transcripts` | `rozporządzenie` | 5,255 | 0.00469% |
| `sejm_committee_transcripts` | `w pobliżu` | 146 | 0.00013% |
| `sejm_committee_transcripts` | `mieszkańców` | 4,129 | 0.00369% |
| `sejm_committee_transcripts` | `Dz.U.` | 73 | 0.00007% |
| `studia_bas` | `w roku` | 87 | 0.00386% |
| `studia_bas` | `klasyfikacji` | 85 | 0.00377% |
| `studia_bas` | `ustawa` | 312 | 0.01383% |
| `studia_bas` | `artykuł` | 272 | 0.01206% |
| `studia_bas` | `parlament` | 154 | 0.00683% |
| `studia_bas` | `rozporządzenie` | 180 | 0.00798% |
| `studia_bas` | `w pobliżu` | 8 | 0.00035% |
| `studia_bas` | `mieszkańców` | 359 | 0.01591% |
| `studia_bas` | `Dz.U.` | 476 | 0.02110% |
| `ted_pl` | `w roku` | 3,586 | 0.00906% |
| `ted_pl` | `klasyfikacji` | 311 | 0.00079% |
| `ted_pl` | `ustawa` | 2,236 | 0.00565% |
| `ted_pl` | `artykuł` | 1,342 | 0.00339% |
| `ted_pl` | `parlament` | 691 | 0.00175% |
| `ted_pl` | `rozporządzenie` | 4,275 | 0.01080% |
| `ted_pl` | `w pobliżu` | 18 | 0.00005% |
| `ted_pl` | `mieszkańców` | 487 | 0.00123% |
| `ted_pl` | `Dz.U.` | 4,202 | 0.01062% |
| `wiadomosci_statystyczne_pl` | `w roku` | 52 | 0.00345% |
| `wiadomosci_statystyczne_pl` | `klasyfikacji` | 122 | 0.00810% |
| `wiadomosci_statystyczne_pl` | `ustawa` | 38 | 0.00252% |
| `wiadomosci_statystyczne_pl` | `artykuł` | 322 | 0.02138% |
| `wiadomosci_statystyczne_pl` | `parlament` | 29 | 0.00193% |
| `wiadomosci_statystyczne_pl` | `rozporządzenie` | 54 | 0.00359% |
| `wiadomosci_statystyczne_pl` | `w pobliżu` | 2 | 0.00013% |
| `wiadomosci_statystyczne_pl` | `mieszkańców` | 227 | 0.01507% |
| `wiadomosci_statystyczne_pl` | `Dz.U.` | 46 | 0.00305% |
| `wikibooks` | `w roku` | 311 | 0.00204% |
| `wikibooks` | `klasyfikacji` | 37 | 0.00024% |
| `wikibooks` | `ustawa` | 164 | 0.00108% |
| `wikibooks` | `artykuł` | 721 | 0.00474% |
| `wikibooks` | `parlament` | 281 | 0.00185% |
| `wikibooks` | `rozporządzenie` | 131 | 0.00086% |
| `wikibooks` | `w pobliżu` | 122 | 0.00080% |
| `wikibooks` | `mieszkańców` | 199 | 0.00131% |
| `wikibooks` | `Dz.U.` | 16 | 0.00011% |
| `wikinews` | `w roku` | 449 | 0.00409% |
| `wikinews` | `klasyfikacji` | 638 | 0.00582% |
| `wikinews` | `ustawa` | 389 | 0.00355% |
| `wikinews` | `artykuł` | 2,462 | 0.02245% |
| `wikinews` | `parlament` | 2,064 | 0.01882% |
| `wikinews` | `rozporządzenie` | 168 | 0.00153% |
| `wikinews` | `w pobliżu` | 455 | 0.00415% |
| `wikinews` | `mieszkańców` | 1,011 | 0.00922% |
| `wikinews` | `Dz.U.` | 27 | 0.00025% |
| `wikipedia` | `w roku` | 157,059 | 0.01280% |
| `wikipedia` | `klasyfikacji` | 79,082 | 0.00645% |
| `wikipedia` | `ustawa` | 15,755 | 0.00128% |
| `wikipedia` | `artykuł` | 43,982 | 0.00358% |
| `wikipedia` | `parlament` | 80,390 | 0.00655% |
| `wikipedia` | `rozporządzenie` | 9,008 | 0.00073% |
| `wikipedia` | `w pobliżu` | 55,953 | 0.00456% |
| `wikipedia` | `mieszkańców` | 179,796 | 0.01465% |
| `wikipedia` | `Dz.U.` | 515 | 0.00004% |
| `wikivoyage` | `w roku` | 460 | 0.00327% |
| `wikivoyage` | `klasyfikacji` | 15 | 0.00011% |
| `wikivoyage` | `ustawa` | 29 | 0.00021% |
| `wikivoyage` | `artykuł` | 616 | 0.00437% |
| `wikivoyage` | `parlament` | 154 | 0.00109% |
| `wikivoyage` | `rozporządzenie` | 31 | 0.00022% |
| `wikivoyage` | `w pobliżu` | 5,865 | 0.04164% |
| `wikivoyage` | `mieszkańców` | 2,883 | 0.02047% |
| `wikivoyage` | `Dz.U.` | 0 | 0.00000% |
| `wiktionary_examples` | `w roku` | 7 | 0.00338% |
| `wiktionary_examples` | `klasyfikacji` | 1 | 0.00048% |
| `wiktionary_examples` | `ustawa` | 3 | 0.00145% |
| `wiktionary_examples` | `artykuł` | 12 | 0.00579% |
| `wiktionary_examples` | `parlament` | 1 | 0.00048% |
| `wiktionary_examples` | `rozporządzenie` | 1 | 0.00048% |
| `wiktionary_examples` | `w pobliżu` | 6 | 0.00290% |
| `wiktionary_examples` | `mieszkańców` | 4 | 0.00193% |
| `wiktionary_examples` | `Dz.U.` | 0 | 0.00000% |
| `wolne_lektury` | `w roku` | 1,921 | 0.00209% |
| `wolne_lektury` | `klasyfikacji` | 79 | 0.00009% |
| `wolne_lektury` | `ustawa` | 1,016 | 0.00111% |
| `wolne_lektury` | `artykuł` | 1,835 | 0.00200% |
| `wolne_lektury` | `parlament` | 676 | 0.00074% |
| `wolne_lektury` | `rozporządzenie` | 117 | 0.00013% |
| `wolne_lektury` | `w pobliżu` | 1,931 | 0.00211% |
| `wolne_lektury` | `mieszkańców` | 1,573 | 0.00172% |
| `wolne_lektury` | `Dz.U.` | 5 | 0.00001% |

![Overall pattern counts](artifacts/pattern_frequency_overall.png)

![w roku by source](artifacts/pattern_frequency_w_roku.png)
![klasyfikacji by source](artifacts/pattern_frequency_klasyfikacji.png)
![ustawa by source](artifacts/pattern_frequency_ustawa.png)
![artykuł by source](artifacts/pattern_frequency_artykul.png)
![parlament by source](artifacts/pattern_frequency_parlament.png)
![rozporządzenie by source](artifacts/pattern_frequency_rozporządzenie.png)
![w pobliżu by source](artifacts/pattern_frequency_w_pobliżu.png)
![mieszkańców by source](artifacts/pattern_frequency_mieszkańców.png)
![Dz.U. by source](artifacts/pattern_frequency_dzu.png)
