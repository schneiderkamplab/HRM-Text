
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [v0.0.26] - 2026-10-25

### Added

- add wikisource

## [v0.0.25] - 2026-10-25

### Added

- add riksarkivet-goteborg-lines
- add riksarkivet-svea-hovratt-lines
- add riksarkivet-krigshovratten-lines
- add riksarkivet-bergskollegium-lines
- add riksarkivet-frihetstiden-lines
- add riksarkivet-pahlman-lines
- add riksarkivet-trolldom-lines
- add riksarkivet-gota-hovratt-lines
- add riksarkivet-bergmastaren-lines
- add riksarkivet-alvsborgs-losen-lines
- add riksarkivet-jonkoping-lines

## [v0.0.24] - 2026-10-25

### Added

- add swedish-pd

## [v0.0.23] - 2026-10-25

### Added

- add lb-restricted

## [v0.0.22] - 2026-10-24

### Added

- add bellman
- add drama

## [v0.0.21] - 2026-10-24

### Added

- add gutenberg
- add runeberg-diverse
- add runeberg-folkbbl
- add runeberg-rost
- add runeberg-tiden
- add runeberg-urdagkron

## [v0.0.20] - 2026-10-24

### Added

- add svt-2004
- add svt-2005
- add svt-2006
- add svt-2007
- add svt-2008
- add svt-2009
- add svt-2010
- add svt-2011
- add svt-2012
- add svt-2013
- add svt-2014
- add svt-2015
- add svt-2016
- add svt-2017
- add svt-2018
- add svt-2019
- add svt-2020
- add svt-2021
- add svt-2022
- add svt-2023
- add svt-nodate

## [v0.0.19] - 2026-10-23

### Added

- add press65
- add press76
- add press95
- add press96
- add press97
- add press98
- add gp1994
- add gp2001
- add gp2002
- add gp2003
- add gp2004
- add gp2005
- add gp2006
- add gp2007
- add gp2008
- add gp2009
- add gp2010
- add gp2011
- add gp2012
- add gp2013
- add attasidor

## [v0.0.18] - 2026-10-20

### Added

- add bloggmix1998
- add bloggmix1999
- add bloggmix2000
- add bloggmix2001
- add bloggmix2002
- add bloggmix2003
- add bloggmix2004
- add bloggmix2005
- add bloggmix2006
- add bloggmix2007
- add bloggmix2008
- add bloggmix2009
- add bloggmix2010
- add bloggmix2011
- add bloggmix2012
- add bloggmix2013
- add bloggmix2014
- add bloggmix2015
- add bloggmix2016
- add bloggmix2017
- add bloggmixodat

## [v0.0.17] - 2026-10-19

### Added

- add sweachum
- add sweacsam

## [v0.0.16] - 2026-10-19

### Added

- add kalmar-1910
- add dalpilen-1910
- add dalpilen-1920
- add ostgotaposten-1910

## [v0.0.15] - 2026-10-18

### Added

- add mosel-voxpopuli
- add mosel-youtube-commons

## [v0.0.14] - 2026-10-18

### Added

- add rd-prop
- add rd-sou
- add rd-prot
- add rd-bet
- add rd-mot
- add rd-ds
- add rd-ovr
- add sfs
- add rd-frsrdg
- add rd-skfr
- add rd-yttr
- add rd-utsk
- add rd-fpm
- add rd-ip
- add rd-kom
- add rd-kammakt
- add rd-utr
- add rd-anf-1993-2018

## [v0.0.13] - 2026-09-05

### Added

- Added the remaining 327 Kubhist 2 collections as individual datasets.

## [v0.0.12] - 2026-07-27

### Added

- Added 36 corpora from Språkbanken Text:
  - 5 remaining `flashback-*` subsets: `flashback-fordon`, `flashback-mat`, `flashback-om-flashback`, `flashback-resor`, `flashback-sex`.
  - 12 `fsv-*` corpora from Fornsvenska textbanken (medieval and early modern Swedish).
  - 7 `standsriksdagen-*` corpora of digitised historical parliamentary records.
  - 5 literary/cultural corpora: `strindbergromaner`, `strindbergbrev`, `dramadialog`, `bibel1917`, `psalmboken`.
  - 5 specialty corpora: `akademiliv`, `dagens-arena`, `gu-journalen`, `forskning-framsteg`, `sv-covid-19`.
  - `europarl-sv` (Swedish European Parliament proceedings).
  - `laakartidningen` (Läkartidningen medical journal, merging 11 yearly releases 1996-2006). First Medical-domain source in the corpus.

### Changed

