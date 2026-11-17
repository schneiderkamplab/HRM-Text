---
type: Experiment
title: DFM11 attention and loss ablations
status: draft
confidence: high
last_updated: 2026-11-17
description: Authorized three-run rotation and subsequent Transformer causal target-only control.
---
# DFM11 attention and loss ablations

The user authorized the following continuation on 2026-11-14. This extends the
existing [architecture comparison](2026-11-10-dfm11-architecture-comparison.md),
using its single SQLite scheduler and existing CUDA-suspension machinery.

## Runs and order

- Fresh B causal/target-only: `B-dfm11-causal-lrauto-bpwarmup-targetonly-epoch1`.
  Same LR-auto and BP2→8/50K warmup as the existing PrefixLM B.
- Existing B causal/all-token: resume
  `B-dfm11-causal-lrauto-bpwarmup-alltokens-epoch1` from its100K checkpoint.
  This is not the historical full-BP B stopped at150K.
- Fresh Transformer48 PrefixLM/target-only:
  `transformer48-dfm11-prefixlm-targetonly-epoch1`.
- After those three finish epoch1 and final evaluation work, fresh Transformer48
  causal/target-only: `transformer48-dfm11-causal-targetonly-epoch1`.

After the currently running B PrefixLM and completed causal Transformer finish
both final evaluation blocks, order is:

1. New B50K, new PrefixLM Transformer50K, new B100K, new Transformer100K.
2. For150K,200K,250K,300K,350K and epoch end: existing causal/all-token B,
   new causal/target-only B, new PrefixLM Transformer, in that order.
3. Causal/target-only Transformer50K,100K,150K,200K,250K,300K,350K,epoch end.

Every boundary retains the full evaluation block. Same-model boundaries use
CUDA offload/evaluation/in-memory resume; model switches use verified offload
and regular disk-checkpoint handoff. Epoch end uses actual data exhaustion;
393732 is the planning estimate, not an exact stopping boundary. Finalization
binds metrics to the actual saved step. Training gates remain terminal-mode on
real inference/export/wait work, not control barriers. The first new run and
last new control also wait on relevant final averages/reports in terminal mode.

All fresh runs keep DFM11 epoch0, seed0,262144-token batches, baseLR3e-4,
5K LR warmup, flat LR thereafter, and one epoch. Transformers retain the original
48-layer1024-hidden architecture and lr_auto=false. B retains H2/L3 and its
LR-auto/BP schedule. This controls the attention/loss comparison within each
architecture; cross-architecture comparisons still differ in optimization and
backpropagation schedule and are not exact measured-FLOP matches.

## Interpretation

Causal/target-only versus PrefixLM/target-only isolates prompt attention;
causal/target-only versus causal/all-token isolates prompt-label masking.
The subsequent Transformer control completes these three meaningful conditions
for both architectures. Simply enabling all-token loss under bidirectional
PrefixLM is not a valid fourth condition: shifted prompt labels become visible
through future prompt keys. Such an experiment needs a separately defined
objective/mask rather than toggling target_only alone.

## Implementation and verification

Preparation scripts:
`scripts/schedule_dfm11_objective_ablation.py` and
`scripts/extend_dfm11_objective_transformers.py`.
They append isolated artifacts, verify full graphs, paths and artifact isolation,
resolve Hydra configurations, back up SQLite, and compare pending row snapshots
before modifying dependencies. Existing running claims are unchanged.
Receipts, resolved-config hashes, additions TSVs and backups are in
`logs/scheduler/dfm11_architecture_comparison_20261110/objective-ablation-20261114/`.
The two-B insertion adds30856 rows; Transformer extension adds35264 and rewires
seven pending training rows. These are evaluation shards/postprocessing rows,
not additional training steps.

