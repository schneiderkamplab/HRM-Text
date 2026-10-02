---
type: Status
title: DFM12 Addition Status
description: Dataset-by-dataset preparation status for additions beyond inherited DFM11.
tags: [dfm12, datasets, status, multilingual]
status: draft
last_updated: 2026-09-29
confidence: high
---
# DFM12 Addition Status

## Completed Synthetic Campaign Integration (2026-09-29)

The joint original-seven/new-twelve generation and independent audit campaign
has completed **875000 accepted conversations**, zero active candidates and
zero remaining targets. No worker/recovery errors were reported at completion.
The owner authorized exporting and uploading all outstanding language packages
and integrating them into DFM12.

The earlier 13-language export contains 525000 rows at
`exports_dfm12/multilingual-completed-20260929-v1`. The final six languages
(CA, CS, ET, FO, IS, PT-PT) contribute 350000 rows; their completed export is
at `exports_dfm12/multilingual-final-six-20260929-v1`. Both retain native
messages, tool calls, tool results and tool definitions. Audit metadata is
separate and must never enter training inputs. All 19 public repositories
`schneiderkamplab/dfm12-multilingual-synthetic-{language}` are uploaded and
remote-verified (875000 rows). Publication revisions, counts and hashes are
recorded in `exports_dfm12/multilingual-publication-20260929-v1/final-receipt.json`.

`dfm12/training_sources.json` now registers these packages and the 21-language,
42000-row identity release. Nine explicit package overrides replace older
identity releases rather than concatenate/double-count them. Synthetic repeat
is 1; identity repeat remains 10. The loader fails closed until publication
receipts and manifest-bound verification are present. All publication and
staging checks passed: 357 exported packages plus 24 local audited DaLA
components, for 381 registered DFM12 addition sources.

`dfm12/training_sources_generated.json` selects only these 40 new/replacement
packages for CPU tokenization without retokenizing inherited sources.
`build_training --tokenize-only` stops before sampling or promotion. The
existing sampled corpus and running training are not changed by staging.

Tokenization completed with 16 CPU workers and the inherited DFM11 Gemma
template/tokenizer, thinking disabled and 4096-token limit. A native tool-call
smoke preserved the definition, two tool-call assistant targets and final answer.
The 40 new/replacement packages produced 135 completed tokenized files:

| Release | Conversations | Assistant targets | Tokens once | Tokens at configured repeat |
| --- | ---: | ---: | ---: | ---: |
| 19-language synthetic | 875000 | 1573886 | 835382409 | 835382409 (repeat 1) |
| 21-language identity | 42000 | 89531 | 20819475 | 208194750 (repeat 10) |

These are package contributions, not net growth over the old identity release
and not final sampled-epoch totals. Per-source counts are in
`data/dfm12/training-build-generated-complete-20260929/token-counts.json`.

The complete accepted source inventory is staged at
`data/dfm12/training-build-completed-campaign-20260929/accepted_inputs`.
All **1325/1325 input files** have verified reusable tokenized outputs at
`data/tokenized_dfm12_additions-completed-campaign-20260929`; the union contains
48949524 assistant targets. Its reuse receipt records each source path.
No inherited token arrays were rewritten and no new final epoch indices were
sampled or promoted to `data/sampled_dfm12` in this operation.

Token inventory measured across all 381 sources: **13806417986** tokens once,
or **13993793261** with the configured identity repeat 10 and other repeats 1.
Inherited DFM11 metadata reports **103214604702** tokens per epoch, giving
an estimated full DFM12 epoch of **117208397963** tokens (117.21B). This is
pre-sampling accounting; final sampled metadata remains authoritative.

Reproduction commands:

```bash
python -m dfm12.build_training --suffix completed-campaign-20260929 --prepare-only
python -m dfm12.build_training --sources-config dfm12/training_sources_generated.json \
  --suffix generated-complete-20260929 --workers 16 --tokenize-only
python -m dfm12.tokenize_registered --workers 16 \
  --build-root data/dfm12/training-build-completed-campaign-20260929 \
  --output data/tokenized_dfm12_additions-completed-campaign-20260929 \
  --reuse data/tokenized_dfm12_additions-generated-complete-20260929 \
  --reuse data/tokenized_dfm12_additions-all-additions-20260928 \
  --reuse data/tokenized_dfm12_additions
```

## Second European Wave (2026-09-26)

The owner authorized twelve further languages plus missing existing-language
instructions and TrustLLM answers. See the [separate operational status and
source map](dfm12-european-expansion.md). CPU preparation is running; these
new candidates are not part of the 89 accepted packages described below.
GPU generation/audit, screening and accepted-only integration remain pending.

## Training Build Authorized And Started (2026-09-25)

