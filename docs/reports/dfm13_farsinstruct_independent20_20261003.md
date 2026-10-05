# FarsInstruct independent accepted-target review, 2026-10-03

## Result

Full supplied source and final answer inspected for all 20 frozen candidates:
**7 publication holds, 13 with no material issue identified in this review.**
Five holds concern source fidelity and two concern materially incomplete answers
to explicit comprehensive-summary instructions. This is an assistant spot-check,
not human/native-Persian certification or a population error estimate.

| Source / class | Reviewed | Holds |
|---|---:|---:|
| pn_sum repaired | 10 | 2 |
| pn_sum original | 2 | 2 |
| wiki_sum original | 4 | 3 |
| PersianQA repaired | 2 | 0 |
| PersianQA original | 2 | 0 |

Sampling was deterministic hash-ranked within these deliberately chosen strata.
There were no accepted repaired wiki_sum rows at sampling time. Stored model
verdicts were not used as correctness evidence. Source factual truth outside the
passage was not independently verified; unsupported details are not automatically
false in the real world. All inspected answers were intelligible Persian; the
material failures were fidelity/completeness rather than English leakage.

## Concrete Holds

Sample numbers below are zero-based and map to the frozen sample and hash sidecar.

| Sample | Class | Finding |
|---|---|---|
| 0 | pn_sum repaired | Source recommends buying neighboring seats; answer changes this to choosing nonadjacent seats. Different operational recommendation. |
| 6 | pn_sum repaired | 1,313 households becomes 1,137. Clear numerical contradiction. |
| 10 | pn_sum original | One-sentence opening-date headline omits the facility name/location, capacity, investment and amenities despite explicit all-key-points instruction. |
| 11 | pn_sum original | One-sentence tourism-restoration headline omits flood/vegetation protection and the separate facade-regulation initiative. These are present before the source's truncated ending. |
| 12 | wiki_sum original | Adds December 30 birthday and October 16/December 20 election dates absent from supplied source. |
| 13 | wiki_sum original | Adds full surname Hajiyev absent from supplied source. |
| 15 | wiki_sum original | Adds birth details and 800 articles / 53 books / over 100 treatises absent from supplied source. |

The two repaired failures demonstrate defective final repaired candidates, not
necessarily defects first introduced by repair: pre-repair targets were not compared.
Do not infer repair causality from final-state inspection alone.

## Non-Hold Observations

PersianQA sample 16 correctly declines to name The Insider's director because the
passage only names Gladiator's director. Samples 17-19 answer luxury cars, Noa and
Taraj, all directly supported. Financial figures in sample 3 and bank schedules
in sample 8 matched the supplied passages. Sample 4 compresses works into groups;
sample 7 blurs banking roles slightly. Neither was assigned a definitive material
hold. Sample 9 repeats ambiguous source fire totals/categories; this was not
attributed to the repair as a newly invented discrepancy. Reasonable summary
compression was not penalized except where major independent topics disappeared
under an explicit comprehensive-summary instruction (10 and 11).

## Artifacts and Release Handoff

- Frozen full records: `data/dfm13/farsinstruct-independent20-20261003/sample.json`.
- Per-row assessments and read-only hash checks: `data/dfm13/farsinstruct-independent20-20261003/assessment.json`.
- Exact candidate holds: `docs/reports/dfm13_farsinstruct_independent_holds_20261003.json`.

The hold sidecar includes live ledger path/key, final record ID, canonical record
hash, raw stored-record hash, prompt/target hashes, repair/reaudit job IDs and
specific evidence. All 20 canonical record hashes matched the live ledgers on
read-only recheck. These are publication-hold requests, **not an automatically
installed export filter**; the release owner must consume the sidecar and exclude
the seven exact candidate versions until resolved. A different candidate hash
requires a fresh review rather than inheriting approval from this inspection.

No live ledger was edited, no worker interrupted, and no model/GPU request made.
This review does not certify the other 13 candidates or the full source for release.
