---
type: Plan
title: DFM16 additions and preparation
description: Approved additions and follow-up synthesis for the next training corpus.
tags: [dfm16, datasets, knowledge, instruction]
status: draft
confidence: high
last_updated: 2026-10-29
---
# DFM16

[English-only validation; other languages held](dfm16-staged-stories.md).

## Staged generation implementation (2026-10-29)

The [staged-generation experiment](dfm16-staged-stories.md) now implements the
previously proposed controlled-source and paragraph-assembly workflow. This supersedes
only the “proposed, not implemented” status from the earlier diagnostic pilot.
Historical failures remain valid. Development and per-language qualification must
finish before any reviewable candidate conclusion; production remains held.

## Context-aware calibration implementation (2026-10-28)

The [new calibration workflow](dfm16-story-calibration.md) preserves the prior
200 conversations as development data, adds focused checks and separate repair
accounting, and gates validation on a frozen qualifying policy. Implementation
tests pass. The earlier pending status is superseded by completed development:
all three policies failed both targets. Of 63 diagnostic repairs, only two passed
the repair gate and both retained defects. Fresh validation was not consumed;
production admission remains blocked. See the workflow for final bounds and cost.


## Qwen pilot completed; production held (2026-10-28)

Completed seed screening (6,993/8,000 accepted), generation/CPU checks
(1,380/2,000 passed), and independent review (**1,073 accepted**, 307 rejected).
Early manual triage of 28 accepted conversations still finds material Danish
and Hindi defects. A separate language-only diagnostic rejects 23/100 sampled
accepts but still misses severe corruption and appears to reject a usable
Japanese rewrite. It is diagnostic, not a proven admission gate.
See [results and examples](../../docs/reports/simplestories-qwen-v3-review-20261028.md).

Production remains held; no rows discarded, no large generation launched, no
DFM16 sampling changes. Do not confuse completion of the pilot with successful
quality qualification. Preserve compact non-thinking judging; prefer a measured
different-judge comparison to endlessly elaborating the same auditor's prompts.
Source audits outside this pilot remain separate workstreams.

## Qwen story remediation and pilot (2026-10-28)

Operational correction: externally owned servers actually use **8500-8507**,
not the originally proposed 8800-8807. Launch our client with `--port-base 8500`;
generation uses 8500-8504 and auditing 8505-8507. UltraData completed all
9,708,091 rows (8,595,404 accepted, 1,112,656 rejected, 31 unresolved), and the
owned Gemma cleanup receipts confirmed no surviving processes on all eight GPUs.

Latest user override: our Qwen clients default to **128 requests/server**,
superseding the initial 256 below. `--concurrency` controls all four stages.
Restarted only our waiting campaign controller; other clients and servers unchanged.

Supersedes Gemma-only generation/review for the next SimpleStories pilot, not
historical journals. User selected **Qwen/Qwen3.8-Flash-Next-FP8** generation on
ports 8800-8804 and **Qwen/Qwen3.8-27B** auditing on 8805-8807, with **256 concurrent
requests per server**. Servers are owned by another thread: this campaign only
waits for matching model IDs and at least 32K serving context; it never starts,
stops or replaces shared servers. Thinking is disabled for both roles; reviews
are plain accept/reject, no JSON schema, at most one retry.

`scripts/queue_dfm16_stories_qwen.py` orchestrates these stages through the existing
rolling `audit_pipeline`, not a second HTTP scheduling implementation:

1. Blind Qwen review of the 100 manually inspected v2 conversations, with human
   review annotations kept separate from model inputs. Compare hold/reject and
   clear/accept; caveats are not binary ground truth.
2. Screen 8,000 seed stories (2,000 per target language). Danish seeds are
   English and reviewed as English before adaptation; do not reject them for
   not already being Danish.
3. Generate 2,000 candidates across four languages and five tasks, using only
   independently accepted seeds. Apply CPU checks for visible initial length,
   exact paragraph boundaries for local edits, selective undo, shortening and
   unchanged/no-op revision responses. Prompt adaptations require the rewrite
   source to have the opposite tense/viewpoint from the requested target.
4. Independently review every conversation, including source quality and all
   accumulated revision constraints. Select five accepted examples per cell
   for manual inspection. **Stop at this gate, not automatic 300K expansion.**

Root: `data/dfm16/expansion-v1/stories/quality-v3-qwen`.
Log: `logs/dfm16/expansion-20261027/stories-qwen-v3.log`.
Status: `quality-v3-qwen/status.json`; each stage has `audit/pipeline/` telemetry
and immutable chunk receipts. Generation and audit are separate durable stages;
model IDs and implementation hashes are sealed in pipeline configurations.
All original 300K and v2 rows remain untouched. No tokenization/admission or
public upload of Qwen pilot output is implied. The Flash-Next license scope for
public synthetic-data publication needs a separate decision; local experimental
generation follows the user's explicit model choice.

The roadmap retains 300K accepted production target, 450K initial candidates
and 600K maximum candidate budget, pending the new manual gate. Review the old
300K's retained subset separately before treating it as clean; never silently
discard or promote those original rows. The optional `audit_pipeline --model`
and three story adapters leave default models and existing tasks unchanged.
CPU verification: 30 tests passed across shared pipeline and story/expansion tests,
including an independent-judge request through the runtime and model-pinned receipt.

## UltraData GPU handoff (2026-10-28)

User requests teardown of the owned Gemma servers after UltraData completes,
before any further GPU tasks. `scripts/finish_ultradata_gpu_handoff.py` pauses
only the current orchestration PID while its independent audit client drains;
then requests the owner's existing cleanup and verifies eight cleanup receipts.
This is a one-off, PID-bound handoff, not a general launcher. Its log is
`logs/dfm16/expansion-20261027/ultradata-handoff.log`.
The other thread will launch Qwen3.8-Flash-Next-FP8 on GPUs 0-4 and Qwen3.8-27B
on GPUs 5-7. Do not launch these here or terminate unrelated servers. Remaining
source audits and CPU finalization are deferred, not declared complete.

