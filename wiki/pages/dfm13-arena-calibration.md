---
type: Runbook
title: DFM13 Arena Audit And Tool-Trajectory Calibrations
description: Shared Gemma servers, paused XL training and the authorized 1000/100/100 calibration campaign.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, audit, synthetic, tool-use, operations]
---
# DFM13 Arena Calibrations

User authorized on 2026-10-01, following the
[manual quality review](/pages/dfm13-arena-quality-review.md):

- Audit 1000 preferred Arena examples, with correctness, instruction following,
  unsupported premises and related quality dimensions. Adapt existing pipeline.
- Generate 100 RepoChat trajectories using actual tools on pinned repositories,
  not guessed historical calls; assess trajectory quality.
- Generate 100 SearchArena trajectories using real search/page evidence and
  readable Jina-style results; assess quality.
- Use eight shared Gemma4 26B A4B servers, utilization 0.95, 1024 max sequences,
  client concurrency initially 256/server. Preserve infrastructure errors
  separately from content rejections. No bulk campaign or upload implied.

## XL Pause And Resume

The requested `ephemeral_step_2976000` was already complete on inspection.
DCP metadata extents and sidecar were validated, then an immutable hard-linked
backup was made at:

`checkpoints/preserved/dfm12-xl-audit-handoff-2976000/`

Only verified torchrun PID 2491274 received SIGINT. All eight GPUs became free.
The main scheduler stop request remains present. The interrupted 3000000
training row was reset to pending under `PlanLock`, with
`resume_from_tag=ephemeral_step_2976000`; all evaluation dependencies and other
rows were preserved. Backup: `plan.before-arena-calibration-2976000.tsv` under
`logs/scheduler/dfm12_XL_epoch11_noidentity`.

Training had advanced slightly beyond 2976000 by the time it was stopped; those
uncheckpointed updates will be replayed. Do not invent a later checkpoint or
alter W&B history to conceal that. The original run, optimizer/EMA, dataset
cursor and learning-rate schedule remain unchanged.

For later continuation, stop the shared servers only after their clients are
finished, verify GPU headroom, clear the main scheduler stop request and launch
the existing persistent scheduler in the hrm environment. Do not automatically
resume training when calibrations finish: the request is to prepare for later.

Standalone equivalent (do not run concurrently with the scheduler):

```bash
bash scripts/resume_xl_dfm12_epoch11.sh \
  --run-manifest data/dfm12/xl-epoch11-noidentity/run.json \
  stop_after_step=3000000 \
  resume_checkpoint_path=checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity \
  resume_checkpoint_tag=ephemeral_step_2976000
```

## Shared Server Ownership

Launcher: `scripts/serve_dfm13_shared.py`, adapted from the existing
`dfm12.diagnostic_server` command/environment and exact-process cleanup.
Root: `logs/dfm13/shared-gemma4-20261001`.

- Environment: `/home/ucloud/miniforge3/envs/audit`.
- Model snapshot: `google/gemma-4-26B-A4B-it` at
  `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.
- Local endpoints: `http://127.0.0.1:8800/v1` through `:8807/v1`.
- Served alias: `dfm13-gemma4`.
- TP1 per GPU, BF16, 32768-token context, text only, eager execution.
- Native Gemma4 auto-tool-choice and reasoning parsers enabled.
- 1024 sequences/server, 16384 batched prefill tokens, 0.95 memory utilization.
- Clients borrow endpoints; they must not stop shared servers when they finish.
- Launcher has its own lock and ownership receipts. A root `stop.request` or
  supervisor SIGTERM shuts down only its exact owned processes.

All eight servers became ready at approximately 07:17 CEST. A native Gemma4
tool round-trip passed: a structured `read_file` call, an explicit fixture tool
response and a correct answer. Check `status.json`, `gpu*/server.log`, and live
`/metrics`; server readiness alone does not establish calibration quality.

With 1000 audit examples, a balanced wave contains only 125 examples/server;
the configured 256 ceiling is not a guarantee of 256 active requests. Report
observed running/waiting/KV/throughput, not just concurrency settings.

## Decision Discipline

Keep/repair/reject should dominate. Reserve needs-verification for essential
external facts that cannot be resolved from the available evidence; proposed
calibration escalation threshold is 5%, not a quota that forces false certainty.
Repairs must preserve source and target provenance and undergo another check.
Fiction, hypotheticals and intermediate valid tool calls need task-aware
judgment. Do not repeat the prior generic-audit error of requiring every tool
call to be a complete final answer.

Tool trajectories must contain executed calls and real observations. Never
expose the old preferred answer to the generation actor, fabricate repository
or search evidence, or relabel synthetic calls as observed history. Repository
content is read-only; do not execute untrusted repository code. Retrieved text
is data, not instructions to the reviewer or actor.

