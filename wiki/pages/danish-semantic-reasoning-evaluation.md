---
type: Runbook
title: Danish semantic reasoning evaluation
description: Local evaluation-only adapter for the pinned CST Danish semantic reasoning benchmark.
status: draft
confidence: high
last_updated: 2026-11-12
tags: [evaluation, danish, semantic-reasoning]
---
# Danish semantic reasoning evaluation

Upstream: [CST benchmark](https://github.com/kuhumcst/danish-semantic-reasoning-benchmark),
pinned at `dea3cb506c3d68ebb3e70b04320f094b93320607`. Downloaded unchanged under
`evaluation/data/danish_semantic_reasoning_upstream/`. This is evaluation-only;
never include the archives or derived records in training exports. No existing
training contamination check has been performed, so independence is not certified.

The repository has expanded since the root README's 26 datasets/4,200 examples.
The downloaded DAMETA file has997 rows, while its README says915. Use archive
hashes and the generated manifest, not README totals, for reproducibility.

| Family | Primary items | Protocol |
|---|---:|---|
| Lexical inference |1020| Binary truth; retain17 source subsets/four qualia roles |
| Event entailment |319| Three labels: true, false, unknown; neutral preserved |
| DanWiC polysemous |1098| Same meaning in two contexts? |
| Synonym selection |288| Four options |
| Similarity outlier |3738| Six options; retain fine/medium/coarse subsets |
| Contextual sentiment |1041| Integer from−3 to3 |
| DAMETA |997| Four paraphrases with typed distractors |

Primary total8501. DanWiC monosemous1098 is an additional all-positive control,
not mixed into the main score. Prepared total9599 including that control.
The legacy150-item free-form metaphor explanation spreadsheets are not included:
they require a separate rubric/human or judge evaluation, unlike DAMETA's gold
multiple-choice labels. The new adapter does not claim published-protocol parity.

## Local preparation and scoring

`scripts/prepare_danish_semantic_reasoning.py` reads the published password-protected
archives directly; the password is provided by upstream for benchmark use.
Standard ZIP archives use zipfile; DAMETA uses AES ZIP and requires pyzipper.
Use the isolated uv dependency environment; no training environment install:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with pyzipper python scripts/prepare_danish_semantic_reasoning.py
```

The script refuses to overwrite an existing prepared directory. Outputs are local
`evaluation/data/danish_semantic_reasoning/{records.jsonl,manifest.json}`. The
manifest pins upstream revision, archive hashes, output hash, subset counts,
excluded row IDs/reasons, and explicit normalizations. No source labels are
semantically repaired. Eight blank rows, one missing/invalid entailment label,
and12 duplicate-choice similarity rows are withheld. Duplicate-choice rows are
flagged conservatively, not certified semantic defects. Their exclusion changes
the scored population and must accompany any report. Known empty TSV fields and
combined `true/false holo_member` fields are parsed explicitly; malformed headers
are bypassed only with fixed validated column schemas. Raw upstream remains intact.

`evaluation/danish_semantic_reasoning_eval.py` provides the Inspect task
`danish_semantic_reasoning(family=..., subset=..., num_shards=..., shard_index=...)`.
It verifies the prepared record hash before loading, defaults DanWiC to polysemous,
uses Danish prompts, temperature0 and16 completion tokens. Exact whole-answer
scoring allows case differences and one final full stop/exclamation mark;
explanations and multiple labels are invalid and count as wrong. Accuracy and
valid-format rate are reported separately. There is no LLM judge or response
repair. Gold labels and distractor metadata are not placed in model prompts.

Example from repository root, with an already configured Inspect model endpoint:

```bash
dfm-evals/.venv/bin/inspect eval evaluation/danish_semantic_reasoning_eval.py@danish_semantic_reasoning -T family=dameta --model openai-api/your-served-model
```

Recipe metadata: `evaluation/config/danish_semantic_reasoning_v1.json`.
Tests: `PYTHONPATH=.:dfm-evals dfm-evals/.venv/bin/python -m pytest tests/test_danish_semantic_reasoning.py -q`.
All18 parser, strict-scoring, dataset-loading and sharding tests passed.
OKF validation retains the existing1oversize-page error and14broken-link warnings.
No model evaluation or scheduler insertion has been performed. The explicit
training pause remains in force. Existing headline averages are unchanged.

Report each family and source subset separately. If adding an overall score,
use an explicitly versioned equal-family mean rather than letting similarity's
larger population dominate. Further analysis should include label-balanced
scores, sentiment MAE, DAMETA distractor types, and polysemy/control breakdowns.
Similarity variants share core-group IDs; uncertainty estimates should cluster
related variants rather than treat them as independent examples. These additional
analyses are recommendations, not implemented metrics in this initial adapter.

## Attribution and scope

Preserve attribution to CST, University of Copenhagen, and the Society for Danish
Language and Literature. Retain upstream LICENSE/README files. Licenses differ
by folder: inference/entailment identify CC BY-SA4.0, DanWiC/similarity/synonymy/
sentiment identify CC BY-ND4.0, and DAMETA identifies CC BY4.0. The root license
alone is not an accurate summary of all subdatasets. Derived evaluation records
remain local; no public dataset upload or redistribution was performed.


## 2026-11-12: Three-Mimir headline campaign and training gate

Supersedes the preparation-only status above: user requested all seven primary
tasks on Mimir v1/v1.5/v1.8 and automatic release of the next training segment.
Campaign directory: combined DFM11 plan `danish-semantic-mimir-20261112/`.
`scripts/schedule_danish_semantic_mimir.py` prepares21 inference rows and3
headline rows,25,503 generations. Model versions run sequentially to avoid
repeated server replacement; tasks within a model share persistent vLLM servers.
Generation is zero-shot, temperature0,16 output tokens; each model uses its
native chat template. Tokenizer preflight measured561 maximum prompt tokens for
all three, safely within4096 including outputs. An initial preflight incorrectly
counted the fields of Transformers' returned encoding object; it was corrected
to explicitly encode the rendered prompt before scheduling. The invalid draft
manifest is retained with its correction name and is not the campaign manifest.

Pinned models:
- v1: HF DFM-Mimir revision396df886074e3e43f30792fbf393b9a019fe28f7.
- v1.5: HF DFM-Mimir-v1.5 revision521b40b36a79918014544b970d4c2669ff1530eb;
  released epoch10 EMA weights226257d0d6c5dc04d920e48bb7079c3361dcf0866a950f4667bfcc9ae7bb6e48.
- v1.8: locally verified3,800,000 EMA export, weights
  07e031ed49b740591a97039de4bad73e46f2818ee9d244631dabb6ad82190c27.
Manifest records model/config/tokenizer/template hashes, dataset hash and scoring
software hashes. It does not silently substitute nearby training checkpoints.

`headline_danish_semantic_v1/overall` is the equal mean of seven family
accuracies. Per-family accuracy, valid-format fraction and sample count are
published together, plus family_count=7 and sample_count=8501. Existing
headline_avg_v3 is untouched. Three separate DFM5 W&B runs use IDs
`danish-semantic-v1-mimir-v1-20261112`,
`danish-semantic-v1-mimir-v1.5-20261112`, and
`danish-semantic-v1-mimir-v1.8-20261112`. Each publication explicitly registers
all metrics and logs one atomic payload under the run-writer lock. Local
per-model headline.json retains input log hashes and publication status.

The publisher validates complete unique sample populations, exact prompts/golds,
successful Inspect logs and absence of sample errors. Missing/failed results
cannot produce a deceptively complete headline.23 focused tests and a two-item
mock-model end-to-end evals suite invocation passed. No actual Mimir score is
claimed from those CPU-only checks.

The next training row is Transformer48 200K→250K. It gains all three headline
rows as terminal dependencies (which themselves depend on the21 inference rows),
and its user_training_pause flag is cleared. This retains the repository's
continuity policy: exhausted evaluation/publication failures remain visible and
terminal instead of stranding training indefinitely. Only this next training
segment is unpaused; the following seven remain explicitly paused. The existing
cooperative disk handoff safely releases PrefixLM B at200K and resumes the
Transformer from its200K checkpoint after the new block.

Insertion completed:24 new rows, three headline dependencies on the next
training row, seven later train rows still paused. Gate-verification receipt
confirms this. Dedicated average-dispatch regression test also passed.

Activation verified: restarted scheduler PID3807573 passed39,696-row preflight
with zero path errors/blockers. Dispatch is unlocked. It is finishing the last88
existing PrefixLM200K inference tasks before admitting Mimir v1; all24 new rows
are queued. Both run and eval-set CLI modes passed CPU mock smoke checks.


## Completed Mimir campaign — 2026-11-12

All 21 inference jobs completed successfully: 8,501 answers per model,
25,503 total. Equal-family headline accuracy (percent): Mimir v1 68.4131,
v1.5 73.7370, v1.8 74.7615. These are seven-task macro averages, not
sample-weighted averages. Invalid answer formats count as wrong; DanWiC
valid-format rates were 82.79%, 96.72%, and 100%, respectively, so the
improvement includes better output compliance. No contamination certification
or independent confidence claim follows from these scores.

Initial publication failed after saving complete local headline.json files:
the Inspect Python environment imported a namespace named wandb without the
SDK (`AttributeError: module 'wandb' has no attribute 'init'`). Installed
`wandb==0.27.0` using `uv pip install --python dfm-evals/.venv/bin/python`
and retried only the three failed headline rows through SQLiteJobStore.
Evaluation inputs, frozen scoring software and generated outputs were unchanged.
Future publication preflight must test callable(wandb.init) in the actual
publisher interpreter, not merely import wandb.

The terminal publication gates released Transformer48 200K→250K automatically;
training was verified advancing beyond 201K during publication recovery.
The following seven training rows remain paused as previously requested.

Recovery verified: all three headline scheduler rows are done and all three
local reports record publication=wandb_finished. W&B synchronization completed.


## Gemma 4 / Qwen 3.5 comparison queued — 2026-11-12

User requested the same seven tasks for Gemma 4 E2B, E4B, 26B and 31B,
and Qwen 3.5 0.8B, 2B, 4B and 9B. Use instruction-tuned Gemma releases
(26B is 26B-A4B-it) and post-trained Qwen releases. The exact HF repository
IDs, commit revisions, configuration/tokenizer hashes and immutable cache blob
identities are pinned in
`logs/scheduler/dfm11_architecture_comparison_20261110/danish-semantic-external-20261112/manifest.json`.

`scripts/schedule_danish_semantic_external.py` prepares and inserts 56 inference
rows plus eight headline publications in the existing SQLite scheduler.
Each model receives the same 8,501 examples (68,008 total). Native chat templates
explicitly disable thinking using vLLM default chat-template kwargs; temperature
0, 16 output tokens, strict answer parsing and equal-family headline remain
unchanged. Text-only serving uses language-model-only, BF16, TP1, memory0.95,
512 server sequences and 64 client connections. Each model's seven tasks share
the persistent serving pool; model groups are ordered by terminal dependencies.

First-group dependencies include Transformer250K training, checkpoint/export,
and all its GPU evaluation tasks. No live training definition, token, pause or
hold is modified. Seven later training rows remain paused. This campaign does
not launch a second scheduler or compete with the current training for GPUs.
Each model publishes its own `danish-semantic-v1-<model>-20261112` W&B run,
using the existing `headline_danish_semantic_v1` metrics and atomic publisher.

Dry-run checked full graph validity, job paths, complete indexed weight files,
all native prompt lengths (maximum561–569 tokens), and the unchanged scoring
hashes. All23 benchmark/publisher tests passed. The installed vLLM registry
supports both model families and exposes the required text-only/non-thinking
flags. GPU loading is deferred to the scheduled block; the CPU preflight is
not a claim that these eight GPU evaluations have run successfully.


The initial whole-plan import was safely rejected because canonical serialization
of an existing claimed training row differed from its stored legacy definition.
No rows changed. The insertion script now uses an additive transaction for only
its64 new rows, preserving all existing definitions and active attempt tokens;
it still validates the complete candidate graph before insertion. Do not use
whole-plan round trips merely to append jobs beside a claimed legacy row.

Insertion verified:64 pending campaign rows, current Transformer250K training
row still running, and seven later training rows still paused. Receipt saved
beside the frozen manifest. OKF validation remains at its pre-existing one
oversized-page error and14 historical link warnings; no new regression.


## Gemma E2B/E4B startup repair — 2026-11-12

The earlier CPU preflight did not establish GPU backend compatibility.
E2B and E4B both failed before inference with `FlashAttention forward only
supports head dimension at most 256`. Their serving backend is now FLASHINFER
(installed implementation supports head sizes through512), superseding the
initial forced FLASH_ATTN setting for these two models. Both metadata fields
and extra CLI arguments were changed. Fourteen failed inference rows and two
headline rows were reset to pending; original server logs and a SQLite backup,
pre-repair row definitions and repair receipt are retained in the campaign.
No weights, prompts, scoring hashes or generation limits changed. The insertion
script also uses FLASHINFER for future E2B/E4B preparations.

Separately, 26B/31B failed backend validation: mm_prefix requires FlashAttention
v4 unavailable for their head size. This is a distinct unresolved serving issue;
the E2B/E4B repair does not establish recovery of those models.


Follow-up diagnosis: FLASHINFER was selected successfully for E2B/E4B, then
startup failed during kernel compilation: `Could not find nvcc and default
cuda_home='/usr/local/cuda' doesn't exist`. Evidence includes gpu_0 server logs
945b282459a78792 (E2B) and18149e1a04f8c999 (E4B). Thus the head-size rejection
was bypassed, but the serving subprocess lacks a discoverable CUDA toolkit.
The initial FlashInfer repair was incomplete; successful inference is still
unverified. 26B/31B retain their separate forced-FLASH_ATTN mm_prefix/head-size
validation failure. These are serving failures, not benchmark scores.


## Authorized Gemma memory interlude — 2026-11-12

User explicitly requested suspension of the ongoing Transformer300K segment,
Gemma evaluations, then automatic restoration from memory. Prepared
`scripts/run_gemma_semantic_memory_interlude.py`: retains the main scheduler's
exclusive training claim and explicit root hold; requests an out-of-band
suspension, verifies generation-matched CUDA offload, runs an isolated eval-only
SQLite plan through the existing scheduler implementation, drains its GPU
servers, reconciles only finished Gemma statuses to the main plan, removes its
own hold and requests supervised restore. Restoration verifies the original
launcher and all rank identities and rejects any disk-fallback receipt.
A live eval process or remaining GPU allocation prevents unsafe restore.

All four Gemmas use TRITON_ATTN, whose installed implementation explicitly
supports head sizes>=32 and mm_prefix, plus cuda_home pointing to the audit
CUDA13.2 toolkit (nvcc version verified). This supersedes the incompatible
FlashAttention configuration and the incomplete FlashInfer workaround. Inputs,
weights, thinking=false,16-token limit and headline definitions are unchanged.
GPU inference compatibility remains to be established by the actual run.
Plan/receipts: `logs/scheduler/gemma_semantic_memory_interlude_20261112`;
local database `/var/tmp/gemma-semantic-memory-interlude-20261112/jobs.sqlite`.
Initial preflight caught a JobStatus string serialization error before any hold;
corrected to the enum and reran. Suspension requested at256136 on the live
Transformer launcher691743. No trainer termination or disk restart is requested.


## Exact26B compiler-path recovery and success gate — 2026-11-12

26B MoE compilation still failed after CUDA_HOME alone: missing cuda_runtime_api.h,
cuda_fp16.h and cublasLt.h. This was already solved in
[dfm12 multilingual extension](dfm12-multilingual-extension-plan.md), startup
correction: set CPATH=audit/targets/x86_64-linux/include and
LIBRARY_PATH=audit/targets/x86_64-linux/lib, MAX_JOBS=16. The working
`dfm12/diagnostic_server.py::command_env` contains those settings. The earlier
repair missed these explicit Conda paths; E2B/E4B do not exercise the same MoE
host compilation path. A host-C++ syntax check of all three headers passed.

Added executable `scripts/gemma_cuda_python` retaining hrm's vLLM interpreter
while supplying audit's CUDA toolkit/include/library paths to the entire server
child tree. Changed only failed26B rows in the interlude DB and reset their
bounded attempts; retained prior definitions/DB backup and logs. Both preparation
scripts now use this wrapper for Gemma. Other running model definitions untouched.

User required26B success before training resumes. Paused only the outer resume
orchestrator709750 with SIGSTOP (its eval child continues), preserving the trainer
hold/offloaded state. `scripts/gemma_interlude_resume_gate.py` polls the interlude
DB and releases that exact identity only after all eight26B rows are done,
8501-sample headline publication is wandb_finished, and all other eval rows are
terminal. Original orchestrator then drains servers, reconciles results and
restores the original Transformer processes. Gate receipt/log live with the
interlude; it intentionally does not release training after another26B failure.


26B recovery verified: all seven tasks completed (8501 answers), headline synced
with overall75.320077%. Completed E2B/E4B/26B statuses were reconciled to the main
plan. The26B server returned actual200 responses after the include-path fix;
server readiness alone was not treated as success. The success gate remains
armed but waits for31B's still-running tasks to become terminal before releasing
the original memory-restoration orchestrator. Transformer remains held at256136.
31B is waiting on checkpoint filesystem reads (observed folio_wait_bit_common),
not the26B compiler-path issue. No in-memory restoration is claimed yet.

Interlude completed: all28 Gemma task jobs and four headlines succeeded and
synced. 31B headline78.966007%. Resume success gate released only after26B
success and all evaluations terminal. All eval servers shut down; the original
Transformer launcher691743 and all eight original ranks were verified restored
from memory at256136 with no disk fallback. Training subsequently advanced
to256210 toward300K. status.json records resumed_from_memory and rank identities.
