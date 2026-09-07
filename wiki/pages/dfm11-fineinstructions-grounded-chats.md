---
type: Training Data Plan
title: DFM11 FineInstructions Grounded Chats
description: Balanced bilingual grounded-chat generation, salvage, finalization, and extension policy for DFM11.
tags: [dfm11, fineinstructions, grounded-chat, synthetic-data, bilingual]
status: stable
last_updated: 2026-09-07
confidence: high
---
# DFM11 FineInstructions Grounded Chats

## Controlled interaction modes

The English FineInstructions campaign retains its first 183,978 accepted chats
unchanged. For the remaining accepted pairs, the generator applies a seeded,
restart-stable, balanced cycle over 20 interaction modes adapted from
Koolbardi's documented ontology. The implementation is owned by the
FineInstructions submodule and has no Koolbardi runtime dependency. Newly
accepted rows retain mode metadata and must pass an explicit mode-adherence
score in addition to the existing grounding and quality gates. Modes that act
on supplied material may use the preceding answer or text actually embedded in
the follow-up, never the hidden grounding document.

Schema-constrained output that reaches its token cap is salvaged only at safe
boundaries: retain fully decoded message objects, discard a dangling user or
partial message, and remove complete trailing exchanges until the rendered
conversation fits 3,900 tokens. Never synthesize missing closing text.

The shared command supports explicit Danish generation with localized mode
labels and the identical salvage/audit contract. The current automatic Danish
handoff ends after helper-model distillation; a later Danish production
pair/chat launcher must select
`--language da --controlled-interaction-modes --balance-interaction-modes`.

## Balanced releases and extension

The release target is 500,000 rows per language. English preserves its 183,978
legacy chats and balances the remaining 316,022 selected rows over all 20
modes. Generation uses per-mode accepted quotas, while deterministic
finalization writes a named immutable release and retains all accepted surplus.

Later extensions raise the quotas under the same seed and pair ordering and
write a new release, without mutating the 500K snapshot. Danish helper-model
distillation remains unchanged; its later production stage should use the same
500K per-mode quota contract over source-balanced grounding candidates.

Deficit-filling passes skip unresolved pairs assigned to already-complete modes
before making model requests. Assignment remains deterministic, and accepted
surplus from bounded in-flight work stays in the append-only ledger.

The English launcher parameterizes both the target and release name, and uses
target-specific generation/finalization markers. This makes later balanced
extensions resumable without deleting the immutable 500K release or replaying
already accepted pair IDs. The initial release uses:

```bash
bash fineinstructions/scripts/run_dfm11_english_1m.sh
```

A later extension can use, for example:

```bash
CHAT_TARGET=650000 \
RELEASE_NAME=english-650k-balanced-v1 \
bash fineinstructions/scripts/run_dfm11_english_1m.sh
```

Generate additional grounded pairs before permitting multiple chat variants
from one pair. Keep every release immutable and retain the append-only accepted
ledger so larger balanced releases remain reproducible.

## English 500K release state

Verified on 2026-09-04: the immutable English release is complete at
`data/fineinstructions/dfm11-english-1m/releases/english-500k-balanced-v1`.
It contains five 100,000-row pair shards and five corresponding 100,000-row
chat shards. The receipt records exactly 183,978 preserved uncontrolled chats
plus 316,022 controlled chats at exact 15,801/15,802 mode quotas. Pair IDs and
chat `pair_id` values match in every corresponding row.

Superseded on 2026-09-04: the integration and upload prerequisites described
above are complete. The immutable campaign release remains unchanged. A
portable package was generated at
`exports_dfm11/dfm11-fineinstructions-en` and uploaded as
`schneiderkamplab/dfm11-fineinstructions-en` at revision
`80f44dfc3cbc0ac8d6e219cc65bee4275db27414`. Its `pairs` and `chats`
configurations each contain exactly 500,000 rows in five deterministic gzip
JSONL shards. Absolute provenance paths were replaced by stable
`source_id/basename` references; stable source revisions and row/window
coordinates remain. An aligned selection map identifies legacy versus
controlled rows and controlled interaction modes without requiring the private
campaign ledger. The package manifest records SHA-256 and byte size for every
shard. The credential-pattern review found no HF, W&B, AWS, or
private-key strings; apparent `sk-...` matches were ordinary hyphenated prose
and URL slugs.

## Legacy versus controlled-chat quality

A complete release scan on 2026-09-04 compared the 183,978 preserved legacy
chats with the 316,022 controlled-mode chats:

