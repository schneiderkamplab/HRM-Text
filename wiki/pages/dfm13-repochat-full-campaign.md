---
type: Runbook
title: DFM13 RepoChat Full Campaign
description: Whole-source native repository trajectories and bounded technical follow-up.
status: draft
last_updated: 2026-10-01
confidence: high
tags: [dfm13, repochat, calibration]
---
# DFM13 RepoChat Full Campaign

## Current Policy: Research Only

Explicit user policy on 2026-10-01: **Do not integrate RepoChat or either search
dataset into DFM13.** Preserve all research artifacts, results, provenance and
failure receipts, but do not register these as DFM13 sources, tokenize them for
DFM13, sample them into training, or admit their candidates into DFM13. This
exclusion supersedes any earlier prospective integration or admission plans;
automatic reviewer passes do not override it. Historical generation/review
authorizations below describe research activity only, not training eligibility.

No new GPU work is implied. Do not interfere with the parent-owned training
resume. This documentation update performs no pipeline or process changes.

## Authorization and Scope

On 2026-10-01 the user authorized generation and independent model review
over the full source, superseding the QA-only scaling restriction in
[reviewer calibration](dfm13-repochat-reviewer-calibration.md). This is not
training admission. Existing exact-answer holds remain applicable.

The parent launched `scripts.dfm13_repochat_full_campaign` as PID 2957939,
root `data/dfm13/repochat-full-20261001`, log
`logs/arena_review/20261001/repochat-full.log`. The source has 3844 rows,
mapped to 3321 unique tasks including ties and complex requests. Pinned public
repositories are accessed through read-only native tools; no repository code
is executed. Unavailable sources are explicit skips. All eight shared
endpoints 8800-8807 are used, limited to 64 requests per endpoint. Shared
servers and other campaigns are not modified.

## Automatic Bounded Follow-up

`scripts/dfm13_repochat_full_retry.py` waits for the parent's completion
receipt, checks its progress hash and implementation/source pins, obtains
the released parent controller lock, and selects only terminal technical
empty-stop generation or transport failures. Reviewed rows, including
quality rejects, cannot enter this retry. Length, context, schema and tool
budget failures are excluded. There is one follow-up attempt, not a loop.

The separate ledger is
`data/dfm13/repochat-full-20261001-technical-retry-v1`. Detached watcher PID
2964447, start ticks 227098085, was armed while the original pass remained
active. `launcher.json`, `watcher-status.json`, `watcher.log`, and subsequent
`selection.json` record its identity, state, selection and parent hashes.
It reuses successful generation response receipts and reconstructs actual
tool history, discarding only empty final response receipts. The normal
generation-to-audit pipeline runs at 64/server. Originals remain unchanged;
restart preserves terminal retry outcomes. There is no automatic admission.

Focused tests: `tests/test_dfm13_repochat_full_retry.py`, 11 passed, covering
selection exclusions, history reuse, original preservation and idempotence.

At the operational check, the main ledger had 1075 reviewed and 512 running;
a nearby read-only failure tally found 271 empty-stop generation failures,
106 audit length failures and three generation length failures. Counts are
live snapshots, not final totals. Empty-stop means no final content/tool
calls despite finish_reason=stop, not a transport outage or quality verdict.
Consult the ledger and progress receipts for current counts.

## Completed Passes and CPU Diagnosis

The live counts above are superseded by the completed ledgers: original 2051
reviewed, 724 technical failures, 546 source skips; follow-up 30 reviewed and
398 technical failures. Combined unique totals are 2081 reviewed, 694 unresolved
technical failures and 546 source skips. Automated passes are not admission.

The dominant failure is native tool finalization: 373 of 428 original empty-stop
responses occur at forced `tool_choice=none` turn 16, all stopping on token 50
(`<|tool_response>`). All 288 original audit-length failures consume their 8192
completion-token budget; 280 produce reasoning without final content. Identical
retry requests did not repair the boundary. Full raw token streams were not
saved, so the precise parser defect remains unproven. Source skips include 175
rate-limit responses and must not all be described as permanently unavailable.

