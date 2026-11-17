---
type: Runbook
title: Separate Mimir-Decide Corpus Build
description: CPU conversion of the top-seven DFM decision clusters into a separately guarded Mimir-Decide training mixture.
tags: [datasets, decisions, conversions, mimir-decide]
status: stable
last_updated: 2026-10-23
confidence: high
---
# Separate Decision Corpus

The owner requested a separate corpus under `/work/dfm/mimir-decide`, cloned
from `https://github.com/lgalke/mimir-decide.git`. Work is on
`cluster/dfm-decision-corpus`; HRM training, evaluations and production data
are not modified. The target repository's `docs/design/d35-dfm-decision-corpus.md`
records the detailed design, and `scripts/build_dfm_decisions.sh` reproduces it.

## Inputs And Admission

* Original LocalLLaMA typed decisions, tasksource's `full` typed decisions,
  verified Bekko decisions, MASSIVE intents and HelpSteer2 ratings use the
  target repository's existing converters and split policies.
* The frozen top-seven inventory has 911 dataset/storage entries. Its 282
  task/family matches and one possible derivative are omitted, alongside
  administrative math-conditioning variants. Further GLUE/SuperGLUE and ComVE
  aliases are excluded in the mixture config.
* The owner explicitly clarified on October 23 that **all HRM-Text data is
  eligible**. A collection-scoped owner-approval switch admits those rows
  without fabricating a permissive licence. This does not grant publication
  rights or relax the existing policy for unrelated decision collections.

## Meaningful Conversions

Named classification labels, unambiguous MCQs, single-valued scalar math,
demonstrated next-tool actions (including responding without a tool), executable
format constraints, Python syntax/exception diagnostics and grounded answer
evidence become native `Decision` rows. Unsupported free responses are reported,
not assigned invented correctness labels. No source code is executed and no
GPU generation, judging or training is performed.

Every source receives a disposition. The first edition scans at most 20,000
rows and retains at most 5,000 decisions per DFM source entry; this is not the
complete conversion of the previously estimated 44.32B source-exposure tokens.
Limits are configurable. Sampling is bounded and deterministic, not claimed
uniform across entire sources. Missing producer-machine paths can use dedicated
HF releases with pinned revisions. Do not combine download, converted and chat
variants of the same source.

## Outputs And Safety

**Owner supersession, 2026-10-23:** full conversion completed with 77,665,705
candidate decisions. The owner then requested dropping evaluation-leakage
filtering and using 32 workers/shards for deduplication and numeric finalization.
The serial guarded build was stopped; completed conversion files remain intact.
New launcher: `scripts/build_dfm_decisions_sharded.sh` in Mimir-Decide.
Output: `/work/dfm/mimir-decide/data/full-scale/mixture-dfm-decisions-sharded`.
Log: `/work/dfm/mimir-decide/data/full-scale/logs/build-sharded.log`.
Thirty-two workers finalize numeric options before hash partitioning; 32 reducers
deduplicate normalized content plus supervision, independent of option order.
Different labels remain distinct. Each reducer owns one output shard and digest
set; map writes are buffered with no shared appenders. Completed work is resumable.
Train split/source exclusions/validity policies remain, but no evaluation text,
group or ngram filtering occurs. Copied pilot eval files are NOT guaranteed
disjoint from this full corpus. Do not claim uncontaminated evaluation scores.
The original guarded pilot builder remains unchanged. The `train.parquet`
output is a directory of 32 Arrow-compatible shards. Current Mimir-Decide training
still loads all text into RAM; large-scale training needs a lazy loader/cache.
Safe HF tokenization with 32 workers remains the requirement for that future stage.

The 32-worker build completed in **494 seconds (8m14s)**. Final output has
**76,483,835 training decisions** across 32 shards (13,995,124,789 bytes),
including 72,692,316 DFM-derived rows. Deduplication removed 1,097,917 rows;
64,535,111 numeric candidates were finalized before deduplication. All 32
Parquet footers were checked and sum to the manifest's training count.
This completes decision conversion/finalization/deduplication, not tokenization.

* Candidate pool and per-source reports: `/work/dfm/mimir-decide/data/dfm-candidates`.
* Final mixture: `/work/dfm/mimir-decide/data/mixture-dfm-decisions`.
* Build log: `/work/dfm/mimir-decide/data/campaign.log`.
* Source config: `/work/dfm/mimir-decide/configs/dfm_source_inventory.json`.

Only train inputs generate added DFM decisions. A prompt-group hash keeps
turns and derived variants together while carving 5% validation. The existing
decision builder applies exact-state, group and cross-source ngram leakage
guards and held-out source rules. Final files use the existing trainer's Arrow
schema; tokenization/chat formatting remains the trainer's responsibility.