- `pretty_name` now uses Språkbanken's official corpus names, keeping the Swedish name as the primary identifier with the official English name as a gloss.
- Corrected `pretty_name` on six existing datasets whose English name misdescribed the corpus: `flashback-vetenskap` was "Science & Technology" but the subforum is *Vetenskap & humaniora* (Science & Humanities), `flashback-hem` was "Home & Garden" rather than *Hem, bostad & familj* (Home, Housing & Family), `flashback-kultur` was "Culture & Entertainment" rather than *Kultur & media*, `flashback-sport` dropped *träning* (Fitness), `familjeliv-allmanna-kropp` dropped *själ* (Soul), and `familjeliv-sexsamlevnad` was "Sex & Cohabitation" rather than *Sex & samlevnad* (Sex & Relationships).
- Pinned the `dynaword` dependency to a specific git rev in every `create.py`, so each script stays reproducible against the API it was written against.
- Corrected `size_categories` across the repo to the values Hugging Face defines; several were non-standard (e.g. `1-10k`, `100k-1M`) or did not match the actual row count. Added a test that checks each datasheet's `size_categories` against the row count in the parquet footer, so this cannot drift again.
- The token-length plot is now sorted alphabetically; it previously used filesystem order, which was arbitrary and unstable between runs.

## [v0.0.11] - 2026-07-26

### Added

- Added 11 remaining `familjeliv-*` subsets from the Familjeliv internet forum: `familjeliv-adoption`, `familjeliv-allmanna-ekonomi`, `familjeliv-allmanna-familjeliv`, `familjeliv-allmanna-fritid`, `familjeliv-allmanna-husdjur`, `familjeliv-allmanna-hushem`, `familjeliv-allmanna-noje`, `familjeliv-allmanna-sandladan`, `familjeliv-anglarum`, `familjeliv-expert`, `familjeliv-pappagrupp`.

### Changed

- Sped up the test suite: dataset-quality checks now scope to datasets changed in the current PR (via a diff against `origin/main`) instead of re-scanning the whole corpus, the global id-uniqueness check was replaced with an equivalent cheaper per-dataset check, and per-dataset checks use a shared, vectorized-PyArrow-backed fixture instead of independently loading and Python-looping over each dataset. This notably speeds up tests from >1h to <2min (of course dependent on size of commit).

## [v0.0.10] - 2026-07-26

### Added

- Added 11 `flashback-*` subsets from the Flashback internet forum: `flashback-dator`, `flashback-droger`, `flashback-ekonomi`, `flashback-hem`, `flashback-kultur`, `flashback-livsstil`, `flashback-ovrigt`, `flashback-politik`, `flashback-samhalle`, `flashback-sport`, `flashback-vetenskap`.
## [v0.0.9] - 2026-07-25

### Added

- Added 12 `familjeliv-*` subsets from the Familjeliv internet forum: `familjeliv-allmanna-kropp`, `familjeliv-allmanna-samhalle`, `familjeliv-foralder`, `familjeliv-gravid`, `familjeliv-kansliga`, `familjeliv-planerarbarn`, `familjeliv-sexsamlevnad`, `familjeliv-svartattfabarn`, `familjeliv-medlem-allmanna`, `familjeliv-medlem-foraldrar`, `familjeliv-medlem-planerarbarn`, `familjeliv-medlem-vantarbarn`.

## [v0.0.8] - 2026-07-25

### Added

- Added `lb-open` (Swedish Literature Bank: Free Works).
- Added `poeter` (Poeter.se poetry sentences).
- Added `wikipedia-sv` (Swedish Wikipedia articles).

## [v0.0.7] - 2026-06-21

### Added

- Added the `cellar` dataset.

## [v0.0.6] - 2026-05-30

### Added

- Added 10 subsets from the Bicameral Riksdag collection: `riksdagen-forfattningssamling`, `riksdagen-reglementen`, `riksdagen-register`, `riksdagen-skrivelser`, `riksdagen-utredningar`, `riksdagen-berattelser`, `riksdagen-motioner`, `riksdagen-betankanden`, `riksdagen-propositioner`, `riksdagen-protokoll`.

## [v0.0.5] - 2026-05-30

### Added

- Added `statens-offentliga-utredningar`

## [v0.0.4] - 2026-05-29

### Added

- Added `biblioteksbladet`

## [v0.0.3] - 2026-05-29

### Added

- Added the `svensk-tidskrift`

### Fixed

- Fixed missing `pydantic` and `dynaword` inline script dependencies in `create.py` for `dalpilen-1860` and `lag1800`. Removed the `sys.path.insert` workaround in favour of a proper `[tool.uv.sources]` declaration.

## [v0.0.2] - 2026-04-13

### Added

- Added the `dalpilen-1860` subset based on Språkbanken Text's *Dalpilen 1860's* / *Dalpilen 1860-talet* corpus from the Kubhist 2 collection.
- Added a reproducible `data/dalpilen-1860/create.py` pipeline that streams the BZ2 XML source, reconstructs issue-level text, and preserves issue dates in Dynaword metadata.
- Added dataset-specific parser tests and generated dataset assets, descriptive statistics, and refreshed README tables and plots for the expanded Swedish Dynaword release.

## [v0.0.1] - 2026-04-09

### Added

- Added the `lag1800` subset based on Sprakbanken's *Laws from the 1800's* corpus.
- Added a reproducible `data/lag1800/create.py` pipeline that converts XML `<text>` nodes into Dynaword rows and derives per-text `created` ranges from `datefrom`/`dateto`.
- Added generated dataset assets, descriptive statistics, and refreshed README tables and plots for the current Swedish Dynaword release.

## [v0.0.0] - 2025-02-15

Project was initialized by copying the structure of the [Danish Dynaword](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword).
