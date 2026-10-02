---
type: Runbook
title: DFM12 Additional DaLA Registration
description: Independent six-language DaLA train imports with pinned screening, raw Gemma4 verification and isolated completed-language audits.
tags: [dfm12, dala, multilingual, provenance, cpu]
status: draft
last_updated: 2026-09-25
confidence: high
---
# DFM12 Additional DaLA Registration

## Polish And Icelandic, 2026-09-25

**Superseded for PL/IS:** the earlier pending/running-language statements below
are historical. The user explicitly authorized importing and auditing completed
Polish and Icelandic DaLA. Producer `recovery_v1/finalization.json` now reports
`candidate_datasets_complete_require_linguistic_review`. This is completed
candidate production, not human linguistic certification or training acceptance.
The previous NB/NN/FO and Swedish imports/audit manifests remain immutable.

### Final Outputs And Screening

Use producer `la_output/six_language_candidates_recovery_v1/{pl,is}`, not the
unfinalized build outputs as training inputs. Individual successful receipts
point to `pl_dynaword_scaled128_v1` and `is_dynaword_scaled256_v1`; their full
raw validation/test pools remain protected, including producer-excluded rows.
The importer pins finalization, isolation, successful status receipts, raw and
final manifests, source revisions/artifacts and current late exclusions.
Final-output ancestry hashes, selected counts and every artifact are checked.

| Language | Raw pairs | Producer-final pairs | Final train input | Local duplicate removals | Retained train pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Polish | 478,930 | 478,929 | 383,144 | 0 | 383,144 |
| Icelandic | 478,930 | 478,928 | 383,142 | 2 | 383,140 |

Producer exclusions: PL removed one late-review held-out pair; IS removed one
near-original duplicate and one late-review train pair. The local normalized
screen then removed two additional IS pairs. No further late or held-out match
was found. Each raw language contributes 95,786 protected held-out pairs;
with NB/NN/FO/SV this is **589,880 protected pairs** (not unique-text count).
The pinned Swedish screen transitively includes previous NB/NN/FO train texts
and full raw held-outs. No new PL/IS held-out text matched previous train text.

PL source: `SlayerLab/polish-dynaword` revision
`1564cb054434ba049cbd0d355a9bfaf044b6a852`, `govpl`, `samorzad_gov_pl`,
`eurlex`, `biblioteka_nauki`. IS source:
`danish-foundation-models/icelandic-dynaword` revision
`0bb26f027648c465d8bdcf6262c6ebab97f2d1ee`, `igc-adjud`, `igc-law`,
`stjornartidindi`, `igc-journals-22-10`, `wikipedia`, including pinned metadata
annotation files. Native prompts explicitly retain `polskim` and `islensku`
(the Icelandic original includes its accent), train-only split, source/license
provenance and balanced clean/corrupted yes/no and correction views.

CPU root: `data/dfm12/dala-pl-is-20260925-v1/`; initial PID **2011116**.
Launch from `/work/mimir/HRM-Text`:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.dala_pl_is --workers 4
```

The runner sets `CUDA_VISIBLE_DEVICES=''`, `TOKENIZERS_PARALLELISM=false`,
and `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`RAYON_NUM_THREADS` to 1. It uses the raw Gemma4 tokenizer/template from
`data/sampled_dfm11/metadata.json`, no Mistral fix, no truncation or sampling.
`process.json` stores the actual detached command and immutable main/SV source
hashes; `runner.log`, `integration.json`, `verification.json`, per-component
receipts and token completions are authoritative progress/completion evidence.

Completed conversion/tokenization counts (all still unaudited):

| Component | Conversations | Raw Gemma4 tokens |
| --- | ---: | ---: |
| dala-pl-acceptability | 766,288 | 59,404,805 |
| dala-pl-correction | 766,288 | 105,668,299 |
| dala-is-acceptability | 766,280 | 73,572,898 |
| dala-is-correction | 766,280 | 138,623,516 |
| Total | 3,065,136 | 377,269,518 |

All retained pairs converted without rendering/length rejection. Independent
verification passed every candidate/array plus 616 raw-Gemma4 replay checks.
`integration.json` SHA256:
`fed4a46f74372021073842f4f0f36bfcaaac9d5264e7c256156845d79b65df4c`.
Audit-readiness discovery independently found the four completed components.