The target environment is the existing `hrm` Python for CPU data work only.
For subsequent offline decision tokenization, the owner initially required the safe
Hugging Face tokenizer implementation with **32 workers**, bounded batches and
buffered writes, not the legacy `data_io` tokenizer. This is a future-stage
requirement: the current build produces native Decision Parquet and does not
launch tokenization. Mimir-Decide currently tokenizes through its own Formatter
at training time; any offline cache must preserve slot/scalar/letter formatting,
option permutation semantics, tokenizer revision and context-length settings.
Its installed Transformers 5.12.1 is below the target project's declared
5.13 minimum; no shared environment was modified and no model training was
started. Offline data tests pass, but a future training launch must use a
properly qualified model environment.

### Offline Tokenization and Separate Sampling (2026-10-23)

The owner superseded the 32-worker request with **64 CPU workers**. The launched
`/work/dfm/mimir-decide/scripts/tokenize_and_sample_dfm_decisions.sh` uses the
effective Hugging Face tokenizer backend, bounded Parquet batches, and independent
chunk files. Raw tokenizer.json differs from the backend configured by AutoTokenizer;
workers therefore use the serialized effective backend. A real-tokenizer parity
smoke passed 768 slot/scalar/letter formatting cases before launch.

Outputs under `/work/dfm/mimir-decide/data/full-scale/`:
- `tokenized-decisions`: reusable component cache, independent of repeats.
- `sampled-decisions`: five shuffled epoch index sets, automatically built only
  after tokenization succeeds.
- `logs/tokenize-sample-campaign.log`: detached pipeline log.

Sampling repeats are HRM-derived `dfm=1`, `bekko=5`, and all other current
collections `=10`: 98,750,351 decision draws per epoch. These are decision rows,
not packed LM tokens. No model training is launched. The cache has a formatter
adapter; the existing training loader still needs explicit cache/index integration
before large-scale training can consume these outputs efficiently.

Completion verified on 2026-10-23: all 322 chunks finished, covering 76,483,835
training decisions plus 35,217 validation/calibration decisions. Both completion
manifests exist. Sampling produced `epoch_0.npy` through `epoch_4.npy`, each with
98,750,351 row indexes (395,001,532 bytes per file). The pipeline exited and no
tokenizer/sampler processes remain. Per-epoch draws: DFM 72,692,316; Bekko
11,857,155; Tasksource 12,757,770; HelpSteer2 960,670; MASSIVE 460,560;
LocalLLaMA 21,880. No model training was started.

## Completed First Edition

**2026-10-23 follow-up:** the owner requested a full uncapped rebuild of the
same converters. The pilot is preserved. The new command in the target repo is
`bash scripts/build_dfm_decisions_full.sh`; its data root is
`/work/dfm/mimir-decide/data/full-scale`, with `logs/prepare.log`,
`logs/build.log`, and `logs/finalize.log`. It removes source row-scan,
candidate-count, two-remote-shard, per-source training and global training
caps. Eight CPU processes stream conversions to Parquet; no GPU work.
Text buffering is bounded, while deduplication and leakage hash indexes still
grow with corpus size. The same source/overlap/split/validity guards and training
format restrictions apply. Evaluation-file reservoirs remain small but guard
all evaluation rows. Final size is unknown until conversion and guards finish;
the pilot below is not the full corpus. Training rows are written in source
order and must be shuffled by the training loader.

Final guarded counts: 1,533,163 training decisions, 17,604 validation,
17,613 calibration, 600 heldout and 11,450 test. Training spans 605 task sources;
464,612 rows are DFM conversions from all seven clusters. DFM contributions:
direct labels 157,086; tools/actions 183,164; instruction constraints 3,770;
math 78,530; code 26,368; mixed reasoning 13,200; QA/evidence 2,494.

The bounded conversion pass yielded 546,779 candidate decisions from 188 entries.
It excluded 283 overlap entries and two storage variants; 437 entries had no
supported conversion in the inspected rows. The one absent train source is
Kaenguruen: its Hub release exposes only test, which was not repurposed.

Finalization replaces the initial numeric distractors with seeded alternatives
whose correct answer has uniform numerical rank and randomized display order.
References, states and split memberships stay unchanged. All training IDs are
unique, with no train/eval ID or group intersections. All 150 offline tests and
the target repository's OKF check pass. A CPU smoke exercised 175 source samples
through each of the slot, scalar and letter chat formatters with the local Mimir
tokenizer. No GPU training or evaluation was launched.

The detailed result is in the target repository's
`docs/observations/o29-dfm-decision-corpus.md`; its implementation is committed
locally on `cluster/dfm-decision-corpus`, not pushed. HRM's global OKF check still
has the pre-existing oversized request-shared scheduler page error and 15 old
link warnings, unrelated to this addition.
