---
type: Runbook
title: Fourth Wave Operational History
description: Dated CPU preparation, audit, repair and release handoff observations for the fourth language wave.
status: draft
confidence: medium
last_updated: 2026-10-03
tags: [dfm13, multilingual, operations, history]
---
# Fourth Wave Operational History

Moved from [Fourth Language Extension Wave](fourth-language-extension-wave.md).
Dated observations are historical, not a current completion or admission claim.

### Repair handoff monitoring (2026-10-03)

EuroBlocks upload metadata correction: its pinned dataset card supplies no
license field (also verified against the upstream card); the separately licensed
EuroLLM model is not evidence for the dataset's license. The exporter now writes
HF `license: unknown` for missing values, retains null in provenance, and states
that no additional license grant is asserted. This is accurate metadata, not
resolution of upstream licensing. Bulgarian EuroBlocks: 245 accepted rows uploaded
and remote-content hash verified. Source:
https://huggingface.co/datasets/utter-project/EuroBlocks-SFT-2512/blob/main/README.md

The incoherent Luxembourgish example carried a contradictory `topic: cooking`
alongside its astronaut-sculpture source. The wave runtime now removes that topic
hint from the generation request for grounded families, without rewriting stored
provenance. Review instructions now explicitly check generated user turns and
conceptual relations/qualifiers rather than keyword overlap. Four runtime tests
pass. New `production-probe-coherence` runs are testing this change; effectiveness
is not yet established and bulk approval remains absent.

Publication progress: Serbian Aya is now uploaded/integrated alongside Croatian
and Hungarian. Luxembourgish reached 2,047 independently accepted repairs at
this snapshot. Failed re-audits now also receive the separate schema-constrained
audit recovery (not only failed original audits); the original failed review
remains recorded. Seven focused repair/runtime tests pass. Remaining malformed
repair requests stay explicit and are not counted as accepted.

Manual inspection of the 32K production probe found false accepts: Luxembourgish
multiturn drifted from the source into incoherent cooking questions; a Belarusian
religion explanation conflated concepts. Therefore high automatic acceptance is
not sufficient for bulk approval. All 57 accepted probe candidates (9 Baltic,
48 wave-four) entered a diagnostic second review with an independent concise
language/coherence rubric checking generated user turns too. Source-audit and
repair workloads continue; synthetic bulk remains unapproved pending resolution.
The second review completed all 57 requests and correctly rejected the incoherent
Luxembourgish conversation, but still accepted the problematic Belarusian religion
answer. Thus a second prompt improves some filtering but does not yet establish
reliable semantic/language calibration for all groups; do not claim this check
resolved the false-accept problem.

All eleven Wikipedia transformation preparations finished: 2,378,641 candidates.
Their old enqueue process had exited on a nonblocking-lock collision after the
first preflight; this was confirmed terminal (no worker PID). It was restarted
from sealed outputs with the waiting queue lock. Enqueue now commits every 512
rows instead of holding one SQLite writer transaction over an entire source.
Deterministic job IDs permit safe resume of partially committed imports; a new
test verifies no duplication when the completion marker is absent.

The actual-stage probe exposed legacy 16K context and ports 8600..8607 despite
the shared servers advertising 32768 on 8800..8807. Wave-only runtime overrides
now validate the exact model and 32K teacher capacity, measure full prompt plus
completion reserve, and reject rather than truncate oversized reviews. Three
runtime tests pass. A new 32K production-path probe is running. Existing v2
prepared manifests now have intentionally stale code pins and must be replaced
by a newly prepared run-state directory after runtime validation; no bulk run
has started under stale pins. Student context remains 4096.

Superseding the earlier runtime-not-installed note below: both controllers now
use `wave_synthetic_runtime`. New `synthetic-v2` run-state directories are prepared
and verified for Baltic (140K) and wave four (770K); old empty prepared run-state
directories are retained as superseded evidence, not silently resealed. These are
not new dataset versions. `dfm12.wave_production_probe` is exercising the actual
streaming stage runner, parser, validation and independent review on one example
per language/family (12 Baltic, 66 wave-four) before production approval.

