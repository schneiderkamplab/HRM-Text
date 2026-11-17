---
type: Assessment
title: HF Rebuild Disaster Recovery Assessment
description: 'Part of DFM15 Plan: disaster-recovery assessment for the serial HF-only DFM1-15 reconstruction queue.'
tags: [dfm15, rebuild, disaster-recovery, data]
status: draft
last_updated: 2026-11-07
confidence: high
---
# Disaster recovery assessment (2026-10-19)

Part of [DFM15 Plan](/pages/dfm15-plan.md).

### Serial replay requirement

**Scope correction, 2026-10-19:** the user requires an HF-only reconstruction,
not a local-reservoir replay. Both local replay attempts were stopped before
completing DFM1. Their outputs must not feed the reconstruction. All public
inputs, including accepted synthetic/audited derivatives, must be downloaded
from HF into an isolated root. Only lexdk and DBC may supply local source data.
Existing production trees may be read for reference inventories/comparison,
but their payloads, sampled indices and tokenized reservoirs are not rebuild
inputs. Reuse is allowed only for predecessors rebuilt in this HF-only chain.

`scripts/prepare_dfm_hf_replay.py` preflights the DFM1 source mapping and
supports fresh downloads from the resulting revision lock using `--input-lock`
and `--download`. The initial preflight resolved metadata for 44 HF sources;
two further families are lexdk/DBC. This establishes repository metadata
access, not payload accessibility or historical equality. Unpinned sources
are explicitly marked `current_hf_head_not_historical_proof`; comparisons may
require recovering historical revisions. The lock is at
`logs/analysis/dfm_hf_replay_preflight_20261019/dfm1-hf-inputs.json`.

Correction from the completed manifest: there are **45**, not 44, public
source families (plus lexdk/DBC). Fresh downloads run under
`data/rebuild_hf_dfm/dfm1-acquisition`. User requested five-minute monitoring:
`scripts/monitor_dfm_hf_replay.py --interval 300` records source completion,
errors, downloader liveness and free space in that directory's `monitor.jsonl`.
The detached monitor is read-only and exits when acquisition completes or the
downloader exits; it does not launch conversion or repair failed downloads.

Download throughput inspection (2026-10-19): acquisition uses four simultaneous
files and serial repositories. A 20-second `/proc` I/O measurement observed
110.7 MB/s written; about 204.7 GB of Sapient payload files had completed after
roughly 62 minutes. Xet is active. File-count progress is not byte progress,
and the source-level receipt is updated only after an entire source completes.
These observations do not establish a network or filesystem saturation limit.

### HF rebuild queue (2026-10-19)

**Verified completion (2026-10-20):** the isolated HF-only DFM1 rebuild
finished all 1,377 tokenization tasks and four sampled epochs. The queue's
comparison passed all 17 arrays (token store plus four index arrays per
epoch) and sampled metadata against preserved historical DFM1.
Receipt: `data/rebuild_hf_dfm/serial-queue/dfm1/verified.json`,
`status: matched`. This establishes DFM1 reproducibility from the downloaded
HF inputs plus agreement-based lexdk/DBC, using the Python/HF driver.
It does not establish later boundaries. DFM2 is now blocked on its missing
HF-only recipe/input lock; the coordinator exited without starting DFM2.
Final watchdog probes were approximately 1-3 ms with no slow-check streak.

**Tokenizer driver migration (2026-10-20):** the DFM1 queue now invokes
`scripts/tokenize_hrm_hf.py`, using Python orchestration and HF `tokenizers`,
instead of the standalone `data_io` binary (which itself uses HF's Rust
encoding engine). The original 65,536-token vocabulary, literal-special-token
encoding, HRM markers/conditions, row order, and uint32 token/uint64 index
arrays are retained. This is not a Gemma migration.
The driver streams parquet batches into temporary files and copies arrays
with bounded buffers; it does not accumulate whole source files in RAM.
Outputs are staged outside the sampler task directory and published only
after completion. A directory lock prevents concurrent drivers. A fingerprint
receipt validates completed Python outputs; old/unreceipted or partial outputs
are rebuilt. Errors propagate to block sampling.

