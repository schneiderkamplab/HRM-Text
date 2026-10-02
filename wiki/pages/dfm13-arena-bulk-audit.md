---
type: Report
title: DFM13 Preferred Arena Bulk Audit
description: User-authorized semantic triage with preserved provenance, transport recovery and explicit quality limitations.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, audit, data]
---
# DFM13 Preferred Arena Bulk Audit

## Dataset Export Handoff

**Final update, superseding the earlier manual-release gate:** main completed
174236 accepted candidates,28121 rejected,2885 needing review. User explicitly
authorized filtered export/upload/replacement and DFM13 integration without
manual per-row review. Main174227 plus next25480 yields199707 selected rows,
excluding all11 current holds, unresolved/rejected rows and Recovery100.
Main validated selections are in
`logs/arena_audit/20261001-repairs-followup-v1/terminal-filtered-readiness-v1`.
The separate `scripts/dfm13_arena_authorized_release.py` adapter preserves
terminal/hash/hold/lineage checks and accepts explicit user authorization,
without changing old receipts or claiming human-gold review.37 focused tests
passed with the existing guard tests. Release pins and six selections:
`docs/reports/dfm13_arena_user_authorized_release_20261001.json`.
Its `_validation.json` sidecar records completed full recheck. Future holds/pin
changes invalidate the release. Export/upload/integration are handed to
Poincare via parent, not launched or completed by this worker. Keep automated
audit labels and raw provenance; no all-verified quality claim.

User subsequently requested filtered export/upload, coordinated by parent with
Poincare. This is not an already queued upload or a release of independent holds.
Per-source totals, terminal status, hold counts, selection paths and timing limits
are in `docs/reports/dfm13_dataset_export_eta_20261001.md`.
Next filtered selections total25480:21629 original,483 recovered,3368 repaired
after excluding ComparIA seq49/89. The existing guard validates the unheld
selection hashes but still requires an explicit terminal quality-review receipt;
no review evidence is invented. Main sources0/1/2 are row-terminal while source3
is draining; existing main readiness is root-wide. No source-local bypass or
upload client was added. Recovery100 remains excluded from export and scaling.

## Tail Decision: No Main Restart

2026-10-01: user explicitly stopped the proposed main migration after queues
drained. Main PID2786888 remains at128/server. No signal, restart, migration
allowance, live code edit or new restart watcher was executed. Isolated staged
files `scripts/dfm13_arena_repairs_migrated.py`,
`scripts/dfm13_arena_migration_budget.py`, and
`scripts/dfm13_arena_safe_tail_migration.py` passed44 focused tests with existing
repair/readiness tests. They cover single-event-loop work stealing, preserved
attempt numbers, one explicitly archived interruption exemption, completed-stage
cache ordering and actual endpoint/raw-directory metadata. These are CPU-tested
future options, not deployed or production-performance-measured behavior.
Do not run the main-migration helper. Any future256/work-stealing integration
is restricted to a separately authorized frozen recovery client.

Recovery100 is not being scaled: its10-row assistant sample supported4 keeps,
identified4 repair disagreements and left2 verification questions unresolved.
Neither4/10 nor99/100 structurally valid outputs is a calibrated population
accuracy estimate. No automated admission/export follows this diagnostic.

A read-only, bounded two-hour main terminal observer writes
`logs/arena_audit/20261001-repairs-followup-v1/terminal-finalization-observer-v1/terminal-summary.json`
only after the completion receipt, disjoint total counts, absence of inflight
attempts and released controller lock agree. It records source/class counts,
attempt statuses and sidecar hold matches, but does not replace full provenance
readiness validation or authorize export. It issues no model calls or signals.

## Authorized Recovery Diagnostic And Next Terminal Snapshot

2026-10-01: user subsequently authorized100 recovery-candidate calls despite
the failed smoke, explicitly not production acceptance. Original failed root
and gate remain unchanged. New isolated adapter
`scripts/dfm13_arena_recovery_candidate_diagnostic.py` passed19 focused tests;
root `logs/arena_audit/20261001-recovery-candidate100-v1` ran as PID2921178.
The manifest pins `controls_pass=false`, `diagnostic_only=true`,
`export_prohibited=true`, and `no_admission=true`. No controls were rerun.
Finished100:99 valid (95 keep,2 repair,2 reject),1 invalid missing verdict,
zero transport errors. These are outputs recovered, not accepted training rows.