See `docs/reports/dfm13_repochat_full_failure_diagnosis_20261001.md` for exact
original/retry buckets, repetition and tool-error counts, concrete examples,
source breakdown and proposed fixes. This investigation was CPU-only. The user
requested XL training resumption; parent owns shared-server teardown and training.
No further RepoChat GPU retry was launched or scheduled after this diagnosis.

## Authorized Scoped Recovery Preparation

Later on 2026-10-01 the user authorized the proposed scoped recovery, not a full
rerun. This supersedes the preceding no-further-retry plan, but does not authorize
automatic training admission or changing shared servers. The parent is providing
one TP8 Gemma instance in training headroom, endpoint
`http://127.0.0.1:8810/v1`, alias `dfm13-gemma4`. Its initial launch hit the memory
guard and was stopped; a lower-budget launch is pending. No recovery inference
was started during this CPU preparation. Training retains priority.

New implementations, leaving frozen campaign modules untouched:

- `scripts/dfm13_repochat_recovery.py`: source-hash/evidence replay, tool-free
  answer finalization, two-request bounded review, exact student target rendering,
  fail-closed KV admission, signal drain and resumable atomic receipts.
- `scripts/dfm13_repochat_source_recovery.py`: public-only CPU source preparation,
  two workers, deduplicated source contexts, up to three bounded HTTP attempts,
  explicit API-only environment credentials, no redirect/credential helpers or
  code execution, unchanged safe extraction and size limits.

Prepared root: `data/dfm13/repochat-recovery-20261001-v3`. The earlier v2 root is
a CPU-only draft superseded by v3; it was never used for inference. `plan.json`
pins implementations, tokenizer/template, source receipts and control authorities.
It selects 395 remaining empty finals, 288 original audit failures, three audit
failures from the first retry, and 546 source-skip tasks. No reviewed row is
selected. Eight degenerate/long generations remain held rather than blindly
regenerated. Source inventory deduplicates to 390 contexts; downloading has not
started. Safety/size and ambiguous explicit-ref holds are not silently relaxed.

The 24 reviewer controls comprise 18 prior independent manual decisions and six
paired source-grounded fixtures: 14 positive, ten negative. These are diagnostic
controls, not unbiased heldouts. Review uses a 2048-token analysis call followed
by a separate 3072-token typed verdict with thinking disabled. Truncated analysis
is labeled fallible notes, never accepted as a verdict. All controls must match
their expected labels before bulk audit recovery. The finalization pilot selects
24 frozen histories; bulk finalization also requires a completed passing pilot.

All 24 pilot source histories replayed exactly on CPU. Existing native target
histories: 14 fit, eight already exceed 4096 tokens, and two contain invalid
historical tool argument counts. Final answers have not yet been generated, so
14 is an upper bound, not a final trainable count. Every new final target is
re-rendered; oversize/invalid traces remain ineligible without truncation.
`pilot-cpu-preflight.json` and `pilot-student-history-preflight.json` are authorities.

The parent allocated RepoChat at most three concurrent requests and Search one,
given about 150114 reported KV tokens. The recovery CLI defaults to three and
also requires KV usage at most 70% with zero waiting requests. Missing metrics
or a bounded headroom timeout stop submissions and preserve resumable deferred
work, rather than flooding the endpoint. No 512-request launch is used.

