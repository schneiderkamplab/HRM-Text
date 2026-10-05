---
type: Runbook
title: DFM13 Verified Additions Assembly
description: Explicit DFM12 base references, verified wave additions, token accounting and remaining non-wave adapters.
tags: [dfm13, datasets, provenance, assembly]
status: stable
last_updated: 2026-10-05
confidence: high
---
# DFM13 Verified Additions Assembly

[32 workers](dfm13-parallel-verification.md).

## Quota-held Local Slovak Integration (2026-10-03)

See [quota-held local integration](dfm13-local-wave-integration.md) for the
isolated delta and October4 v11 reconciliation (35 newer OPUS packages missing).

## Current Successor v11: Large Translation Batch and Exact FinePDF Rights

2026-10-03: v11 contains **270 sources, 10,074,921 rows, 3,230,749,804
tokens**; since v9, **116 sources, 639,179 rows, 73,004,034 tokens**.
All six exact-document FinePDF packages are included (9 rows, 17,944 tokens).
`dfm12/finepdf_assembly.py` verifies publisher inventory, integrated upload receipt,
all attachments, pinned rights evidence and each row's exact document grant;
generic wave token/mask checks remain unchanged. Adapter/assembler tests: 60 passed.
Unverified FinePDF rights and pending Europarl rights are not admitted.

The single full batch build v10 exposed the missing FinePDF `manifest` adapter;
v10 is preserved with those failures. V11 adds only those six verified entries,
reusing v10 hashes only after unchanged file signatures and current registry
admission checks before/after. No repeated full scan, sampling or base copy.
Report: `docs/reports/dfm13_verified_additions_v11_20261003.json`; new remote proofs:
`docs/reports/dfm13_v10_new_remote_20261003.json`. At completion, 35 later entries
were ready outside the freeze and no registered translation tokenization backlog
remained. Four quality holds persist; three freeze-time tokenizer gaps have since
completed. HF repo-creation quota failures remain prepared-only, never uploaded by
this verifier; Tesla owns metadata retries and publisher decoupling.

## Translation Reconciliation After v9 (2026-10-03)

The wave4 OPUS inventory advanced to 99 published/tokenized packages. Independent
incremental verification checked the 84 entries absent from v9: **24,056 rows,
954,020 tokens**. All passed publication/provenance, native token-array contract,
HF pinned/current revision and attachment hashes, and final unchanged registry
entry/local-file signature checks. No tokenizer gaps or published receipt orphans
were found at completion. Existing watcher PID 2134027 remained alive; no worker
was restarted and no assembly was rebuilt. These are verified additions pending
a later snapshot, not additions retroactively included in v9.

Evidence: `docs/reports/dfm13_wave4_translation_incremental_20261003.json`.
Context-fit review paths are `dfm12/nonwave_context_view.py`,
`dfm12/nonwave_assembly.py`, and dispatch in
`scripts/assemble_dfm13_additions.py`; focused tests are
`tests/test_nonwave_context_view.py` and `tests/test_nonwave_assembly.py`
(55 passed on this reconciliation).

## Current Successor v9: Context-fit Views (2026-10-03)

**Supersedes the whole-source context holds below.** Those nine blanket holds
were a conservative adapter decision, not a requirement to exclude every row
from a published source. Existing `data_io/sample_tokenized.py` supports explicit
selection ordinals and whole-row drop mode; its default truncation mode is not
used here. `dataset_new.py` packs prompt+response minus one autoregressive
position. The current assembler's explicit raw prompt+response limit remains
4096, unchanged; the new views select at precisely that boundary.

`dfm12/nonwave_context_view.py` produced nine local views under
`data/dfm13/nonwave-context-fit-20261003-v1`, without retokenization or new HF
repositories. Each receipt binds the full parent publication/token receipt,
per-shard selected ordinals, unchanged retained JSONL bytes and exact token spans
and prompt/response boundaries. `long-rows.jsonl` lists every deferred ID, global
and shard ordinal, target index, length and explicit context-only reason.
Full publications, native histories and full token roots remain intact.

The nine views select324,402 rows /269,497,048 tokens and defer9,742 rows
/68,603,890 tokens for long-context use. Exact parent row/token conservation was
verified; no quality rejection, silent drop, history trimming or target rewriting
occurred. Including the five already-fit sources, all14non-wave sources now
contribute360,284 rows /281,561,152 tokens. Shared Arena validation is reused only
within a process while all guard input signatures (including ledger/WAL inputs)
remain unchanged; changed evidence forces full revalidation.115focused tests
passed, including cache invalidation, exact selection/masks and tamper rejection.

`data/dfm13/verified-wave-additions-20261003-v9` is verified; v8 remains historical.

| Scope | Sources | Training-view rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Arena | 8 | 191,136 | 165,625,986 |
| JJzha | 6 | 169,148 | 115,935,166 |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 74 | 2,117,986 | 1,949,414,339 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 154 | 9,435,742 | 3,157,745,770 |

All nine view replays, full local checks and153remote publication checks passed.
Current-registry verification passed before/after with unchanged pinned local
signatures. There were no missing eligible entries at freeze. Four source-quality
holds and21not-yet-tokenized translation entries were excluded at freeze;22new
eligible translations observed afterwards are listed in the report, not added
mid-build. Two Fars summaries remain held outside the uploaded registry.
No final sampling, base copy, HF publication change or GPU action occurred.

Evidence: `docs/reports/dfm13_nonwave_context_fit_20261003.json` and
`docs/reports/dfm13_verified_additions_v9_20261003.json`. Source outputs and full
row counts remain publication facts; training-view counts are not a claim that
all published rows were admitted into this4096-context assembly.

## Historical v8 And Non-wave Tokens (2026-10-03)