Ten uniformly random cases were selected before inference, then independently
assistant-reviewed before consulting new verdicts. All10 model verdicts were
keep; assistant assessment:4 keep,4 repair,2 unresolved verification. These
provisional multilingual judgments are neither human/native gold nor population
accuracy; repair disagreements include interpretation/clarity, and unresolved
claims are not proven false. See `independent-manual-review.md` in the new root.
The reviewer confidently endorsed an unverified scholarly citation. Structural
recovery does not establish semantic reliability. No automatic merge/export.

Next repairs completed with25482 accepted candidates,6065 rejected,442 needing
review. Classes:21629 original keeps,483 recovered unchanged keeps,3370 repaired
and re-audited keeps. Existing guard validated all candidate hashes/lineages in
`logs/arena_audit/20261001-pending-next-repairs-v1/terminal-readiness-snapshot-v1`.
Original/recovered receipts require manual quality review; repaired receipt is
blocked by existing seq49/89 independent holds. `report.md` and `summary.json`
provide source-level counts, evidence hashes and restrictions. No uploads or
admission authorized by these receipts.

## Frozen Review-Only Recovery Smoke

2026-10-01: isolated adapter `scripts/dfm13_arena_frozen_review_recovery.py`
passed39 focused tests and prepared
`logs/arena_audit/20261001-frozen-whitespace-recovery100-v1`.
A read-only transactional snapshot selected100 of282 eligible finalized
review-whitespace failures, with no context exclusions. Original candidates,
history, raw evidence and source pins remain preserved. No corrections or
automatic admission are allowed. Six exposed smoke controls launched as
PID2918116 (`controls.log`); the100 recovery calls require all controls to pass
and explicit assistant review.

**Blocked before recovery dispatch:** the invented-internals hard negative
returned `keep`, endorsing its unsupported internal "English filter" claim as
technically accurate. The frozen semantic gate therefore fails regardless of
the remaining smoke outcomes. Do not weaken the gate or describe JSON validity
as semantic reliability. The100 recovery calls have not launched; no automatic
watcher is scheduled. `assessment.md`, isolated `ledger.sqlite`, and final
`controls-results.json`/`controls-complete.json` in that root preserve evidence.
Active repair clients, ledgers and servers were not modified.
Final smoke:6 structurally complete,0 technical errors;4 keep,1 reject,1 repair.
Five of6 match the predeclared allowed verdicts, so `controls_pass=false` and
all100 recovery cases remain pending. This exposed smoke is not an accuracy
estimate; a matching disposition does not independently validate its rationale.

## Timeout Integrity Check

2026-10-01 read-only investigation confirmed main1020 and next668 unknown
attempts are all `TimeoutError()`, with zero `interrupted_unknown` rows. Six raw
pairs expired after600.03-601.00seconds and predate the detached observer. The
read-only guard/observer do not initialize or UPDATE the live ledgers. A105-second
server metrics window shows decode-dominated162-205second mean completion latency,
zero waiting, and running counts close to the two clients' active counts; no
large residual-work accumulation was measured. Installed vLLM handles disconnects
with handler cancellation and engine abort, but raw captures lack per-request
server abort acknowledgements. Zero abort counters are not conclusive because
already-aborted output states are skipped before normal finished statistics.
Evidence and exact limitations:
`logs/arena_audit/20261001-repairs-followup-v1/timeout-integrity-20261001/report.md`.
No active client/server actions or model requests were made for this check.

## Scheduled Client Concurrency Migration

**Superseded before execution:** watcher2894608 was cancelled on2026-10-01
after the user required infrastructure interruption recovery to be separate
from the original attempt budget. Main PID2786888 remains128/server with the
unchanged plan hash `bc43f79a825715653a95aa00cae8bc2bbce5ffa96ab8cc48b720bbb30db751ae`.
No main repair client or server received a signal, and no migration archive was
started. `migration-256-preparation-v1/watcher-cancelled.json` records this.
Do not relaunch the current interruption helper: it preserves unknown attempts
but the unchanged driver counts them toward max3. An interrupted third attempt
would become technically exhausted `needs_review` (not a semantic reject).
That is an unacceptable performance-only increase in unresolved work. A future
version must retain original attempt history while providing a separately bounded
infrastructure-recovery budget; until then remain128/server. There is no live
graceful-drain or in-process-resize API.
The retired helper CLI now refuses execution before any process action;59
focused tests pass, including the disabled-CLI regression. Its historical
interruption routines are not an approved recovery implementation.

Read-only next-repair completion observer **2901991** continues checking every
30seconds (bounded two hours), with no model requests or process signals.
Its `completion-observer.log`, `completion-observer.json` and launch receipt
are in the next-repair root. It writes `completion-observer-terminal.json` only
after disjoint final counts cover the input, no inflight attempts remain and the
controller lock is released. This observer does not schedule any migration.

