
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [v0.0.22] - 2026-10-16

### Added

- add wikiquote-nob, wikiquote-nno, wiktionary-nob, wiktionary-nno and wikinews

## [v0.0.21] - 2026-10-15

### Added

- add lagmannsrettene
- add tingrettene

## [v0.0.20] - 2026-10-15

### Added

- add hoyesterett

## [v0.0.19] - 2026-10-14

### Added

- add nva-cc-by
- add nva-cc-by-sa
- add nva-cc0

## [v0.0.18] - 2026-09-07

### Added

- Added Propella metadata for every dataset, exposed through the `meta` config.
- Added annotation profiles to the main README and source datasheets.
- Added the official Propella prompt/schema helpers and inference example.

### Changed

- Renamed source parquet files to `data.parquet` to separate corpus data from `metadata.parquet`.

## [v0.0.17] - 2026-08-12

### Added

- Added `bokselskap`, `veidemann-municipalities`, and `nbdigital` datasets

## [v0.0.16] - 2026-08-05

### Added

- Added eight `lovdata-ncc-*` datasets: the Lovdata CD/DVD material that used to make up `lovdata`, now split by document type (`norgeslover`, `sentrale-forskrifter`, `lokale-forskrifter`, `odelsting`, `somb-rundskriv`, `rtv-rundskriv`, `skatt-rundskriv`, `rundskriv-lovavdeling`). The text is unchanged, but statutes, local regulations, circulars and ombudsman statements can now be selected separately.

### Changed

- Replaced the `lovdata` dataset. It is now built from [Lovverk](https://github.com/bartoszkobylinski/lovverk), an open Git-versioned corpus of current Norwegian laws and central regulations, generated daily from Lovdata's public-data API. The previous version was derived from the NCC (Lovdata CD/DVD collections, last published in 2005); that material is now carried by the `lovdata-ncc-*` datasets.

## [v0.0.15] - 2026-07-21

### Added

- Added the `wikisource` dataset

## [v0.0.14] - 2026-06-03

### Added

- Added the dataset `cellar`.

## [v0.0.13] - 2026-05-07

### Added

- Added the datasets `wikibooks` and `wiki-comments`.

## [v0.0.12] - 2026-04-30

### Added

- Added the dataset `gutenberg`.

## [v0.0.11] - 2025-02-03

### Added

- Fixed language tag to use the three letter iso 639-3 instead of the two letter. 

## [v0.0.10] - 2025-02-03

### Added

- Added language distribution plot

## [v0.0.9] - 2025-02-03

### Added

- Added the dataset `lovdata`

### Changed

- Updated description for `maalfrid`, and `ncc-newspapers`
- Added NCC as a main citation to ensure credit assignment

## [v0.0.8] - 2025-02-02

### Added

- Added the dataset `government-nob` and `government-nno`, `public-reports`
- Added NCC as a baseline for the tokens over time plot. The 

### Changed

- Corrected the domain of for `ncc-books` to "Books" instead of "Spoken"
- Add new domain "Report" for denoting `government-*`
- Minor grammatical fixes across the datasheets
- Update dependency for kaleido
- Fix for token length plots
- Fix for tokens over time

## [v0.0.7] - 2025-01-25

### Added

- Added the dataset `ncc-books`

### Changed

- Corrected license for `stortingsforhandlingerne` to NLOD 2.0 instead of CC


## [v0.0.6] - 2025-01-25

### Changed

- Removed language filter from wikipedia. We assume it is correct.

## [v0.0.5] - 2025-01-25

### Added

- Added the dataset `stortingsforhandlingerne`

## [v0.0.4] - 2025-01-25

### Added

- Added the datasets `wikipedia-nno` and `wikipedia-nob`

## [v0.0.3] - 2025-01-25

### Added

- Added the dataset `ncc-newspapers`

## [v0.0.2] - 2025-01-25

### Changed

- Filtered documents <10 tokens from `maalfrid`


## [v0.0.1] - 2025-01-25

### Added

- Added the `maalfrid` corpus


## [v0.0.0] - 2025-01-24

Project was initialized by copying the structure of the [Danish Dynaword](https://huggingface.co/datasets/danish-foundation-models/norwegian-dynaword).
