---
type: Plan
title: DFM15 Native Reasoning
description: Native thinking and direct-answer supervision inherited from immutable DFM14.
status: draft
confidence: high
last_updated: 2026-11-02
tags: [dfm15, reasoning, data, training]
---
# DFM15

### DFM7 recipe recovered; lock exists (2026-11-02)

Supersedes the DFM7-blocked status below. The DFM7 hold is resolved at the
recipe level: `config/data/dfm7_hf_rebuild.json` now exists, recovered by
`scripts/rebuild_dfm7.py recover-lock` and cross-checked against the preserved
historical build (130 additions over the verified 10,521-task DFM6 base; 18
direct HF tasks, 98 Apertus shards totalling 3,942,208 rows, 14 converted
special sources with historical row counts; 33 input files pinned from the
preserved download snapshot and sha-verified against later acquisitions;
4,891 frozen sapient filter links). Full details and pipeline:
[DFM7 HF-only rebuild recipe](dfm7-plan/hf-rebuild-recipe.md).

`scripts/queue_dfm_hf_rebuild.py` gained `enable-dfm7` (recipe `dfm7-hf-v1`,
stages prepare, convert, verify-rows, smoke, tokenize, assemble, verify,
sample, compare; sampling `epochs=6 seed=0 concat_workers=1` with the six-epoch
comparison expectation). DFM7 is **not yet enabled** in the queue; no worker
was started and no equivalence is claimed until `dfm7/verified.json` exists.
Focused DFM5/6/7/queue tests: 31 passed.

### DFM6 verified; queue blocked at DFM7 (2026-11-02 status check)

Supersedes the DFM6-pending status below. DFM6's reconstruction passed on
2026-10-22: `data/rebuild_hf_dfm/serial-queue/dfm6/verified.json` records
`status: matched` across all 21 token/epoch-index arrays plus metadata after
the full 10,523-task comparison. DFM1-6 are verified. The queue then stopped
at DFM7 with hold `HF-only recipe/input lock must be recovered; local
reservoirs forbidden` (`logs/analysis/dfm6-hf-rebuild-20261021/runner.log`);
DFM7-15 remain pending, no `dfm7_hf_rebuild.json` lock exists, and no worker
was running at this check. Later-boundary recovery gaps are listed in
[hf-rebuild-recovery-assessment.md](dfm15-plan/hf-rebuild-recovery-assessment.md).

### DFM5 verified; DFM6 historical reconstruction enabled (2026-10-21)

Supersedes the pending DFM5 comparison and DFM6 recipe hold below. DFM5
passed all 21 token/index arrays across five epochs plus metadata; receipt:
`data/rebuild_hf_dfm/serial-queue/dfm5/verified.json`. DFM1-5 are verified.

DFM6 is a tokenizer migration, not token-array reuse. Its recovered lock is
`config/data/dfm6_hf_rebuild.json`: 10,523 task identities mapped to pinned HF
downloads or verified earlier rebuild source rows. Production token arrays
are comparison references only; lexdk/DBC retain their agreement exception.
`scripts/rebuild_dfm6.py` freezes the June renderer at main revision
`038e9a50baf9623277e8da623992f3bbe0597266` and the template at data_io revision
`0483afe9776c6b318a0005580cff4495578a2d67`. Current renderer improvements must
not silently change this historical reconstruction.

Gemma tokenizer acquisition uses `google/gemma-4-31B-it` revision
`3548789868c5356dbf307c98e6f609007b82b3eb`. Its BOS postprocessor differs from
the historical local copy: reconstruct the explicitly locked postprocessor
and require complete tokenizer semantic SHA equality. Historical encoding
uses `add_special_tokens=False`; this is not a vocabulary change. The
Nemotron Agentic tool-calling source requires the documented one-NUL-row
removal (8,443 retained physical records), not silent arbitrary error skipping.

`scripts/tokenize_historical_chat.py` uses the frozen parser/renderer with
bounded Arrow batches and streamed array writes, atomic staging, and restart
receipts. It never runs the old file-wide Python-list or Rust tokenizer.
The guarded serial runner validates inputs, smokes three examples per source
family, runs 64 tokenizer workers, compares every source array, samples five
epochs (seed 0, one concatenation worker), then compares all sampled arrays
and metadata. No DFM6 equivalence claim until `dfm6/verified.json` exists.

Launch: `python -m scripts.queue_dfm_hf_rebuild enable-dfm6 --queue
data/rebuild_hf_dfm/serial-queue`, then the existing detached
`scripts/watch_dfm_rebuild_io.py` runner. Use module invocation for the queue
CLI so repository imports resolve. Logs:
`logs/analysis/dfm6-hf-rebuild-20261021/runner.log` and per-stage logs in
`data/rebuild_hf_dfm/serial-queue/dfm6`. Sustained filesystem latency stops
only this isolated reconstruction process group. Training/evaluation unchanged.
Focused DFM6, DFM5 and queue tests: 22 passed.
SWE is now explicitly split into 32 whole-conversation shards and joined in
source order before comparison; see the [DFM6 sharding record](dfm6-plan/main-challenges.md).
An independent first-example comparison across the 144-source-family inventory
(empty reference outputs skipped) passed without discrepancies. This is a smoke
check only; full source and sampled comparisons remain pending. At launch,
the coordinator PID was 1050188 and its filesystem watchdog PID was 1050180.