The production controller `dfm12.wave4_synthetic_campaign` has prepared and
verified `data/dfm13/wave4/synthetic`: 66 groups, 770K accepted target, source and
implementation hashes, and a calibration-approval gate. Six focused quota/recovery
tests pass. Preparation is not production launch. The calibrated generation and
review request settings must match production before approval; the current
132-case retry snapshot is 100 accepted, 28 rejected and four failed examples.

Runtime reconciliation found that the inherited pilot overrides generation to
temperature .65/.75 and repetition penalty 1.15, adds review frequency penalty
.5, and rewrites JSON schemas. `dfm12.wave_synthetic_runtime` now implements
the calibrated .3/1.1 generation policy and explicit review schema while keeping
the original CPU-validation constraints. Two focused tests verify override and
validation behavior. It is not yet installed into the sealed production runners;
that requires new implementation pins and a production-path calibration before
bulk approval. Existing sealed manifests must not be silently relabeled valid.

`config/dfm13_wave4_synthetic.yaml` records 70K accepted conversations for each
of the eleven languages (770K total, 66 language/family groups), with individual
tier evidence. Current prepared sources are small or domain/task-narrow; neither
Wikipedia-only LuxIT nor task-template-heavy FarsInstruct establishes broad chat
coverage. This follows the scarce/narrow-supply tier rather than counting raw
template repetitions as broad instruction coverage. Baltic adds 140K separately.
Calibration remains required before bulk generation; these are targets, not
completed rows. Additional native seed supply may still be needed for retries.

Calibration transport errors were predominantly `Server disconnected`, not
semantic rejects. Fresh HTTP connections are being tested as a mitigation for
possible idle keep-alive races; the cause is not yet proven. A one-off
`scripts.retry_wave_calibrations` waits for the two current client PIDs before
retrying unfinished examples once. It does not restart servers or overwrite
completed reviews. Recovery-path testing also verifies that original failed
audit attempts remain intact and cannot authorize publication without a new
positive review.

Follow-up: the repair ledger's `repair_infrastructure_failed` label also covered
malformed generated conversations (`missing_conversation`, invalid roles, empty
content), not just infrastructure outages. Do not interpret that status as a
transport diagnosis. Repair generation now uses an explicit status/messages/reason
schema. Failed legacy JSON-object repair requests receive one schema-constrained
replacement job; their old jobs/events remain. Failed new-schema jobs are not
automatically retried indefinitely. Structural checks and independent re-audit
still govern acceptance.

Wave-four seed preparation completed for all eleven languages, with 100,000
modernized-English OpenHermes seeds and distinct native document windows.
`python -m dfm12.wave4_calibration_prepare` sealed 660 calibration requests (ten
per language/family). A first 132-case pass (two per group) is running through
`dfm12.baltic_calibration --wave4 --requests ...`, with separate results under
`data/dfm13/wave4/calibration/results-run`. No production approval is inferred
from seed readiness or request preparation. Baltic calibration expanded to 120.

Persian CPU conversion is running via `python -m dfm12.wave4_farsinstruct`.
It selects one direct template per underlying train example from FarsInstruct:
FarsTail `can_you_infer`, PN-summary `summarize_the_article`, Wiki-summary
`summarize_article`, Persian-QA `answer_Q_A`, and ParsinLU comprehension
`give_short_answer`. The duplicate aggregate config, P3 translations, reverse
article generation, and unsupported rationale templates are not selected.
Up to 141,847 candidates precede context filtering/deduplication/audit; this is
not an accepted count. First entailment component: 7,266 candidates. Each source
row retains the FarsInstruct pinned revision/file/row; published attribution
must retain underlying-source provenance as well as the collection license.
The release path now recovers `underlying_dataset` and `source_template` from
the pinned source parquet using only those two columns, including for already
converted rows. Newly converted candidates preserve these fields directly.
This does not change conversation content or invalidate its audit.

