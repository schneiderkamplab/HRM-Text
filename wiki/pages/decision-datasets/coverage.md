---
type: Reference
title: Decision Inventory Coverage and Reproduction
description: What the DFM1-15 decision-source census covers, how its evidence is encoded, and what remains unverified.
tags: [datasets, inventory, provenance, decision-modelling]
status: draft
last_updated: 2026-10-21
confidence: high
---
# Coverage and Reproduction

The [overview](../decision-datasets.md) is backed by source-specific tables
and a metadata-only census. It is systematic across the available DFM1-15
inventories, but is **not a row-by-row audit or a certified decision-row yield**.

## Outputs

* [Compact TSV](source-inventory.tsv): searchable source identifiers and
  provisional routes, version mentions and evidence files.
* [Full evidence JSON, gzip](source-inventory.json.gz): preserves detailed
  provenance, membership observations and exact task-name relationships.
* [Summary JSON](source-inventory-summary.json): counts, input checksums,
  limitations and explicit gaps.

The October 21 census reads **131 metadata inputs**, records **48,429 exact
task names**, and indexes **8,810 identifiers** across repository, source-key,
sampling-prefix, local-collection and export-package namespaces. These overlap
and are **not 8,810 independent datasets**. It leaves **1,220** identifier
assessments explicitly unmapped rather than guessing a label contract.
Descriptive source tables refine the coarse automated routes.

The early supplements independently account for **all 5,212 original Sapient
file identifiers**, including template variants, and **168** additional early
category names. The latest supplements enumerate all **277 DFM14 components**
in the inspected registry, sharing **261 HF package IDs**, and DFM15's six
reasoning-repair families and four late additions. Package counts are not
counts of underlying original corpora, unique examples or sampled exposures.

## How to Interpret Evidence

* `reported_sampled_positive` means the named task had positive exposure in a
  particular preserved analytics report, possibly spanning several epochs.
* `reported_sampled_zero` is still useful historical coverage, not an active
  source recommendation.
* Sampling rules and registry declarations describe intent or inventory;
  they do not prove positive sampled exposure.
* Upstream attribution is distinct from a directly trained HF package.
* Tokenized directories and stored token ranges can include unselected rows.
* Not observing the same identifier in DFM15 does not prove removal: a repaired
  package or renamed source may retain the underlying examples.

Every automated route has inferred/unknown confidence. Filename keywords can
identify promising tasks but cannot establish whether a converted template
still has options, whether a QA task instead asks for question generation,
or whether a correction pair expresses a real error. Use the narrative source
tables and inspect the schema before implementing each converter.

## Known Limits

No canonical per-task analytics report was found here for DFM6 or DFM11-15;
their coverage uses other manifests, lineage, registry and range evidence.
The canonical DFM9 analytics file has the same task counts as DFM8, so it is
not proof of all later DFM9 extensions. Mini/post/smoke/context variants and
all historical archived reports were not exhaustively ingested. The source
aliases have not been globally deduplicated. These gaps remain explicit in
the summary; none is hidden by assuming inheritance is append-only.

Do not turn draft/eval-only/filtered sources into training merely because they
appear in a registered downloader or organization scan. Do not infer usable
decision-row counts from task counts, token counts, repeats or accepted SFT
rows. Unmapped entries mean further schema inspection is needed, not that the
source is low-quality or categorically unusable for decisions.

## Regenerate the Census

From the repository root:

```bash
python scripts/build_decision_dataset_inventory.py
python -m pytest -q tests/test_decision_dataset_inventory.py
python scripts/validate_okf.py wiki
```

This reads bounded metadata files only: no payload scans, token arrays,
network downloads, GPU work or production-data mutation. Output is a snapshot
of the inputs present on that machine. Missing inputs are recorded, so running
on another checkout does not silently establish equivalent coverage.

The script regenerates the machine ledger, not the source-specific narrative
tables; review those when source manifests or transformation policies change.
Its deterministic gzip preserves the full evidence without committing large
duplicated uncompressed tables.
