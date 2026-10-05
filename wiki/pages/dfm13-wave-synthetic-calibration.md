---
type: Runbook
title: DFM13 Wave Synthetic Calibration
description: Wave-three and wave-four synthetic conversation calibration, seed allocation, and quality gates.
tags: [dfm13, multilingual, synthetic, calibration]
status: draft
last_updated: 2026-10-03
confidence: medium
---
# DFM13 Wave Synthetic Calibration

Part of the [fourth language extension wave](fourth-language-extension-wave.md).
These operational findings do not establish population-level quality rates.

### Frozen-ledger CPU publication continuation (2026-10-03)

`scripts.finalize_slovak_offline` verifies all410 terminal status hashes against
`recovery-drain.json`, reads accepted ledgers read-only, finalizes selections,
and exports with `upload=False`. It cannot enqueue GPU jobs. Existing packages
require matching selection/data hashes; conflicts fail closed. Five tests passed.
Detached PID2694011 writes
`logs/slovak-offline-publication-20261003.log`; its durable progress is
`data/dfm13/wave4/slovak-additive-20261003-v1/offline-publication-progress.json`.

Actual receipts show main140 uploaded/135 local-only; Baltic43 uploaded.
Publisher logs report HTTP429 creation quota300/day, retry "about23 hours"
(logged observation, not a new reset-time probe). This continuation made no
upload/API attempts. Local exports are not remote integration. The26B source
controllers remain frozen; no GPU/server actions were performed.
Continuation: both missing selections completed (`sk-sv`423,198 pairs,
`sk-uk`8); six new small packages built locally. Slovak now has30 ready
selections:20 uploaded,7 local-only packages,3 large packages still building
(`en-sk`, `nl-sk`, `sk-sv`). These are progress counts, not publication completion.

### Audit-first simplification (2026-10-03)

See [audit-first policy](dfm13-audit-first.md). Targets and source holds remain.

### Generation constraint variant, CPU-prepared (2026-10-03)

Moved intact to [generation constraints and compact review](dfm13-generation-constraints.md)
on2026-10-03 to keep this page within the OKF size bound. Historical31B/26B
artifacts, commands, source holds and model-choice supersession remain linked there.

### Completed 31B comparison: independent diagnostic review (2026-10-03)

