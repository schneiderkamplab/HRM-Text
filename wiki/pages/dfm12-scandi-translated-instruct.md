---
type: Runbook
title: DFM12 Scandi Translated Instruct Review
description: Pinned Scandi evidence, historical omission, and explicitly authorized isolated CPU preparation with retained overlap annotations.
tags: [dfm12, datasets, licensing, norwegian, swedish, decontamination]
status: draft
last_updated: 2026-09-25
confidence: high
sources:
  - id: scandi
    resource: https://huggingface.co/datasets/V4ldeLund/scandi-translated-instruct/tree/5da16f97d23330fd029fec4462140433f65295d7
    title: Pinned Scandi release
  - id: muri
    resource: https://huggingface.co/datasets/akoksal/muri-it-language-split/tree/4987fc82a54145caf778efec6a682863591be1f2
    title: Pinned MURI language-split release
  - id: aya
    resource: https://huggingface.co/datasets/CohereLabs/aya_collection_language_split/tree/a3af2fde4b4cb5b2775830b11244a1a20b5f004f
    title: Pinned Aya language-split source card
  - id: alpaca
    resource: https://huggingface.co/datasets/neph1/Alpaca-Lora-GPT4-Swedish-Refined/tree/5dbae8fe27b8e8b1a69810b7a4aeb635d4461c37
    title: Pinned Swedish Alpaca source card
  - id: precursor
    resource: https://huggingface.co/datasets/V4ldeLund/da-translated-instruct/tree/ff73bcd22072bc01866cf3fe066744330abbf9c6
    title: Pinned Danish precursor with train/validation/test mixing statement
---
# Scandi Translated Instruct

## Accepted Export Support (2026-09-25)

The latest user explicitly authorizes accepted-only preparation/publication of
finished Scandi, NorQuAD/FLEURS, PL/IS and identity components, without retries.
This supersedes the earlier audit-only operational export hold, not source pins,
terminal completion, score gates, license limitations or benchmark annotations.
The exporter-support owner changed only `export_finished.py`,
`export_validator.py`, `export_licenses.py`, focused tests and documentation;
the parent runs export/upload. No production export/upload was run for this change.

Keep all five owning `--run` roots, the original unscoped `--crossscreen`,
`--incremental`, `--authorize-local-accepted-export`, and the existing Swedish
authorization. New explicit flags:

```text
--completed-dala-authorization data/dfm12/full-audit-pl-is-20260925-v1/completed-dala-authorization.json
--scoped-inclusion-authorization data/dfm12/scoped-inclusion-audits-20260925-v1/scandi/scoped-screen.json
--scoped-inclusion-authorization data/dfm12/scoped-inclusion-audits-20260925-v1/norquad-fleurs/scoped-screen.json
```

Both new flags are repeatable. The exporter uses the original completed-DaLA
validator for PL/IS and a separate pinned screen for each inclusion root.
Root ownership, exact component sets, source descriptors and transitive evidence
pins remain mandatory. It freezes only completed components with terminal jobs;
failed/unresolved decisions are recorded, not retried or admitted. Only kept
scores >=4 passing deterministic gates become student rows. The final pin checks
must exit zero before the parent starts upload. Root snapshots remain local-only.

Identity compatibility uses Boole's exact companion protocol:
`dfm12.export_identity.verify_identity_source(root, descriptor, packages)`.
The parent preserves `identity_source_manifest` in the shared root inventory and
copies the companion unchanged. Only its verified nine identity packages map to
the companion's common `source` dictionary; no prefix-based exemption or identity
package metadata rewrite is performed. The exporter preserves this descriptor
and pins its hash through completion. Optional `--identity-source-manifest PATH`
asserts the already-inventoried companion path; it does not admit an unregistered
manifest. The earlier proposed `identity_accepted_export_inventory` schema was
not retained and must not be used. All other packages require explicit audit-root
ownership as before.

The portable stdlib validator independently checks generic Norwegian only for
the exact Scandi/MURI message-bound policy or the pre-existing pinned inclusive
Norwegian policy. It does not add unrestricted `no`. Scandi license metadata
bundles pinned release/constituent cards and preserves umbrella-claim limitations;
unspecified Alpaca rights are not relabeled permissive. Existing NorQuAD passage
and annotation terms, FLORES/FLEURS notices, and DaLA per-document license,
revision, author and URL-kind fields remain unchanged. Portable license-evidence
references must match the package's hashed metadata inventory.

## Explicit Inclusion Supersession (2026-09-25)

**Superseded:** the source-level omission and Scandi MURI benchmark holds below
describe the earlier decision. The owner now explicitly requests the whole pinned
Scandi release for DA, NB, NN and SV, including Aya/Alpaca constituents, subject to
ordinary format validation, exact deduplication and teacher quality review.
The owner knowingly retains known MURI validation/test overlaps as annotations.
This is preparation authorization, **not a newly established license grant**, not
benchmark clearance and not acceptance for training or publication. Existing
license/provenance limitations remain recorded below. Other sources' benchmark
rules are not changed by this scoped Scandi policy.

