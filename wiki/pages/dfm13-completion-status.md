---
type: Runbook
title: DFM13 Completion Status
description: Finished additions, authoritative assembly promotion, and outstanding source work.
status: draft
confidence: high
last_updated: 2026-10-04
tags: [dfm13, datasets, integration]
---
# DFM13 Completion Status

## Authorized Exact150 Publication

**Complete:** all150 authorized repositories are uploaded, public and remotely
hash-verified:145 OPUS, four Baltic math/tool, one MATH. Eight Portuguese card
metadata corrections succeeded in the automatic second pass. Final receipts:

- `data/dfm13/upload-ready150-20261004-v2/completion.json`
- `data/dfm13/upload-ready150-20261004-v2/publication-receipts.json`
- `data/dfm13/upload-ready150-20261004-v2/final-verification.json`

The final independent check queried every exact commit and confirmed public
visibility, unchanged original source payload/card hashes, exact150-repository
membership and unchanged non-README upload hashes across both sealed queues.
No extra datasets, inherited DaLA repositories, training changes or central
registry rewrites occurred. The live finalization inventory consumes the sealed
publication overlay, so these repositories are no longer upload-pending.
Queue SHA256: `1363e1389645d895a5c1e92f2f5f37dda5c87d26f929e4b5182db4b7fde429a4`.
Receipt SHA256: `e225e78cff2eb83fb5a99b509e335968524431a6a141782261ed0180aaaf54e5`.

The following launch/progress notes are retained as execution history.

User explicitly authorized uploading exactly145 ready OPUS packages, four Baltic
math/tool packages and the MATH package. No inherited DaLA or other packages are
included in this operation. Detached uploader PID3469958 runs
`scripts.upload_dfm13_ready150`; log `logs/dfm13-upload-ready150-20261004.log`.
Queue root: `data/dfm13/upload-ready150-20261004-v1`.

The uploader authenticates using existing HF configuration without displaying
credentials, freezes allowlisted files under a sealed150-entry queue, and uploads
public canonical `schneiderkamplab` repositories. Frozen payload hashes must match
accepted export hashes. Existing conflicting remote contents are not overwritten.
Every remote file is downloaded at the returned commit revision and hash-checked;
extra remote files fail verification. Source exports/manifests and central registry
entries are not rewritten. Publication is recorded externally in
`publication-receipts.json`; `completion.json` is true only for150 verified repos.
HTTP401/403/429 stop dispatch with a durable blocker; no quota or authentication
bypass. The same command resumes the sealed queue without resetting verified work.
Initial metadata-shape error in the first launcher occurred before queue creation
or uploads; the restarted process uses exact Baltic package names rather than an
absent family field. Other CPU finalization continues independently.

HF's card validator confirmed that the Portuguese failures are metadata-only:
`language[1]` value `pt_pt` is not an ISO639 code. The normalized `pt` card passed
the same validator. A follow-up waiter PID3472007 runs
`scripts.finish_dfm13_ready150_cards`; it waits for the first upload pass, then
prepares `data/dfm13/upload-ready150-20261004-v2` with the same150 repositories.
Only failed Portuguese cards are normalized, retaining European Portuguese
`pt-PT` in prose. Atomic replacement breaks the copy's hard link, preserving all
source cards, original frozen queue pins, payload bytes and provenance. Already
verified repositories are retained, not republished. The final150 receipt is
the v2 `completion.json`; old and new queues/receipts remain independently sealed.
Latest observed first-pass progress:28 verified, two metadata-blocked and one
uploaded awaiting remote verification. No authorization/quota failure observed.

Exact HF validation diagnostic (no headers/credentials):
`"language[1]" with value "pt_pt" is not valid. It must be an ISO 639-1, 639-2 or
639-3 code (two/three letters), or a special value like "code", "multilingual".
If you want to use BCP-47 identifiers, you can specify them in language_bcp47.`
Four focused tests passed: exact remote revision/file hashes, extra-file rejection,
original hardlinked README and payload preservation, unchanged150-repo membership,
retention of149 prior verified receipts, and refusal to republish an already
verified Portuguese repository. No test performed an upload.
Parsed YAML inventory confirms eight affected Portuguese cards (BE, BG, BS, FA,
HR, HU paired with PT; PT paired with SL and SR). An earlier26 count was text
occurrences, not distinct cards; it is superseded. The helper operates on parsed
language values, not text occurrence counts.