`python -m scripts.advance_wave4_instructions` now advances sealed instruction
components every five minutes: imports completed reviews, queues warranted
repairs and fresh reviews, then exports/uploads/registers only fully resolved
components. Infrastructure failures remain visible and block publication rather
than being silently dropped. The separate monitor supplies pending GPU work.

The Baltic refined synthetic calibration also exposed invalid reviewer JSON:
JSON-object mode alone returned bare criterion evidence rather than the required
review contract. A new small calibration retains an explicit, unbounded-string
review schema even when generation uses JSON-object mode. This is a protocol
repair, not evidence that generation quality has passed calibration.

The corrected 12-case calibration initially produced eight structurally valid
reviews (six accepts, two rejects), three disconnected requests and one invalid
generation. Failed requests are being retried without overwriting completed
reviews; this small sample does not yet authorize bulk synthetic production.
Instruction-source failed audits (mostly output truncation or malformed JSON)
now receive a separate schema-constrained retry in the repair queue. Original
job attempts/events remain unchanged. A retry failure still blocks publication.

`scripts/monitor_dfm13_wave_campaign.py` checks shared GPU/server metrics every
120 seconds and restarts absent wave-4 audit, repair-generation, and repair-audit
clients when their respective queues have pending work. It distinguishes stages
within the same repair database and never terminates servers or other workloads.
Repair outputs must preserve non-assistant turns and pass a separate audit;
structural validity alone is not acceptance. The first Croatian component yielded
439 direct accepts and nine repaired accepts. The initially pending final repair
was rejected on re-audit (seven total repair rejections). This supersedes the
earlier pending-publication snapshot: all 448 accepted rows are uploaded to
`schneiderkamplab/dfm13-wave4-administraktor-hrvatski-dataset-v2-hr`, pinned at
`db8194519a1e64aa728c197cf1d554b3deb7c3cb`, and registered in DFM13. Downloaded
remote JSONL SHA-256 matched the local export. Tokenization is still pending.
`python -m dfm12.wave_release --root data/dfm13/wave4 --component
administraktor--hrvatski-dataset-v2-hr --upload` performs accepted-only publication
and locked registry integration; it currently handles plain single-source
instruction components, not translation/transform components.

### 2026-10-03 Continued campaign checks

The production-path coherence probes completed with 8/12 accepted Baltic
examples and 39/66 accepted wave-4 examples. Six outputs across the two probes
were malformed (generation or review); the other non-accepts were valid reviewer
rejections. These are small calibration samples, not bulk acceptance estimates;
bulk synthetic production remains unapproved pending quality assessment.

The shared servers remained busy during these checks: approximately 36.8K
completed requests/minute, 47-56% KV occupancy, and 95-100% GPU utilization.
The publication worker was restarted while sleeping to load the corrected
missing-license metadata handling and latest recovery logic. Shared servers,
audit clients, and unrelated processes were not interrupted. The detached
120-second monitoring/client-recovery process remains active.

Transformation publication is now implemented separately per task using
`python -m dfm12.wave_release --root data/dfm13/wave4 --component wikipedia-LANG
--task TASK --upload`. Unlike the earlier instruction-only limitation, this path
supports the four native transformation tasks, preserves article-level
attribution, verifies source revisions, and reads the license list from the
pinned Wikipedia card (CC-BY-SA-3.0 and GFDL). Rejected transformations are not
rewritten into invented reference answers. The detached
`scripts.advance_wave4_transforms` worker advances sealed, fully enqueued
components through audit recovery and accepted-only publication; unresolved
reviews still block publication. Each task has its own HF repository and
publication receipt. Five focused release/repair tests passed, including
task isolation, exclusion of rejected rows, and source-pin mismatch rejection.

No new raw-continuation policy, source admission for unresolved candidates,
GPU allocation or final sampling is authorized by this research document.

### Translation continuation and exhausted outputs (2026-10-03)