## SimpleStories v2 manual review: gate remains closed (2026-10-28)

Reviewed all turns of 100 automatically accepted pilot conversations (five per
language/task cell). See [per-example review](../../docs/reports/simplestories-v2-review-20261028.md).
All 20 revision openings now contain requests and all 40 creative/revision
initial responses meet sampled length ranges. Nevertheless, source corruption
(especially Hindi), no-op transformations, lost revision constraints, and factual
drift survive acceptance. Danish cross-lingual examples need explicit labeling,
not automatic rejection merely for being cross-lingual.

Manual review is complete but **production is not authorized**. Preserve the
old 300K and all journals. The fresh re-audit's accept count is not proof of
cleanliness; do not infer population defect rates from this stratified pilot.
Before scaling, screen seeds, choose applicable transformations, enforce visible
CPU-checkable constraints, and recheck a small sample. Keep compact non-thinking
accept/reject judging. This review did not interrupt ongoing source audits.

## SimpleStories v2 and mandatory re-audit (2026-10-28)

Confirmed queue order: revised 2,000-candidate SimpleStories pilot, full 300K
SimpleStories re-audit, then UltraData auditing (9,708,091 converted candidates).
UltraData is the first source in the expansion registry and now has its complete
readiness manifest. The existing controller handles this handoff using its eight
servers; do not start a competing audit controller or restart current work.

User-approved follow-up: preserve and re-audit **all 300,000** previously accepted
conversations; old acceptance must not silently confer admission. No old rows
were discarded. The complete old materialization and tokens are preserved at
`data/dfm16/expansion-v1/held/simplestories-v1`; original generation/audit journals
remain under `stories/wave-*`. `stories/admission-hold.json` prevents the old
materializer from recreating an admitted corpus. The quarantined directory has
an explicit non-admitted receipt, and tokenization rejects quarantined sources.

`scripts/prepare_dfm16_stories_v2.py` prepares:
- `stories/quality-v2/reaudit`: all 300K IDs, with source hashes and fresh compact
  whole-conversation review instructions. No pre-existing accept is reused.
- `stories/quality-v2/pilot`: 2,000 fresh candidates, 100 per language/task cell,
  explicitly sampled genre/tone/viewpoint/ending/audience/length and revision
  operations. Japanese uses character lengths. Revision openings must contain
  an explicit request. Exact user echoes and unexpected reasoning are rejected.

The expansion controller runs the pilot, writes per-cell acceptance counts and
100 manual-review examples using `scripts/report_dfm16_stories_v2.py`, then runs
the full re-audit. Only newly accepted old rows can be materialized separately
as `accepted/simplestories-reaudited-v2`. All negative/unresolved decisions remain
in the journal; the original corpus is retained. The new pilot is **not**
automatically admitted, and production remains blocked on manual review.
Production proposal after passing that gate: 300K accepted, 450K initial
candidates, capacity for 600K, balanced replenishment with fresh candidates.
Reviews remain non-thinking plain accept/reject with at most one retry for
invalid responses/transport errors. Do not add verbose judging scaffolding.

At launch the GPUs were occupied by other vLLM workloads, so the controller
waits for free GPUs without terminating those processes. The restart also
records unresolved JSON Schema references as row-level failures and disables
implicit external reference retrieval; completed structured-generation journals
are preserved with the prior implementation seal archived.

## October 28 recovery and manual quality review

Supersedes the interrupted-controller status below. UltraData now runs with
32 file-level CPU workers via `scripts/resume_ultradata_parallel.py`, not the
old source-level pool. Completed serial chunks are preserved; the boundary
file is replayed, and one deterministic merger deduplicates against the prefix.
Per-file receipts permit restart without rerunning completed files. Progress:
`data/dfm16/expansion-v1/converted/openbmb__UltraData-SFT-2605/parallel-status.json`.
Log: `logs/dfm16/expansion-20261027/ultradata-parallel.log`.

The structured-answer preparation failure was a JSON Schema dialect mismatch.
`scripts/dfm16_schema.py` preserves declared dialects and normalizes legacy
boolean bounds/required properties in undeclared schemas, without rewriting
literal examples or weakening modern constraints such as `const`. Malformed
schemas are held with provenance and errors: 9,292 prepared, 145 held out of
9,437. The recovery GPU controller resumes existing audit journals and includes
UltraData after its conversion; no corpus sampling is authorized. Recovery log:
`logs/dfm16/expansion-20261027/recovery.log`. Focused tests: 26 passed.

Manual review of 20 accepted SimpleStories conversations (one per language/task
cell; fixed seed 20261028) is saved under
`docs/reports/simplestories-review-20261028/`: `samples.jsonl`,
`conversations.txt`, and `assessment.md`. Qualitative triage: 7 clean, 7 with
caveats, 6 needing repair before scaling. This is not a population defect-rate
estimate. Keep the completed 300K pilot; **do not scale the recipe unchanged**.
All four sampled revision openings lacked an instruction, and the creative/
rewrite styles were repetitive. Improve opening supervision, diversify explicit
constraints, distinguish cross-lingual tasks, and repair language defects before
a larger campaign. No additional SimpleStories production was launched.

## Expansion and SimpleStories pilot (2026-10-27, latest decision)

**Supersedes the automatic resampling authorization below:** continue the Dyna
audit and accepted-only CPU tokenization, but do not rebuild/sample DFM16 yet.
The existing sampled corpus remains unchanged. `queue_dfm16_dyna` now defaults
to no sampling; rebuilding requires an explicit `--sample` argument. The waiting
controller was restarted without that flag, before any GPU audit started.

The complete expansion registry is `config/dfm16_expansion.json`. Acquisition
pins repository revisions, retains cards and records individual access failures.
Research and existing-source overlap caveats are in
[the additional-source review](dfm16-additional-source-review.md).

