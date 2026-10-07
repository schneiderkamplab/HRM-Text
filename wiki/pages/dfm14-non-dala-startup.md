---
type: Plan
title: DFM14 Non-DaLA Startup
description: Local readiness, reusable code, concrete blockers and a staged implementation sequence for DFM14 excluding separately curated DaLA.
status: draft
confidence: high
last_updated: 2026-10-06
tags: [dfm14, data, generation, audit, implementation]
---
# DFM14 Non-DaLA Startup

## Grounding Preference and Completed CPU Pass (2026-10-06)

**Superseding decision later the same day:** Wikipedia is explicitly approved
as a grounding source. Delete the DFM14 broad-web downloads and derived
candidates, rather than retaining them on hold. Removed FineWeb-2,
FinePDFs-Edu, Irish FineWeb-Edu, Macedonian cleaned corpus, Cosmos Turkish,
Korean Webtext and Chinese FineWeb-Edu from the executable registry and all
three CPU preparation passes. Historical configuration/progress JSON remains
as provenance only; it is not an active source list or current row inventory.
Instruction/chat candidates are unchanged. Current coverage comes from the
surviving receipts, not the original progress counters. This cleanup is scoped
to DFM14 and does not change inherited training datasets.

Remaining prepared grounding for the sixteen extension languages is Wikipedia
only (829,222 document seeds); additional curated grounding is still needed for
breadth, particularly Maltese and Irish. These are bounded sampled documents,
not full Wikipedia sizes or audited acceptance counts. The separately selected
Faroese law and Polish educational subsets are outside these sixteen languages.

Owner clarification supersedes the broad-web fallback proposed below: prefer
curated, attributable educational, institutional and reference material for
grounding. Hold broad web-crawl candidates and their derived transformations
out of generation, audit campaigns and admission until explicitly reconsidered.
This includes FineWeb-2, FinePDFs-Edu, web-derived language corpora and mixed
corpora whose selected subset provenance has not been established. An educational
quality score or a successful conversion does not establish factual reliability,
privacy clearance or underlying-content rights. FinePDFs-Edu is not a non-web
alternative merely because its inputs are PDFs.

Keep existing candidate files and provenance receipts for inspection; do not
delete them or alter the historical preparation receipts. This is an admission
hold, not a claim that historical candidate preparation excluded these sources.
Wikipedia and explicitly selected educational/institutional DynaWord subsets
are preferred candidates, still requiring source review, deduplication,
decontamination and language/semantic audit. Seek alternatives for each language
before filling coverage gaps with general crawls.

The expanded CPU pass has finished (no preparation worker remains running):
247/269 file jobs prepared, 22 download failures due to access-denied responses,
and seven discovery holds. Completed receipts contain 1,010,915 instruction
candidates, 1,993,255 document seeds and 5,563,763 separate transformation
candidates. Counts are bounded, within-file-deduplicated candidates, not accepted
or globally unique rows. All sixteen target languages have instruction candidates.
The corpus has not been audited, admitted, tokenized or sampled as DFM14.

Artifacts: `data/dfm14/cpu-preparation-expanded/{progress,coverage}.json`
and per-file `candidates/*/*/receipt.json`. No further bulk preparation or GPU
audit was launched following the owner's request to wait.

## Scope and Observed State

This is the implementation assessment requested on October 6, not authorization
to launch the proposed production volumes. Follow the
[DFM14 plan](dfm14-plan.md) and
[independent-machine handoff](dfm14-remote-production-handoff.md).
DaLA remains a separately delivered component: it must not gate preparation,
generation, audit or publication of the other components. Final assembly must
state explicitly which approved components it includes.

The receiving checkout is `/work/dfm/HRM-Text`. The handoff's reference to
"this machine" training XL describes its `/work/mimir` authoring host; locally
the eight GPUs are occupied by DFM13 XXL-wide training. A full eight-server
generation campaign cannot be placed beside that training at 0.95 memory
utilization. Use a separately available machine, or arrange an explicit
checkpoint-boundary GPU handoff later. Do not pause training as a side effect
of preparation.