The owner subsequently authorized final tokenization and sampling, superseding
the sampling deferral below. `python -m dfm12.build_training --workers 16
--epochs 10` runs detached with CPU-only visibility; its log is
`logs/dfm12_build/build.log`. All 89 verified accepted packages are included,
identity at repeat 10 and other additions at repeat 1. Translation ceilings
are checked, not filled by repetition. Input hashes and upload receipts gate
staging; rejected rows and unaudited tokenization trees are never inputs.

The complete local `data/sampled_dfm11` has ten matching epoch index sets.
Reuse their exact selections and append the sampled additions, then uniformly
shuffle complete rows with deterministic epoch seeds. This avoids rebuilding
the unavailable inherited tokenized union or changing its source weights.
Outputs are `data/tokenized_dfm12_additions`, `data/sampled_dfm12_additions`,
and `data/sampled_dfm12`. The inherited token array is copied sequentially,
with bounded chunks and one writer; existing training data is not modified.
Final metadata is published only after all ten merged index sets complete.
The build receipt will report exact per-epoch inherited and additional totals.
This launch is not yet a completion claim. The running XXL job is unchanged.

## Verified Publication Completion (2026-09-25)

Supersedes the in-progress audit/export states below: all authorized audit
queues are terminal, and all 89 accepted-only packages are exported and publicly
uploaded with verified receipts. They contain 15,988,682 training rows in total.
The last two packages were `dfm12-dala-en` and `dfm12-dala-nl`.
The final orchestrator receipt reports no remaining audits and no finished
sources awaiting export:
`data/dfm12/export-orchestration-20260925/20260925T143233Z-1790346753307995441/receipt.json`.
Remote upload receipts are in `exports_dfm12/metadata/upload-receipts.json`.

The audit-owned GPU servers were released, and both completion hooks finished.
This is publication completion, not a completed sampled DFM12 training corpus:
final accepted-source tokenization/union reconciliation and mixture/epoch
sampling remain to be performed. Final sampling remains deferred by the owner.
Exhausted failures were not retried, as requested.

## Completion And Publication Decision (2026-09-25)

The owner authorized accepted-only preparation and public upload of all finished
DFM12 additions, including the scoped Scandi/NorQuAD/FLEURS and identity sources.
Exhausted request failures remain excluded: do not retry or regenerate them.
After all audit sources are complete and all jobs terminal, release only the
audit-owned vLLM servers, then prepare and upload the remaining accepted datasets.
Publication must retain source/split/benchmark annotations and validate each
package. Shared root `exports_dfm12/metadata` remains local-only; never upload its
rejected-row snapshots. Final training sampling remains deferred.

## Source Inclusion Supersession (2026-09-25)

Explicit owner instruction: **include Scandi, NorQuAD and FLEURS**, and ensure
their audits are queued. This supersedes their exclusions in the historical
sections below. Full NorQuAD Wikipedia train (1,886 candidates), not only the
815 passage-disjoint subset, and all 1,457 FLEURS translation pairs are in scope.
The pinned Scandi collection is admitted to preparation/quality audit, including
Danish and recoverable generic Norwegian; no unsupported NB/NN label is inferred.
Normal schema, length, deduplication and quality checks still apply.

Known benchmark-origin/overlap facts are preserved as provenance and reporting
caveats, not silently relabeled as benchmark-clean. Inclusion is not a new
license grant or native-speaker certification. Prior audit source manifests
remain immutable; the new components use isolated manifests/queues on the
existing servers. Final sampling remains deferred. PLLuMIC-syn-ext stays deferred.

Audit queue: `data/dfm12/scoped-inclusion-audits-20260925-v1/registration.json`.
The detached watcher records live state in `status.json`. NorQuAD/FLEURS have
launched an isolated audit client (1,886 and 1,457 candidates respectively).
Scandi is registered against
`data/dfm12/scandi-included-20260925-v1/integration.json` and waits for the
completion sentinel and checksum validation before launching. These queues reuse
the existing eight servers without restarting the main or Polish/Icelandic audits.

## Earlier Exclusions And Deferrals (Superseded For Scandi/NorQuAD/FLEURS)

This reconciles the historical holds below; it does not introduce new exclusions.

- `pelcra/PLLuMIC-syn-ext`: explicitly deferred by the owner. Main PLLuMIC and
  PLLuM-Align are included, with conflicting identity/branding rows screened out.
- `V4ldeLund/scandi-translated-instruct`: the pinned release is omitted
  (1,252,683 rows), following constituent/split/attribution review and known
  MURI held-out matches. See the [scoped disposition](dfm12-scandi-translated-instruct.md).
- Norwegian DynaInstruct's NorQuAD and FLEURS constituents remain unselected
  operationally. The [2026-09-25 review](dfm12-norwegian-dynainstruct.md)
  recommends auditing 815 passage-disjoint NorQuAD train candidates and retaining
  the FLEURS exclusion because of FLORES evaluation-text lineage. No admission
  has been changed. Unknown/mixed Norwegian variants are **not**
  excluded: the owner-authorized 5,741 additions were integrated and audited.