The dedicated exact14-source controller `scripts/tokenize_dfm13_nonwave.py`
ran as PID2554308 and finished. It used at most16CPU workers, with no overlapping
source scope or interruption of wave tokenizer2134027. Artifacts are preserved
under `data/dfm13/nonwave-tokenization-20261003-v1`; per-source tokenizer logs,
complete token file hashes and source-bound receipts are there. No publication
payload, history, target or provenance was rewritten.

All14sources are now tokenized and registered: **370,026 rows /350,165,042 tokens**,
zero dropped rows, no truncation, unchanged native Gemma target-only semantics.
Five JJzha sources (SkillSpan, Kompetencer, Green, IMDb Dutch, Dutch Exam) passed
admission:35,882 rows /12,064,104 tokens. Eight Arena sources plus CroCo contain
9,742 sequences over4096 in aggregate. Their full token artifacts are registered
with `tokenization_admission_blocker`; they are not mistaken for missing work or
silently admitted. No length-selected subset or changed context limit was
authorized/applied here. Resolving those full-row context conflicts is the next
integration step, not additional tokenization. This supersedes the earlier
missing-tokenization diagnosis below.

`data/dfm13/verified-wave-additions-20261003-v8` is verified; v7 remains unchanged.

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 59 | 2,102,506 | 1,948,739,311 |
| JJzha | 5 | 35,882 | 12,064,104 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 130 | 9,095,860 | 2,887,573,694 |

Full local checks and129remote publication checks passed, with current-registry
verification before/after and unchanged local signatures. Four QA/P3 holds stay
excluded, as do the nine over-context sources. Be-en was present but not tokenized
at freeze; the existing watcher completed it during verification. It is recorded
as post-freeze eligible, not inserted into v8. Two Fars summaries remain held
outside the uploaded registry. No final sampling, base copy or GPU actions.

Evidence: `docs/reports/dfm13_nonwave_tokenization_20261003.json` and
`docs/reports/dfm13_verified_additions_v8_20261003.json`.106focused controller,
adapter and assembler tests passed. The unchanged explicit base is
`data/sampled_dfm12`; repeats remain recorded rather than materialized.

## Historical Successor v7 (2026-10-03)

`data/dfm13/verified-wave-additions-20261003-v7` includes all currently eligible
wave entries at its freeze, including four corrected SR releases. V6 is preserved
unchanged as historical. Base remains `data/sampled_dfm12`, referenced without
copying; no sampling, repeat materialization, publisher or GPU changes occurred.

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 59 | 2,102,506 | 1,948,739,311 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 125 | 9,059,978 | 2,875,509,590 |

SR adds254,288 rows /251,293,446 tokens. Independent full exported-row scanning
confirmed cases32/36/37/47 absent and case45 present exactly once in span-filling;
the manual proof matched SHA256
`ea8ef4a198d392e9dc21c28e45f44d91e1aa6d2b098aa8e031916b1b0274f0c6`.
All124 wave repositories passed remote current/pinned revision, payload and
provenance checks. Full local assembler checks passed; registry consistency
passed before/after, local signatures remained unchanged and no eligible source
was missing or newly waiting after freeze. SR's earlier pending-correction
restriction below is superseded only for these verified metadata revisions.

Eighteen registry entries remain unready: fourteen Arena/JJzha sources now have
supported narrow adapters but lack native target-only tokenization receipts;
four Baltic QA/P3 entries retain source-fidelity holds. Two Fars summaries remain
held outside the uploaded registry. Evidence:
`docs/reports/dfm13_verified_additions_v7_20261003.json` and
`docs/reports/dfm13_sr_v7_independent_20261003.json`.

## Arena/JJzha Adapter Readiness (2026-10-03)

The generic unsupported-contract diagnosis for fourteen non-wave entries is
superseded by `dfm12/nonwave_assembly.py` and narrow assembler dispatch. Exact
scope: eight Arena packages (199,678 rows) and six JJzha packages (170,348 rows),
370,026 rows total. All fourteen local publication checks and pinned/current
remote payload/provenance checks passed. This is **not tokenization or training
admission**: all fourteen currently have `tokenization_performed=false` and no
registered token roots/receipts. Their new readiness reason is
`nonwave_target_only_tokenization_not_ready`, not unsupported source contract.

Arena verification retains the existing full export validation, explicit release
authorization and current hold checks, per-row provenance, source/license pins,
verified upload receipt and exact target-index/full-history policy. The live
inspection reused the common eight-package inventory/selection verification
after checking its pins rather than repeating the same population eight times.
JJzha verification replays every published row against its read-only accepted
ledger, including repaired-target keep decisions and source-specific validation;
it preserves the distinction between model-reviewed IMDb/CroCo and validated
BIO/exam datasets. FLAN/Tasksource exclusions and binary IMDb semantics remain
enforced. No raw fallback, registry mutation or publisher change occurred.

The token adapter requires a hash-pinned receipt with schema
`dfm13-nonwave-target-only-tokenization-v1`, source hash, exact target policy,
`hard_truncation=false`, `regex_fix=false`, output root, rows/tokens and a complete
absolute-path SHA-256 file inventory. It checks the base tokenizer/template,
no dropped/expanded rows, full array integrity/counts and bounded native
target-only parity. Existing4096-context integrity checks remain in force;
overlength Arena histories cannot be silently truncated or declared eligible.
An explicit length-selection/provenance step is required if full native rows
exceed the training context. No tokenization receipt is fabricated by this task.

Next CPU work: produce native target-only token artifacts/receipts for these
already published sources, resolving any over-context rows explicitly, then
register their pinned roots and reverify. This task did not rebuild v6 or sample
an epoch. SR publication/correction remains separately owned by Jason.

