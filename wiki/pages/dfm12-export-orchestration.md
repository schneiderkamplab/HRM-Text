---
type: Runbook
title: DFM12 Accepted Export and Publication Orchestration
description: Repeatable CPU-only publication of finished audit sources and separately validated identity packages.
tags: [dfm12, exports, publication, cpu, operations]
status: draft
last_updated: 2026-09-28
confidence: high
---
# Accepted Export and Publication

## European Expansion: Local Export (2026-09-28)

The earlier root manifest now inventories 89 packages with 15,988,682 training
rows: 14 DaLA packages, 33 OPUS packages, six DynaWord packages, eight reordering
supplements, nine identity packages, and 19 instruction/chat/QA packages.
This supersedes the initial 58-package launch baseline below, not its historical
preservation requirement.

The completed European audit contains 12,169,124 accepted records among
14,394,514 completed judgments; 44,620 exhausted failures remain excluded.
The owner requested local accepted-only preparation, **not upload**. The new
queue schema is handled by `dfm12.export_european`, reusing the existing student
views, provenance bundling, and standalone validator. Its 21-language gate is
scoped to `export_schema=dfm12-european-v1`; older package gates are unchanged.
Both directions of accepted translation pairs are retained, so records and
training rows are different counts.

Output: `exports_dfm12/european-expansion/`, separate from earlier packages.
Eight CPU workers have exclusive component ownership and bounded input queues.
Packages are built under `.building-*`, validated, then renamed atomically.
The audit database is read-only. Failed or rejected rows never enter training
files. Provenance and judgments stay in metadata sidecars. Automated acceptance
does not imply native-speaker certification, complete benchmark decontamination,
or a new blanket license.

```bash
TMPDIR="$PWD/data/dfm12/european-export-tmp" CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.export_european --workers 8
```

The detached launch is recorded in `launch.json` within the output directory.
Inspect `export.log`, `progress.json`, and `worker-*.json`; only the final
`manifest.json` with `finished=true` establishes full completion. Do not restart
over existing staging blindly. Initial launch PID: 3789585. Regression tests:
16 passed across the European and existing finished-export tests. This entry
records preparation in progress, not completed export or publication.

Completion verified later on 2026-09-28: the final manifest has `finished=true`,
237 validated packages, 12,169,124 accepted records and **14,960,472 training
rows** after retaining both translation directions. Compressed training shards
total **8,934,220,410 bytes** (metadata sidecars excluded). No staging packages
remain, no errors were logged, and `upload_performed=false`. This supersedes the
in-progress status above. No DaLA components were included in this export;
earlier DaLA packages remain untouched.

## Publication and Complete Source Registration (2026-09-28)

The owner subsequently authorized public Hub uploads and integration of all new
exports, including DaLA. `dfm12/training_sources.json` is now the builder's
default registry: the earlier 89 exports, 237 European exports, and the existing
audited DaLA registry (24 train-only components from 12 newly published producer
datasets). There are **350 distinct training components**, with no name overlaps.
DaLA's published validation/test splits are not training inputs. Its producer
publication receipts already verify all twelve new repositories; do not upload
them again under duplicate names.

`python -m dfm12.publish_and_integrate` publishes missing registered packages
under `schneiderkamplab`, skips verified immutable uploads, then stages the
complete inputs using `dfm12.build_training --suffix all-additions-20260928
--prepare-only`. This does not tokenize, sample, promote a new corpus, or change
training. Identity retains repeat 10; other additions repeat 1. Existing corpora
are immutable. English OPUS pairs are recognized regardless of language order.

Detached execution records and log:
`data/dfm12/publication-integration-20260928/{launch.json,status.json,run.log}`.
Per-package Hub revisions live in each export root's
`metadata/upload-receipts.json`. The builder requires verified publication and
matching manifest hashes for exported inputs, and the pinned train-only audit
contract for local DaLA inputs. Its staged `sources.json` includes HF IDs.
Errors stop the chain; rerunning skips already verified uploads. A final
`status.json` phase `complete` is required before claiming staging is done.

This is an active publication job, not yet a claim that all uploads completed.
Eight focused regression tests passed, including duplicate registration and
changed-publication rejection.

