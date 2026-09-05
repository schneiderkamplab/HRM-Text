---
type: Software
title: scripts/prepare_dfm11_koolbardi_exports.py
description: Builds validated bilingual Hugging Face publication packages from the finalized controlled Koolbardi campaign.
tags: [dfm11, koolbardi, export, validation]
status: stable
last_updated: 2026-09-04
confidence: high
---
# `scripts/prepare_dfm11_koolbardi_exports.py`

The builder streams the immutable controlled-campaign `final.jsonl`, validates
every admitted row, strips generation-only metadata, partitions each language
deterministically into 32 gzip JSONL shards, and emits cards, checksummed
manifests, and standalone exhaustive validators.

It refuses releases below 500,000 rows per language. The publication model and
persona revisions are pinned in code, and the complete package state is
recorded in `exports_dfm11/koolbardi_manifest.json`.
