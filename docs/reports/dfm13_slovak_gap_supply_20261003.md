# Remaining Slovak translation edges: bounded supply check

2026-10-03. Handoff for main/Tesla: **no additive candidate bundle found** for
`ca-sk`, `fo-sk`, or `nn-sk` under the selected sources and bounded checks below.
This does not establish global unavailability. No approvals were relaxed,
corpus archives downloaded, base queues duplicated, or GPU calls made.

## Exact cached-source check

Evidence root: `data/dfm13/wave4/slovak-gap-research-20261003-v1`.
`receipt.json` pins inventories, candidate files, candidate receipts and the
existing pivot manifest; `evidence/00.json` through `07.json` preserve eight
bounded remote metadata responses with URLs, fetch times and hashes.

| Edge | Existing English-leg candidate pairs | Unique unambiguous English anchors | Exact joins with selected SK leg |
|---|---:|---:|---:|
| ca-sk | 2,286 | 1,989 | 0 |
| fo-sk | 299 | 284 | 0 |
| nn-sk | 2,736 | 2,121 | 0 |

The selected Slovak addition contains **784,241 candidate pairs**, with 643,332
unique unambiguous English anchors in the existing index. Its approved sources
are ELRC-487-Culture_Slovak and ELRC-488-Justice_Slovak (public domain), plus
ELRC-2721-EMEA (CC-BY-4.0). The three other English legs are selected Tatoeba data.

`independent-stream-crosscheck.json` independently streams the four hash-verified
candidate files, including all 784,241 SK rows. It confirms **zero raw exact
English-anchor intersections** for every edge, before ambiguity rejection.
Thus the negative result does not depend solely on the mutable SQLite index.
There is no case folding, approximate matching, machine translation, guessed
alignment, or ordinal matching. Existing DFM12 OPUS inventory additionally has
no entries for these direct edges or en-sk/sk-en.

## Bounded upstream review

OPUS Tatoeba Moses API queries without a version filter returned empty corpus
lists for en-sk, ca-sk, fo-sk and nn-sk; raw responses are retained. This is an
API result, not proof that Tatoeba has no Slovak sentences or that another
distribution could not contain a suitable licensed pair.

Selected direct inventory alternatives do not yield new approved supply:

- QED: research-only in the pinned [release metadata](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/QED/v2.0a/info.yaml).
- TED2020: points to TED usage terms rather than an approved PD/CC0/CC-BY grant
  in its [release metadata](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/TED2020/v1/info.yaml). No new clearance inferred.
- ELRC-wikipedia_health: CC-BY-SA-3.0, outside this requested license set,
  per [release metadata](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/ELRC-wikipedia_health/v1/info.yaml).
- EUbookshop: release metadata supplies no license/copyright field. Its 1,989
  advertised ca-sk alignments remain a rights-review possibility, not approved
  candidates. No rights are inferred from institutional authorship.
- Existing software-fragment, subtitle and web-mined quality exclusions remain
  unchanged; no license-based bypass was attempted.

The saved discovery run is capped at eight metadata requests, 2MB per response,
20-second request timeout, and 60-second per-language indexed query. No corpus
payload download. Preliminary interactive metadata checks preceded that run;
the eight-request bound describes the reproducible script, not all research traffic.

## Reproduce / next action

```bash
python -m scripts.research_slovak_gap_supply --root NEW_ISOLATED_ROOT
python -m scripts.research_slovak_gap_supply --root NEW_ISOLATED_ROOT --verify-local
python -m pytest -q tests/test_slovak_gap_supply.py
```

Two tests passed: exact matching/ambiguity rejection and changed-input refusal.
The independent crosscheck records its script hash and input hashes. No native
render preflight was needed because zero candidate pairs were created.

Main/Tesla should retain these three gaps as **no available supply under selected
sources**, not a permanent language-pair impossibility. A next step would need
new authoritative rights evidence and an actual qualifying parallel release or
exact English anchor overlap. Any such future addition must be isolated,
deduplicated against both base and existing additive candidates, checked in both
directions with the native student renderer, and audited before queue admission.
No changes to production inputs, existing release selection or target budgets.