Completion supersedes that active-job note: all **237 European packages** now
have verified public HF publication receipts (14,960,472 training rows).
The orchestration status is `complete`, `sampled=false`. All **350 components**
were staged under `data/dfm12/training-build-all-additions-20260928/accepted_inputs`,
with `sources.json` and `prefix_config.yaml` alongside. This includes the earlier
89 packages and 24 audited train-only DaLA components; existing sampled DFM12
was not replaced and the new European additions were not tokenized by this job.

## Tokenizing All Registered Additions

Subsequent owner instruction: tokenize with **64 workers**, without sampling.
`python -m dfm12.tokenize_registered --workers 64` uses the staged 350-source
input tree and DFM11's unchanged raw Gemma tokenizer/non-thinking chat template,
with a 4,096-token limit. Output is
`data/tokenized_dfm12_additions-all-additions-20260928`.
The wrapper locks the build root, checks tokenizer/template settings and hashes,
source metadata and completed arrays, and reuses earlier immutable shards by
symlink. Initial launch reused **703** completed shards (387 earlier additions
and 316 audited DaLA shards) and scheduled **496** new shards, **1,199** total.
No previously completed shard is deliberately retokenized.

Launch/progress: `data/dfm12/training-build-all-additions-20260928/`
contains `tokenization-launch.json`, `tokenization.log`, and
`tokenizer-reuse.json`. The tokenizer's final `completion.json` is the completion
marker; this paragraph records a successful start, not finished tokenization.
The training builder also accepts up to 64 workers. No sampling, GPU process
changes or training changes are part of this operation.

Completion verified: all 496 new shards finished in **331.9 seconds** with
**15,609,755 new assistant-target examples and zero skipped rows**. Including
703 reused shards, `completion.json` records **1,199 files and 47,303,761
examples**. The launcher exited successfully. This supersedes the launch-only
status above; no final sampling was performed.

Exact completed-array accounting (`inst_len.npy` plus `resp_len.npy`) gives
**12,954,325,563 tokens** across the joint additions: 3,548,176,188 earlier,
8,140,700,545 European expansion, and 1,265,448,830 new audited DaLA tokens.
With identity repeat 10 and all other additions repeat 1, the expected addition
per epoch is **12,991,310,712 tokens**, before any subsequent sampling changes.
These are additions only, excluding the inherited DFM11 corpus.

## Swedish Pin-Format Recovery (2026-09-25)

The first incremental pass built 20 new validated packages (78 total), but
failed before upload while checking a literal filename `path`. The Swedish
authorization uses a list of `{path, sha256}` descriptors; newer authorizations
use a path-to-checksum mapping. Passing the former to `dict.update` silently
created the wrong keys. `authorization_pins` now normalizes both formats, with
a regression test. Revalidate the real authorization evidence, refresh only the
reviewed exporter/contract hashes in the completion hook, and resume publication
incrementally. Do not rerun audits or discard the already validated packages.

User authorization, 2026-09-25: export and publicly upload all finished accepted
DFM12 additions now; publish the remainder after audit completion. Exhausted
audit failures remain excluded, without retries or regeneration. Training
resume after GPU release is independent of upload completion. This module
does not release GPUs, manipulate other processes, sample data, or modify any
audit database. GPU release/training hooks belong to their separate owners.

Related: [DFM12 status](dfm12-status.md),
[audit readiness](dfm12-audit-readiness.md),
[identity generation](dfm12-identity-generation.md).