### DFM4 publication and DFM5 continuation (2026-10-21)

Supersedes the pending publication and DFM5 recipe-hold status below.
DFM4 additions are public at `schneiderkamplab/dfm4-historical-additions`,
commit `1e4744a49693ce9b76ecad39aa479bd71f93a6b5`. All 4,469 payload files
(about 5.19 GB) and provenance were remotely checksum-verified. Registry key
`4` pins the commit and manifest digest. New DFM4 rebuilds fetch this package
by default; `--regenerate-transforms` explicitly selects CPU regeneration.
Completed verified reconstruction rows are never reset by enabling a recipe.

DFM5's `dfm5-hf-v1` recipe is running in the isolated serial queue. It reselects
4,891 original Sapient tasks using policy revision
`a6549a836180ad7522b983865e6b48b1ef2bea53`, reuses 193 verified mixed tasks
and 4,019 verified summary tasks, and recovers the accepted exports and 70
synthetic replacements from pinned June HF publications. DFM5 is not a plain
append to DFM4. The 82 export/synthetic source identities live in
`config/data/dfm5_hf_rebuild.json`; later DFM8 expansion rows are not admitted.
Publication dates identify candidates, not proof of historical equivalence.

Logs: `logs/analysis/dfm5-hf-rebuild-20261021/runner.log`, `acquire.log`, and
`data/rebuild_hf_dfm/serial-queue/dfm5/prepare.log`. Queue PID at launch:
509104; acquisition PID: 496382. Both have filesystem-latency watchdogs.
Safe HF tokenization uses 64 workers; source-array comparison gates five-epoch
sampling, followed by full token/index/metadata comparison. At this update,
preparation passed: 1,139 verified Sapient tasks are reused and 3,752 are
being retokenized by the safe 64-worker driver (PID 511090). Nine of 82
export/synthetic source repositories are downloaded;
DFM5 equivalence is **not yet established**, and DFM6 remains blocked behind
that verification. Production training/evaluation/data were not modified.

Later October 21 check: all 82 repositories finished acquisition and the
3,752-task Sapient tokenization finished. Full source-array verification is
running (3,175 tasks passed at the check). An independent first-row token
comparison passed for each of the 70 synthetic repositories and 12 export
families. This validates initial decoding/format handling only, not complete
row order or corpus equivalence. The existing guarded runner will continue
through recovery, source comparisons, five-epoch sampling and final comparison.

Recovery still must establish exported row ordering and freeze historical
partition counts into the release recipe after verification; those counts
currently come from reference NPY headers, not reference text/token payloads.

Focused DFM5/queue and DFM4 publication tests: 24 passed. An optional redundant
fresh DFM4 package fetch was stopped before completion; it is not additional
validation evidence. The completed upload's remote SHA-256 verification is
recorded in `dfm4/hf-publication.json` under the reconstruction queue.

### DFM4 historical reconstruction enabled (2026-10-21)

**Completion update (2026-10-21):** superseding the preliminary equivalence
status below, the full DFM4 reconstruction passed. Receipt:
`data/rebuild_hf_dfm/serial-queue/dfm4/verified.json`: all token values,
all five epoch index sets (21 arrays total), and metadata match. The worker
exited successfully. DFM1-4 are now verified; DFM5 is blocked on its missing
HF-only recipe/input lock, and DFM6-15 remain pending. No reconstruction
workers were running at this status check. DFM4 public materialization remains
pending; only the DFM2/3 packages are currently registered in
`config/data/historical_rebuild_packages.json`.

**Post-verification export decision (2026-10-21):** after the full DFM4
sampled-array and metadata comparison passes, package and publicly publish
its costly deterministic additions rather than requiring their regeneration:

- `dfm4_common_pile_paragraph_reorder`: original single-window outputs.
- `dfm4_dynaword_paragraph_reorder`: final DynaWord multi-window outputs.
- `dfm4_arxiv_paper_summarization`, `dfm4_govreport_summarization`,
  `dfm4_wiki_cat_sum_summarization`, and `dfm4_laion_scientific_summaries`:
  exact historical extracted/converted summarization examples.

Grouping related task families into HF packages is acceptable, but preserve
each original task name, relative filename, row order and variant. Include
source revision locks, reconstruction code/settings, sampling configuration,
SHA-256 payload checksums, and comparison evidence. Keep upstream attribution
and licenses; do not replace them with a blanket license. Reuse published
DFM1-3 inputs rather than republishing the inherited corpus. Register pinned
published revisions as the default DFM4 reconstruction inputs, with CPU
regeneration only as an explicit fallback. Do not upload the preliminary
smoke outputs or unverified generations. This is an approved follow-up;
the DFM4 publication worker has not yet been implemented/launched.