APIs: `publication(entry, pins)` validates the existing release evidence;
`verify(entry, contract, pins)` additionally requires native token artifacts.
The assembler calls these only for the fourteen exact allowlisted names and
preserves existing source holds first.111focused non-wave/assembler/Arena export
tests passed. Evidence:
`docs/reports/dfm13_nonwave_adapter_preflight_20261003.json` and
`docs/reports/dfm13_nonwave_remote_verification_20261003.json`.

## Historical Successor v6 (2026-10-03)

`data/dfm13/verified-wave-additions-20261003-v6` is the new verified partial
assembly; v5 remains unchanged as a historical snapshot. The explicit base
remains `data/sampled_dfm12`, referenced without copying. No final sampling,
repeat materialization, GPU intervention or training change occurred.

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 55 | 1,848,218 | 1,697,445,865 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 121 | 8,805,690 | 2,624,216,144 |

All eight SL/SQ transformation packages are included:276,504 rows /285,123,007
tokens. Independent replay verified the four corrected subsets remove exactly
the four approved IDs and retain all other bytes/order. All four IDs are absent
from all eight current payloads. Corrected subsets total139,038 rows /135,872,404
tokens; unaffected packages total137,466 /149,250,603. This supersedes the
pending SL/SQ correction warning below, without erasing the historical race.
Evidence: `docs/reports/dfm13_sl_sq_corrected_eight_20261003.json`.

Full local source/receipt/token-array verification passed. All120 wave remote
repositories passed current/pinned revision, payload and provenance checks;
current-registry admission passed before/after and local signatures remained
unchanged. No eligible entry was missing at freeze or newly awaiting inclusion
at the final check.75focused subset/assembler/report tests passed.
Full evidence: `docs/reports/dfm13_verified_additions_v6_20261003.json`.

**No SR entry is included.** Await Jason's verified exact corrections for
cases32/36/37/47; case45 remains valid and must not be excluded. Wave4 translation
entries not completed by this freeze are likewise absent. Remaining registry
unready entries: four Baltic QA/P3 source-fidelity holds and fourteen unsupported
non-wave adapters (eight Arena, six jjzha). Two Fars summaries remain held outside
the uploaded registry. Reverify current admission before eventual consumption.

## Four Unaffected SL/SQ Packages Verified (2026-10-03)

The existing tokenizer completed the unaffected SL/SQ denoising and span-filling
packages. Independent full source/receipt/token-array checks and remote
current/pinned revision, payload and provenance checks passed for all four.
Their registry entries and exact local file signatures remained unchanged
through final reconciliation.

| Package | Rows | Stored tokens |
| --- | ---: | ---: |
| SL denoising | 61,365 | 80,325,058 |
| SL span-filling | 35,091 | 22,211,638 |
| SQ denoising | 25,567 | 36,475,777 |
| SQ span-filling | 15,443 | 10,238,130 |
| Total | 137,466 | 149,250,603 |

Per-language totals: SL96,456 rows /102,536,696 tokens; SQ41,010 rows
/46,713,907 tokens. Hash-bound evidence and all four remote revisions:
`docs/reports/dfm13_sl_sq_unaffected_ready_20261003.json`.
This verification does **not** admit affected prefix/reordering packages or
supersede their exact-ID correction requirements below. No successor assembly,
publisher, tokenizer or GPU job was started; wait for corrected successors
before considering another batch assembly.

## SL/SQ Release Watch And Exclusion Race (2026-10-03)

A roughly15-minute watch confirmed the same finalizer PID2355940
(start_ticks245791146) completed its loop, slept normally, woke and published
all four SL and four SQ packages. SL reconciled to187,571 accepted,33,185
rejected and2excluded-unreviewed; SQ to88,937 accepted and16,731 rejected.
SR's last observed ledger remained empty. These counts precede the separately
authorized four manual exclusions and are not all certified for admission.

The227MB paragraph-reordering upload was **SL**. Its published payload at
`b1bcb2789ac08c34fbe170469ce0a681a15641e5` still contains reviewed case14;
SL prefix at `5964d460dd114eaaff522d395f71734eb20cc9a4` contains case1.
Jason owns exact-ID subset successors preserving old exports and replacing
canonical HF packages. Do not certify the affected SL/SQ reordering/prefix
entries until all four specified bad IDs are absent and successor provenance
passes verification. Existing publication/tokenization flags do not resolve
these manual findings. No exclusions, publisher actions or registry edits were
performed by this watcher.

The existing tokenizer completed SL's four packages. **Unaffected SL denoising**
passed full source/receipt/token-array checks and remote current/pinned payload
and provenance checks:61,365 rows /80,325,058 stored tokens, revision
`9a6723f1fd430a87349b1defc478d0e4eb7ee324`. Evidence:
`docs/reports/dfm13_sl_denoising_ready_20261003.json`. No assembly was rebuilt.

Watch evidence: `docs/reports/dfm13_transform_finalizer_watch_20261003.json`;
exact-ID publication evidence:
`docs/reports/dfm13_sl_sq_publication_exclusion_race_20261003.json`.
The last read-only ledger poll timed out on a SQLite lock; this observation gap
is recorded, not attributed to worker failure. Finalizer2355940 and
tokenizer2134027 were subsequently confirmed alive. No worker was interrupted.

## Post-v5 Release Check (2026-10-03)

The next independent check found no registry additions or replacements since
v5. Its current-registry admission checks passed before/after inspection, and
all previously hashed local inputs retained their exact signatures. No new
assembly or tokenization was started. Evidence and observation timestamp:
`docs/reports/dfm13_release_progress_after_v5_20261003.json`.

SL transformation ledger:187,551 accepted,33 audit-retry-pending,33,174 rejected.
The33 underlying jobs are now terminal:31done and2failed after four attempts
with `ValueError: Incomplete output: length`. The existing finalizer/quarantine
path must reconcile these; they were not retried or admitted by this check.
SQ:88,928 accepted,11pending,16,729 rejected; all11 underlying jobs are done.
SR's release ledger is not yet populated. These are intermediate counts, not
newly publishable accepted-only package totals.

