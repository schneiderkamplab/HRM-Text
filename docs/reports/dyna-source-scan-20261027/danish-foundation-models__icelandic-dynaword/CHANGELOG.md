# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [v0.0.15] - 2026-09-07

### Added

- Added Propella metadata for every dataset, exposed through the `meta` config.
- Added annotation profiles to the main README and source datasheets.
- Added the official Propella prompt/schema helpers and inference example.

### Changed

- Renamed source parquet files to `data.parquet` to separate corpus data from `metadata.parquet`.

## [v0.0.14] - 2026-08-13

### Added

- Added `rafbokavefur`, `icepahc` and `gutenberg` — the book-length sources.

### Fixed

- Changed heading in datasheets from "Source" to "Source Data" in all datasets to match the automatic text under "Data Fields".

## [v0.0.13] - 2026-08-12

### Added

- Added `stjornartidindi` and clarified relationsship with igc-law

### Fixed

- Added missing headings in part of igc-law

## [v0.0.12] - 2026-08-05

### Added

- Added `wikibooks`, `wikisource` and `wiki-comments`.

### Changed

- Shortened short descriptions in the data cards.

## [v0.0.11] - 2026-07-31

### Changed

- igc-forums is split into three datasets - one for each forum
- Descriptions in datasheets were shortened and rearranged, so a description of the data comes before descriptions of the processing. 

## [v0.0.10] - 2026-07-28

### Added

- Added `hjh-corpus`.

## [v0.0.9] - 2026-07-28

### Added

- Added `Wikipedia`.

## [v0.0.8] - 2026-07-24

### Added

- Added `IGC-law`.

## [v0.0.7] - 2026-07-24

### Fixed

- Fixed `update_descriptive_statistics.py` hanging on exit on macOS (kaleido/matplotlib) by force-exiting after `main()` completes.

## [v0.0.6] - 2026-07-24

### Added

- Added the social datasets from IGC whose license permits it.

## [v0.0.5] - 2026-07-09

### Added

- Combined the parla releases into `igc-parla` (22.10 base + 2024ext), replacing `igc-parla-2024ext`

## [v0.0.4] - 2026-07-09

### Added

- Added the `saga`
- Added *.log to .gitignore.

## [v0.0.3] - 2026-07-06

### Added

- Added the `igc-adjud`

## [v0.0.2] - 2026-06-30

### Added

- Added the `igc-journals-22-10`

### Fixed

- Fixed a timezone-awareness crash in `src/dynaword/plots/plot_tokens_over_time.py` that broke `make update-descriptive-statistics` whenever the working-tree `descriptive_stats.json` diverged from the last commit (i.e. whenever a dataset is added).


## [v0.0.1] - 2026-04-23

### Added

- Added the `igc-parla-2024ext` subset based on CLARIN-IS's *IGC-Parla 2024ext (unannotated version)* release from the Icelandic Gigaword Corpus project.
- Added a reproducible `data/igc-parla-2024ext/create.py` pipeline that downloads the TEI archive, converts each meeting file to a Dynaword sample, and preserves meeting dates in the Dynaword metadata.
- Added generated dataset assets, descriptive statistics, and refreshed README tables and plots for the first Icelandic Dynaword subset release.

## [v0.0.0] - 2026-04-23

### Added

- Initialized the Icelandic Dynaword repository scaffold based on the Swedish Dynaword project structure.
- Added shared Dynaword tooling, tests, contributor guidance, and package metadata for the Icelandic variant.
- Added an Icelandic Gigaword reference line to the repository token-history plot configuration.