| Measure | Legacy | Controlled |
|---|---:|---:|
| Mean rendered tokens | 1,087.6 | 1,133.3 |
| Exact repeated turn text | 1.62% | 0.55% |
| Any assistant turn under five words | 0.31% | 0.52% |
| Four-message conversations | 0.42% | 45.99% |
| Six-message conversations | 52.37% | 47.79% |
| Eight-or-more-message conversations | 47.21% | 6.22% |

The controlled slice is better for task diversity and exact-turn repetition:
all 20 modes have exact quotas, sampled follow-ups are more purposeful, and
verbatim repeated turns are about one third as frequent. It is not established
as uniformly better semantic data. It inherits the original pair exchange,
including awkward prompts and source artifacts, and is materially shallower as
multi-turn supervision because almost half of its rows contain only one new
user/assistant exchange.

Accepted audit fields cannot resolve this comparison: all shared quality means
round to 5.0 in both slices, and the controlled mode-adherence mean is 4.9987.
Generation and audit are separate requests to the same Gemma 4 checkpoint, so
their errors may be correlated. Most non-empty complaint fields are the literal
string `none`; excluding those leaves real criticism in roughly 0.1% of the
controlled rows. Before upload or DFM11 admission, run a model-independent,
stratified audit by source, mode, and conversation depth, with special checks
for malformed initial exchanges, truncated final prose, source leakage, and
whether the follow-up genuinely depends on prior turns.

## Proposed DFM11 admission mix

Pending project approval and the independent audit, use the conversations as
the primary training artifact rather than training on every pair and its chat:

| Slice | Proposed per-epoch admission | Reason |
|---|---:|---|
| Controlled chats | All 316,022, repeat 1 | Exact 20-mode breadth and the strongest marginal instruction-following value |
| Legacy chats | 100,000 source-balanced rows, repeat 1 | Retain deeper multi-turn and reading-comprehension behavior without allowing the legacy concentration to dominate |
| Pairs represented by admitted chats | Exclude | Their complete user/assistant exchange already begins the chat, so inclusion would duplicate supervision |
| Other accepted pairs | Initially exclude; optional 50,000-100,000 source/task-balanced ablation, repeat 1 | They can add single-turn coverage but are not the distinctive value of this artifact and inherit the same source/prompt defects |

The approved chat-only selection contributes 465,175,486 release-rendered
tokens: 358,143,555 controlled and 107,031,931 legacy. Preserve all 500,000
release rows on the Hub even though the initial DFM11 training selection uses a
deterministic 100,000-row legacy subset. Do not repeat any slice. Admit optional
pair-only rows only from pair IDs absent from the admitted chat set, and compare
their marginal validation effect before expanding them.

## DFM11 integration state

The approved selection is materialized under
`data/converted_dfm11/fineinstructions_english` as two independently named
prefixes. Controlled uses all 316,022 chats. Legacy uses a deterministic
source-balanced 100,000-row sample: all 7,276 available Project Gutenberg
legacy chats and 10,302-10,303 rows from each of the other nine families. The
selection seed is 11031. No represented pair rows are staged.

The final Gemma 4 native-template tokenization completed in 279.8 seconds with eight CPU
workers and a 4,096-token limit. It produced nine tasks, 1,184,450 supervised
assistant targets, zero overlength skips, and 1,033,994,750 stored tokens:

| Prefix | Chats | Assistant targets | Stored tokens | Repeat |
|---|---:|---:|---:|---:|
| `dfm11-fineinstructions-en-controlled__` | 316,022 | 835,770 | 737,680,897 | 1 |
| `dfm11-fineinstructions-en-legacy-balanced__` | 100,000 | 348,680 | 296,313,853 | 1 |

The task arrays are present in `data/tokenized_dfm11_additions`, and both
repeat-one rules are at the top of `data_io/prefix_config_dfm11.yaml`. The
source-specific policy and pinned Hub revision live in
`config/data/dfm11_fineinstructions_english.yaml`.

The aggregate `data/tokenized_dfm11` union could not be rebuilt on the current
host because its inherited `data/tokenized_dfm10/tokenizer_info.json` base is
not present. `scripts/build_tokenized_dfm11_tree.py --force` failed immediately
on that missing prerequisite without modifying the completed addition. Rebuild
the union after transferring or recreating the DFM10 tokenized base; sampling
must wait for that complete union rather than silently sampling additions only.

## Danish silver-label quality gate