## Repeatable Command

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.export_orchestrator launch --contract data/dfm12/export-orchestration-ready-20260925.json --state data/dfm12/export-orchestration-20260925
```

Run from the repository root. `launch` starts a detached child with
`subprocess.Popen(start_new_session=True)` and returns immediately. Tesla's
completion hook can invoke the identical command independently of Jason's
training hook. Each pass waits up to 43,200 seconds for the orchestration lock;
a final pass arriving during the first pass is queued, not discarded. Timeout
fails explicitly without retrying any work. No implicit helper retry loop.

The readiness contract pins helper code and test evidence. Changed helper code
requires deliberate retesting and contract resealing; do not silently replace
the hashes while a pass is running. The initial combined helper/orchestrator
suite passed **59 tests**, including lock contention, `upload=None`, immutable
published package preservation, identity companion adoption and idempotency.
Cached Hugging Face authentication and target namespace membership were
verified without printing credentials.

## Ownership and Ordering

Implementation: `dfm12/export_orchestrator.py`; tests:
`tests/test_dfm12_export_orchestrator.py`. Standard output root:
`exports_dfm12`; namespace: `schneiderkamplab`.

The source-export helper receives all five explicit owning roots:

- `data/dfm12/full-audit-20260924-v1`
- `data/dfm12/full-audit-sv-20260924-v1`
- `data/dfm12/full-audit-pl-is-20260925-v1`
- `data/dfm12/scoped-inclusion-audits-20260925-v1/scandi`
- `data/dfm12/scoped-inclusion-audits-20260925-v1/norquad-fleurs`

Swedish, PL/IS and both inclusion roots receive explicit per-root authorization
arguments. Completed source ingestion and terminal audit jobs determine export
eligibility. Failed audit rows remain unresolved/excluded in the exporter.
The orchestration probe reads only the indexed active statuses, avoiding
repeated full-database job grouping; the exporter independently enforces its
authoritative frozen-source checks. Its existing full key scans may take minutes.

Source export runs first. Identity adoption follows, using Boole's validated
isolated `data/dfm12/identity-export-20260925-v1` output when present, or the
explicit helper CLI if absent. All nine identity folders are validated and
copied under `.export.lock`; their unchanged `identity_source_manifest`
companion is copied and verified before the root inventory is updated. The
private identity database snapshot stays in isolated staging, not a package.
Poincare's incremental exporter uses that companion to preserve identity
ownership on later passes. Repeat 10 remains identity mix metadata, not
physical row duplication or final sampling.

The existing uploader then publishes nonempty packages, validates new exports,
and skips previously verified unchanged packages. A narrow uploader addition
validates but skips zero-row packages rather than blocking all other uploads.
Root `exports_dfm12/metadata` remains **local only**, never uploaded: it contains
full excluded records in frozen snapshots. Only inventoried per-package files
are submitted. Existing published package manifests and verified upload receipts
must remain unchanged; the initial preservation baseline is 58 packages and
58 verified uploads, totaling 3,431,930 training rows.

## Launch Evidence

First pass launched on 2026-09-25 at 11:32:07 UTC. Orchestrator PID **2215535**
was observed reparented to PID 1; source-export child **2215545** was observed
running with all five roots and explicit authorization flags. This records a
launch, not completed publication. At launch, 20 additional source components
were finished; `dala-en` and `dala-nl` remained nonterminal. The identity helper
has nine accepted packages totaling **8,715 conversations** ready for adoption.

State directory: `data/dfm12/export-orchestration-20260925/`:

- `helpers-tested-ready.json`: final tested-helper hash marker.
- `launch.json`, `launch-<PID>.json`: detached argv/PID/start-time evidence.
- `preserved-baseline.json`: immutable original package/verified-receipt pins.
- `latest.json`: current receipt path and status.
- `<timestamp>/receipt.json`: phase results, before/after counts, new packages,
  verified uploads, and finished/unexported or still-active source components.
- `<timestamp>/{export,identity,upload}.log`: helper logs; reused identity staging
  needs no regeneration log.

The first pass's source log is
`20260925T113207Z-1790335927070076537/export.log` under that state directory.
Read actual receipts for completion; do not infer completion from the launch
or from the initial 20-source count. Failures record
`failed_no_automatic_retry`, retaining all outputs for inspection. Interrupted
identity copies fail closed instead of deleting or overwriting partial files.

Parent handoff: link this page from the shared index/status; those files remain
under coordinating ownership. Wire the exact command above to the completion
hook independently of GPU release and training resume.

`finalization-ready.json` in the state directory records the exact hook argv,
CPU environment, helper-contract hash and observed orchestrator/exporter process
identities. It explicitly does not claim upload completion. OKF validation at
handoff reported only missing parent-owned index links for this page and the
concurrently authored `dfm12-identity-export.md`; zero warnings.
