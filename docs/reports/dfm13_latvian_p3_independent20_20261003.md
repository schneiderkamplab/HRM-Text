# Latvian P3 independent 20-row assessment

2026-10-03. Manual assistant assessment, without a second model or generation
calls. This is not native-speaker gold and not a population quality estimate.

## Scope And Publication State

The publisher had already completed when this review began. Both v1 license
partitions were uploaded, registered and subsequently tokenized:

| Partition | Rows | HF revision |
| --- | ---: | --- |
| CC BY 4.0 | 4,480 | `dd39d2e75964de419df9ab38ac66d511bea3b756` |
| CC BY-SA 4.0 | 3,200 | `4bd0277b998dd85b0df21949ceb4ecfaaa666f67` |

Repositories are `schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-4-0` and
`schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-sa-4-0`. The completion receipt is
`exports_dfm13/latvian-p3-publication-20261003-v1/integrated.json`.
No published files, active registry entries, token arrays or quality-ledger
decisions were changed by this review. Holds are a separate, hash-bound sidecar.

Selection was fixed before reading answers: independently within each of four
constituents and two quality strata, sort by
`dfm12.io.digest(['p3-manual20-20261003', row.id])`; take three repaired and two
originally accepted rows per constituent. Thus 20 rows: 12 repairs, 8 originals.
All full questions, choices and answers were read, not just verdicts or snippets.

Evidence directory: `data/dfm13/latvian-p3-independent20-20261003/`.
`sample.json` pins published source files and exact selected record hashes.
`sample-with-source.json` includes each original translated Parquet row.
`sample-with-english.json` adds all 20 English P3 references, fetched at matching
configuration/train ordinals from the public HF dataset-server. The English
snapshots are individually hashed under `english/`; they are retrieved current
views, not claimed to be the translation's original revision. The question and
choice content was compared, rather than assuming ordinal alignment proves it.

## Findings

**8 scoped holds and 12 rows without a hard hold** in this deliberately stratified
sample. Holds comprise six repaired and two originally accepted rows. They are
not eight equally certain wrong answer keys: the sidecar separates answer errors,
unmet instructions, missing context, source translation defects and language
defects. Minor morphology/wording warnings are not counted as hard failures.

| Sample | ID prefix | Decision | Independent finding |
| ---: | --- | --- | --- |
| 0 | `f0c72ffdcbba` | No hard hold | Cells/D is the intended school-level distinction; repair changes source numeric 4 to D correctly. |
| 1 | `cabad4ec7a4b` | Minor wording | Cellular respiration releases usable energy/A; repaired explanation is correct. User has a Latvian genitive error and answer repeats wording, not a substantive error. |
| 2 | `e4ad9482378a` | Hold: source fidelity | C is correct, but English option B says bacteria **do not contain DNA**; Latvian says they **contain DNA**. A negation was lost before repair. Do not label the repaired C itself factually wrong. |
| 3 | `e98970108402` | No hard hold | Coffee inertia/A; supplied options and intended explanation preserved. |
| 4 | `f69ac73a4592` | Hold: translation review | English explicitly asks about gaps in the **fossil record**. Latvian substitutes a series of mineral/excavated finds, with malformed rock-case endings. D fits the English fossil question, but the translated scientific term requires correction, not blind answer replacement. |
| 5 | `007b1864ec47` | No hard hold | Small-dog breeding is selective breeding/C. Redundant terminology does not alter the concept. |
| 6 | `6ed7dcc13ef1` | Hold: changed construct | English asks for a **learned** trait, A/reading. Translation asks for an **acquired** trait, where both reading and a scar are plausible. Repair changes A to C; this is not a uniquely justified correction. Restore the prompt construct before choosing a target. |
| 7 | `d8272a6ad87a` | Wording warning | Competition for food/B is correct. Distractor A's Latvian word for decomposers is malformed; answer remains supported. Polish/recheck that distractor rather than asserting wrong answer. |
| 8 | `b99ad36b70ac` | No hard hold | Flower/A produces seeds in the intended elementary flowering-plant question. |
| 9 | `feb4454e1457` | No hard hold | Strawberry roots/D absorb water. |
| 10 | `0b0625f1e230` | Conditional-context keep | Answer follows the supplied larger-alkene/lower-temperature premise and matches English P3. The premise is unusual as real-world chemistry; this is passage-conditioned reasoning, not proof the repair invented a false relation. Do not force a context-contradicting answer to satisfy outside knowledge. |
| 11 | `1ac4caa22d79` | No hard hold | Adding citric acid raises acid levels. The paragraph concerns acid strength rather than added amount, so it is weak task evidence, but the answer is reasonable and matches English. |
| 12 | `c094565ef199` | Hold: missing premise | English says Joe's urine **was almost black**. Latvian omits that observation while asking for Joe's water content. Repair answers low without the necessary case fact. |
| 13 | `60910e0ef57a` | Minor wording | Faster flow/increased energy matches context. Latvian answer uses a transitive form instead of the question's intransitive form; meaning remains clear. |
| 14 | `c950bd37d3de` | No hard hold | Less food, lower mass/inertia, easier to move; supported by text. |
| 15 | `1fac18500801` | Hold: repair introduced factual error | Hank Baskett is assigned to Philadelphia **76ers**. English and original translated source say **Eagles**; independent official 2010 NFL records confirm the sport/team error. |
| 16 | `49a93f79cb6d` | Hold: nonanswer | Asked **which years** Steelers won; repair says **six times**, supplying no years. The old English target, Super Bowl X, was also incomplete. |
| 17 | `fcf204b55c5a` | Hold: malformed invented description | Bosnian is called “slavenā dižvaloda” (a famous/grand language), an unsupported and unnatural description. The later Slavic/Serbian/Croatian relationship sentence does not cure it. Old source target “Serbian language” is also not a sound replacement. |
| 18 | `4fb65f008240` | No hard hold | Lorne in Angel: Andy Hallett; matches source and known role. No material language issue identified. |
| 19 | `b8fef7e39b2b` | Hold: inherited historical error | Baltimore Colts/AFC South is inherited from English, not introduced by repair. Official franchise history identifies AFC East in the Baltimore AFC era. The question also lacks a precise era; do not substitute today's Indianapolis division. |