The following launch description is historical and **not an active schedule**.
2026-10-01: isolated migration watcher **2894608** is waiting for next repair
PID2807933 to become terminal and release its lock. Main PID2786888 remains
at128/server. There is no early main stop or server action. Watcher log:
`logs/arena_audit/20261001-repairs-followup-v1/migration-256-watcher.log`;
launch receipt: `migration-256-preparation-v1/watcher-launch.json` in that root.
58 focused tests passed, including13 migration tests. The implementation and
test pins are recorded; do not edit the live watcher or active repair driver.

The existing driver cannot gracefully drain or resize. This is explicitly a
controlled owned-client interruption, not a graceful-drain claim: exact command
and process start identity plus a pidfd protect against PID reuse; only SIGINT
is permitted. After exit, an exclusive controller lock protects the SQLite
backup and archived plan/seal. No completed rows or attempts are discarded.
Interrupted requests remain unknown and consume the existing max3 budget;
duplicate accepted rows are prevented, but repeated computation for unknown
requests cannot be ruled out. No unknown response is called completed.

Before interruption, fresh metrics must show no queue, KV below80% and no more
than256 total requests/server. After connection closure, three low-load samples
(at most16 requests/server, KV below20%, no queue) permit the256-client plan.
Failure to obtain that headroom within120seconds resumes the unchanged128 plan
instead. The runtime KV90%/shared512/reserve16 gate remains unchanged; its
conservative own-active reservation can limit effective concurrency below256.
Only `own_per_server` changes. Downstream prepared review-only recovery pins
are archived/refreshed without launching that recovery. Resume verifies actual
activity and byte-identical prior final records/completed stage cache against
the backup. Migration receipts will be in `migration-256-v1/` after execution.

## Classified Readiness And Completion Watch

2026-10-01: the existing readiness guard now supports three explicit selection
kinds: `original` (original audit keep), `recovered` (unchanged target with a
completed technical retry keep), and `repaired` (content-only correction with
completed fresh re-audit keep). Source bytes/identity/line, sealed repair input,
stage evidence and all independent holds are checked. Readiness remains blocked
while the relevant pipeline is active; final admission/upload are never implied.
Sample-based terminal review is allowed with an explicit bound sample basis,
not per-row manual gold or a claim of population certification. Detailed API:
`docs/reports/dfm13_arena_readiness_classification_20261001.md`.
45 focused CPU tests passed. No active repair code, plan or server was changed.

Next-repair seq49 has an independent verification hold for unsupported website
observations; seq89 has a localized hard hold for a visible letter-category
mismatch. These extend the existing hold sidecar from nine to eleven entries.
See `docs/reports/dfm13_next_repair_spotcheck_20261001.md`; the three-row assistant
spot-check is not human gold or an error-rate estimate. Early zero-error next
repair observations are superseded by subsequent600-second timeouts and length
failures, including whitespace-heavy outputs. Attempts remain separately saved.

Minute-by-minute stage/error/verdict/endpoint snapshots are in next repair
`completion-watch-v1/`. Main proposed128-to256 client concurrency change is
prepared only in `migration-256-preparation-v1/`; the live plan/seal are intact.
The current runner cannot resize workers or gracefully drain in-process. A
second same-ledger writer is not allowed. Any later controlled restart must
wait for next repairs to finish/unlock, recheck endpoint KV/headroom, preserve
unknown attempts and backup receipts, and refresh downstream review-only pins.

## Next Eligible Candidate Audit

**Next-audit to repair handoff verified:** the31989-row audit finished with
31069 complete and920 invalid responses, no pending/inflight, and its client
exited. Valid verdicts:21629 keep,5810 reject,3619 repair,11 needs verification.
Repair PID **2807933** automatically snapshotted the terminal ledger and sent
1024 captured requests (initial825 corrections and199 technical re-audits).
Its initial4154 accepted/1118 rejected table rows were imported audit decisions,
not newly successful corrections. Main repair PID2786888 remained running.
No server or training actions. The next-repair root contains a separate
`handoff-observation.json` for a short initial stage-completion rate measurement;
do not interpret startup rate as steady-state throughput or semantic accuracy.