Controller lifecycle, BE/BS publication and the subsequent SQLite connection
fix are documented in the focused [assembly/finalizer runbook](dfm13-verified-additions-assembly.md#finalizer-runtime-checks).

The original direct-translation preparer was confirmed terminated after the old
nonblocking enqueue-lock failure. `scripts.advance_wave4_parallel` now resumes
direct and institutional preparation under the corrected locks, then calls the
existing exact-English pivot builder with an explicit wave-4 root. Only after
both preparation processes exit successfully are the English source legs frozen
for joins. Ambiguous English anchors are excluded; both source legs are retained;
resulting pivots remain unauthorized until audited. A regression test verifies
root isolation, ambiguity rejection, bidirectional output, and sealed reuse.

Superseding the earlier blanket publication block for every exhausted output:
after four failed attempts, explicitly recognized malformed model outputs may be
quarantined as `excluded_invalid_repair` or `excluded_unreviewed`. The local
`exclusions` ledger retains the job ID, stage, attempt count and error; original
jobs/events are unchanged. These are not semantic rejections and never enter
accepted-only exports. Network/transport errors remain blocking and recoverable.
This prevents a handful of malformed outputs from indefinitely withholding an
otherwise reviewed component. Seven focused repair/release/pivot tests passed.

The focused language/source-fidelity review (`dfm12.wave_language_review`) ran on
76 assembled coherence-probe candidates with no malformed reviews. All 47
previously accepted examples remained accepted, including the manually flagged
Luxembourgish example. The Belarusian encoding-error example was rejected, but
had already failed the first review. Thus this second prompt does not establish
adequate false-accept control; it must not be treated as bulk approval. Retain
these examples for a stronger-model comparison rather than repeatedly varying
the same model's rubric without evidence of improvement.

The shared monitor now adds 320 wave-4 audit requests per server when the Baltic
audit database has no pending or running work, supplementing the existing
64/server client. SQLite leases separate the two clients' work. It neither
terminates servers nor resets jobs, and checks for an existing booster before
launching another. A regression test verifies pending/running Baltic work blocks
handoff and repeated checks do not launch duplicate clients. Failed Baltic rows
remain recorded for independent recovery; draining is not a claim of full release.

### Baltic instruction release continuation

`scripts.advance_baltic_instructions` now processes the completed Baltic audits
for Lithuanian Aya, `neurotechnology/lithuanian-qa-v1`, and
`martinsu/latvian-wikipedia-qa-gemma3`. These three sources have no unresolved
source-specific export hold. The publisher uses the `dfm13-wave3-` namespace,
checks original source revisions and pinned README hashes, preserves card license
metadata, and verifies remote JSONL bytes before registry admission. All other
Baltic components remain blocked from this automatic publisher pending their
separate provenance/rights handling; audit acceptance cannot bypass that gate.
The shared monitor also starts Baltic repair-generation and independent review
clients at 32 requests/server per stage when their queues contain work. Eight
release, repair and handoff tests passed, including refusal to publish the held
Lithuanian summarization component and detection of source-card mutation.

The first Baltic audit pass finished with 5,187,548 completed jobs and 6,469
exhausted failures. `python -m scripts.recover_wave_audits --root
data/dfm13/baltic` queued 6,375 additional schema-constrained reviews and reused
94 already queued instruction recoveries. Original failed jobs and their
attempt/error history are untouched; the recovery mapping is retained under
`repair/source-audit-retries.jsonl`. This operation is idempotent, tested, and
does not treat a recovered request as accepted without its positive review.
The automatic wave-4 audit booster has started after Baltic drained. All eight
shared server endpoints remain in use; no server was stopped during handoff.

### Accepted translation selection

`scripts.select_baltic_translations --pair XX-YY` now reconciles all audited
direct, institutional and pivot shards for a requested Baltic pair. It waits on
unresolved reviews, deduplicates the exact bilingual text pair, favors direct
over pivot duplicates, and applies one shared cap using preflight-rendered
tokens for both directions. Selection uses deterministic hash order, preserves
reviews and provenance, and never inflates repeats to fill a shortfall. Source
audit and baseline-budget hashes are pinned; changed provenance cannot silently
reuse an existing selection. This is source admission preparation, not epoch
sampling. Upload and training admission remain separate steps.

Verified first selections: Faroese-Latvian has 24 accepted pairs (48 directional
conversations; 2,184 rendered tokens), and Icelandic-Latvian has 69 pairs (138
conversations; 6,244 rendered tokens). Both are far below the 165,312,851-token
non-English pair cap. Full Baltic pair selection is running in one background
CPU process, logging to `logs/dfm13/baltic/select-translations.log`.

`dfm12.wave_translation_release` now exports both translation directions as
separate native-template conversations, rechecks their rendered token totals,
bundles original OPUS attribution/README/license evidence (both legs for pivots),
and verifies remote hashes for data and attribution before DFM13 registration.
The first release is `schneiderkamplab/dfm13-wave3-opus-fo-lv`, revision
`07b47df59f62d0462fc95949f6c8bc4230c6a7f2`: 48 conversations from 24 pairs,
2,184 rendered tokens. The initial HF metadata rejection was corrected: custom
`license_link` must be an absolute HTTPS URL, not a relative README anchor.
`scripts.advance_wave_translations --root data/dfm13/baltic` now publishes further
completed pair selections automatically; partial review sets remain ineligible.

### Synthetic false-accept control set

Additional manual inspection found accepted synthetic defects in five languages,
not only Luxembourgish: Lithuanian prompt grammar, Latvian source-list counting
(31 returned versus 33 listed), Belarusian vocabulary/inflection, Slovenian
grammar plus an unsupported modifier, and Luxembourgish language/factual drift.
`config/dfm13_synthetic_quality_controls.json` records the findings;
`data/dfm13/wave4/quality-controls-evidence.json` pins the exact candidates and
their positive first-review outcomes. This is a purposive sample, not a measured
population error rate or native-speaker certification. It does not support
language-by-language bulk approval yet.

An independent 76-case Gemma 4 31B review comparison is CPU-prepared under
`data/dfm13/wave4/gemma31-quality-comparison` with candidate hashes and no supplied
prior verdicts in the reviewer prompt. It is **not running**: the eight shared
26B-A4B servers remain fully occupied with source audits/repairs. Requests must
only be sent to an endpoint explicitly serving `google/gemma-4-31B-it`, never to
the existing 26B alias. Synthetic accepted-count targets remain unchanged.

### Automatic selection follow-up (2026-10-03)

`scripts.advance_baltic_selections` waits for the live initial selector process
to exit, then revisits missing or incomplete pair receipts every ten minutes.
It leaves completed selections unchanged and uses a singleton lock plus the
existing per-pair selector locks. This closes the one-pass gap for translation
pairs whose recovered reviews finish later. The separate translation publisher
continues to verify, upload and register ready selections. Logs are at
`logs/dfm13/baltic/advance-selections.log`. Tests cover skipping immutable ready
receipts, idempotence and waiting on a live process rather than stale lock files.

### Accepted release tokenization

`scripts.tokenize_wave_releases` watches verified, uploaded wave-3/4 registry
entries. It checks the published source hash and final-target index, stages
5,000-row chunks, then uses the existing Gemma-native tokenizer with 16 workers,
thinking disabled and a 4,096-token limit. Dropped or expanded row counts prevent
registration. Array counts and lengths are checked before a locked registry
update records the actual token count. Interrupted unverified sources are rebuilt;
other registry entries are preserved. This does not sample epochs. Outputs live
under `data/dfm13/tokenized_wave_releases`, with the log at
`logs/dfm13/wave4/tokenize-releases.log`.

### Repair terminal-state correction

Two Latvian QA repair blockers were exhausted `missing_assistant_target` model
outputs, not transport failures. These now enter explicit invalid-repair
quarantine after four attempts, preserving the original job/error history.
Recovered source audits also clear their old review pointer when entering repair;
otherwise a completed historical review could hide a failed repair generation.
Quarantine checks the actual failed generation before a later review. Regression
tests cover stale completed review pointers and leave network failures unresolved.
The Baltic instruction finalizer was restarted while sleeping to load this fix;
shared inference servers and active client requests were left untouched.

### Baltic transformation publication

The source-verified publication allowlist now includes Lithuanian and Latvian
Wikipedia and ParlaMint transformations, as four separate task repos per source.
`scripts.advance_baltic_transforms` reconciles completed audits and publishes only
positive rows once all reviews are terminal. It verifies the original document
file hash against the acquisition receipt and each row's file/source attribution.
Wikipedia retains CC-BY-SA/GFDL metadata and article URLs; ParlaMint retains the
original archive URL, version, archive hash and CC-BY-4.0 metadata. This does not
release the held Europarl, fine-PDF or BLKT components. The worker log is
`logs/dfm13/baltic/advance-transforms.log`; uploaded releases are picked up by the
existing wave tokenizer. Publisher tests cover provenance mismatches and retained
holds on other components.

Verified completion on 2026-10-03: all 16 Wikipedia/ParlaMint task publications
have uploaded receipts and registry entries, totaling 223,835 accepted rows.
The transformation finalizer exited normally after all four components reported
`uploaded_and_integrated`. Tokenization continues separately; these rows do not
count toward the synthetic-conversation accepted targets.

### Wave-4 translation release handoff

`scripts.advance_wave4_selections` waits for the direct/institutional/pivot CPU
preparer's final completion marker, then freezes the registered parallel-component
hashes in `audit/translation-manifest.json`. It uses the same verified EN-DA
baseline caps as Baltic selection, combined across directions and routes, and
revisits unfinished reviews. Pairs without available source components are
explicitly recorded as supply shortfalls, not fabricated or silently fulfilled.
`scripts.advance_wave_translations --root data/dfm13/wave4` publishes ready pairs;
the wave tokenizer discovers their verified registry entries. Both workers are
started detached, logging to `logs/dfm13/wave4/advance-{selections,translations}.log`.
Tests verify waiting before preparation completes, excluding nonparallel jobs,
and refusing changed preparation after the manifest has been frozen.

### Baltic EuroBlocks release adapter

The 179 prepared Baltic EuroBlocks instruction rows (165 Latvian, 14 Lithuanian)
now enter the same repair/re-audit/publication finalizer as other Baltic
instructions. Publication pins the original DFM12 source revision and train-file
allowlist against the same-revision wave-4 source card. As with wave-4 EuroBlocks,
missing dataset license metadata stays unspecified; no model license is borrowed
or new grant asserted. Only accepted/repaired-and-re-audited rows may publish.
Tests cover the unspecified license and refusal of non-training splits.

### Synthetic control repair experiment

Moved to [synthetic calibration](dfm13-wave-synthetic-calibration.md#synthetic-control-repair-experiment).

### Lithuanian QA metadata correction

The initial release's null license is superseded: the pinned upstream card puts
its CC BY 4.0 declaration under `dataset.usage_and_licensing.licensing_information`,
not the usual top-level `license`. The publisher now reads this source-specific
declaration. `scripts.correct_baltic_qa_license` corrected the existing Hub card
and manifest at revision `b3c073c6aba1b97f1bafecd9554a1f317817f5d2`, verified both
metadata files and the unchanged data hash, and preserved tokenization fields in
the registry. No accepted rows or token IDs were changed. The card explicitly
explains historical null row-level license fields and credits Neurotechnology.

### Native synthetic seed allocation

See [seed allocation](dfm13-wave-synthetic-calibration.md#native-synthetic-seed-allocation).

### Expanded production-path calibration

See [expanded calibration](dfm13-wave-synthetic-calibration.md#expanded-production-path-calibration).