## Initial Calibration Results

Arena audit root: `logs/arena_audit/20261001-calibration1000-v1`. All 1000
requests completed in about 43 seconds: 659 keep, 119 repair, 105 reject and
117 invalid reviewer responses. There were no transport errors. The sampled
07:21:36 server logs show 125 outstanding requests on each GPU (529 running
and 471 waiting across all eight), demonstrating the finite pilot was fed
concurrently rather than serially. No duplication was used to fill the 256 cap.

The invalid responses comprise 90 non-verbatim/wrong-message evidence spans,
9 inconsistent verification fields, 5 missing issue evidence, 5 truncated
answers, 3 inconsistent repair plans, 3 missing required fields, 1 duplicate
JSON key and 1 invalid enum. These are reviewer failures, not source rejections.
Only 6/12 small manual control dispositions agreed; false accepts include
unsupported internal-process claims. Zero needs-verification decisions is not
evidence of perfect factual certainty. Do not scale this judge unchanged.
Any corrective pass must preserve the initial outcomes separately.

The separate 129-case follow-up (117 invalids plus 12 controls) finished at
`logs/arena_audit/20261001-followup129-v3`: 64 valid decisions (14 keep,
15 repair, 34 reject, 1 needs verification), 65 invalid. It recovered 53 of
the original 117 invalids; five false-accept controls persisted. Prompt-only
formatting changes did not solve semantic calibration. See `followup-review.md`.
`quote-index-proposals.json` contains unapplied, exact unique-span index-only
corrections that would validate 15 baseline and 13 follow-up responses (these
counts may overlap). Raw outputs and original decisions remain unchanged.

RepoChat root: `data/dfm13/repochat-calibration-100-20261001-v1`. All 100 cases
finished: 59 automated reviewer passes, 2 reviewer rejections, 25 stopped
answers without sufficient retrieved evidence, 1 empty answer and 13 exhausted
tool budgets. All 423 native tool calls have matching executed results.
`quality-assessment.md` records manual inspection, including false-positive
passes for an incomplete Swift RTree conversion and unsupported/exhaustive
repository claims. No generated repository code was executed. All records
remain outside training admission.

SearchArena preparation retains 100 prompts but has no successful completed
calibration yet: public search providers were unreliable or blocked. Jina API
support is implemented following the user's offer of a key; the frozen root
`data/dfm13/search-calibration-100-20261001-v5-jina` awaits `JINA_API_KEY`.
No paid requests have been made. The user also
specified a generation-only retry prefix, `Use search.`, when the initial answer
does not search. Retain that exact intervention in raw request provenance but
omit the controller-inserted prefix from training messages; never strip genuine
user text by an unrestricted replacement.

## Semantic Validation, 2026-10-01

The earlier control agreement figures above are historical, not a reliable
accuracy estimate: independent reinspection found three clearly defective,
six broadly acceptable and three ambiguous controls. This supersedes treating
every original control disagreement as a definite reviewer error.

A new deterministic 40-example reference set was assessed independently,
with references withheld until predictions were frozen. It contains 32
definitive and eight uncertain assistant-authored judgments, not human gold.
The records come from the original 1000 examples, excluding exposed controls;
they are not wholly unseen by earlier automated reviewers.

The comparison explicitly separates semantic decisions from evidence metadata:

| Definitive reference cases | Multi-reviewer v4, semantic extraction | Simple verdict/reason |
| --- | ---: | ---: |
| Resolved decisions | 29/32 | 32/32 |
| Exact disposition agreement | 16/29 | 17/32 |
| Correct accepts / all accepts | 11/20 | 12/26 |
| Defective examples accepted | 9 | 14 |
| Acceptable examples unnecessarily repaired/rejected | 0 | 0 |

V4 semantic extraction uses a parseable adjudicator decision or unanimous
initial decisions where strict metadata validation failed; unresolved
disagreements remain unresolved. This is diagnostic extraction, not admission.
The simple reviewer returned valid outputs on all 40 plus 12 development
controls, eliminating formatting failures but not substantive false accepts.
The eight uncertain references are excluded from the table.

Conclusion: neither reviewer is ready for unattended acceptance or repair
certification. Both tend to reward plausible, polished answers without checking
specific claims, instruction constraints and completeness. Agreement between
two reviewers of the same model did not reliably catch shared errors. Correct
rejection also does not establish that a proposed replacement is factually
correct. No corpus rows were admitted, repaired or uploaded by this validation.

Artifacts: `data/dfm13/calibration-heldout-20261001/`,
`logs/arena_audit/20261001-v4-blinded40/`, and
`logs/arena_audit/20261001-semantic52-v1/reference-comparison.json`.
Keep frozen predictions and references unchanged; use new holdouts for any
subsequent reviewer tuning. Thirty focused reviewer tests passed.