The corrected v5 retrieval qualification passed, but this does not make the
subsequent instantiation labels training-ready. On 2026-09-05, 652 of the first
3,736 generated positive rows (17.45%) retained unresolved `<fi>` markers. In a
deterministic 100-row sample, the Gemma self-audit accepted 97 rows, including
all 17 rows with this structural defect. Manual inspection additionally found
awkward, repetitive, underspecified, and task-incoherent examples. Treat the
current production output as a raw candidate pool only. Danish instantiator
training remains blocked on a deterministic unresolved-placeholder gate and a
stricter, independently validated semantic audit.

Raw Danish instantiation generation now uses eight race-free workers, one per
teacher endpoint, with 1,024 in-flight requests and an 8,192-row work window
per worker. The raised 180,000-positive raw target protects the intended
100,000-positive release from strict-audit attrition. At steady state, a
30-second sample measured 91.4% mean KV-cache occupancy and effectively 100%
GPU utilization across all eight B200s; this is the recorded operating point.

Superseded later on 2026-09-05: the `180,000` raw-positive count is an initial
target, not an admission guarantee. Its first strengthened audit retained
101,512 of the required 120,000 positives. The production supervisor now
iterates generation and incremental audit, adding 40,000 unique raw-positive
capacity after each short audit until the audited target is met. Duplicate
candidate IDs no longer count toward worker quotas, quota-skipped candidates
can be revisited after target expansion, and a raw completion marker is valid
only when its stated target was reached. Since all original top-12 candidates
had already been attempted, recovery first creates resumable top-24 retrieval
shards and uses only the genuinely new candidates plus any newly useful
quota-skipped positives. Positive-capable excerpt and JSON-format failures are
regenerated under a stricter exact-copy prompt with a changed deterministic
attempt seed, capped at three total attempts per candidate.

The initial 120,000 audited positives produced only 88,133 rows within the
4,096-token helper limit; 32,822 were overlength. The supervisor therefore
extends the loop through materialization: each short exact selection adds
20,000 to the audited-positive target and 40,000 to the raw-positive target,
then resumes generation and incremental audit. Training remains blocked until
the exact 100,000-positive/5,000-negative in-limit file is written atomically.

Verified later on 2026-09-05: recovery reached 280,000 unique raw positives,
140,000 teacher-audited positives, and the exact 100,000/5,000 in-limit file.
The independent Qwen2.5-14B gate nevertheless accepted only 353/500 rows
(`70.6%`) and made 146 semantic rejections, mainly for label correctness,
usefulness, instruction quality, and grounding. This is a substantive quality
failure; Danish instantiator training remains blocked without weakening the
95% gate.

Qualified later on 2026-09-05: inspection showed that this is not a clean
70.6% estimate of usable-row prevalence. Qwen found genuine defects, but also
systematically rejected valid concrete template substitutions, extractive
continuation tasks, and appropriately selective summaries. It passed all 25
negative labels but only 328/475 positives, and assigned the minimum
label-correctness/usefulness scores to 135/146 parsed rejects. The production
path should use a calibrated independent row-level filter over the full pool,
with explicit examples and stronger deterministic structure checks, and expand
generation until 100,000 independently accepted in-limit positives are
available. The 95% release gate should then validate the filtered output rather
than the pre-filtered teacher output.

Implemented as `independent-v3` on 2026-09-05. The calibrated replay accepted
315/475 positives and 25/25 negatives; 38 positive instructions were rejected
deterministically for leaked `<excerpt>` markup. The production supervisor now
filters the complete in-limit pool and expands teacher retention only when the
100,000/5,000 independently accepted target remains short. Its final artifact
is `silver/instantiator-v2/training-v3.jsonl` with per-row audit profile and
model provenance.

Superseded by `independent-v3`: the earlier follow-on supervisor was
fail-closed. It expanded and merged the raw pool
until the full strengthened teacher audit reaches its retained-row target,
then independently re-audits a deterministic
475-positive/25-negative sample with `Qwen/Qwen2.5-14B-Instruct`. It requires
at least 95% acceptance and zero structural defects before admitting the exact
100,000-positive/5,000-negative training mix and starting eight-GPU
Qwen3.5-4B instantiator training. Failure status 42 blocks training rather than
retrying or weakening the gate.

The helper's 4,096-token limit is enforced before final admission. A 1,000-row
sample found 12.5% of raw labels over that limit, so the full audit first
retains 120,000 positives and 6,000 incompatibles. Final materialization then
writes exactly 100,000 and 5,000 in-limit rows respectively; training no longer
relies on `CompletionDataset` silently dropping overlength labels.