New isolated implementation: `dfm12/scandi_admission.py` and
`dfm12/cpu_scandi_admission.py`. Output is
`data/dfm12/scandi-included-20260925-v1/`. The completion sentinel is
`integration.json`, published last after source/tokenizer hash checks. Partial
candidate files are not ready for audit. The user policy is serialized in
`authorization.json`; each row carries its canonical SHA256, pinned repository,
revision and original release file/ordinal. Original messages are preserved,
including arbitrary multi-turn conversations. Recovered exact MURI lineage
includes source task/subtask, original split and upstream row pointer; unknown
Aya/Alpaca/Danish MURI original task/split provenance remains explicitly unknown.

`authorized_language(record)` is a narrow boolean exception for generic `no`:
the original release label must be blank, constituent MURI, all verified lineage
must be pinned `nor`, and ordered message labels must be `no`. Complete messages
are hash-bound to the exact upstream input/output. No blank row is relabeled NB.
`authorized_muri_heldout(record)` scopes the owner override to message-bound
MURI validation/test evidence, including a pinned frozen normalized-overlap alias
when the row also has exact original MURI lineage. The parent/Tesla owns shared validator, screening
wrapper and audit queue changes; this adapter does not launch a GPU audit.

Deduplication preserves exact text, all message fields and language/target/tool
semantics. The inherited OpenHermes attribution fields are explicitly recognized;
unknown training fields are not silently discarded. The inherited originals stay
immutable and loser pointers/lineage are written to `exclusions.jsonl`.
Whitespace-normalized collisions alone are not automatic exclusions, and shared
documents do not justify dropping a conversation. Frozen overlap findings are
retained in audit context. Missing full inherited raw data, unsupported tools,
later additions and semantic/translated overlap remain coverage limitations.

Raw current Gemma4 rendering is used with thinking disabled, no Mistral fix and
no conversation truncation. `tokens.unaudited.jsonl` contains all per-assistant
prompt/response token arrays; it is an audit artifact, not a sampled training
package. Candidates remain `accepted=false`, `audit_status=unaudited`. Teacher
review must assess actual language/variant, translation quality, correctness and
training usefulness. No upload or final sampling is authorized before auditing.

Launch uses four CPU tokenizer workers with CUDA hidden and tokenizer/BLAS thread limits.
The initial attempt was stopped by its owner after discovering additional
OpenHermes attribution fields; its incomplete output is preserved under
`scandi-included-20260925-v1-interrupted-allowlist/`, without an integration
sentinel. A second incomplete attempt is preserved under
`scandi-included-20260925-v1-interrupted-repair-attribution/` after resolving four
repaired/retried OpenHermes attribution records. All 169 inherited occurrences
are now classified for exact original-message comparison. The corrected log is
`data/dfm12/scandi-included-20260925-v1-final.log`. Focused tests: 49 passed,
including a spawned CPU end-to-end fixture and independent output replay.
No shared audit, server, readiness, configuration or wiki index file was edited.

Audit handoff is `data/dfm12/scandi-admission-handoff-20260925.json`.
Tesla's `dfm12.scoped_inclusion_audit` watcher PID 2051761 was observed live;
`data/dfm12/scoped-inclusion-audits-20260925-v1/registration.json` contains the
correct Scandi integration path. Its initial observed Scandi state is
`registered_waiting_completed_integration`. Registration is not a claim that
Scandi jobs already ran: the watcher validates completed source pins before
launching audit clients against the existing eight servers.

The earlier 3,201 held-out count is a whitespace-normalized count. Strict original
messages identify 3,200 such rows plus one NN row at release shard 1, ordinal
225487: it exactly matches MURI `nor/train` ordinal 11146 and differs only in
whitespace from `nor/test` ordinal 384. Its true original split stays train;
its frozen held-out overlap annotation is retained and the scoped helper honors
the owner override. Runner `known_heldout_*` counters refer to **exact-original
lineage**; verification separately reconciles the additional normalized alias.
This distinction is not benchmark clearance or a reason to erase the old count.

`license-evidence-map.json` retains the pinned umbrella claims and unresolved
underlying rights chain. In particular, missing Swedish Alpaca grant and missing
Aya constituent attribution are not repaired by relabeling them permissive.
The pinned Danish precursor's OpenHermes MIT statement is marked as a precursor
claim, not an independently recovered direct upstream revision/license grant.

### Completed CPU Materialization

The final CPU conversion PID 2053192 exited zero after 672.6 seconds. All
1,252,683 pinned source rows were processed. Completed components remain
unaudited; these are candidate tokens, not accepted training tokens.

| Component | Candidate rows | Raw Gemma4 tokens |
| --- | ---: | ---: |
| scandi-included-da | 375,253 | 148,813,781 |
| scandi-included-nb | 267,009 | 118,201,328 |
| scandi-included-nn | 269,179 | 119,958,539 |
| scandi-included-no | 3,036 | 1,348,045 |
| scandi-included-sv | 330,633 | 134,389,570 |
| Total | 1,245,110 | 522,711,263 |