- OPUS web-mined alignments and low-priority fragments/subtitles/religious corpora
  remain excluded. Other unreviewed OPUS releases remain outside the approved
  Tatoeba plus seven named ELRC releases; `data/dfm12/opus/review-decisions.json`
  records the exact release-level decisions. These are not failed audit jobs.
- The pinned Danish DynaInstruct composite has no new increments relative to
  inherited source reservoirs; it is not duplicated as a new addition.
- Held-out matches, exact duplicates, superseded preparation alternatives,
  malformed/overlength rows, audit rejections and exhausted requests are
  row-level exclusions, not blanket exclusions of their parent datasets.

Supersedes the overnight queue state below: identity bulk audit was explicitly
authorized and launched (PID 2011630); Polish/Icelandic train-only DaLA was
converted, verified and launched in an isolated audit root (PID 2017186).
Neither is deferred. Existing main audit and vLLM servers were left running.
No final DFM12 epoch sampling has been requested or performed.

Subsequent completion: identity bulk audit has finished all 8,575 rows, in
addition to 177 earlier pilot rows. Of the 8,752 unique conversations, 8,715
passed the automated audit (4,109,461 rendered tokens); this is not a claim of
human/native-speaker validation or a completed HF export. The current full
candidate pool is 4,502,796,551 rendered tokens before audit/row exclusions,
including all 73 pinned non-identity components plus identity. See the
[token accounting](dfm12-token-accounting.md) for exact snapshots and the
distinction between candidates, accepted exports and per-epoch sampling.

Overnight check, 2026-09-25: Swedish audit finished (1,531,144 decisions,
1,428 exhausted request failures). The handoff succeeded: main PID 1847954
is running at 768 clients/endpoint, preserving servers and existing decisions.
At this check the main audit has 7,587,729 done and 9,692 exhausted failures.
Newly audit-finished, not yet exported: Norwegian/Polish DynaWord, Dutch
UltraChat, Swedish DaLA acceptability and correction. Icelandic DynaWord was
already exported locally but not uploaded; 52 earlier packages remain public.

Supersedes the prior still-building PL/IS claim: the external producer's
`recovery_v1/finalization.json` now reports all six candidate datasets complete,
including 478,929 Polish and 478,928 Icelandic pairs (all splits). These two
still require the DFM12 train-only isolation/import checks and audit enqueue;
neither is in the active audit manifests. The external `current-run.json`
running label is stale relative to finalization. Identity bulk review remains
gated (8,575 jobs); generation is complete except 69 exhausted failures.

Third local export batch, 2026-09-24: `dfm12-dynaword-is` contains 162,270
accepted training rows, 97,006,392 compressed training bytes. Standalone
validation passed; 47,505 audit rejects, 79 unresolved request failures and
14,625 pre-audit quarantines are excluded. Combined local inventory now has
53 packages / 1,208,420 training rows. This new package is **not uploaded**;
the previous 52 remain public. Icelandic constituent-license resolution uses
the pinned DynaWord card, preserving per-source attribution/share-alike labels.

Post-Swedish capacity handoff scheduled, 2026-09-24: user requested increasing
main concurrency when Swedish DaLA finishes. Detached watcher PID 1800915 runs
`python -m dfm12.audit_handoff` and waits for **both** Swedish sources to have
`complete=1` and no pending/running/parked rows. It then gracefully drains only
the main client and resumes its existing database at **768 requests/endpoint**
(up from 512), preserving today's combined main512+Swedish256 client budget.
No server restarts, force kills, accepted/failed resets or training changes.
State/log/receipt: `data/dfm12/full-audit-20260924-v1/swedish-handoff*`.
If main has already finished, it exits without relaunching; unexpected absent
main client or a drain timeout is reported rather than guessed through.

Swedish 256 trial, 2026-09-24: user approved raising only the Swedish client
from 128 to **256 requests/endpoint (2,048 total)**. PID 1757505 drained fully;
PID 1762864 resumed the same database with unchanged single preparation worker.
The authorization cap was explicitly raised to 256, preserving its prior copy.
Main audit stays at 512/endpoint; server settings and processes are untouched.
Log: `data/dfm12/full-audit-sv-20260924-v1/runner-concurrency256.log`.
Before/after throughput and vLLM measurements are saved alongside as
`concurrency128-measurement.json` and `concurrency256-measurement.json`.
Five-snapshot short-window results (30-second settling time after restart):
Swedish 7,772 -> 15,256 completed rows/min; main 7,666 -> 7,685;
combined 15,438 -> 22,941 (+49%). Mean active requests/server 203 -> 362,
mean GPU utilization 66.4% -> 74.4%, mean KV occupancy 39.0% -> 69.9%.
Peak sampled KV occupancy at 256 was 96.7%; no KV preemptions observed.
Keep 256 for now, do not infer headroom for another increase from the mean.
These are short, changing-source windows, not a controlled benchmark or firm ETA.