`tests/test_tokenize_hrm_hf.py` passed exact array/dtype parity against the
existing Rust binary on a small Unicode/special-token/multi-condition fixture,
plus cached reuse and incomplete-output rebuild. Full historical equality
still requires completing tokenization, sampling and comparison.
The queue was initially left stopped, with 16 configured workers. Earlier permission
errors and the explicit SIGTERM stop are not proven encoding-engine failures;
changing the driver does not repair filesystem permissions.

Later October 20: restarted under `scripts/watch_dfm_rebuild_io.py`, with
16 workers. Initial launch caught seven retained JSONL inputs; added historical
JSONL/gzip handling and verified Rust parity for both parquet and JSONL fixtures
(two tests passed), then relaunched. Watchdog logs and runner log:
`logs/analysis/dfm1-hf-driver-20261020/`.
It measures a 4 KiB write/fsync/read every 30 seconds and stops only the
isolated rebuild process group after three measurements above
max(0.5 seconds, 10 times initial median). This is a latency guard, not proof
of no impact on bulk filesystem throughput. No training/eval processes targeted.

Fresh DFM1 acquisition completed: 45 HF families, 532,224,414,876 bytes, no
recorded failures. `scripts/queue_dfm_hf_rebuild.py` creates/runs a separate
CPU-only queue at `data/rebuild_hf_dfm/serial-queue/plan.json`, with DFM1-15 in
strict comparison-success order. It does not modify the live eval/training
scheduler. DFM1 passed input preparation/filtering and started conversion.

DFM1 stages: prepare allowed inputs, apply the recorded `45a297f` source
filter, convert (8 CPU workers), compare source/task layout, tokenize (1 Rust
worker), sample four epochs, compare all token/index values and metadata.
HF OPUS packaging is mapped from `data/opus_da_en.jsonl.gz` to the historical
root-level input name. Tokenized public sources are never reused. Agreement
inputs are restricted to lexdk/DBC. A mismatch blocks the queue, preserving
both reference and rebuilt outputs for diagnosis.

DFM2-15 have ordered pending queue entries, but their HF-only recipes/input
locks are **not yet implemented**. They are explicit recipe holds, not a claim
that the entire chain is runnable. The local-reservoir replay adapters are not
used. A successor requires its predecessor's successful comparison receipt.

Runner log: `logs/analysis/dfm_hf_serial_queue_20261019.log`. Read-only monitor
checks every 300 seconds and logs to
`logs/analysis/dfm_hf_serial_monitor_20261019.log`. It exits on a blocked row
or completion. Use `python -m scripts.queue_dfm_hf_rebuild status --queue
data/rebuild_hf_dfm/serial-queue` for current state.

User update (2026-10-19): **32 tokenizer workers** supersedes the one-worker
setting above. `tokenizer_workers` defaults to 32 and the generated command
was checked. The old coordinator was terminated by exact PID, without stopping
the active converter; its replacement waits for that converter to exit, then
incrementally rechecks completed conversion outputs before continuing with the
new tokenizer setting. Conversion remains at 8 workers.

Later-version HF acquisition now overlaps DFM1 conversion. The independent
`scripts/prefetch_dfm_hf_additions.py` job uses 2 repository workers and 16
file workers per repository. Inventory comes from the tracked Mimir collection
recipe, downloader declarations and DFM13-15 published-source registries:
846 repository/revision entries, 837 distinct repositories at initialization.
This is a declared-candidate prefetch, **not** a verified complete historical
DFM2-15 closure (notably, older/DFM12 receipt reconciliation remains necessary).
Pinned published derivatives take precedence over their raw upstream sources
in the DFM13-15 registry extraction. No local public payloads are inputs.