The 7,573 exclusions comprise 6,475 exact within-release duplicates, 100 exact
inherited conversations, 997 rendering/context failures and one empty/nontext
chat. All 50 excluded rows with exact MURI held-out lineage failed the ordinary
rendering/context rule, not the overlap policy. The retained known overlap pool
is 3,150 exact-original held-out rows plus the one normalized alias described
above. Of the 3,065 blank-language MURI rows, 3,036 are generic `no`; 29 fail
rendering/context validation. No blank label is invented as NB.

Source completion files are `integration.json` and `source-manifest.json` under
the isolated root. `dfm12.scandi_admission_verify` independently replays the
complete source/output partition, original messages/provenance, duplicate
representatives and token counts. It additionally rerenders the first and every
10,000th candidate per component against the raw template and compares token
IDs. This is verification, not final dataset sampling. Its log is
`data/dfm12/scandi-included-20260925-v1-verification.log`; successful replay is
recorded separately as `verification.json`. The watcher observed the completion
sentinel automatically and advanced to `validating_completed_integration`.

Subsequently confirmed: watcher-launched Scandi audit client PID **2059362** is
running under `data/dfm12/scoped-inclusion-audits-20260925-v1/scandi/`, using
the existing eight servers. Initial observed queue snapshot: 8,112 done, 4,061
pending, 1,779 running, no preparation quarantines. All five components are
registered; bounded preparation initially streams DA/NB. Audit results are
automated review signals, not a claim of full audit completion, training
acceptance or publication authorization. This preparation owner did not launch
the client or modify the shared audit runtime.

Independent verification PID **2059145 exited zero**. All 1,252,683 source rows
partition into the reported candidates/exclusions; every candidate's original
messages and provenance replay, all token records/counts agree, and 127
deterministically selected records match freshly rendered token IDs exactly.
The verification does not claim to have rerendered every token array.

The 169 inherited OpenHermes occurrences map to 164 Scandi source rows:
100 exact conversations are excluded and 64 whitespace-distinct conversations
remain with explicit overlap annotations. Whitespace can affect task content,
so normalized fingerprint equality is not silently promoted to exact semantic
equality. `inherited-overlap-disposition.json` joins every inherited occurrence
to its Scandi original file/ordinal and final disposition, using the frozen
observation database and exclusion ledger. Its SHA256 is
`9ef183325ed87f1eebcdfddcd7c2b47379f0dcdf06a9ad234a53cab11dd51fc2`.
The completed integration/source-manifest SHA256 is
`c1e8a7d98b4c1e70ea57df351c05e0bcf88c8b9efb89c0850f1382981a88fcb0`.

Remaining limitations are explicit: original Aya task/split attribution and
some underlying rights remain unresolved; Danish MURI original splits are not
locally reconstructed; full inherited raw data, unsupported tool schemas,
post-snapshot additions and fuzzy/translated overlap are not fully covered.
No benchmark-clean claim, human quality certification, final sampling or upload
was made. Parent/Tesla retains ownership of the running audit and later decisions.

## Interpreting The Findings (2026-09-25)

**Historical, superseded by the explicit inclusion decision above.**

The owner requested an explanation, not a policy change. Distinguish measured
problems from conservative unresolved-review holds: 3,201 exact MURI held-out
matches, 6,525 duplicate occurrences, one malformed chat and 3,065 blank language
labels are measured. Missing constituent attribution/split IDs (especially Aya)
and unsupported NB/NN evidence are review limitations, not proof that every row
is low quality or legally unusable. The 3,201 are upstream MURI validation/test
matches, **not a claim of 3,201 matches to our current EuroEval suite**.
No fluent-language/answer-coherence audit of this entire collection was run.

The full omission is deliberately conservative. A smaller recoverable pool could
be reconsidered by tracing original task/split IDs, removing known held-out and
duplicate rows, preserving upstream attribution, and auditing language and answer
quality. Known exact MURI lineage is easier to recover than Aya's lost mixture
metadata. No Scandi admission or running audit was changed during this review.

## Applied Screening Exclusions

2026-09-24 user supersession: the earlier gate-only handoff below is historical.
The user now explicitly requested materialization into separate filtered
candidate components. `dfm12/screening_application.py` owns this operation;
`dfm12/screening_application_verify.py` independently replays retained rows
and exclusions. Neither module modifies original source outputs or shared
audit-readiness/configuration code. Output root:
`data/dfm12/screened-candidates-20260924-v1/`.

Completion must be established by `application-manifest.json`, `integration.json`
and `verification.json`, not the existence of partial candidate files. All
outputs remain unaudited. Original tokenized outputs are not filtered outputs
and must not be substituted for them. No tokenizer template, sampling,
training, evaluation, GPU process or server is changed by this operation.