Subsequent actual120-second stage measurement (not output-table imports): main
repairs completed329 validated stages (2.742/sec), with430 terminal attempts
including101 invalid attempts; next repairs completed772 stages (6.433/sec).
Next stage totals at window end:544 corrections,395 fresh re-audits,145 technical
reviews complete;742/146/136 respectively inflight, total1024. Main remains
running independently. `rate-before.json`, `rate-after.json` and
`remaining-stage-estimate.json` in the next-repair root preserve observations.
The nearby remaining-work estimate was7591 nominal GPU stages for next repairs
and22951 for main repairs, excluding bookkeeping-only original keeps/rejects.
At these measured rates that is roughly20 minutes and2h20m respectively, before
long-tail/additional-retry uncertainty; rates can change when the other client
finishes or source/response mix changes. These are conditional workload estimates,
not whole-campaign completion guarantees or semantic quality rates.

**Recent-reservation migration complete:** next-audit PID **2836374** supersedes
2819638. The latter was soft-drained; the ledger was backed up with all completed
and invalid outcomes preserved. `migration-recent-reservations-v1/` contains
code/test/manifest/seal archives, before/after metrics, ledger backup and receipt.
Next-repair pins were refreshed under its corresponding archive without
restarting that watcher. Current repair PID 2786888 remained running throughout.
The gate now reserves only active calls dispatched in the last two seconds,
plus decrementing per-sample credits, rather than double-counting all active
calls. Own128, total256, no waiting, KV80% and stale-metric fail-closed rules
remain. Twenty-seven CPU tests passed. Actual load rose from 190-194 to 248-256
requests/server, with no server waiting and KV52-55%; this confirms improved
admission utilization, not yet a controlled throughput benchmark.

**Superseding scheduling update:** user authorized gated overlap while the main
bulk drains. Next-audit PID **2819638** replaced watcher 2805295, preserving all
31989 pending ledger rows at migration. Only the next adapter/tests changed;
25 CPU tests passed. Archives and receipts are under
`migration-gated-overlap-v1/` in both next-audit and next-repair roots. The
next-repair plan pins were refreshed; its watcher was not restarted. Bulk,
current repairs, servers and training were untouched.

Every next-audit HTTP attempt now passes a per-endpoint gate: own maximum128,
fresh metrics (two-second reuse maximum), running total below256 with reserved
unobserved dispatch, zero server waiting, KV below80%. Missing metrics fail
closed; all locally active calls are conservatively reserved at each refresh.
The previous repair-completion wait is bypassed only by the sealed
`gated_overlap` authorization. Initial observed completions included four on
8802 and five on 8803. Runtime log is `gated-overlap.log`. Thus the strictly
serial chain below is historical: main repairs and the next audit may overlap,
while next repairs still require its own source audit to finish and unlock.

Gate fairness observation: a simultaneous snapshot showed 188-197 actual server
requests, zero server queues and 41-43% KV, despite 128 repair-active/server and
1024 next-audit ledger inflight. Next ledger inflight includes gate/preparation
waiters. The gate formula `256 - server_running - local_active` deliberately
double-reserves already visible local calls: with 128 repair calls it tends
toward 64 next-audit calls/server, or 192 combined. Both clients were submitting:
last-minute raw requests per endpoint were repair 69-96 and next audit 39-78.
Next audit completed 1354 rows in the sampled 120 seconds. This demonstrates
conservative admission underfill, not complete starvation or evidence of CPU
preparation saturation. Recommended future controlled migration: reserve only
recent/not-yet-observed dispatch rather than all local active requests, while
retaining own128, total256, fresh-metrics, no-queue and KV80% constraints. No
active pinned code was changed during this investigation.

The full sequential chain is now scheduled: bulk **2782433** -> current repairs
**2786888** -> next audit **2805295** -> next repairs **2807933**.
Next-repair root: `logs/arena_audit/20261001-pending-next-repairs-v1`, with its
own sealed plan, launch receipt, `progress.json` and `watcher.log`. The existing
repair runner derives its terminal count from the source manifest; its prepared
plan was verified to contain **31989**, with no 205242 hardcode. Initial state
was `waiting_for_bulk_terminal_and_lock`; no requests sent. The next audit's
lock remains held while it waits for current repairs, preserving stage order.
Next repairs retain 128/server, KV gating, bounded technical retries,
repair-only correction and fresh-context re-audit; no admission or upload.
Fifteen CPU tests passed again. No active code or servers were changed.

At this chain check the current bulk ledger had 167495 complete, 31899 pending,
3072 inflight, 236 transport unknowns, 2278 invalid responses and 262 preflight
blocks. The last 120 seconds yielded 3945 completions (~33/sec): approximately
18 minutes plus tail drain for 34971 outstanding, conditional on sustained load.
Automatic watchers poll every 30 seconds, then perform verification/preparation;
this minimizes idle gaps but is not a zero-idle guarantee.

