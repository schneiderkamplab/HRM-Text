
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/).

## [v1.2.20] - 2026-08-04

### Added

- Added the Danish MOSEL VoxPopuli and YouTube-Commons transcript datasets.

## [v1.2.19] - 2026-07-27

### Changed

- Changed license of wikibooks, wikipedia, wikisource and wiki-comments to CC BY-SA 4.0 to reflect their actual copyright information. See for example https://en.wikipedia.org/wiki/Wikipedia:Copyrights

## [v1.2.18] - 2026-07-20

### Added

- Added dataset: dakultur

### Fixed

- Fixed `update_descriptive_statistics.py`/`tables.py` skipping the `meta` config when regenerating README tables.

## [v1.2.17] - 2026-06-22

### Added

- Added Propella metadata files for Dynaword datasets.
- Added official Propella prompt/schema helpers and an OpenAI-compatible inference example.
- Added a `meta` dataset config and documentation for loading and merging metadata.

## [v1.2.16] - 2026-04-29

### Added

- Added dataset: tidsskrift-dk

## [v1.2.15] - 2026-04-06

### Added

- Added dataset: hvadvilduhelst

## [v1.2.14] - 2026-02-027

### Added 

- Added datasets: municipality_meetings

## [v1.2.13] - 2026-02-02

### Added 

- Added datasets: kb_administrative_publication, kb_historical_letters 


## [v1.2.12] - 2025-09-16

### Added 

- Added dataset: historical-danish-handwriting 

## [v1.2.11 - 2025-09-02

### Changed

- Updated Contributing.md to include the activation of the environment

### Added

- Added dataset: wiki-comments

## [v1.2.10] - 2025-08-18

### Changed

- Updated the wiki, wikibooks, wikisource datasets. 
- Changed `wiki` to `wikipedia`
- Fixed rounding error in average token count
- Improved the speed of token counting

### Added 

- Added `create.py` for wiki, wikibooks, wikisource.

## [v1.2.9] - 2025-08-05

### Docs

- Average document length now uses tokens instead of characters
- Added vizualization for checking document length in sub datasets
- Changes to `*/descriptive_stats.json`: 
  - The object no longer includes revision. 
  - Now include character-level metrics along with minimum and maximum length. Removed average document length as it is computable from existing metrics.
- Removed per-dataset histograms from the main readme. The goal is to avoid loading the entire dataset when updating the readme. This should make it easier for contributors.
- Simplifying PR workflow in `contributing.md`

### CI
- Fixes bug causing `make update-descriptive-stats` to fail when not having a linear commit history. The script now skips a dataset update based on revision, but only if the `descriptive_stats.json` file does not exist. To ensure that the main readme is always up to date, we change the make command always to update it.

## [v1.2.8] - 2025-08-05

### Added

- Added dataset: Enevældens Nyheder Online (`enevaeldens_nyheder`). This brings us to >5B tokens!

## [v1.2.7] - 2025-07-22

### Added

- Added dataset: Grundtvigs Works (`grundtvig`) 
- Added bias and risk section to the README

## [v1.2.6] - 2025-07-21

### Added

- Added two table to get an overview of data by license and domain

### Changed

- Dataset overview table now appears in a drop down menu

## [v1.2.5] - 2025-07-08

### Added

- Added the `domsdatabasen` dataset.

## [v1.2.4] - 2025-07-08

### Added

- Add a plot for tokens over time to see how the dataset develops
- Minor documentation improvements in the main readme

### Changed

- Rename `scrape_hovedstaden` to `health_hovedstaden` avoid confusion with its pretty name

## [v1.2.3] - 2025-06-30

### Added

- Added a `create.py` script for the `retsinformationdk` dataset.
  - Resulted in a boost in tokens and documents  

### Changed

- Did a full stats update on datasets, resulting in minor changes in a few datasheets

## [v1.2.2] - 2025-06-26

### Added

- Added the new `scrape_hovedstaden` dataset. 
- Added a new domain type `Medical`.

## [v1.2.1] - 2025-06-24

### Fixed

- Updated the danske-taler dataset. This version fixes a problem where the texts from the API contains no newlines, and where there should have been newline there is now space between words and punctuation.

## [v1.2.0] - 2025-06-23

### Fixed

- Updated the memo dataset, this second version fixed previous [issues](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword/discussions/67) with the download and processing of the Danish Memo which cut off the text leading to notably smaller documents.

## [v1.1.1] - 2025-06-16

### Added

- Added tests to ensure that 1 tokens document don't appear in the data. This filtered out 0 documents in total.

## [v1.1.0] - 2025-04-29

### Added

- Added multiple quality controls
  - Removed all empty string
  - Removed duplicates across within datasets
- Restructured datasets
  - Removed columns from the dataset to make the structure more lightweight, these include domain, metadata, and license. These have been moved to the individual datasheets. It is still possible to filter for license by using the dataset name
  - Added column for number of tokens
- For developers
  - Restructered CI codebase substantially
    - Added `DataSheet` to make CI for convenient 
    - factored out plots and tables

### Docs

- Sorted overview table
- Minor changes to dataset documentation


## [v1.0.12] - 2025-05-08

### Added

- Added new datasets
  - Norwegian Colossal Corpus (newspapers) (~191.08K tokens)
  - Norwegian Colossal Corpus (books) (~531.97M tokens)
  - Norwegian Colossal Corpus (maalfrid) (~29.26M tokens)
  - Norwegian Colossal Corpus (parliament) (~338.87M tokens)

## [v1.0.11] - 2025-03-29

### Added

- Added new datasets (more than 1B tokens 🎉)
  - AI Aktindsigt
  - Cellar
  - Danske Taler
  - Miljøportalen
  - EUR-Lex SUM
  - Finansministeriets Udgivelser

### Docs

- Sorted main table in readme
- Added Changelog
- Minor changes to dataset documentation 