The optimized helper-training runtime is the dedicated `qwen` Conda
environment. Conda owns its CUDA 13.2/compiler stack and native libraries;
Python packages are installed only through `uv pip`. The reproducible command
is `bash fineinstructions/scripts/create_qwen_conda_env.sh qwen`. Its compiled
causal-convolution and FLA gated-delta forward/backward kernels pass on B200,
and Transformers selects the Qwen3.5 fast path.

On 2026-09-06 the Danish 4B instantiator first resumed from epoch-1
`checkpoint-12868` under `qwen`. The optimized batch-one DDP path measured
about 0.39 s/step, compared with about 2.3 s/step for the superseded fallback
run. A subsequent from-base batch-two run uses FSDP1 full sharding, activation
checkpointing, native BF16 parameters/optimizer moments/compute, and the
pretokenized 102,939/2,061 train/validation cache. FSDP2 is currently
incompatible with the tied Qwen embedding/LM-head aliases through the installed
Transformers/Accelerate integration. The verified FSDP run processes about 22
examples/s, or roughly six times the fallback sample throughput.

The independently filtered `training-v3.jsonl` is approved only as helper-
instantiator supervision. Its 100,000 compatible and 5,000 incompatible rows
are structurally valid, in-limit, and generally grounded, but score-4 rows and
awkward synthetic Danish remain. Its JSON and `<excerpt>` target contract must
not be mixed directly into ordinary chat/SFT training. Final helper admission
still requires held-out generated-output checks beyond training/validation
loss.

The run early-stopped at epoch four after validation loss improved from
`0.2605` to `0.2241` at epoch two and then regressed to `0.2387` and `0.2699`.
Trainer restored epoch-two `checkpoint-12868` into `final/`; do not continue
training that checkpoint on the unchanged dataset merely to reach eight
epochs.

The preparation command is restart-safe with `--force` and leaves the immutable
release untouched:

```bash
python scripts/prepare_dfm11_fineinstructions_english.py --force
python scripts/tokenize_chat_template.py \
  data/converted_dfm11/fineinstructions_english \
  -o data/tokenized_dfm11_additions \
  --tokenizer-path ../brainsurgery/models/gemma4_31b/tokenizer.json \
  --chat-template data_io/chat_templates/gemma4_native_chat.jinja \
  --max-seq-len 4096 --workers 8 --force
```

## Danish distillation recovery

On 2026-09-04, four-way Danish retrieval completed with 499,797 unique
candidates, 203 below the original hard minimum of 500,000. This caused the
automatic handoff to exit and retry while GPUs 4-7 were idle; the subsequent
`no managed state` messages were harmless server-cleanup output rather than the
failure itself. The retrieval gate is now 499,000. The downstream requirement
of 100,000 accepted instantiator examples is unchanged.

Superseded later on 2026-09-04: passing the retrieval-count gate did not make
the silver set viable. Gemma labeled 129,612 of 130,000 generated
template/document rows incompatible. The subsequent independent audit accepted
only 14 of its first 8,192 decisions, so it could not possibly reach the
100,000-row target. The automatic handoff was stopped with `HANDOFF_STOP`, and
only its exact managed audit and vLLM processes were terminated. Preserve the
generated ledgers for diagnosis, but do not resume the audit or train the
instantiator from this set.

The observed failure is consistent with the implementation having skipped the
planned Danish retrieval qualification: document-description silver labels,
hard-positive/negative calibration, and a controlled comparison before deciding
whether BGE-M3 needs Danish fine-tuning. Resolve and smoke-test that stage before
regenerating instantiator silver labels. An all-stage ETA is undefined until a
qualification demonstrates a compatibility yield sufficient for 100,000
positives plus at most 5% genuine incompatible examples.

Two source-balanced 2,000-document qualifications then isolated the bottleneck.
Selecting the six highest-scoring templates from the 50,000-row silver bank
produced 27 positives among 6,004 valid teacher labels (0.45%) and covered only
1.50% of documents. Retrieving from teacher-written document capability
descriptions produced 46 positives among 5,969 labels (0.77%) and covered 2.23%
of documents. Both failed closed and their managed servers exited.