All43 Baltic translation selections are already published. Wave4 has no
translation selection receipts yet: main CPU preparation is in `pivot_enqueue`,
and selectors correctly await its completion marker. The separate Slovak
additive controller is advancing CPU preflight/enqueue. No ready-but-unpublished
translation receipt or concrete CPU publication bug was found. Existing
transform finalizer2355940, tokenizer2134027 and publisher/selector processes
were left running; their identities are recorded in the report. Source-quality
holds remain unchanged.

## Historical Successor v5 (2026-10-03)

`data/dfm13/verified-wave-additions-20261003-v5` supersedes v4 for current
admission. It includes all twelve newly ready HU/LB/SK packages and the HR44
paragraph-reordering successor (`hr_reordering_manual44_v1`, revision
`116c771f15f417d3ac0e06ac8d8867bb7fbc04b1`). V4 remains unchanged and historical.

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 47 | 1,571,714 | 1,412,322,858 |
| Existing MATH | 1 | 7,496 | 2,431,145 |
| Total | 113 | 8,529,186 | 2,339,093,137 |

These are additions-only, one stored copy; repeat policies remain unmaterialized.
The explicit base remains `data/sampled_dfm12`. No final sampling or training
changes occurred. The existing assembler fully checked source/receipt hashes,
token arrays and bounded native token parity. All112 wave HF repositories
passed current/pinned revision and payload/provenance checks. Local signatures
remained unchanged and current-registry admission checks passed before and
after remote verification; no eligible source was missing or newly awaiting
inclusion at completion.

Eighteen entries remain unready: four wave3 source-fidelity holds (Baltic LT/LV
QA and Latvian P3 CC-BY/CC-BY-SA), plus eight Arena and six jjzha entries lacking
supported non-wave adapters. No registered wave4 entry is unready. Two Fars
summary components remain source-held outside the uploaded registry; this is
not a claim that every planned wave component has been published.

Evidence: `docs/reports/dfm13_verified_additions_v5_20261003.json`.
Focused HR-subset, assembler and reporting tests:69passed. The assembly manifest
SHA-256 is `d9918f42da4bd3b41a41ac960dfe6cf70b99a20787ac49e740e296ad63392fd6`.
Recheck admission before future consumption because registry holds or source
replacements can supersede this snapshot too.

## HU/LB/SK Release Verification (2026-10-03)

All twelve Wikipedia transformation packages are uploaded and tokenized. An
independent CPU check verified current/pinned HF revisions, remote payload and
provenance attachment hashes, local publication/source receipts, token arrays
and tokenizer/template pins using the existing assembly source verifier.

| Language | Packages | Accepted rows | Stored tokens |
| --- | ---: | ---: | ---: |
| HU | 4 | 248,822 | 258,733,323 |
| LB | 4 | 56,636 | 52,239,127 |
| SK | 4 | 177,562 | 167,829,757 |
| Total | 12 | 483,020 | 478,802,207 |

Stored token totals match the published rendered totals. SK's two terminal
`excluded_unreviewed` rows remain excluded. LB span-filling was verified at
revision `6197dc484c396d0ec92c0573f6cfee2f7cb07d54`.
Complete per-package revisions, hashes and verification evidence are in
`docs/reports/dfm13_hu_lb_sk_ready_verification_20261003.json`.

This supersedes the pending HU/LB/SK progress below and the initial partial
`dfm13_hu_lb_sk_remote_progress_20261003.json` report. These sources are ready
for a future batch assembly; **v4 was not rebuilt or modified**. The existing
tokenization watcher completed the work without restart or a duplicate client.
No GPU, registry, publication or sampling changes were made by this check.

## Historical Successor v4 (2026-10-03)

**HR44 successor boundary:** v4 is the preserved pre-HR44 snapshot. Jason owns
the authorized44 manually verified HR paragraph-reordering exclusions, same-HF
replacement and new token artifacts. At the guard check, the registry still
matched v4: promotion had not yet occurred. Once its included HR entry changes,
v4 becomes historical/ineligible for consumption even if every old artifact's
bytes remain intact. Do not rewrite v4 or rebuild solely for these44 rows;
the next assembly should also capture newly ready HU/LB/SK and translations.

`verify_assembly` now compares every included source with its current registry
entry before expensive hashing and again before successful return. Removal,
new holds/unready status, changed source/publication/token pins, revision,
counts, subset policy, licensing/use conditions or repeat policy fail closed.
Unrelated new registry entries do not invalidate the snapshot. This supersedes
the old behavior that allowed withdrawal/replacement while frozen bytes matched.
No concurrent registry or publication edits were made for this guard.

New `data/dfm13/verified-wave-additions-20261003-v4` is complete as a verified
additions snapshot: **101 sources / 8,046,210 rows / 1,860,313,386 stored tokens**.
The explicit base remains `data/sampled_dfm12`, matching v3; no base/training
change, final sampling, token concatenation or repeat materialization occurred.

| Scope | Sources | Rows | Stored tokens |
| --- | ---: | ---: | ---: |
| Wave3 | 65 | 6,949,976 | 924,339,134 |
| Wave4 | 35 | 1,088,738 | 933,543,107 |
| Existing MATH | 1 | 7,496 | 2,431,145 |

Every eligible source in the frozen registry passed its actual adapter, full
local hash/array/receipt checks and sampled native token parity. All100 wave
repositories passed pinned/current revision plus remote LFS-SHA256/git-blob
checks of payloads, manifests/cards and declared provenance attachments.
The four filtered FA successors contain234,956 rows /168,662,614 tokens; old
FA payload/token artifacts are not selected. HR's four transformations are
included. Existing MATH repeat5 is preserved in the mapping, not multiplied
into these stored totals.72focused assembler/subset/report tests passed.