Manifest/download root: `data/rebuild_hf_dfm/later-acquisition`. Log:
`logs/analysis/dfm_hf_later_downloads_20261019.log`. All result-manifest writes
are serialized through the coordinator. Downloads do not release comparison
gates or authorize inclusion; reconstruction stays serial and fail-closed.

The independent union checks and DFM12-14 index probes are **not** evidence
of a serial reconstruction. Superseded interpretation: a later independent
"match" does not clear an earlier mismatch. The recorded DFM4 root list and
DFM6 `tokenized_dfm6_direct_jinja` input resolve their local union mismatches,
but do not establish recovery of those inputs from HF.

`scripts/replay_dfm_serial.py` now runs fail-closed in ascending version order.
It begins with DFM1, passes replayed predecessor trees into incremental
builders, and stops at the first mismatch or missing historical recipe.
DFM5 is an explicit reselection from source reservoirs, while DFM6 is a
tokenizer migration; neither is represented as a simple append. The first
now-stopped local run is under `logs/analysis/dfm_serial_replay_live_20261019`, with
stdout in the sibling `.log` file. The earlier foreground
`dfm_serial_replay_20261019` attempt was stopped during the initial header
scan to relaunch detached with finer progress reporting; it verified no
boundaries and is not an input to the live replay.

For each implemented boundary it compares the entire logical source-token
concatenation against the saved backing before reusing that backing read-only,
regenerates all epoch indices, compares every index value, and checks metadata.
This is a **local tokenized-reservoir replay**, not an HF cold rebuild.
No production data is modified. DFM9 and DFM12-15 serial adapters still need
recovery/implementation; the runner blocks instead of silently substituting
their production datasets. A `verified.json` is emitted only after a full
boundary succeeds; `progress.json` records the current phase or blocker.

Repository inspection does **not** establish a clean-clone, HF-only rebuild of
the full inherited corpus, even excluding agreement-based lexdk/DBC. Do not
equate publication of individual datasets with a verified reconstruction recipe.
This assessment checked local code/registries, not a fresh exhaustive Hub audit.

- DFM15 registers four additions with repository IDs and revisions.
- DFM14 registers 277 additions with published repository IDs and revisions.
- DFM13 registers 312 additions: 310 have derivative HF IDs/revisions; the
  other two point to pinned upstream `EleutherAI/hendrycks_math` and
  `Setur/fo-instruct`. Entries are components, not necessarily distinct repos.
- Older inherited publication evidence exists locally, for example
  `exports_dfm10/inherited_hf_audit.json` (2026-08-29); it is not tracked and
  is not proof of current availability of the entire DFM15 dependency closure.

Concrete recovery gaps: DFM12 build registration reads untracked export-root
manifests, upload receipts and DaLA registries. DFM14 similarly requires local
accepted-release manifests, DaLA registry and inheritance reconciliation.
DFM15 full-mixture builder assumes an existing repaired sample and rsyncs
tokenized parts and selection arrays from a hardcoded SSH endpoint. Native
reasoning repair reconstructs offsets from local DFM11/12 token stores; math
conditioning also relies on local/remote source boundaries and an external
local tokenizer path. These are CPU transformations, but not yet a standalone
download-and-rebuild interface.

Required before claiming disaster recovery: freeze a transitive training-source
lockfile (published accepted/repair outputs, revisions, files/hashes, conversion
and repeat/cap rules); preserve or deterministically reconstruct selection and
audit-admission records; pin tokenizer/template and source ordering; provide
a CPU-only rebuild that bypasses generation/audit workflows; verify from empty
directories against per-source counts and sampled epoch checksums. Exact epoch
reproduction needs stronger guarantees than equivalent source exposure.

### Status checked 2026-11-07