Swedish concurrency update, 2026-09-24: explicitly authorized by the user,
the separate Swedish audit was cleanly drained and restarted as PID 1757505
with **128 client requests per endpoint (1,024 total)**. This supersedes the
initial one-request-per-endpoint limit. The pinned authorization records the
new cap; evidence, sources, accepted-export gates and single-writer database
remain unchanged. One CPU preparation worker remains. Neither the main audit
nor any vLLM server was restarted. Tests: 27 passed. Log:
`data/dfm12/full-audit-sv-20260924-v1/runner-concurrency128.log`.

## Latest Audit Check (2026-09-24, 22:04 CEST)

Recovery in the same session: `Database.finish` now ASCII-escapes JSON for
SQLite storage and safely escapes malformed error text. The HTTP worker checks
UTF-8 encodability after audit validation, treating unpaired model surrogates as
retryable row failures, never accepted results or whole-client crashes. All 19
full-audit tests passed, including the surrogate regression. Main audit resumed
as PID 1753152 using the original database, 16 preparation workers and 512
clients per endpoint; no servers restarted and no done/failed rows reset.
Log: `data/dfm12/full-audit-20260924-v1/runner-unicode-resume.log`.

Supersedes earlier running-process claims: main audit PID 1483293 has exited.
`runner-512.log` reports `UnicodeEncodeError` in `Database.finish`: a judge
result contains an unpaired surrogate (`\\udbac`), and `json.dumps(...,
ensure_ascii=False)` cannot be written through SQLite's UTF-8 boundary.
Database state: 3,641,572 done, 3,192 exhausted failures, 16 pending and 363
leased/running leftovers. No newly completed components beyond the 52 public
HF packages. Repair serialization and resume from the existing database; do not
discard completed decisions or restart servers merely for this client failure.

Swedish audit PID 1694116 remains active (8,958 done, six failures at this
check); acceptability is streaming and correction is in its manifest but not
yet registered. Identity generation completed 8,931/9,000 requests with 69
failed requests; bulk identity quality audits remain staged pending pilot
review. Polish and Icelandic DaLA producer jobs are still running externally.

## CPU Completion Campaign

Accepted export authorization, 2026-09-24: the user authorized local HF
packages under `exports_dfm12` for audit-finished components. This supersedes
the no-accepted-export restriction below only for this explicit packaging
operation; the auditor's operational approval is not modified. Sources must
have completed preparation and no pending/running jobs. Exhausted failures
are excluded as unresolved, not quality rejections. Only validated kept
decisions passing deterministic gates enter training data. No upload or final
sampling is authorized. Root `exports_dfm12/metadata/` contains private local
snapshots and must not be uploaded; each nonempty validated `dfm12-*` directory
is a separate upload candidate. Package manifests report rows and byte sizes.

The first completed export snapshot contains **39 validated nonempty packages**:
31 OPUS pairs and eight NB/NL/NN/SV reordering components. They contain
**481,224 training rows**, **154,037,100 compressed training bytes**, and
**628,261,823 whole-package bytes** (excluding the private root snapshot).
149 unresolved audit failures are excluded. All standalone package validations,
28 focused tests, and offline HF streaming loads of translation and reordering
examples passed. See `exports_dfm12/README.md` for the individual inventory.
Nothing was uploaded; the rest of the audit remains independent and running.

Second export batch, 2026-09-24: incremental packaging added 13 finished
components (FO/NL/SV DynaWord, FO DaLA acceptability/correction, FO/IS
DynaInstruct, four Norwegian components, PLLuM-Align and PLLuMIC).
The original 39 packages were checksum-verified and not replaced. New packages
contain 564,926 accepted rows and 224,789,687 compressed training bytes.
Combined inventory: **52 packages, 1,046,150 rows, 378,826,787 compressed
training bytes and 1,496,173,876 whole-package bytes**. All newly built packages
passed standalone validation. No uploads.

Full-audit update, 2026-09-24 (supersedes startup/concurrency settings below):
all eight Gemma4 26B-A4B servers are healthy and serving requests on ports
8400-8407, with `--max-num-seqs 256`, 0.90 GPU memory utilization and
**client concurrency 256 per endpoint**. The full-corpus client is running
as PID 1413633; its live counters are in
`data/dfm12/full-audit-20260924-v1/runtime.json`. At the verification snapshot,
39,539 rows had completed, with successful responses from every endpoint.
Source preparation is still streaming; this is not a completion claim.
Server restart records/logs: `logs/dfm12-audit-20260924/servers-maxseq256/`.
Automated audit decisions do not directly authorize accepted training exports;
training remains paused and no final sampling is authorized.