Exact per-language, per-wave/language and per-source rows/tokens, remote hashes
and exclusions: `docs/reports/dfm13_verified_additions_v4_20261003.json` and its
`.md` companion. `scripts.report_dfm13_verified_additions` counts explicit row
labels against actual per-row prompt/response array lengths. The7,496 MATH rows
omit row.language and are explicitly unknown, not inferred from a filename.

Eighteen registry entries remain unready: four explicit QA/P3 source holds and
fourteen unsupported non-wave adapters (eight Arena, six jjzha). Two Fars summary
components remain held outside this uploaded snapshot. HU/LB/SK transforms are
impending finalizer work, not silently added after snapshot freeze; their current
8/10/67 pending-ledger counts and parent-reported terminal underlying jobs are
recorded in `docs/reports/dfm13_assembly_v4_impending_sources_20261003.json`.
PID2355940 and other live workers were not restarted or duplicated. Final live
registry reconciliation found no missing newly eligible entries or new holds
affecting v4. V3 remains preserved and blocked as described below.

## Historical Snapshot Admission Hold (2026-10-03)

The previously verified `verified-wave-additions-20261003-v3` snapshot is now
**ineligible for consumption** because it includes Baltic QA sources subsequently
placed on source-fidelity holds. A direct `verify_assembly()` call on the retained
snapshot raises `quality_hold_source_fidelity: previously assembled source now
held`. Its historical files and counts remain unchanged; earlier verification
does not override the newer quality finding. Build a new snapshot excluding held
sources when needed, and recheck admission before any eventual sampling.

Part of the [DFM13 additions plan](dfm13-plan.md). This prepares source inputs;
it does not produce a complete DFM13 training dataset or sample an epoch.

## Verified Run

The completed command, run from the repository root, was:

```bash
python scripts/assemble_dfm13_additions.py \
  --base data/sampled_dfm12 \
  --output data/dfm13/verified-wave-additions-20261003-v2
```

The output `assembly.json` records **72 ready additions, 15 unready additions,
4,619,050 rows and 749,078,486 stored tokens**. These are additions only, one
stored copy before repeat multiplication, not base-plus-additions epoch totals.
The frozen `registry.snapshot.json` SHA-256 is
`38d87f0c2122e5e5dc7407fa35baa6e28b0be4aba370d8f632e5884f0fc55e9d`.
This is a snapshot, not a claim about later live registry/worker progress.

The explicit base is `data/sampled_dfm12`, as chosen for this invocation. It is
not inferred to be `data/sampled_dfm12_xl_epoch11_noidentity`. Future assembly
must likewise supply the intended base; this receipt does not authorize changing
the active training dataset or establish identity/noidentity inheritance policy.

Outputs include the frozen registry, `repeat_mapping.json`, source JSONL links
under `accepted_inputs/`, and collision-safe shard links under
`tokenized_additions/`. No token payload is copied or overwritten. The output
must be a fresh directory. Direct script invocation now supports repository
imports; its subprocess regression runs outside the repository without
`PYTHONPATH` and exercises native rendering. Focused tests: 39 passed.

## Token Basis And Verification

The initial assembly's six `Rendered token count mismatch` failures are
superseded by the corrected counting contract, not by a data rewrite:

- `token_metrics.training` and existing `tokens`: actual final-assistant-only
  prompt plus response tokens in arrays, equal to receipt/registry tokenized counts.
- `token_metrics.preflight`: export `rendered_tokens`, summing all assistant
  targets with repeated history prefixes. This is a preparation budget, not
  final-target training exposure. Source-row sums are checked when present.
- `native_token_parity`: deterministic sampled untruncated prompt/response
  token-ID checks, using source ordinals mapped to actual shard indices.

The six-source investigation passed full source/receipt/array verification and
43 sampled native renders, including 21 multi-assistant rows. Details and
hash-bound evidence are in `docs/reports/dfm13_wave_token_basis_20261003.md` and
its JSON companion. Each assembled source now receives the same bounded parity
check: five spread ordinals plus the first three multi-assistant rows,
deduplicated. No truncation is allowed in these verification renders.

All additions arrays are hash-pinned and checked for integer shape, contiguous
starts, matching row counts, response boundaries, vocabulary bounds and context
limits. Source/export/publication/tokenization provenance and tokenizer/template
hashes must agree. Exact duplicate source payload/shard targets are rejected.

Limitations: native rerender parity is sampled, not whole-corpus; no semantic
quality certification or whole-corpus deduplication is implied. Base metadata is
hashed, but base epoch/token payloads are only unchanged stat references, not
fresh payload hashes. Publication is checked against local receipts, not a new
remote request. Symlink targets remain external and must be reverified with
`scripts.assemble_dfm13_additions.verify_assembly(Path(output))` before later
consumption. No epoch selection, final sampling, training configuration or
registry mutation is performed.

## Remaining Adapters

All 15 exclusions in this frozen assembly have reason
`unsupported_non_wave_contract`; that is not a quality rejection. Their registry
and representative existing receipts reveal three distinct integration paths:

| Adapter | Frozen registry entries | Required work |
| --- | --- | --- |
| Audited Arena package | `ai_arenaen_preferred`, `arena_human_preference_140k`, `arena_human_preference_100k`, `arena_human_preference_55k`, `comparia_preferred`, `helpsteer3_edit`, `helpsteer3_preference`, `arena_expert5k` | Validate `dfm13-audited-arena-package-v1` export manifests, release authorization, disposition/provenance and publication pins; tokenize explicitly selected target indices with full native history, then verify arrays/parity. |
| jjzha release | `jjzha_skillspan`, `jjzha_kompetencer`, `jjzha_green`, `jjzha_imdb_dutch`, `jjzha_dutch_exam`, `jjzha_croco` | Adapt jjzha release/source field mapping and package/ledger provenance; tokenize final-assistant targets and verify native parity, hashes and counts. |
| Worked MATH | `hendrycks_math_worked` | Validate the existing conversion/tokenization receipt and differently named shard layout; verify single-assistant targets and arrays without retokenizing merely to mimic a wave receipt. Preserve repeat 5. |

