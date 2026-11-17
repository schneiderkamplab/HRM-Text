# Changelog

All notable changes to Norwegian dyna-instruct are documented here.

## [0.1.0] - 2026-09-03

- Forked the reproducible schema and tooling from Icelandic dyna-instruct revision
  `a9fa6eb7d8cbed0a3b6b8112cfb4845e84090dc9`.
- Added the open-license NB Samtale turn-pair, NorQuAD Wikipedia training, FLEURS
  English→Bokmål translation, Magpie Qwen3 Bokmål, and Norwegian punctuation
  restoration constituents.
- Documented source provenance, license evidence, attribution, and benchmark lineage
  in the constituent dataset cards.
- Added pinned converters, schema checks, generated statistics, and source-specific
  dataset cards.
- Rewrote the dataset cards in a shorter, plain-language format.
- Filtered the punctuation-restoration source to nonempty answers that preserve the
  input's normalized letter/digit sequence, as required by its own instruction.
- Removed English prompt/response generations from the Bokmål Magpie constituent with
  a pinned `langid` filter.