**Update: queued and alive, PID 2805295.** Poincare supplied
`data/dfm13/pending-arena-eligibility-20261001/eligibility.json`; the consumer
verified its pinned evidence/output hashes and sealed **31989** rows in
`logs/arena_audit/20261001-pending-next-v1`: ComparIA 460, HelpSteer3 edit 7909,
HelpSteer3 preference 21377, Expert5K 2243. PRISM remains held and absent from
the audit ledger. `launch.json`, `watcher.log` and `queue-status.json` record
the detached process; verified state is `waiting_for_repairs_complete`.
No model requests have been made by this next-batch client. Bulk PID 2782433
and repair watcher PID 2786888 were verified alive and left untouched.
The earlier missing-receipt blocker below is now superseded. Fifteen focused
CPU tests passed again before handoff completion.

Clearance is specifically audit-only. The evidence screens exact contexts and
adjacent user/answer pairs against five pinned HelpSteer3 validation subsets;
exhaustive inherited DFM11/12 overlap and other benchmark overlap remain
unresolved. Provider-output terms and training/redistribution admission remain
separate gates. These limitations are preserved in the pinned producer receipts.

`scripts/dfm13_arena_next_audit.py` provides isolated generic `prepare`/`watch`
commands, reusing the reason-first bulk engine without its hardcoded preparation
total. CPU tests successfully prepared two rows; next-adapter plus repair tests
total 15 passing. No active pinned scripts were modified.

Inventory `data/dfm13/pending-arena-candidates-20261001/manifest.json` contains
53242 converted rows, including 18441 PRISM rows explicitly held on license.
Conversion validation alone is insufficient. At implementation time no completed
license/heldout-overlap handoff was available: **no next-audit process or eligible
queue has been launched**. Proposed immutable producer/consumer receipt format
and commands are in
`logs/arena_audit/20261001-pending-next-v1/eligibility-handoff.md`.
Only explicitly ready sources with cleared license and overlap checks plus
hash-pinned evidence and screened source bytes can prepare. PRISM requires
explicit clearance and is not implicitly included. Poincare's receipt-interface
confirmation remains pending; no direct agent messaging tool was available.

The next audit waits for the existing repair completion receipt, verifies all
input rows occur exactly once across repair output tables, and requires the
repair lock released. It uses 128/server, timeout600, thinking8192, fresh
connections and bounded three-attempt transport recovery. It retains original
CPU string bounds while removing native-grammar string bounds. Unlike repairs,
this adapter inherits bulk dispatch without a live KV gate; sequential scheduling
and coordination of unrelated clients remain required. No automatic admission,
upload, or PRISM auditing while held. No new GPU requests were made for integration.

## Scheduled Repair Follow-up (2026-10-01)

**Original-keep assessment and three additional holds:** parent supplied
`docs/reports/dfm13_original_keep_manual10_20261001.md`:7 retain,2 localized
repair concerns,1 needs factual verification. This source-stratified ten-row
sample used a different seed and3/3/2/2 quotas from the locally prepared unused
2/3/3/2 sample below; do not attach the findings to that unused sample or request
duplicate review. Neither sample supports a population precision or repair-risk
estimate. No automatic admission of the seven retained cases.

The common independent hold sidecar now additionally binds original seq945
(unverified emissions assumptions),60542 (unsupported autobiographical specifics)
and141981 (illustrative16-versus17-byte length) to their exact source IDs and
original-row hashes. The six-repair-only sidecar was archived before this update.
All three are non-admissible pending resolution; uncertain assumptions are not
relabeled as proven false. Original-byte selection support in the readiness guard
checks ledger offsets, IDs and recorded/selected hashes without reading repair
content. Actual read-only preparation/enforcement blocked all3 originals and all6
repairs under the updated sidecar. Proofs: `original-keep-readiness.json` and
`readiness-v2.json` in the existing readiness root. Ten guard tests pass. Old
readiness pins intentionally fail after hold/guard updates. No active-ledger edits.

**Bounded review-only recovery prepared, not launched:**
`scripts/dfm13_arena_review_only_recovery.py` and sealed plan
`logs/arena_audit/20261001-review-only-whitespace-v1/plan.json` cap a future
post-terminal diagnostic at32 unresolved whitespace review failures. No watcher
or automatic run was created. It requires a terminal receipt, released source
lock, complete/disjoint output accounting and no inflight attempts before freezing
jobs. Only latest unresolved retry-audit/fresh-re-audit whitespace failures in
final needs-review rows qualify; successful stages, correction-generation failures,
thinking loops and genuinely long outputs do not. One attempt/case, explicit
JSON-object contract, thinking-on whole-target review, strict CPU validation;
no generation, accepted-table writes or automatic admission. Thinking-off
correction remains unscaled.

