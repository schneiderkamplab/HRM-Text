---
type: Plan
title: DFM14 Production Time Estimate
description: Volume-dependent walltime budget for preparing, generating, auditing and publishing DFM14 additions.
status: draft
confidence: low
last_updated: 2026-10-05
tags: [dfm14, data, throughput, planning]
---
# DFM14 Production Time Estimate

## Scope and Assumptions

Planning estimate, not a live ETA. Assume eight dedicated B200s with Gemma 4
26B A4B, eight independent work/ledger shards, sufficient CPU preparation,
and the [expansion playbook](new-language-expansion-playbook.md). Existing
unchanged inherited DFM13 data is reused, not generated or audited again.
See the [DFM14 plan](dfm14-plan.md) for the 16 new language variants.

At 35K-70K accepted synthetic conversations per language, the new-language
target is **560K-1.12M accepted conversations**. Individual language quotas
remain conditional on accepted existing instruction breadth. Optional identity
at 2K per language adds 32K. The proposed English knowledge pilot adds a separate
500K accepted rows if approved; existing-source conversions need not all be
generated. DaLA production in another thread is not included in generation
time below, although its submitted rows count toward audit volume.

## Measured References and Planning Rates

- [Joint synthetic production](dfm12-joint-synthetic-production.md): a
  five-minute window produced 6,282 accepted conversations, about 1,256/min.
  This is an accepted-output pipeline measurement: do not charge the same
  synthetic rows a second full audit budget.
- [Bulk audit throughput](dfm12-audit-client-throughput.md): 60,580 decisions
  in 4.52 minutes, about 13,406 rows/min; earlier periods were 5,600-6,000/min.
- Budget **300-700 net accepted synthetic conversations/min** and
  **6K-12K compact audit rows/min**. These are deliberately discounted planning
  assumptions, not measured DFM14 rates. New scripts, languages, longer replies,
  difficult repairs and reviewer calibration may reduce them further.

Both rates refer to the eight-GPU pool. Concurrent campaigns share that pool;
they cannot each receive the full measured throughput simultaneously.

## Stage Budget

| Stage | Assumed workload | Walltime budget |
|---|---|---|
| Download, normalize, provenance and task construction | 16 languages; parallel CPU preparation | 1-3 days, overlapping GPU work |
| Native-language generation/reviewer calibration | All 16 languages and task families | 0.5-1 day initially; may overlap preparation |
| Generate and audit synthetic conversations | 560K-1.12M accepted | 13-62 hours of eight-GPU capacity |
| Audit existing instructions, transforms, translations and supplied DaLA | Per 1M input rows | 1.4-2.8 hours of eight-GPU capacity |
| Repairs, reaudits and slow tails | Depends on salvageable rejection volume | Reserve 25-50% over GPU production time |
| Deduplicate, package, upload, tokenize, verify and sample | Accepted new sources; reuse inherited artifacts | 1-2 days provisional, largely incremental/overlapping |

The final CPU/I/O allowance is less well supported than the audit rates.
Large source verification, repository upload limits or network/storage latency
can extend it. Automated corruption/reordering task construction is CPU work;
its row audit belongs in the bulk audit budget, not teacher generation.

## Whole-Campaign Scenarios

The bulk volumes below are **scenarios**, not a measured DFM14 inventory.
They exclude synthetic rows already covered by the accepted-output rate.

| Scenario | Bulk rows audited | Approximate end-to-end walltime |
|---|---:|---:|
| Lean | 20M | 4-7 days |
| Working budget | 40M | 6-12 days |
| Large | 60M | 8-15 days |

These include synthetic production, calibration, a repair/tail allowance and
overlapped CPU finalization. Use **about one to two weeks** as the working
reservation until source manifests establish volume. A ten-day reservation is
1,920 allocated B200 GPU-hours; that is not a claim of continuous useful GPU
compute during CPU work. Unavailable source access or extensive failed language
calibration are outside these bounds.

If the optional 500K English knowledge pilot is all generated, add roughly
12-28 hours before additional repair overhead. Additional costly pivot
translation generation and separate DaLA creation require their own budgets;
the bulk audit rate does not pay for generating those rows.

## Tightening the Estimate

Freeze per-component row counts, measure accepted yield on every new language,
then measure a representative mixed five-minute window and a complete first
wave. Estimate remaining accepted targets using net acceptance throughput,
not request throughput. Report generation, bulk audit, repair and CPU tails
separately. Do not resubmit accepted work to fill devices or hide poor yield.