The eight Arena and six jjzha entries explicitly record
`tokenization_performed=false` in this snapshot. Arena exports preserve full
history without a 4096 cutoff; a future adapter needs an explicit length policy
and exclusion accounting, not silent truncation. Their target index must not be
silently replaced by an assumed final target. Automated accepted/repaired rows
are not certified gold, and existing holds must remain excluded.

The MATH receipt already records 7,496 rows, 2,431,145 tokens, maximum sequence
2,999, no hard truncation and file hashes under
`data/converted_sources/dfm13_math_worked/metadata/tokenization-receipt.json`.
It uses `tokenized_output` rather than the wave `tokenized_path` contract.
These are inspected receipt claims, not a fresh MATH payload verification in
this documentation turn. Registry provenance explicitly notes intentional
problem overlap with inherited direct-answer RLVR MATH; do not claim deduplication.

MATH is the smallest immediate adapter gap because tokenized artifacts already
exist. Arena and jjzha additionally require verified tokenization receipts.
No adapter was implemented or admitted in this documentation turn. Mimir Search,
SearchArena and RepoChat remain excluded research artifacts, not adapter targets.

### Worked MATH Adapter Implemented, 2026-10-03

Superseding the MATH-only gap above: `dfm12/math_assembly.py` now verifies the
existing local worked-solution contract. API:
`verify(entry, contract, pins, api=assembler_module)`; the shared assembler has
only name-scoped dispatch branches in `unready_reason` and `verify_entry`.
Other agents' LT-summary/P3 publication adapters remain separate. Unknown
non-wave sources are not admitted by this change.

Actual payload verification completed with **7,496 rows / 2,431,145 stored
tokens / repeat 5**, maximum untruncated sequence 2,999. All converted-source,
screening, original train/test source, license-evidence, token-receipt and array
hashes were checked. Checks also cover exact shard inventory, row lineage,
train-only two-message single-assistant targets, no skipped/truncated rows,
token-array continuity/vocabulary bounds, matching native tokenizer/template
pins and five deterministic prompt/response token-ID parity samples.

The historical pinned conversion manifest records repeat 1; it is not rewritten.
The current registry policy requires repeat 5, preserved in the verified source
and future repeat mapping. Neither token copies nor epoch exposure were
materialized. The resulting assembly entry retains both historical and current
`corpus_overlap` text, conversion/effective repeats, original-source (not model
audited) quality basis, screening exclusions and
`whole_corpus_deduplicated=false`. Intentional problem overlap with inherited
RLVR direct-answer MATH is not represented as deduplication or source novelty.

Evidence: `docs/reports/dfm13_math_assembly_verification_20261003.json`, containing
the verified source record and file pins. Tests:
`python -m pytest -q tests/test_dfm12_math_assembly.py tests/test_assemble_dfm13_additions.py`
in the `hrm` environment: **57 passed**. Actual production work invoked only
`verify_entry`, not a new full assembly. No retokenization, epoch sampling,
registry mutation or training change was performed.

## Finalizer Runtime Checks

### Baltic Four-Job Completion Gap, 2026-10-03

The remaining nonheld EN-LT/EN-LV blockers were not exhausted transport failures.
Four 5,000-row institutional components had only 4,999 ledger records:
`institutional-en-lt-part00098`, `institutional-en-lt-part00116`,
`institutional-en-lt-part00154`, and `institutional-en-lv-part00101`.
Each missing candidate ID existed with the correct message fingerprint in the
original `candidate_ids` index, but its exact component-specific audit job did
not exist. The enqueue path skips previously indexed IDs while the job hash
includes component/provenance, explaining this inconsistent completion coverage.
No sealed candidate or dedup index was rewritten.

Failed-job inventory found 6,469 first-pass audit failures, 1,453 repair-audit
failures and 57 repair-generation failures, all model-format/validation classes
(JSON decoding, incomplete output, invalid role order or missing assistant).
No retained failure justified a transport/infrastructure retry. Evidence:
`docs/reports/dfm13_baltic_failed_job_classes_20261003.json`.

The narrow `scripts.recover_baltic_missing_audits` helper checks the frozen
component seals, exact four candidate IDs and original content fingerprints,
then uses `Queue.add` for only the absent component-specific jobs. Existing
failed jobs are explicitly refused; attempts/results/events are never reset.
Applied command:

```bash
python -m scripts.recover_baltic_missing_audits \
  --receipt data/dfm13/baltic/audit/missing-component-jobs-recovery-20261003.json --apply
```

Exactly four jobs were added. The existing stage client was run with four
explicit `--job-id` restrictions, concurrency/max-concurrency 4, on the already
running port 8800 endpoint. No GPU server changes occurred. All four completed
on attempt 1 with keep=true; current `wave_repair` then made all four component
ledgers terminal. The existing selector was actively working on EN-LV and was
not duplicated/interrupted. EN-LT's pair receipt still needed its next finalizer
pass; old pair-level pending lists are not evidence that these four audits remain
unfinished. Do not mark either pair uploaded solely from component completion.
Results: `docs/reports/dfm13_baltic_missing_jobs_outcome_20261003.json`.
Client artifacts: `logs/dfm13/baltic/missing-component-audits-20261003/`.
Three focused recovery tests passed, covering idempotence, unchanged historical
failures, exact failed-job refusal and sealed-input drift. Quality-held sources
(P3, Baltic QA and Fars summaries) were outside this four-job scope.