The isolated queue `data/rebuild_hf_dfm/serial-queue/plan.json` now records
**DFM1 through DFM9 done**. Each version has a `verified.json` receipt with
`status: matched`, covering all token values, epoch-index values and metadata
under the HF-only plus local lexdk/DBC policy. This receipt inspection supersedes
earlier incomplete reconstruction status; it did not rerun the full comparisons.

DFM10 has completed preparation and tokenization but is **blocked at assemble**
(nonzero exit from `scripts/rebuild_dfm10.py assemble`), with no final verified
receipt. DFM11–DFM15 remain pending with no completed stages and recipe/input-lock
holds. Existing production/training DFM15 data is not evidence that its isolated
HF reconstruction has completed. No queue or production state was modified by
this status check.

### DFM10 isolated reconstruction resumed, 2026-11-07

User requested continuation of DFM10. Fixed assembly's missing
`dfm10_synthetic_values_model_charter_da` manifest entry by using the same existing
fallback as source discovery, and made pre-created component directories resumable
while rejecting symlink directories. Fixed verification's boundary check: rebuilt
payloads must resolve inside the isolated queue; historical production arrays are
read-only comparison targets, not inputs subject to that input-root check.
Eight focused recipe tests pass, including partial-assembly resume and the queue
version ceiling. `--through 10` was added to the serial runner so this request
cannot start DFM11 accidentally.

Detached runner PID 1220270 executes the existing serial pipeline from completed
prepare/tokenize receipts, CPU-only with numerical-library threads capped at one.
Log: `logs/analysis/dfm10-reconstruction-20261107/runner.log`. Assembly has passed:
15,746 task directories, matching the historical inventory; the recipe's 15,748
entry count also includes non-task metadata entries. `assemble-receipt.json`
exists and the `verify` stage is now comparing fresh token arrays. Sampling and
full epoch-index/token/metadata comparison remain pending at this update.
Original failure logs are retained. No production files or B trainer settings
were changed.

**Provenance correction:** the prepared DFM10 recipe has `acquisitions: {}` and
4,351 digest-pinned local source entries, including public sources under
`data/converted_sources` and `data/dfm10_*_sources`. Its DFM9 base was HF-rebuilt,
but these additions do not establish an HF-only reconstruction. The queue's
blanket HF-only label must not be interpreted as evidence for DFM10. Corrected
the final DFM10 comparison receipt to report this local-source lineage explicitly.
This continuation can establish isolated historical token/index equivalence;
strict HF-only DFM10 recovery still requires the corresponding published input
acquisition and verification. DFM1–DFM9 receipts are unchanged.

### DFM1–9 provenance re-audit and DFM10 correction (2026-11-07)

Inspected completed recipes, input locks/acquisition receipts, and resolved
symlinks for DFM1–9. All nine have matched historical output receipts and
no observed public-data path outside the isolated HF rebuild/acquisition
root. External agreement paths are restricted to lexdk/DBC. DFM2 and DFM3
were regenerated from the HF-derived predecessors/raw acquisitions; DFM4
regenerated paragraphs/summaries from those predecessors and its three
pinned additional HF sources. Later published DFM2–4 packages are not the
basis for claiming the earlier executions downloaded those packages.
DFM5 uses pinned Sapient plus 82 acquired repositories and earlier verified
outputs; DFM6–9 continue that chain with pinned acquisitions/conversions.

Evidence: `logs/analysis/dfm-hf-provenance-20261107/path-audit.json` records
resolved-path counts and all nine original verification receipts. This is
a dataset-input provenance re-audit, not a new full payload rehash or a
claim that code, sampling policies and historical tokenizer assets require
no repository-local dependencies.

DFM10's prior local-input recipe was **not HF-only**; its misleading label
is superseded. User stopped the local-source execution. Its CLI now rejects
the legacy recipe, and the queue remains held. A separate pinned HF-only
acquisition is running; see [the corrected DFM10 runbook](/pages/dfm10-hf-rebuild-recipe.md).
