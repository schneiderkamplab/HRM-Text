# Original-Keep Manual Spot Check, 2026-10-01

## Handoff To Parent And Epicurus

CPU/manual review only. **7 retain, 2 localized repair concerns, 1 needs factual
verification.** No blanket reject finding, production mutation, generated
correction, GPU/model request or admission change. These are ten source-
stratified observations, not an estimate of whole-corpus precision or proof that
repairs are better/worse. No corrected answers were inspected.

Artifacts:
- `data/dfm13/original-keep-manual10-20261001-v1/manifest.json`
- `data/dfm13/original-keep-manual10-20261001-v1/samples.jsonl` (full original conversations)
- `data/dfm13/original-keep-manual10-20261001-v1/manual-review.json` (per-dimension findings, uncertainty and repair risks)

The baseline ledger is
`logs/arena_audit/20261001-bulk205242-reasonfirst-thinking-v3/ledger.sqlite`.
Epicurus's repair artifacts remain separate under
`logs/arena_audit/20261001-repairs-followup-v1`; this report does not alter or
authorize that campaign. Use original source IDs to join, not sample numbers.

## Selection And Evidence

Read-only SQLite transaction; no pending/inflight jobs at selection. Only
`status=complete` and `result.semantic_decision=keep` enter the sampling frame.
Rows are fetched from the original exported source bytes at ledger offsets,
not any repair/correction directory. All four complete source-file SHA256
values match the audit manifest; selected IDs match the ledger. Selected audit
result strings are hashed, but their judge reasons were not used for manual
ratings. The original keep label is known, so this is not verdict-blind.

Seed `dfm13-original-keep-manual10-20261001-v1`; within each source sort ascending
by SHA256 of `seed|source_index|source_id`, take fixed quotas 3/3/2/2 in manifest
order. Quotas and seed were chosen before reading selected answers. No language,
length, difficulty or content replacement. Source keep populations: AI-Arenaen
2,094; 100K 45,812; 140K 82,382; 55K 25,598. This deliberately overrepresents the
small Danish source and is not population-proportional. All 10 target answers
and full preceding messages were read; sample 2 has 14 messages, target index13.

## Findings By Sample

| # | Source | Exact source ID | Disposition | Bounded finding |
| --- | --- | --- | --- | --- |
| 1 | AI-Arenaen | `3fd08086-1020-4a69-b731-1c805e1a8692:b` | Retain | Useful Danish meeting workflow with consent, confidentiality and human-review caveats. Product feature entitlements not exhaustively checked. |
| 2 | AI-Arenaen | `67d26cbc-75a1-45af-942d-2ba1c632ba4d:a` | Retain, caveat | Interprets supplied feature ranking and warns about overfitting/leakage; calling power deviation the most real pattern is overconfident, not proof of causality. Older assistant code is not this target. |
| 3 | AI-Arenaen | `11400852-0b7b-40df-92ad-9840b3f21988:b` | Needs verification | Emissions arithmetic is consistent; route-specific factors and multiplier remain unverified, not proven false. |
| 4 | 100K | `arena_human_preference_100k:bc167de9a17c40c9b84f4c2a0f2940da:a` | Retain | Correctly asks for location instead of inventing whether it is rainy season locally. |
| 5 | 100K | `arena_human_preference_100k:3e88636a07934fbda33525ee565b5566:b` | Retain | Requested fictional scene and flight reminiscence are present; no demand for unrequested canon completeness. |
| 6 | 100K | `arena_human_preference_100k:0ac6649e21cd43f385484d47c1360a69:a` | Localized repair | Expanded internship account asserts specific forms, approvals and prepared presentations not supplied by the user. These are unsupported, not established false. |
| 7 | 140K | `arena_human_preference_140k:4a18c30a-20b5-4583-aa8e-5493d9c8f80b:a` | Retain | Accurate, restrained explanation of supplied innuendo. |
| 8 | 140K | `arena_human_preference_140k:51203302-0914-4c7f-a621-e5f6db4d758c:b` | Localized repair | Illustrative `Length:16` for `alice@example.com` is inconsistent with its 17 ASCII bytes. Novel conceptual format is appropriate to request. |
| 9 | 55K | `arena_human_preference_55k:2159119873:b` | Retain | Grammatical rephrasing preserves the technical meaning. |
| 10 | 55K | `arena_human_preference_55k:521212002:b` | Retain, style caveat | Both requested email versions provided and core qualifications preserved; ceremonious phrasing alone does not justify a semantic rejection. |

For sample 3, 1,750 times 0.09..0.14 is 157.5..245 kg, consistent with the rounded
calculation. ICAO's [calculator methodology overview](https://www.icao.int/environmental-protection/environmental-tools/icec?target=_blank)
confirms dependence on aircraft, route and load factors; it does **not** verify
this sample's 150..250 kg estimate. No paid calculator/API call was made.

For sample 8, CPU `len('alice@example.com'.encode('utf-8'))` returned **17**.
The format's units are not formally specified, so the safest repair is to make
the example's byte-count convention explicit and use 17, not claim a tested
binary implementation is broken. A coarse comparison table and broad design
goals were not turned into additional invented defects.

## Baseline Versus Repair Risk

Preserve useful correct content and caveats. For #6, qualify only the unsupported
autobiographical specifics; the user did request substantial elaboration, so
removing all explanatory prose would also be wrong. For #8, correct the local
encoding example without replacing the whole creative design. For #3, establish
a dated, scoped methodology before substituting any number. For the seven
retained examples, no mandatory rewrite is supported by this spot check.

No empirical original-versus-corrected comparison was performed. The two
localized concerns are not a 20% catastrophic-failure estimate, and the one
uncertain example is not counted as a confirmed false acceptance.