Follow-up on 2026-10-03: `baltic_audit.queue` now ensures each exact audit
payload even when its candidate ID is already indexed. `Queue.add` remains
INSERT OR IGNORE, so existing failed/completed jobs retain attempts, errors and
results; replay cannot create duplicate exact jobs. The receipt separately counts
candidate IDs and actual audit jobs and records per-component payload coverage.
The old candidate-ID-only skip was insufficient because audit payloads retain
component/provenance context. The live sealed manifest was not regenerated:
only the four previously recorded recovery inserts affected the live queue.
CPU enqueue/recovery tests: **21 passed**, including a shared candidate ID in
two components, missing-job recovery, repeat enqueue and unchanged failed rows.

EN-LV selection subsequently completed with **606,497 pairs / 1,212,994
conversation rows / 115,360,618 rendered tokens**. Publisher PID 2121810 was
observed holding the EN-LV publication lock; upload is not yet claimed complete.
Selector PID 2131994 remains alive for the next EN-LT pass, and tokenization
watcher PID 2134027 remains alive. Logs respectively:
`logs/dfm13/baltic/advance-translations.log`,
`logs/dfm13/baltic/advance-selections.log`, and
`logs/dfm13/wave4/tokenize-releases.log`. No duplicate selector or restart was
introduced. Registry checks retain explicit P3 and Baltic QA source-fidelity
holds; Fars summary holds remain separate from these translation pairs.
Historical assembly admission holds above remain authoritative; no assembly
was rebuilt or cleared by this enqueue correction.

Wave-four follow-up: its `wave4_cpu.enqueue` uses exact payload inserts followed
by component registration, not Baltic's candidate-ID skip. Therefore the Baltic
failure mechanism is not established for producer PID 2103633. A defensive
`wave_job_coverage.reconcile` now checks sealed registered parallel components
under `.enqueue.lock`, ensures exact jobs with INSERT OR IGNORE, and writes
`audit/component-job-coverage.json` with per-component counts and inserted jobs.
Existing failures/results/attempts are retained. Source drift fails closed.

The active producer/controller were not restarted. Controller PID 2103630
starts institutional preparation as a fresh Python subprocess after its current
direct producer finishes; that subprocess now reconciles direct/institutional
coverage before returning. Newly launched `advance_wave4_parallel` controllers
also reconcile after pivot enqueue and before the final preparation marker.
The already-imported controller does not gain that latter hook retroactively;
its pivot enqueue still follows the existing exact-payload-before-registration
path. The new coverage receipt is pending until the institutional stage runs,
not evidence of already-completed reconciliation. Enqueue/recovery/coverage and
selection-freeze tests: **24 passed**. No quality hold or admission gate changed.

### Post-v3 Incremental Verification, 2026-10-03

Later EN-LV publication supersedes its pending-upload state above: revision
`b247a04a27696aa2010e8f173a0ecad8933f7a62` contains 1,212,994 conversations /
115,360,618 rendered tokens. All five remote attribution attachments were
independently hash-checked at that exact revision; receipt:
`docs/reports/dfm13_enlv_remote_attribution_20261003.json`. The publisher also
verified the remote data payload before registry insertion. Local tokenization
is still pending the existing watcher, not falsely marked complete. EN-LT
selection is now ready with 621,567 pairs / 1,243,134 conversations /
116,050,220 rendered tokens; its publication receipt was not yet present.
Existing automatic publishers/watchers remain responsible, without duplicates.

EN-LV tokenization subsequently completed. Independent full verification through
the actual `verify_entry` API checked **1,212,994 rows / 115,360,618 tokens**,
all arrays and **1,228 local pins**, plus sampled native token parity. Pinned
remote payload and all five attribution attachments also match. Evidence:
`docs/reports/dfm13_enlv_ready_verification_20261003.json`. EN-LT's publisher
was observed holding its pair lock and writing its isolated temporary export;
no duplicate publisher/tokenizer was started.

EN-LT also completed publication and tokenization later in the same turn:
**1,243,134 rows / 116,050,220 tokens**, revision
`aafee45fc3cf94bf7a3707128a31f2a9b3573bd9`. All arrays, native sampled parity,
**1,257 local pins**, remote payload and all four attribution attachments were
verified. Evidence: `docs/reports/dfm13_enlt_ready_verification_20261003.json`.
This supersedes the EN-LT pending state above. Both pairs are verified ready;
no assembly rebuild or final sampling was performed.

Final current-registry/HF-head recheck:
`docs/reports/dfm13_enlt_enlv_final_recheck_20261003.json`. Both remote heads
still match those exact revisions; all2,485 local pin stat signatures are
unchanged from full hash/array/native-parity verification. No repeated bulk
array scan was needed, and no old FA artifact was re-admitted by this check.

Persian structural replacements are a separate in-progress publication lineage.
Do not treat historical FA pins below as current admission. Read-only contract
findings are in `docs/reports/dfm13_fa_subset_assembly_contract_review_20261003.md`:
the generic assembler currently does not verify an arbitrary derived-subset
receipt. A scoped receipt/parent/census/child binding is needed if Jason's final
publisher schema uses that contract; no competing assembler edit was made.

Six newly ready wave sources passed the actual `verify_entry` API without a
new assembly: four Persian Wikipedia transformation tasks and the LT/LV-pt-PT
pairs. Total **246,758 rows / 171,569,405 tokens**. Receipt:
`docs/reports/dfm13_wave_new_ready_after_v3_20261003.json` records full token-array
hash/structure checks, source/receipt pins and sampled native token parity for
only these new sources. Existing sources were not retokenized or repeatedly
rescanned. Automatic tokenization of all six completed.