GPU startup update, 2026-09-24: eight parallel Gemma4 26B-A4B servers use the
`audit` conda environment, HTTP ports 8400-8407, eager mode, 8192 context,
0.90 GPU memory target and 64 maximum sequences. Slow shared-filesystem imports
delayed CUDA initialization by over an hour. Three servers (GPUs 2/5/6) exited
with internal TCPStore EADDRINUSE; only those were relaunched, with distinct
VLLM_PORT ranges 25200/25500/25600. All eight subsequently allocated 2960 MiB
each, but this is initialization, not confirmed inference. Live startups must
not be interrupted; owner explicitly declined sequential startup for future runs.
Logs: `logs/dfm12-audit-20260924/servers/`. Clients use `hrm`, concurrency 32
per endpoint, and wait without consuming audit attempts until endpoints respond.

Latest completion check, 2026-09-24 (supersedes running assignments below): all
six assigned CPU workstreams have returned results. Reordering integration is
complete: NB 55,757 native / 21,651 blocks; NN 23,192 / 6,108; SV 52,636 /
36,279; NL 44,344 / 16,393. NN remains 4,474 below desired audit headroom.
Norwegian inclusive preparation adds 5,741 rows / 1,757,549 tokens, unaudited.
Cross-source screening covered 143 files / 17,359,485 conversation views:
two Norwegian held-out matches require quarantine; duplicate groups and source
overlap are recorded in its audit manifest. All Scandi rows explicitly omitted.

Remaining CPU integration: apply screening gates and refresh audit manifests
for the completed reordering/inclusive additions without mutating live pilot
snapshots. Other-thread PL/SV/IS DaLA builds are still running; integrate released
outputs after their isolation/exclusion checks. Accepted-only export and
tokenization remain dependent on GPU audit results. No final sampling.

Owner update, 2026-09-24: **superseded Norwegian omission decision**. Include
the 4,496 punctuation-restoration rows and 1,245 mixed NB/NN conversation pairs
as unaudited candidates. Preserve unspecified Norwegian standard and actual
speaker orthography; do not invent a pure NB label. Preparation and audit
integration assigned to the Norwegian/audit agents. Quality acceptance remains
separate from this inclusion decision.

GPU audit launch authorized in the same follow-up. Training/scheduler stopped;
all eight GPUs verified empty. Last complete resumable checkpoint:
`checkpoints/dfm11/XXL-from-dfm10-epoch2/ephemeral_step_650500`
(tag, with state JSON and eight FSDP shards). Scheduler `stop.request` remains
set in `logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725`.
GPU startup is delegated to the audit agent; pilot review is not yet approved.

Latest snapshot, 2026-09-24: four agents completed their assignments; two CPU
processes remain active. Reordering expansion finished, integration/deduplication
is running. Cross-component overlap scanning is still reading inherited sources.

- Audit readiness: scanned 8,003,379 records across 51 components; staged 3,838
  non-runnable audit jobs across nine languages, including all 94 FO-NL pairs.
  Refresh after reordering integration.
- Token accounting: EN-DA baseline 2,645,319,308.5 tokens per epoch;
  integer caps T/4 = 661,329,827 and T/16 = 165,332,456. Sixty exact component
  inventories and twelve tokenization cross-checks. The old helper omits
  ten-epoch normalization; use the new accounting report.
- Norwegian: preserved 5,307 conversations; explicitly omitted 4,496 ambiguous
  reasoning rows and 1,245 mixed-variant pairs. No unresolved variant holds.
- Additional DaLA: six languages registered, zero ready/imported/tokenized.
  NB has 478,930 raw pairs and FO 88,237, awaiting isolation/late exclusions;
  other four builds incomplete. Refresh rather than admit raw rows.

Reports: [audit readiness](dfm12-audit-readiness.md),
[token accounting](dfm12-token-accounting.md),
[DaLA registration](dfm12-dala-registration.md).

2026-09-24 follow-up: owner authorized proceeding with all seven CPU gaps.
Six background agents have been assigned the work below. This supersedes the
previous idle handoff state; assignment is not evidence of completion.

| Workstream | Agent | Scope |
| --- | --- | --- |
| Reordering | Boole | Expand bounded scans and reconcile native repairs / synthetic blocks with original candidates, with deduplication. |
| Cross-source checks | Poincare | Available inherited/held-out overlap checks and explicit Scandi disposition. |
| Audit readiness | Tesla | Representative multilingual samples and refreshable staged audit manifests; retain pilot approval gate. |
| Token accounting | Jason | Recover EN-DA reference budget and component token contributions without final sampling. |
| Norwegian holds | Harvey | Resolve reliable variant evidence or explicitly omit ambiguous subsets. |
| Additional DaLA | Epicurus | Discover and register complete other-thread sources; record pending manifests without duplicating generation. |