Boole's later wave4 attribution handoff is pinned separately at
`data/dfm13/wave4-publication-inventory-20261004-v2/parent-tesla-handoff.json`:
66 packages /790,843 conversations, no Wikipedia identity gaps, and723 OpenHermes
rows missing component labels while retaining source IDs/hashes. The user allows
OpenHermes broadly; use applicable upstream evidence/notices and document the
label gaps, not fabricated row-level license certification. This inventory does
not add those66 packages to the explicitly authorized150 upload queue. Current
publication remains the priority; first-pass verified count subsequently reached35.

## Current DaLA Publication Policy

**2026-10-04 user correction supersedes the pool-separated publication policy
and272-repository counts below.** Publish exactly one DaLA v2 HF dataset per
language, with accepted baseline and recovery combined and deduplicated. Keep
task configs, train/heldout splits, full messages, target indices and pool/source
provenance. NL/FA must wait for both finalized pools. Internal training components
may remain separate, with recovery-overlap exclusions on baseline intake.

Expected unpublished destinations: **270**, comprising145 OPUS,78 synthetic,
1 MATH,34 DaLA v2 languages and12 inherited DaLA repositories (24 task components).
At the policy transition **162 packages were locally upload-ready**:145 OPUS,
12 inherited DaLA,4 Baltic synthetic and1 MATH. Old pool-separated DaLA v2
packages are excluded from this ready count; the new combined packages count
only after their payload/card/provenance validation completes.

The old pool packager3450458 was stopped by checked pidfd. Its immutable payloads
remain for evidence; ready receipts and the nine-language publication queue are
marked `superseded_do_not_upload`, with prior receipts archived. New packager
PID3466871 runs `scripts.package_dala_languages --watch`, log
`logs/dala-language-packages-20261004.log`, output `exports_dfm13_dala_languages`.
`queue.json` registers all34 canonical language destinations before packaging.
Exact native conversation duplicates are removed within task/split; conflicting
split assignments fail closed. Removed duplicate provenance is retained locally.
Two focused tests cover cross-pool deduplication, task separation, cross-split
rejection and the required two-pool NL/FA completion gate. No HF upload occurred.

## Latest Execution Snapshot (2026-10-04)

This section supersedes the older operational counts and training-state claims
below. CPU finalization does not alter the running training job.

- Authoritative additions: `data/dfm13/verified-finished-additions-dala9-20261004-v1`,
  468 verified sources, 34,449,485 training rows, 5,412,678,655 stored tokens.
- DaLA13 successor PID3393745 remains in full verification; Baltic/TLPC successor
  PID3397065 waits for that promotion. Baltic has 140,000 conversations,
  251,527 assistant targets and 138,766,115 tokens locally finalized.
- All 34 baseline DaLA languages now have complete terminal audit sources.
  Remaining 21-language finalization launched as PID3435652 (eight CPU workers),
  log `logs/dala-remaining21-finalization-20261004.log`, output
  `data/dfm13/dala-remaining21-finalized-20261004-v1`. It selects BG, BS, CA, DA,
  EL, ET, FI, FO, HR, HU, IS, LB, LT, LV, NB, NN, RO, SL, SQ, SR and SV.
  Dutch/Persian baseline-versus-recovery overlap remains a separately recorded
  pool-level reconciliation; those languages already have recovery releases.
- `scripts/queue_dala34_assembly.py` serializes the remaining-language successor
  after Baltic/TLPC promotion. Failed finalization cannot promote an assembly.
- Both published TLPC entries pass assembly eligibility and are merged from the
  current registry by the Baltic successor. Their inclusion is not yet verified
  in the authoritative assembly. Earlier TLPC access/defer claims are superseded
  by its completed authorized release.
- Boole's latest recovered wave4 selection reports 790,843 conversations:
  90,843 LB plus 70,000 for each other ten languages. Packaging is still active;
  this is not yet exported/tokenized/integrated completion.
- Refreshable inventory: `data/dfm13/all-source-finalization-20261004-v1/inventory.json`,
  generated by `scripts/dfm13_finalization_inventory.py`. It unions central and
  composite registries, retaining exact entry evidence rather than confusing the
  smaller central registry with the authoritative composite. Current snapshot:
  468 integrated, four held, 22 registered but not currently integrated.
  It explicitly marks comprehensive specification reconciliation **incomplete**.
- RepoChat, SearchArena and Mimir Search remain research-only; both Fars summary
  sources remain excluded. No epoch sampling, GPU action or blanket publication
  authorization is inferred from local integration.