Supersedes the DFM4 recipe hold below. Source acquisition is complete and
`dfm4-hf-v1` is enabled in the isolated serial queue. No production payloads
are used as inputs; reuse is limited to verified HF-rebuilt DFM1/3 source
trees and the pinned DFM4 downloads.

Recovered Common Pile paragraph recipe: trim the leading source text to 1370
characters with the historical sentence/paragraph-aware trimmer, split into
paragraphs of at least 80 characters, retain at most eight, require at least
three, shuffle deterministically with seed 20260601 plus source-relative path
and row index. One example per eligible source row; cap 6000/file, scan up to
250000 rows. DynaWord retains its later four-window algorithm, cap 200000/file.
The current summarization generator matches inspected historical outputs;
unlike DFM2/3, no target-length override is needed in the inspected files.

Preflight evidence: complete 6000-row USPTO-0195 output matches historical
instruction/response tokens; first ten examples in ten sampled Common Pile
files match; first 100 ADL DynaWord rows match; complete inspected LAION
(38 rows) and GovReport (1921 rows) parquet files match exactly. Nine focused
tests pass. This is not yet full DFM4 equivalence.

`scripts/rebuild_dfm4_additions.py` generates with eight CPU workers, then
checks DynaWord/summary rows. Common Pile's preserved parquet tree is partly
overwritten, so its authoritative check uses historical token arrays.
After safe HF tokenization (64 workers), compare every addition's token and
index arrays before assembling the union and sampling five epochs with seed
0 and one concatenation worker. Final comparison covers **21 arrays** plus
metadata. Per-file generation receipts are tied to code and input metadata;
staged outputs publish only on successful completion.

Logs: `logs/analysis/dfm4-historical-rebuild-20261021/runner.log`,
`logs/analysis/dfm4-rebuild-watchdog.log`, and per-stage logs under
`data/rebuild_hf_dfm/serial-queue/dfm4/`. Filesystem watchdog remains active.

### Reconstruction milestone (2026-10-20 evening)

DFM1, DFM2 and DFM3 now pass exact sampled token/index and metadata comparisons.
Both historical transformation packages were publicly uploaded and remote
payload checksums verified; pinned revisions are recorded in
`config/data/historical_rebuild_packages.json` and the per-version
`hf-publication.json` receipts. DFM4 acquisition has started (GovReport,
WikiCatSum, LAION Scientific-Summaries). Its reconstruction row remains
blocked on recovery of the historical mixed paragraph-generation recipe;
acquisition is not a completed DFM4 reconstruction.

## Post-reconstruction release recipes

User direction, 2026-10-20: after the serial HF reconstruction through DFM15
has completed and comparisons have passed (DFM2-14 remain prerequisites),
consider consolidating the supported reconstruction entry points around
**Mimir Training Corpus (MTC)** releases rather than every intermediate DFM
iteration:

- **MTCv1**: the final DFM version used to train Mimir v1.
- **MTCv1.5**, **MTCv1.8**, and subsequent releases: the corresponding final
  training-corpus versions, verified from model-release and training records.

**Verified mapping, 2026-10-20: MTCv1 corresponds to DFM8.** Mimir v1 is the
DFM8 XL EMA step_1650000 checkpoint, exported as
`exports/dfm8_XL_step1650000_ema_hf`. See
[release identification](dfm9-plan/motivation.md) and the
[checkpoint analysis](mimir-v1-evaluation-gap-analysis.md). Earlier DFM
training remains part of its lineage.

The other mappings are not established by the naming proposal. Confirm the exact
DFM version, source revisions, tokenizer/template, conversion settings,
sampling configuration, epoch count and comparison fingerprints for each.
Distinguish a release's final corpus recipe from the model's full multi-corpus
training history; preserve both rather than implying it trained only on its
last corpus.

Once verified, expose release-aligned recipes that reconstruct directly from
HF plus the two agreement-based sources, reusing cached intermediates where
available. Preserve historical DFM recipes, lineage and verification evidence
as archival provenance, but assess whether users need to execute the whole
DFM1-15 chain. Do not delete or consolidate recipes before the current replay
has established equivalence. No change to the active reconstruction queue.

### DFM2 HF reconstruction (2026-10-20)

The isolated serial queue now runs DFM2 after the verified DFM1 predecessor.
Reuse the freshly HF-downloaded/reconstructed DynaWord source, not production
payloads. Generate with seed `20260530` and **max_chars=3000** (the generator's
current default 1800 is not historical DFM2). Check generated per-task counts
against the preserved manifest before tokenization. Use
`scripts/tokenize_hrm_hf.py`, 16 bounded-memory workers, original Sapient BPE
and HRM template; do not launch the old bulk Rust tokenizer.

