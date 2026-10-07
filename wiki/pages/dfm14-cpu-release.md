---
type: Runbook
title: DFM14 accepted CPU release and 900K handoff
description: Resumable CPU release, verified publication and sampling while XXL-wide continues DFM13.
status: draft
confidence: high
last_updated: 2026-10-07
tags: [dfm14, release, sampling, training]
---
# DFM14 CPU Release

The owner authorized completion of the CPU-side release on 2026-10-07. All
source audits, the broad translation audit and synthetic generation/review
have finished. The eight owned shared Gemma servers were stopped via their
supervisor's `servers/stop.request`; unrelated processes were not terminated.

XXL-wide resumed from the fully verified `ephemeral_step_866500` in
`checkpoints/dfm13/XXL-wide-from-dfm11-epoch2`. The existing scheduler is
`logs/scheduler/dfm10_XL_epoch9_20260831`; training retains BP8, GAS4,
GBS262144, automatic module LRs with base 3e-4, FP32 FSDP parameters,
BF16 compute, no activation checkpointing and `fsdp_reshard_after_forward=false`.
W&B remains `DFM5/dfm10-xxl-wide`. Training advanced after restore at about
2.85 seconds per optimizer step.

## Boundary Safety

DFM13 runs to 900K. The successor depends on `xxlw-dfm14-ready-at-900000`,
a real checkpoint wait for the isolated DFM14 handoff view in
`data/dfm14/xxl-wide-handoff/resume`, tag `step_900000`. That view must not be created
until the dataset, uploads and resume cursor are verified. The DFM13 wrapper
also refuses training targets above 900K. Future plan commands still need the
DFM14 handoff update; merely completing the CPU release does not start DFM14.

## CPU Pipeline

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
  /home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm14.build --workers 16