No GPU audits, identity generation, training/evaluation changes, or final DFM12
sampling are authorized by this CPU campaign. Outputs remain unaudited staging.
Agents own separate implementation/report files; this central status page is
maintained by the coordinating agent. Audit manifests must be refreshed after
reordering integration rather than treating concurrent partial output as final.

## Latest Handoff and CPU Gaps

Latest check, 2026-09-24: this section supersedes historical running/blocked
states below. The background preparation/review agents have completed their
reported tasks; no `python.*dfm12` preparation process was observed running.
All material remains unaudited; no final sampling.

| Component | Latest result |
| --- | --- |
| Six original instruction sources | All converted and pre-tokenized, including UltraChat and all three Dolci languages. |
| Norwegian / Icelandic / Faroese instructions | CPU complete: 5,307 / 8,107 / 8,609 conversations. Norwegian ambiguous variants remain held. |
| PLLuMIC main | Access now works; CPU complete: 596 conversations, 548,519 rendered tokens. |
| PLLuM-Align | CPU complete: 1,607 conversations, 926,968 rendered tokens. |
| PLLuMIC-syn-ext | Explicitly deferred; not blocking. |
| Danish increments | Scan complete; zero new eligible increments in the pinned composite. |
| Original transformations | Candidate preparation complete for all seven languages, including Polish; shortfalls remain. |
| Scandi translated instructions | Review complete; zero cleared rows. 3,201 MURI validation/test matches, 6,525 duplicates, one malformed chat; rights/attribution and variant evidence unresolved. |
| OPUS approved expansion | Complete: 1,875,532 candidate pairs across 32 direct pair groups. |
| FO-NL English-anchor fallback | 94 pairs / 188 directional examples prepared separately; audit queued; non-blocking. |

Structure-preserving repair results (isolated, not yet integrated):

| Language | Native paragraphs | Synthetic multi-sentence blocks |
| --- | ---: | ---: |
| NB | 21,731 | 5,320 |
| NN | 6,570 | 1,798 |
| SV | 11,768 | 3,525 |
| NL | 1,014 from earlier repair | 4,968 |

Scans were bounded, not exhaustive. Native candidate deficits against the
22,516 accepted-row target: NB 785, NN 15,946, SV 10,748, before audit losses.
Blocks are an explicitly different fallback task. The 191 Swedish XML-probe
candidates are alternatives, not additive. Dutch original/repair counts must
not simply be summed. New native/fallback outputs have zero document overlap;
all candidates passed source replay and actual <=4096-token rendering.
See [reordering report](dfm12-structure-preserving-reordering.md).

| CPU gap | Next action |
| --- | --- |
| Repair integration | Reconcile/deduplicate isolated paragraph and block candidates with original outputs; preserve task labels and provenance. |
| Reordering volume | Expand bounded scans, especially NN/SV/NL, and leave audit headroom; report genuine exhaustion without repetition. |
| Cross-component quality checks | Complete available inherited/held-out overlap and cross-source duplicate checks; report missing raw-source coverage. |
| Audit readiness | Build representative multilingual review samples and queues; bulk enqueue remains gated by pilot approval. |
| Token-budget accounting | Recover inherited EN-DA sampled-token baseline; report component token distributions for agreed caps. No final sampling. |
| Held instruction subsets | Resolve evidence or explicitly omit Scandi and ambiguous Norwegian subsets. No license-only DynaInstruct holds. |
| Other-thread additions | Register new DaLA sources when split/provenance manifests arrive; do not duplicate their work. |

Optional unaudited transformation/translation pre-tokenization is CPU-only but
does not replace accepted-only rebuilding after audits. Identity generation
and substantive language/coherence audits need GPUs. Detailed completed review:
[Scandi](dfm12-scandi-translated-instruct.md),
[Polish](dfm12-polish-instructions.md).

Snapshot from the 2026-09-24 preparation check. Running/queued states below
are observations at that check, not a live monitor. Update this overview as
components advance. Review-held sources are proposed additions, not approved
inclusions. Inherited DFM11 datasets are not repeated here.

**No final DFM12 sampling has been performed or requested.** Pre-tokenized
unaudited material is staging output, not an accepted training corpus.

Policy update, 2026-09-24: the owner authorizes treating **all DynaWord and
DynaInstruct licenses as acceptable across all languages**. This supersedes
license-only holds below for those families; it is owner authorization, not
independent legal verification. Preserve provenance and upstream notices.
Language, quality, format, deduplication and benchmark-overlap checks remain.
Icelandic/Faroese DynaInstruct CPU preparation was delegated to background
agent `01a0d22b-4ac5-7993-a72f-70fef9e202f9`.

## Identity and Instructions