**Original keep baseline sample:** CPU-prepared ten immutable original keeps in
`logs/arena_audit/20261001-original-keeps-independent10-v1/samples.json`, with
separate lineage and Poincare handoff. Seeded hash-random ranks within four source
strata yield quotas2/3/3/2 from keep populations2094/45812/82382/25598. No repair
outputs are sampled. Independent review remains pending; the parent must route
the handoff because no direct agent-messaging tool was available. Source-only
stratification is not language balancing, and comparison with the biased eight
repair examples is not a population error-rate estimate. Nine new focused CPU
tests cover selection, terminal gating, explicit contract and reproducible sampling.

**Six-candidate export hold enforcement:** the confirmed sidecar now holds seq9
and seq2616 as hard holds, and seq2606/2609/2613/2632 as verification holds, all
bound to live candidate hashes with release unauthorized. Seq2616's independent
numerical boundary defect is preserved separately from the four verification
targets. The original seq9-only sidecar was archived as
`dfm13_bulk_repair_independent_holds_20261001.before-six-holds.json`.
No active ledger was edited. The eight-example/two-source assessment is biased,
not a population estimate; neither of the other two examples is automatically
certified.

New guard `scripts/dfm13_arena_export_readiness.py` pins the current hold sidecar,
independent assessment, selected candidate hashes and manual-review scope. It
blocks both hold dispositions (including copied held hashes and changed hashes
for the same source identity), rejects pin/content drift and requires whole-target
manual review before readiness. Eight guard tests passed. Read-only validation
against all six actual accepted candidates produced `blocked_independent_hold`
and the expected enforcement exception. Receipt and mandatory export-owner hook:
`logs/arena_audit/20261001-repair-export-readiness-v1/readiness.json` and
`export-owner-handoff.md`. Future exporters must invoke the guard before writing
and reference the receipt/holds in their manifests. No exporter was launched or
globally patched; a report link alone is not enforcement. Existing GPU work runs
unchanged.

**Length-pilot final:** v1's12 initial calls and v2's11 correction/re-audit calls
all stopped normally, using17050 completion tokens combined. V1 had five valid
whitespace-review decisions, one missing verdict and six correction contract
failures. V2 (explicit unchanged schema in prompt) produced five valid corrections
and one schema-shaped invalid object; their five fresh re-audits returned four
keep and one repair. The latter caught seq191's short100-word correction. Other
spot-check warnings remain, so no full follow-up or admission was queued.
Final report: `logs/arena_audit/20261001-length-diagnostic-contract-v2/assessment.md`.

**Manual quality gate required before exports:** the parent reported an accepted
seq9 repair with suspected remaining Andersen date/title errors; Boole owns
verification and an external hard-hold ledger. Preserve that independent hold;
do not treat this page as factual verification of the disputed details. User
explicitly requested the current run continue, without admission, and a manual
repair-quality sample before any export. No export or upload is authorized by
automated `keep`, even after fresh-context re-audit.

Separate length diagnostic is frozen under
`logs/arena_audit/20261001-length-diagnostic-v1`, using six whitespace failures
and six suspected correction reasoning loops. It reused Search's JSON-object
transport helper with strict CPU schemas, one attempt/stage, one client/endpoint
under the same headroom gate. All original attempts/pins remain unchanged;
long/unclassified cases are deferred separately. V1 finished with five valid
reviews, one missing-verdict response and six correction contract failures.
The correction contract depended on the removed transport schema for enum
values; outputs were rejected rather than normalized silently.

`scripts/dfm13_arena_length_pilot_v2.py` explicitly supplies the unchanged output
schema in the prompt and retries only those same six correction cases under
`logs/arena_audit/20261001-length-diagnostic-contract-v2` (PID2845657 at launch).
Thinking-off corrections use4096 tokens; each valid candidate receives a fresh
thinking-on JSON-object re-audit with8192 tokens. This is a contract fix, not
gold-label tuning. No full follow-up or candidate admission is automatic.
Initial spot-check: seq191's corrected100-word story has92 whitespace body
tokens (91 excluding its standalone dash). Seq728 received a re-audit keep
despite that reviewer explicitly declining to verify a specific historical
claim. These are quality warnings, not evidence that transport recovery certifies
correctness. Pilot JSON/status success and semantic quality must be reported
separately; native-language or external-fact gold is not claimed.