Verified outcome: 20 materialized components, 2,342,773 input rows,
2,342,053 retained, 720 excluded. Exclusions comprise 299 exact semantic
duplicates, 415 superseded Dutch paragraphs, and six held-out row copies
(five distinct IDs). The canonical registration contains 16 components and
2,323,770 retained rows with 710 exclusions; four historical alternatives are
not registered. Both original Norwegian held-out IDs are removed. Fresh
reordering checks additionally found NB punctuation validation ordinal 66,
NB punctuation test ordinal 108, and MURI Norwegian validation ordinal 350
in the NN block pool. The known NB test-48 ID was removed from both original
and integrated copies. All 5,741 inclusive Norwegian rows are retained.

Follow-up covers 256,360 integrated reordering rows plus the 5,741 inclusive
Norwegian rows. It found no exact inherited-chat matches or unresolved active
chat matches in those additions. The full replay confirms every retained row
is unchanged, all 720 exclusions and 299 semantic duplicate decisions replay,
and input hashes are unchanged. `duplicate-resolution.json` records 24 Dolci
collision groups differing in language labels; these are conservatively kept.
Tests passed: 150 (two multiprocessing-fork deprecation warnings), including
seven focused screening tests; OKF validation has zero errors/warnings.
Read-only readiness discovery loaded 61 components, including all 16 filtered
registrations. No shared readiness refresh was run.

Parent/Tesla handoff: `data/dfm12/screening-application-handoff-20260924.md`
and output-root `handoff.json`. Materialization PID 1143276 and verification
PID 1152279 exited successfully. Logs are
`data/dfm12/screened-candidates-20260924-v1.log` and
`data/dfm12/screened-candidates-20260924-v1-verification.log`.

Duplicate decisions use exact JSON after excluding only `id`, `provenance`,
`audit_context` and `rendered_tokens`. Language, task, assistant target indices,
complete multi-turn messages, reverse messages, tools, extra message fields
and unknown top-level fields remain significant. Whitespace-normalized chat
equality alone is not enough to remove a row. Registered canonical components
precede historical alternatives; deterministic component/ordinal order selects
the representative. The exclusion ledger preserves loser attribution and
the representative pointer. This dedup scope is the previously flagged rows
plus new integrations, not a fresh full-corpus semantic deduplication.

Shared documents and original-window overlaps alone do not trigger removal.
The Dutch legacy paragraph-reordering task is separately superseded by the
reconciled integration; other Dutch tasks are retained. Norwegian inclusive
additions and all eight integrated reordering components are freshly compared
against the six available held-out files and the frozen inherited-chat index.
Inherited exact-chat hits are quarantined; active-source chat matches without
resolved exact training semantics remain explicit follow-up review signals.
The original missing-corpus, unsupported-tool-schema, fuzzy/translated and
full-evaluation-suite coverage limitations remain in force.

Parent/Tesla consumes the filtered `integration.json` **after verification**,
last after any original integration registrations. It supersedes matching
component names, not unrelated components. The old `CrossScreen` hashes and
blanket duplicate/shared-document vetoes are not automatically updated:
the readiness owner must bind the application manifest and verified filtered
hashes, retaining hard held-out gates and unresolved coverage. This worker does
not edit `audit_readiness.py`, refresh shared queues, or activate audit jobs.

## Final Disposition And Cross-Component Follow-Up

2026-09-24 continuation: **Superseded: the open-ended Scandi holds below.**
All constituent/language subsets of revision
`5da16f97d23330fd029fec4462140433f65295d7` are now **explicitly omitted from
current DFM12 preparation**, not queued for automatic later admission.
This does not erase the original license/provenance evidence or assert that
independently sourced copies are unlawful. Reconsideration requires new
constituent-specific evidence and review. Admitted/pre-tokenized Scandi rows
remain zero. The omission covers all 1,252,683 rows, including Danish and
blank-language rows outside the original requested languages.

Machine-readable disposition:
`data/dfm12/scandi-cross-component-20260924-v1/scandi-disposition.json`.
It records every source/language/model subset, original row count, reason,
source revision and prior receipt hash. No shared source approval or sampler
configuration was changed.

The dedicated CPU cross-component audit uses `dfm12/scandi_overlap.py` and
`dfm12/scandi_overlap_finalize.py`. A frozen discovery manifest covers 143
files: 51 current candidate files, 11 separately owned repair alternatives,
71 available inherited files, four omitted Scandi shards, and six held-out
files. Total source size is approximately 24.2 GB on disk. Historical pilots,
superseded island/repair versions and duplicate tokenizer-input copies are
not independent components and are deliberately excluded.

Checks preserve complete role-aware conversations, compare OPUS reverse
directions separately, and additionally match entire messages/source windows
against available held-out text at a minimum of 160 normalized characters.
Whitespace is normalized; case, punctuation and turn boundaries are retained.
There is no substring, fuzzy, translated or semantic matching. Short labels
such as yes/no are not evidence of held-out-text contamination. Messages with
tool-call metadata or nontext content are counted as unsupported rather than
stripped. Full-chat hashes cover role/content, not top-level tool definitions
or target-message selection; owner resolution must inspect original metadata.