### Audit And Export Interface

Audit root: `data/dfm12/full-audit-pl-is-20260925-v1/`.
`python -m dfm12.dala_completed_audit` prepares the exact four verified
components, retaining the standard `sources.json` and `jobs.sqlite` schemas.
New `audit_full --completed-dala-authorization` accepts only the pinned
language set, verified producer-final import, current raw held-out/exclusion
evidence and nonoverlapping audit root. Existing default rejection and legacy
Swedish authorization remain intact; simultaneous authorization modes fail.
The authorization pins the existing cross-screen as supplemental evidence,
without pretending its old coverage includes PL/IS or all inherited DFM11.

Requested client settings: **128 HTTP workers per endpoint**, ports 8400-8407,
same `google/gemma-4-26B-A4B-it`, **two preparation workers**. Sources are ordered
so PL and IS begin preparation together. Main PID 1847954 remains at 768 per
endpoint; identity PID 2011630 was reported at 16 at handoff, but was no longer
present by audit launch (this task did not touch it). No server/main restart or resource
reconfiguration is performed. The detached audit command/environment and PID
are recorded in its `process.json`, with `runner.log` and `runtime.json`.
The new audit client started as **PID 2017186**. Its source manifest SHA256 is
`b2c6e2b3753a311b9d76cf75b21e53eada98e88ef22ed223e88658310fa406ce`.
Preparation PIDs: **2017311, 2017312**. `startup-verification.json` proves
13,804 persisted decisions (PL 7,290, IS 6,514), responses from all eight
endpoints, 3,973 pending and 1,423 leased/running jobs at the snapshot.
No exhausted failures; ten currently unresolved retry errors were nine
keep/score contradictions and one length-truncated response. Such responses
are not accepted as completed decisions. Both languages are preparing their
acceptability components; correction components remain in the pinned source
queue. Main/SV source hashes were rechecked unchanged. This is a live startup
proof, not whole-corpus audit completion.

Exact audit command from the repository root (launch detached via Python
`subprocess.Popen(..., start_new_session=True)`; stdout/stderr to `runner.log`):

```bash
CUDA_VISIBLE_DEVICES='' TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 \
OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.audit_full \
  --source-manifest data/dfm12/full-audit-pl-is-20260925-v1/sources.json \
  --operational-approval data/dfm12/full-audit-pl-is-20260925-v1/operational-approval.json \
  --crossscreen /work/mimir/HRM-Text/data/dfm12/scandi-cross-component-20260924-v1/audit-manifest.json \
  --output data/dfm12/full-audit-pl-is-20260925-v1 \
  --endpoints http://127.0.0.1:8400/v1 http://127.0.0.1:8401/v1 \
    http://127.0.0.1:8402/v1 http://127.0.0.1:8403/v1 \
    http://127.0.0.1:8404/v1 http://127.0.0.1:8405/v1 \
    http://127.0.0.1:8406/v1 http://127.0.0.1:8407/v1 \
  --preparation-workers 2 --concurrency 128 \
  --completed-dala-authorization data/dfm12/full-audit-pl-is-20260925-v1/completed-dala-authorization.json
```

Poincare owns exports/uploads and Tesla owns identity. The isolated
`owner-handoff.json` records their source/integration/authorization interface;
the validator is `dfm12.dala_completed_audit.validate_authorization`, or
`audit_full.validate_sources(..., dala_authorization=path)` (not the legacy
Swedish authorization argument). The receipt scope is
`completed_dala_automated_audit_only`, languages exactly `pl,is` for this run.
no direct inter-agent messaging tool is available. This task does not edit
`export_finished`, `exports_dfm12`, identity files, main/SV source manifests,
producer files or `audit_readiness.py`. `accepted_exports_allowed=false`
remains explicit; automated audits are signals, not export authorization.

Combined final regression run: **77 passed**, with two existing multiprocessing/fork
deprecation warnings from audit-readiness tests. Coverage includes final-output
ancestry/terminal checks, native task views, excluded raw held-out protection,
complete conversion/token verification, scoped authorization tampering,
default rejection, concurrency limits, audit handoff/resize compatibility and
immutable-root protection. OKF validation: zero errors/warnings; git diff
whitespace validation passed.