Historical76-case snapshot and15-case independent assessment moved to
[generation constraints](dfm13-generation-constraints.md#completed-31b-comparison)
to retain size headroom. The hash-bound report and all limitations remain linked.

### Remaining Slovak edges: bounded source check (2026-10-03)

The ca-sk, fo-sk and nn-sk gaps remain **no available supply under selected
sources**, not global unavailability. Independent streaming of pinned CA/FO/NN
English legs against all 784,241 selected SK candidates found zero raw exact
English overlaps; the existing unambiguous pivot index also returned zero.
Bounded OPUS metadata checks found no new approved PD/CC0/CC-BY release for
these gaps. Research evidence is isolated at
`data/dfm13/wave4/slovak-gap-research-20261003-v1`; no candidate bundle, queue
write, license relaxation or GPU call occurred. Two focused tests passed.
See [the main/Tesla evidence handoff](../../docs/reports/dfm13_slovak_gap_supply_20261003.md)
for exact counts, source restrictions and reproduction commands.

### Luxembourgish conditional seed reserve (2026-10-03)

Prepared isolated `data/dfm13/wave4/lb-seed-reserve-20261003-v1`: 5,538
verified additional disjoint windows from 4,258 existing Wikipedia documents,
not new documents, alongside the unchanged 34,013-window original inventory.
All passed exact/whitespace duplicate exclusion against existing LB plus reserve,
pinned source/extractor checks, and full native student-template diagnostic echo
probes (maximum 2,761/4,096 tokens; no cuts). Eleven CPU tests passed and the
existing wave-four provider consumed a reserve view in a temporary selection root.

This is **unadmitted reserve**, not a changed approval or guaranteed acceptance
yield. Use only after observed supply shortage through an explicitly reviewed
successor; retain parent/view provenance, maximum three views per parent/family,
rights, task diversity, semantic deduplication, and full generated-conversation
validation. No frozen roots, cursors or GPU processes changed. Exact pins,
reproduction command and admission limitations are recorded in
[the reserve report](../../docs/reports/dfm13_lb_seed_reserve_20261003.md).

### Slovak additive candidate preparation

FINAL recovery-ledger verification1791058184:all410 Slovak statuses terminal,
all status/input pins verified against recovery-drain.json. Counts1380829accepted,
528813rejected,373excluded_unreviewed total1910015. Source queue10739087done/
19364failed; recovery52023done/4241failed, no pending/running.10659 generation
jobs explicitly deferred31B,83547done/58failed. This establishes this source's
GPU-recovery drain, NOT admission/upload completion; uploads remain quota-held.
Caller recovery-first now loops real ledger reconciliation to terminal before
accepted selection, with separate pinned recovery-drain.json. Owned CPU2642708
resumed after exact SIGINT cleanup of2638570, no competing writers/GPU changes.
21 tests pass. Main launched recovery2639505 via existing monitor helper (not an
independently added client); earlier autonomous-restart attribution is superseded.

Quota recovery supersedes prior livePID:2542233 exited naturally on HF300/day
repo-creation429. Caller-local --defer-uploads resumes from verified enqueue
receipt without prep rerun; writes explicit per-pair pending uploads and never
completion.json while publication deferred.2635437 resumed, then exact pidfd
SIGINT cleanup safely yielded single ownership to2638570 with --recovery-first.
This materializes missing/nonterminal ledgers before accepted selection. No
shared queue/IO/frozen31B edits, no GPU/server signals.20 focused tests pass.
v7 log completed115/115 priority components; all410 ledgers now exist (310terminal,
100 awaiting reconciliation at snapshot). Existing monitor restarted recovery
client2639505 at unchanged32/endpoint; actual audit completions51526->52020,
32running at snapshot. Upload quota hold remains explicit; no premature drain.
Logs:slovak-additive-advance-v6.log/v7.log; exact handoff in additive root
recovery-priority-handoff.json. CPUaccepted selection now follows recovery feed.

Portuguese publication blocker RESOLVED for lb-pt_pt (92rows) and pt_pt-sq
(578rows). Existing card_languages already normalized ISO pt with BCP47 pt-PT;
the live publisher had stale imported code. Targeted retries used the existing
release API/pair locks, with original data hashes guarded before upload and
verified unchanged afterward. Remote README/data/attribution hashes verified;
row language remains pt_pt. No publisher module/controller edit or GPU change.
Five focused tests pass. Receipts:wave4/portuguese-card-retry-20261003/result.json.
HF create_repo initially hit daily creation cap; authenticated repo_info proved
both repos already existed, so only updates were retried without new creation.
Poincare ownership handoff: successful publication receipts make the live
publisher skip these two; future pt_pt pairs still need its next safe code refresh.

Drain follow-up1791056792:410 combined components/pins reverified. Main parallel
pass complete240ready/35awaiting/33no-supply,0inflight/errors. Slovak167/410 ledgers
materialized784349rows;46parts/140s implies~12min unvisited CPU tail, not guaranteed
drain ETA. Source snapshot250793pending/3202running; later recovery0pending/
78running still has active ledger producers. Do not infer drain from a momentary
empty recovery queue. Transform11uploaded; instructions15uploaded/1empty/2held;
10659 generation jobs remain explicitly deferred31B. Publisher separately reports
HF pt_pt README language rejection for lb-pt_pt and pt_pt-sq; no exporter changes.
Detailed readiness conditions in the Slovak additive report.

Third idle watch succeeded1791055717: original2143812 had written all308 pair
outcomes and entered sleep without pair/component locks. Exact pidfd handoff
launched2607843 with2 workers2607863/2607866; original is gone, no duplicate
controller. Log advance-selections-parallel2-1791055717.log; preserved evidence
translation-release/parallel-handoff.json.140second window completed42 more pair
outcomes without errors, while Slovak370->381; different second-pass population
prevents claiming a controlled speedup over the prior15-pair first-pass sample.

Slovak CPU preparation now VERIFIED COMPLETE:410 registered parts/1910015 rows,
matching all chunk/preflight/registered pins. Combined manifest contains410
additive components; main416-component manifest excludes them. Durable receipt
slovak-additive-20261003-v1/cpu-preparation-verified.json. Watcher2520116 exited
normally; no handoff watchers remain. Static waiting_main_component_freeze phase
is superseded by actual manifests/active en-sk selection in2542233, not a block.
At1791056347 source audit pending471662/running3611; recovery pending169/running258.
CPU completion is NOT audit drain/GPU-release readiness. Main selector240ready,
34awaiting,33no-supply,1inflight; no reported errors. No GPU concurrency changes.

Second authorized900second watch1791054595..1791055498 likewise found no
full-pass idle boundary. Selector2143812 remains active on ro-sq,264 pair
receipts; Slovak reached351/410 queued parts. No signal or parallel successor;
watcher exited normally and pgrep confirmed no handoff watcher left. GPU
concurrency unchanged. The same parallel-handoff.json records signaled=false.

Authorized2-worker handoff watch completed1791053604..1791054505 without a
verified full-pass idle boundary. Exact selector2143812 remained active through
el-* and en-*; no signals or successor launch. Evidence:
translation-release/parallel-handoff.json phase=no_idle_within_watch,
signaled=false. Guard script handoff_wave4_selector.py requires fresh complete
pass status, sleep state, no pair/component locks, exact identity and pidfd
revalidation before any signal.10 guard/parallel tests pass. During watch en-fa
ledger exposed140 audit retries; Slovak reached297 parts. No after-handoff
performance comparison possible because handoff correctly did not occur.

Selection efficiency inspection:2143812 advanced75->90 pair receipts in140s,
about44 CPU-seconds; large components take~60s while small pairs are fast.
Slovak advanced204->215 concurrently. Optional NEW parallel selector script
advance_wave4_selections_parallel.py prepared, NOT launched: same controller
lock,1..4 spawned workers, bounded outstanding pairs, unchanged pair/component
locks, one status writer and graceful future drain. Current active bs-sr pair
was not interrupted; no duplicate controller or frozen31B edit.27 related tests
pass. Shared I/O contention prevents assuming4x speedup; safe idle-boundary
handoff requirements and command recorded in the Slovak additive report.

Main CPU completion confirmed at1791052208:416 components/6269371 rows,
exact_payload_coverage=true,0 new jobs,226 queued pivots. Main2448161 exited
normally. Selector2143812 then activated on its next scheduled cycle: frozen
manifest has exactly those416 components, valid preparation hash and0 additive
components. At1791052469 it had32 pair receipts (31 pending,1 ready); publisher
2143813 remained alive on its independent300second polling cycle, publication
not yet verified. Slovak2542233 resumed actual enqueue to130 parts/650000 rows
of410 expected. Main completion is NOT additive completion or audit drain.

120-second follow-up1791052009..1791052129: main coverage advanced
5508658->5929050 rows (177 components),0 additions. Main2448161,
Slovak2542233 and selectors2143812/2143813 remain alive. Main receipt/selection
manifest still absent;113 additive parts registered of410 expected. No combined
CPU-complete or audit-drain readiness claimed; no worker intervention.

Actual timeout/recovery observed at1791051857: original Slovak2481015 exited
naturally with v4 log ending in the exact enqueue-lock TimeoutError. Watcher2520116
verified terminal identity and launched2542233 once with43200-second local wait.
No signals, main-preparation rerun, job reset or GPU action. Evidence:
slovak-additive-20261003-v1/timeout-resume.json; successor log
logs/dfm13/wave4/slovak-additive-advance-v5.log. All113 registered parts preserved.
Main2448161 then verified5263032 rows across123 components with0 additions;
selection2143812/publisher2143813 alive, still awaiting the completion receipt.

Timeout handling successor: scripts/slovak_chunked_preflight.py now provides
caller-local enqueue_with_wait, default43200seconds via
advance_wave4_slovak_additive --enqueue-wait-seconds. Only the exact shared-lock
timeout (before queue writes) is retried; other errors propagate. Shared IO,
queue implementation and frozen dependencies are unchanged. Existing2481015
was NOT interrupted or reset. Detached watcher2520116 observes its exact identity
and may resume it once ONLY after terminal enqueue-lock timeout, preserving all
parts/jobs. Contract and status live in the additive root as
cpu-completion-watch-contract.json and cpu-completion-watch.json; log
logs/dfm13/wave4/cpu-completion-watch.log. It tracks main coverage, pinned selection
manifest and additive enqueue receipt separately, never global-ready/audit-ready.
At1791050590:46 components/1427962 rows reconciled,0 missing jobs; old waiter alive.
Twenty-two focused tests pass. Watcher continues until both CPU receipts and
selection activation are verified; GPU processes remain untouched.

Follow-up 15-minute watch (Unix1791049313..1791050213): main2448161
finished all226 expected pivot registrations and entered exact_coverage at
1791050071. Reconciliation advanced through direct-bg-el:25 components,
359748 rows checked,0 missing jobs inserted. No parallel-preparation or
selection manifest yet; selection2143812 correctly remains waiting.
Slovak2481015 advanced81->113 queued parts before reconciliation acquired
the shared enqueue lock;127 part preflights sealed. This is a temporary enqueue
wait, not additive completion. GPU workers untouched; latest monitor reported
19721 requests/minute and91-100% utilization. No new fix/restart was needed.

Operational recheck at Unix time1791048886 confirms both unchanged producers
advance: main2448161 reached pivot-hu-sl; Slovak2481015 reached64 queued parts
and95 sealed preflights of410 expected. Earlier same-check registration snapshot
contained172 main pivot components/87400 rows and63 additive parts/315000 rows.
Audit snapshot:6732390 done,7440 failed,2390692 pending,3074 running;
monitor reported about29786 requests/min across eight servers (74-100% GPU).
Main preparation/freeze and additive enqueue-complete markers remain absent,
so release watchers correctly wait rather than publish incomplete selections.
Fourteen focused tests rerun successfully; no additional restart or code change.
The separate additive completion and canonical publication guards remain required.

Enqueue fairness update: watcher2481015 resumes preserved parts after a safe
SIGINT refresh of2475044 while the operator exclusively held the enqueue lock.
It yields2seconds between parts only when exact main2448161 is polling in
pivot_enqueue. Main advanced beyond fa-nl; no GPU-client throttling or resets.
Fourteen focused tests pass; current log slovak-additive-advance-v4.log.

Latest continuation2475044 replaces serial preflight with16 spawnedCPU workers,
5000-row deterministic parts,32 outstanding tasks and one enqueue writer. No
whole jobs had been queued; partial temp preserved. Initial check:33 preflighted
parts,2 registered/10000 rows. Input1910015 pairs materially extends drain ETA.
Combined pair budget/dedup and publisher guard unchanged;13 tests pass. Current
log `logs/dfm13/wave4/slovak-additive-advance-v3.log`; shared handoff tracks parts.

Publisher collision guard now requires a frozen main manifest with no publishable
SK supply and no prior canonical export/registry entry. Main prefixes exclude new
sk-additive-v1-* components; separate combined selection includes them. Existing
data/arrays are never automatically replaced. Current watcher2470642 supersedes
2465638 (waiting-only restart); CPU2460511 and GPU clients unchanged. Ten tests
pass; exact evidence/recovery boundary in the Slovak additive report below.

Primary pinned OPUS metadata plus downloaded READMEs support public-domain
ELRC-487/488 Slovak ministry releases and CC-BY-4.0 numbered ELRC-2721-EMEA v1.
These were absent from the narrow existing allowlist, explaining33 empty Slovak
edges. Isolated CPU PID2460511 prepares en-sk and exact-English Slovak pivots in
`wave4/slovak-additive-20261003-v1`; no old frozen input or live queue mutated.
Counts remain candidate-only; license/quality/actual join coverage are distinct.
Evidence, caveats, tests and version-aware integration contract:
`docs/reports/dfm13_slovak_additive_20261003.md`.

Authorized continuation is armed as watcher2465638 behind CPU2460511: preflight/
versioned audit enqueue, separate old+new combined manifest, single-cap accepted
selection and existing verified export/upload/integration. Four focused tests
pass. Assembly must include `data/dfm13/wave4/slovak-additive-handoff.json` and
its producer/queue state; main wave4 completion cannot imply additive completion.
Current phase waiting_cpu_integration, both completion flags false. No target cuts.

The final launch matrix now names the measured-capacity Fars/QA successor
consumers and the two-pass P3 dispatcher, superseding the earlier consumer-v1
launch entries without altering historical artifacts. See
`docs/reports/dfm13_31b_final_root_matrix_20261003.md`. CPU readiness is not
semantic or live-capacity approval; source holds remain in force.

### Read-only source-feed audit, later2026-10-03

Subsequent explicitly authorized coverage fix uses bounded512-payload digest-ID
membership reads and writes only absent jobs, preserving source hashes/history
and concurrent-writer races. Six tests pass. Live institutional pass untouched;
next wrapper import benefits. Filesystem-page waits are observed, SQLite lock
contention remains plausible rather than proven. Poincare handoff:
`docs/reports/dfm13_coverage_efficiency_handoff_20261003.md`.

User then authorized controlled continuation: detached PID2446844 verifies
extraction/sealed registrations, signals only exact old CPU child2427821, waits
for parent2103630/locks, then resumes pivots/enqueue/read-first coverage. No
discovery rerun or GPU/client signals; completion marker only after coverage.
Nine focused tests pass. Live phase is in
`data/dfm13/wave4/coverage-continuation-status.json`; ownership details are in
the coverage-efficiency handoff report. Poincare should not duplicate this chain.

Continuation update: first process2446844 signaled the exact child successfully
but hit a psutil.NoSuchProcess exit-check bug. Regression fix and successor
authorization preserve that history; no second signal. PID2448161 now runs
`pivot_build` after verifying203 direct/21 institutional extraction receipts.
Old child/parent are absent, original audit clients still live; anchor database
grew past1GB and completion marker remains absent. Ten focused tests pass.
Current log: `logs/dfm13/wave4/coverage-continuation-v2.log`.

Post-handoff observation: a 60.23-second direct Prometheus counter window
measured 32,666 completed requests/minute, with all eight GPUs at 96-100% at
the final sample. An earlier 30.30-second window measured 18,017/minute.
These are mixed-workload observations, not a controlled causal benchmark;
instantaneous KV occupancy and inflight requests can be low between feed bursts.
All English direct/institutional legs had reached the pivot index log by this
measurement. Audit clients and GPU servers were not restarted.

At Unix1791044769 source queue had5080100 done,6329 failed,3641183 pending and3584
running. Approved direct/institutional extraction and registration are complete;
active CPU child2427821 is reconciling coverage before pivots, not downloading.
No pivot completion marker yet;258 pairs qualify, output count unknown. Observed
GPU-feed bursts and filesystem waits suggest investigating I/O/commit contention,
not adding clients to an already3.645M-row backlog. No workers altered. Exact
counts, caveats and actionable CPU stages:
`docs/reports/dfm13_wave4_cpu_operational_audit_20261003.md`.

### Final production31B freeze and root matrix

New wave4/Baltic `synthetic31-full-staged-v3` roots independently verify with
unchanged770000/140000 quotas, zero jobs/accepted/active and no approval receipts.
Production now pins the shared snapshot/context gate directly, not the unrelated
fresh-comparison preparation module. Meaningful renderer/reviewer/quota/recovery/
capacity dependencies remain pinned;28 focused tests pass. Capacity measurements
and real comparison approval remain pending. Fresh30-v5/12-v3 still verify.
The earlier requirement to replace balanced execution-v1 is now satisfied:
source-v4/execution-v2 independently verify against the final production hash.
Old roots remain preserved, not repinned. Exact matrix and freeze receipt:
`docs/reports/dfm13_31b_final_root_matrix_20261003.md`. No GPU actions or launches.

### CPU launch rehearsal, 2026-10-03

**Superseding endpoint fix, later same day:** explicit user authorization added
strict advertised context/snapshot validation before76 dispatch. The shared
`wave31_endpoint_health` gate also supports P3 via an exact child command after
`--`, refusing launch on mismatch.26 CPU tests pass. Freeze-v2 and new fresh30-v5/
fresh12-v3 receipts preserve all prior versions. Boole/Poincare/Epicurus interface
and ordered commands: `docs/reports/dfm13_31b_endpoint_gate_handoff_20261003.md`.
No GPU actions. The missing context-check finding below is historical; balanced
execution and final Fars consumer remain with their respective owners.

Subsequent Epicurus finalization resolves the Fars preparation gap: final held
freeze has zero pending/running, and sealed consumer-v1 contains89296 versions.
Its launch authorization remains false; global drain is separately required.
The shared endpoint gate interface also applies to the new Baltic QA consumer.
See the endpoint-gate handoff report for exact module/API and final Fars paths.

Thirteen mocked launcher/readiness/transition tests pass; no process, socket,
GPU or HTTP actions occurred. Exact eight-server construction retains only31B,
32K context, TP1, distinct internal ports and comparison maxseq8. Fresh42 and
balanced234 verify, but the full launch sequence is not yet ready: balanced234
has no run CLI; Fars needs final freeze/delta and a sealed consumer catalog;
transition's pre76 readiness checks IDs but not advertised context/snapshot.
Latvian7680 pins/preflight are clean but its consumer needs an external model/
context health gate. No frozen modules changed or existing roots repinned.
Commands, mock receipt and owner follow-ups:
`docs/reports/dfm13_31b_launch_dryrun_20261003.md`. Do not treat mocked readiness
or successful CPU preflight as live inference or semantic approval.

### Balanced fresh 31B CPU calibration, 2026-10-03

**Successor execution update:** input root
`data/dfm13/gemma31-balanced-calibration-20261003-v4` and execution root
`data/dfm13/gemma31-balanced-execution-20261003-v2` supersede the launchability
of balanced v2/v3 and execution v1. Shared endpoint/production changes required
new roots, not repinning old artifacts. All234 specifications and generation
requests remain exactly equal to balanced v2. The runner now exists:

```bash
python -m dfm12.wave31_balanced_run verify \
  --root data/dfm13/gemma31-balanced-execution-20261003-v2
# Future authorized execution only; not launched by CPU preparation:
python -m dfm12.wave31_balanced_run run \
  --root data/dfm13/gemma31-balanced-execution-20261003-v2 \
  --concurrency-per-server 2
```

It reuses the existing fresh lifecycle through private globals and production's
strict first/second audits; resume rechecks frozen generation bindings and raw
audit evidence before counting a keep. The shared endpoint validator enforces
exact31B identity, absolute verified snapshot and32K context. Wave4 and Baltic
run sequentially; interrupted/drained work does not advance to the next wave.
No export or production approval is produced.28focused tests pass. The final
CPU receipt is `docs/reports/dfm13_balanced234_execution_preflight_20261003.json`;
root matrix/commands are in
`docs/reports/dfm13_balanced234_execution_handoff_20261003.md`. No GPU calls.

Final read-only successor recheck passed against Tesla's frozen matrix and all
four companion comparison/production roots:
`docs/reports/dfm13_balanced234_final_matrix_recheck_20261003.json`. The matrix's
old balanced-root entries were explicitly superseded with source-v4/execution-v2.
CPU execution readiness does not authorize interruption of the still-active26B
queue or bypass the transition owner's resource/drain gate.

Prepared and verified `data/dfm13/gemma31-balanced-calibration-20261003-v2`:
**234 cases, exactly three per each of 13 languages x six families (78 groups)**.
Wave-four contributes 198; Lithuanian/Latvian contribute 36. The earlier 30+12
matched comparisons remain separate and exposed; they were not replaced or
counted as fresh balanced coverage. Neither set authorizes production alone.

`dfm12.wave31_balanced_calibration` uses the existing wave providers, pinned
seed inventories, production31B configuration/controller, generation requests
and compact transport. Historical specifications are read without reviewer
verdicts. The frozen exclusion snapshot covers known local calibration and
production allocations, source IDs/text/messages, exact references and tool
scenarios; it is not a claim of global pretraining novelty. Existing seed pools
and allocation ledgers are untouched. Each group retains its three-case quota.

The first v1 preparation is preserved but superseded: a stricter post-check
found 11 reused code references despite different allocation labels. V2 excludes
these reference duplicates before selection; the subsequent check found zero
prior reference/scenario overlaps. No model calls or answers were produced in
either preparation. V1 implementation pins were not refreshed for resume.

Actual pinned Gemma4-31B tokenizer preflight passed all full generation prompts
with output reserve: wave4 maximum 5,936 tokens; Baltic maximum 5,738, against
32,768. The native student renderer/template smoke passed and its assets are
pinned. Actual generated-message/tool rendering (4096-token student limit) and
full-candidate reviewer context checks remain pending generation; no answer was
fabricated to claim those checks. No Mistral regex fix was added.

Family balance does not imply full subtype coverage: only four of the 39
math-code cases use code because exposed fixed references were excluded.
Detailed subtype counts and exclusions:
`docs/reports/dfm13_31b_balanced_calibration_20261003.json`. Three cases per group
are bounded diagnostics, not statistical quality certification. Independent
full-source semantic review and all-group evidence remain required; production,
admission and publication approval flags are false. This module provides CPU
prepare/verify only; GPU execution and production approval are not armed.

```bash
python -m dfm12.wave31_balanced_calibration verify \
  --root data/dfm13/gemma31-balanced-calibration-20261003-v2
```

Prepare refuses existing roots. Source/config/implementation, exclusion
snapshots, requests, budgets, student assets and actual31B tokenizer assets are
hash-bound. New/production/fresh-comparison tests: **17 passed**. No GPU calls
or server changes occurred.

### Fresh42 pin refresh completed

Later2026-10-03, the user relayed Epicurus's stable transition confirmation;
`data/dfm13/wave4/transition-frozen.json` records that provenance, not launch
approval. CPU waiter2394992 completed and exited. The successor status is
`phase=ready`: independent verification passes30 cases at
`data/dfm13/wave4/gemma31-fresh-comparison30-v4` and12 at
`data/dfm13/baltic/gemma31-fresh-comparison12-v2`. All original specifications and
requests match exactly; actual31B maximum prompt plus reserve is5850/5505 tokens.
Both production-v2 roots verify, preserving770000/140000 targets without
production approval. No GPU calls or server changes. Explicitly pass these
current roots; the runner's historical default is not the successor.

The following pending-freeze account is superseded by that completion:

Transition closing fix invalidated fresh30-v3/Balticfresh12 pins; originals remain
preserved and must not be repinned. Epicurus owns transition edits. CPU-only
waiter2394992 waits at most30minutes for `wave4/transition-frozen.json`, then
prepares fresh30-v4/Balticfresh12-v2 with exact prompt equality, actual31B tokenizer
preflight and fresh pin verification. `data/dfm13/wave4/fresh42-successor-status.json`
is authoritative; until ready, these successor roots are not launchable. Both
production-v2 roots verified cleanly, no approval generated.24focused tests pass.
No server/client actions; Poincare's234unexposed cases untouched. Details and
current-root instructions are in the31B handoff report.

### Full-target31B successor support, unapproved

**Capacity update, later2026-10-03:**8sequences/server and4aggregate requests/server
were comparison/bootstrap settings, not permanent production limits. New measured
capacity profiles allow up to64aggregate requests/server with explicit wave
allocations after pinned all-eight31B stability/throughput measurements. Current
unapproved roots are `synthetic31-full-staged-v2`; v1 preserved/superseded. No
profile, production approval or GPU change fabricated. CPU LB study scanned62,414
documents: zero new eligible documents,5,538proposed non-overlapping additional
windows from existing documents,12,479short documents still excluded. No pool
appends or target cuts. Details: `docs/reports/dfm13_31b_capacity_and_lb_supply_20261003.md`.

`dfm12.wave31_production` prepared separate wave4/Baltic
`synthetic31-full-staged-v1` roots:770K+140K=910K targets,78groups,70K per each
of13languages. No target cuts, no26B imports, all historical holds preserved.
Private model adapters reuse existing quota/dedup/recovery/source/renderer paths;
first strict keep requires a second blind-context source/native review before
quota credit. Same31B second request is not human/native certification. No
comparison-reviewed approval files exist, so launch is blocked. Dynamic CPU
request preflight passed42specs with actual31B tokenizer; noGPUcalls. Finite
source exhaustion exits blocked with original targets intact, not repeated seeds.
LB34,013seeds is the narrowest native supply; full20Kgrounded target depends on
yield/additional approved sources. Full recipe, source limits, lineage and gates:
`docs/reports/dfm13_31b_full_production_recipe_20261003.md`.

### Read-only handoff readiness, 2026-10-03

Snapshot15:30:19Z: wave4 source audits3,611,550pending/3,128running; repair
generation18,421pending/257running, with future re-audits still possible. Parallel
producer2103630/2103633 and eight workers remain active; final direct/institutional/
pivot marker missing. Monitor2111503 can respawn clients and must be included in
the eventual exact-identity producer freeze. Baltic audit/repair/privacy queues
are terminal, and synthetic2192702 has exited/drained with active0. Its automated
keeps remain quality-held.31B weights and42fresh prompts are prepared, but GPU
handoff is NOT ready. Exact queue snapshots/process identities and CPU/selection
blockers: `data/dfm13/wave4/handoff-readiness-20261003.json` and
`docs/reports/dfm13_31b_readiness_20261003.md`. Servers untouched; no actions armed.

### Stronger-teacher handoff prepared (2026-10-03)

Stop further speculative26B prompt variants. New isolated
`dfm12.wave4_gemma31_transition` provides read-only inspection, explicit readiness
checks and a gated post-drain31B switch, reusing the existing eight-server
launcher/environment and exact supervisor identity. No process actions executed.
The actual `gemma31-quality-comparison` root has76 hash-verified review jobs,
not fresh generation jobs. Missing local31B weights and active source CPU/audit/
repair/Baltic synthetic consumers currently block transition. Require complete
CPU receipts, frozen producers, all queues terminal and all clients exited
before releasing supervisor1856648. Eight31B endpoints must advertise only31B;
client concurrency8/server, no automatic production approval. Detailed contract,
commands, recovery limits and next full-target comparison step:
`docs/reports/dfm13_wave4_gemma31_handoff_20261003.md`.

**Weight blocker superseded later2026-10-03:** authorized CPU downloadPID2320976
completed and exited, revision `842da3794eaa0b77d5f08bae87a17459d91ff475`.
All12 files/62,578,686,256bytes verified against upstream LFS SHA256 or git blob
hashes; atomic `data/dfm13/wave4/gemma31-download/ready.json` records exact snapshot
and local hashes. Authenticated payload access succeeded; no duplicate download.
Source/repair drain remains required; no servers stopped or GPU requests made.

New isolated `dfm12.wave4_gemma31_fresh` prepared30 matched full generation jobs
at `data/dfm13/wave4/gemma31-fresh-comparison30-v3`:14 weak cases,16controls, all11
languages/sixfamilies. Original prompts unchanged except teacher model, no new
26B suffix. Actual31B tokenizer preflight30/30, max5850prompt+reserve tokens,
no truncation. Strict automated review plus separate hash-bound independent
semantic-review queue; no production/publication approval. Eight focused tests
pass. Commands and receipts are in the handoff report above.
The unlaunched earlier30/v2 roots are superseded, preserved, and must not be
repinned/resumed. Separate `data/dfm13/baltic/gemma31-fresh-comparison12` adds all
six families for LT/LV; failed prior generations retain null baseline candidates
and original status. Run the two comparisons sequentially after the drain and
31B startup, not alongside the76-job client at its8/server limit. No target cuts.

### Isolated literal-preservation comparison (2026-10-03)

`dfm12.wave4_literal_probe` completed18 cases at
`data/dfm13/wave4/literal-preservation-probe-20261003-v2`, PID2255174,
two concurrent requests per existing8800..8807 server; no server restart or live
campaign changes. Four comparatively good controls plus14 exposed failures.
Original specs/source pins and all complete targets retained. Three tests pass.
The initial root failed CPU preparation before model requests and is preserved.

Generation suffix emphasizes complete task input, literal source relationships,
native prose and exact dates/function outputs. Script-contamination sidecars
are diagnostic only, exempting code/URLs/source quotations. Automated result:
11keeps,6rejects,1invalid review. Independent reading of all18 finds only three
of11 keeps without a clear material issue in this sample. Some local repairs
work (SK extraction, LB source subject), but native prose and false accepts
persist; HU summary gains new unsupported decades of research and a BE control
regresses. Do not promote this variant or infer heldout improvement. Full case
comparisons and caveats: `docs/reports/dfm13_wave4_literal_probe_20261003.md`.

### Independent accepted-wave4 reading (2026-10-03)

CPU-only review of `production-probe-expanded-keepalive` read42 effective keeps:
three families per language across all11 languages, plus five BE and four LB
extras. Reproducible slot-based selection, full candidate filenames and individual
source/reference findings are in
`docs/reports/dfm13_wave4_accepted_independent42_20261003.md`.
No candidates, code, outcomes, workers or GPU state were changed.

Strong accepted false positives block blanket native-quality confidence for
BE/LB/HU/SK/SL: foreign-script intrusions, source meaning changes, missing source
user input and unrelated scenario substitution. BE/LB copied extractions can be
good while generated prose/tool descriptions fail. Correct code/arguments do not
validate surrounding language. The other six languages have a stronger but
small and correlated sample; native review remains required and no population
error rate or production approval is inferred. Findings distinguish definite
material defects from uncertain idiomatic judgments and source quality issues.

### Synthetic control repair experiment

`scripts.calibrate_wave_control_repairs` queues repairs for the five manually
flagged synthetic controls on existing shared clients. Only in this synthetic
experiment may generated user grammar be corrected; source facts, intent,
roles and system/tool context must remain intact. Corrected candidates receive
a fresh review without the defect description or repair rationale. Outputs are
explicitly pilot-only and never auto-published or counted toward language targets.
Even passing all five does not establish general reviewer calibration. Results:
`data/dfm13/wave4/control-repair-calibration/status.json`; log:
`logs/dfm13/wave4/control-repair-calibration.log`.

The five controls currently share the FIFO repair queue with FarsInstruct and
may wait behind its larger summary backlog; the repair client was verified live
and progressing, not stuck. A purposive spot check of two rejected `pn_sum`
examples found an unsupported event result and an overly brief target relative
to an explicit comprehensive-summary prompt. This supports continuing grounded
repair/re-audit, not blanket acceptance based on source reputation. It is not an
estimate of the whole source's error rate.

Superseding the FIFO-only wait for these controls: `dfm12.european_stage` now
supports optional repeated `--job-id` arguments (up to 128). A targeted client
uses the same transactional leases but claims, expires and reports only those
jobs; the default bulk path is unchanged. This allows the five calibration
controls to run without waiting behind tens of thousands of repairs or resetting
them. Tests exercise competing bulk/control owners and refusal of wrong-owner
completion. The targeted generation client was launched against all eight shared
endpoints with only five eligible jobs.

The control repair experiment completed: four repaired conversations passed the
fresh automated review; Belarusian repair was declined. Manual inspection found
that Latvian's count was corrected to 33, but Luxembourgish still contained
`Nein` and `Ursprünglech` while its reviewer assigned 5/5 to language quality.
Thus same-model repair plus a fresh review does not solve the known language
false-accept issue. These five rows remain pilot-only. The prepared stronger-model
comparison remains necessary before approving general synthetic production;
source auditing/publication can continue independently.

### Native synthetic seed allocation

Wave 4 explicitly enables `source_reuse_by_family`: a native text may ground
different task families, but cannot be selected twice within the same family.
This corrects the earlier global uniqueness assumption: Luxembourgish has about
34K native seeds against 45K source-grounded accepted targets across families.
Selection receipts still preserve source identity and immutable per-slot specs.
The policy is fingerprinted; existing selection roots cannot silently change it.
Earlier campaigns retain their default global uniqueness. This removes the
cross-family allocation bottleneck, not the language-review quality gate or a
guarantee that each family has sufficient accepted yield.

### Expanded production-path calibration

On 2026-10-03, `dfm12.wave_production_probe --per-family 10` started a balanced
120-case Baltic and 660-case wave-four probe on the existing eight shared
servers, with eight concurrent requests per endpoint per probe. It now uses
bounded keep-alive connections like the production client rather than the
earlier probe-only `force_close=True` transport. Existing bulk audits and repairs
were not interrupted. Results are isolated under each wave's
`production-probe-expanded-keepalive`; they do not authorize or enter training.
The Baltic probe completed with 72 effective keeps, 31 valid rejections, eight
invalid generations and nine invalid reviews. Independent content review is
still required before interpreting keeps as acceptable training quality.

The wave-four probe also completed: 461 effective keeps, 129 valid rejections,
37 invalid generations and 33 invalid reviews out of 660. Neither probe had
transport-failure outcomes with the production keep-alive settings. This does
not clear the remaining semantic-quality checks.

## Staged Family Admission

The controller now supports explicit approved language/family groups without
changing any targets. A hash-bound calibration receipt names those groups and
its evidence files. Deferred groups remain in the ledger and are never reported
as completed; the default legacy controller remains unrestricted unless this
option is supplied. Tests cover reservations, deferral, target preservation and
later admission of another group.

Independent inspection of all 32 accepted Baltic grounded/tool cases supported
a staged start for Latvian grounded-instruct. The nine accepted calibration
examples were source-faithful with minor language/format blemishes. On 2026-10-03,
`data/dfm13/baltic/synthetic-production-staged-v3` began the 20K accepted target
for that group, using all eight shared endpoints at 16 concurrent conversations
per server alongside audits/repairs. The other 120K Baltic targets remain pending.
The first 500+ production examples have passed automated gates; a fresh content
sample is required before publication. This is not native-speaker certification.
The decision is recorded in `data/dfm13/baltic/grounded-production-review.md`.

The wider review found substantial long-form language errors and false accepts,
including a wrong Latvian matrix example, invalid action intent in a tool
conversation, and missing source-user input. For wave four, the independent
42-case report is `docs/reports/dfm13_wave4_accepted_independent42_20261003.md`.
Those results do not authorize blanket synthetic production. Source-transform
and translation auditing/publication continue independently.

Fresh staged-production inspection read 20 evenly spaced accepted rows among
the first 500 Latvian grounded examples. It found two clear source-fidelity
errors, one borderline inference with damaged wording, and two language-repair
cases. Fifteen had no clear material defect in that review. Generation continues,
but publication remains held; provisional automated keeps do not count as final
release acceptance. The five exact job IDs and required work are recorded in
`synthetic-production-staged-v3/independent-review-holds.json`. Final rejections
must be replaced before claiming the accepted target is met.

## 31B Operational Handoff Correction

Later2026-10-03 documentation review supersedes the old launch-dryrun missing
endpoint/balanced/P3 execution claims without erasing historical test results.
Current roots and ordered commands are linked in
`docs/reports/dfm13_31b_operational_handoff_20261003.md`. Article-aware QA v3 roots
are now sealed and pin-verified: diagnostic20 fits; bulk retains497 explicit
context holds among118866 rows. No semantic approval is implied.
Production clients accept measured profiles on staged-v3 roots, but the only
existing31B server CLI still forces comparison max-seqs8. A new isolated owned
production/ramp launcher is proposed, not implemented; emitting capacity JSON
does not apply settings. No frozen code or GPU process changed in this review.

**Resolved subsequently2026-10-03:** `dfm12.wave31_server_lifecycle` now provides
an isolated executable ramp/production launcher. Ramp permits sequences16/32/64/128;
production requires the validated measured profile. Both require a fresh root,
free devices/ports, sole verified31B snapshot and strict all-eight readiness.
Actual argv, logs, ownership, sequence settings and metrics URLs are recorded;
exact-owned cleanup never authorizes a reused session ID alone. No frozen
transition/production dependency changed and no GPU launch was performed.
Epicurus's measurement driver remains separate; CLI/receipt contract:
`docs/reports/dfm13_31b_server_lifecycle_handoff_20261003.md`.

## Independent 31B Content Review (2026-10-03)

`docs/reports/dfm13_wave4_fresh31b30_independent_20261003.md` examines all 30
fresh comparison specifications/outcomes, 23 candidates, seven invalid raw
generations and all prior 26B pairs. All 134 input pins verified. Seven invalid
outputs are source-copy `user.maxLength=900` failures, not seven demonstrated
semantic failures. Their hypothetical complete duplicated-source targets render
to 687-2213 student tokens, below 4096. Balanced-v2 uses the same instruction,
schema and JSON-object response mode, so this is not merely a historical-request
artifact. The report proposes a separately versioned source/instruction adapter
with exact-copy safeguards and full student-budget validation; no frozen code
or schema changed. Long-form language failures and false automated keeps remain.

The follow-up report
`docs/reports/dfm13_wave4_balanced31b_grounded_summary_multiturn50_20261003.md`
and hash-bound JSON companion independently assess every one of the 50 automated
keeps in those three wave-four families. Other families and Baltic remain separate
review assignments. Concrete issues include fabricated library/transport rules,
external-action promises without tools, source defects, malformed prompts and
localized language errors. Source-faithful short answers are not blanket approval
of the entire conversation. These reports neither certify native proficiency nor
authorize admission, launch, publication or target changes; all work was CPU-only.

### Source/Instruction Successor Prepared

`dfm12.wave31_source_instruction_adapter` now implements the narrow successor
without editing frozen generation modules. New outputs use instruction<=900 and
assistant<=2400; CPU retains the complete pinned source in the training user turn.
The assembled untrimmed target and masks must pass the existing 4096-token check.
Incomplete generation, malformed/duplicate-key JSON and uncertain source echoes
fail closed. No global unescaping or truncation is performed.

Legacy recovery recognizes only the complete pinned source verbatim or its exact
JSON serialization (one/two escaping layers). Only that matched span is restored;
literal code/backslashes within the canonical source and all other text remain
unchanged. Changed/partial copies are not guessed. Three of seven historical
failures recover on CPU for inspection: hu276f1583e9fd (1278 tokens),
hr6d45c707a298 (371), bg6f7c4e6140f4 (651). Four remain uncertain holds. Semantic
review remains required even for structurally recovered rows.

Authoritative prepared rerun root:
`data/dfm13/wave4/gemma31-source-instruction-rerun7-v2`. Seven new requests,
parent/implementation/tokenizer pins, exact-echo classification and inspection
outputs are sealed. The earlier v1 root is a preserved CPU draft superseded by
v2, which adds finish-reason enforcement and inspection-output pins; do not run
v1. Fourteen tests cover preservation, source duplication, escaping, literal
code, field bounds, 4096 overflow, route isolation and incomplete output. Caller
must use successor `decode(spec, content, finish_reason)` then independent review,
not legacy v4 decoding. No GPU request or production admission occurred.

Model-selection clarification: 31B comparison does not authorize replacing the
26B bulk teacher. `dfm12.source_instruction_adapter` now exposes the same CPU
schema/assembly/decode behavior with explicit model selection, defaulting to
`google/gemma-4-26B-A4B-it`. The historically named wave31 implementation remains
unchanged so previous sealed bundles retain valid pins. New prepared root
`data/dfm13/wave4/source-instruction-rerun7-26b-v1` contains seven 26B requests;
31B is only an explicit optional identifier, not an approved bulk choice. Model
and endpoint/tokenizer preflight is required at execution time. Nineteen tests
passed across model-selection and source-preservation suites. No inference was
launched and no prior artifact was overwritten.

The user subsequently authorized only the bounded source7 generation/review on
26B once Epicurus confirms readiness. `dfm12.source_instruction_probe` reuses
the production `Stages`, raw-response writer, stream transport and indexed
reviewer, with successor decode replacing only legacy source-field assembly.
It requires exact26B/32K endpoints and keeps admission false. Prepared execution
root: `data/dfm13/wave4/source-instruction-execution7-26b-v1`. Twenty-two tests
passed; actual26B generation budgets are 5007-5642 tokens including reserve.
At preparation, `logs/dfm13/gemma26-compiled-switchback-20261003-v1/status.json`
still reported starting; no request was sent before readiness. Automated review
will be followed by independent whole-case inspection, not treated as approval.

Launch supersession: the seven-case26B run completed on2026-10-03. See
[source7 outcomes and independent review](dfm13-source7-26b.md); no admission.