Latest receipt check, 2026-09-24 (supersedes running/queued states in the
initial tables): all six original instruction routes have completed CPU
conversion and pre-tokenization. UltraChat NL: 192,591 conversations; Dolci
NL/PL/SV: 487,449 / 470,489 / 479,943. Norwegian preparation completed with
5,307 conversations and 2,675,108 tokens; ambiguous/mixed variants remain held.
Icelandic/Faroese completed with 8,107 / 8,609 conversations and
6,578,180 / 2,538,727 tokens. Polish Align completed with 1,607 conversations,
926,968 rendered tokens; both PLLuMIC payloads remain access-blocked (403).
Danish comparison completed over 4,402,318 input conversations, with zero new
eligible increments. These are unaudited staging results, not final acceptance.

All original transformation runs, including Polish, have completed candidate
preparation; paragraph shortfalls remain. The isolated repair produced 1,014
Dutch paragraph candidates, not yet merged into original outputs. The approved
OPUS expansion also completed: 1,875,532 candidate pairs across 32 prepared
pair groups; FO-NL remains blocked. Both directions are represented per pair.
The newly assigned structure-preserving source and Scandi-Instruct agents are
separate from these completed CPU campaigns.

| Dataset / HF source | Language(s) | Status |
| --- | --- | --- |
| New Mimir identity conversations | EN, DA, NL, NB, NN, SV, IS, FO, PL | Fact registry and generation scripts ready; 180 pilot requests queued. Not generated. |
| `schneiderkamplab/dala-english-common-pile`: acceptability + correction | English | Converted and pre-tokenized: 1,532,576 conversations. Audit pending. |
| `schneiderkamplab/dala-dutch-dynaword`: acceptability + correction | Dutch | Converted and pre-tokenized: 1,532,524 conversations. Audit pending. |
| `BramVanroy/ultrachat_200k_dutch`: training SFT split | Dutch | Downloaded; full conversion running, tokenization follows. |
| `openeurollm/Dolci-Instruct-SFT-translated`: Dutch | Dutch | Downloaded; pilot validated; full conversion/tokenization queued. |
| `openeurollm/Dolci-Instruct-SFT-translated`: Polish | Polish | Downloaded; pilot validated; full conversion/tokenization queued. |
| `openeurollm/Dolci-Instruct-SFT-translated`: Swedish | Swedish | Downloaded; pilot validated; full conversion/tokenization queued. |
| `V4ldeLund/scandi-translated-instruct` | NB, NN, SV | Held for constituent-license and evaluation-overlap review. |
| `danish-foundation-models/norwegian-dyna-instruct`: selected constituents | NB, NN | Held for source/variant checks; NorQuAD and FLEURS not selected. |
| `danish-foundation-models/icelandic-dyna-instruct` | Icelandic | Held for constituent-license review. |
| `danish-foundation-models/faroese-dyna-instruct` | Faroese | Held for constituent-license review. |
| `pelcra/PLLuMIC` | Polish | Access, schema and model-identity review pending. |
| `pelcra/PLLuMIC-syn-ext` | Polish | Access and overlap review pending. |
| `NASK-PIB/PLLuM-Align`: chosen responses | Polish | Conversion, identity filtering and deduplication pending. |
| `danish-foundation-models/dfm-dyna-instruct`: new increments only | Danish | Inherited-content comparison and constituent selection pending. |
| Further DaLA-like acceptability/correction datasets | Polish, Swedish, others | Being prepared in another thread; not yet registered here. |

## Transformations

Update, 2026-09-24: owner permits a fallback for paragraph shortages: group
contiguous sentences from one document into multi-sentence blocks, then shuffle
blocks. Label boundaries synthetic and prompt for block ordering, not recovery
of original paragraphs. Native paragraph sources remain preferred. Assigned
to the structure-preserving-source agent, with separate candidate outputs.

Each language has four intended datasets: denoising/error correction, prefix
completion, span filling and paragraph reordering. All candidates remain
unaudited. Candidate production does not imply accepted targets were met.

| Source HF repository | Language | Status |
| --- | --- | --- |
| `danish-foundation-models/dutch-dynaword` | Dutch | Candidates prepared; substantial shortfalls, especially paragraph reordering. |
| `danish-foundation-models/norwegian-dynaword` | Bokmal | Three task candidates prepared; paragraph reordering missing. |
| `danish-foundation-models/norwegian-dynaword` | Nynorsk | Three task candidates prepared; paragraph reordering missing. |
| `danish-foundation-models/swedish-dynaword` | Swedish | Three task candidates prepared; paragraph reordering missing. |
| `danish-foundation-models/icelandic-dynaword` | Icelandic | All four candidate types prepared; some shortfalls. |
| `danish-foundation-models/faroese-dynaword` | Faroese | All four candidate types prepared; shortfalls. |
| `SlayerLab/polish-dynaword` | Polish | Downloaded; transformation preparation running. |