Transformer PrefixLM support required relaxing the causal-only export guard in
`conversion/convert_to_hf.py` and preserving installed PrefixLM attention in
`evaluation/vllm_plugins/transformer48_vllm.py`; causal exports retain the ordinary
causal override. CPU tests verify native/export logits, bidirectional prompt
behavior, causal answer behavior, cached decode, recurrent causal backward,
and serving-adapter attention selection (five tests pass). This is not a fresh
full-size GPU throughput or vLLM inference certification; first-use GPU behavior
must still be monitored. Existing dependency deprecation warnings remain.

## Historical diagnosis and final-evaluation repair

The following records preserve the diagnosis and earlier recommendation; the
authorized schedule above supersedes the earlier “not scheduled” status.

### Epoch-end status and next ablation assessment — 2026-11-14

The392K watcher successfully restored the original Transformer. Training exhausted
DFM11 at393995, but its scheduler train row failed in
`scripts/finalize_transformer48_epoch.py`: it rejects any non-pending final row,
including already-terminal control rows. Final Transformer block remains2197
pending/6done; B final block2201pending/2done. B epoch-end training is running
around371440 at0.29–0.30s/step. Final evaluation completion estimates are
conditional on repairing finalization/dependencies; training completion itself
is not evidence of final evaluation success. Recent350K export/inference log
mtime spans were48.3minutes Transformer and41.8minutes B (approximate spans,
not exact end-to-end publication durations).

Recommended next scientific ablation (not scheduled): fresh B DFM11 causal
attention with target_only=true, keeping the PrefixLM baseline's LR-auto,
BP2→8/50K warmup, initialization seed, data order, batch and LR schedule.
This adds the missing causal/response-only condition: comparison to existing
PrefixLM/response-only isolates attention; comparison to existing LR-auto
causal/all-token at50K/100K isolates loss masking. Switching a trained checkpoint
would measure adaptation instead of a from-start objective ablation.
Do not simply enable all-token loss under bidirectional PrefixLM: dataset_new.py
supervises shifted prompt labels when target_only=false while the prefix attention
mask permits future prompt keys, leaking those prompt targets. This combination
requires a different masked/causal objective to be scientifically meaningful.

Final-evaluation repair completed (2026-11-14): authoritative checkpoint state
records393997 (supersedes393995 inferred from the last displayed progress line).
Checkpoint readiness and epoch1/batch0 verified. Finalizer now ignores control-only
barrier/teardown rows and is idempotent for already-correct metadata; it still
refuses changing dispatched evaluation metadata. Four regression tests passed.
Bound pending Transformer final metrics to393997; recovered only its completed
training row from failed to done via SQLiteJobStore, which rearms terminal
barriers. Existing B training claim was preserved. Backup and recovery receipt:
combined plan `before-final-epoch-repair-20261114.sqlite` and
`final-epoch-repair-20261114.json`. Final checkpoint-wait row is now ready;
GPU evaluations must wait for the current B training lease. The same fixed
finalizer will run at B epoch exhaustion, preventing the identical control-row
failure there. No new ablation has been scheduled.

Installed verification: all30 new/continued training boundaries and the complete
105880-row graph pass; current B PrefixLM training remains the only running
row and no failed rows remain. `installed-verification.json` records the exact
order. OKF validation remains at its historical baseline of one unrelated
oversized scheduler page and14 unresolved-link warnings; no new violations.

2026-11-14 19:33 CET status: both original runs exhausted epoch1 at393997.
Transformer final block is2203/2203 done, including all1045 inference rows.
B PrefixLM final evaluation is progressing (906/1045 inference rows done at
inspection); no failed scheduler rows. Fresh B target-only50K remains pending
on the existing final-work gates. The finalization repair succeeded for B too.

2026-11-14 19:53 CET: new causal/target-only B launched and advanced past305
steps; sole running scheduler job, zero failures. All eight GPUs97–100% busy,
about40944MiB each. Early BP2 warmup retains fewer backward activations than
BP8; this is expected, with unchanged262144-token batch/GAS1 and no activation
checkpointing. Stable early progress approximately0.168s/step, not a full-run ETA.