```

Detached log: `logs/dfm14/cpu-release-v1.log`.
Progress and evidence: `data/dfm14/release-v1/`.
Packages: `exports_dfm14/`. Sample destination: `data/sampled_dfm14`.
Configuration: `config/data/dfm14.yaml`; source registry is written after
verified publication as `config/dfm14_sources.json`.

The pipeline verifies input/journal/receipt hashes, selects accept decisions
only, preserves legacy accepted synthetic slots, and keeps both directions of
accepted translation pairs. Repair requests, rejected rows and failed reviews
are not admitted. It reuses the published, train-only DaLA components and their
token arrays; inherited DFM13 data are not retokenized.

English repeats: two for the selected Smol constraints/rewrite/summarize and
SmolTalk2 components; one for Smol Magpie Ultra, OpenCoder and UltraChat.
Other new components default to one; inherited repeats remain unchanged.

New chats use the existing native Gemma tokenizer/template, disabled thinking,
and final-assistant supervision with complete untruncated history. Targets
over 4,096 tokens are explicitly counted as holds, not silently truncated.
This mirrors the final-target additions contract; it does not claim that all
audited conversations fit the current training context.

Normalized exact benchmark checks use the repository's eight-benchmark Mimir
manifest. Exact chat duplicates across additions are removed. Exact inherited
prompt/response token pairs are removed before sampling using a vectorized
shortlist followed by full token comparison. Neither check establishes semantic
or translated benchmark decontamination. Standalone uploaded packages may still
overlap inherited sources; the mixture, not the public source package, removes
that overlap.

HF nested columns (`messages_json`, `tools_json`, `provenance_json`, `audit_json`)
are lossless JSON strings to avoid incompatible Arrow tool schemas. Decode with
`json.loads`; do not train on serialized JSON. Source attribution and applicable
upstream/teacher conditions remain attached; no blanket permissive relicensing.

Three deterministic epoch sets are prepared over the three existing DFM13
epoch sets. Sampling metadata is published last after index bounds and token
count checks. A single-writer build lock and atomic stage receipts allow resume.
`completion.json` is written only after all HF packages have pinned revisions
and verified remote content hashes. Until then, DFM14 is **not ready**.

## Accepted Packaging Progress (2026-10-07)

All 31,789 input jobs passed receipt/native preparation. They contain 9,266,422
accepted source records, producing 12,907,279 eligible directional conversations
and 4,673,224,668 native prompt/target tokens before deduplication/repeats.
Held explicitly: 2,069 over-context targets and 55 exact benchmark matches.
Cross-addition chat deduplication removed 581 rows, leaving **12,906,698 rows
in 245 packages**. These figures exclude the already published DaLA components.
Packages exist locally; this snapshot does not claim all uploads or sampling
have finished.

Historical synthetic checks can contain successful check records, not only an
empty list; the release verifies their `passed=true` values. Older per-turn
reviews require every recorded criterion to pass. Knowledge-pilot rows lacking
an ID receive a stable job/slot ID, never a random ID. Language variants such
as `pt_pt` are preserved in row metadata and use hyphens in HF repository names.
Fifteen focused release/production/instruction tests pass.

The inherited three epoch pointer multisets differ. Exact overlap removal
therefore scans all three. Its shortlist probes tokens throughout the prompt
and response; template suffixes alone would produce excessive collisions for
DaLA/classification tasks. Only complete token equality excludes a target.

## Sampling Repair and Coverage (2026-10-07)

Superseded: the first release attempt passed filtered index arrays together
with the original full token store to the sampler. Its allocation assumes
complete original indices, so concatenation failed (189,570 source tokens
versus a 117,892-token destination). No source tokens were corrupted.

The fixed integration uses existing `selection_indices_path` support, with
unaltered original arrays and token stores. Retained row ordinals are recovered
from the completed deduplication outputs and all four index fields are checked
for exact equality. No new overlap scan, tokenization or audit is needed.
Seven focused tests pass, including a real sampler subprocess checking retained
token offsets. `min_resp_length=1` preserves valid short DaLA targets.

Overlap removal excluded 360,098 added prompt/response pairs. Every packaged
source retains rows. Additions contribute 6,879,561,807 tokens and 41,424,816
row occurrences per epoch after repeats. Sampling additions succeeded; merged
sampling and publication must still finish before declaring readiness.

`python -m dfm14.release_coverage` reconciles the pinned input inventory,
generation targets, eligible rows, package selections and upload receipts.
Reports: `data/dfm14/release-v1/coverage.json` and
`docs/reports/dfm14-release-coverage.md`.

Important shortfall: the English synthetic math pilot has zero accepted rows,
not a missing converter/export. Jobs finished with answer-contract errors.
Do not claim that all planned generation targets were achieved or admit failed
rows without a separate repair/review. Other English knowledge families and
all six families for each of the sixteen new languages have eligible data.

## Inheritance Discrepancy Discovered (2026-10-07)

The size comparison exposed an unresolved snapshot mismatch. The local XXL-wide
DFM13 was built from `data/dfm13_build/remote/sampled_dfm12`: 106,799,766,039
tokens/epoch, comprising DFM11 plus only 3,585,161,337 addition tokens. Its frozen
`data/dfm13_build/sources.json` has 13 additions, while the current checked-in
DFM13 registry has 312. The final remote authoritative composition files are
not present locally. The documented later XL DFM12 no-identity sample has
117,000,690,762 tokens, including 13,785,598,511 addition tokens.

Thus the apparent DFM12-to-DFM13 reduction is NOT established as an intentional
sampling reduction. It compares different release snapshots. The local DFM14
113,880,339,621-token sample inherits this older DFM13 snapshot. Earlier
mechanical readiness claims do not establish complete planned inheritance.
Keep the 900K handoff gated until authoritative membership is reconciled;
valid new package publication can proceed independently. Do not overwrite
the running DFM13 sample or claim all later DFM12/13 sources are included.

## Authorized Rebuild And Resume (2026-10-07)

The user stopped training and authorized rebuilding DFM12, DFM13 and DFM14,
then immediately resuming on DFM14. This supersedes the earlier 900K-only
handoff: the last complete checkpoint is `step_870000` in
`checkpoints/dfm13/XXL-wide-from-dfm11-epoch2`. Training and the scheduler were
stopped; unrelated package publication was allowed to finish.

The authoritative remote is reachable at `ucloud@ssh.cloud.sdu.dk:2850`, root
`/work/mimir/HRM-Text`. Its final composition pins **381 DFM12 components plus
603 approved DFM13 components**, with four explicit source-fidelity holds.
All thirteen additions in the frozen local DFM13 are covered. Importing the
remote sampled XL corpus directly would incorrectly enable XL identity repeats.
Instead, `python -m dfm14.reconcile_inheritance` rebuilds from local DFM11 and
the pinned tokenized composition, keeping all model identity components at
repeat 0. MATH repeat 5 and Setur/fo-instruct repeat 10 are retained.

Transferred 104,022,540,713 bytes, covering 1325 DFM12 and 7692 DFM13 tokenized
parts. Verified weighted additions: DFM12 48,859,993 rows / 13,785,598,511 tokens;
DFM13 80,662,659 rows / 11,170,372,396 tokens per epoch. Three index sets are
built at every level. DFM14 reuses accepted tokenized additions but recomputes
exact overlap against the corrected inheritance. No retokenization is required.

Build workspace: `data/dfm14/inheritance-reconciliation`; log:
`logs/dfm14/inheritance-rebuild.log`. Outputs stay isolated until full bounded
index scans, token totals, source counts and publication checks pass. Earlier
release readiness is marked `superseded_incomplete_inheritance`, not erased.

`python -m dfm14.continue_training watch` waits for validation, retains old
samples as recovery copies, and promotes the new samples using symlinks. It
uses a private hardlinked checkpoint copy with independent sidecar, resetting
only the dataset cursor to zero at dataset epoch index 2, preserving step
870000, optimizer/EMA, historical rewarm and current hyperparameters. The new
checkpoint directory is `checkpoints/dfm14/XXL-wide-from-dfm13-step870000`.
W&B remains `peter-sk-sdu/DFM5/dfm10-xxl-wide`; BP8, GAS4, GBS262144 and base
LR3e-4 with auto recurrence dividers remain unchanged.

Resume log: `logs/dfm14/rebuild-resume.log`. The watcher modifies the existing
`dfm10_XL_epoch9_20260831` plan under lock, replacing only obsolete pending
DFM13 continuation rows. It retains 50K evaluations, adds 32 new-language
DaLA/GEC tasks (four shards each), and keeps old suite averages separate from
new multilingual averages. CPU preflight verified 2000 unique samples per
task and 500 per shard. Epoch axes continue from the actual pre-switch row
fraction, not from a fabricated integer boundary. Exact remaining steps are
counted using the same multipack/GAS settings before launch.

Create `data/dfm14/inheritance-reconciliation/training/cancel` to cancel the
automatic continuation before launch. A failed rebuild never authorizes resume.
At documentation time rebuilding is active, not yet promoted or training.

### Duplicate Attribution From The First Build

The completed scan against the OLD 107B DFM13 sample removed 360,098 added
targets. Joining excluded token-index ordinals back to package row provenance
attributes 347,078 to `HuggingFaceTB/smoltalk`, 11,687 to
`CohereLabs/aya_dataset`, 545 to `IlyaGusev/saiga_scored`, and 788 to eleven
other upstream repositories. These are incoming-source attributions, not
identification of which inherited dataset contains the matching target.
Exact details: `data/dfm14/release-v1/duplicate-provenance.json`.
These counts must NOT be presented as the completed corrected-inheritance scan,
which was still running when this attribution was produced on 2026-10-07.

### Superseded: Inherited Duplicate Scan Disabled

Later on 2026-10-07 the user explicitly disabled the inherited-example scan.
The scan and resume watcher were stopped, and the rebuild restarted using the
already validated DFM12/DFM13 corpora. All accepted DFM14 additions are now
sampled with their configured repeats, without subtracting inherited matches.
`dfm14/selection.json` records `inherited_overlap_policy: keep_all`; sampler
rules use the original arrays without `selection_indices_path`. The earlier
completed duplicate counts remain historical evidence, not the new selection.
Existing package-level quality filters and prior cross-addition deduplication
are unchanged. Full index/token accounting validation and guarded automatic
training resume remain enabled. This supersedes the overlap-filtering steps
described above, not the source-level inheritance reconciliation.

The user additionally requires training to wait for free GPUs. The existing
all-GPU scheduler reservation requires at least178000MiB free per GPU. The
DFM14 segment wrapper now rechecks GPUs0-7 immediately before torchrun: all
eight must meet that threshold AND have no compute clients. It polls every120s,
fails closed on GPU-query errors, honors stop/cancel requests, and never kills
unrelated GPU processes. This covers external processes not tracked by the
scheduler, including small clients that would pass the memory-only threshold.

The corrected keep-all build subsequently passed validation and was promoted:
DFM14 has406830651rows/epoch,135548235716mean tokens/epoch, and three index sets.
Exact packing gives521204optimizer steps for one full pass with GBS262144/GAS4;
the resumed total is1391204from step870000. After a user-requested stop during
the initial launch (before any new checkpoint), the user authorized resume again.
The existing scheduler was restarted with the cancellation cleared and the
interrupted attempt reset. GPUs were occupied by unrelated clients at restart;
training waits for availability rather than terminating them. W&B/run settings
and the private step870000 resume checkpoint remain unchanged.