Paragraph structure/source selection needs investigation: many windows fail
the distinct-paragraph requirement. Do not silently substitute unrelated
paragraphs or describe the zero-row tasks as completed datasets.

Update, 2026-09-24: delegated paragraph-boundary/window investigation and
conservative repair to background agent `01a0d228-7a1e-71a0-b21f-adb855235289`.
The task includes real-source inspection, regression tests and isolated
paragraph-only preparation if validated; existing candidate outputs and active
CPU jobs must remain untouched until a deliberate handoff.

## Translation

Owner follow-up, 2026-09-24: proceed with the unambiguous FO-NL English-anchor
matches. CPU preparation command `python -m dfm12.opus_fo_nl` writes isolated
`candidates/opus-fo-nl-english-anchor` records, both directions, with original
archive line numbers/hashes and English anchor retained only in provenance/audit
context. These are not direct parallel-source alignments or machine-generated
translations. Queue up to 100 bilingual audit candidates; no GPU audit starts.
The main PLLuMIC access recheck/preparation is assigned back to the Polish agent;
`PLLuMIC-syn-ext` is now explicitly deferred and must not block preparation.

Update, 2026-09-24: owner requested an English-anchor FO-NL feasibility probe,
a narrow exception to the earlier no-pivot investigation policy, not blanket
approval to include pivoted data. Tatoeba v2026-07-08 has 299 EN-FO pairs,
291 distinct English anchors. Exact-text joining with same-release EN-NL
finds 122 shared anchors, of which 94 have exactly one FO and one NL translation.
These remain probe-only: English homographs/sense differences and sentence-ID
identity need checking, followed by bilingual quality audit. No machine
translation was generated. Evidence: `data/dfm12/opus/fo-nl-pivot-probe.json`;
reproduce with `python -m dfm12.opus_pivot_probe`. FO-NL is explicitly
non-blocking for the overall DFM12 preparation.

Update, 2026-09-24: launched the approved ELRC expansion with
`python -m dfm12.cpu_translations` in detached tmux session
`dfm12-translations`. This supersedes the "not yet prepared" launch state
below: those releases are now queued/in progress, not confirmed complete.
The job reuses unchanged completed pairs and rebuilds expanded pairs.

Rows describing pair families and rows describing contributing OPUS corpora
refer to the same eventual translation components, not additive datasets.
Both directions are prepared together for joint auditing.

| Dataset family / OPUS source | Scope | Status |
| --- | --- | --- |
| English translation pairs | EN with NL, NB, NN, SV, PL: five pairs | Tatoeba candidates prepared; larger approved corpora pending preparation. |
| Non-English translation pairs | All 28 pairs among DA, NL, NB, NN, SV, IS, FO, PL | Tatoeba pass completed where available; FO-NL lacks an approved source. |
| `ELRC-2707-EMEA`, `ELRC-2725-EMEA` | EN-NL, EN-SV | Approved for preparation; not yet prepared. |
| `ELRC-401-Swedish_Labour_Part2`, `ELRC-406-Swedish_Labour_Part1` | Available requested pairs | Approved for preparation; not yet prepared. |
| `ELRC-403-Rights_Arrested` | Available requested pairs | Approved for preparation; not yet prepared. |
| `ELRC-518-www.regjeringen.no` | English-Norwegian | Approved for preparation; variant audit required. |
| `ELRC-84-Dutch_Government` | Available requested pairs | Approved for preparation; not yet prepared. |

Web-mined and other low-priority translation corpora are excluded from this
mix. Other promising OPUS sources remain review-held; see the detailed
[quality-first review](dfm12-components.md#opus-quality-first-review-2026-09-24).

## Status Evidence

Background assignments, 2026-09-24: structure-preserving NB/NN/SV source
recovery is assigned to `01a0d277-b24f-7bd1-8748-e8c1079944c8`; Scandinavian
translated instruction review/preparation to
`01a0d277-f35a-71f2-a233-c9a32bd766af`. Both are CPU-only and use isolated
outputs. Island-language preparation has completed; see its focused report.
The Danish pinned composite has no eligible increments by inherited-source
receipt comparison; its supplemental fingerprint scan is separate work.

- `data/dfm12/cpu-preparation.json`: completed downloads/conversions/tokenization.
- `data/dfm12/candidates/*/receipt.json`: completed candidate counts and checksums.
- `data/dfm12/opus/preparation-status.json`: translation pair preparation.
- `data/dfm12/opus/review-decisions.json`: per-release OPUS decisions.
- `data/dfm12/jobs.sqlite`: generation/audit queue, not preparation completion.
- `data/dfm12/cpu-{preparation,transforms,translations}.log`: operational logs.

Related: [DFM12 plan](dfm12-plan.md) and
[component preparation runbook](dfm12-components.md).