### Automatic Continuation

Remaining-language integration waiter PID3437236 writes
`logs/dala34-successor-20261004.log`. Wave4 exporter PID3434470 writes
`data/dfm13/wave4-finished-release-20261004-v1`; its serialized assembly waiter
PID3439395 writes `logs/wave4-finished-assembly-20261004.log` and targets
`verified-all-finished-additions-wave4-20261004-v1` after DaLA34 promotion.
The narrow wave4 adapter verifies native full-target rendering, export/evidence
fingerprints, source ledger pins and the exact uncapped-LB release population.
Eight focused adapter/DaLA tests passed.

Inventory watcher PID3440385 refreshes the all-source inventory every minute.
Completion requires all 34 DaLA language/task pairs, 12 Baltic synthetic packages,
66 wave4 synthetic packages, both TLPC packages, registered-finished membership,
explicit specification reconciliation and local publication readiness. Missing
rights/readiness evidence cannot be replaced by an HF repository name or card.
Remote upload is not required for local-readiness completion.

The waiters above were refreshed while verified sleeping, using exact pidfds;
the active DaLA13 assembler was not signaled. Current waiters: Baltic/TLPC
3443402, DaLA34 3443482, wave4 3443483, inventory 3443547. The new
`scripts/assemble_dfm13_successor.py` fully hashes/verifies the predecessor once,
reuses semantic results only for exactly unchanged registry entries, checks
input signatures through construction, and fully validates new/changed entries.
The successor is still fully hash-verified before promotion. Nine focused tests
passed, including rejection of semantic reuse for changed registry entries.
Diagnosis of the original slow run: PID3393745 was actively replaying French
DaLA correction evidence after about 532GB of reads, not deadlocked. No restart.

NL/FA reconciliation finished: 1,001,494 Dutch and 1,139,656 Persian baseline
passing decisions were not duplicated in the admitted recovery inputs. These
are NOT admitted counts. PID3441801 runs the usual source/prior/heldout gates,
with recovery training inputs additionally seeded into the exclusion index.
Output: `data/dfm13/dala-baseline-delta-finalized-20261004-v1`.
Waiter3443548 integrates this delta after wave4; source/recovery exclusion pins
are verified by the assembly adapter. No raw source or audit decisions changed.

### Inherited DFM12 Coverage Blocker

The sampled DFM12 base is a historical reference, not proof of all later DFM12
coverage. Harvey's independent check finds 292 later source names and nine
same-name identity replacements absent from that build. Evidence:
`docs/reports/dfm13_inherited_dfm12_base_check_20261004.md` and companion JSON.
Harvey owns the exact delta/replacement candidate. Final inventory completion
now also requires explicit verified inherited coverage; none of the successors
above alone establishes complete DFM13. No epoch sampling or running-training
data change is authorized by this reconciliation.

**Superseded blocker, 2026-10-04:** Harvey delivered sealed
`data/dfm13/dfm12-full-inheritance-20261004-v2/handoff.json`. Its 381-source
composition is now materialized as reference/symlink inputs under
`data/dfm13/full-inheritance-compositions-20261004-v1`, with the current pointer
`data/dfm13/authoritative-composition.json`. This is the authoritative future-build
composition: DFM11 base plus latest381 DFM12 packages once plus current verified
DFM13 additions. The embedded sampled-DFM12 base in older additions manifests is
explicitly superseded, not appended. Nine obsolete identities are therefore not
included twice. Inherited additions: 1,325 token parts, 48,949,524 rows,
13,806,417,986 stored tokens. Validation preserves the handoff's honest scope:
metadata/source pins, headers and bounded array checks, not a new full payload
rehash. The separate 21-language XXL-wide identity catalog remains repeat0.

Composition watcher3448333 updates the composition after each additions promotion.
Active DaLA13 builder3393745 was safely stopped by checked pidfd while its output
was unpublished; replacement3448141 reuses the completed local views and registry.
Predecessor signatures are captured before hash verification and rechecked after
it and throughout construction; mutation and changed-entry tests pass.
Updated waiters: Baltic 3448871, DaLA34 3448951, wave4 3449015, NL/FA 3449016;
inventory3449145 refreshes its implementation each cycle.