The decisive omission was the production templating pass: the published method
trains on roughly 50,000 silver templates and then templatizes a much larger
query corpus, whereas the first Danish launcher indexed the 50,000 training
labels directly. The corrected resumable path prepares 533,900 source-balanced
production queries, including 500,000 from the modernized Danish OpenHermes
corpus; retrains the 2B templatizer with best-checkpoint selection and early
stopping; materializes a 500,000-template production bank; and qualifies that
bank before full retrieval. A first recovery attempt using eight examples per
device OOMed after 12 optimizer steps when Transformers upcast the
full-vocabulary logits to FP32, peaking near 168 GiB on a B200. Superseded on
2026-09-04: the stable setting is four examples per device with two-step
accumulation on four GPUs. It preserves the original effective global batch of
32 and retained at least 47 GiB of headroom through the initial variable-length
training batches.

The retraining completed before the 2026-09-05 power outage and selected
checkpoint 6,104 with validation loss `0.651962`; the fully written final model
and stage marker survived. Production templating had durably flushed 265,669
unique accepted rows and 8,763 retryable failures. A complete JSONL scan found
no malformed or duplicate accepted rows. Restarting the same staged launcher
skipped all finished stages and accepted IDs, retried the prior failures, and
returned to about 5,900 accepted templates per minute after those retries. This
confirms that recovery requires no ledger rollback; only the active unflushed
batch can be lost in an interruption.

As of 2026-09-05, all eight local B200s are assigned to the Danish campaign.
All parallelizable inference and retrieval stages use GPUs 0-7, including
production templating, qualification, full retrieval, and teacher generation
and audit. The 4B instantiator SFT also uses eight DDP workers with per-device
batch one, giving effective global batch eight. The already completed 2B
templatizer retains its four-GPU/global-batch-32 receipt. Shared HNSW index
construction remains single-GPU because that stage writes one serial index.

Generation and audit now count compatible positives and genuine incompatible
negatives independently. Production silver targets are 130,000 positive plus
6,500 negative generated labels and 100,000 positive plus 5,000 negative
audited labels. Audit scores classification correctness rather than literal
pair compatibility for negative labels, and terminal decisions are not retried.

On 2026-09-05, the first production-bank qualification was found invalid: the
teacher prompt allowed both direct and abbreviated excerpt markers, but the
parser handled only abbreviated markers. This systematically rejected most
compatible rows and caused an unchanged supervisor retry loop. The corrected
v5 run source-validates both marker forms, processes all candidates once, and
makes deterministic model-output failures terminal while leaving transport
failures retryable. It retained 3,563 positives and 11,733 incompatibles from
19,827 candidates; its 23.29% positive rate and 67.77% document-hit rate passed
the 15% and 50% gates. Semantic gate exit status 42 now stops the handoff rather
than retrying unchanged inputs. Full production retrieval started after this
receipt passed.

On 2026-09-06, the Danish helper completed and its best epoch-two Qwen3.5-4B
checkpoint was restored under
`data/fineinstructions/dfm11-danish-distillation/models/danish-template-instantiator-qwen3.5-4b-v2-fsdp1-ac-native-bf16-bs2/final`.
The initial production pass now runs through
`fineinstructions/scripts/run_dfm11_danish_500k.sh` with strict structural JSON
decoding and a Danish-specific independent Gemma audit. Its held-out gate
retained 111 of 410 structurally valid generations. The current retrieval bank
is therefore an initial resumable pass, not sufficient evidence for the full
500K release; chat generation remains blocked until 700K audited pairs exist.

Superseded later on 2026-09-06 by an explicit operational decision: the 700K
pair count remains a final-release capacity check, but available audited pairs
are extended immediately rather than leaving GPUs idle. The Danish extension
uses the same 20 controlled modes, language-specific prompts, strict schemas,
3,900-token ceiling, and inline Gemma audit as the English path. Its accepted
ledger is resumable when later retrieval expansions add more pairs.

The first production launch was compute-underfed at 1,024 requests per server.
It was resumed with 4,096 requests per server and 32,768 globally in flight;
this raised steady-state SM utilization to approximately 95-100% while KV
occupancy remained 33-40%. Deterministic incompatibility and validation rows
are now terminal resume decisions, whereas transport failures remain retryable.

The initial production-bank pass finished on 2026-09-06 with 665,698 raw pairs
from 1,919,670 retrieved candidates. The independent Danish audit retained
231,941 pairs and rejected 433,757, giving a 34.84% pair-audit yield and a
12.08% end-to-end candidate-to-audited-pair yield. The first 8,192 chat
extensions retained 8,188 (99.95%), but that small prefix was optimistic: the
complete initial pass retained 214,504 of 231,941 pairs (92.48%). The final
measured capacity contract is therefore 560,000 audited pairs for 500,000
balanced accepted chats rather than the old 700,000-pair planning estimate.