Output root: `data/dfm12/scandi-cross-component-20260924-v1/`.
Log: `data/dfm12/scandi-cross-component-20260924-v1.log`.

- `coverage.json`: discovered paths, sizes/mtimes, scanned SHA-256 hashes,
  row/view/schema counters, explicit missing coverage and completion state.
- `observations.sqlite`: every comparable chat hash, component/file identity,
  zero-based row ordinal, direction and original row ID. Hashes link back to
  the unchanged source payloads; the audit does not republish training text.
- `collision-groups.jsonl`, `component-pairs.json`: raw diagnostic collisions
  and shared unique-hash counts, not accepted source selections.
- `heldout-text-hits.jsonl`: exact long-text evidence with source/held-out
  file IDs, ordinals and fields; multiple field hits can concern one row.
- `heldout-quarantine.jsonl`: **two active candidate rows excluded from audit
  export until resolved**, with consolidated matching fields. This is separate
  from full-chat duplicate flags and must not be omitted during gate intake.
- `audit-gates.jsonl`, `flagged-chat-rows.jsonl`, `audit-manifest.json`:
  final owner-action gates and row references, per-component results and
  post-scan file-drift checks. Prefer these gates to preliminary actions in
  `collision-groups.jsonl`.
- `source-observations.sqlite`, `source-overlap-groups.jsonl`,
  `source-overlap-coverage.json`: supplementary comparisons across the 17
  original-transformation and repair-alternative files. These compare exact
  original source windows and same pinned repo/revision/file/source-ID, not
  inferred cross-release article identities. Shared documents across tasks
  are review signals, not automatically duplicate training examples.
- `verification.json`: output checksums, all observation/flag counts and replay
  of the three active held-out field hits from their original source records.
- `legacy-heldout-notice.json`: append-only notice of one independently replayed
  inherited OpenHermes/MURI-test overlap; no legacy training/eval changes.

Exact held-out chat matches must be excluded; exact long-text matches require
quarantine/review. Inherited and active cross-component duplicate matches
require owner resolution before acceptance. Overlap only with omitted Scandi
is informational, not grounds to reject otherwise valid independent provenance.
Alternative repairs remain comparison components, not additive selections.
No candidate file is rewritten or accepted by this audit.
Representative observations are evidence pointers, not automatic keep-winner
decisions. Flagged directions retain their original complete conversation.
Apply gates only against the recorded file hashes. Reordered or revised exports
need source-ID/content-hash reconciliation or a fresh scan, not blind reuse of
the old ordinals. Inherited acceptance is explicitly unchanged/comparator-only.

Coverage limitations: only locally available inherited raw chats are scanned,
not the full DFM11 corpus. The available held-out payloads are MURI nor/swe
test/validation and Norwegian punctuation test/validation. DaLA, UltraChat,
Dolci, island-language and Polish held-out payloads were not locally discovered.
NorQuAD/FLEURS/FLORES, full benchmark suites, new other-thread DaLA payloads,
future integrations, identity generations and article-level overlap remain
outside coverage. A no-hit result is **not decontamination clearance**.
The final manifest captures the six-language DaLA registration state and
receipt hash without reading or altering the producer's unfinished payloads.
Full-chat collision exports focus on additions/alternatives/omitted Scandi;
inherited-only groups are not an independent audit of all legacy training.

Reproduce into a new audit root, then finalize after scan completion:
Use `/home/ucloud/miniforge3/envs/hrm/bin/python` for these commands.

```bash
python -m dfm12.scandi_overlap --output data/dfm12/NEW-SCANDI-AUDIT
python -m dfm12.scandi_overlap_finalize --root data/dfm12/NEW-SCANDI-AUDIT
python -m dfm12.scandi_overlap_finalize --root data/dfm12/NEW-SCANDI-AUDIT --verify
```

Both commands refuse existing final outputs and use a dedicated nonblocking
writer lock. The scan uses one low-priority CPU worker (nice 10), empty CUDA
visibility and bounded Arrow/BLAS threads. Other agents' outputs are read-only.

### Completed Snapshot Results

| Scope | Files | Input rows | Comparable chat views |
| --- | ---: | ---: | ---: |
| Current additions | 51 | 8,003,379 | 9,879,005 |
| Separate repair alternatives | 11 | 56,885 | 56,885 |
| Available inherited sources | 71 | 7,583,981 | 6,167,712 |
| Held-out references | 6 | 3,700 | 3,200 |
| Omitted Scandi | 4 | 1,252,683 | 1,252,683 |
| Total | 143 | 16,900,628 | 17,359,485 |

Views include both directions of 1,875,626 OPUS pairs. They are schema-comparable
role/content records, **not accepted or structurally certified training rows**.
The inherited comparator has **1,416,269 unsupported chat-schema rows**, largely
native tool records. Another 500 punctuation references are field-screened but
not represented as conversations. Those gaps are not silently counted as clear.

