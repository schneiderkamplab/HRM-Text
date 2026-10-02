---
type: Runbook
title: DFM13 Pending Arena Audit Candidates
description: CPU-only local conversion and scoped audit inventory for ComparIA, HelpSteer3, Expert5K and PRISM.
status: draft
confidence: high
last_updated: 2026-10-01
tags: [dfm13, data, provenance, audit]
---
# Pending Arena Preparation

## Completed Publication And Integration (2026-10-01)

Supersedes the in-progress checkpoints below: detached driver **2951927**
completed successfully and exited. All eight HF repositories were uploaded and
byte-verified; all eight source entries now point to audited local JSONL in
`config/dfm13_sources.json`. **199,678 rows**, no pending HF components. Four
existing repositories were replaced at the same IDs; four new sources received
their newly authorized canonical IDs, never `-audited` duplicate repositories.

| HF repository under `schneiderkamplab` | Rows |
| --- | ---: |
| `dfm13-ai-arenaen-preferred` | 2,328 |
| `dfm13-arena-human-preference-100k-preferred` | 52,652 |
| `dfm13-arena-human-preference-140k-preferred` | 88,774 |
| `dfm13-arena-human-preference-55k-preferred` | 30,446 |
| `dfm13-comparia-preferred` | 399 |
| `dfm13-helpsteer3-edit` | 6,321 |
| `dfm13-helpsteer3-preference` | 16,875 |
| `dfm13-arena-expert5k-preferred` | 1,883 |

Receipts under `exports_dfm13_audited/20261001-v1/private/`:
`upload-receipts.json` (exact commits/rows), `integration-receipt.json`,
`completion-receipt.json`, and `final-independent-verification.json`.
Final export inventory SHA256:
`d99653ba453d0fdd0affeb639d5f3ca999de2f2a59176af6153522dc6025f09e`.
Integrated config SHA256:
`ef984e5e0b40621494c3334c705c45c5cff34f4f22c9a884c399e33adaf3fca4`.
The pre-integration config is preserved in `dfm13_sources.before-integration.json`.

This is model-audited source registration, not certified gold, exhaustive manual
review, tokenization, final sampling, or training. Existing hold and unresolved
exclusions remain; 29 exact duplicates were removed with attribution retained.
Full histories/native tools and singular targets were preserved without a 4K
export cutoff. Training consumers must enforce target-only loss and their
separate length policy. No GPU/server/training state was changed.

## All-Eight Publication Resume (2026-10-01)

The user clarified that entirely new datasets may receive new canonical HF
repositories. This supersedes the pending-name/no-new interpretation below;
the four existing repositories still retain their exact IDs. New authorized IDs
under `schneiderkamplab`: `dfm13-comparia-preferred`, `dfm13-helpsteer3-edit`,
`dfm13-helpsteer3-preference`, and `dfm13-arena-expert5k-preferred`.
Destination map: `exports_dfm13_audited/20261001-v1/private/all-destinations.json`.

First driver 2944759 stopped on HF rejection of a relative `license_link` after
successfully uploading and byte-verifying AI-ArenaEN (2,328 rows), commit
`701e66c1afa9efb08ecdd2a78f7abd544d1995d3`. The resumed driver corrects only cards
to HTTPS canonical-repository `blob/main/manifest.json` links, recording old/new
hashes in `private/card-license-link-repair.json`; data and package manifests
are unchanged. Inventory/card hashes are renewed explicitly, followed by full
validation and authorization, not silent acceptance of changed pins.

Detached replacement driver **2951927**, verified live at authorization, runs
all-eight publication and integration automatically. Log/status paths below
are unchanged. Integration moves obsolete raw `file`/`selection` fields into
`upstream_conversion_provenance`; active `output` points to audited local JSONL.
`repo_id`/`revision` retain upstream attribution, whereas `hf_repo_id` and
`hf_revision` identify the published derivative. Combined tests: **56 passed**.
Use completion/upload receipts for terminal status; this checkpoint does not
claim that the remaining uploads or source integration already completed.

## Authorized Replacement Execution (2026-10-01)

Supersedes the historical manual-release prerequisite and inflight estimates
below: all eight audit/repair components are terminal. The user explicitly
authorized automated accepted rows minus unresolved rows and current holds,
exact deduplication, replacement of existing unaudited HF repositories, and
DFM13 integration. This is not certified gold or full manual verification.
The pinned authorization is
`docs/reports/dfm13_arena_user_authorized_release_20261001.json` (199,707 rows
before export deduplication), checked through Epicurus's existing
`scripts/dfm13_arena_authorized_release.py` and shared lineage/hold guard.