## Swedish Completed Import, 2026-09-24

**Superseded for Swedish:** the earlier running-SV/all-six gate below no longer
applies. The user explicitly authorized the completed `screening_v1` Swedish
export, local split/late-exclusion checks and a separate bounded automated audit.
PL and IS remain excluded. No producer finalization is asserted or modified.

Producer receipt:
`/work/mimir/DaLA/wiki/artifacts/six-language-expansion/screening_v1/sv-status.json`
has exit code zero and `candidate_build_complete_requires_final_audit`.
All 19 artifacts of `la_output/sv_dynaword_screening_v1` were size/hash verified
before and after screening. The source is Swedish DynaWord revision
`f7cf2952b597eee76d8a3bddaa732ca6788b51c1`, constituents `akademiliv`,
`forskning-framsteg` and `cellar`; original attribution/license/source fields
and explicit `svenska` prompts are retained.

CPU root: `data/dfm12/dala-sv-20260924-v1/`.
Runner: `python -m dfm12.dala_swedish --workers 4` (hrm environment).
`process.json` records completed CPU PID 1689549; `runner.log` records progress.
The isolated SQLite screen copies and pins the completed NB/NN/FO screen
read-only, protects all 95,786 Swedish validation/test pairs plus all 302,522
earlier raw held-out pairs, and checks previous retained train texts too.
Of 383,144 Swedish train pairs, one late-review exclusion was removed;
383,143 remain. No other normalized-text/document collision was observed;
no Swedish held-out text matched previous retained train text.

| Component | Conversations | Raw Gemma4 tokens |
| --- | ---: | ---: |
| dala-sv-acceptability | 766,286 | 58,243,455 |
| dala-sv-correction | 766,286 | 104,941,883 |
| Total | 1,532,572 | 163,185,338 |

All rows are train-only, unaudited, with balanced clean/corrupted task views.
No rendering/length rejection, Mistral fix, final sampling or export occurred.
`inputs.json`, `previous-screen.json`, `screening.json`, shard receipts,
`tokenizer.json` and per-component token completions preserve provenance.
Independent full candidate/array verification completed before auditing, with
308 raw-Gemma4 replay checks. Its authoritative completion is
`verification.json`, binding `integration.json` at SHA256
`4465cc098c9e2abade2d50283b816137fc6c4dafc61eb925ac4d540f00476285`.
The latter implements the existing `audit_readiness` integration interface;
`audit_readiness.py` and the frozen full-audit source manifest are unchanged.

### Isolated Swedish Audit

Separate audit root: `data/dfm12/full-audit-sv-20260924-v1/`.
`dfm12.dala_sv_audit` prepares pinned `sources.json`, copies the existing
operational approval without broadening it, and writes
`completed-swedish-authorization.json` only for the verified two-component
Swedish import. `audit_full` still rejects SV/PL/IS by default. Its explicit
Swedish exception validates the separate root, candidate/proof/evidence hashes,
full producer artifacts, current late-exclusion hash, previous screening seed
and the original cross-screen descriptor. PL/IS cannot use this exception.

The bounded client uses one preparation worker and **one HTTP request per
endpoint**, existing ports 8400-8407 only. It starts no servers. Main audit
`data/dfm12/full-audit-20260924-v1`, its pinned inputs/database and the parent's
incremental `exports_dfm12` operation are not modified. Owner coordination is
the separate `owner-handoff.json` plus thread progress; no direct Tesla messaging
interface is available. Audit PID, command and log go in the separate root's
`process.json`; counters are in `runtime.json`. The separate client started as
PID **1694116**. Its `sources.json` SHA256 is
`5d9d0e34dffcf1779f1cff722f9a93ef1b776e96754e5ca08e72ec609e8ace32`.
First live check persisted 48 valid responses across all eight endpoints,
with no failed jobs or producer error. Preparation PID is 1694155; these are
startup counters, not audit completion. The main source-manifest hash remains
`ed0e30113e8da0c0e57d818b88a7830fcec84adefdf31e697c59e0287ac314ab`.