Union 1377 verified DFM1 tasks with 450 regenerated tasks, sample four epochs
with seed 0 and `data_io/prefix_config_dfm2.yaml`, then compare all 17 arrays
and metadata against `data/sampled_dfm2`. Historical target:
42,317,252,803 tokens/epoch. **DFM2 equality is pending**, not yet established.
Work: `data/rebuild_hf_dfm/serial-queue/dfm2`. Watchdog and coordinator logs:
`logs/analysis/dfm2-hf-rebuild-20261020/`. The filesystem watchdog stops only
the rebuild process group after sustained slow probes.

### DFM3 queue and future worker count (2026-10-20)

Superseding the earlier DFM3 recipe hold: DFM3 reconstruction is queued via
`scripts/queue_dfm3_after_dfm2.py`. It waits for the active DFM2 coordinator's
lock before installing the recipe, avoiding concurrent whole-plan writes.
The coordinator still requires DFM2's exact comparison to pass before DFM3.
DFM2 retains 16 HF tokenizer workers; **DFM3-15 use 32 HF tokenizer workers**
as their recipes are enabled. This does not authorize the old bulk tokenizer.

DFM3 acquires 477 historical Common Pile source files from 12 HF repositories,
using historical conversion receipts only for paths/sizes. HF revisions are
pinned at acquisition; historical identity remains subject to comparison.
Convert with 12000-character raw windows, generate six objectives with seed
20260531 and max_chars 1800, check the 2862-task inventory, tokenize, union
with rebuilt DFM1/DFM2 physical task roots, sample four epochs with seed 0,
then compare all 17 arrays and metadata. Preserve output under
`data/rebuild_hf_dfm/serial-queue/dfm3`; logs and handoff under
`logs/analysis/dfm3-hf-rebuild-20261020`. Filesystem watchdog remains enabled.
DFM4-15 still require recipe recovery; setting worker counts does not claim
these recipes are ready. Two focused queue/command tests pass.

Handoff check: DFM2 sampling completed but exact comparison failed:
`tokens.npy` rebuilt shape `(177907672278,)` versus preserved
`(183051776892,)`, both int32. DFM3 is installed but correctly remains
pending behind this predecessor mismatch. Generated row counts alone did not
establish equality; investigate transformation/token lengths before releasing
DFM3. No failed DFM2 outputs are approved as reconstruction inputs.

Mismatch diagnosis, 2026-10-20: the current generator introduced a later
context-budget shortening of denoising/span-filling targets to about 1390
characters, whereas historical DFM2 used full 3000-character chunks.
Matching aggregate row counts therefore missed the content change. The new
explicit `--historical-full-reconstruction` option preserves original targets;
default behavior is unchanged. All ten variants of the first inspected memo
row match preserved historical rows exactly with this option.

The isolated DFM2 repair regenerates with this mode and now compares every
generated parquet row across all 450 files before tokenization, then repeats
sampling and the final 17-array/metadata comparison. Three focused regression
tests passed. Full equality remains pending until the repair finishes.
Repair logs: `logs/analysis/dfm2-historical-repair-20261020/`;
watchdog log: `logs/analysis/dfm2-repair-watchdog.log`. DFM3 releases only after
successful DFM2 verification.

Verified completion, 2026-10-20: the corrected DFM2 reconstruction passed
all 17 token/epoch-index array comparisons and metadata equality
(`data/rebuild_hf_dfm/serial-queue/dfm2/verified.json`). This supersedes the
pending equality status above and confirms the historical-mode repair.
DFM3 automatically advanced: all 477 source files from 12 HF repositories
were acquired and converted; deterministic objective generation is running.

DFM3 generation has since completed with an exact 2862-task layout match;
32-worker HF tokenization is running, followed automatically by sampling and
full comparison. Layout equality alone does not establish content equality.

User-approved publication gate (2026-10-20): only after DFM3's full comparison
passes, package and upload the verified historical DFM2 and DFM3 transformed
outputs. Preserve filenames, variants, row order, source revision locks,
generation parameters, recipes and checksums. These should be distinct from
later filtered/expanded transform releases. After checking uploaded contents,
use pinned HF packages in reconstruction recipes, retaining CPU regeneration
as a fallback. Do not publish a failed or merely layout-matched reconstruction.

DFM3 comparison failed on 2026-10-20 after tokenization and sampling:
rebuilt `tokens.npy` has 253,593,966,148 int32 entries versus historical
302,212,210,334. The coordinator stopped; publication and successors remain
blocked. Inspection confirms a historical/current transformation discrepancy:
the first inspected USPTO-0160 denoising target is 2922 characters historically
versus 1390 rebuilt. DFM3's current generator also contains later
reconstruction-target shortening, and the queued 1800-character chunk setting
needs historical recovery. Fix and verify content, not just task inventory,
before retrying.

