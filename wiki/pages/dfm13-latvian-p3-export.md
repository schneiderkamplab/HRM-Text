---
type: Runbook
title: Latvian P3 Rights-Separated Export
description: Isolated review-only CC BY and CC BY-SA packages with source membership and repair lineage checks.
status: stable
confidence: high
last_updated: 2026-10-03
tags: [dfm13, baltic, latvian, licensing, export]
---
# Latvian P3 Rights-Separated Export

**Current status, 2026-10-03: both entire P3 partitions are on
`quality_hold_source_fidelity`.** This supersedes initial `accepted_uploaded`
eligibility and the proposed eight-row filtered replacement. Existing upload and
tokenization receipts remain historical provenance, not quality clearance.

Whole-source hold evidence is under
`data/dfm13/latvian-p3-quality-hold-20261003-v1/`; the detailed superseding report
is `docs/reports/dfm13_latvian_p3_source_hold_20261003.md`. Registry changes were
atomic and retained repeats, data pins and tokenized artifacts. HF warning-only
commits are `a64b01b3fbc93eb203c67c868989cb5f0bbe446b` (CC BY) and
`4a53cf0c80f37d27b3d64d5c5fa014e43dfdc7ff` (CC BY-SA); all non-card blobs were
verified unchanged. The scoped publisher cannot clear this hold on rerun.

Full CPU review packets cover 7,680 rows under
`data/dfm13/latvian-p3-english-alignment-20261003-v1/review-v2/`, with 9,844
English raw source rows cached at a pinned revision. Exact config/question lookup
does not establish a bilingual bridge: 20 manually checked pairs are verified,
7,639 positional proposals remain unverified and 21 English-question matches are
ambiguous. No ordinal-only pairing is certified. Twenty audit and eight repair
calibration requests target Gemma 4 31B; none were sent. Full candidate questions
and answers are preserved. No 26B call, GPU job or filtered v2 release occurred.

### CPU Content Queue, 2026-10-03

The current full 31B review handoff is
`data/dfm13/latvian-p3-content-alignment-20261003-v1/fused-review-v2/`:
7,680 pending jobs, zero attempts, with byte-identical packet hashes and job
counts verified by an actual resume. It combines pinned CPU E5 retrieval and
character TF-IDF with separately labelled unverified positional alternatives.
All questions, answers and alternate source references remain intact. Only the
previous 20 manual bridges are verified; no ordinal or retrieval score certifies
a bilingual pairing. Content retrieval finds the known reference for 11/20
existing diagnostic cases, insufficient for automatic alignment and not a
population accuracy estimate. Uncalibrated per-row probability bounds are [0,1].
Both whole-source holds remain authoritative. Preparation commands, uncertainty
details and hashes are recorded in
`docs/reports/dfm13_latvian_p3_content_alignment_20261003.md`.

The separate executable protocol queue is `consumer-v1/` under that same root;
it leaves the fused packet sealed and adds bidirectional literal pairing checks.
Both inventories have all 7,680 full native 31B renders checked: largest totals
including 8,192 output tokens are 15,838 (fused) and 16,070 (consumer), below
32,768, with no truncation. Tokenizer and per-job receipts are in each root.
The resumable consumer is prepared but **not launched**. Model decisions never
certify pairing or admit data. Repair requires a separate independently verified,
hash-bound source-pairing receipt; complete proposed repairs automatically acquire
fresh re-audit jobs, including restart reconciliation. No GPU/server change or
review call was made.

Bulk-gate clarification: independent pairing receipts need not be human-authored
per row. A calibrated 31B comparison plus a separate blind full-evidence check can
support versioned model-verified receipts; the blind-check/receipt adapter is not
yet implemented. Same-model calls are correlated, so agreement alone is not
certification. Ambiguous or conflicting matches must terminate as rejects, not
permanent human-approval waits. Pairing, translation fidelity and answer quality
remain distinct; completion means all 7,680 rows dispositioned, not all accepted.
The proposed protocol and remaining implementation gap are detailed in the
content-alignment report. Existing source holds and sealed queues are unchanged.

The preceding missing-adapter claim is superseded by the later 2026-10-03 CPU
implementation: `dfm12.latvian_p3_pairing` and isolated `blind-calibrated-v2/` now
prepare two blinded review paths for all 7,680 rows plus 140 diagnostic controls
(84 development / 56 heldout). Calibration is not yet run. The adapter produces
explicitly model-verified, never human-labelled receipts only after calibration;
uncertain/disagreeing pairs terminate as rejects. One repair proposal and a fresh
re-audit are permitted per row, with bounded transport attempts. All reviewed
candidates remain unadmitted. Its run entry point uses the strict shared31B
model/context/snapshot health gate; do not launch the old low-level consumer
directly. Detailed commands, control limitations and test evidence are in
`docs/reports/dfm13_p3_blind_pairing_handoff_20261003.md`. No GPU call was launched.
The earlier blind-v1 draft is preserved but superseded because its whitelist
omitted the original translated-source question/answer. V2 retains those in
addition to complete published conversations and English alternatives; this
allows reviewers to inspect repair-induced input drift. No inference used v1.
All 15,640 initial v2 requests (two passes plus both control paths) pass the actual
31B native-template preflight, maximum 11,780 tokens including 8,192 output
reserve, no truncation. The guarded protocol and endpoint tests total 58 passes;
actual model calibration is still pending, not certified.