**Active held-out quarantine: two distinct rows, three field hits.**

| Candidate | Zero-based ordinal | Held-out evidence | Replayed match |
| --- | ---: | --- | --- |
| `candidates/dynaword-no/candidates.jsonl` | 366300 | Punctuation validation row 69, `original_text` and `corrupt` | Entire assistant target, 261 normalized characters |
| `data/dfm12-sentence-blocks-20260924-v3/candidates/nb/candidates.jsonl` | 4096 | Punctuation test row 48, `original_text` | Entire assistant target and original audit-context window, 767 normalized characters; one row, not two |

The first path is relative to `data/dfm12/`. Exact UUIDs, file hashes, source
field hashes and held-out file IDs are in `heldout-quarantine.jsonl` and
`verification.json`. Both are fail-closed audit-export gates, not claims that
the original owner files were edited. No active addition had an exact complete
conversation match to the available inherited or held-out chat comparators;
that does **not** waive these observed held-out target/source-text matches.

**Full-chat duplicate gates: 180 unique groups, 505 view occurrences.**

| Finding | Unique chat hashes | View occurrences |
| --- | ---: | ---: |
| Within original Icelandic transformations | 92 | 296 |
| Within original Polish transformations | 53 | 139 |
| Dolci PL versus Dolci SV | 24 | 48 |
| Original Dutch transformations versus Dutch paragraph repair | 2 | 4 |
| Native Swedish alternative versus Swedish XML-probe alternative | 9 | 18 |

Thus there are **145 within-component groups** and **35 cross-component
groups**, with 435 and 70 flagged view occurrences respectively. No automatic
winner selection or deletion was performed. The 9,850 remaining diagnostic
collision groups concern omitted Scandi/reference material, not active-addition
duplicate gates.

The supplementary 17-file scan replayed **1,464,840 transformation/alternative
rows**, finding **22 shared original-window groups** and **1,806 shared pinned
document-reference groups** across components. These counts are different
features, not additive distinct-document counts. Most involve original Dutch
transformations and the Dutch repair/block alternatives; nine shared windows
link the two Swedish alternatives, and one links original Norwegian material
with the native NB alternative. Keep these as document-level review signals;
different tasks on one source document are not automatically duplicate chats.

**Legacy notice:** inherited OpenHermes English
`data/train-00003.jsonl.gz`, ordinal **2762**, exactly matches MURI Swedish
test ordinal **279**, and also occurs in omitted Scandi. Independent replay
verified both file hashes, the 466-character normalized prompt, and the entire
conversation equality. The full-chat hash is
`eb60b813cd40944f36f966e8dcf056fefc0bb990e0d5dd7ae675b8c8b6631d36`.
This is recorded in `legacy-heldout-notice.json` for owner review; existing
training/evaluation files, acceptance and running jobs were not changed.

The input snapshot was stable at finalization; no additional files appeared
within the frozen inventory's discovery scope. The captured other-thread DaLA
registration has six registered sources, zero ready/imported sources, and
unfinished producer finalization. It is explicitly outside payload comparison.

Main scan PID **972088**, finalizer PID **1028808**, and verification PID
**1032051** completed and exited. Each stage used one low-priority CPU worker;
main-scan RSS stayed about 270 MB with three OS threads (bounded Arrow runtime).
Verification rehashed **11 output artifacts**, checked all **17,359,485** SQLite
observations and all **505** flagged row references, and independently replayed
the three active held-out field hits. The legacy replay was an additional
read-only check recorded in the append-only notice.

Logs:
`data/dfm12/scandi-cross-component-20260924-v1.log`,
`data/dfm12/scandi-cross-component-20260924-v1-finalization.log`, and
`data/dfm12/scandi-cross-component-20260924-v1-verification.log`.
The combined Scandi/overlap/core/Norwegian test run passed **111 tests**, including
source-window distinction, whole-row held-out gates, source replay, changed-file
detection, immutable finalization, and unchanged inherited acceptance.
Final OKF validation passed with **zero errors and zero warnings**;
`git diff --check` passed. Recorded scan/finalizer implementation hashes still
match the finished code. No task-owned process remained at the final check.
The earlier training PID 205421 was no longer present at this later check;
this worker issued no stop/start/signal commands for it or any other job.
No GPU, final sampling, tokenization, training/evaluation change or recursive
agent work was performed in this continuation. Parent owns shared-file intake.

## Decision

CPU review completed for all four pinned release shards on 2026-09-24.
**No constituents are cleared by this review: prepared conversations 0,
pre-tokenized examples 0, rendered training tokens 0.** This is a conservative
hold, not a declaration that every row is legally unusable. No tokenizer was
run on held data and no accepted export was made. User authorization for all
DynaWord/DynaInstruct licenses does **not** extend to this separate collection.