### GPU order and CPU overlap

1. Finish the existing 24,111-row Dyna audit when GPUs become free. Unrelated
   processes are never stopped. Accepted Dyna tokenization proceeds on CPU.
2. Run the **300,000 accepted-conversation SimpleStories pilot** on eight shared
   Gemma 4 26B-A4B servers, through `audit_pipeline`, concurrency 256/server.
3. Audit ready converted additions, then generate/schema-validate/review the
   NVIDIA structured-output answers. Other generation inputs are queued behind
   SimpleStories but held until their source-specific verification is ready.
4. Materialize accepted rows and tokenize with the safe HF implementation,
   64 workers per tokenization job. No sampler or training launcher is called.

CPU downloads, conversion and seed preparation can overlap all GPU work.
The GPU controller waits for the Dyna audit-completion receipt and prepared
story manifest, then for two fully-free GPU checks. It starts/stops only its
own servers. Accepted rows and completed chunks survive restarts. Plain
non-thinking accept/reject review, no JSON grammar for reviews, at most one
retry, no request spacing or chunk-tail scheduling barriers.

### Pilot quotas (accepted conversations, repeat 1)

| Language | Creative writing | Multi-turn revision | Summary | Rewrite | Narrative QA | Total |
|---|---:|---:|---:|---:|---:|---:|
| English | 60,000 | 60,000 | 30,000 | 30,000 | 20,000 | 200,000 |
| Danish | 15,000 | 15,000 | 7,500 | 7,500 | 5,000 | 50,000 |
| Japanese | 7,500 | 7,500 | 3,750 | 3,750 | 2,500 | 25,000 |
| Hindi | 7,500 | 7,500 | 3,750 | 3,750 | 2,500 | 25,000 |
| Total | 90,000 | 90,000 | 45,000 | 45,000 | 30,000 | 300,000 |

Revision conversations contain an initial story plus two/three/four revisions
in 60/30/10 proportions. Every assistant turn is supervised: tokenized target
counts exceed conversation counts and must be reported separately. Generation
uses natural chat in the target language, complete responses and no literal
reasoning/control tags. Source metadata are not presumed true. Story facts and
unaffected details must survive requested summaries/edits; fantasy is allowed,
but not treated as real-world factual supervision.

Sample broadly over complete train files using a deterministic reservoir.
English and Danish use disjoint English seed partitions; Japanese can be
independently generated, not translated. Hindi uses the parallel English/Hindi
release. Preserve family IDs for translations/derived tasks. Supplemental Hindi
and JA/EN-ending releases are downloaded for overlap/unique-content inspection,
not blindly combined. Ten bounded replenishment waves can fill rejected slots;
unmet quotas fail visibly rather than silently reducing the target.

### Full candidate inventory

| HF repository | Preparation / status |
|---|---|
| `SimpleStories/SimpleStories` | Downloaded; English seeds and Danish adaptations. |
| `SimpleStories/SimpleStories-JA` | Downloaded; independent Japanese seeds. |
| `SmallScale/Simple-Stories-Eng-Hin` | Downloaded; Hindi seed stories and shared lineage. |
| `SmallScale/Simple-Stories-Hindi` | Downloaded; overlap inspection before supplemental admission. |
| `keenanpepper/simplestories-ja-en-endings` | Downloaded; translated ending passages only, overlap inspection. |
| `openbmb/UltraData-SFT-2605` | Initial 403 superseded by access approval; retry actively downloading. Native chat/reasoning conversion and source audit. |
| `Nanbeige/ToolMind` | Native tool-schema/call/result conversion; invalid/ambiguous rows held. Audit after pilot. |
| `SWE-bench/SWE-smith-trajectories` | Successful trajectories only; XML representation includes definitions missing from tool representation. Convert definitions, calls and observations to native tools. Select complete assistant targets with all preceding context intact; omit later targets exceeding 4K rather than rejecting every long trajectory. |
| `open-thoughts/OpenThoughts3-1.2M` | Native reasoning conversion, complete-context fit, audit; inherited OT2/code overlap remains to reconcile. |
| `nvidia/Nemotron-RL-instruction_following-structured_outputs` | Train prompts/schema downloaded. Generate answers, JSON-schema check and semantic review after pilot. |
| `MiniMaxAI/SynLogic` | Downloaded train prompts/verifier metadata. Queue solution generation; requires task-specific verifier integration before admission. |
| `nvidia/Nemotron-RL-Agentic-Conversational-Tool-Use-Pivot-v1` | Downloaded; reference actions exist. Convert Responses histories and reference targets, then audit. |
| `nvidia/Nemotron-RL-Agentic-Function-Calling-Pivot-v1` | Downloaded; same native reference-action conversion, schema validation. |
| `nvidia/Nemotron-RL-Agentic-SWE-Pivot-v1` | Downloaded; same conversion, preserving observations and rejecting unsupported embedded protocols. |
| `nvidia/Nemotron-RL-agent-calendar_scheduling` | Downloaded; needs generated answers with calendar-state verification. Held from training pending verifier. |
| `nvidia/Nemotron-RL-agent-workplace_assistant` | Downloaded; convert explicit reference calls; rows lacking references remain pending generation. |
| `allenai/Dolci-Instruct-RL-7B` | Downloaded; reconcile existing coverage, then generate/verify missing solutions. Prompts alone are not SFT. |
| `allenai/atomic` | Hub card/loader downloaded; actual data uses an external archive. Reconcile ATOMIC/ATOMIC2020 coverage before acquisition or new synthesis. |

Existing-coverage checks, not duplicate blanket imports:
`HuggingFaceTB/{smoltalk,smoltalk2}`, `OpenCoder-LLM/opc-sft-stage2`,
`HuggingFaceH4/ultrachat_200k`, `allenai/IF_multi_constraints_upto5`,
`PleIAs/SYNTH`, OpenThoughts2, MegaScience/TextbookReasoning and existing
xLAM/ToolACE/Nemotron sources. All earlier approved decision sources, Hetionet
and Dyna additions remain included in the DFM16 plan; this extension does not
replace them. Laya remains a separate gated-access check.