Local inspection found no `data/dfm14`, `logs/dfm14`, `exports_dfm14`, DFM14
source configuration or executable DFM14 campaign. `data/dfm12` is also absent.
There are local accepted transformation exports under `export/`, Gemma model
directories under `/work/dfm/brainsurgery/models`, and a frozen October 2 DFM13
build under `data/dfm13_build`. Directory presence is not a verified immutable
input receipt. In particular, that local 13-addition DFM13 sample is not the
later expanded DFM13 release and is insufficient as the sole deduplication
reference for DFM14.

## Code Reuse and Required Changes

### CPU Preparation Status Recheck (2026-10-06)

**Superseded later on October 6:** the owner authorized up to **320 CPU
workers**, then requested broader instruction and grounding-source coverage
for all sixteen languages. CPU preparation is now implemented and running;
the earlier not-started assessment below remains historical context.

The isolated `dfm14/` package and its [README](../../dfm14/README.md) document
the current bounded source-preparation pass. PID3169941 runs
`python -u -m dfm14.prepare --workers 320 --download-workers 8
--download-root data/dfm14/cpu-preparation-v1/downloads`, under `nice 10` in
the `hrm` environment, detached from this session. It uses no GPUs and does
not touch the live training sample or DaLA. Log:
`logs/dfm14/cpu-preparation-v2.log`; outputs/progress:
`data/dfm14/cpu-preparation-v2/`.

The expanded registry contains **117 components from 53 HF repositories**:
instruction/chat candidates across all sixteen languages, native Wikipedia,
FinePDFs-Edu and FineWeb2 language partitions, selected regional corpora,
Faroese/Polish Dyna increments and bounded Persian/knowledge candidates.
The first scan pinned payloads for 107 components, planning 264 files; absent,
oversized and gated sources are explicitly blocked, not assumed downloaded.
Viet4all and Infinity-Instruct returned access-denied responses with the current
credentials. Generic coverage tags and translated Alpaca supplements are not
evidence of native task breadth or independently accepted conversations.

Each component is currently bounded to eight deterministically selected files,
2 GiB downloaded, and 2,000 hash-sampled eligible rows per file. These are
**preparation/calibration samples, not final production quotas**. Full-source
expansion requires inspected adapters, deduplication and measured quality.
One process pool permits at most 320 workers (264 file jobs in this pass);
network concurrency is eight and internal tokenizer/Arrow/BLAS threads are one.
Per-file locks/atomic receipts and a parent-only manifest avoid output races.

The four transformation families are implemented as audit candidates with
original evidence: denoising, prefix continuation, span filling and paragraph
reordering. Corruption operates on graphemes; CJK splits at sentence boundaries;
reordering requires three real source paragraphs. Native prompt wording,
quality and grounding still require calibration/audit. None is accepted or
integrated into training yet. Parallel pairs and synthetic generation remain
separate pending stages.

The exploratory v1 pass was stopped and superseded after detecting serving
versus training-template incompatibility, JSON streams mislabeled `.json`,
and overly broad mixed-language file patterns. Its outputs are **not an
admission source**. V2 uses the exact inherited DFM13 native training template,
passes a render-prefix smoke before launch, preserves source system messages,
and holds unsupported tools/reasoning instead of silently flattening them.
Seven focused CPU tests passed, including Unicode reconstruction and format
handling. Running training remained active throughout.

Inspect measured (not declared) coverage with:

```bash
python -m dfm14.status --output data/dfm14/cpu-preparation-v2/coverage.json
```