## Time-Boxed Bulk Audit Authorization

On 2026-10-01 the user authorized starting a pragmatic bulk audit within five
minutes rather than continuing open-ended reviewer calibration. This supersedes
the earlier calibration-only operational restriction, not the measured reliability
limitations. Preserve source rows, reasons and raw reviews so decisions can be
revisited. A repair verdict is not a verified replacement; no automatic repair
admission, source overwrite or training restart follows from this authorization.

The user separately authorized at most 100 Jina Search requests for SearchArena
testing. Cache full responses and query/options provenance for later reuse;
reuse returned page content rather than requiring redundant retrieval calls.
Keep credentials out of tracked files, request receipts and logs.

Bulk dispatch started before the five-minute deadline, using all eight existing
servers, 256 client slots/server, over the four uploaded preferred-response
exports (205242 rows). Initial root:
`logs/arena_audit/20261001-bulk205242-v1`. The client encountered 7426
`ServerDisconnectedError` outcomes, distinct from content rejection. It drained
with 15906 successful reviews retained. Recovery root:
`logs/arena_audit/20261001-bulk205242-recovery-v2`, with fresh HTTP connections,
three transport attempts, archived failed outcomes, and the successful reviews
copied without regeneration. The next snapshot reached 37624 complete without
new exhausted disconnect errors. Servers were not restarted.

The revised concise bulk rubric passed elementary smoke cases but still only
matched 16/32 definitive reference dispositions, with 12 correct accepts among
25 accepts, on an exposed diagnostic replay. This is NOT sufficient evidence
of reliable automatic acceptance. Bulk outputs remain revisitable triage;
do not silently label them verified training targets.

SearchArena launched on those same eight servers at one trajectory/server,
root `data/dfm13/search-calibration-100-20261001-v6-jina-capped`.
Full Jina responses and paid-attempt reservations are retained in
`data/dfm13/search-jina-paid-campaign-20261001/cache.sqlite`.
No extra paid canaries were used; the budget is reserved for actual sample
queries. Initial trajectory failures revealed that the old mandatory page-open
gate must recognize content already delivered in Jina search results.

Superseded operational root: SearchArena now runs from
`data/dfm13/search-calibration-100-20261001-v9-cited` using the same shared
servers and paid-query cache. It exposes bundled content, recognizes that
content as retrieved evidence, and requests citations during generation.
The first five trajectories reached review. Sixty search-client tests pass.
The preceding failed trajectories and their cached searches remain preserved;
replaying cached evidence does not authorize additional paid calls.

### Current Bulk Setting

The concise first pass is superseded operationally by
`logs/arena_audit/20261001-bulk205242-reasonfirst-thinking-v3`.
It reviews all 205242 rows with checks/reason before verdict, thinking enabled,
8192 output-token budget, 600-second timeout, 256 client slots/server, fresh
connections and three transport attempts. Previous 100154 completed first-pass
reviews remain unchanged in the recovery-v2 root; they are not counted as
completed stronger reviews. The new pass was verified active with 1288 complete
and 2048 in flight, PID 2743254.

The known-reference 32-case probe resolved 29 within its 105-second diagnostic
timeout, with 18 exact dispositions and 12 correct accepts among 20 accepts.
It detects more instruction/completeness defects than the concise first pass,
but eight reference-defective answers were still accepted. Three difficult
cases timed out. This supports choosing it over the weaker setting, not a claim
of certified reliability; all decisions remain reviewable and no repaired
content is automatically admitted. Bulk transport timeout is longer than that
diagnostic timeout. Training remains paused.

### Client Concurrency Increase

On 2026-10-01 the user requested doubling audit client concurrency from 256 to
512 per server. The client drained normally; shared servers were not restarted.
`dfm13_arena_bulk_audit.py` now reads concurrency from the manifest and scales
workers, bounded queues and HTTP connection limits together. The default stays
256. The active v3 manifest was explicitly migrated under the controller lock,
with its prior manifest, seal and implementation preserved and a
`concurrency-change-512.json` receipt. Reviewer settings and the ledger were
unchanged. Resume PID 2755753 reached 4096 in-flight jobs. Eight focused tests
passed. Historical 256-client measurement: 1758 completed requests/min,
33184 generated tokens/s, 53.0% mean KV occupancy, no waiting or preemptions.