### Operations and honesty of status

Data: `data/dfm16/expansion-v1`; logs: `logs/dfm16/expansion-20261027`.
Commands: `python -m scripts.acquire_dfm16_expansion`,
`python -m scripts.prepare_dfm16_expansion --wait`,
`python -m scripts.prepare_dfm16_stories`, and
`python -m scripts.queue_dfm16_expansion` (all from repo root in `hrm`).
The last command is the GPU dependency controller, not a second request engine.
Source audits and story generation use the existing rolling shared runtime.
Inspect `status.json`, per-source conversion receipts and `followup-queue.json`:
downloaded, converted, audited, tokenized and sampling-integrated are distinct.
Pending verifier work and malformed rows are never silently marked complete.
CPU conversion runs four independent source workers; tokenization uses 64 safe
HF workers. Pilot inputs are prepared: 2,355 chunks / 300,000 first-wave slots,
with seed reservoirs of 120K English, 30K Danish, 20K Japanese and 20K Hindi.
Slots are not accepted rows; replenishment is required for any rejections.
Focused tests: 51 passed, covering shared runtime, native conversion defaults,
new quotas/contracts, reference actions, SWE protocol conversion and queue safety.
Thirty inspected successful SWE XML trajectories converted structurally; one
real trajectory had two whole targets fitting 4K and thirteen later targets held.

### October 27 GPU startup recovery

The first Dyna server lifecycle (`servers-1793122179579932402`) failed after
passing the free-GPU check: engine startup saw only 17.81/178.39 GiB available,
below the configured 0.95 reservation. This was later memory contention, not a
CUDA import/compiler failure. Owned servers were cleaned up. Once the owner
reported the GPUs free again, all eight were verified at 0 MiB/0% and the Dyna
controller was restarted without sampling. New lifecycle:
`logs/dfm16/dyna-audit-sample-20261027/servers-1793126781125090283`.
Retain 0.95 for genuinely free GPUs; do not kill unrelated occupants or silently
lower the allocation to work around a competing launch. The free-GPU check is
not an exclusive machine-wide reservation.

This lifecycle uses vLLM 0.27.1, Gemma 4 26B-A4B-it, ports 8800-8807,
32K context, 1024 server sequences and 256 audit requests/server. Startup
was slow on WekaFS: vLLM did not automatically prefetch this filesystem;
sequential reads warmed the two weight shards. After weight loading and
Torch compilation, FlashInfer Blackwell MoE kernel compilation was observed
running under Ninja with 16 workers. GPU idleness during this stage is not
evidence of active auditing; wait for server readiness and request counters.
The configured 0.95 allocation is a memory budget, not GPU compute utilization.

Measured completion: the FlashInfer `fused_moe_100` Ninja log recorded 267
build entries and 884378 ms elapsed (14m44s), with the shared library linked
successfully. GPU0 finished CUDA graph capture at 20:28:40 in four seconds.
At 20:29 all eight processes remained alive but HTTP readiness was still false;
successful compilation alone does not establish that the audit has started.

At 20:32 all eight HTTP servers became ready after further TileLang imports
blocked on WekaFS reads. The audit then actually processed requests (GPU0's
log contains over 3000 request/throughput lines), completing 24111 reviews:
17532 accept, 6579 reject. Accepted-row tokenization completed without sampling
at 20:34. The expansion controller started its server lifecycle
`logs/dfm16/expansion-20261027/servers-1793129717498599611` for SimpleStories.
An initial live diagnosis that receipts were merely reused was incorrect;
request logs and receipt timestamps show real auditing during this lifecycle.

The first expansion startup then failed because mimir-decide Qwen servers
claimed GPUs concurrently. Do not stop those unrelated processes. At owner
request the expansion controller was relaunched detached as PID 1396127;
verified phase `waiting_for_free_gpus`, checking every 30 seconds and requiring
two free checks. SimpleStories remains first, followed by ready source audits
and structured-output generation/review. This free-memory check is still not
a machine-wide reservation. UltraData download is complete and CPU conversion
continues. Other completed conversions offer 374379 audit candidates before
UltraData: ToolMind 246720, SWE-smith 19258, OpenThoughts3 25480, conversational
tool Pivot 79737, function-calling Pivot 2106, workplace 1078. These are not
accepted training rows. SynLogic, calendar, Dolci RL and missing workplace
answers still need verified-generation adapters; ATOMIC payload/overlap review
is unresolved. No new sampling is authorized.

### Verified answer adapters and ATOMIC review (2026-10-27)

**Supersedes the missing-adapter/ATOMIC-payload blockers above.** Implemented
`prepare_dfm16_verified_answers`, `dfm16_verification`, and the isolated
`dfm16_verifier_worker`; extended the existing `answers` adapter and expansion
controller. The waiting controller was reloaded as PID 1529407. It remains
detached, waits for free GPUs, runs SimpleStories first, then ready source
audits and all prepared answer-generation campaigns. No sampling.

| Source | Generation candidates | Verification |
|---|---:|---|
| SynLogic | 47,717 | Upstream task-specific puzzle verifiers; legacy think/answer instruction prefix removed from prompts. |
| Calendar scheduling | 2,546 | Exact event IDs/durations, time windows, permanent constraints and no overlaps; semantic review also checks names/history. |
| Dolci code | 19,866 | Supplied assertion tests, then semantic review. |
| Dolci math | 63,998 | `math_verify` against private references, then semantic review; final boxed answer contract. |
| Dolci instruction following | 37,566 | All constraints must pass pinned Open-Instruct IFEvalG checks, then semantic review. All 54 used checker IDs exist. |
| Dolci general/reference quality | 45,239 | Explicitly reference-guided semantic review, not claimed as executable verification. |
| Workplace missing references | 0 fitting | Tool-aware semantic adapter implemented, but all 170 prompts exceed 3500 prompt tokens with complete definitions. No definition removal/truncation. |