DFM3 repair started, 2026-10-20: explicitly restore `--max-chars 3000`
and `--historical-full-reconstruction`; retain current default generation
behavior outside historical replay. All six variants of the inspected
USPTO-0160 first row match historical content with these settings.
Reused completed HF acquisition/conversion; reset generation onward.
Every generated row in all 2862 files must now match preserved parquet
content before the 32-worker HF tokenizer runs. Sampling and full-array
comparison still gate publication. Five focused tests pass; end-to-end
verification remains pending. Logs:
`logs/analysis/dfm3-historical-repair-20261020/` and
`logs/analysis/dfm3-repair-watchdog.log`.

Worker policy update, 2026-10-20: user permits **64 workers for future
tokenization**, conditional on the safe bounded-memory HF driver. This
supersedes the earlier 32-worker policy. Runtime configuration is
`config/data/hf_rebuild_runtime.json`; tokenizer launches read it independently
of the active queue's plan, avoiding concurrent plan edits. Only
`scripts/tokenize_hrm_hf.py` is allowed. Do not switch to the old bulk Rust
tokenizer. The already-running DFM3 process remains at 32 workers; retain the
filesystem watchdog.

### Publication followed by DFM4 preparation

Queued on 2026-10-20 using `scripts/publish_verified_dfm_transforms.py
--queue data/rebuild_hf_dfm/serial-queue --wait`, detached and protected by
`publication.lock`. Polls every 120 seconds for both DFM2 and DFM3 exact
verification. Intended repositories:
`schneiderkamplab/dfm2-dynaword-historical` and
`schneiderkamplab/dfm3-common-pile-historical`. New repositories start private;
do not imply a blanket license for the heterogeneous upstream materials.
Packages include unchanged parquet layout/order, SHA-256 manifest, generator,
source revision provenance, sampling config and comparison receipts. Uploads
are checked against remote LFS SHA-256/size at the returned commit before
writing `hf-publication.json`.

After both publications, the same job acquires pinned HF GovReport,
WikiCatSum and LAION Scientific-Summaries into isolated `dfm4/downloads`,
then records `dfm4/preparation.json`. Full DFM4 reconstruction is **not yet
enabled**: its 425 original Common Pile paragraph tasks and 25 newer
DynaWord multi-window tasks require distinct historical generation behavior,
and summarization target lengths need verification. Do not run current
defaults and assume equality. DFM4's intended worker count is 32, sampling
five epochs. Job log:
`logs/analysis/dfm2-dfm3-publication-then-dfm4.log`.

**Superseding publication policy, 2026-10-20:** user requires these packages
to be **public**, not private. The waiting publisher was restarted with
`private=False`, also enforcing public visibility for existing target repos.
Publication records pinned verified revisions in
`config/data/historical_rebuild_packages.json`.

Newly enabled DFM2/3 reconstruction recipes default to downloading these
pinned packages, verifying all payload SHA-256 hashes and preserving
task-relative paths before tokenization. Missing unpublished pins fail closed;
there is no silent regeneration fallback. Use `--regenerate-transforms`
explicitly to recover the CPU generation path. The active DFM3 validation
run retains its generation recipe so it can establish the publication proof.
DFM1 already acquires registered HF sources/packages (including the published
OPUS package); it has no DFM2/3 transformations to regenerate. Future derivative
packages should likewise become the default source at their first applicable
DFM boundary. Six focused tests pass. End-to-end downloading of the new
packages remains gated on their successful publication.

## Disaster recovery assessment (2026-10-19)

The complete 2026-10-19 assessment now lives in
[hf-rebuild-recovery-assessment.md](dfm15-plan/hf-rebuild-recovery-assessment.md).
Summary: the user requires an HF-only reconstruction; local reservoirs are not
inputs (only lexdk/DBC may come from local agreement data); the isolated serial
queue at `data/rebuild_hf_dfm/serial-queue` enforces strict per-version
comparison receipts; and several later boundaries (DFM9, DFM12-15) still need
recipe/adapter recovery before the chain can continue past the DFM7 hold.

## Math Conditioning Handoff (2026-10-17)

The earlier full-mixture hold release is superseded for the newly approved
conservative math-format conditioning. The DFM15 training row is pending with
`dfm15_preparation_hold=true` and an unreachable GPU-memory admission threshold.
Existing evaluations continue. Both the hold-release helper and training launcher
require `data/sampled_dfm15/math-answer-conditioning-verified.json` before
training may start; the full-mixture receipt alone is no longer sufficient.
Only successful conditioning and verification may release this hold.

CPU conditioning was launched on 2026-10-17 after two focused converter tests
passed (mode preservation and conservative exclusions). It uses 16 conversion
workers after collecting source boundaries and scanning the three index sets.
Progress log: `logs/training/dfm15_XL_extension/math-conditioning.log`.
No GPU work or benchmark scorer changes are involved.