After the parent confirms the replacement server ready, commands are:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_repochat_recovery --phase controls --endpoint http://127.0.0.1:8810/v1 --model dfm13-gemma4 --concurrency 3
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_repochat_recovery --phase pilot --endpoint http://127.0.0.1:8810/v1 --model dfm13-gemma4 --concurrency 3
```

The same CLI offers `--phase audit` (288 plus separately labeled three) and
`--phase finalize`, guarded by the control/pilot receipts. CPU source inventory
is prepared with `python -m scripts.dfm13_repochat_source_recovery`; explicit
`--execute` enables bounded CPU downloads only, never generation or inference.
Tests: 37 passed across recovery, source recovery and first-follow-up selection.

### Replacement Server Ready and Calibration Launched

The parent subsequently verified TP8 v3 ready on 8810 with the memory guard not
triggered. API preflight confirmed `dfm13-gemma4`, 32768 context, zero waiting
requests and initially zero KV use. Detached supervisor PID 2997345 (start ticks
227475320) launched controls child PID 2997410. The supervisor runs controls then
the 24-case pilot, sequentially, and cannot start bulk recovery. Its receipts and
log are `calibration-launcher.json`, `calibration-supervisor-status.json`, and
`calibration-supervisor.log` under the v3 recovery root.

Actual request activity was verified: three saved analysis requests, three
server-running requests, zero waiting, KV utilization 0.5116. No control results
had completed at this first check; neither controls nor pilot are claimed passed.
`capacity-coordination.json` records the parent-authorized RepoChat three / Search
one allocation (four combined). Direct agent messaging was unavailable; the
allocation and receipt were reported to the parent for coordination with Jason.

The user then required assessment of all 24 controls before proceeding. The
automatic controls-to-pilot handoff above is superseded: only supervisor PID
2997345 was terminated by exact verified PID, not its process group. Controls
worker 2997410 (start ticks 227475343) remained alive, reparented to PID 1, and
uninterrupted. `pilot-handoff-cancelled.json` records the action. At that check
zero control verdicts were complete. Pilot and bulk remain stopped pending the
complete control assessment, including false accepts, false rejects, operational
failures, and qualitative comparison with the independent control authorities.

### Final Control Assessment: Hold

All 24 controls are terminal: 22 complete verdicts and two operational failures.
The confusion counts are 13 correct accepts, three correct rejects, six false
accepts, zero false rejects, plus one unresolved positive and one unresolved
negative. Agreement is 16/22 verdicts (16/24 including operational failures).
All six synthetic fixtures match, but every one of the six real-repository
negative controls with a verdict falsely passes. These are exposed diagnostics,
not a population quality estimate.

Separate budgets repaired review completion for the 22 returned analyses (eight
were capped at 2048 tokens); all produced complete typed verdicts. The two other
analysis requests failed at roughly 600 seconds, consistent with the client
timeout, but the saved error strings lack exception types. Semantic reliability
did not pass: Agnai exports, Neuro API bounds, MergePath losses, URLPages host
dependency, UltimateMember profile/login distinction and Voxtulate implementation
claims still falsely pass. The analysis itself excuses or misses these defects.

`control-assessment.json` pins every outcome and manual authority. Detailed report:
`docs/reports/dfm13_repochat_recovery_controls24_assessment_20261001.md`.
The controls worker exited after about 51 minutes; neither supervisor nor controls
worker remains active. Pilot outcomes remain zero. **Pilot and bulk are held**;
the answer-only finalization implementation has not yet been demonstrated by the
pilot. No new recovery retry, admission, server change or training action followed
the assessment.

Further CPU source rechecking qualifies the six expected-label disagreements:
four are confirmed false accepts (Agnai, Neuro, MergePath, Voxtulate); URLPages is
a debatable hard-negative for a broad overview, and UltimateMember's 'current
user' query needs selected-profile versus logged-in scope clarified. Original
control labels and verdicts remain unchanged; see
`control-disagreement-recheck.json` and the report's control-validity addendum.
These two control limitations do not excuse the four clear failures or clear the
pilot/bulk gate. Both technical failures occurred in analysis at 600.3/601.0
seconds, consistent with request timeout, not recorded parsing/context failures.

## Focused Claim-Verification Controls

The user next authorized a focused reviewer revision and actual controls launch,
not bulk recovery. New module `scripts/dfm13_repochat_claim_controls.py` leaves
all old modules, labels and outcomes unchanged. It checks material assertions
against supplied declarations, export relationships, behavioral qualifiers and
objective mathematics; a separate verifier checks the proposed findings against
the original source. Neither prompt contains repository names, IDs or fixture
answers. Minor omissions and ambiguous questions are distinguished from material
false or unsupported implementation claims. A checker/verifier contradiction is
held and recorded, not silently resolved as a pass.

The new root is `data/dfm13/repochat-claim-controls-20261001-v1`. Its pinned plan
contains 32 records: the preserved 24, four paired positives for confirmed
failures, and positive/negative explicit-query variants for URLPages and
UltimateMember. The original two weak negatives remain informational rather than
gate-required (30 required). One paired positive deliberately reuses the earlier
manually reviewed Voxtulate repair and richer source packet; it is not an
independent new sample. All these controls are exposed diagnostics.

The client holds a concurrency slot for an entire case, preventing the earlier
analysis queue from delaying every verdict. It uses at most three concurrent
cases alongside Search's allocated one, KV admission at 70% with no waiting
requests, 1200-second per-request deadlines and one timeout-only retry. Exception
type, stage and elapsed time are recorded. Both claim-check and verdict outputs
are bounded typed JSON; incomplete responses fail closed. There is no automatic
pilot or bulk handoff, even when labels agree. Independent assessment remains
required.

Tests: 21 passed across the new controls and recovery tests, including preserved
original packets/labels, repaired pairs, prompt non-specialization, timeout-only
retry bounds, and incomplete-output rejection. API preflight on shared 8810
confirmed `dfm13-gemma4`, one existing request and low KV. Detached client PID
3030298 (start ticks 227955337) then launched three actual claim-check requests.
The first check showed 0/32 completed, three active RepoChat cases, four total
server requests, zero waiting and KV utilization 0.2858. No success is claimed
before results. `launcher.json`, `progress.json`, `runner.log`, per-control
receipts and eventual `completion.json` are the operational authorities.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.dfm13_repochat_claim_controls --run --root data/dfm13/repochat-claim-controls-20261001-v1 --endpoint http://127.0.0.1:8810/v1 --model dfm13-gemma4 --concurrency 3
```