There are 216,932 new candidates above, plus the existing 9,437 structured
extraction prompts. Prompt-only rows are not training data. Generation and
review remain non-thinking; reviews are plain accept/reject, with at most one
retry. Deterministic wrong answers are rejected without regeneration retries.
Review evidence/references are never passed to the generator. Only the newly
generated assistant target is supervised, with its full history retained.

Pinned verifier checkouts under `data/dfm16/expansion-v1/verifiers`:
MiniMax-AI/SynLogic `d8c527fd17edb739172619efb9b681805fc74b8d` and
allenai/open-instruct `98de7b4b76564626b057e391291dfa32fc6abeab`.
Some upstream puzzle verifiers use `eval`; run them and generated code in
PID/network namespaces with Landlock filesystem restrictions and resource/time
limits. No credentials are inherited; repository reads and outbound networking
were tested denied. Bubblewrap was installed but cannot remount WekaFS read-only
in this container, so it is not used. Linux `unshare` and Landlock ABI >=3 are
required; isolation errors fail closed. CPU verification runs outside the shared
runtime's serialized preparation lane, bounded to eight checks per endpoint.
Additional dependencies were installed with `uv pip`: `markdown` and
`immutabledict`; NLTK `punkt_tab` is under `data/nltk_data`. Focused suite: 64
tests passed, including valid/invalid code/math/IFEval and isolation checks.

ATOMIC external archive acquired from the URL in the pinned HF loader:
`https://homes.cs.washington.edu/~msap/atomic/data/atomic_data.tgz`.
`prepare_dfm16_atomic` records its checksum and parses CSV/JSON without executing
the dataset loader or extracting arbitrary archive members. Comparison against
`data/dfm14/knowledge-pilot-v1/atomic-train-relations.jsonl` found 592,451 of
592,476 training triples already covered (99.9958%). Only 25 new triples across
22 relation rows enter the source-audit queue as tentative commonsense Q&A.
Dev/test files were measured but not admitted. Comparison normalizes Unicode,
case, whitespace and terminal periods; it is not semantic paraphrase dedup or
proof that every inherited seed was trained. Evidence is in
`data/dfm16/expansion-v1/downloads/allenai__atomic/overlap.json`.

### October 28 status: generation queue interrupted

At 03:21 the expansion controller is not running and all GPUs are free. It
failed October 27 at 22:47 while preparing NVIDIA structured-output prompts:
`exclusiveMinimum: true` in an upstream schema fails Draft 2020-12 validation
(which requires a numeric bound). Schema dialect handling must be repaired
before resuming; do not silently drop the bound or claim GPU work complete.
SimpleStories did finish all 300000 accepted conversations, including quota
replenishment, and tokenization: 524818 assistant targets / 392409179 tokens.
ToolMind, SWE-smith, OpenThoughts3, conversational/function Pivot, workplace
and ATOMIC source audits completed. Verified-answer generation did not start.
UltraData conversion remains active (10.064M input rows, 7.975M audit candidates
at this snapshot); its audit was skipped while preparation was unfinished.
Recovery must include it explicitly, not merely resume the answer generation.

## Approved Dyna refresh (2026-10-27)

Owner approved proceeding with the October 27 shortlist. Preparation command:
`python -m scripts.prepare_dfm16_dyna --workers 64`.
Inputs are pinned by `docs/reports/dyna-source-scan-20261027/inventory.json`.
This command does not mutate the published sampled DFM16 corpus.

- `oliverkinch/dynaword-no-bt`: native Gemma chat conversion and safe HF
  tokenization complete, 6,013 examples / 3,845,263 tokens, all within 4K.
  Repeat 1, language provenance category 2. Original prompt, target, source
  metadata and IDs are preserved. Exact within-source conversation duplicates
  are checked; inherited corpus-wide content overlap is not yet established.
  Prepared receipt: `data/dfm16/dyna-v1/dynaword-no-bt/prepared.json`.
  Next sampling can explicitly include it using
  `--additional-source data/dfm16/dyna-v1/dynaword-no-bt/prepared.json`.
- `syvai/danish-dynaword-laya`: approved **ctx1024 train only**; download
  currently blocked by gated-access HTTP 403. No converter claimed verified
  against unseen payloads. Fetch test only to verify disjoint `doc_id`s; never
  combine the 16K and 1K representations. Inspect choice/score/boolean target
  types and retain any supplied uncertainty instead of inventing hard labels.
- Norwegian NVA CC-BY/CC-BY-SA/CC0 and Swedish RD-SOU/RD-DS: bounded
  document-grounded transformation preparation, not raw-text admission.
  Hash-rank documents across each complete file, at most 2,000 documents per
  component, one complete window up to 1,500 tokens per selected document.
  First bound complete sentences/paragraphs to 8,000 characters using the
  existing `dfm12.transform.window`: PDF exports can contain whole-book single
  paragraphs, which made token-based window selection unnecessarily slow.
  Reuse `dfm14.transforms` for denoising, prefix continuation, span filling,
  and paragraph reordering. Retain source, revision, document ID, row and
  licence partition. Language identification distinguishes nb/nn/sv and holds
  English or uncertain windows; semantic/language/OCR review is still required.
  Initial Swedish samples have fused words and PDF spacing damage.

The report candidates use 256-row chunks compatible with `audit_pipeline`:
`python -m audit_pipeline audit --root data/dfm16/dyna-v1/grounding
--output data/dfm16/dyna-v1/audit --concurrency 256 --ports 8800,8801,8802,8803,8804,8805,8806,8807`.
Start only against verified shared Gemma endpoints. No new reviewer or server
launcher is introduced. Audit acceptance, inherited-source overlap checks and
accepted-only tokenization remain admission gates for these transformations.
Grounded QA/summary generation remains follow-up, not a completed output.
Training, evaluation plans and existing sampled epochs remain unchanged.