Conditioning completed and all three index sets were verified on 2026-10-17.
Exactly 1,250 unique targets (1,250 occurrences per epoch) were changed; the
conservative matcher left 743,095 cohort candidates without an unambiguous
numeric final unchanged. This is limited format exposure, not a corpus-wide
math normalization. The verification receipt was published and the training
hold released; normal evaluation dependencies still govern training admission.

The 1,250-example intervention above is superseded by a second pass requested
on the same day. Inspection found that the first matcher rejected terminal
`\\boxed{25}.` because of punctuation and bare direct numeric targets such as
`3`. It also confused ordinary problem wording such as "only three apples"
with output constraints. Version 2 handles these cases, keeps the same fixed
10% source-offset cohort, and preserves symbolic/ambiguous targets and genuine
format constraints. It preserves worked solutions verbatim and appends the
requested `ANSWER:` line; direct numeric targets receive that prefix without
adding reasoning. Existing native thinking channels are retained.

Version 2 uses `data/dfm15/math-answer-conditioning-v2` for evidence and
`logs/training/dfm15_XL_extension/math-conditioning-v2.log` for progress.
The scheduler hold was reinstated; the launcher and release helper now require
a version-2 receipt. Six focused tests passed. Index replacements are staged
one epoch at a time with a commit journal, rather than changing four live
arrays independently without recovery. Mathematical answer correctness is
inherited from the sources; this format pass does not independently solve them.

Version-2 preparation selected 521,883 additional unique examples: 521,698
OpenMathInstruct2, 159 AllenAI Open Math, 25 GSM-Symbolic and one Tulu personas
math example. Alongside version 1 this gives 523,133 conditioned examples per
epoch, about 6.7% of the scoped math-source occurrences. The net version-2
addition is 11,272,888 tokens per epoch. Seven focused tests passed, including
staged publication, preservation of unchanged rows and token accounting.
A seeded 1,000-row decoded check confirmed prompt/target transformations,
thinking-channel counts and the 4097-token limit.

Quality caveat discovered during inspection: the changed Tulu example asks
about products of pass totals, while its inherited final answer claims 18
successful goals. The format pass preserves that existing answer; it does not
establish correctness or repair source-level semantic inconsistencies. Source
evidence is retained in `math-answer-conditioning-v2/examples.jsonl`.

Final verification completed for all three epochs; temporary staged index
arrays and variant token buffers were removed. Mean DFM15 size is now
**134,516,139,170 tokens/epoch**. The version-2 receipt was published and the
DFM15 preparation hold released, with existing evaluation dependencies intact.

## Full Local Sample and Scorer Compatibility (2026-10-17)

Upstream pulled through `0c9fe65`. The repair-only local sample was replaced
in place using `scripts/build_dfm15_full_sample.py`; its large token backing
was reused, not copied. Only full `data/sampled_dfm15` remains. All three
index sets pass bounds, nonempty-target, length and token-total verification.
Per epoch additions at repeat 1 after whole-row length admission:

| Addition | Rows | Tokens |
|---|---:|---:|
| Faroese Dyna-Instruct | 1,008,183 | 70,610,198 |
| Icelandic Dyna-Instruct | 608,280 | 74,094,689 |
| English GSM-Symbolic synthetic train | 3,799 | 682,844 |
| Danish linguistic-quality corrections | 615 | 101,629 |
| Total additions | 1,620,877 | 145,489,360 |

Mean full-mixture tokens/epoch: **134,504,846,117**. Omitted 614 Faroese and
1,824 Icelandic overlength conversations, without truncating targets.
Inherited selection/repetition is retained, with additions uniformly
interleaved at deterministic positions per epoch. Exact duplicate FO-Instruct
remains excluded from the composite addition, retaining the inherited route.
Publication receipt: `data/sampled_dfm15/full-mixture-verified.json` pins
`config/dfm15_sources.json`. The existing scheduler training hold was released
only after this receipt was published. The continuation wrapper requires it.

GSM-Symbolic conversion verifies `####` against the numeric target, removes
calculator markup, puts reasoning in native Gemma thought channels, and emits
one `\\boxed{number}` final answer. Decoded tokenized row 0 has thought
`78+39 = 117` and final `\\boxed{117}`. This matches our GSM8k extractor
(`evaluation/benchmarks.py`) and both projects' boxed-first MATH scoring.

**HRM-test distinction:** on `ssh.cloud.sdu.dk:6768`,
`/work/dfm/HRM-test/run_three_model_queue.py` selects built-in
`inspect_evals/gsm8k`, not its older `custom_english_tasks.py@gsm8k_0shot`.
The installed built-in uses 10 shots, a step-by-step `ANSWER: ...` prompt,
and `match(numeric=True)` from the brainsurgery environment. Direct CPU tests
of its installed matching functions reject `\\boxed{117}` and accept
`ANSWER: 117`; a preceding standalone `39` can become the extracted answer
when the final box cannot be parsed. The older custom scorer explicitly
accepts boxes. HRM-test's MATH custom/HF scorers extract a final box and use
math_verify; its IE MATH scorer tries `ANSWER:` first, then a box, then full
text. Its IE prompt requests `ANSWER:` even though boxes score correctly.
No scorer or target-format changes were made as part of this inspection.