### Bounded Contract Revision

Inspection during the claim-control run found spurious expected-label agreement:
Agnai and MergePath were labeled rejected solely because findings contained
'None' while rationale praised the answer. Their paired correct answers received
the same placeholder findings. These four cases are contract contradictions, not
successful source verification or established semantic rejections. Voxtulate did
produce a real unsupported-implementation finding and its corrected pair passed.
One Neuro claim-check response reached its 3072-token limit.

Under the user's continuous bounded-fix authorization, only client 3030298 was
gracefully drained by exact verified PID. It exited with eight terminal outcomes
(seven mechanically reviewed, one claim-length failure) plus preserved deferred
requests; it did not complete all 32. Servers and training were untouched.
`drain-for-contract-revision.json` preserves the action. Its reported five label
matches must not be treated as five reliable semantic decisions.

New isolated wrapper `scripts/dfm13_repochat_claim_controls_v2.py` preserves old
source files and adds atomic-proposition checks, concise evidence comparison and
an explicit empty-findings contract. Placeholder findings are classified as
invalid rather than promoted to accept or counted as meaningful rejects. The
experiment is bounded to the four original defect/repair pairs (eight cases);
the full 32-case catalog remains saved. It cannot automatically start another
stage. Fifteen focused tests passed, including placeholder detection, preservation
of genuine findings beginning 'None of', prompt non-specialization and selection.

After confirming the old client exited and shared API/KV admission remained
healthy, PID 3036107 launched on 8810 at three whole cases. Root:
`data/dfm13/repochat-claim-controls-20261001-v2`. `launcher.json`, `progress.json`,
`runner.log` and `completion.json` record progress. At launch no revised case had
completed; pilot, production and admission remain gated on substantive assessment,
not the accidental agreement seen in v1.

The eight-case v2 run completed with seven structured verdicts and one verdict
length failure (corrected Neuro answer); six mechanically matched expected
labels. Independent inspection did not verify reliable discrimination. The atomic
checker identified the Agnai export and Voxtulate evidence gaps, but the second
stage sometimes judged the proposed checks rather than the answer. MergePath's
rejection relied on weaker unsupported descriptive labels rather than its known
objective error; Neuro's original timing/data claims still passed. Such matches
cannot release the gate. PID 3036107 exited; all outputs are preserved.

A bounded framing fix is isolated in
`scripts/dfm13_repochat_answer_verdict_probe.py`: only the original request,
answer and source are sent to the verifier, not the proposed checks. It explicitly
seeks qualifying/counterevidence and judges defects in the answer. All eight claim
receipts are reused with exact request-hash verification; no generation, source
retrieval or claim-check inference is repeated. Eleven focused tests passed.
After verifying the prior client exited and KV admission was healthy, detached
PID 3043612 (start ticks 228156314) launched eight verdict-only cases at concurrency
three, root `data/dfm13/repochat-answer-verdict-probe-20261001-v1`. No next-stage
handoff is automatic; pilot, bulk and admission remain blocked pending inspection
of actual findings, not just derived label agreement.