DaLA local-package watcher3450458 creates separate task configs with train and
heldout splits, without rejected text, under `exports_dfm13_dala_compact`.
It follows all 36 language/pool groups, including separate NL/FA baseline and
recovery pools. The final expected unpublished destination count is **272**:
145 OPUS +78 synthetic +1 MATH +36 DaLA v2 +12 inherited DaLA repositories.
The inherited12 comprise24 task components, not24 repositories. Earlier
materialized-destination snapshots are progress counts, not this final backlog.
HF uploads are not performed by these CPU preparation steps.

Wave4 release is now complete: 66 packages, 790,843 conversations, 1,404,259
assistant targets and 974,517,843 stored tokens. Integration remains queued.
The inherited12 local HF package builder PID3451214 uses the existing accepted
exports and integration/source hashes, with task-specific train configs and no
retokenization. Output: `exports_dfm13_inherited_dala`. New DaLA v2 package
watcher3450458 reported14 completed packages without errors at this snapshot.
Publication inventory now deduplicates all repository destinations, including
the12 inherited repositories, and records completed local-package receipts.
`latest-checked.json` reported239 materialized/proposed pending destinations,
172 with explicit local readiness; the expected final total remains272.
These are time-stamped progress numbers, not remote-upload completion claims.

The wave4 adapter additionally caches shared source-ledger hashes only while the
full filesystem identity signature is unchanged; changed files are rehashed and
must match their expected digest. This avoids 66 repeated hashes of the same
large source ledgers without removing final assembly pin verification. The
mutation regression test passes. MATH local readiness metadata was attached
under `config/dfm13_sources.lock`; original payload/token paths, repeat5 and
remote publication state remain unchanged.

Read-only NL/FA overlap reconciliation PID3440384 compares baseline passing
decisions against actually exported recovery training inputs. Its receipts live
under `data/dfm13/dala-baseline-recovery-reconciliation-20261004-v1`; a novel
baseline pass still needs source/prior/heldout gates before admission.
MATH's local HF package is complete at
`exports_dfm13/dfm13-hendrycks-math-worked`, with 7,496 unchanged physical rows,
repeat5 metadata and 2,431,145 tokens. Publication is not claimed.

## Finished Additions

User authorized integrating all completed eligible additions on 2026-10-04,
including locally verified translation packages awaiting HF publication. No final
epoch sampling or training switch was requested.

The fenced build completed and reverified
`data/dfm13/verified-finished-additions-20261004-v1`: **450 additions,
22,023,543 rows and 4,385,275,196 stored tokens**, preserving Arena, JJzha,
MATH, Baltic and fourth-wave sources. This includes 35 newer uploaded OPUS
packages and 145 completed local packages absent from v11. These totals exclude
the inherited DFM12 base and are before repeat weighting or epoch sampling.

The completion watcher published `data/dfm13/authoritative-additions.json`
after successful assembly and reverification. Check the build's `-control`
directory for `verified.json` and `completion-report.json`; a failed build must
not replace the authoritative reference. Local-only does not mean HF uploaded.
See [local integration](dfm13-local-wave-integration.md) for the publisher rewrite
race, locks and launch records, and [assembly](dfm13-verified-additions-assembly.md)
for the existing verified dataset contract.

## Outstanding Work

### Final Cleanup Policy (2026-10-04)

User supersedes indefinite holds/retry work with a final strict selection:

- Mark completed DaLA v2 English, German, French, Spanish, Italian, European
  Portuguese, Czech, Dutch and Persian subsets for upload and combined integration.
  Preserve train/heldout separation and the explicit compact-audit contract.
- LT/LV Wikipedia QA gets a bounded strict-judge check and, only if reliable,
  survivor selection. If it cannot reliably salvage rows, stop work on it.
- Latvian P3 and Persian summaries get final strict audits. Keep only verified
  survivors; ignore remaining nonaccepted rows rather than repair/retry them.
  Previously failed negative controls must not be admitted by the new pass.
- Matina access has been requested; defer it while access is pending. Recheck
  TLPC independently for access and suitability and integrate relevant supply.
- Defer other unresolved rights/unavailable-source work for now.

The table below retains the preceding operational snapshot; the final-cleanup
policy above replaces its implied open-ended follow-up scope. Upload marking is
not proof of HF publication; completed uploads require publication receipts.

Execution receipts:

- The nine DaLA subsets are marked in
  `data/dfm13/dala-v2-upload-nine-20261004-v1/queue.json`: 18 task components,
  12,425,942 train rows and 1,027,403,459 tokens. No upload is claimed. Combined
  assembly targets `verified-finished-additions-dala9-20261004-v1`; keep the
  preceding authoritative reference until this successor verifies and promotes.