## Confirmed Dataset Additions

User decision on 2026-10-15: include both instruction datasets in DFM15:

| Language | Hugging Face dataset | Integration status |
|---|---|---|
| Faroese | `danish-foundation-models/faroese-dyna-instruct` | Downloaded, tokenized, registered; inherited FO-Instruct excluded |
| Icelandic | `danish-foundation-models/icelandic-dyna-instruct` | Downloaded, tokenized, registered |

Before rebuilding DFM15, inspect their schemas and source lineage, convert to
the native Gemma 4 conversation/reasoning format, check overlap with inherited
Dyna-derived examples, and tokenize. Determine sampling weights from measured
row/token counts; preparation defaults to repeat 1. The staged
token totals below do not include these additions. DFM14 remains unchanged.

### Organization Scan and Prepared Additions (2026-10-15)

The user authorized checking overlaps and integrating new organization
datasets/subsets. `scripts/scan_dfm15_organization.py` pins the 42 visible Hub
repositories and file hashes in `data/dfm15/organization-inventory.json`.
`config/dfm15_sources.json` registers these tokenized additions on top of the
native-reasoning staged base, with per-part selection indices:

| Source | Selected rows | Native Gemma tokens before length admission |
|---|---:|---:|
| Faroese dyna-instruct | 1,008,797 | 75,274,250 |
| Icelandic dyna-instruct | 610,104 | 100,239,190 |
| multilingual-gsm-symbolic, English synthetic train only | 3,799 | 682,844 |
| linguistic-quality, Danish correction pairs | 615 | 101,629 |

These are **tokenized staging**, not a rebuilt sampled DFM15. Full conversations
were preserved: 614 Faroese and 1,824 Icelandic sequences exceed 4,096 tokens;
future sample admission must handle them explicitly without truncating targets.
GSM-Symbolic uses native thought-channel reasoning and one boxed final answer;
21 exact internal duplicates were removed. Its 191 original training rows are
GSM8k-derived and not added again; no test split is admitted.

Overlap findings:

- All 571 composite FO-Instruct rows exactly match the pinned inherited
  `Setur/fo-instruct` multiset (NFC/outer-whitespace normalized). Preserve the
  inherited repeat-10 route and exclude the composite copy.
- No further identical normalized conversations occur across the four prepared
  additions. Evidence: `data/dfm15/overlap-report.json`.
- Danish and Norwegian dyna-instruct revisions and payload hashes are unchanged
  from the October 5 scan. Preserve earlier constituent exclusions, including
  duplicated direct Synquid sources and held-out Norwegian evaluation sources.
- This is **not** an exhaustive row-level match against the entire inherited
  corpus. Shared DynaWord grounding lineage is not proof of identical SFT rows.

Other organization repositories: retain existing audited routes for Laerebogen,
Arena, model-charter and Kaenguruen, existing Croco selection, and the explicit
danish-wildchat4.8M exclusion. Raw DynaWord/Gigaword/Nasjonalt vitenarkiv and
metadata collections are not direct instruction additions; creating new
grounded transformations from them is separate work. `Icelandic-flan` has no
Parquet/JSONL payload. Protect evaluation-only splits and existing DaLA holdouts.

Two potentially useful private collections remain blocked: `dialog-k2-da`
(89,545 filtered conversations; do not also add its unfiltered copy) and
`instruction-dataset-v1` (constituent and all-shuffled copies must not both be
included). The Hub returned **403: organization private repository storage
limit reached**, not an ordinary missing-token error. Their schemas can be
listed but content could not be downloaded. Once access is restored, compare
their constituents (Dialog, Dolly, EuroBlocks, FLAN, Laerebogen, OASST2,
OpenCodeInstruct, SciRIFF) against inherited routes before admitting increments.

Reproducible CPU commands:

```bash
python -m scripts.scan_dfm15_organization
python -m scripts.prepare_dfm15_dyna_instruct --workers 16
python -m scripts.prepare_dfm15_small_additions
python -m scripts.register_dfm15_additions
```