### Qualifier Regression (2026-10-01)

The verdict-only probe completed eight valid reviews without technical failures.
All four corrected positives passed, but the independent verifier also accepted
all four known negatives. Three negatives were held only by checker conflicts;
Neuro passed both stages. Nominal combined agreement of seven/eight is therefore
not evidence of reliable verification. PID 3043612 exited; no pilot launched.

The original six disagreements are not equally critical: Agnai's export relation,
Neuro's timing/data guarantees, MergePath's stated objective, and Voxtulate's
unsupported specific mechanism are material. URLPages is a weaker qualification
omission in a broad overview; UltimateMember's original query is ambiguous.
Original labels remain preserved, with explicit disambiguated controls separate.

`scripts/dfm13_repochat_qualifier_controls.py` adds a generic counterexample test:
documented delay, priority or validation exceptions contradict unconditional
immediate/always/guaranteed claims. It does not encode repository names or answers
in the rubric. Four targeted cases preserve the original Neuro negative and
corrected positive, plus explicit negative/positive timing variants. The same
reviewer then runs all 32 preserved regression controls, including positives and
the disambiguated controls. Fourteen focused CPU tests passed before launch.

Run root: `data/dfm13/repochat-qualifier-controls-20261001-v1`, with exact process
identity in `launcher.json`, logs in `runner.log`, and separate `targeted` and
`regression` progress/completion receipts. Maximum concurrency remains three
whole cases on shared 8810; no servers or training changed. Regression follows
targeted completion for diagnostic coverage, not approval. No automatic pilot,
production or admission handoff exists; actual findings require assessment.

### Explicit Candidate Recovery Authorization (2026-10-01)

Superseding the calibration launch gate for candidate production only, the user
explicitly ordered bulk scoped recovery despite imperfect controls. Admission
remains false regardless of automatic reviewer verdict. New isolated runner
`scripts/dfm13_repochat_candidate_recovery.py` selects 686 pinned failed-stage
jobs: 395 answer-only finalizations and 291 audit-only recoveries. Original
successes, source/input hashes and independent answer-hash holds are preserved.
It replays real tool evidence, uses the generic qualifier/guarantee checks in
independent claim and answer reviews, preserves native structures, and checks
student context without truncation. Technical failures stay failed, not admitted.

Five focused CPU tests passed. The calibration client received verified-own-PID
SIGTERM to drain; with two requests still active, recovery launched at one case
on 8810 so combined RepoChat concurrency remains at most three and the existing
Mimir reservation stays free. No server or training changes occurred. Root:
`data/dfm13/repochat-candidate-recovery-20261001-v1`; `launcher.json` identifies the
detached process, `runner.log` records outcomes, and `progress.json` records
actual stages/counts. This is not evidence that reviewer quality is solved.

At approximately 40 minutes, six/686 recoveries had completed and a seventh
was reviewing. Calibration had exited. Direct two-point server measurement over
10 seconds showed 106 decoded tokens (10.6 tokens/s aggregate), two running
requests, zero queued requests/preemptions, and KV occupancy 15.9-16.0 percent.
Completed finalizations took 63-445 seconds, claim checks 68-224 seconds, and
verdicts 9-37 seconds. Thus slow decoding plus the deliberately serial client,
not a controller deadlock or saturated KV, explains the poor observed rate.

`scripts/dfm13_repochat_restore_capacity.py` performs an exact-PID/start-tick
verified graceful drain, then rechecks pins and KV before restarting the same
ledger at its previously allocated three cases. Transition supervisor PID
3075004 writes `capacity-transition.json` and `capacity-transition.log`; no
second client starts until the old one exits, and timeout fails closed. Saved
stage receipts are reused. Neither Mimir nor training/server processes are
signaled. The earlier one-worker linear estimate is about 75 hours; ideal
three-worker scaling would be about 25 hours, but shared decode contention and
the small initial sample prevent treating that as a reliable completion ETA.

