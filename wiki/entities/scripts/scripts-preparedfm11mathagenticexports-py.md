---
type: Software Source
title: scripts/prepare_dfm11_mathagentic_exports.py
description: Deterministic upload-package builder for DFM11 Mathagentic datasets.
tags: [scripts, dfm11, mathagentic, export]
status: stable
last_updated: 2026-09-03
confidence: high
---
# `scripts/prepare_dfm11_mathagentic_exports.py`

Builds the audited TinyGSM-Python and verified GSM8K-Prolog source trajectories
as separate upload-staging packages under `exports_dfm11/`. It filters
TinyGSM against the complete accepted-verdict ledger, validates native
call/result/answer structure, writes deterministic gzip shards and checksums,
and atomically replaces destinations only after a complete build.

See [DFM11 Mathagentic Export Packages](/pages/dfm11-mathagentic-exports.md).