Related: [DFM12 plan](dfm12-plan.md),
[Norwegian DynaInstruct review](dfm12-norwegian-dynainstruct.md),
[Danish inherited review](dfm12-danish-increments.md), [OKF rules](/schema.md).
Shared config, catalog, source lock, prepare/status files, indexes, training,
evaluation, sampling and active jobs were not changed. Parent owns indexing.

## Constituent Decisions

The Scandi card marks the release `other`, claims Apache-2.0 for MURI/Aya,
and explicitly notes the unspecified Swedish Alpaca license. Upstream pins
here are independently resolved review snapshots, **not** proven revisions
used by the Scandi builder. Exact row matching provides stronger provenance
for MURI than the composite card alone.[^scandi][^muri][^aya][^alpaca]
None of the five review repositories has a separate LICENSE/LICENCE/NOTICE
file at these pins. Card declarations are retained as claims, not independent
legal clearance or permission to discard original-work attribution.

| Constituent | Requested-language rows | Decision and blockers |
| --- | ---: | --- |
| Aya | 791,268 | Hold. Apache-2.0 umbrella claim is retained, not treated as approval of every original dataset. Original dataset/task/template IDs, attribution and splits were dropped. Requires constituent-level rights and benchmark review; no blanket approval. |
| MURI Swedish | 16,800 | Hold. Apache-2.0 card describes original Wikipedia/CulturaX outputs and NLP-task mixtures. Exact upstream matches restore task/split labels but do not restore per-document URLs/authorship for the web/Wikipedia text. No blanket relicensing of that text; Super-Natural Instructions tasks need separate policy/license/benchmark review. |
| MURI NB/NN | 12,135 | Hold for the same lineage/rights issues plus unsupported orthographic variant labels. Upstream `nor` is a macrolanguage, not NB/NN evidence. |
| Swedish Alpaca | 52,002 | Hold. Pinned card has no license grant and links to another Alpaca-derived dataset; cleaning descriptions do not resolve the rights chain. |
| Danish and blank-language rows | 380,478 | Exclude from this NB/NN/SV request. No inference from blank labels. Danish OpenHermes is already an inherited source family. |

For MURI, the exact-matched pool includes 14,842 Wikipedia rows, 15,158
CulturaX rows, and 2,000 Super-Natural Instructions rows. Tasks include
Europarl translation/classification/language identification, ECDC translation,
and OPUS Books translation. Those counts include upstream held-out splits.
The selected repository schema has no original document URL/author field.
Retaining the MURI repository citation is not asserted to resolve attribution
for all underlying works. This hold is intentionally stricter than accepting
the composite's umbrella license note.[^muri]

Aya's separately pinned collection card at
`09069079fad96ad9c7f8781be8c1d70471dfa768` lists translated CNN/DailyMail,
Dolly and FLAN subsets including CoQA, CoT, LAMBADA and QA. This establishes
mixture-level contamination risk, **not** that every such subset occurs in
these Scandi rows. Its original subset IDs cannot be recovered from Scandi's
four columns alone. The precursor explicitly documents merging train,
validation and test data; its `train` release name is not upstream split
clearance.[^precursor]

## Census And Labels

Actual schema in all four Parquet shards: `language`, `model`, `source`
strings and `messages: list<struct<content: string, role: string>>`.
Every conversation has two messages. The adapter nonetheless preserves all
turns, roles and content and is tested with multi-turn input; it does not
flatten conversations or put attribution/model labels into prompts.

| Actual language | Aya | MURI | Alpaca | Danish OpenHermes | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| NB | 263,756 | 5,119 | 0 | 0 | 268,875 |
| NN | 263,756 | 7,016 | 0 | 0 | 270,772 |
| SV | 263,756 | 16,800 | 52,002 | 0 | 332,558 |
| DA | 263,756 | 15,000 | 0 | 98,657 | 377,413 |
| Empty string | 0 | 3,065 | 0 | 0 | 3,065 |

Total **1,252,683** rows. The four language totals in the card sum to only
1,249,618; the full scan locates the missing 3,065 as empty-string MURI labels.
No blank/generic Norwegian label is mapped to NB. Aya NB/NN are declared
translation targets, not a completed fluency or orthography audit. The MURI
NB/NN/blank partition matches the generic upstream `nor` pool; no pinned
builder code was available in the Scandi repository to substantiate the split.

Structural validation: **1,252,682 valid chats**, one empty/nontext-content
rejection, zero multi-turn chats. Whitespace-normalized role-aware full-chat
fingerprints: **1,246,157 unique**, **6,525 duplicate occurrences**. These are
review statistics over held/excluded data, not 1.2M converted candidates.

## Contamination And Overlap

All **32,000** NB/NN/blank/SV MURI conversations exactly match the pinned
upstream `nor`/`swe` files after whitespace normalization. The 15,000 Danish
MURI rows do not match those language files and were not traced further.
Original upstream metadata is restored in `muri-lineage.jsonl` by composite
shard/ordinal and hash, preserving every matching upstream candidate rather
than guessing when matches are ambiguous.