`fineinstructions/scripts/continue_dfm11_danish_500k.sh` is the resumable
capacity-expansion path. It first retrieves top-80 templates per document into
new shard files, targets 1,800,000 raw pairs and 560,000 audited pairs, and then
fills the existing append-only chat ledger to 500,000. If rank degradation
leaves the release short, it automatically retries with top-112 retrieval and
raises raw-pair capacity to 2,300,000.
Previously accepted rows are preserved. Deterministic pair and chat rejects are
also resume-terminal; request/transport failures remain retryable.

Superseded on 2026-09-07 after the balanced-mode tail became measurable: the
aggregate 92.48% chat yield understated the required pair capacity because the
least-filled mode reached only 18,272 of its 25,000-row quota when aggregate
chat acceptance reached 484,831. Uniform mode assignment means the remaining
top-80 pairs cannot close that deficit. The operational target is therefore
700,000 audited pairs, using the planned top-112/2,300,000-raw-pair fallback.

Superseded later on 2026-09-07: deeper pair generation is not required merely
to compensate for modulo assignment. Balanced continuation now builds a
deterministic, deficit-weighted mode schedule from the accepted ledger and
assigns each unused pair directly to an outstanding quota. Modes at quota make
no model requests, deterministic failures remain terminal, and interrupted
runs reconstruct the remaining schedule from persisted mode counts. The first
targeted restart moved from 490,506 to 492,303 accepted chats in 24 seconds of
active client time. Top-112 remains a capacity fallback only if the existing
unused audited pairs truly exhaust before all quotas reach 25,000.

## Danish publication and DFM11 integration

Completed on 2026-09-07: the deficit-targeted pass finished with 503,740
accepted chats. Every one of the 20 controlled interaction modes has at least
25,000 accepted rows; `brainstorming` is exactly at quota and bounded in-flight
surplus accounts for the additional 3,740 rows. The full accepted ledger is the
release: no rows were discarded to force an exactly 500,000-row snapshot.

The portable package is published as
`schneiderkamplab/dfm11-fineinstructions-da` at revision
`80e37a930948c6e52bcaaffa20408842de87732c`. Its `chats` and `pairs`
configurations each contain 503,740 rows in eleven deterministic gzip JSONL
shards. Pair provenance retains source ID, revision, basename, source row, and
window coordinates. Embedded grounding documents are omitted from the package
and replaced by their character counts and SHA-256 receipts. Every chat
`pair_id` was verified against exactly one packaged pair, and local-path and
credential-pattern scans passed.

DFM11 admits all 503,740 chats at repeat one and does not separately admit the
matching pairs. Gemma 4 native-template tokenization completed in 86.9 seconds
with 16 workers and a 4,096-token limit. It produced 1,335,942 assistant
targets, skipped zero overlength targets, and stored 663,788,470 tokens under
the `dfm11-fineinstructions-da__` prefix in
`data/tokenized_dfm11_additions`. The pinned source policy is
`config/data/dfm11_fineinstructions_danish.yaml`; sampling is registered in
`data_io/prefix_config_dfm11.yaml`. Rebuilding the aggregate
`data/tokenized_dfm11` union remains blocked on this host because the inherited
`data/tokenized_dfm10` base is absent; the isolated DFM11 addition itself is
complete.

The locally trained helper models and their exact selected training sets are
also published and remotely verified:

| Artifact | Rows | Revision |
|---|---:|---|
| `schneiderkamplab/dfm11-danish-query-templatizer-training` | 49,808 | `b67725c20718c68609170e0c4e670381141ef0e8` |
| `schneiderkamplab/dfm11-danish-template-instantiator-training` | 105,000 | `3449ffba7e5557453365402a186c8325e3b40894` |
| `schneiderkamplab/dfm11-danish-query-templatizer-qwen3.5-2b` | - | `1beb3475b3d1514cf94f3cc3b13b3f887d7d7c31` |
| `schneiderkamplab/dfm11-danish-template-instantiator-qwen3.5-4b` | - | `c34410ad5209956e671ef59b39fc1094450bf8af` |

The selected models are the best-checkpoint-restored v2 templatizer and the
native-BF16 FSDP instantiator. Superseded intermediate models and optimizer
checkpoints were intentionally not published. The verified publication receipt
is `logs/fineinstructions/dfm11-danish-500k/publication-receipt.json`.
