---
type: Runbook
title: DFM12 Structure-Preserving Reordering Sources
description: Isolated native Wikipedia paragraph recovery and explicitly synthetic sentence-block fallback for NB, NN, SV and NL.
tags: [dfm12, paragraphs, wikipedia, provenance, cpu, synthetic-boundaries]
status: draft
last_updated: 2026-09-24
confidence: high
---
# DFM12 Structure-Preserving Reordering Sources

Related: [paragraph repair](dfm12-paragraph-repair.md),
[components](dfm12-components.md), [status](dfm12-status.md).
This task owns new source-specific modules, tests, this page and isolated data
roots only. Parent maintains indexes/status/log integration. No shared candidate,
accepted, audit queue, training, evaluation, GPU or final sampling changes.

## Scope and Updated Authorization

The earlier paragraph repair correctly refused to invent source paragraphs.
**Superseded restriction, 2026-09-24:** the owner subsequently authorized a
separate fallback that groups contiguous sentences from the same document into
multi-sentence text blocks. This does not authorize calling synthetic blocks
native paragraphs. Native recovery stays preferred; fallback has task
`text-block-reordering`, `synthetic_boundaries: true`, its own IDs and native
language prompts saying text blocks. The target preserves source sentence order.
Do not silently merge it into `paragraph-reordering` statistics or accepted data.
The NN prompt's `blokkene` is a valid feminine definite plural, not an accidental
Bokmal substitution; checked against [Nynorskordboka](https://ordbokene.no/nob/nn/6876).

Owner authorization covers all DynaWord/DynaInstruct licenses. Alternate
Wikipedia releases were also reviewed independently as named encyclopedic
sources with attribution/share-alike notices; this is not unrestricted web
mining. Quality, language, contamination and source deduplication remain gates.

## Pinned Ingestion Evidence

Evidence files and retrieval/hash receipts are in each native run's `evidence/`.
The inspected DynaWord revisions remain:

- Norwegian: `2bc33815865fb3d610e2a080b19156db8e98feef`.
- Swedish: `f7cf2952b597eee76d8a3bddaa732ca6788b51c1`.

Norwegian `data/wikipedia-{nob,nno}/create.py` loads `NbAiLab/NCC` revision
`857a5832b73ef33c66b5674d970777c39d991c0e`, selects
`wikipedia_download_nbo` / `wikipedia_download_nno`, copies `text` unchanged,
removes NCC IDs, and assigns synthetic DynaWord IDs. This does not recover lost
paragraphs or original page IDs. The Bokmal datasheet's filtering prose says
Nynorsk, but its actual filter is `nbo`; the code is the stronger evidence.

Swedish `wikipedia-sv/create.py` and both selected Riksdagen importers iterate
sentences and join them with spaces. The parliamentary sources are explicitly
historical bicameral records, not clean modern parliamentary prose. They remain
excluded here; no OCR restoration or sentence-to-paragraph relabeling is used.

## Structured Upstreams and Rights

### Wikimedia Article Release

`wikimedia/wikipedia`, revision
`b04c8d1ceb2f5cd4588862100d08de323dccfbaa`, configs `20231101.no`,
`20231101.nn`, `20231101.sv`: nine parquet files, all downloaded and verified
against their HF LFS SHA256 values. They retain article `id`, `url`, `title`,
and blank-line-separated prose. This is an **alternate 2023 source release**,
not exact restoration of the NCC 2021 / Sprakbanken 2022 DynaWord snapshots.

The [pinned release card](https://huggingface.co/datasets/wikimedia/wikipedia/blob/b04c8d1ceb2f5cd4588862100d08de323dccfbaa/README.md)
describes cleaned Wikipedia dump articles and declares CC-BY-SA-3.0/GFDL.
Retain article attribution, history links and upstream notices; do not propagate
the Norwegian DynaWord constituent's CC0 label onto Wikipedia article text.
Current [publisher terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)
refer to CC-BY-SA-4.0; the older release-card declaration is recorded as evidence,
not a claim that this task can relicense individual revisions or waive share-alike.

Variant mapping is source-specific: `no.wikipedia.org` is explicitly configured
as `nb` in Wikimedia's `wgLanguageCode` (`nowiki => nb`), verified in the archived
`InitialiseSettings.php`; `nn` and `sv` are separate editions. This is not a
generic Norwegian-to-Bokmal mapping or row-level language certification.
URLs must match the expected edition exactly. The archived legacy Wikipedia
cleaner preserves within-section blank lines and joins sections with blank lines;
it is useful mechanism evidence, **not a verified build script for this release**.

### Original Swedish XML

The exact URL used by the pinned Swedish importer is still available:
`https://spraakbanken.gu.se/resurser/meningsmangder/wikipedia-sv.xml.bz2`.
The current response is a newer release (annotation header 2026-08-13), with
explicit `paragraph` elements, `_id`, `url`, article `permalink` revisions, and
encoded token `_tail` spacing. The resource page now cites DOI
`10.23695/7dz6-ek80`, updated 2026-08-17, and labels its download CC-BY-4.0.
The pinned DynaWord datasheet labels Wikipedia CC-BY-SA-4.0; preserve Wikipedia
share-alike obligations as well as distributor attribution rather than silently
choosing the weaker label. See the archived `source-card.html` and
[current resource](https://sprakbanken.se/en/resources/wikipedia-sv).

The adapter only consumes direct, explicit XML paragraphs. Header/list/table
blocks remain barriers. It decodes documented whitespace escapes, not guessed
punctuation spacing. Sparv's exporter at commit
`cde410113ef3d696a1013076c3dc375b13eea17c` omits empty attributes: missing `_tail`
can mean adjacency, but missing word-to-word spacing is conservatively rejected.
Unknown escapes and unsupported XML nesting fail closed. The exporter source is
archived as `sparv-xml-utils.py`.

## Adapter Contracts

`dfm12/structure_preserving.py` and `dfm12/cpu_structure_preserving.py`:

- Exactly three distinct, contiguous, complete native blocks; no truncation,
  section crossing, heading deletion or sentence fallback.
- At least 120 characters / 20 words per block, terminal punctuation, prose
  character ratio, no residual markup or ambiguous embedded single line breaks.
- Reject observed missing-template-value artifacts and Swedish formulaic bot
  geography. Spot checks exposed these in initial structural-only candidates;
  structural eligibility alone was insufficient.
- Store source repo/revision, file SHA256, absolute row ordinal, original ID/URL,
  attribution/history, source-text/document hashes and exact block spans.
- Actual DFM11 current Gemma tokenizer/template rendering must fit 4096 tokens;
  tokenizer and template hashes are recorded. One candidate per source document,
  exact document/window deduplication, deterministic eligible-candidate ranking.
- Exclusive new output roots. No source quota borrowing into unrelated corpora.

`dfm12/sentence_blocks.py` and `dfm12/cpu_sentence_blocks.py`:

- NLTK 3.9.4 pretrained Punkt Norwegian, Swedish and Dutch models, already
  installed locally; model-file SHA256 receipts and abbreviation overrides saved.
- Norwegian model is shared by NB/NN, **not a separately trained NN model**.
  Native-language regression probes cover `f.eks.`, `t.d.`, `m.a.`, `t.ex.`,
  `bijv.`, titles and closing quotes; language/variant audit remains mandatory.
- Length-preserving quote normalization is used only for segmentation offsets;
  returned source text is unchanged. No generic regex sentence splitter.
- Six adjacent complete sentences become three distinct blocks of two sentences.
  Each sentence requires six words, 35-1200 characters, a capitalized start,
  terminal punctuation, balanced quotes/parentheses, and no markup/ellipsis/hole
  artifacts. Invalid fragments and real line/paragraph/heading breaks are barriers.
- Require identical Punkt spans in document context and in each isolated block.
  Replay found 17 context-unstable candidates in fallback v2 (mostly quotes or
  abbreviations at block ends); v2 is diagnostic only. Rebuilt v3 rejects these
  boundaries and may choose another stable window in the same document.
- NB/NN/SV fallback is taken inside a single eligible source prose block and
  skips documents with any structurally viable native three-paragraph window.
  NL uses only the already reviewed DynaWord government constituent
  `data/dienst_publiek_en_communicatie/data.parquet`, with its reviewed single-line
  native-paragraph check first. No parliamentary OCR, social or mined corpus fill.
- Save all six sentence spans, three block spans, exact source excerpt and
  explicit synthetic-boundary metadata. IDs/task differ from native paragraph
  reordering; actual rendered length must still be <=4096.
- NL DynaWord rows lack original URLs. Preserve their IDs/file ordinals/hashes;
  this limitation is explicit in provenance, not filled with invented URLs.

## Completed Preparation

All counts below are **unaudited candidates**, not accepted data or exhaustion.
The wide scan uses prefixes of up to 64 evenly spread parquet row groups, up to
50,000 rows per file. NN supplied 49,872 because the final group was small.

| Language | Rows inspected | Native paragraphs | Separate sentence blocks | Native candidate gap to nominal 22,516 |
| --- | ---: | ---: | ---: | ---: |
| NB | 150,000 | 21,731 | 5,320 | 785 |
| NN | 49,872 | 6,570 | 1,798 | 15,946 |
| SV | 250,000 | 11,768 | 3,525 | 10,748 |
| NL | 50,000 fallback-only | Not rebuilt here | 4,968 | Not assessed here |

Native total: **40,069**. Separate fallback total: **15,611**. Accepted: **zero**;
the accepted target still needs auditing, not merely raw candidate volume.
Fallback volumes do not erase native-paragraph shortfalls. Prior NL repair's
1,014 candidates remain unchanged and must not be blindly added to new pools.

Native quality filter rejected 28,371 scanned Swedish documents for formulaic
bot geography/markers. The narrower Swedish XML prefix independently inspected
2,000 documents (4,390,912 compressed response bytes): 1,844 had supported
explicit paragraph layouts, 156 had unsupported layouts, and **191 candidates**
were produced. This alternative pool overlaps the Wikipedia source universe;
do not add its count without cross-release URL/text deduplication.
Measured overlap: 13 canonicalized article URLs and nine identical normalized
windows with the native SV pool. Redirects, renames and semantic overlap remain
unchecked; the 191 XML candidates stay an alternative pool, not additive supply.

## Paths and Commands

Handoff roots:

- Native: `data/dfm12-structure-preserving-20260924-v3/candidates/{nb,nn,sv}/`.
- Fallback: `data/dfm12-sentence-blocks-20260924-v3/candidates/{nb,nn,sv,nl}/`.
- Original Swedish XML probe: `data/dfm12-sparv-paragraphs-20260924-v3/`.

Each has receipts, candidate JSONL, process records and a sibling `.log` file.
Native v3 uses read-only symlinks to SHA256-verified downloads in native v1.
**Keep native v1 downloads** even though its candidates are diagnostic only.
The XML probe preserves a compressed **prefix**, not a complete bz2 archive,
plus replayable complete XML elements in `complete-text-elements.jsonl.gz`.

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.cpu_structure_preserving \
  --output data/dfm12-structure-preserving-20260924-v3 \
  --reuse-downloads data/dfm12-structure-preserving-20260924-v1/downloads

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.cpu_sentence_blocks \
  --output data/dfm12-sentence-blocks-20260924-v3 \
  --native-root data/dfm12-structure-preserving-20260924-v3
```

These commands refuse existing roots; use a new path for another run. Actual
launches used detached sessions with null stdin. Native v3 PID 709889, fallback
v3 PID 737064 and XML v3 PID 717620 all completed; no processes remain from
those preparation launches. Diagnostic native v1/v2 and fallback v1/v2 are marked
`diagnostic-only.json`; fallback v1 was stopped by its owning task before reuse.
XML v1/v2 strict-spacing probes returned zero and are superseded by v3's verified
empty-attribute handling. None of these candidate generations are additive.

## Verification and Remaining Work

Focused and inherited regression command:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest \
  tests/test_dfm12_structure_preserving.py tests/test_dfm12_sentence_blocks.py \
  tests/test_dfm12_paragraph_repair.py tests/test_dfm12.py -q
```

104 tests passed. Tests include source-span fidelity, immutable outputs,
no heading/fragment bridging, no fabricated native boundaries, duplicate blocks,
abbreviations, quote handling, exact two-sentence blocks and real tokenizer limits.

Replay verifier:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.verify_structure_preserving \
  --native-root data/dfm12-structure-preserving-20260924-v3 \
  --fallback-root data/dfm12-sentence-blocks-20260924-v3 \
  --sparv-root data/dfm12-sparv-paragraphs-20260924-v3
```

Per-component `verification.json` records completed source replay, exact source
spans, distinct IDs, message validity and re-rendered token lengths. Cross-pool
verification checks that no Wikipedia document is used in both native and
fallback outputs. This is structural verification, **not quality certification**.
Completed replay: all 40,069 native, 15,611 fallback and 191 XML candidates
passed. Native rendered maxima: NB 3,136, NN 2,394, SV 3,234 tokens. Fallback
maxima: NB 935, NN 1,053, SV 1,071, NL 895. XML also passed the <=4,096 check.
Wikipedia native/fallback document overlap is zero; NL fallback also has zero
source-ID overlap with the prior 1,014-row native NL repair output.

`python scripts/validate_okf.py wiki` checked this page without schema/link errors
inside the page, but exited with two missing immediate-child index links:
this page and the concurrently authored `dfm12-scandi-translated-instruct.md`.
Index maintenance is deliberately left to the parent; no shared index was edited.

Remaining: independent language/variant/coherence audit; benchmark and inherited
content contamination checks; semantic and cross-release deduplication; broader
reviewed coverage, particularly NN; explicit parent approval before integration.

## Full Reviewed Scan and Integration, 2026-09-24

**Superseded scope restriction:** the owner subsequently authorized CPU volume
expansion and isolated integration/deduplication of originals, native repairs
and synthetic blocks. The preceding bounded-run counts remain historical,
not additive. This does not authorize final sampling, accepted-row promotion,
training/evaluation changes or replacement of shared outputs.

New modules are `dfm12/reordering_sources.py`,
`dfm12/cpu_reordering_expand.py`, `dfm12/reordering_integration.py` and
`dfm12/verify_reordering_integration.py`; focused tests are
`tests/test_dfm12_reordering_integration.py`. The source registry restricts NL
to the five already selected constituents (government communications, European
Parliament, Naturalis, PBL, Wikiwijs). Only the reviewed government constituent
uses individual newline paragraph boundaries; the others require actual blank
lines or paragraph separators. Dutch fallback remains government-only.

Expansion scans every row in the named local pinned releases: NN 167,653,
NB 617,937, SV 2,574,513, NL 250,549. This is exhaustion of these release files,
not exhaustion of all potentially eligible sources. Candidate caps are 45,032
per language/task, hash-ranked across the complete scan, not final sampling.
Every admissible document is offered to the native adapter first; synthetic fallback is
attempted only if no fitting native window survives. Existing prose, bot,
sentence completeness and exact current Gemma4 rendering limits remain active.

The integration replays original source rows/XML, exact spans, native prompts
and deterministic targets before admitting records. Native records precede all
synthetic records; within native records, explicit Swedish XML precedes the
expanded release, then prior native repairs and originals. Exact transitive
deduplication covers IDs, source identities, normalized answers/full source
documents, and canonical Wikipedia article URLs. XML full-document text is not
used as a dedup key because rejected XML layouts need not be fully reconstructed.
No semantic equivalence or independent quality certification is claimed.

All original fields and provenance are retained on surviving rows; added
`integration` lineage identifies the input checksum, row and original-record
hash. Dropped duplicates retain provenance in `duplicates.jsonl`; incompatible
originals go to `quarantine.jsonl`, never back into modified accepted/original
files. SQLite staging supports accounting and transitive duplicate resolution.
Input/source hashes are checked again after integration. Independent export
verification repeats source replay and real rendering and checks cross-pool
duplicates, retained winner IDs and complete input accounting.

Expansion process PID 973921 completed, writing only
`data/dfm12-reordering-expanded-20260924-v1/`, with a sibling `.log`,
`process.json`, `sources.json` and per-language receipts. NN and NL completed
first: respectively 23,193/6,109 and 44,375/16,139 native/synthetic candidates.
SV retained 45,032/36,289 and NB 45,032/21,651. Before the native cap,
SV had 120,791 eligible native windows and NB 88,964. Across all four languages,
3,610,652 source rows were scanned. Integration PID 1013830 writes a new
`data/dfm12-reordering-integrated-20260924-v1/` root and sibling `.log`.
Final deduplicated counts are recorded below after verification; expanded
counts must not be added to the older pools.

Reproduction (each preparation/integration root must be new):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.cpu_reordering_expand \
  --output data/dfm12-reordering-expanded-20260924-v1

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.reordering_integration \
  --expanded data/dfm12-reordering-expanded-20260924-v1 \
  --output data/dfm12-reordering-integrated-20260924-v1

CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.verify_reordering_integration \
  --root data/dfm12-reordering-integrated-20260924-v1
```

Spot review, not a representative quality audit, found three source-level
exclusions. NN Wikipedia IDs `389875` and `170472` contain respectively a
missing timeline value (`fram til januar 561`) and malformed chart position
(`trettandeokaseb`); Dutch `dienst_publiek_en_communicatie_72537` is a newsletter
window switching from patient deductibles to ambulance regulation. Integration
quarantines these exact revision-qualified document IDs, retaining the reason
and provenance; it does not silently repair their text. Remaining candidates
still require independent language, coherence, extraction-damage and
contamination review.

Replay of older Dutch pools admitted 302 of 1,014 prior repairs to deduplication;
712 failed `no_exact_contiguous_quality_native_window`. All 415 paragraph rows
in the original mixed Dutch candidate file failed the same stricter gate.
This combines exact native-boundary/contiguity checks with the current prose
threshold and rejection of embedded line breaks/markup. It is not a finding
that all 1,127 underlying documents are unusable. Their original files remain
unchanged and their IDs, source provenance and reasons remain in quarantine.
The original Norwegian and Swedish mixed pools contain zero paragraph rows.

The reviewed Norwegian source selection contains only `wikipedia-nno` and
`wikipedia-nob`; there is no additional already-selected clean NN constituent
to scan. Reusing an older flattened Wikipedia release without recovering
article identity risks cross-release duplication and is not claimed as new
headroom. The full NN release scan therefore remains a finite source-volume
constraint, not a reason to relax the structural or source policy.

### Integrated Candidate Counts

Integration PID 1013830 completed successfully. The isolated integrated receipt
records 1,075,525 input rows examined, of which 295,120 are in-scope reordering
rows: 293,989 passed replay, 1,131 were quarantined, 37,629 valid duplicates
were removed and 256,360 candidates remain. No original row was rewritten.

| Language | Native `paragraph-reordering` | Synthetic `text-block-reordering` |
| --- | ---: | ---: |
| NB | 55,757 | 21,651 |
| NN | 23,192 | 6,108 |
| SV | 52,636 | 36,279 |
| NL | 44,344 | 16,393 |
| Total | 175,929 | 80,431 |

These are **unaudited candidates, zero accepted rows**, not additive to the
prior/expanded pools. Every language has more native candidates than the
22,516 nominal accepted-row target, but NN has only 676 native rows of margin
before audit losses. NN is 10,582 native rows below the 33,774 audit-headroom
target, or 4,474 below even when its separately labeled approved fallback is
included. NB, SV and NL exceed that headroom with native candidates alone.
Do not silently relabel fallback rows to make a native-only quota look met.

Of the 1,131 quarantined rows, 1,127 are the earlier Dutch gate failures;
four rows represent the three explicit spot-review exclusions (one NN article
occurs in both expanded and older fallback inputs). All reasons and source
identities are retained. Exact deduplication is transitive and cross-pool within
each language, not semantic or benchmark decontamination.

Handoff layout:

- `data/dfm12-reordering-integrated-20260924-v1/candidates/{nb,nn,sv,nl}/`:
  separate `paragraph-reordering.jsonl` and `text-block-reordering.jsonl`.
- `receipt.json`, `inputs.json`, `sources.json`, `process.json`: counts,
  implementation hashes, input/source checksums, source policy and process ID.
- `duplicates.jsonl`, `quarantine.jsonl`, `integration.sqlite`: complete
  dropped-record provenance and staging/accounting evidence.
- Sibling `data/dfm12-reordering-integrated-20260924-v1.log`: integration log.
- Independent verifier PID 1030482 completed successfully, using `verification-process.json` and sibling
  `data/dfm12-reordering-integrated-20260924-v1.verification.log`; its final
  `verification.json` is the source-replay/export verification completion gate.

The full focused/inherited test run now has 114 passing tests, adding source
checksums, full-scan accounting, native preference, late-bridge deduplication,
quarantine accounting, lineage preservation, immutable outputs and modified-file
rejection to the earlier paragraph/sentence tests. An intermediate OKF validation found
three parent-owned missing index links (`dfm12-audit-readiness.md`,
`dfm12-dala-registration.md`, `dfm12-token-accounting.md`), with no error in this
focused page. The final check reports **0 errors and 0 warnings** after those
index gaps were resolved. Central status/index/log files remain untouched by this task.

Independent verification completed at `2026-09-24T10:51:22Z`: all 256,360
exports replay their source, all current Gemma4 renderings fit <=4,096, exact
cross-pool duplicate count is zero, and input/source hashes are unchanged.
Observed native/synthetic token maxima: NB 3,211/1,311; NN 2,813/1,053;
SV 3,537/1,627; NL 3,533/1,884. The current tokenizer/template hashes also
match the integrated receipt. All three process IDs above have exited.
`artifact-checksums.json` records checksums for 17 completed output files and all three logs,
including duplicate/quarantine ledgers and SQLite provenance.

Retained lineage includes, beyond expanded survivors, 10,725 older NB native
repairs, 7,459 older SV native repairs, all 191 SV XML records, four older Dutch
European Parliament native repairs and 256 older NL fallback records. This is
why the final counts differ from simply replacing the older pools with the
expanded ones. Duplicates are not counted twice and synthetic tasks keep their
original labels. No final sampling, accepted export, GPU, training/evaluation
change, shared-output overwrite or old-output deletion was performed.

Remaining gates: independent row-level language/variant/coherence audit,
extraction-damage review, benchmark/inherited-content contamination checks and
semantic deduplication. NN still lacks the stated audit headroom; this completed
CPU handoff does not claim all accepted-row targets are fulfilled.