The Baltic QA source-fidelity gate landed during verification. The actual
assembler readiness predicate excludes both LT/LV QA even before registry
status normalization; uploaded/tokenized alone is not an admission decision.
The resulting snapshot is **92 ready wave sources, 5,379,564 rows and
1,440,273,009 stored tokens**, excluding both QA and both P3 packages. The two
FarsInstruct summary components remain publication-held and were not added.
Worked MATH is a separate non-wave addition. These are readiness totals, not
a replacement for frozen assembly v3 or an epoch sample.

The SQLite lifetime correction was also applied to all three read connections
in `scripts/monitor_dfm13_wave_campaign.py` and both in
`dfm12/wave4_gemma31_transition.py`, retaining their queries, timeouts and control
behavior. `closing` guarantees close on success, exceptions and early returns.
No monitor restart, teacher transition or GPU operation was performed. Current
connection, transition, source-hold, summary, MATH and assembler tests: **95 passed**.

Lifecycle follow-up: instruction PID 2293017 and selection PID 2143812 were
newer than their relevant updates; selection correctly waited for the complete
parallel-preparation marker. Parallel PID 2103630 had an active preparation child
and was not interrupted. The stale transform PID 2101719 held a component lock;
its first 180-second idle guard expired without changes. The subsequent bounded
ownership-checked guard PID 2310384 recorded its result in
`logs/dfm13/wave4/refresh-transforms-2101719.json`. It required the exact process
creation time/command/UID, a sleep boundary, no component lock and no children.
`do_wait` or active filesystem I/O is not an idle boundary.

Current repair/release code was separately run under component locks for BE and
BS rather than waiting. BE finished with 211,603 accepted, 29,102 rejected and
two excluded-unreviewed; BS with 111,348 accepted, 20,177 rejected and five
excluded-unreviewed. All eight nonempty task packages were uploaded, remotely
data-hash verified and registered. BG was not duplicated. Receipt/count/hash
report: `docs/reports/dfm13_wave4_be_bs_publication_20261003.json`.
Release/repair/control tests: 11 passed; no GPU server/client changes.

### Full Wave Registry Crosscheck, 2026-10-03

Independent read-only snapshot scan:
`docs/reports/dfm13_wave_registry_crosscheck_20261003.json`.
The initial snapshot had 91 accepted-uploaded wave sources and two explicit P3
source-fidelity holds. Every accepted source payload was hashed and counted once;
final-target markers, declared rendered-token sums, publication/export/registry
agreement and tokenization receipts/array-header totals had zero mismatches.
Token payloads were not repeatedly rehashed: this is a handoff crosscheck, not a
replacement for full array verification in the assembler. Later metadata checks
also matched source revisions, selection/input pins, licenses and model-use
conditions. The three subsequently added payloads were checked separately,
without rereading the initial source set. The reconciliation snapshot contained
94 accepted-uploaded sources, 92 tokenized; the two newly published Portuguese
pairs were awaiting the existing watcher. P3 holds stayed excluded.

Two real ready-but-unpublished gaps were LT-pt-PT (3,776 conversations) and
LV-pt-PT (940). HF rejected the internal identifier `pt_pt` in card `language`.
The scoped serialization fix in `dfm12.wave_translation_release.card_languages`
uses ISO `pt` plus `language_bcp47: pt-PT`, leaving dataset labels and the
European-Portuguese variant unchanged. Both pairs were published with remote
data/attribution hash verification and registry integration; no extra quality
approval or tokenization job was introduced. They were the only observed ready
pair selections lacking publication. Unfinished EN-LT/EN-LV selections and
wave-four preparation/review work are genuine pending work, not orphan exports.

`contextlib.closing` now wraps read connections in
`advance_wave4_transforms`, `advance_wave4_selections` and
`select_baltic_translations`. SQLite's own context manager commits/rolls back but
does not close the connection, so the old loops accumulated descriptors. Tests
cover success and exception exits. No live controller was interrupted for this
patch; already-imported code needs the next ownership-checked idle refresh.
The earlier guard successfully replaced PID 2101719 with 2355940 before this
closing patch. Do not mistake that earlier restart for loading a later edit.

Combined connection/selection/translation-release/MATH/assembler/BLKT tests:
75 passed. The main agent owns fresh assembly v3; no duplicate assembly,
retokenization of existing sources, GPU changes or Arena/JJzha expansion occurred.

The later 2026-10-03 snapshot
`data/dfm13/verified-wave-additions-20261003-v3` verified 89 sources,
5,259,168 rows and 1,367,865,360 stored tokens (before repeat weighting).
It includes the scoped BLKT, LT-summary and existing MATH adapters. Eighteen
entries were unready: fourteen legacy Arena/jjzha adapter gaps, two P3
source-fidelity holds and two Persian Wikipedia tasks awaiting tokenization at
snapshot time. This supersedes v2's coverage counts, not its immutable evidence.
The base remains explicit `data/sampled_dfm12`; no epochs were sampled and no
claim of complete DFM13 or completed wave targets is made.

On 2026-10-03, BLKT uploads were verified but their initial registry records
omitted `status=accepted_uploaded`. `uploaded=true` alone does not make a source
eligible for `scripts/tokenize_wave_releases.py`. Check the actual eligibility
predicate after every new publisher integration; publication, tokenization and
assembly verification are separate completion milestones.

Long-running finalizers retain imported Python code. The wave-four instruction
and transform finalizers started before the exhausted-invalid-output quarantine
fix in `dfm12.wave_repair`; the old code could leave four-times-truncated audit
responses blocking otherwise finished components. Refresh these owned CPU
controllers at an idle boundary after relevant code changes. Do not restart GPU
servers or active clients for a finalizer-only update. Preserve transport failures
for recovery; only the explicitly classified exhausted model-output failures may
be excluded, with their error and attempt history retained.