Shared-server execution audit: the original pairing CLI was one-endpoint serial.
New isolated `dfm12.latvian_p3_dispatch` reuses the sealed queue with up to eight
endpoints, one worker each by default, a single aggregate attempt budget and strict
all-endpoint prechecks. Root/shared P3 locks prevent duplicate P3 dispatches; they
do not constrain foreign clients. It requires the transition's actual terminal76
receipt and never repeats that client. Handoff ownership still governs later
comparison phases and shared capacity allocation. Bulk commands and limitations
are in the blind-pairing handoff report; no frozen module or prepared packet changed.

Implements only the Latvian P3 partition policy from
[Baltic publication rights](dfm13-baltic-publication-rights.md).
`dfm12/latvian_p3_export.py` and `tests/test_latvian_p3_export.py` are isolated
from shared publishers and the separately owned BLKT implementation.
The initial preparation had no upload, registry integration, tokenization or
training admission enabled. This preparation-only restriction is superseded for
the two cleared partitions by the explicit owner publication authorization below;
the four unclear/restricted constituents remain held.

## Partition Contract

- CC BY 4.0: QuaRTz and WebQuestions only.
- CC BY-SA 4.0: ARC-Easy and ARC-Challenge only.
- Held: MRPC (restricted MSR terms), WikiQA (research terms), OpenBookQA and
  QuaRel (primary data grants unverified). Positive quality decisions do not
  clear these rights holds.

The exact configuration, train split, pinned translated source revision, original
file hash/ordinal and family must agree with the sealed candidate membership.
Only `accepted` and `accepted_repair` rows with positive schema-valid audit
scores are prepared. Repairs retain the parent, corrective content ID and
repair/re-audit job IDs; nonassistant context cannot change. Original provenance
is retained, with partition metadata added outside assistant messages.

Each partition includes `data/train.jsonl`, `LICENSE.txt`, `NOTICE.txt`, original
translated-source card and primary constituent evidence. The dated changes
notice distinguishes upstream translation, formatting, selection and marked
assistant repairs. Files are hash-pinned. All rows and manifests remain
`admission_authorized=false`, `uploaded=false`, pending package review.

Primary source snapshots and full CC licenses were fetched and inspected on
2026-10-03 under `data/dfm13/latvian-p3-rights-evidence-20261003/`.
`evidence.json` records URLs, retrieval dates and content hashes; ARC/QuaRTz
publisher cards and Stanford's WebQuestions release state the respective grants.
This archives the evidence previously referenced only by live URLs; it does not
assert a blanket license for translated P3 or provide legal certification.

## Prepared Partial Snapshot

`data/dfm13/latvian-p3-rights-preview-20261003-v1/manifest.json` records:

| Partition / constituent | Prepared rows |
| --- | ---: |
| CC BY 4.0 total | 3,012 |
| WebQuestions | 1,830 |
| QuaRTz | 1,182 |
| CC BY-SA 4.0 total | 3,025 |
| ARC-Easy | 2,030 |
| ARC-Challenge | 995 |

The consistent read-only SQLite snapshot contained 10,790 accepted originals,
3,951 repair-rejected rows, 5,441 re-audits pending and 22 repairs pending.
Of the 20,204 total rows, 6,037 were prepared; 3,764 allowed-constituent rows were
not yet quality-accepted, and 10,403 rows belonged to held constituents.
These are snapshot counts, not current production or final release totals.

`ledger-snapshot.jsonl` and `dispositions.jsonl` provide private, hash-bound
membership/count accounting. **The outer snapshot includes held source content
and is not a publishable package.** Only individually reviewed license-partition
folders could become publication inputs later; never upload the outer root.

## Terminal Preparation

The initial preview used the command below with `--allow-partial` instead of
`--wait-terminal` and output suffix `v1`. For a fresh terminal preview:

```bash
python -m dfm12.latvian_p3_export \
  --root data/dfm13/baltic \
  --output data/dfm13/latvian-p3-rights-preview-20261003-terminal \
  --evidence-manifest data/dfm13/latvian-p3-rights-evidence-20261003/evidence.json \
  --change-date 2026-10-03 \
  --wait-terminal --refresh-seconds 60 --wait-timeout 86400
```

The optional wait calls existing `wave_repair.process(root, 'latvian-p3')`
periodically so finished repairs enqueue re-audits and completed decisions reach
the ledger. It starts no clients, touches no BLKT component, respects the existing
nonblocking lock and blocks export on terminal infrastructure failures or timeout.
Existing Baltic monitors continue to own repair/audit clients. No additional wait
process was launched in this implementation turn. Without either wait or explicit
partial mode, unfinished ledger states prevent export. Every output root must be
fresh; snapshots and previous packages are never overwritten.