## Primary Factual Cross-Checks

- [Eagles 2010 transactions](https://www.philadelphiaeagles.com/team/transactions/2010)
  record Hank Baskett's March signing and September release as a wide receiver.
  [NFL's 2010 Vikings roster](https://www.nfl.com/sitemap/html/rosters/2010/minnesota-vikings)
  also lists him. A corrected answer should account for the within-2010 team
  change rather than simply treating a single old KB answer as exhaustive.
- [Steelers Super Bowl history](https://www.steelers.com/history/super-bowls/)
  supplies game dates. A fresh target can state calendar years 1975, 1976, 1979,
  1980, 2006 and 2009, explicitly distinguishing season years if needed. Existing
  answer fails even without resolving this convention: it provides no years.
- [Colts' official 1970s history](https://www.colts.com/team/history/by-the-decade/1970s)
  places the Baltimore club in the AFC Eastern Division. Earlier pre-merger
  affiliations make explicit temporal scope preferable to an unqualified rewrite.

## Versioned Correction Proposal

Create a new release revision/artifact, never edit v1 in place. The immediate
conservative option is to exclude these eight exact record hashes: five CC BY
rows and three CC BY-SA rows, yielding 4,475 and 3,197 rows respectively if there
are no other changes. This arithmetic is a proposed filtered population, not a
claim that a v2 corpus was built or that all remaining rows are clean.

For rehabilitation, source-prompt defects (2, 4, 6, 12) require a distinct
English-grounded retranslation candidate and fresh review; assistant-only repair
cannot restore the missing/damaged input. Answer defects (15-17) require short,
source-grounded targets and a new quality decision. Row 19 requires historical
scope, not an unquestioned copy of the original answer. Keep old IDs/parent
hashes, English evidence and the exact correction reason in new provenance.

Coordinate with the registry/tokenizer owner before any replacement: v1 is
already tokenized under immutable source hashes. Use new versioned source names
and tokenization roots, and a new pinned HF commit or explicitly versioned repo.
Retire v1 from future sampling using an explicit supersession/repeat policy only
after v2 verifies; never change the payload behind a tokenizer's existing name.
Do not admit both versions simultaneously. Carry these exact hash-bound holds
into the next assembly rather than silently treating uploaded/auto-reviewed as
semantically clean. No registry or watcher edits are performed by this report.
