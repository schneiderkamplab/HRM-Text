# Slovak approved-supply gap and isolated addition

The original mesh has33 empty Slovak edges:32 non-English pairs plus en-sk.
This is a narrow named-release approval gap, not proof that Slovak corpora do not
exist. Existing institutional review reuses only corpus/version names in the
old DFM12 allowlist; it does not automatically approve different numbered EMEA
or Slovak ministry releases. No live gate or inventory was relaxed.

## Primary license evidence

Pinned OPUS repository revision42d4fbe382245487a68e853ca53bea832a41a02a. Both
parent and release YAML were downloaded and retained under the additive evidence
directory. Named releases:

| Release | License metadata | Upstream Moses pairs |
| --- | --- | ---: |
| ELRC-487-Culture_Slovak v1 | public domain | 2610 |
| ELRC-488-Justice_Slovak v1 | public domain | 2896 |
| ELRC-2721-EMEA v1 | CC-BY-4.0 | 780098 |

Primary release metadata:
[Culture](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/ELRC-487-Culture_Slovak/v1/info.yaml),
[Justice](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/ELRC-488-Justice_Slovak/v1/info.yaml),
[EMEA](https://raw.githubusercontent.com/Helsinki-NLP/OPUS/42d4fbe382245487a68e853ca53bea832a41a02a/corpus/ELRC-2721-EMEA/v1/info.yaml).
Parent descriptions identify Slovak ministry prose and EMA PDF translations.
The generic ELRC-EMEA license conflict is NOT used to approve these by analogy;
numbered2721 has matching parent/release CC-BY evidence independently.

Downloaded ZIP READMEs agree: publicDomain for both ministries and CC-BY-4.0
for2721. ZIP LICENSE files contain OPUS's redistribution disclaimer and direct
readers to corpus metadata, not a new blanket license. Upstream original ELRC
landing page was inaccessible through the browser tool; that limitation remains
explicit. Attribution retains provider links, original README and OPUS citation.
License eligibility is for candidate preparation only, not legal/native-quality
certification. DGT/Europarl/JRC-Acquis were NOT newly approved or substituted.

## Actual isolated CPU work

Root: `data/dfm13/wave4/slovak-additive-20261003-v1`.
Script: `scripts/prepare_wave4_slovak_additive.py`.
Detached PID2460511, log `logs/dfm13/wave4/slovak-additive-v1.log`.
CUDA_VISIBLE_DEVICES empty; one tokenizer/OMP thread; no GPU/model calls.
No matching selected archives existed in checked old download caches, so three
official archives were downloaded:208292,238291,58665588 bytes. No gated access.

The existing OPUS converter supplies exact pair deduplication, structural gates,
native student-template rendering/4096 limit, both directions and per-row
attribution. Candidate conversion is running; upstream785604 raw alignments are
NOT claimed as output or accepted counts. All32 non-English Slovak pivots then
use the same exact-English/ambiguity guard against immutable existing English
legs referenced read-only in this separate root. Actual overlap/quality may be
insufficient; do not promise all pair quotas merely from a large English corpus.

Two license/version/pair fail-closed tests pass. No old approval list, inventory,
candidate, frozen pivot manifest, active audit DB or31B implementation changed.
Future integration.json assigns NEW component names `sk-additive-v1-direct-en-sk`
and `sk-additive-v1-pivot-*`, with hashes, evidence and explicit audit/native-audit-
preflight required. It does not enqueue or accept automatically. Existing combined
pair budgets must apply across old+new accepted versions, without double-counting
or repetition inflation. Existing final-selection manifests must not be repinned.

Concrete next action after CPU completion: inspect all33 pair yields and sampled
alignment/PDF artifacts, run native audit preflight, then schedule dedicated
versioned audit components through the owner after the server handoff. Holds and
benchmark/duplicate screening remain applicable; never fabricate missing pairs.

## Authorized automatic continuation

User subsequently authorized continuation through preflight, audit enqueue,
combined accepted-only selection/export/integration. Detached watcher2465638:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.advance_wave4_slovak_additive \
  --root data/dfm13/wave4/slovak-additive-20261003-v1
```

Log `logs/dfm13/wave4/slovak-additive-advance-v1.log`; shared handoff inventory
**`data/dfm13/wave4/slovak-additive-handoff.json`**. Source preparer2460511 remains
active. The watcher is currently waiting_cpu_integration, not already queued.
Parent/assembly MUST include this separate producer/receipt and both existing
audit and repair queues in final drain inventory. Main wave4 parallel-preparation
completion does NOT imply this additive is finished. Both completion booleans
remain false until actual work satisfies them; no synthetic completion receipt.

After candidate integration appears, the watcher verifies source/evidence hashes
and calls the existing native audit preflight/enqueue for NEW sk-additive-v1-*
components on the existing main audit DB. It does not start servers/clients.
After the original main preparation marker, it freezes a SEPARATE combined audit
manifest including any old direct/institutional/pivot SK components plus new ones.
It does not alter the old main manifest or candidate inputs. Names intentionally
do not impersonate old components or silently enter an old frozen selector.

Each pair uses one original baseline token cap across old and new direct/pivot
rows, exact target-pair dedup and direct preference through PairSelection. It
processes source audit/technical recovery via existing wave_repair and requires
every component export_ready; technical failures cannot become silent acceptance.
No-ready/no-accepted supply is reported separately and targets are not inflated
or cut. Existing accepted-only translation release produces both directions,
validates rendered counts/masks and licenses, bundles attribution, uploads and
verifies remote bytes before canonical registry integration. Shared pair cap
prevents additive budget doubling; canonical pair entry replaces rather than
duplicates an earlier combined entry, if one exists.

**Superseded by publication-collision review:** automatic replacement described
above is now forbidden. Main and additive per-root release locks do not provide
mutual exclusion for their shared canonical export path. Read-only inspection
found zero main SK components, zero main SK selection receipts and zero canonical
SK exports. Before each new publication, publication_guard requires the frozen
main manifest to match its preparation marker, rejects additive prefixes in that
manifest, and rejects any nonzero main pair component/selection or main publication.
It also refuses an existing canonical export directory or registry entry, preserving
all existing files/arrays. Replacement or incomplete prior publication requires
explicit coordinated recovery rather than blind overwrite. An absent main freeze
blocks publication. The main selector's direct/institutional/pivot prefixes exclude
sk-additive-v1-*; the separate combined selector explicitly includes them once.

Watcher2465638 was verified waiting with no requests, then alone stopped/restarted
to load this guard. Current watcher2470642, log
`logs/dfm13/wave4/slovak-additive-advance-v2.log`. Source CPU2460511 unchanged;
no GPUs/audit clients touched. Restart evidence is publisher-guard-restart.json
inside the additive root. Ten focused tests pass, including main nonzero supply,
nonzero selection, prior export/registry preservation and additive-prefix rejection.

## Parallel native preflight, later2026-10-03

Completed additive input contains1910015 pairs across30 nonempty components:
en-sk784241, nl-sk559463, sk-sv566038 dominate. Serial preflight measured74432
rows in about149seconds (~500/sec), roughly64minutes for all1.91M if unchanged.
User authorized16 CPU workers; no servers/model clients changed.

Before stopping exact watcher2470642, inspection confirmed no whole component
registered and no sealed whole preflight receipt, therefore no partial whole-job
enqueue was possible in that API sequence. Temp artifacts remain preserved.
After process exit, the advance lock briefly remained busy; launch waited for
release rather than overlapping. Current detached watcher2475044 uses16 spawned
CPU processes,32 outstanding futures maximum and one enqueue writer. Log:
`logs/dfm13/wave4/slovak-additive-advance-v3.log`.

`scripts/slovak_chunked_preflight.py` reuses baltic_audit.preflight and existing
enqueue. Deterministic5000-row parts have stable original-component-partNNNNN
names, source hashes and exact row-count receipts. Resume preserves sealed parts.
A sealed whole component takes the old whole path rather than creating duplicate
part audits. No extra per-part budget: route_pair removes part suffix, so existing
combined old/new pair dedup, cap and fail-closed publisher checks remain unchanged.

Actual initial verification:33 part preflights completed;2 parts/10000 ready rows
registered in the live audit queue. Enqueue throughput is distinct from CPU
preflight throughput and may wait on the shared queue lock. Thirteen focused
tests pass, including stable chunk resume, exact row coverage and preservation
of an existing whole-component population. Shared handoff file now reports the
parallel stage and queued part names. Main completion never covers this addition.

Drain planning must include up to1.91M additional audited pairs (preflight may
reject some), not just the earlier main backlog. At17K..29K requests/min that is
roughly66..112 additional minutes before retries/workload effects; this is not a
guaranteed ETA and cannot be hidden by main source completion.

## Fair CPU enqueue handoff

### Post-fix operational verification

#### Upload quota cannot block recovery

Final ledger-drain correction and evidence:after the first recovery-first pass,
100 ledgers still had560 audit_retry_pending rows while all linked jobs were
already terminal (450done/110failed). A single pass followed by expensive
accepted selection was insufficient. Caller now loops actual process() status
reconciliation before selection, writing recovery-drain.json only when every
component status is genuinely terminal. It preserves failed/excluded outcomes
and explicitly sets admission_authorized=false, publication_complete=false.
Exact owned2638570 received SIGINT for finally cleanup; exit/ownership lock
verified before2642708 resumed v8. No concurrent writer or GPU action.

At1791058184 independently verified410/410 terminal statuses and exact status
hashes/input pins against recovery-drain.json. Row totals1380829accepted,
528813rejected,373excluded_unreviewed sum1910015. Source queue10739087done/
19364failed, recovery52023done/4241failed; neither has pending/running jobs.
Generation83547done/58failed/10659explicitlydeferred31B. Thus this source's
GPU-producing ledger tail is drained, independently of CPU accepted selection
and pending uploads. This is not blanket admission or publication completion.
21 tests pass, including withholding the receipt until real terminal states.
Main confirms it launched2639505 via the existing monitor helper; that supersedes
the earlier inference that the monitor loop itself initiated the restart.

Original2542233 exited naturally on repository creation429/300perday during
release. No kill was needed. Narrow caller changes add --defer-uploads and resume
verified enqueue-complete registrations without repeating preflight/enqueue.
Publication holds are written explicitly in root/per-pair upload-deferred.json.
Exact quota errors are caught for future runs; other failures still propagate.
When all reviews finish, audit-finalization.json can be written with
publication_complete=false, but completion.json is never written for held uploads.
This preserves unfinished upload obligations instead of declaring the goal done.

Resumed2635437 with uploads deferred. Inspection showed pair selection still
interleaved accepted-row copying before reaching unmaterialized sk-sv ledgers.
Added caller-only --recovery-first: skip terminal pinned component statuses,
process missing ledgers first, then nonterminal ones under existing component
locks, before any accepted PairSelection work. After20 passing focused tests,
exact pidfd SIGINT to owned2635437 ran existing finally cleanup/SQLite rollback;
verified exit and free advance.lock before successor2638570. No simultaneous
owner, source resets, GPU/server signals or shared/frozen module edits.

Evidence:recovery-priority-handoff.json; log
logs/dfm13/wave4/slovak-additive-advance-v7.log. Priority pass115/115 completed;
all410 component ledgers exist,310 terminal/100 nonterminal at snapshot. The
existing monitor2111503 restarted drained recovery client2639505 with its
unchanged32-per-endpoint setting. Actual completed recovery audits rose
51526->52020, failed4123->4212,32running at snapshot. These are actual newly
processed jobs, not just enqueued intentions. No competing client was launched
manually.100 nonterminal ledger statuses still require reconciliation; uploaded
and audit-drained readiness are not inferred from temporary empty queues.

#### Portuguese cards resolved, publisher ownership preserved

The observed pt_pt card rejection is superseded for lb-pt_pt and pt_pt-sq.
The publisher module already contained card_languages normalization from prior
work:ISO pt plus language_bcp47 pt-PT. The live process had old imported code.
No overlapping publisher-module edit/controller restart was made. Added focused
tests for both affected pair orders;5 tests pass including existing release tests.

Retried only these pairs through existing release(), pair locks, native token
checks and remote data/attribution verification. Pinned original train.jsonl
hashes were required unchanged immediately before upload and verified afterward;
all row language/provenance variants remain pt_pt. Publisher regenerated
byte-identical payloads; no training rows/content changed. Remote README hashes
and parsed pt/pt-PT metadata also verified at the uploaded revisions:

- lb-pt_pt:92rows,revision eef5776db55669e4f5e49b5223f58872a8051eb2.
- pt_pt-sq:578rows,revision63bdfda2eea33a5b1a4eb1705dd048ea40a7d6fd.

Before/result evidence lives under wave4/portuguese-card-retry-20261003.
First create_repo call received429 daily repository-creation limit (300/day).
Authenticated repo_info confirmed both existing repos; the scoped retry skipped
unnecessary creation and updated only those repos. No gate or rate limit was
bypassed and no new repositories requested on the successful retry. Existing
registry/publication receipts were completed by the normal publisher API.

Ownership handoff for Poincare: no source edits or live controller replacement;
successful publication receipts make the live publisher skip these two pairs.
Other future Portuguese pairs may still require the owner's next safe idle code
refresh. Daily new-repository creation remains a separate service restriction.

#### Successful handoff and completed CPU preparation

Follow-up1791056724..1791056792 reverified the exact410 combined component set,
all registered hashes, integration pin and main-preparation pin. Parallel selector
completed its second full pass:240ready,35awaiting,33no-supply,0inflight/errors.
It is in its normal600second interval; no competing controller added.

Remaining GPU producers are the existing main/additive ledger finalizers:
failed first-pass rows enqueue bounded recovery audits. Slovak167/410 component
ledgers cover784349 rows;46 component status receipts advanced in140seconds.
Unvisited243-component tail is about12minutes at that recent rate, an inference
subject to disk contention/component mix, not guaranteed drain ETA. Its1057
audit_retry_pending ledger statuses are not a live queue count: recovery results
can finish before the next ledger reconciliation. Live recovery snapshot shortly
afterward:50978done/3991failed/78running,0pending. Source audit snapshot:
10485548done/18908failed/250793pending/3202running. Do not switch teachers merely
because a transient recovery queue is empty while these producers are active.

Transform finalizer status:11 uploaded/integrated components. Instruction status:
15 uploaded/integrated,1 empty,2 fidelity holds.10659 generation jobs are explicitly
deferred31B, not live26B generation work. Drain needs source pending/running zero,
finalizer catch-up after terminal source results, and recovery pending/running
zero after producers have reconciled; failed/held/deferred outcomes remain
explicit and never become accepted through drain. CPU uploads can remain a
separate completion condition.

Observed publication-only blocker in publisher status:lb-pt_pt and pt_pt-sq HF
README language metadata rejects literal pt_pt. This is separate from GPU drain;
no exporter edits or retries performed in this inspection. Publisher remains live.

Third authorized idle watch found the real boundary at1791055717. Old2143812
had written all308 requested pair outcomes at1791055708, was sleeping, and had
no active pair/component locks. Exact identity plus pidfd revalidation preceded
SIGTERM; old process exited, controller lock was released. New2607843 owns the
same controller plan with2 spawned workers2607863/2607866. Log:
`logs/dfm13/wave4/advance-selections-parallel2-1791055717.log`; exact proof and
command in `translation-release/parallel-handoff.json`. No GPU changes.

140second sample1791055777..1791055917:44->86 completed eligible pair outcomes,
0 reported errors;33 no-supply outcomes were static and excluded from the delta.
Slovak370->381 parts concurrently. Prior sequential sample15/140s was first-pass
work and is not directly comparable with this second pass; no causal speedup
claim. Subsequent main status240ready/34awaiting/33no-supply/1inflight.

At1791056314 verified all410 additive chunk component IDs exactly match enqueue
receipt and registrations, every chunk input/preflight seal hash matches, and
integration hash is unchanged.1910015 input and preflight-ready rows across410
parts. Combined manifest410additive components, main manifest416 with0additive.
`cpu-preparation-verified.json` records these checks. Completion watcher2520116
exited with both_cpu_complete=true but audits_complete=false. No handoff watcher
left running. Additive2542233 is actively selecting en-sk (part00021 observed);
its old phase label is not evidence of a block.

Read-only queue snapshot1791056347: source audit10264413done/18765failed/
471662pending/3611running. Recovery audit50038done/3669failed/169pending/258running;
generation83547done/58failed/10659deferred31B. CPU preparation is finished, but
audit/recovery drain and accepted-only finalization remain. No GPU release or
31B launch is authorized by the CPU verification receipt.

#### Optional bounded selection successor, not deployed

Second explicitly authorized900second watch1791054595..1791055498 ended
without idle eligibility. Previous watcher was confirmed absent before starting;
the second exited normally and no handoff watcher remained afterward. Selector
2143812 was still active on ro-sq, with264 pair receipts, while Slovak reached
351 queued parts. Same identity, no signal, no parallel launch, no GPU
concurrency change. This is observation-window expiry, not a controller failure.

User authorized2workers only at a verified full-pass idle boundary. Executed a
900second bounded watch1791053604..1791054505 with NEW
scripts/handoff_wave4_selector.py. Guard requires complete requested-pair status
written within120seconds, sleep wait channel, no open pair/component lock or
SQLite journal/candidate input, exact PID identity and pidfd revalidation.
No eligible boundary appeared:2143812 stayed active through el-* and en-*.
Receipt `translation-release/parallel-handoff.json` records
`no_idle_within_watch`, `signaled:false`. No successor or duplicate controller
launched; no active pair interrupted. During watch en-fa ledger processing
produced140 audit_retry_pending rows and Slovak advanced to297 parts.10 focused
guard/parallel tests pass. No post-handoff speedup comparison can be claimed.

Measured current sequential2143812 at Unix1791053225..1791053366:75->90
pair receipts out of308 requested, about44 CPU-seconds over140 wall-seconds.
Small pairs finish in fractions of a second; large bs-ro and bs-sq components
introduced roughly60second gaps. At the end it actively held bs-sr pair and
direct-bs-sr component locks. Slovak advanced204->215 queued parts concurrently.
This supports possible I/O-overlap benefit, not a measured4x speedup. Shared
filesystem/SQLite pressure may reduce benefit or slow prioritized Slovak work.

Prepared NEW `scripts/advance_wave4_selections_parallel.py`, leaving the live
controller and frozen31B modules untouched. It acquires the SAME exclusive
selection-advance.lock, uses1..4 spawned processes with at most that many
outstanding pairs, delegates unchanged select/process APIs and existing
pair/component locks, rejects duplicate ownership, and has one status writer.
SIGTERM to the new controller stops dispatch and drains active workers. Existing
controller cannot gain that handler retroactively. No duplicate owner launched.

After an independently verified idle boundary and terminal old controller ONLY:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.advance_wave4_selections_parallel \
  --root data/dfm13/wave4 --workers 4
```

Do not interrupt the currently active pair to deploy this. Safe handoff requires
old owner idle outside pair/component locks, exact identity revalidation, and
its release of the controller lock; otherwise leave it working. A second launch
while2143812 owns the lock fails before manifest/selection work. Five focused
tests cover bounded dispatch, duplicate rejection, drain, error preservation and
single-owner exclusion;27 related tests pass. No production speedup claimed yet.

Main CPU completed naturally at1791052208: exact coverage416 components,
6269371 rows,0 additions,226 pivots. Both parallel-preparation.json and
audit/component-job-coverage.json are present. Selector2143812 started its next
scheduled cycle, produced the frozen416-component manifest bound to the exact
preparation hash, and wrote pair receipts (32 at1791052469;31 pending,1 ready).
The frozen manifest excludes all additive components. Publisher2143813 remained
alive in its separate300second polling loop; no upload success inferred from
selector activation. Slovak2542233 resumed after lock release to130 registered
parts/650000 rows. All410 parts and the separate enqueue-complete receipt remain
required before additive CPU completion; no source-audit-drain readiness claimed.

#### Caller-local timeout recovery

Recovery actually executed at Unix1791051857, not merely armed: original2481015
exited naturally, and the v4 log ended in the precise enqueue-lock TimeoutError.
Watcher2520116 verified terminal state and started successor2542233 with
`--enqueue-wait-seconds 43200`. No process was signaled. Exact old/new identities,
command and log are preserved in `timeout-resume.json`. The old v3 KeyboardInterrupt
was not consulted. Main2448161 and the whole preparation chain were not rerun.
All113 registered additive parts remain; successor is alive in chunked preparation
and waiting for the shared lock. Main advanced to direct-hr-sq, totaling123 checked
components/5263032 rows/0 additions. Selector2143812 and publisher2143813 remain
alive waiting for the main completion receipt; no false-ready marker was written.

The prior1800-second timeout risk is now handled for successor runs without
changing shared IO, wave4_cpu, or frozen31B dependencies. The additive CLI accepts
`--enqueue-wait-seconds 43200` (default12hours). Local enqueue_with_wait retries
only `TimeoutError: Audit enqueue lock remained busy`, raised before Queue
construction/writes. Source drift, SQLite errors and unrelated timeouts propagate.
The deadline is checked between shared1800-second acquisition windows; it is not
a strict cancellation deadline for successful enqueue work.

Existing2481015 remains untouched. A detached exact-identity watcher2520116 runs:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m scripts.watch_wave4_cpu_completion \
  --contract data/dfm13/wave4/slovak-additive-20261003-v1/cpu-completion-watch-contract.json
```

Log: `logs/dfm13/wave4/cpu-completion-watch.log`. Contract pins the original
process and successor code. It performs NO signals. Only after the exact process
is terminal and its log ends with the precise timeout may it launch one successor
with the local12hour wait; it probes advance.lock and never resets jobs. Successor
identity/log/command will be recorded in `timeout-resume.json`, with output at
`logs/dfm13/wave4/slovak-additive-advance-v5.log`. Unknown failures fail closed;
there is no repeated restart loop.

`cpu-completion-watch.json` separately records main preparation, exact coverage,
selection manifest binding, and additive enqueue completion. Watcher stops only
when those CPU boundaries are complete, NOT when audits or uploads are complete.
Existing additive release watcher remains responsible for its later lifecycle.
At1791050590 main had reconciled46 components/1427962 rows with0 new jobs, and
the original Slovak process was still alive waiting. Twenty-two focused tests
passed, including live-waiter non-restart and unrelated-failure rejection.

Subsequent requested 15-minute watch, Unix1791049313..1791050213:
all226 expected main pivots registered. Main entered exact_coverage at
1791050071 and actually progressed through direct-bg-el (25 components,
359748 rows,0 new jobs), proving lock acquisition and read-first execution.
The main preparation receipt and selection manifest remained absent at the end;
selection pickup is therefore not yet verified. Selection2143812 and
publisher2143813 remained alive and waiting. No false global-ready claim.

Slovak advanced81->113 registered/queued parts,127 preflight receipts sealed,
then waited on the enqueue lock held by reconciliation. All work is preserved.
The existing lock acquisition timeout is1800seconds: if reconciliation exceeds
that, inspect the additive watcher for its explicit timeout and resume its
existing parts after the lock is released; never reset jobs or fabricate its
completion marker. This is a remaining operational risk, not an observed failure.
Latest monitor:19721 requests/minute,91-100% GPU utilization. No process signals,
GPU changes, synthetic handoff, or code edits during this watch.

At Unix time1791048886, both producers remained alive and progressed without
further intervention. Main2448161 moved from pivot-hu-nb to pivot-hu-sl during
the check; additive2481015 moved from63 to64 queued parts, with95 sealed native
preflights of410 expected. Registration snapshot before the latter increment:
172 main pivot components/87400 rows;63 additive parts/315000 rows.

Shared audit snapshot:6732390 done,7440 failed,2390692 pending,3074 running.
Monitor time1791048780 reported29786 requests/minute aggregate and74-100%
GPU utilization. This is an instantaneous operational snapshot, not a drain ETA
or acceptance count. No queue-supply shortage is present.

Main selection2143812 and publisher2143813 remain alive. Main preparation and
translation-manifest markers are absent while enqueue/coverage continues;
additive enqueue-complete is likewise absent. These are expected release gates,
not permission to manufacture completion. Existing chains will freeze/select
after preparation and audit completion. Additive publication additionally proves
main cannot publish nonzero SK supply, and refuses any existing canonical export.
The three no-supply edges ca-sk, fo-sk and nn-sk remain genuine candidate gaps.
Fourteen chunking/selection tests passed again. No workers, servers, histories,
or frozen inputs were changed during this verification.

Main continuation2448161 was sleeping in its one-second enqueue-lock polling
loop at pivot-fa-nl while Slovak2475044 repeatedly completed5000-row parts. The
Slovak process had the enqueue-lock descriptor open; this filesystem did not
expose a usable kernel flock-owner record. No GPU-client backoff was introduced.

To refresh safely, the operator acquired the SAME enqueue lock exclusively,
revalidated2475044 identity, then sent SIGINT only while that exclusive lock
proved the producer could not hold a queue-write transaction. Pool preflights
finished and parent exited; no escalation or unknown-write SIGTERM. Evidence:
`fair-yield-restart.json` in the additive root. Main immediately advanced through
fa-nn/fa-pl/fa-pt_pt, supporting starvation as the practical cause.

Current watcher2481015, log `logs/dfm13/wave4/slovak-additive-advance-v4.log`.
It resumes all existing chunks/preflights/registrations without resetting jobs.
After each part, outside enqueue and transactions, a two-second yield occurs
ONLY if the exact pinned main identity remains in pivot_enqueue and its wait
channel is nanosleep. The main poll interval is one second, so this gives it
an acquisition opportunity without a new scheduler. Once main leaves that phase
or identity exits, no yield. Peer pin: enqueue-peer.json. Sixteen CPU workers and
bounded futures remain; fourteen chunk/selection tests pass. No audit/GPU changes.

Four focused tests pass, including old/new same-target dedup and a single cap
that fits only one of two eligible pairs. Native review, release correctness and
all existing controls remain inherited from the proven pipeline. Automatic
progress is recorded independently; no generation or server manipulation added.