CPU preparation completed: **6,072 selected documents**, **5,459 retained
windows** (1,873 nb; 400 nn; 3,186 sv). There are **18,098 audit candidates
in 71 chunks**: 5,459 each for denoising, prefix continuation and span filling,
plus 1,721 paragraph reordering. The other 3,738 windows lack three distinct
paragraphs; no artificial paragraph boundaries were invented. Document holds:
234 uncertain/out-of-scope language, 368 insufficient complete window, 11 empty
window. These are CPU checks, not a semantic acceptance rate.
Outputs: `data/dfm16/dyna-v1/grounding/{seeds.jsonl,manifest.json,receipt.json}`.
GPU auditing has not started: unrelated Mimir-Decide servers began using the
GPUs during preparation and were left untouched. No new epoch has been built
from these additions yet. Seven focused conversion/sampling tests pass.

### Queued audit through full sampling (2026-10-27)

Owner subsequently requested automatic auditing, tokenization and full DFM16
sampling when GPUs become available. Detached controller:
`python -u -m scripts.queue_dfm16_dyna --workers 64`.
Work directory: `logs/dfm16/dyna-audit-sample-20261027`; `status.json` gives the
phase and `controller.log` contains the complete downstream CPU/sampling log.
After the Weka publication fix, observed controller PID is 447969, waiting for
GPUs, not a server PID (supersedes initial waiting controller 218439).

The immutable combined audit input has **24,111 rows / 95 chunks**, including
all 6,013 Norwegian instruction pairs as well as the 18,098 transformations.
Wait for two free checks 30 seconds apart: no GPU compute processes and less
than 1 GiB used on every GPU. Zero utilization alone is not sufficient; never
kill the unrelated resident servers. Reuse the owned eight-replica Gemma 4
26B-A4B launcher, conda `audit`, ports 8800-8807, utilization 0.95, server
max sequences 1024, 32K context. Reviewer concurrency is 256/server, no
thinking, plain accept/reject, one retry, using `audit_pipeline`.

After review, stop only the owned servers before CPU work. Validate every
input/result ID and journal checksum; unresolved review errors fail closed,
not silently become rejections. Convert accepted rows per source, tokenize
with the safe HF implementation and 64 workers, repeat each new source once.
Rebuild **all three epochs** from unchanged DFM15 plus all previously prepared
DFM16 additions and these accepted sources. Laya remains explicitly excluded
pending access and verified conversion; this does not block the accessible
campaign requested here.

Build at `data/sampled_dfm16_dyna_verified`, verify every inherited/new index
through the existing full sampler, then publish at `data/sampled_dfm16`.
**Preflight correction:** WekaFS returns EINVAL for `renameat2(RENAME_EXCHANGE)`.
Use a journaled, locked two-rename handoff with rollback and restart recovery
instead; this has a brief path gap, not atomic-exchange semantics. The previous
corpus remains at `data/sampled_dfm16_before_dyna_20261027` as a backup.
Metadata/template paths and receipt hashes are corrected before
publication. Ownership markers make publication recovery idempotent; changed
inputs or unowned build directories are rejected. Finally refresh
`docs/dfm16-mix.md` and `data/dfm16/mix-comparison.json`. No training is launched.
Eleven focused queue/conversion/sampling tests pass, including atomic exchange
where supported, Weka-style fallback and interrupted-handoff recovery,
recovery without publishing twice, and metadata-tamper refusal.

Conversion/tokenization operations: [decision preparation](dfm16-decision-preparation.md).
Owner explicitly requested no sampling yet (2026-10-26).

### Sampling authorization (2026-10-26, later update)

The no-sampling instruction above is superseded: owner requested sampling and
a DFM15/DFM16 mix comparison, allowing higher repeats for smaller valuable
sources. `scripts/sample_dfm16.py` preserves all three transferred DFM15 epochs
from `incoming/mimir-xl-20261015/data/sampled_dfm15` and interleaves additions.
It writes a separate `data/sampled_dfm16`, leaving DFM15 and active jobs alone.
The inherited 4097-token index limit (4K training context plus shift) applies
to complete examples; long examples are excluded without truncation.

Repeat 3: NLI4CT, FEVER gold evidence, typed-decisions, QuALITY, executable
curriculum. Repeat 2: Nemotron knowledge MCQA, AgentTraj-L, CommitPackFT,
PubMedQA. Repeat 1: OpenScience, WebJev, Mind2Web, both Open-Jev versions,
Hetionet. These are exposure decisions, not new semantic quality judgments.
Hetionet remains at one because of the documented review caveats.

Preparation completion supersedes the pending-conversion/tokenization claims
below: all 13 HF decision additions, curriculum and Hetionet are prepared.
The measured eligible addition exposure is **3,566,712,534 tokens per epoch**.
Expected mean total: **138,082,851,704**, versus DFM15 **134,516,139,170**.
Sampling completed and published: `data/sampled_dfm16/ready.json` exists.
All three epochs passed full index read-back comparison, preserving every
inherited index sequence and exact inherited token totals. Epoch totals are
138,083,343,268; 138,082,420,772; and 138,082,791,073 tokens respectively.
Each adds 4,558,146 occurrences from 2,938,682 eligible unique examples;
857,324 prepared examples are length/empty-response excluded. Nothing was
truncated, and no training or evaluation job was modified.
`scripts/report_dfm16_mix.py` generates `docs/dfm16-mix.md` and
`data/dfm16/mix-comparison.json` from published receipts and epoch-zero
source-domain sidecars. The latter categories describe provenance, not
per-example semantic classifications or Danish/English language counts.
The inherited source-domain sidecar exists only for epoch zero; DFM16
preserves/extends it there and does not invent sidecars for epochs one/two.
Ordinary training does not need them; metadata-biased multi-epoch pilots
would need the remaining sidecars prepared separately.