- Final Persian-summary controls failed with two false accepts among seven
  known negatives (six of 16 outputs were also technically unresolved).
  `data/dfm13/fars-final-strict-controls-20261004-v1/assessment.json` records the
  result. No bulk admission or further calibration: exclude these summaries.
- TLPC payload access rechecked with stored authentication still returns HTTP
  403 `GatedRepoError`. Metadata is readable, payload is not. Receipt:
  `data/dfm13/wave4/tlpc-access-20261004/receipt.json`. No TLPC rows downloaded,
  prepared or admitted by this check; Matina was not retried.
  A subsequent check with the user-supplied temporary credential also returned
  HTTP 403 for the same TLPC payload. The credential was entered via a hidden
  process prompt and used in memory only, not saved via HF login or to a file.
  User then explicitly deferred TLPC: ignore it for this iteration; no further
  access retries or queued preparation without new authorization.
- The final evidence-first QA/P3 check also cannot authorize salvage. All five
  QA positive controls produced invalid judgments, while P3 accepted a known
  incorrect source answer. This is already decisive even while the last bounded
  diagnostic conversations finish. No full-source admission or additional
  calibration is authorized; preserve evidence and leave these sources excluded.
  Evidence root: `data/dfm13/held-source-final26-20261004-v1`.

User confirmed automatic promotion of the DaLA combined build once ready.
Promotion means updating the authoritative local additions reference only after
full verification; it does not upload, sample epochs or resume training.

| Component | Remaining work |
| --- | --- |
| Baltic synthetic | Reach 70K audited accepts each for LT/LV; recover exact technical review failures without admitting held rows; resolve low-yield families; finalize/export/tokenize/integrate. |
| Fourth-wave synthetic | Queued after verified Baltic completion; 11 languages at 70K each, generation plus audit, then finalization/integration. |
| LT/LV Wikipedia QA | 118,866 source-held rows; source-grounded and follow-up per-turn calibrations did not establish reliable admission. Holds remain; no blanket release. |
| Latvian P3 | 7,680 source-held rows; follow-up fidelity/correctness calibration accepted all 26 examples, including eight known negatives. Holds remain; correct answer labels alone do not establish translation fidelity. |
| Persian Fars summaries | Source-fidelity holds remain; compact staged candidates are not blanket admission. |
| DaLA v2 | Main 34-language audit ongoing; completed passing subsets need split-preserving export and train-only tokenization through an explicit compact-audit adapter. Failed/flagged/uncertain rows are not training accepts. |
| Local OPUS publication | 145 completed local packages await HF quota resolution; local integration is separate from publication. |
| Persian Matina/TLPC | Approved sources, but payload access remained HTTP 403 at the last verified check; not downloaded/assembled supply. |
| Other deferred sources | Broader FinePDF/standalone Europarl rights and unavailable approved OPUS pairs remain governed by their source-specific records; no silent substitution. |

DaLA finalization can advance terminal source subsets without waiting for
unrelated languages. It must not relabel compact pair/control judgments as
producer per-edit verification, or put held-out splits into training.

## Operational References

- [Baltic generation](dfm13-baltic-compact-production.md)
- [Fourth-wave handoff](dfm13-baltic-wave4-handoff.md)
- [DaLA audit](dfm13-dala-v2-audit.md)
- [DaLA inventory](dfm13-dala-v2-audit-inventory.md)
- [QA holds](dfm13-baltic-qa-quality-holds.md)
- [P3 holds and source alignment](dfm13-latvian-p3-export.md)
- [Fourth-wave sources](fourth-language-extension-wave.md)

Training remains paused. Shared generation/review servers are not restarted by
these CPU integration operations.

## Baltic Validation Recovery

On 2026-10-04, recovered 13,093 previously rejected complete reviewer responses
with exactly `keep`, empty issues and an empty rationale. Source, native-format,
fingerprint and hold checks remained enforced; saved evidence and recovery
receipts are retained. This brought the stopped campaign from 9,369 to 22,462
accepted conversations before restarting generation. The private successor
allows this exact response shape without relaxing semantic checks. A broader
semantic reviewer change failed calibration and was not deployed. Recovery is
not new GPU throughput and must be excluded from subsequent ETA measurements.

## Additional Authorized Uploads (2026-10-04)