2026-11-14 W&B visibility: remote run was running and synced through11700.
Workspace mkrhf1q0gcj now uses additive selections.root=0 and contained only
original B PrefixLM and causal Transformer (supersedes the earlier subtractive
selection observation). Added the new causal/target-only B only, preserving all
other settings; exact remote readback verified. Before/after backups:
`logs/diagnostics/ablation-workspace-20261114/`. Headline curves require the50K
results; no headline points were fabricated. Read-only full history scan was
cancelled after current remote summaries supplied the requested final comparison.
Both final summaries have epoch1/train_step393997 and matching headline task
counts (Danish17, English15, Math/code4). Transformer versus B PrefixLM scores
in percent: overall31.7064/40.0595, Danish39.7133/51.3701,
English43.6236/52.4456, Math/code34.9668/41.8644.

User requested49K suspension of the new causal/target-only B and automatic
memory resume after five continuous minutes of all-eight-GPU idle. Submitted
49000 to the live control queue with an explicit hold; detached offload helper
PID3714772 verifies exact-boundary CUDA offload before starting
`scripts/watch_btarget_49k_idle_resume.py`. Same zero-utilization, <=128MiB/GPU,
no-compute-process check as previous pauses; any activity resets the timer.
The existing supervisor owns restoration. The50K evaluation remains scheduled.

49K verified: exact49000/generation1 offloaded; original launcher and eight
ranks validated alive. Watcher PID3715442 active, idle timer advancing, all
GPUs0%/4MiB and no compute processes. Receipt/status under new B control
`user-pause-49000.json` and `idle-resume-49000/`.

2026-11-15 comparison refresh: remote sampled history returned all23 published
headline checkpoints across six DFM11 variants, including new B causal/target-only
50K and Transformer PrefixLM/target-only50K. Each run's final returned checkpoint
agrees with its remote summary. Snapshot:
`logs/diagnostics/dfm11-all-checkpoints-20261115.json`. At50K the new Transformer
PrefixLM overall is24.9553 versus B PrefixLM21.4740; B causal/target-only21.0223
versus matched causal/all-token LR-auto15.7800. These are observed single-seed
headline scores, not significance claims.

Comparison figures (2026-11-15): `logs/diagnostics/dfm11-comparison-figures/`
contains learning-curves and matched50K four-panel figures, PNG/SVG and
reproducible plot.py, using the23-checkpoint snapshot. Axes use common scales;
series end at published checkpoints. PDF export was dropped after slow shared
filesystem reads of fontTools; PNG/SVG completed and were visually inspected.

## Exact sampled-token exposure audit — 2026-11-15

Read-only computation completed with `scripts/compute_dfm11_token_exposure.py`.
Artifacts: `logs/diagnostics/dfm11-token-exposure-20261115/report.json`,
`category-counts.csv`, `source-ranges.json`, per-checkpoint source-count arrays.
No token payloads read; sequential sampled-index reads throttled near80MB/s.
Source intervals derive from sorted16023 source NPY byte lengths using the
writer's uint32/128-byte-header format, spread-header checks and exact total
reconciliation (223595843215 stored tokens). All sampled prompt/answer ranges
were checked against their assigned interval. Conservative existing source-family
classification is retained: mixed sources are not guessed into math/code.
Counts are tokens in those source examples, not semantic classification of
individual tokens. Source map and code hashes are in the report.

All six runs have identical50K cursor29891706; later shared checkpoint cursors
also match. Final tail replay from saved392K yields1997 batches and exactly
393997 steps, consuming235520649 rows and dropping62 final rows. Category sums
reconcile at every checkpoint. All-token supervised/nonpadding processed count
is inst_len+resp_len-1; target-only supervised count is resp_len.