Use `data=dfm16` for the new sampled path. Reproduce with
`python -m scripts.sample_dfm16`, then `python -m scripts.report_dfm16_mix`.
The builder refuses an existing final directory, takes a filesystem lock,
uses a private inherited token-store copy, and publishes by directory rename.
Focused sampling/conversion/tokenizer tests: 18 passed. OKF validation still
reports the pre-existing oversized request-shared-eval-scheduler page and
15 unresolved artifact links; no new structural wiki findings were introduced.

Additional source triage: [Mimir-Decide candidates](dfm16-decision-source-review.md)
(2026-10-26; recommendations only, no new admission).

## Approved decision additions (2026-10-26)

Owner subsequently approved **all high and medium priorities**, superseding
the recommendations-only status above. Registry:
`config/dfm16_decision_sources.json`, consumed by the downloader's
`dfm16_decisions` group. It pins 13 HF repositories, exact selected files,
conversion requirements, source-review/overlap status, and repeat 1 initially.
Existing Mimir-Decide snapshots are present locally; do not redownload merely
to copy them into a differently named directory. The registry allows separate
Hub reconstruction through `scripts/download_training_datasets.py`.

Includes Nemotron knowledge MCQA, OpenScienceReasoning-2, WebJev, Mind2Web,
AgentTraj-L, NLI4CT, FEVER gold evidence, LocalLLaMA typed decisions, both
Open-Jev versions, CommitPackFT, QuALITY and PubMedQA. The local eight-family
executable curriculum is included too. Lower-priority sources are not added.

`python -m scripts.prepare_dfm16_decision_curriculum` converted **90,120 train
rows** to messages at `data/dfm16/decision_curriculum/input/train.jsonl`;
development rows excluded, source/group provenance retained, verification
answers never inserted into prompts. Numeric option identifiers support
more than 26 options. No invented reasoning. Receipt includes source hash
and per-family counts. It is not yet tokenized or sampled.

The 13 HF additions are registered/downloaded but **conversion is pending**;
approval is not a claim of completed tokenization or inclusion in a sampled
DFM16 epoch. Avoid duplicate LocalLLaMA `all` plus component configs, duplicate
Open-Jev-v1.1 raw/Parquet copies, and PubMedQA unlabeled rows (already omitted
from selected files). Pending checks include OpenScience/MCQA overlap,
aggregate-source novelty, native tool contracts, and explicit partitioning
for unsplit CommitPackFT. Source terms unresolved in the inspected registry
remain recorded, not silently declared resolved by inclusion approval.

## Hetionet addition

### Inclusion decision (2026-10-23, after sample review)

Owner approved tokenizing and including the current train split as-is.
This supersedes the review recommendation below to audit/correct before
training: further auditing, corrections and natural QA/chat synthesis are
**non-blocking follow-ups**, not DFM16 readiness conditions. Retain the
sample findings for review; do not silently discard flagged rows.

Preparation command: `python -m scripts.prepare_dfm16_hetionet` in the hrm
environment. It uses the newer HF-backed `scripts.tokenize_chat_template`
with 64 CPU workers, not the historical bulk Rust tokenizer. It partitions
the single train Parquet into 64 contiguous parts, preserves all message
pairs, and uses DFM15's Gemma 4 tokenizer/native template with thinking off.
No truncation or additional synthetic reasoning is requested. Outputs:
`data/dfm16/hetionet/tokenized`; validated row/token counts and tokenizer
hashes: `data/dfm16/hetionet/prepared.json`. No sampling or DFM15 modification.
Completed successfully: **439,906 rows, 19,114,150 tokens**, 64 parts,
zero skipped rows. Validated row counts and token-array lengths.