Exporter: `scripts/export_dfm13_audited_arena.py`; focused exporter/release/guard
suite including detached integration: **54 passed**. CLI stages are `prepare --repair-root ...`, `validate`,
`authorize --release ...`, and `upload --destinations ...`, all with `--output`.
Output: `exports_dfm13_audited/20261001-v1`. It snapshots terminal SQLite ledgers
under both controller locks, preserves native history/tools and singular target,
does not truncate/tokenize, and retains duplicate attribution separately.
Only package files are uploaded; private snapshots and root metadata are not.
Replacement uses a pinned parent commit and removes obsolete repository files
in the same commit. It does not invent audited-suffix HF destinations.

First completed local batch: ComparIA 399, HelpSteer3 edit 6,321, HelpSteer3
preference 16,875, Expert5K 1,883; total 25,478 after two exact duplicates.
All eight exports completed and validated: **199,678 rows**, excluding 11 holds
and 29 exact duplicates from 199,718 automated accepted candidates. Final main
counts are AI-ArenaEN 2,328; Arena100k 52,652; Arena140k 88,774; Arena55k 30,446.
The final inventory hash is
`6f54af9194c4a2957efe6c60512af3aa2ba6ec6a2dbecada03749981f531539e`.

Detached driver `scripts/finish_dfm13_arena_release.py` launched as PID/session
2944759, verified live in authorization. It automatically validates, authorizes,
replaces existing HF repositories, then replaces the old raw registry entries
and registers all eight local packages in `config/dfm13_sources.json`. Integration
retains a pre-change config backup and checks verified upload receipts for the
four replacements. This is source registration, not tokenization, sampling or
training. No replacement upload or integration was complete at this checkpoint.
Driver log: `exports_dfm13_audited/20261001-v1/private/release-driver.log`.
Same directory contains `driver-status.json`, then `upload-receipts.json`,
`integration-receipt.json`, and `completion-receipt.json` as stages complete.
Errors produce an explicit blocked status and stop the chain.

Existing four HF IDs are pinned in the export root's
`private/existing-destinations.json`; the four new components have no existing
derivative repositories and require parent selection of canonical destinations.

## Audited Replacement Handoff (2026-10-01)

**Updated execution/ETA inspection:**
`docs/reports/dfm13_arena_export_upload_eta_20261001.md`. Next-four repairs are
terminal with 25,482 accepted before holds/dedup. Cached HF write authentication
verified without exposing credentials. Main had 49 inflight 55K rows at snapshot.
Epicurus's updated guard now supports recovered keeps and explicit sample review;
this supersedes the missing-support warning below. Old DFM13 exporters remain
pre-audit copies, and the DFM12 uploader is not DFM13-compatible unchanged.
New accepted-only adapter/tests and exact sample receipts remain prerequisites;
no export/upload performed. ETA ranges in the report are conditional estimates.

CPU-only design: `docs/reports/dfm13_audited_replacement_handoff_20261001.md`.
Proposes eight isolated per-source packages: replace four pre-audit Arena
additions and add the four eligible components below, without overwriting old
exports. No export/admission/upload performed. Reuse Epicurus's existing
`scripts/dfm13_arena_export_readiness.py` guard; do not duplicate hold logic.
Important integration gap: repair-ledger accepted rows include unchanged
retry-audit keeps, whereas the current guard's repair branch requires a corrected
candidate. These need narrow owner support or explicit omission, never bypass.
Final snapshots, exact manual receipts, post-repair dedup/held-out checks,
target-only Gemma mask validation and license/provenance checks remain required.

## Scope And State

On 2026-10-01 the user requested CPU-only inspection/preparation of downloaded
Compar:IA, HelpSteer3, Expert5K and PRISM preferred/good responses, with no GPU
clients or uploads. This supersedes the **not converted** state in the
[initial candidate discovery](/pages/dfm13-plan.md), but does **not** imply
training inclusion, quality approval, or blanket licensing permission.

Converter: `scripts/prepare_dfm13_pending_arena.py`.
Root: `data/dfm13/pending-arena-candidates-20261001/`.
Original downloads and existing exports/registry are unchanged. The root is
fresh-only; a rerun cannot overwrite it. No network access, paid calls, model
requests, GPU use, upload, repair, final sampling or tokenized training output
was performed by this preparation.

## Counts

| Component | Local source rows | Structurally selected targets | Exact duplicates | Audit candidates | Structurally held source rows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Compar:IA publisher sample | 1,000 | 466 | 4 | 462 | 3 |
| HelpSteer3 human edit train | 13,740 | 13,719 | 4,803 | 8,916 | 21 |
| HelpSteer3 preference train | 38,459 | 36,207 | 13,084 | 23,123 | 94 |
| Arena Expert5K train | 5,128 | 3,531 | 1,231 | 2,300 | 19 |
| PRISM chosen, score >=80 | 8,011 conversations | 18,586 | 145 | 18,441 | 0 |