Read-only failure inspection is saved in
`logs/arena_audit/20261001-repairs-followup-v1/length-failure-review.md`.
A live 443-length-attempt snapshot contained 145 outputs over95% whitespace,
249 with no final content and 49 other visible outputs. Sampled corrections
with no final content exhausted reasoning on repeated reconsideration/counting;
one substantial specification correction genuinely ran long. Whitespace loops
persisted in sampled re-audits despite removing transport string bounds.
No active repair/retry policy changed: the report recommends separately bounded,
post-completion transport/reasoning diagnostics rather than identical retries or
a blanket token increase. Raw provenance and invalid status remain intact.

**Actual handoff verified:** bulk PID 2782433 exited after all 205242 rows became
terminal: 201402 complete, 510 transport unknown, 3068 invalid responses and
262 preflight blocked. Repair PID **2786888** automatically acquired the source
lock, created its snapshot/ledger and sent 1024 captured requests. An early
follow-up check recorded 24 completed technical re-audits and two completed
corrections, all with `finish_reason=stop`; both corrections then entered
`fresh_reaudit`. This is actual stage execution, not merely a scheduled watcher.
No completed fresh-re-audit outcome was observed at that initial check. Original
keeps/rejects carried into output tables are not new model reviews. No servers,
training processes or active code were changed during the handoff.

Watcher PID 2764056 below is superseded by **2786888** after the parent's bulk
384/server migration. Verified manifest delta was exactly
`concurrency_per_server: 512 -> 384`; all reviewer/code pins remained unchanged.
Only the watcher was stopped/restarted. Its old plan, seal, launch and progress
were archived under `migration-384-1790840855788071729/` in the follow-up root,
with `receipt.json`; the refreshed plan embeds the current manifest and pins
its current manifest/seal. Bulk PID 2782433, source ledger and servers were not
changed. Restart passed verification and reported
`waiting_for_bulk_terminal_and_lock`. Follow-up remains **128/server**.

At the migration check, bulk had 121946 completed and 80602 pending/inflight.
The short observed interval was approximately 44.4 completed rows/second,
suggesting about 30 minutes plus drain time; allow 30-45 minutes if sustained.
This is a short-window estimate, not a completion guarantee. Starting repairs
before terminal bulk would require a new incremental snapshot/claim protocol
and a shared admission gate; the present watcher deliberately does neither.
Do not bypass the terminal/lock gate just to overlap the two clients.

User-authorized watcher PID **2764056** is scheduled in
`logs/arena_audit/20261001-repairs-followup-v1`, with `plan.json`, `seal.json`,
`launch.json`, `progress.json` and `watcher.log`. Implementation:
`scripts/dfm13_arena_repairs.py`; seven focused CPU tests passed in
`tests/test_dfm13_arena_repairs.py`. The active bulk PID 2755753 and servers
were not changed. The verified initial watcher state is
`waiting_for_bulk_terminal_and_lock`, with no model calls.

The watcher requires all 205242 v3 rows terminal (no pending/inflight) and
exclusive acquisition of the bulk controller lock, then backs up its SQLite
ledger without changing it. A crashed incomplete bulk remains blocked rather
than being mistaken for completion. Source hashes, code/tokenizer pins and the
plan seal are checked before dispatch. Resume uses the same command:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python scripts/dfm13_arena_repairs.py watch \
  --root logs/arena_audit/20261001-repairs-followup-v1