After the original150 verified publications, the remaining uploader continues
with combined per-language DaLA packages (never split baseline/recovery repos).
PID3483105 runs `scripts.upload_dfm13_remaining_ready --watch`. Its first batch
has12 inherited repository conflicts; existing canonical repositories contain
different shards plus heldouts/provenance. They are not overwritten, and mere
repository existence is not counted as verified publication of the local view.
Decoded-row/source-version reconciliation remains required; automatic blind
retries cannot resolve this conflict.

The independently authorized66 wave4 packages upload concurrently, without
overlapping DaLA repositories. PID3487288 runs
`python -u -m scripts.upload_dfm13_wave4_ready --root data/dfm13/upload-wave4-ready66-20261004-v1`.
Log: `logs/dfm13-upload-wave4-ready66-20261004.log`. Its queue binds Boole's
`wave4-publication-notices-20261004-v4/upload-authorized-handoff.json`, all66
unchanged accepted exports, package attribution/notices, and shared evidence.
Initial observed progress:5 remotely SHA-verified, sixth verification underway.

PID3488028 runs `scripts.upload_dfm13_baltic_ready2` with root
`data/dfm13/upload-baltic-ready2-20261004-v1`; log
`logs/dfm13-upload-baltic-ready2-20261004.log`. Only the two cleared LT/LV
OpenHermes packages (30,000 conversations) are selected. Initial progress: one
verified, second verification underway. Six other Baltic packages remain
blocked by exact Europarl sitting-attribution/adaptation-scope evidence for
30,528 rows. No unsupported completion ETA is assigned to that evidence gap.

Each queue writes `publication-receipts.json` with exact remote revisions and
file hashes, then `completion.json`. The live finalization inventory consumes
these verified overlays and all remaining DaLA batch receipts without changing
sealed source manifests or active assembly inputs. Ten uploader/scope/seal/card
tests passed. No GPU, training, sampling or source payload changes were made.

### Resolved Publication Fields (2026-10-05)

`scripts.dfm13_finalization_inventory` now exposes `hf_repo_id` and
`hf_revision` for verified grouped DaLA components, using the same pinned
publication/integration proof as specification reconciliation. The reporting
overlay explicitly identifies a derived local view and makes no byte-identity
claim. Original registry and assembly evidence remain unchanged. This corrects
the misleading inference that a missing field meant a local-only dataset.
The refreshed `data/dfm13/publication-resolved-inventory-20261005.json` resolves
72 components to 34 repositories, including all four Dutch baseline/recovery
task components to `schneiderkamplab/dfm13-dala-v2-nl-compact` at revision
`ad00994945ce311c15a31010577cd56f116d5ca1`. Eleven focused inventory/reconciliation
tests passed. Sealed sampling receipts and running jobs were not modified.

### Inherited Publication Correction

The earlier12 inherited upload conflicts are superseded by
`docs/reports/dfm13_inherited_dala_collision_20261004.json`: all12 pinned remote
producer manifests and audited train-pair hashes exactly equal the local
producer evidence, with identical counts. Local50K versus remote100K shards,
projection metadata and ordering explain the different gzip hashes. German
pair-ID/variant comparison matched24/24 sampled native messages across both
tasks; this is a sample, not an exhaustive message comparison for all languages.

These are existing publications, not12 missing independent datasets. Historical
270 initial /120 post-first150 backlog counts are corrected to258 /108 before
subsequent uploads. The live inventory records existing producer revisions and
the comparison receipt separately from local projection provenance, explicitly
not claiming byte-identical local/remote packages. Original failed upload
receipts remain historical evidence. No overwrite, derivative repository or
additional upload is authorized or performed for these12 by this correction.

On2026-10-05 the user explicitly selected Option1: reuse those12 existing HF
repositories at the verified pinned revisions and document the local conversion.
This supersedes treating their historical uploader `blocked` records as current
upload backlog. Policy receipt:
`data/dfm13/inherited-dala-publication-disposition-20261005.json`.
No duplicate repository, overwrite or derivative upload is permitted by this
selection. All66 wave4, both cleared Baltic OpenHermes, and all34 combined
DaLA-v2 language packages now have verified remote publication receipts; these
are separate from the12 reused inherited producers. Other publication holds
and CPU integration checks remain independent.

### Baltic Six Scoped Gate Supersession (2026-10-05)