At50K, all examples contain13.068705262B processed/all-token-supervised positions
versus4.553733665B target-only labels. Dedicated math:711290591 vs323261394
(45.45% retained); dedicated code:976222002 vs166788649 (17.09%); combined
math/code sources:3312897 vs678611. Combined known math/code is1.690825490B
vs0.490728654B (29.023%); epoch end13.3407B vs3.8676B (28.991%).
All-data epoch totals102.979554001B processed vs35.870881945B target labels.
Code's share of labels falls from7.47% to3.66%, whereas math's rises from5.44%
to7.10%. Thus loss masking substantially reduces code supervision, but cannot
explain causal-target versus PrefixLM-target differences at the same checkpoint:
their sample/label counts agree. Stable proportions across checkpoints do not
support a changing math/code mixture as the cause of later recovery.

MixedLM assessment (proposal only, not scheduled): alternate causal/all-token
and PrefixLM/target-only batches on unchanged data order, e.g. an initial50/50
step mix with separate loss normalization/logging and deterministic resumed mode
selection. Retain the correct attention/loss pairing to avoid prompt target
leakage. Current AttnType only supports static causal/prefixlm; loader target_only
is also static. Runtime mode selection, two compiled paths, checkpoint-replay
and export/evaluation mode tests are needed. A50/50 mix would provide expected
~571.5M code labels at50K (~3.43times target-only), without running two forward
passes per batch, but labels are not a direct measure of gradient contribution
or identical FLOPs. Related primary evidence: [UL2](https://arxiv.org/abs/2205.05131)
combines pretraining objectives; it does not validate this particular DFM11 mix.

## Future experiments and MixedLM terminology correction — 2026-11-15

User requested recording the50/50 causal/all-token versus PrefixLM/target-only
batch mixture as a possible future experiment. It is recorded, not authorized
for scheduling. **Terminology correction:** the preceding “MixedLM assessment”
used the wrong meaning of MixedLM for the user's question. Name that proposal
“mixed-objective batch training”; retain its contents as a separate future idea.

The user means Schneider-Kamp Lab llama.cpp MixedLM. Inspected local submodule
commit a800a5ff30fc9c37e0fa57629d0acf58a7340bea and
`native/mimir/MIXEDLM.md`, plus `llama.cpp/include/llama.h` API comments.
It is frozen-prefix suffix reuse: first prompt is bidirectional; on a new turn,
keep older prefix KV, discard the previous answer's causal KV and reprocess the
previous answer plus new user prompt/header as a bidirectional suffix that can
attend to old frozen keys. Older representations do not update from new text;
new answer generation is causal. Exact full PrefixLM recomputes the whole prompt.
The native document records a historical real-model instruction-following
regression despite functional correctness. Historical release/backend claims in
that document should not override the newer upstream-integration runbook.

Training for this mode is thinkable: reproduce the turn/block attention graph,
keep target-only answer supervision, and evaluate against exact PrefixLM and
MixedLM on identical multi-turn transcripts. This tests train/inference mask
mismatch, not recovery of prompt-token supervision. Existing sampled arrays
only carry aggregate instruction/response lengths, so reliable turn/extension
boundaries (including reprocessed previous answers and template tokens) must be
recovered or supplied. Need attention-mask and native-oracle parity tests,
packed-example isolation, and recurrent-cache semantics before launch. Frozen
forward representations do not by themselves require stop-gradient through
historical blocks during training; gradient truncation is a separate choice.
No training settings or scheduled experiments changed for either proposal.

## Future experiment: append-only MixedLM — 2026-11-15

User explicitly requested recording this alternative, not scheduling it. Keep
all historical KV, including the previous assistant answer's causal KV. Execute
new queries only for the new user-input block and assistant header; those tokens
attend bidirectionally within the new block and to all retained history. Generate
the next answer causally. “Only the new prompt” means only new queries/recomputation,
not removing access to historical keys. Unlike fork MixedLM, do not discard and
bidirectionally re-encode the previous answer. Compare matched training masks,
multi-turn quality and time-to-first-token/cache work against exact PrefixLM and
fork MixedLM. No queue entries or current settings changed for this alternative.

## MixedLM preparation follow-up — 2026-11-15

The earlier statement that no MixedLM experiments were scheduled is superseded
by the follow-up implementation and queue work requested for both architectures. See
[MixedLM implementation and schedule](2026-11-15-dfm11-mixedlm.md). The append-only
and mixed-objective-batch proposals remain future work.

## Transformer PrefixLM 100K result — 2026-11-15

Transformer48 PrefixLM/target-only reached100K and completed its evaluation and
average publication. The local finalized W&B summary at
`wandb/run-20261115_150117-transformer48-dfm11-prefixlm-targetonly-epoch1/files/wandb-summary.json`
records `headline_avg_v3/train_step=100000`: overall0.325772758,
Danish0.486833986, English0.492682297, math/code0.222905939. The averaging log
records successful W&B sync. At inspection2202 rows in this checkpoint block
were done and2 teardown rows remained pending; B causal/all-token LR-auto
training had started its next segment. Transformer PrefixLM150K remained pending.
Its50K overall was0.249552808; the100K causal/all-token Transformer overall was
0.246567440 and B PrefixLM/target-only overall0.269774605. These are single-seed
checkpoint comparisons, not isolated causal estimates of attention or loss scope.

## Transformer PrefixLM priority reorder — 2026-11-15

User requested moving the previously listed segments2 and5 next after the
running B causal/all-token100K→150K segment. The new order is B-all150K
(current), Transformer PrefixLM150K, Transformer PrefixLM200K, B-target150K,
B-all200K, B-target200K, then the existing250K-and-later three-run rotation.
Each boundary retains its existing evaluation block. This supersedes the
strict three-way alternation through200K; later segments and MixedLM ordering
are unchanged.

Updated five pending/unclaimed training definitions and their dependency rows
in one SQLite transaction. Each preserves terminal gating on the predecessor's
1047 inference/checkpoint/export rows. The same-model Transformer200K row has
no disk handoff, allowing in-memory resume after150K evaluations. Cross-model
handoff roots/steps were retargeted to their new immediate predecessors.
Complete141144-node graph validation found no cycles; all five job preflights
passed. The running B150K definition/status/attempt token were unchanged and
no administrative lock remained. Backup, exact changes and read-back receipt:
`logs/scheduler/dfm11_architecture_comparison_20261110/reorder-prefix-first-20261115/`.

## Queue priority revised on 2026-11-15

The user superseded the earlier placement after MixedLM: complete all remaining
Transformer48 PrefixLM/target-only boundaries first (the100K→150K boundary
was already running), then the entire Sandwich B PrefixLM/target-only epoch.
After Sandwich, preserve the other runs' prior relative order: B causal
all-token/target-only rotation, Transformer48 causal/target-only, then the
B/Transformer MixedLM rotation. Evaluations remain between all boundaries.

The reorder updated only unclaimed pending training markers and their dependency
edges. Same-run boundaries retain in-memory CUDA resume; cross-model disk
handoff metadata now names the actual preceding unfinished run. Completed
predecessor epochs need no suspended-trainer handoff. Full graph validation and
changed-job path preflight passed. Readback verified the running trainer's
unchanged definition, the exact changed-row set, and no administrative lock.
Backup, old/new order and transaction receipts are in
`logs/scheduler/dfm11_architecture_comparison_20261110/reorder-prefix-sandwich-20261115/`.

## Transformer PrefixLM at200K (2026-11-16)

Checkpoint-specific atomic headline_v3 publication logs report successful sync
through200K. The200K headline is overall0.37597461, Danish0.50269675,
English0.53123233, math/code0.26084683. Relative to150K, overall rises
1.9923 percentage points, English1.5092 and math/code4.0357; Danish falls
0.9628 points. No statistical-significance claim follows from this comparison.
At matched200K it exceeds Transformer causal/all-token overall0.27539519
and B PrefixLM/target-only overall0.33282901, but trails their math/code
0.31230623 and0.30670198 respectively. Sources and full50K–200K trajectory:
`logs/diagnostics/transformer-prefix-assessment-20261116.json`; comparator
snapshot: `logs/diagnostics/dfm11-all-checkpoints-20261115.json`.
Use the specific atomic publication run identified by each average job's log;
other concurrent W&B summary writers may retain stale headline step values.

### Checkpoint inventory refresh — 2026-11-17

Read-only scheduler inspection found15 DFM11 architecture/objective runs.
Transformer48 PrefixLM/target-only has completed epoch1: headline overall
24.96,32.58,35.61,37.60,38.23,39.40,39.89,40.48 percent at50K through350K
and epoch end respectively. B causal/target-only reached100K (25.35);
B causal/all-token LR-auto/BP-warmup reached150K (19.70). Local published
summary provenance is preserved in
`logs/diagnostics/dfm11-headline-latest-20261117.json`; earlier checkpoints in
`logs/diagnostics/dfm11-all-checkpoints-20261115.json`. Sandwich is the current
run; the three completed epochs are Transformer causal/all-token, B PrefixLM
target-only, and Transformer PrefixLM target-only. Append-only MixedLM and
mixed-objective batch training remain ideas, not queued jobs.

## MixedLM+ buckets and fast experiment table — 2026-11-17

User requested MixedLM+ as idea-only, without adding training jobs. Proposed
interpretation: partition incoming input into bounded buckets, with bidirectional
attention inside a completed bucket and attention to frozen earlier buckets.
Commit each bucket's KV once; later buckets do not update prior representations.
Keep answer prediction causal and target-only. Bucket sizes, boundaries, flush
behavior, training masks and model choices remain unspecified. To avoid all
recomputation, buffer a bucket until complete; incrementally revising an open
bucket would instead incur bounded recomputation. Never allow bidirectional
answer-token visibility to leak prediction targets.

This generalizes append-only MixedLM, whose bidirectional unit is the complete
new user prompt/header. If buckets equal those turn blocks, the two coincide;
smaller buckets change the attention graph and latency. Neither proposal is
queued. Mixed-objective batch training remains a different idea: alternate
causal/all-token and PrefixLM/target-only batches (initial proposal50/50).

Run `python scripts/dfm11_experiment_table.py` for the compact ruler-free table.
It reads SQLite read-only, collapses eval-block dependencies onto training
boundaries and sorts current/upcoming experiments by first pending boundary;
completed/stopped runs follow, then ideas. Rows summarize experiments, not every
interleaved segment. Scores are headline_avg_v3/overall times100. Unknown scores
remain dots. It seeds preserved reports, then reads only completed atomic-all
average jobs' exact log/summary paths with matching checkpoint steps; unchanged
log signatures are cached in `logs/diagnostics/dfm11-table-cache.json`. No W&B
API calls or directory-wide run scans. `--refresh` rereads known logs; `--json`
includes missing-summary warnings. Bootstrap0.2s on this node. The historical
score sources and latest source paths remain in the cache.

## Minimir continual-pretraining ideas — 2026-11-17

Record three idea-only branches initialized from `DFM-Mimir-v1.8-Mini`
(Minimir): (1) sampled recursion depths, (2) transition to CausalLM, and
(3) transition to existing MixedLM semantics. These are checkpoint continuations,
not new from-scratch DFM11 runs. No jobs are scheduled. Dataset, training budget,
LR/re-warm policy, loss masking, recursion pool/BP budget, and checkpoint
compatibility checks remain to be specified. Existing MixedLM here means
re-encoding the previous answer plus new prompt as the new bidirectional suffix;
append-only and bucketed MixedLM+ remain distinct ideas. Table checkpoint columns
for these ideas will represent additional CPT steps if later scheduled.