Owner decision, October 23: include
[`schneiderkamplab/synth-kg-text-hetionet`](https://huggingface.co/datasets/schneiderkamplab/synth-kg-text-hetionet).
Registered as `dfm16_synth_kg_text_hetionet` in the downloader, pinned to
`24eed50a87b43c5bb384b3bd0204692d43506a44`. This is source registration and a
preparation plan, not a claim of completed download, tokenization or sampling.
DFM15 and active training remain unchanged.

The inspected card reports 439,906 training rows, 24,525 validation rows and
24,389 test rows. Generation used Qwen/Qwen3.6-35B-A3B on Hetionet v1.0.
The dataset already contains `messages`, not merely raw graph verbalizations.
The build report covers atomic QA, MCQ, multi-hop QA, relation classification
and support classification. Thus additional synthesis should improve natural
use of knowledge rather than recreate formats already present.

Preparation:

1. Download the pinned train split and its metadata. Keep validation, test,
   seen-fact/unseen-phrasing and compositional subsets out of training.
2. Inspect a stratified sample per task and relation, checking answers against
   `source_triples`, entity IDs, relation direction and negative construction.
   Preserve provenance, graph-unit IDs, source references and per-row licenses.
3. Convert messages through the existing Gemma 4 native template pipeline.
   Preserve role boundaries; do not invent reasoning or add literal think tags.
4. Check duplicate graph facts and paraphrases against inherited sources;
   report unique facts as well as rows and token volume. Start with repeat 1
   as a proposal, adjusting only after measuring exposure and quality.
5. Tokenize with the safe HF implementation, register in the eventual DFM16
   assembly and report actual per-epoch contribution before sampling.

## Natural QA and chat synthesis

### Download and random-sample review (2026-10-23)

The initial registration-only status above is superseded for downloading:
the pinned train split and metadata are now downloaded to
`data/downloads/datasets/dfm16_synth_kg_text_hetionet` (about 120 MB).
No conversion, repair, tokenization or training inclusion has been performed.
Downloader command requires `--groups dfm16 --only dfm16_synth_kg_text_hetionet
--download --max-workers 4`; default groups alone do not select this source.

`scripts/sample_hetionet_review.py` selected 100 uniformly random training
rows without replacement, seed 20261023. Sorting selected row indices for
reading does not stratify or bias the sample. Artifacts live under
`logs/analysis/dfm16_hetionet_review_20261023/`: `sample.jsonl`,
`sampling.json` (indices and source SHA256), `review.jsonl` and
`review_summary.json`. `scripts/record_hetionet_sample_review.py` records the
assistant's manual annotations, not automated judgments. All 100 message
pairs and supplied triples were inspected, without GPU work.

| Screening outcome | Rows |
|---|---:|
| Provisionally usable | 74 |
| Recommended semantic/scope repair | 18 |
| Optional language polish | 8 |

The sample contains 19 atomic QA, 25 MCQ, 11 support classification,
20 relation classification and 25 multi-hop QA examples. English is generally
readable; no role corruption or literal think markup was observed.

Repair flags: four unscoped negative evidence claims; three unsupported
"most similar" comparisons; three implied unique gene answers; six disease
expression statements needing observational rather than causal wording;
one gene/protein binding confusion; one expression/activity conflation.
These are screening judgments, not verified biomedical falsehood counts.

Examples (zero-based sample indices):

- 21: asks which compound is *most* similar to Levomethadyl Acetate;
  one Loperamide similarity edge supplies no comparative ranking.
- 46: denies evidence for SPZ1 under-expression in articular capsule;
  supplied evidence is a bone-marrow edge, not a literature search.
- 41: asks which *gene* Glutathione binds; the intended target is the
  protein product of GGT1.
- 75: says Erlotinib increases gene *activity*; the edge says upregulates.

Recommendation: audit/correct before training, prioritizing these relation
and negative-construction patterns, with deterministic checks where possible
and a concise graph-grounded review for remaining semantic cases. Do not
ask an LLM to certify medical truth from memory. Missing edges cannot prove
real-world falsity, and MCQ distractor uniqueness needs more than the single
stored positive edge. All sampled prompts omit their evidence triples;
multi-hop QA therefore primarily teaches graph recall, not reasoning over
provided evidence. Add grounded-context variants in future synthesis.
An independent source-level factual audit was not done; the 74 usable rows
remain provisional. No blanket discard or full regeneration is warranted
by this sample alone.

Owner requested follow-up natural QA/chat grounded in this material. Prepare
English and Danish versions, using graph facts plus suitable source passages
when an explanation requires information absent from the graph. Useful forms:

- Ordinary entity questions, explanations and comparisons with explicit scope.
- Multi-turn follow-ups that resolve references and build on previous answers.
- Evidence-grounded multi-hop questions with verifiable paths.
- Distractor-based MCQs with randomized answer positions, concise explanations,
  and one uniquely supported correct answer.
- Questions where the supplied evidence is insufficient; teach an appropriately
  qualified response instead of fabricated mechanisms or exhaustive claims.

Do not promote graph association to causation, similarity to equivalence,
absence of an edge to evidence of falsity, or one listed target to the only
target. One sampled training row asks which gene is linked to Parkinson's
disease and answers "The gene ... is SOD1" from a single association edge.
This exemplifies an unsupported uniqueness implication, not evidence that the
underlying graph edge itself is wrong. Repair wording before treating it as
natural explanatory supervision. Avoid personalized clinical recommendations.

Use shared `audit_pipeline`: non-thinking, short plain accept/reject reviews,
at most one retry, no lengthy JSON evidence or request spacing. Keep grounding
and lineage, and group related facts/paraphrases when making held-out checks.
Generation size/model and inclusion weights are not yet fixed; no GPU work is
authorized or started merely by this plan.

## Independent SimpleStories judge calibration (2026-10-28)

See the [preserved judge-comparison history](dfm16-story-calibration-history.md)
for the completed prose and multiview studies, their labels and limitations.
The [context-aware follow-up](dfm16-story-calibration.md) uses these 200 parents
as development data; prior results do not certify the new acceptance gate.

## Expected effect and assessment

Hypothesis, not measured result: direct training may help biomedical recall
and relevant MMLU/MMLU-Pro subjects because QA and MCQ are already represented.
It is not a broad MMLU solution: graph-relation memorization need not transfer
to novel questions, reasoning, or natural conversation. Natural QA/chat is a
complement, not a prerequisite for every possible benchmark gain.

Compare relevant subject breakdowns as well as overall MMLU/MMLU-Pro, and
test unseen phrasings and multi-turn questions separately. Do not generate
training examples from evaluation questions. Decide the value of the direct
source and added natural variants empirically; do not promise score gains.

## Evidence inspected

- [Dataset card](https://huggingface.co/datasets/schneiderkamplab/synth-kg-text-hetionet/blob/24eed50a87b43c5bb384b3bd0204692d43506a44/README.md).
- [Build report](https://huggingface.co/datasets/schneiderkamplab/synth-kg-text-hetionet/blob/24eed50a87b43c5bb384b3bd0204692d43506a44/metadata/reports/summary.md).
- Hub train preview: inspected schema and first two rows, not a full quality audit.
  Card loading example names `giannor/...`; use the owner-specified
  `schneiderkamplab/...` repository and pinned revision above.


### Staged generation follow-up: practical audit configurations, 2026-10-29

The user relaxed development screening to 10/20 and made low false acceptance primary.
The [completed staged comparison](dfm16-staged-stories.md#completed-exploratory-audit-comparisons-2026-10-29)
retains all historical failures and reports the four languages independently. English
and Japanese have zero observed false accepts in the combined development/control cohort;
Danish and Hindi retain generated-example defects. Adaptive refinements and small/correlated
samples prevent qualification claims. Requested generation/auditing capacity is now 4/4;
existing inference servers were not reassigned. No production or untouched-validation
admission has occurred.