Tests: 12 pass, covering partition conservation, notices, rights/source hash
drift, forged membership, positive audit scores, repair lineage/context,
partial-state opt-in and periodic terminal refresh/failure handling. Production
preview preparation verified source and evidence hashes without mutating the
quality ledger. Native tokenization and final publication review remain separate.

## Authorized Terminal Publication

On 2026-10-03 the owner authorized actual upload and registry integration of the
two cleared partitions, without an additional generic manual approval gate.
`dfm12/latvian_p3_publish.py` creates new publication artifacts from a terminal
preparation; earlier preview files remain unchanged. It rerenders every selected
conversation without truncation, verifies source/evidence/license pins and retains
full provenance. Metadata authorizes the published rows; conversation text is
unchanged. Pending, rejected and quarantined rows are never admitted.

Publisher destinations:

- `schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-4-0`
- `schneiderkamplab/dfm13-wave3-latvian-p3-cc-by-sa-4-0`

Every uploaded data, license, notice, evidence, README and manifest file must
match its local hash when downloaded from the returned HF commit. Only after
both partitions verify does the publisher update the registry under its existing
lock. Entries use `status=accepted_uploaded`, `uploaded=true`, a pinned
`hf_revision`, and `dfm13_wave3_` names. The existing tokenizer recognizes them;
no tokenizer worker or shared publisher was changed. Publication receipts use
`manifest` for the verified post-upload record and `export_manifest` for the
original package manifest, compatible with the wave additions assembler.

Combined tests: 22 pass, including corrupt remote data/license/notice/evidence
rejection, preservation of tokenization fields on idempotent registration, and
actual assembler receipt-contract consumption with synthetic token arrays.
Terminal `excluded_unreviewed` and `excluded_invalid_repair` are accounted as
exclusions, not endlessly pending jobs. Infrastructure failures still block export.

Detached launch receipt and exact command:
`data/dfm13/latvian-p3-publication-launch-20261003-v2/launch.json`.
PID at launch: `2295175`; log: the adjacent `run.log`. This replaced only the
owned waiting PID `2289823` to include terminal quarantine-state handling; code
hashes were re-pinned. No foreign process or BLKT work was stopped.
The process refreshes P3 every 60 seconds, waits for terminal quality, prepares
`data/dfm13/latvian-p3-rights-terminal-20261003-v1`, then builds/uploads
`exports_dfm13/latvian-p3-publication-20261003-v1`.

`integrated.json` in that publication root is the completion receipt, with both
repository commit revisions and counts. Until that file exists, these are target
repositories, not a claim of completed upload. Registry publication eligibility
is not completed tokenization or a complete DFM13 assembly; a later isolated
assembly must consume the verified tokenization receipts. No epoch sampling is
performed. The private outer preparation snapshot includes held data and is
never an upload input.

## Completed Publication And Independent Sample

The terminal publisher subsequently completed successfully: CC BY has 4,480
rows / 400,658 rendered tokens at HF revision
`dd39d2e75964de419df9ab38ac66d511bea3b756`; CC BY-SA has 3,200 rows / 473,065
tokens at revision `4bd0277b998dd85b0df21949ceb4ecfaaa666f67`. Both are registered
and tokenized. Completion is recorded in the publication root's `integrated.json`.
This supersedes the earlier waiting status, not the quality limitations.

An independent post-publication manual sample on 2026-10-03 read 20 full rows:
three repairs plus two original acceptances from each of four constituents,
selected by deterministic hash order. English P3 reference rows were recovered
and hash-snapshotted for all 20. Findings: **eight scoped holds, twelve without a
hard hold**. Six holds concern repaired rows; two concern original acceptances.
These strata are deliberately balanced, not population-rate estimates or native
language gold. Source-translation defects are distinguished from wrong answers.

Examples: a repair assigns NFL player Hank Baskett to the NBA 76ers; a years
question receives only a count; the translated urine question omits the decisive
English observation; learned/acquired trait drift creates ambiguity and flips
the target. A separate answer correctly follows an unusual supplied premise and
was not mislabeled as a repair error merely for contradicting outside knowledge.

Report: `docs/reports/dfm13_latvian_p3_independent20_20261003.md`.
Evidence/assessment: `data/dfm13/latvian-p3-independent20-20261003/assessment.json`.
Exact-row holds: adjacent `holds.jsonl`, SHA-256
`93c67c6de5aa0f2c4831e23cfa56826758f3470b8848f6aabf8563caff761df9`.
These are external sidecars, not applied mutations of the active ledger,
registry, published revisions or token arrays. A proposed versioned correction
must carry the holds into future assembly, preserve v1, use fresh tokenizer
names/roots, and coordinate explicit registry supersession to prevent sampling
both versions. Publication success is not semantic cleanliness.