Total: **53,242 unaudited candidates**, including **18,441 license-held PRISM
candidates**; the other four components total **34,801**. Counts are not quality
acceptances. One PRISM conversation can yield several explicitly selected
turns, so source-row counts and candidate counts are different units.

Compar:IA has only the downloaded 1,000-row publisher sample, not the 675K full
release. Its votes are 118 A-better, 109 B-better, 121 both-good, 12 both-bad,
14 undecided and 626 unrated. Both-good permits both sides; unrated and
both-bad do not. The pre-validation target count is 469, not a full-corpus count.

## Exact Pins And Licenses

Pinned local HF download receipts and cached cards are hashed in every component
manifest; no card/revision is fetched implicitly.

| Source | Revision | Pinned card policy |
| --- | --- | --- |
| ministere-culture/comparia-fr-arena | `3cc8e20ae56fd0a4bc04d7f0e73244b9c353c6df` | Etalab-2.0 / CC-BY-4.0, with third-party output terms |
| nvidia/HelpSteer3 | `f6d145777bcbde96137596340fab89793acd1031` | CC-BY-4.0 |
| lmarena-ai/arena-expert-5k | `171f77047d8d153c41b3f2c11bc910273f62f183` | CC-BY-4.0 prompts; provider terms for outputs |
| HannahRoseKirk/prism-alignment | `18ab5cfb37456f4ec8cbc00212ce54cf7b1239f6` | CC-BY-4.0 human text; CC-BY-NC-4.0 outputs plus provider terms |

PRISM was prepared for inspection only and is now explicitly **held from audit**
pending licensing (2026-10-01 follow-up). No grant for unrestricted
training or redistribution is inferred from approval to inspect it. The score
80 threshold carries forward the existing qualitative inspection policy;
it is not an upstream correctness guarantee or newly asserted user policy.

## Conversation And Attribution Contract

Each `candidates.jsonl` row uses the existing canonical `id`, `messages`,
`target_message_index`, `chat_template_kwargs.enable_thinking=false`, and
`metadata` shape. Only the final selected assistant is a target; earlier
assistant answers remain context, including imperfect earlier answers. No
hidden reasoning or synthetic special tokens are injected, no text is
translated, and no history is truncated to fit a model window.

- Compar:IA reuses the existing Danish turn locator, removes future turns and
  retains the source choice, model, comparison/response IDs and history repairs.
- HelpSteer3 negative preference selects response1, positive selects response2;
  zero is a tie, not approval of both. Human edits are a separate component with
  original-response hash and feedback/change-summary provenance, not injected
  into the training conversation. Domain/language labels are retained as-is.
- Expert5K uses the restricted AST parser for NumPy object reprs, never eval.
  The current block must match exactly once in selected-side history. Seventeen
  rows have unsupported representations and two have empty/nonstring content;
  they remain held, not silently reconstructed.
- PRISM preserves the chosen branch. Its 265 multi-chosen turns all have
  identical visible answer text; one message enters subsequent context, with
  every chosen within-turn ID retained in branch lineage. Distinct ambiguous
  chosen branches would fail closed. No participant survey/demographic fields
  are copied into candidates.

Exact dedup keys include complete messages, target index, tools and template
kwargs. Existing four DFM13 additions win first, followed by Compar:IA,
HelpSteer3 edits, HelpSteer3 preferences, Expert5K and PRISM. No fuzzy or
shared-document matches are automatically removed. Every dropped occurrence
retains its attribution and retained-row pointer in `exclusions.jsonl`.

Of Expert5K duplicates, 1,229 match the existing 140K addition and two are
internal. HelpSteer3 edits have 4,799 internal repeats and four matches to 100K;
preferences have 12,718 internal repeats, 355 edit matches and 11 matches to
100K. Compar:IA's four match 100K. PRISM has 118 internal repeats and 27 matches
to existing international additions. Full source/output hashes and exact
duplicate ledgers permit reconstruction without modifying source artifacts.

## Held-Out Coverage And Next Audit

**Superseded 2026-10-01:** the initial conversion had no downloaded HelpSteer3
validation files and no validation overlap check. The follow-up below downloads
and screens all five pinned validation subsets; only train candidates are
eligible for audit. The other local
releases have no evaluation split selected or manufactured here. Compar:IA
future splits must group by comparison ID; PRISM by conversation (and consider
participant grouping), and HelpSteer3 repeated contexts must not be row-split.

Known coverage is exact matching against the four existing DFM13 converted
sources and among these candidates. Exhaustive inherited DFM11/DFM12 overlap,
benchmark decontamination and evaluation-prompt overlap remain **missing**.
No benchmark-clean claim is made and no arbitrary keyword-based exclusions
were applied. Those checks must be resolved or explicitly authorized in the
later admission policy, not hidden behind an audit pass.