The earlier six-package hold is superseded by the completed
`exports_dfm13/baltic-source-attribution-20261004-v2/handoff.json` and
`docs/reports/baltic-europarl-scoped-reuse-resolution-20261004.md`.
All90,000 conversation payloads are unchanged. The scoped decision preserves
actual source links, sitting identities, captured terms and separate generated
answer labelling; it does not invent a CC grant or waive other source holds.
The uploader checked all handoff evidence pins, package manifest hashes,
scoped decision attachments and every frozen file hash before publication.

Launched PID466048 with `scripts.upload_dfm13_baltic_ready2 --scoped-six`,
v2 handoff and root `data/dfm13/upload-baltic-ready6-20261005-v1`.
Log: `logs/dfm13-upload-baltic-ready6-20261005.log`.
The exact six-repository queue excludes the two already-published OpenHermes
packages and four math/tool packages. `publication-receipts.json` binds each
verified remote revision and file digest; `completion.json` is the terminal
result. The live inventory consumes this overlay, not obsolete v1 hold flags.
Seven focused uploader tests passed. No source payload, registry, GPU or
training changes were made.

Terminal result: **6/6 uploaded and remotely SHA256-verified**, all90,000
conversations. Receipt:
`data/dfm13/upload-baltic-ready6-20261005-v1/completion.json`, `complete=true`.
Queue SHA256: `55b0e1f1de8c5d3d4fb47cf1a6f718e01e9d478f281cedae6402452021e604d9`.
Publication receipts SHA256:
`9a22530774aa57c13f708970c99925a84396c2f9a5805ef34d0bab14ea42ae21`.
All twelve Baltic synthetic packages are now published across the original
four math/tool, two OpenHermes and six scoped successor queues. Publication
completion does not claim the separate canonical assembly backlog is complete.

### Publication Campaign Terminal (2026-10-05)

**258/258 newly published repositories remotely verified; upload backlog0.**
Breakdown: original150 +66 wave4 +34 combined DaLA-v2 languages +2 Baltic
OpenHermes +6 Baltic scoped successors. Twelve inherited DaLA producers are
reused at verified existing revisions, not counted as new uploads. The refreshed
`data/dfm13/all-source-finalization-20261004-v1/latest-checked.json` records
`named_pending_repositories=0` and a separate `publication_campaign` result.
Canonical assembly integration remains incomplete and is not represented as
finished by this publication-only milestone.

### Authorized Final Assembly And One Epoch (2026-10-05)

User now authorizes integration, verification and sampling, with explicit
`epochs=1`, destination `data/sampled_dfm13`. No DFM13-specific epoch setting
previously existed; generic sampler10 was not adopted. Running DFM12 is untouched.

The old DaLA13 builder had exited at a final signature check on CS acceptability
`test_challenge.jsonl.gz`. Its SHA256 remained
`91464b2a1e249ba16bf854c0f646da894a3444bcbd55023c41761c1c2c7d5141`;
inode, size and mtime matched while ctime changed and nlink became2 through
packaging. No integrity guard was removed. A brief retry and four idle owned
successor waiters were stopped using exact command identity/starttime plus pidfd.

Consolidated builder PID472511, `scripts.assemble_dfm13_final_successor`, writes
`data/dfm13/verified-all-finished-additions-20261005-v1`; log
`logs/dfm13-final-successor-20261005.log`. It reuses the predecessor and prepared
eight-component delta, prepares42 remaining-language plus4 NL/FA baseline
components (37,509,812 new task rows), and admits finished Baltic, wave4 and
central additions including TLPC through existing validators. Only a fully
verified successor is promoted. Expected CPU duration is hours, not a promised
deadline; one consolidated successor replaces four repeated verification passes.

Existing composition watcher PID3448333 updates the DFM11 + latest381DFM12 +
DFM13 composition after promotion. Nine replaced legacy identity sources are
not appended twice; inherited21 XXL-wide identity repeat0 remains explicit.
Sampler PID473790, `scripts.sample_dfm13_final`, waits for that exact final
verified composition. Log: `logs/dfm13-final-sampling-20261005.log`; progress and
final receipt: `data/dfm13/sampling-20261005-v1/`. It reuses
`dfm12.build_training.combine`, native Gemma/tokenizer checks, preserved repeats,
and one explicit epoch. Addition rows/tokens must exactly equal weighted input
totals, rejecting silent drops/truncation. It scans all final token vocabulary
values and all index bounds/context lengths and reconciles token totals before
writing completion. Sampling metadata and final completion are distinct; the
latter is required to claim validated completion. Five focused merge/validation
tests passed. No GPU or running-training process changes were made.