### Paused for Parent-Owned Full-GPU Handoff

Superseded by explicit user instruction: the restart supervisor 3075004 was
terminated and candidate client 3058623 gracefully drained; both exits verified.
Six completed reviews and all partial stage receipts remain. Exact identities
and final empty-active progress are in `user-pause-receipt.json`. No server or
training actions were performed by this worker.

Prepared, not launched: `scripts.dfm13_repochat_replica_recovery.py`, with eight
explicit localhost endpoints, `--per-endpoint 256`, and required
`--parent-gpus-cleared`. It resumes the same locked ledger, bounds each endpoint
to 256 requests and total case workers to the 686-job inventory, preserving
the KV admission threshold of 0.70. Server GPU utilization 0.95 is a separate
parent/Jason-owned launch setting, not a reason to bypass KV admission. Four
focused tests passed; saved successful outcomes and response receipts are reused.

Completion contract for Jason: root `gpu-work-terminal.json`, schema
`repochat-gpu-terminal-v1`, includes exact PID/start ticks, plan hash, expected
686, terminal counts, missing IDs, status (`complete` or `incomplete_or_error`),
exception and closed-session marker. The bounded campaign includes finalization
and independent review, with one timeout-only retry per request; answer-only
finalization is its repair step. No unbounded semantic repair/calibration follows.
Admission stays false. After receipt AND verified exact client exit, orchestrator
tears down only its owned vLLM and resumes training on success or operational
failure; a forced kill without receipt must be treated as failure, not completion.
CPU exports follow training restart. No wrapper launch is authorized until parent
confirms GPUs cleared and provides the eight replica endpoints.

Parent readiness subsequently confirmed eight replicas on 8800-8807. Detached
handoff supervisor 3081159 launched client 3081227 with `--per-endpoint 256`;
`replica-launcher.json` pins readiness and exact client identity. Six completed
rows were reused; 680 remaining cases entered evidence/finalization preparation.
`scripts/dfm13_repochat_replica_handoff.py` waits for actual child exit and writes
Jason's requested `logs/dfm13/repo-bulk-interlude-2981000/bulk-gpu-terminal.json`
with status complete/failed, all_gpu_stages_terminal and gpu_clients_stopped.
These flags are never emitted merely because generation finished. Four focused
tests passed before launch. Actual GPU inference progress is recorded separately
from CPU evidence preparation; a worker marked active is not proof of inference.

### Terminal Recovery Diagnosis

All 686 jobs reached terminal outcomes: 512 reviewed, 174 technical failures.
Client exited zero and handoff receipt was emitted after exit. No further GPU
retry is authorized by this worker; parent/Jason can resume training promptly.
Of reviewed candidates, 370 automatically pass and 142 reject; only 106 automatic
passes fit the student context contract. None are admitted.

CPU classification in `terminal-failure-classification.json` under the recovery
root finds zero transport failures and zero teacher-context-overflow failures.
The 168 evidence failures comprise mutually exclusive 76 no-tool-result histories,
56 listings-only histories, 13 listings plus empty searches, and 23 histories
with tool errors but no successful content evidence. These are deterministic
under the saved histories, not retryable server outages: 74 were finalization
jobs and 94 audit-only jobs. Recovery would require new targeted evidence
retrieval, not replaying the same review or relaxing the evidence requirement.

The other six failures all hit the claim-check output limit of 3072 tokens;
prompt lengths were 3466-9401, so these were not 32768-context exhaustion.
Four responses ended mid-content and two showed degenerate trailing whitespace.
They are generation/contract failures, not network failures. Future authorized
repair can constrain concise claim output or diagnose whitespace degeneration
while retaining the saved answers; blindly increasing context is not indicated.

Low-utilization implementation limitation: the shared aiohttp
`TCPConnector(force_close=True)` retained default global connection limit 100.
Thus eight per-endpoint caps of 256 did not permit 2048 actual simultaneous HTTP
requests. Future implementations need explicit bounded global/per-host limits
and separate CPU evidence/write capacity, with admission metrics retained.
Two-second KV polling and 0.70 admission remain conservative controls, not proof
of a bottleneck when measured occupancy was low. No frozen runner was edited and
no new GPU work launched during this diagnosis.