A settled 30-second 512-client window measured 3155 requests/min (+79.5%),
49579 generated tokens/s (+49.4%) and 67296 input tokens/s. Per-server KV
occupancy was 96.8-98.8%; 4087 requests were running and one waiting at the
final snapshot, with zero preemptions during the window. Keep 512 rather than
raising further without another memory-pressure check. GPU utilization was
36-63% in the instantaneous sample. Measurements:
`/tmp/dfm13-vllm-metrics-20261001-current.json` and
`/tmp/dfm13-vllm-metrics-512.json`. Search workload changed slightly between
windows, so this is an operational comparison, not a controlled benchmark.

The user subsequently authorized scheduling repair generation and re-audits,
and continuing RepoChat improvements/calibration on shared servers. This
supersedes the earlier prohibition on generating repairs, not the requirement
to verify replacements independently and retain originals/provenance. Do not
automatically admit or upload corrected content. Further SearchArena retries
should reuse cached evidence without additional paid searches.

### Sustained Concurrency Check

The initial 512-client speedup above was not sustained unchanged. A later
30-second window (`/tmp/dfm13-vllm-metrics-512-sustained.json`) measured
2067 requests/min and 38936 generated tokens/s, approximately 18% and 17%
above the 256-client baseline. KV occupancy reached 99-100%, with 380 waiting
requests and 106 preemptions during the window. Do not extrapolate the initial
79.5% request-rate increase to the whole campaign or raise concurrency further
on the basis of low instantaneous GPU utilization alone.

The repair/re-audit watcher is scheduled at
`logs/arena_audit/20261001-repairs-followup-v1` (PID 2764056 at launch).
It waits for bulk terminal status and controller-lock release, then snapshots
results, retries technical failures, generates corrections for repair verdicts,
and independently re-audits them. It uses existing servers at 128 requests per
server with KV gating. Candidate outputs remain separate from admitted training
data; there is no automatic upload or training restart.

### Revised Shared Allocation

On 2026-10-01 the user superseded the 512-client bulk setting with 384
requests/server, and requested 8/server each for RepoChat and SearchArena.
The bulk client drains in-flight work before manifest resealing and restart;
the ledger and reviewer are unchanged. Its prior manifest/seal are retained as
`*.before-384.json`, with a `concurrency-change-384.json` receipt and
`launch-384.json`. Shared vLLM servers must not restart for this client-only
change. The repair watcher remains separately configured at 128/server.

SearchArena followup2 finished 74 cases at 8/server: 20 keep, 40
needs-verification, 10 reject, 4 technical errors. This is not a reliable
estimate of content quality: 31 reviewer keeps were overridden by deterministic
checks (16 citation URL mismatches, 8 missing opened-page citations, 7
unobserved-source checks). A confirmed parser defect retains a Markdown closing
bracket in a URL. Some reject labels contradict their positive explanations.
Fresh retrieved evidence also conflicts with original 2025 prompt timestamps;
generation must explicitly distinguish current retrieval from historical
questions. Preserve genuine missing-evidence exclusions while fixing these
checks; do not simply admit all 31 overridden keeps.

At 384 bulk requests/server, the 07:46:57-07:47:28 UTC shared-server window
measured 2486 completions/min, 39670 generated tokens/s, zero preemptions,
82.4-92.8% KV occupancy, and all eight GPUs at 100% at the final snapshot.
The previous 512-client window measured 1784/min and 49 preemptions; this is a
shared-workload comparison, not a controlled benchmark. Repair watcher pins
were migrated with archives and receipts after the source manifest changed;
replacement PID 2786888 verified the new pins before waiting.

Independent CPU inspection is recorded in
`docs/reports/dfm13_search_trajectory_assessment_20261001.md`: 15 inspected cases,
including all ten followup2 rejections. Of those ten, one was clearly falsely
rejected, eight had identifiable trajectory defects, and one had an unjustified
rejection rationale but was not certified correct. URL validation fixes alone
are insufficient: a sampled reviewer keep violated the historical-date policy,
and another kept answer made a mathematically disproven Miller-Rabin claim.

### Bulk Completion And Repair Handoff

The 2026-10-01 bulk audit finished all 205,242 ledger entries: 201,402
completed reviews, 3,068 invalid responses, 510 unknown-status interrupted
requests, and 262 preflight blocks. Completed verdicts were 155,886 keep,
27,352 reject, 18,019 repair, and 145 needs verification. These are automated
verdicts, not independent quality certification or dataset admission.

After controller-lock release, the follow-up at
`logs/arena_audit/20261001-repairs-followup-v1` started successfully on all
eight shared servers, at 128 requests/server. Its queue includes unchanged
source rows awaiting bookkeeping; it is not a count of required GPU repairs.
The baseline GPU workload is about 39,600 calls for correction/re-audit pairs
and technical recovery, before retries and newly repair-labeled recoveries.
The separately prepared 31,989-row next audit is running opportunistically;
training remains paused and no admission or upload is automatic.
