# DFM13 Verified Additions v4

New snapshot: `data/dfm13/verified-wave-additions-20261003-v4`.
Base: `data/sampled_dfm12`, unchanged from v3. This is an additions assembly,
not a sampled epoch or complete DFM13 training dataset. Old v3 is preserved
and remains blocked by subsequent Baltic QA source-fidelity holds.

## Verified Totals

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| wave3 | 65 | 6,949,976 | 924,339,134 |
| wave4 | 35 | 1,088,738 | 933,543,107 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 101 | 8,046,210 | 1,860,313,386 |

Totals are one stored copy, before repeat weighting. MATH repeat5 is preserved
in repeat_mapping.json, not materialized. No sampling or training changes.

All100 wave repositories match their pinned/current HF revisions. Remote LFS
SHA256 or git blob identities match local payloads, cards, manifests and declared
license/attribution attachments. Full local source/receipt/array verification
and bounded native-token parity passed; post-report file signatures and links
remain unchanged. There are zero eligible-source adapter failures.72 tests pass.

The four FA packages use fa_minimal_structural_v2:234,956 rows and168,662,614
tokens, excluding7,086 census-bound rows. Their original artifacts remain
historical, not admitted. Retention is not semantic certification.

## Per-Language Totals

Explicit row.language labels; tokens are exact corresponding prompt+response
array lengths. Missing labels are unknown, not inferred from source names.

| Language | Rows | Stored tokens |
| --- | ---: | ---: |
| be | 211,603 | 210,184,779 |
| bg | 259,975 | 239,602,092 |
| bs | 111,348 | 96,232,691 |
| ca | 135 | 5,795 |
| cs | 572 | 24,077 |
| da | 808 | 32,856 |
| de | 2,722 | 119,710 |
| el | 677 | 29,526 |
| en | 1,228,064 | 115,705,419 |
| es | 4,334 | 182,816 |
| et | 334 | 13,702 |
| fa | 250,403 | 172,615,967 |
| fi | 1,322 | 57,893 |
| fo | 56 | 2,524 |
| fr | 3,322 | 144,658 |
| hr | 203,787 | 186,384,476 |
| hu | 4,067 | 3,721,615 |
| is | 378 | 17,152 |
| it | 1,931 | 82,368 |
| lb | 42,138 | 17,436,940 |
| lt | 1,962,515 | 325,039,880 |
| lv | 2,010,390 | 301,899,000 |
| nb | 550 | 23,405 |
| nl | 856,979 | 90,574,566 |
| nn | 74 | 3,316 |
| pl | 2,182 | 93,996 |
| pt_pt | 2,358 | 111,376 |
| ro | 617 | 26,925 |
| sk | 859 | 668,568 |
| sl | 185 | 142,439 |
| sq | 4,237 | 6,512,105 |
| sr | 136 | 41,435 |
| sv | 867,670 | 90,062,771 |
| uk | 1,986 | 85,403 |
| unknown | 7,496 | 2,431,145 |

All unknown rows are the existing MATH source, whose canonical rows omit
row.language. Exact per-wave/per-language and per-source tables are in the JSON.

## Incomplete Sources

- Four registry source holds: Baltic LT/LV QA and two Latvian P3 license partitions.
- Fourteen unsupported non-wave adapters: eight Arena-family sources and six jjzha sources. Not silently admitted or declared unusable.
- Two Fars summary components remain source-held outside this uploaded registry snapshot.
- HU/LB/SK Wikipedia transformations await the existing finalizer. Status snapshots show8/10/67 audit_retry_pending ledger entries; the parent reports underlying jobs terminal. No duplicate finalizer/retry was launched.
- HR four-task transforms are included. No new eligible entry or new hold appeared in the final registry reconciliation.

Impending-source evidence: `docs/reports/dfm13_assembly_v4_impending_sources_20261003.json`.
Complete hashes, remote methods, counts and exclusions:
`docs/reports/dfm13_verified_additions_v4_20261003.json`.

## Reproduction

```bash
python -m scripts.assemble_dfm13_additions --base data/sampled_dfm12 \
  --output <new-successor-root>
python -m scripts.report_dfm13_verified_additions --assembly <new-successor-root> \
  --output <new-report.json> --remote
```

No registry, live worker, GPU server, training or sampler was changed. The
assembly references external immutable-intended artifacts through symlinks;
revalidate pins and current source holds before later consumption. Base payloads
are unchanged stat references, not freshly content-hashed. No whole-corpus
semantic certification or semantic deduplication is claimed.