```

Technical failures get at most three follow-up attempts per stage, including
interrupted attempts; original attempts remain in the source root/snapshot.
Context-overflow preflight is not repeatedly dispatched. Only validated `repair`
decisions generate replacement target content; history, tools and provenance
remain unchanged. Rejects are not regenerated. Each corrected target receives
a fresh-context reason-first thinking audit, without the previous decision or
correction rationale. This uses the same model, not an independent model.

All stages share **128 requests/server**, timeout 600 seconds, thinking enabled,
8192 output tokens and eight CPU preparation threads. New dispatch pauses at
90% KV or when measured running/waiting plus local active requests approach
the shared 512 cap with 16 reserved slots (RepoChat uses four). Missing/stale
metrics fail closed. This conservative client cannot enforce limits on unrelated
clients that independently increase their traffic. No server lifecycle actions.
Native transport omits string-length grammar bounds; CPU validation retains
them. Exact raw requests/responses and stage attempts are preserved.

Separate SQLite tables `accepted`, `rejected`, `needs_review` contain decisions
and provenance; corrected rows are stored with original and candidate hashes.
`accepted` means an automated candidate verdict, **not training admission**.
No automatic exports, uploads or admission. Remaining semantic false accepts
from calibration still apply; a second context does not certify correctness.

Planning estimate from the earlier 53885-complete snapshot: roughly 19K repairs,
about 38K correction/re-audit calls plus technical retries. Allow roughly
45-120 minutes after bulk completion under available capacity, potentially
longer during KV pauses; this is not a measured completion promise. Watcher
checks terminal status every 30 seconds. Follow-up outputs are separate from
the immutable original bulk results.

Read-only driver review and CPU test rerun: seven tests passed (2026-10-01).
Coverage checks content-only replacement including tool metadata, transport-only
string-bound removal, fresh-review isolation from the correction rationale,
verdict routing, terminal row counts, active source-lock exclusion and seal drift.
The asynchronous retry/resume and metrics-gate paths have been source-reviewed,
but are not covered by an end-to-end fake-server test; no live repair smoke has
run. Do not interpret these seven tests as full runtime validation.

Operational constraints: the watcher is a detached process, not an automatic
restart supervisor. A pin/source drift or startup failure exits rather than
repinning itself. Persistently high KV or unavailable metrics can pause it
indefinitely. A crash between snapshot rename and its hash receipt requires
manual inspection (it fails closed). Per-row SQLite commits and sequential
metrics polling can limit throughput. `complete.json` is the authoritative
completion receipt; the last `progress.json` may still say running. Existing
original keeps are carried into the candidate table, not audited again by this
follow-up. Corrections requiring tool-call changes go to manual review.

The user authorized all 205242 uploaded preferred rows despite the unresolved
quality limitations documented in [reviewer calibration](/pages/dfm13-arena-reviewer-v4.md).
This is unverified triage, not certified correctness or automatic admission.

Original root: `logs/arena_audit/20261001-bulk205242-v1`, PID 2731673. It started
before the requested deadline, then was soft-drained after widespread
ServerDisconnectedError while all eight server health endpoints remained 200.
Only the owned client was signalled; no servers or training processes were touched.

Historical recovery root (superseded by the stronger pass below): `logs/arena_audit/20261001-bulk205242-recovery-v2`, PID
2735457. Fresh HTTP connections and at most three saved transport attempts replace
pooled reuse. All 15906 completed original rows were verified byte-identical;
7426 failed attempts were archived, then 7421 completed and five returned explicit
invalid outputs. No new terminal transport errors had appeared at the documented
34722-complete snapshot. Use `progress.json` for current counts.

The SQLite ledger retains verdicts, reasons, provenance and error states; raw
requests/responses remain in `raw/` and the preserved original root. Eight existing
8800-8807 endpoints serve dfm13-gemma4, at 256 client requests/server, with eight CPU
preparation threads. Full prompt/output context is checked without truncation.
No full-corpus pretokenization, automatic repair, export, upload or admission.

Exact-rubric development probe: `logs/arena_audit/20261001-bulk-rubric-probe44`.
All 44 responses were structurally valid, but definitive-reference agreement was
16/32 and keep precision 12/25 (48%). The invented-internals control and several
visible factual/instruction failures remain accepted. This is not an improvement
established by calibration. User authorization to collect triage does not change
that assessment.

Implementation: `scripts/dfm13_arena_bulk_audit.py` and the isolated
`scripts/dfm13_arena_bulk_recovery.py`; four focused tests passed. Detailed evidence
and launch/recovery paths: `recovery-report.md` in the recovery root.

## Stronger Full Pass

User authorized switching to the tested reason-first/thinking setting and
re-reviewing every row, not overwriting the first pass. PID 2735457 was
soft-drained and exited; first-pass results remain separately preserved.

Active PID **2743254**, root
`logs/arena_audit/20261001-bulk205242-reasonfirst-thinking-v3`. The minimal
`scripts/dfm13_arena_bulk_reasonfirst.py` adapter reuses the runner/recovery
transport, exact tested prompt/schema, thinking=true, 8192 output tokens,
600-second timeout and 256 requests/server. All 205242 source row locations
were copied into a fresh ledger without copying prior judgments into prompts.

Live request capture verified reason-before-verdict and thinking settings.
First snapshot: 2372 complete, 2048 in flight, no transport errors. All servers
returned 200, with 253-256 active requests each, zero waiting and KV usage 45-48%.
See `progress.json`, `client.log`, `ledger.sqlite`, `raw/`, and `launch-report.md`
in the new root. No server or training changes.

The 32-case known-reference reason-first probe yielded 29 valid outputs and
three timeouts: 18/29 agreement, 12/20 keep precision. This is stronger on the
matched diagnostic than the previous setting but still has substantial semantic
errors. User authorization does not imply certified quality or automatic admission.