Sources: [Faroese](https://huggingface.co/datasets/danish-foundation-models/faroese-dyna-instruct),
[Icelandic](https://huggingface.co/datasets/danish-foundation-models/icelandic-dyna-instruct),
[GSM-Symbolic](https://huggingface.co/datasets/danish-foundation-models/multilingual-gsm-symbolic),
[linguistic quality](https://huggingface.co/datasets/danish-foundation-models/linguistic-quality).

## XL Extension Approved 2026-10-16

2026-10-17 recovery: DFM14 completed step 3,768,319 at 03:25 CEST,
but finalization failed because `display_epoch` read an in-epoch row cursor
from an epoch checkpoint. Epoch checkpoints legitimately omit that field.
Final checkpoints now map directly to parent epoch + 1; intermediate
checkpoints still require and validate the cursor. Regression-tested with a
cursor-free epoch sidecar. Resetting the failed training row also rearms the
terminal inference barriers, so DFM15 cannot bypass the final DFM14 evals.
DFM15 transfer and validation completed and its continuation was installed
at 00:50 CEST; data readiness was not the cause of this stall.

**Superseded 2026-10-17:** selecting the native-reasoning base alone was incorrect.
The continuation requires all four registered additions from
`config/dfm15_sources.json` as well as the repaired inherited mixture.
Reuse the transferred backing in place; do not retain a second repair-only sample.
Continue the existing XL run after DFM14 epoch completion at
3,768,319 through step 3,800,000 (31,681 steps). Preserve optimizer and EMA;
reset only the data cursor to DFM15 `epoch_0` using an isolated checkpoint
wrapper. Keep base LR 1e-5 with lr_auto, BP8, GAS2, no warmup or decay.
The training wrapper requires a full-mixture validation receipt before launch.

`scripts/prepare_dfm15_extension.py` transfers the validated remote sample,
checks tokenizer identity, index bounds/lengths and token totals for all three
index sets, and atomically publishes `data/sampled_dfm15`.
`scripts/schedule_dfm15_xl_extension.py --wait` installs the continuation into
the existing authoritative SQLite plan only after validation. Training follows
successful DFM14 completion and terminal final-epoch GPU inference, not CPU
publication. Same W&B run: `DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full`.
Logs and installation receipt: `logs/training/dfm15_XL_extension/`.

The archive watcher now requires the 3.8M checkpoint as well as completed
DFM14 final evaluations before final catch-up. It includes the DFM15 sample
and checkpoints and writes a remote completion receipt. The initial archive
remains resumable and runs concurrently; do not shut down before its final
receipt is present.

## Evaluation Inheritance

Retain the complete [DFM14 evaluation baseline](dfm14-evaluation-baseline.md),
including all 50 languages and Andersen modernization. Native-reasoning
diagnostics are separately named additions, not replacements for existing
benchmarks or average populations; proposed additions are listed there.

## Version Boundary

User decision on 2026-10-09: native-reasoning repairs belong to **DFM15**.
DFM14 remains unchanged. Do not promote either the old plaintext repair or
the native-reasoning staging output into `data/sampled_dfm14`; do not change
ongoing DFM14 training or its scheduler as part of this data preparation.

The completed CPU build has been designated the first DFM15 staged base:

- Work root: `data/dfm15/native-reasoning-v2`.
- Sample: `data/dfm15/native-reasoning-v2/sampled_dfm15`.
- Three index sets: `epoch_0`, `epoch_1`, `epoch_2`.
- Mean tokens per epoch: **134,359,356,757** (134.359B).
- Native-thinking occurrences from repaired sources: about **2.079M per epoch**.
- Quarantined sampled occurrences removed: **38,828 / 38,976 / 38,996**.
- Status: validated staging, not promoted, not selected by live training.
- Original build log remains `logs/dfm14/native-reasoning-v2/build.log` as
  historical evidence; the build started before the DFM15 naming decision.

## Policy and Implementation

2026-10-28 inventory: the five retained repaired thinking source groups plus
English GSM-Symbolic provide 2,923,688 prepared targets / 7,131,590,210 tokens
before sampling and repeats. DFM16 OpenScienceReasoning-2 and AgentTraj-L add
1,711,682 prepared thinking targets / 9,917,587,140 tokens, many overlength.
These are source-pool totals, not epoch exposure. Decoded representatives from
all eight sources confirm enabled prompts and native thought-channel targets.
See [source-by-source counts and exclusions](../../docs/reports/native-thinking-inventory-20261028.md).

Preserve well-formed reasoning and final answers separately in native Gemma
channels with thinking enabled. Repair only unambiguous malformed boundaries;
retain an intact final answer in non-thinking mode when reasoning cannot safely
be retained or exceeds context. Quarantine examples without a complete usable
answer. Keep ordinary direct-answer supervision. Never truncate a thought
channel or remove its final answer merely to meet context length.

The implementation currently lives in `dfm14/native_reasoning.py` and
`dfm14/build_native_reasoning.py` because DFM14 is its immutable input. Its
default output is now DFM15. See the [repair details and history](dfm14-cpu-release.md)
for source coverage, tests, tool-specific repairs and evidence layout.
The stage carries its own template; shared/live templates remain untouched.

Before eventual training: finalize other DFM15 additions, review mode exposure,
select the required epoch index convention, calculate the packed-step budget,
and perform a checkpoint-safe explicit data switch. None of these are implied
by naming this staged corpus DFM15.