The old cross-screen did not cover Swedish: the newly pinned local screen is
additional evidence, **not** a claim of full inherited-DFM11 deduplication,
semantic/near-duplicate clearance, benchmark clearance or six-language producer
finalization. Automated judgments remain review signals, not accepted exports.
Focused regression suites: **64 passed**, covering DaLA integration/registration,
new Swedish screening/authorization, streaming full-audit behavior, audit gates
and audit-readiness discovery. `git diff --check` passed. OKF validation reports
one unrelated missing immediate-child link for `dfm12-identity-generation.md`
in the concurrently owned pages index; this task did not edit that index.

## NB/NN/FO Integration, 2026-09-24

**Superseded for NB/NN/FO:** the earlier all-six-terminal wait below is no
longer an integration requirement for these completed languages. The owner
explicitly authorized local late-exclusion/split screening while PL/SV/IS keep
running. The producer's `recovery_v1/finalization.json` still says
`waiting_for_builds`; this task did not change it or claim producer finalization.

Completed CPU output:
`data/dfm12/dala-nb-nn-fo-20260924-v1/`.

| Standard | Retained train pairs | Acceptability conversations | Correction conversations | Pre-tokenized tokens, both tasks |
| --- | ---: | ---: | ---: | ---: |
| Bokmal (nb) | 383,115 | 766,230 | 766,230 | 160,077,058 |
| Nynorsk (nn) | 383,140 | 766,280 | 766,280 | 155,219,572 |
| Faroese (fo) | 70,349 | 140,698 | 140,698 | 33,268,714 |
| **Total** | **836,604** | **1,673,208** | **1,673,208** | **348,565,344** |

All **3,346,416 conversations remain unaudited**. No rendering/length rejection
occurred. Token counts are actual raw-Gemma4 prompt-plus-target tokens, not
estimated budgets or final sampled volume. Six per-component completion
receipts and candidate SHA256 values back these numbers.

### Inputs And Local Screening

`inputs.json` pins producer manifests, source snapshots, successful individual
build receipts, the current-run selection and late exclusions. All producer
artifact hashes/sizes were checked before and after screening. No producer
file, generation job, source configuration or review exclusion was modified.

- NB and FO use their completed `*_dynaword_recovery_v1` exports.
- NN uses the explicitly selected `la_output/nynorsk_capped_478930/nn` export,
  not the full 871,199-pair source pool. The selected export contains 478,930
  pairs across its original splits. Its ancestry checksum/cap were verified.
- Held-out protection deliberately uses the **full raw** NB/NN/FO validation
  and test pools: NN 188,851 pairs, NB 95,786, FO 17,885; 302,522 total. This
  includes NN held-outs omitted from its capped export.
- SQLite screens original and corrupted text using NFC, case folding and
  collapsed whitespace, plus source-document SHA256 matches. All three
  held-out pools are indexed before any train pair is considered. No held-out
  rows are converted; no source document is reassigned to another split.
- NB rejected 11 held-out-text matches, 17 normalized duplicates and one late
  review flag. NN rejected four held-out-text matches. FO rejected three late
  review flags. These 36 pairs are excluded as whole pairs, preserving balanced
  yes/no labels and clean/corrupted correction controls. Some producer flags
  concern held-out or already omitted pairs, so flag-list length is not the
  number removed from training.

`screening.json`, `screening.sqlite` and retained canonical `screened_pairs/`
shards preserve the evidence. This is **local exact normalized screening**,
not a new six-language near-duplicate finalization, semantic decontamination,
or a complete inherited-DFM11 scan. Future PL/SV/IS integrations must still be
checked against these pinned NB/NN/FO outputs and their protected held-outs.

### Conversion And Verification

`dfm12/dala_integrate.py` reconstructs the producer's four canonical task views
from each retained pair: clean yes, corrupted no, identity correction, and
corrupted-to-original correction. It preserves exact explicit-standard prompts
and stores source revision/file, pair/document IDs, licenses, authors, URLs,
edits and clean-control metadata outside rendered chat text. Full canonical
pair metadata remains in the pinned local screened shards.

The worker uses the existing `examples_from_messages`/`tokenize_example`
implementation with the raw tokenizer JSON and chat template from
`data/sampled_dfm11/metadata.json`, non-thinking, 4096-token limit. It writes the
standard uint32 token and uint64 index arrays directly, without a second
rendering pass, Mistral fix, target truncation or tokenizer/template change.
Four CPU workers were used; array output is under `tokenized_unaudited/`.