Root `manifest.json` supplies `sources` entries with canonical path, rows,
SHA256 and component manifest pins. `seal.json` pins that inventory. This is
not directly runnable through the old bulk preparation: its total and source
manifest assumptions are hardcoded to **205,242** previously uploaded rows.
A separately owned/pinned audit-run manifest must select the new inventory,
measure full reviewer requests against context limits without truncation, and
retain license-held status. Do not change an active campaign's pinned inputs.
Existing exporters are registry/converter-specific and do not automatically
publish these isolated candidates. Future publication requires explicit
scope, licensing disposition and the audited output path, never this raw root.

## CPU Verification

Preparation command (fails if root already exists):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.prepare_dfm13_pending_arena
```

Focused converter plus retained Arena/target-adapter tests: **39 passed**.
`cpu-validation.json` records exhaustive canonical/audit-visible/single-target
adapter checks and five sampled renders with the actual pinned Gemma4 teacher
template, no Mistral regex fix. Sampled rendering is not an all-row token-budget
or language-quality preflight. No GPU clients were started.

## Completed Screening And Handoff

On 2026-10-01 the user requested validation download/screening, full-context
CPU preflight with at most 16 workers, and PRISM license hold without another
permission request. `scripts/screen_dfm13_pending_arena.py` completed with exit
zero using 16 CPU workers (parent PID 2802915, now exited). Original conversion
outputs remain unchanged; eligible lines are copied byte-for-byte.

All five `nvidia/HelpSteer3` validation files were obtained at revision
`f6d145777bcbde96137596340fab89793acd1031`: preference 2,017; edit 721;
feedback 2,039; edit_quality 163; principle 1,024, totaling **5,964 rows**.
File content SHA256, HF download receipt and revision are checked. Exact full
contexts and adjacent user/answer pairs are checked before every assistant
message, including prior turns, against all published response alternatives.
No fuzzy, shared-document or answer-only rule is used.

| Component | Input candidates | Validation overlaps held | Context overflow held | Audit eligible |
| --- | ---: | ---: | ---: | ---: |
| Compar:IA | 462 | 2 | 0 | 460 |
| HelpSteer3 edit | 8,916 | 1,007 | 0 | 7,909 |
| HelpSteer3 preference | 23,123 | 1,746 | 0 | 21,377 |
| Expert5K | 2,300 | 0 | 57 | 2,243 |
| PRISM | 18,441 | Not screened | Not measured | 0 (license held) |

Total **31,989 audit-eligible**, **2,755 validation overlaps**, **57 overflows**,
and **18,441 license-held**. The 32,046 non-overlap/non-PRISM candidates all had
their actual reason-first reviewer payload rendered and tokenized, with
thinking enabled, 8,192 output tokens reserved and a 32,768 context limit.
Tokenizer uses the raw pinned Gemma4 template and `fix_mistral_regex=False`.
No truncation occurred. Expert's maximum prompt was 107,189 tokens; overflow
rows are excluded rather than shortened. Request hashes and actual token-ID
hashes are recorded for every measured candidate.

Artifacts:

- `data/dfm13/pending-arena-screened-20261001/manifest.json`: sealed screened inventory, source/code/tokenizer pins and explicit coverage gaps.
- Per-component `preflight.jsonl`, `excluded.jsonl`, `manifest.json` and immutable `candidates.jsonl`.
- `validation-index.jsonl`: full pinned heldout identities, context/pair hashes and one-based file rows; derived IDs are explicitly labeled where upstream provides none.
- `data/dfm13/pending-arena-eligibility-20261001/eligibility.json`: adapter-compatible independent source readiness, four clearance receipts, PRISM held.

The eligibility receipt is for **auditing only**, not training, export or a new
license grant. Pinned license cards and original source IDs/file rows accompany
the source evidence. `license_cleared` and `heldout_overlap_cleared` are scoped
to this audit and its documented checks, not exhaustive legal or benchmark
clearance. Expert5K explicitly publishes `train`; no Expert5K evaluation task
was found in inspected local DFM registries/configs. This does not prove that
its text has never appeared in any benchmark. No blanket exclusion based on
the dataset's name was invented; exhaustive inherited and other benchmark
coverage remains unresolved for later admission.

`scripts/handoff_dfm13_pending_arena.py` can seal completed components separately
without blocking them on another source. All four completed together here.
The next-audit adapter's `eligible()` accepted four sources / 31,989 rows and
all evidence hashes verified. **42 tests passed** across conversion, screening,
handoff and next-audit tests. A handoff helper initially passed string paths to
a Path-only hash helper; this was corrected before any receipt was emitted,
with a regression test. No failed or partial eligibility receipt was published.

Epicurus owns preparing/queuing `scripts/dfm13_arena_next_audit.py` after repairs;
this work did not start its watcher or any GPU/model client. No active audit,
server, registry, export, training job or source output was modified.