Bounded preparation successor: PID475951 replaces472511 with16 spawned CPU
processes using `scripts.prepare_dfm13_dala_parallel`; log
`logs/dfm13-final-successor-parallel-20261005.log`. Each component has independent
atomic output and reconstructs exact original bytes, hashes, counts and split
checks. Completed views are retained only after byte-equivalence verification.
Progress under control `local-views/<finalizer>/progress.json` reports completed
rows, components, throughput and rough preparation ETA. Observed17/42 components,
11,284,262/34,057,348 remaining-language rows prepared;4 baseline-delta components
follow. Full semantic verification remains required and is still serial.

Sampler PID477498 supersedes473790 while waiting, with the same log. It now
requires `data/dfm13/all-source-finalization-20261004-v1/sampling-reconciliation.json`
containing `all_specifications_disposed=true`, `sampling_authorized=true`, and
the final `assembly_sha256`. Independent coverage/replacement reconciliation
must supply this receipt; it is not fabricated by the sampler. Output is staged
at `data/sampled_dfm13.building-20261005-v1`, scanned fully, compared against
exact base epoch0 rows/tokens plus weighted additions, then atomically renamed.
No generic base average is used as an exact epoch count. Seven tests passed for
parallel/serial byte parity, existing-view preservation, drift rejection and
sampling bounds. Training remains unchanged.

### Setur FO Repeat10 Sampling Gate (2026-10-05)

User adds `Setur/fo-instruct` at repeat10. Parent owns source preparation,
native tokenization, adapter and central registration; none is duplicated here.
Running606-entry verifier PID475951 is preserved. Detached successor waiter
PID612888 (`scripts.queue_dfm13_fo_instruct_successor`) waits for its verified
promotion plus exactly one completed central FO entry at integer repeat10.
Log: `logs/dfm13-fo-successor-20261005.log`. Successor root:
`data/dfm13/verified-all-finished-additions-fo-instruct-20261005-v1`.
Repository identity is exact `Setur/fo-instruct` in `hf_repo_id`, `source_repo`
or `source_repo_id`, not a substring match. Duplicate registration, wrong
repeat or failed admission prevents promotion.

Only the idle sampler was refreshed: PID612823, log
`logs/dfm13-final-sampling-fo-20261005.log`. It now requires the FO-inclusive
successor, verified FO admission, composition repeat10 and reconciliation
bound to that successor's assembly hash. Thus the preceding606-entry assembly
cannot be sampled without the requested source. At wiring time both source
registration and predecessor verification were pending: queued is not included.
Six focused gate/sampler tests passed. No Git, GPU, preparation duplication or
running DFM12 changes were made.

Setur preparation is now complete and centrally registered as
`setur_fo_instruct`, `repo_id=Setur/fo-instruct`, revision
`55a97b043e1a3f2778492c72bf124f4091341402`, recorded CC-BY-4.0.
Receipt: `data/dfm13/setur-fo-instruct-20261005-v1/completion.json`.
It contains571 native training rows and41,370 stored tokens; repeat10 means
5,710 weighted rows and413,700 weighted tokens per epoch. The receipt records
no hard truncation and deterministic sampled native token parity, not a model
quality audit. Source preparation/adapter ownership remains with parent.

The successor's exact source matching was extended to the actual `repo_id`
field after detecting that the earlier three-key matcher left registration
unrecognized. Only the idle successor and sampling waiters were refreshed;
verifier475951 remained untouched. Seven focused matcher/sampler tests passed.
Source preparation is complete but successor integration and final sampling
are still pending verified predecessor completion and reconciliation. Dyna
inventory research is read-only; no scan candidates are added to this scope.

Reconciliation watcher corrected to use the shared FO-inclusive successor root
instead of the previous hardcoded606-entry root. PID621177 replaces the idle
old watcher; log `logs/dfm13-specification-reconciliation-fo-20261005.log`.
It requires verified FO admission at repeat10 before authorizing sampling.
Setur readiness is narrowly bound to the exact completion entry, pinned source
revision, original/card/native-output hashes and token files (13 checked pins),
as existing upstream publication plus local conversion, not a new upload or
model audit. This avoids a false missing-publication gate. Ten reconciliation
and successor tests passed; the live606-entry verifier was not modified or
restarted. Final reconciliation and sampling remain pending actual promotion.