**3,201 Scandi conversations match upstream held-out content:** 1,601 test,
1,600 validation. Two also have train matches and must still be excluded.
Ten Scandi rows have multiple upstream matches. The receipt's raw match-edge
counts (28,857 train, 1,601 test, 1,600 validation) are not disjoint row counts.
This is measured split leakage, not merely a speculative benchmark concern.

Exact comparison with all **11,053** locally downloaded Norwegian DynaInstruct
Magpie/Samtale/punctuation chats found **zero** hits. Separately comparing the
**5,307** prepared Magpie/Samtale chats also found zero. These are overlapping
comparison scopes, not 16,360 distinct source examples. Input hashes are in
the receipt. NorQuAD/FLEURS were not downloaded for this comparison.

Inherited comparison scanned **1,885,429** rows in 20 local DFM11 OpenHermes
DA/EN source-cache files; **1,885,424** had comparable chat schemas and five
were unsupported. It found **169 exact matching inherited row occurrences**:
168 against Danish OpenHermes and one against Swedish-labeled MURI. This is
not a count of unique inherited duplicate conversations. It does not
reconstruct the full inherited corpus, compare substrings,
article identities, translations or paraphrases, or establish benchmark
clearance. The immutable inherited-policy snapshot is separately hashed.
The per-shard verification report is authoritative for measured overlap.

## Operations

Implementation: `dfm12/scandi.py`, `dfm12/cpu_scandi.py`,
`dfm12/scandi_verify.py`; tests: `tests/test_dfm12_scandi.py`.
Root: `data/dfm12/scandi-review-20260924/`.

- `evidence.json`: 15 pinned cards/data files with URLs, sizes and SHA-256;
  1,091,998,084 bytes total, including 1,049,943,636 bytes of Scandi Parquet.
- `receipt.json`: complete census, schema, holds, Norwegian overlap,
  tokenizer hashes, explicit `accepted: false`, `audit_status: unaudited`.
- `fingerprints.sqlite`: disk-backed full-chat fingerprints and MURI lineage.
- `muri-inventory.json`, `muri-lineage.jsonl`: task/split census and exact joins.
- `verification.json`: evidence rehash, DB count, inherited source comparison.
- `diagnostics.json`: held-out row counts, LFS checks, extra pinned Aya card.
- Logs: `data/dfm12/scandi-review-20260924.log` and
  `data/dfm12/scandi-review-20260924-verification.log`.

Raw current tokenizer is `data/dfm11_tokenizer/tokenizer.json`, SHA-256
`12bac982b793c44b03d52a250a9f0d0b666813da566b910c24a6da0695fd11e6`;
Gemma4 template is `data/dfm11_tokenizer/chat_template.jinja`, SHA-256
`d8ae62ccf8e47299c8e912a86b16e93bf6b195d24e8b06fffb865e061e89f07e`.
No Mistral fix, template rewrite, tokenization or length truncation occurred.
Nothing is staged as accepted or sent to GPUs.

Run from repository root with `/home/ucloud/miniforge3/envs/hrm/bin/python`:

```bash
python -m dfm12.cpu_scandi --root data/dfm12/NEW-SCANDI-ROOT
python -m dfm12.scandi_verify --root data/dfm12/NEW-SCANDI-ROOT
python -m dfm12.cpu_scandi --root data/dfm12/NEW-SCANDI-ROOT --diagnostics
python -m pytest tests/test_dfm12_scandi.py -q
```

The runner refuses an existing census root, verification/diagnostics refuse
existing final receipts, and all commands share a nonblocking single-writer
lock. CPU worker count is one; CUDA visibility is empty; BLAS/Arrow/Rayon and
tokenizer concurrency are bounded. Starting affinity was 384 CPUs and load
11.78/18.13/21.73. Census PID **674513** completed and exited.
Verification PID **677132** also completed and exited. All 15 original
evidence files rehashed correctly; all ten Parquet files matched upstream
LFS SHA-256. Supplemental diagnostics completed successfully and reacquired
the shared Scandi lock. No task-owned process remains live. The existing
training process **205421** was still live at the final process check and
was not signalled or changed. Available memory/disk during verification were
1.4 TiB / 2.0 PiB; verification remained one OS thread.

The dedicated regression suite passed **22 tests**; the combined dedicated,
core DFM12 and Norwegian suites passed **92 tests**. OKF validation reported
only this page's expected missing parent-owned index link, with zero warnings.
Remaining gates are
underlying rights/attribution, task-level approval, supported NB/NN labels,
broader inherited/benchmark decontamination, and quality audit. Do not rerun
with generic catalog approval or apply DynaInstruct authorization to bypass
these gates. Parent must add this focused page to `wiki/pages/index.md`.

[^scandi]: Locally retained pinned card and four full Parquet shards.
[^muri]: Locally retained pinned card and all six nor/swe train/validation/test shards.
[^aya]: Locally retained pinned language-split card; no blanket constituent approval.
[^alpaca]: Locally retained pinned card lacks an explicit license grant.
[^precursor]: Locally retained pinned Danish precursor card describes split merging.