`dfm12/dala_verify.py` independently verified every candidate against its
canonical task view, all array hashes/dtypes/contiguous bounds, balanced
four-view pairs, concatenated candidate hashes and receipt counts. It also
replayed 676 rows against the raw Gemma4 tokenizer (two rows per task/shard).
`verification.json` records the result and binds the final integration hash.
The late-exclusion file was unchanged at verification. This is mechanical
verification, not linguistic acceptance.

### Parent Handoff

Use this additional argument on the parent's existing audit-readiness refresh,
retaining its other integration and cross-screen arguments:

```bash
--integration-manifest data/dfm12/dala-nb-nn-fo-20260924-v1/integration.json
```

The version-1 `complete_unaudited` manifest exposes exactly six components:
`dala-{nb,nn,fo}-{acceptability,correction}`. It includes candidate receipts,
SHA256 values, tokenizer completions, canonical/screening evidence and independent
verification. `producer_finalized` is false. It does not resolve the generic
`additional-dala` wait because PL/SV/IS remain pending.

Read-only discovery with the parent's existing reordering and Norwegian
integration paths succeeded: 67 total components, including all six new DaLA
components. Evidence: `audit-readiness-handoff.json`. The parent's running
refresh/snapshot was not restarted or changed, and **audit_readiness.py was
not edited**. No final sampling or training/evaluation changes occurred.

The separate DaLA registration manifest was refreshed using:

```bash
python -m dfm12.dala_refresh --integration-manifest \
  data/dfm12/dala-nb-nn-fo-20260924-v1/integration.json
```

It now reports three `integrated_unaudited` sources and three pending sources,
with the actual imported/pre-tokenized count. Ordinary later refreshes retain
and reverify this registered local integration instead of reinstating the
all-six wait for completed NB/NN/FO. Original producer blockers remain recorded
separately as `producer_blockers`, not silently erased from provenance.

Reproduction/verification:

```bash
python -m dfm12.dala_integrate --workers 4
python -m dfm12.dala_verify
python -m unittest discover -s tests -p 'test_dfm12_dala*.py' -v
```

Use `/home/ucloud/miniforge3/envs/hrm/bin/python` on this host. Fifteen tests
passed, including real raw-Gemma4 array generation/replay, a complete synthetic
three-language run while its finalizer waits, audit-readiness discovery,
partial registry integration, late-exclusion invalidation, split/provenance
checks, explicit-standard guards and resumability. Conversion workers now use
spawn to avoid forking a process after tokenizer threads have been initialized.

Completed job log: `data/dfm12/dala-nb-nn-fo-20260924-v1.log`.
Completed verification log: `data/dfm12/dala-nb-nn-fo-20260924-v1.verify.log`.
The detached conversion session was `dfm12-dala-nb-nn-fo` (PID 1144102);
conversion and verification both exited successfully, not ongoing jobs.

## Earlier Registration Snapshot

At 2026-09-24 10:12 UTC, **six sources are registered pending; none is safe to
import yet**. The producer's authoritative current-run pointer identifies
`recovery_v1`, whose finalizer reports `waiting_for_builds`. These are not
published HF releases. Proposed dataset names do not establish repository
availability or immutable publication revisions.

| DFM12 source | Standard | Producer state | Raw candidate pairs | Raw train rows per task |
| --- | --- | --- | ---: | ---: |
| dala-pl | Polish | Current completion receipt absent; building | Not final | Not final |
| dala-sv | Swedish | Current completion receipt absent; building | Not final | Not final |
| dala-nb | Norwegian Bokmal | Raw candidate build complete | 478,930 | 766,288 |
| dala-nn | Norwegian Nynorsk | Current completion receipt absent; building | Not final | Not final |
| dala-fo | Faroese | Raw candidate build complete | 88,237 | 140,704 |
| dala-is | Icelandic | Current completion receipt absent; building | Not final | Not final |

The two numeric columns come from producer manifests, not an independent
row recount. Each pair yields two acceptability and two correction examples.
The raw counts **precede cross-dataset isolation and late review exclusions**
and must not be described as accepted or final DFM12 volume. Producer-owned
generation processes and finalizer were observed running; no generation was
duplicated, stopped, restarted or modified by this task.