Further source leads from the October 6 scan: `orai-nlp/MagpieEU` provides a
Basque translated instruction supplement; `BrainboxAI/medical-training-il`
has a Hebrew training subset, but its English exam-derived and persona records
must not be blindly included. These are follow-up candidates, not yet included
in the running immutable registry. Broad Hebrew instruction coverage remains
less established than the larger-language pools. Source links:
[MagpieEU](https://huggingface.co/datasets/orai-nlp/MagpieEU),
[medical-training-il](https://huggingface.co/datasets/BrainboxAI/medical-training-il).

**Earlier recheck, before implementation:**

The v2 pass subsequently **finished**, preparing 242/264 planned files with
326,687 instruction/document candidates. All sixteen languages had instruction
and grounding candidates. The 22 failed file downloads belonged to four gated
repositories: Viet4all, Infinity-Instruct, Matina Persian and IndustryInstruction.
There were no worker/file-conversion crashes in the corrected v2 pass;
source-specific schema/reasoning holds remain separately counted.

The active expanded pass supersedes v2's row selection (do not concatenate):
`data/dfm14/cpu-preparation-expanded`, log
`logs/dfm14/cpu-preparation-expanded.log`, PID3174464. It uses **20,000** sampled
eligible rows per file with the same 320-worker ceiling and eight downloads.
The registry is now **118 components/54 repositories**, including MagpieEU and
only the Hebrew Wikipedia subset of medical-training-il, excluding its English
exam/persona rows. Turkish CSV column mapping, Korean explicit role markers and
Zstandard JSONL support were added; nine focused tests passed. `zstandard`
0.25.0 was installed with `uv pip` in `hrm`. Native Gemma rendering is unchanged.
At the first expanded snapshot 111/269 files were prepared, 607,126 candidates
written, and preparation children used about 117 GiB RSS; live training still
ran at roughly 2.85 s/step. Counts are bounded candidate counts, not accepted
unique training examples or complete source sizes. The generated coverage
report measures actual instruction/document/transform rows by language.

**Original pre-implementation observation:**

After the explicit DFM13 training resume, the user asked whether non-DaLA CPU
preparation was complete. It was not: local inspection found no `dfm14`
package, `logs/dfm14` campaign, DFM14 source configuration or active preparation
process. The earlier request to fix and launch CPU preparation with at most
64 workers had not been executed. Source-candidate research for all sixteen
languages exists, but is not a pinned/downloaded/converted source inventory.
The separately progressing DaLA work under `/work/dfm/DaLA` is outside this
status assessment and was not touched. Implementing adapters and fixtures,
pinning inputs, preparing candidate shards and generating validation receipts
remain prerequisites before declaring the non-DaLA CPU work ready.

### Repository Counting Check (2026-10-06)

**Correction after token reconciliation, 2026-10-06:** the 776 count below
was wrong: it omitted the separate 381-source DFM12 inheritance list. Including
that list adds 369 distinct repositories (12 already appeared), giving **1,145
HF repositories**, of which **1,096 are schneiderkamplab**. The full sampled
epoch has **128,379,257,908 rendered tokens**, exactly matching the finalized
remote DFM13 metadata: 103,215,092,251 from DFM11, 13,993,793,261 from DFM12,
and 11,170,372,396 from DFM13 additions, with repeats applied. HF sources supply
127,776,823,803 tokens; DBC 289,036,655 and Lex.dk 313,397,450 are non-HF.
The counting script now includes all three layers and asserts the integer token
sum against the sampled metadata. The original-161 lineage dispositions below
remain valid. The report paths below now contain corrected counts and a Markdown
account/token table. Earlier claims of 776 and 727 schneiderkamplab repositories
are superseded, not a different dataset selection.

**Superseding reconciliation later on 2026-10-06:** the partial DFM13 counts
below have now been resolved. The full DFM13 inheritance accounts for **776
unique training-payload HF repositories**, including 727 under
`schneiderkamplab`, plus the two non-HF Lex.dk/DBC collections. The grouped
DaLA resolver maps the 72 components to 34 repositories, yielding 565 unique
repositories for the DFM12/13 additions and 211 for the sampled DFM11 base.
Repaired/materialized derivatives count instead of their upstream seed repos;
files, repeats and multiple configurations do not add repositories. The
inherited selection's base metadata hash matches the DFM13 inheritance receipt.
See `docs/reports/dfm13_hf_repository_counts_20261006.json` for every mapping,
input hashes and account totals; reproduce with
`python -m scripts.count_dfm13_hf_repositories --output <report.json>`.
This is the final expanded DFM13 scope, not the older local October 2 subset
and not a finalized DFM14 count. No data, training or publication was changed.

The original Mimir v1/DFM8 inventory was cross-checked individually on the same
date: 161 entries comprise 159 HF repositories and two agreement collections.
Of these, 127 HF IDs remain directly represented, 28 have included successor
packages, four are deliberately excluded, and both agreement collections
remain represented. The four exclusions are Oliver Kinch DA-AR and DA-EN
machine translation and the synthetic few/zero-shot MSMARCO task871 question
generation variants. Evidence is in `docs/dfm10-filter-reconciliation.md`,
the final DFM10 source reconciliation page, and the inherited sampling policy.
All 161 dispositions are in
`docs/reports/dfm8_to_dfm13_lineage_20261006.md` and its JSON companion;
reproduce with `python -m scripts.audit_dfm8_dfm13_lineage`.
This proves source-level accounting, not preservation of every original row:
repairs, quality filtering, sampling weights and repository revisions differ.

The following is retained as the earlier, superseded partial investigation:

An all-in DFM14 repository count is not finalized. The remote DFM13
`data/dfm13/all-source-finalization-20261004-v1/inventory.json` contains 603
integrated components and four quality holds. Joining its publication
destinations to integrated component names yields 530 distinct
`schneiderkamplab` repositories. Another 72 integrated DaLA components need
their grouped publication mappings, and `setur_fo_instruct` refers to
`Setur/fo-instruct`. These are not the whole inherited corpus: DFM11 and
earlier sources must be reconciled separately, including replacements.
The inventory's 580 publication destinations are not an included-dataset
count; not every destination joins to a currently integrated component.
Do not label 603, 580, or 530 as the total number of DFM14 HF datasets.
Count unique training-payload repositories, not both a derivative and its
upstream seed, and keep local agreement-backed sources separate.

| Area | Reusable code | Required work before bulk use |
| --- | --- | --- |
| Source inventory and conversion | `dfm12/catalog.py`, `records.py`, `prepare.py` | New pinned DFM14 registry and adapters; preserve source splits, script labels, tools, provenance and inherited overlap. |
| Transformations | `dfm12/transform.py`, `wave4_transforms.py` | New native prompts and language-aware boundaries/corruptions; token-length rather than character-count assumptions. |
| Parallel text | `dfm12/opus.py`, `baltic_opus.py` | New pair inventory, accepted equivalence audit, correct per-epoch caps and canonical pair IDs. |
| Synthetic tasks/review | `multilingual_tasks.py`, `multilingual_calibration_v6.py`, `wave_synthetic_runtime.py` | New manifest-bound DFM14 provider/controller, calibration and configuration-driven quotas. |
| State and scheduling | Existing queue/lease/atomic-write helpers | Eight independent ledger/output partitions with many leased work chunks and a shared per-endpoint concurrency budget. |
| Release | Existing accepted-export, provenance, tokenization and validation helpers | DFM14-specific manifests, heldout exclusion, deduplication and explicit replacement semantics; no live sample mutation. |

Concrete hazards verified in code:

- `wave4_synthetic_campaign.py` enforces its old language set, 66 groups,
  770,000 target, repository prefix and sealed implementation hashes. It is
  not a generic DFM14 launcher. Keep old guards intact and implement a new
  campaign wrapper instead of relaxing them.
- `wave4_cpu.enqueue()` uses one `audit/jobs.sqlite` writer. Do not copy that
  bottleneck into an eight-GPU production campaign.
- `transform.window()` splits long paragraphs with `[.!?]` followed by
  whitespace; span/prefix tasks require at least 20 whitespace boundaries.
  These assumptions do not support unspaced Chinese/Japanese prose. Case-swap
  corruption is also inappropriate as a universal error generator. Add tests
  for the new scripts, punctuation, combining characters and exact target
  reconstruction, including RTL languages.
- `prepare.Renderer.count()` passes an empty tools list to assistant-example
  rendering. The new tool-dialogue route must preserve and count row-level
  tool definitions, calls and responses, not just message text.
- `dfm12.budgets.opus_budget()` sums report coverage without normalizing by
  epoch count. Use `dfm12.token_accounting.inherited_budget()` or its validated
  receipt; see the [superseding accounting](dfm12-token-accounting.md).

## Workstreams and Starting Order

1. **CPU foundation:** implement a small `dfm14` CLI/package and separate
   source/runtime configurations. Resolve revision/file pins and small random
   samples, then normalize into candidate records. Download only selected
   payloads, not whole giant corpora. Record blocked sources independently.
2. **Existing instruction/chat:** start with the documented Russian, Turkish,
   Chinese, Arabic and Japanese candidates while preparing the remaining eleven
   languages in parallel. Their source-card assessment is not admission.
   Inspect complete conversations, native-language shares and benchmark overlap.
3. **Document-derived tasks:** prepare broad native text reservoirs for all
   sixteen languages. Dyna increments (Faroese Logir and the seven prioritized
   Polish educational/cultural subsets) and bounded Matina Persian samples
   are useful independent enrichment tracks, subject to their existing approval
   gates. Replace repaired sources rather than adding duplicate versions.
4. **Direct translations:** English pairs first, then well-supported other
   direct pairs. Do not make all-to-all pivot production a prerequisite for
   the first useful release. Caps are ceilings, not quotas to manufacture.
5. **Synthetic conversation gaps:** assign 35K/70K accepted-conversation tiers
   from audited existing breadth; use the six families in the playbook. Audit
   committed generation chunks immediately and re-audit repaired candidates.
6. **Knowledge/commonsense:** keep the proposed 500K English pilot separately
   budgeted and approval-gated. Prioritize uncovered OpenStax concepts, balanced
   science and bounded math QA selection; do not count inherited data as new.

Identity remains separately scoped. DaLA can attach later through immutable
delivery manifests; do not generate replacement labels in this campaign.

## Budget References to Verify

The historical accepted transformation caps per new language are 50,758
denoising, 76,142 prefix continuation, 44,795 span filling and 22,516 reordering
rows: 194,211 total, or 3,107,376 across sixteen languages. These are derived
from the historical Danish baseline, not freshly verified DFM14 accepted counts.
Transfer or reconstruct the pinned baseline before sealing production targets.

The inherited repaired EN-DA reference is 2,645,319,308.5 rendered tokens per
epoch. Corresponding pair ceilings, both directions combined, are 661,329,827
tokens for English pairs and 165,332,456 for other pairs. The old helper can
overstate these tenfold on the ten-epoch report. A regression test must cover
that normalization. Synthetic language targets add 560K-1.12M conversations;
the separate knowledge pilot is not included in those totals.

## Calibration and Launch Gates

Proposed first calibration: about 100 examples per available language/family,
including deliberately invalid and known-good controls, with recorded manual
review of boundary cases. Failures block the affected component, not all ready
languages. Add crash/resume, no-duplicate-claim, partition-union and accepted-only
export tests before scaling.

On dedicated GPUs, pin `google/gemma-4-26B-A4B-it` and its revision and reuse
eight owned vLLM endpoints. The handoff's 0.95 utilization, 1,024 sequences and
384 combined requests per endpoint are starting candidates, not promises of
capacity. Measure five-minute accepted throughput, KV pressure, preemptions,
invalid reviews and writer backlog. Generator, reviewer and repair traffic
share one endpoint budget; do not multiply it by the number of clients.

The first implementation milestone should end with a source lock, validated
native-format CPU fixtures, small candidate shards, explicit unresolved access
and language issues, and a dry-run queue. Bulk generation, upload and final
sampling remain separate gated operations. No DFM14 processes were launched
by this assessment.