## Registration Interface

Only uniquely new source definitions are added, in `dfm12/dala_sources.yaml`.
This independent local registry avoids changing `dfm12/config.yaml` and its
already-resolved global `config_hash` in `data/dfm12/sources.lock.json`.
Existing English/Dutch DaLA entries and prepared outputs are untouched.
The new entries are not silently added to the generic HF downloader.

Run from the HRM-Text repository root:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.dala_refresh
```

Optional arguments: `--producer-root PATH`, `--config PATH`, and `--output PATH`.
Default result: `data/dfm12/dala-registration/manifest.json`.
This JSON is the dedicated machine-readable pending/status report. It records
source names, standards, blockers, raw split counts, source snapshots, observed
time and SHA256 evidence for the exact producer manifests and state receipts.
Re-running atomically refreshes the report under a single-writer lock.

Refresh completed successfully with:

- registered sources: **6**;
- ready sources: **0**;
- imported conversations: **0**;
- pre-tokenized conversations: **0**.

No background registration process remains running; invoke refresh after the
producer finalizes. Pending state is a successful discovery result, not a
license failure. All DynaWord/Instruct licenses are owner-approved; provenance
and notices remain required. No external upload or network access is performed.

## Completion Gates

Historical producer-only route: the all-six gate in this section is superseded
for completed NB/NN/FO by the verified local integration described above.
It remains applicable when considering the producer's eventual joint export.

The implementation reads `/work/mimir/DaLA/wiki/artifacts/six-language-expansion/`
`current-run.json`, then that run's exact `finalization.json` and language build
receipts. It does not glob for the newest directory or fall back to old
`scale_v1`, `scale_v2`, `pilot`, `audit` or isolation-smoke outputs.

Raw `candidate_build_complete_requires_final_audit` receipts are insufficient.
The terminal producer state must be
`candidate_datasets_complete_require_linguistic_review`, covering all six
standards, before any source can become `ready_for_unaudited_cpu_import`.
Final outputs must be the current run's isolated production destinations.
Checks require manifest schema/language agreement, document-separated splits,
source snapshots, cross-dataset isolation, late-review provenance, matching
isolation totals and all required train/validation/test/provenance artifacts.
All listed artifact sizes and SHA256 hashes are verified on a terminal refresh.
Changed state during refresh, missing/malformed receipts, wrong standards,
escaping paths or changed artifacts fail closed to pending.

Only the two `train/{acceptability,correction}_it.jsonl` paths are exposed for
future import; held-out artifacts are checked but never selected for training.
`audit_status` remains `unaudited`. Automatic producer checks and linguistic
review are different gates; no native-speaker validation is inferred.

**Refresh registers eligibility; it does not convert or tokenize.** Even a
ready entry retains `import_enabled: false`. These local exports use native
DaLA `direction`/`samples` task views, not the published EN/NL `messages`
schema. Once isolated exports exist, a dedicated CPU adapter must preserve
their exact written-standard prompts, canonical yes/no labels, pair/document
IDs, source revisions, licenses and unchanged correction controls. Do not feed
them into the existing EN/NL-only adapter or relabel NB and NN interchangeably.
Future pre-tokenization must use current raw Gemma4 assets and remain unaudited;
no tokenizer/template or Mistral-fix change is part of registration.

## Verification And Ownership

Eight tests passed:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m unittest discover \
  -s tests -p test_dfm12_dala_refresh.py -v
```

Coverage includes pending raw builds, ignored superseded receipts, terminal
checksum-verified train-only registration, held-out checksum changes, path
escapes, smoke-output rejection, malformed producer JSON and wrong-standard
rejection. The runner only reads producer files and refuses an output path
inside the producer workspace. It uses one CPU process, no parser/generation
workers and no GPU. There is no final sampling or training/evaluation change.

Central status/index files and other agents' code/config entries are untouched.
Compilation and `git diff --check` passed. OKF validation reports only this
new page's missing index link, deliberately left to the coordinating thread.

Related: [DFM12 component preparation](dfm12-components.md),
[DFM12 plan](dfm12-plan.md).
