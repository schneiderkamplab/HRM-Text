---
type: Runbook
title: DFM12 Scoped Inclusion Audits
description: Explicit user-authorized Scandi and NorQuAD/FLEURS audit queues, with retained benchmark lineage and no implicit acceptance.
tags: [dfm12, audits, scandi, norwegian, provenance]
status: draft
last_updated: 2026-09-25
confidence: high
---
# DFM12 Scoped Inclusion Audits

## Completion, GPU Release and Handoff

Later on 2026-09-25 the user requested terminal audits without retrying failed
jobs, release of only the audit GPUs, and independent training continuation and
finished-dataset export/upload. `dfm12.audit_completion_release` implements the
completion barrier and process release only; Jason owns the verified training
resume command and Harvey owns export/upload orchestration.

Detached watcher **PID 2211212** was armed with:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.audit_completion_release \
  --root data/dfm12/audit-completion-release-20260925-v1
```

The root contains `launch.json`, `pins.json`, `status.json`, and `watcher.log`.
Pins bind boot ID, exact PID/starttime/executable/argv for API PIDs
1483285 through 1483292 on ports 8400 through 8407, and their 16 descendants
(24 total). Listener socket ownership was verified during pinning. No unrelated
process or environment is captured for termination.

The barrier queries SQLite read-only for main, SV, PL/IS, scoped Scandi, scoped
NorQuAD/FLEURS, and identity. Every manifest-pinned source must exist with the
same hash and `complete=1`; jobs must all be `done` or `failed`. Identity unique
records must have terminal audit jobs. Missing, pending, running, parked and
unknown states block release. Runtime JSON is not completion authority. It also
waits for audit clients to exit, acquires all six client run locks, then repeats
the barrier. No rows, attempts, leases or retry policies are modified.

Release uses Linux pidfds via libc (this Python build lacks the Python pidfd
wrappers), verifies identity again after obtaining each pidfd, and sends TERM
only to pinned APIs. After a grace period, pinned remnants receive TERM and,
after another grace period, KILL. Zombies count as exited. New descendants or
reused/changed process identities fail closed. Successful release requires no
pinned GPU compute processes and closed audit ports. Any unrelated GPU process
is reported and never killed. Evidence is in `completion-barrier.json`,
`release-progress.json`, and `gpu-release.json`.

Training and export/upload hooks are independent, training checked first,
and neither runs before the verified GPU-release receipt. Each ready marker is
published by the coordinating owner after command files are final:

```json
{
  "ready": true,
  "user_authorized": true,
  "scope": "finished_dataset_export_upload_only",
  "argv": ["/absolute/python", "-u", "-m", "approved.module"],
  "cwd": "/work/mimir/HRM-Text",
  "pins": {"/absolute/final-command-file": "SHA256"}
}
```

Use `finalization-ready.json` with the scope above, or `training-ready.json`
with scope `verified_training_resume_only`, in the watcher root. Marker absence
does not delay GPU release. Hook claims are written before subprocess launch,
so crashes/errors never implicitly retry uploads or training startup. Hooks run
detached and concurrently; finalization failure cannot block training startup.
Their `*-started.json`, `*-process.json`, `*-completion.json` and separate logs
retain evidence. No ready command is invented while owner verification is pending.

The training hook was subsequently confirmed ready by the parent and armed in
`training-ready.json`, pinning the finalized
`scripts/resume_xxl_after_dfm12_audit.py` and the scheduler's
`resume-after-dfm12-audit/prepared.json`. Its command is the HRM Python with
`-u scripts/resume_xxl_after_dfm12_audit.py --start-after-gpu-release`.
Prepared state resumes `ephemeral_step_650500` in the same scheduler plan;
the hook rechecks checkpoint/dependencies, requires no GPU compute processes
and at least 178,000 MiB free on each of eight GPUs. Four hook tests passed
locally; parent also reported all 18 combined resume/release tests passing.
Watcher PID 2211212 remained live without restart and was still waiting for
audit completion when the marker was published. Training was not yet invoked.

**Temporary hold, later 2026-09-25:** the parent identified the watcher's empty
`CUDA_VISIBLE_DEVICES` inheritance and assigned Jason an explicit eight-GPU
environment fix in the resume hook. The training marker was set `ready=false`
pending that finalized fix and refreshed script hash. No watcher/server restart
or training invocation occurred. This supersedes the armed state above until
the ready marker is republished after confirmation.

**Hold resolved, later 2026-09-25:** the parent confirmed the finalized resume
hook now sets `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7` explicitly and reported
30 passing combined export/identity/orchestration/resume tests. The training
marker was re-armed with fresh script and prepared-receipt hashes. Independently,
`finalization-ready.json` was armed after validating the `helpers_ready`
orchestration contract and every helper-evidence hash (nine total pins including
the contract). Its exact command is:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.export_orchestrator once \
  --contract data/dfm12/export-orchestration-ready-20260925.json \
  --state data/dfm12/export-orchestration-20260925 \
  --lock-wait-seconds 43200
```

The 12-hour lock wait serializes this final pass behind the already-running
export/upload orchestrator without blocking the independent training hook.
Both markers are ready and all pins verified; watcher PID 2211212 remains in
`waiting_audit_completion`. Neither hook had started at this publication, and
no watcher, audit client or server restart was performed.

Fourteen focused tests passed in `tests/test_dfm12_audit_completion_release.py`,
covering terminal states, source completion/hash gates, descendant boundaries,
PID reuse/argv changes, zombies, the libc pidfd capability, missing hook markers,
and independent one-shot hook launch. At arming, only the main audit was still
nonterminal; all other queues and identity were terminal. Those counts are a
historical arming observation, not a permanent live counter.

Related: [audit readiness](dfm12-audit-readiness.md),
[Scandi source review](dfm12-scandi-translated-instruct.md),
[Norwegian preparation](dfm12-norwegian-dynainstruct.md).

## Authorization Boundary

On 2026-09-25 the user explicitly requested inclusion of Scandi and
NorQuAD/FLEURS and that their audits be queued. Preparation owners retain
full native messages, remove ordinary duplicates, and retain known held-out
annotations. This authorizes automated quality review of these named additions;
it does not imply human/native-speaker approval, benchmark cleanliness, accepted
export permission, upload, training or final sampling.

`dfm12.scoped_inclusion_audit` registers a persistent detached waiting launcher.
`data/dfm12/scoped-inclusion-audits-20260925-v1/registration.json` is the explicit
two-family registration; `watcher-launch.json` records the current exact PID and
command; `status.json` distinguishes waiting, validating, running and completed.
The watcher started before CPU completion rather than leaving a manual command
for later. The small Norwegian integration is validated independently of the
large Scandi integration. Current PID should be read from the launch receipt,
not inferred from historical messages.

## Launch Contract

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.scoped_inclusion_audit \
  --root data/dfm12/scoped-inclusion-audits-20260925-v1
```

The deployed process is launched with `subprocess.Popen(start_new_session=True)`
and logs to `watcher.log`. This survives CLI exit. A file lock prevents duplicate
watchers. Integration paths are registered explicitly, never discovered by
glob or selected by newest directory. No source file is consumed until a
version-1 `complete_unaudited` integration and all candidate/receipt/evidence
checksums pass. All records are validated before a client starts.

Each family gets a dedicated subdirectory, immutable `sources.json`, copied
prior operational findings plus a separate explicit user authorization note,
`scoped-screen.json`, `jobs.sqlite`, `launch.json`, `configuration.json`, and
`client.log`. The launcher reuses `dfm12.audit_full`: a single SQLite broker,
bounded preparation/HTTP buffers, two CPU preparation workers, and client
concurrency 128 per endpoint. Endpoints are existing ports 8400 through 8407,
served model `google/gemma-4-26B-A4B-it`. No server restart or main-queue source
mutation is performed. Families can execute independently.

## Scoped Gates

The new CrossScreen wrapper is opt-in through a dedicated scoped manifest.
Existing cross-screen manifests retain their prior behavior. Only matching
component, source path and SHA256 can use the wrapper. It suppresses the three
held-out ID/text/reference quarantines for the explicitly included Norwegian
source pool; for Scandi this additionally requires exact-message-bound known
MURI held-out lineage. All annotations remain in audit records. Duplicate and
shared-source gates stay active unless the Scandi completed integration
explicitly resolves them with pinned overlap/exclusion evidence and
`authoritative_filtered=true`. Legacy XML tool and no-truncation context-length
gates still apply. Sources outside the
pinned scope fail closed. `accepted_exports_allowed=false`,
`benchmarks_clear=false`, and incomplete inherited coverage remain explicit.

NorQuAD/FLEURS are restricted to exact component names
`norquad-wikipedia` and
`fleurs-alpaca-en-no`, the pinned Norwegian composite repo
and revision, their specific inclusion policy, and explicit benchmark-lineage
metadata. Both components must complete before their client launches.
Scandi must match its pinned repository/revision; generic Norwegian requires
the source-specific authorized validator, not blanket permission for `no`.

## Verification

Final combined regression run: **57 tests passed** across scoped inclusion,
cross-screen gates, Scandi admission, audit readiness and the full audit client. Tests verify
that original held-out gates remain active, scoped held-out override cannot
spread to another component/hash, duplicates and tools remain quarantined,
and modified integration evidence is refused.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m pytest -q \
  tests/test_dfm12_scoped_inclusion_audit.py tests/test_dfm12_audit_gates.py \
  tests/test_dfm12_audit_readiness.py tests/test_dfm12_audit_full.py \
  tests/test_dfm12_scandi_admission.py
python scripts/validate_okf.py wiki
```

Deployment verified on 2026-09-25: detached watcher **PID 2051761**, isolated
NorQuAD/FLEURS audit client **PID 2051971**. The current Norwegian queue contains
all **3,343** prepared rows (1,886 NorQuAD + 1,457 FLEURS), zero quarantines.
At the verification snapshot, **3,342 decisions completed**, one FLEURS request
remained running, zero failed, and all eight endpoints had successful decisions
(417 or 418 each). NorQuAD was fully complete. This is an operational snapshot,
not a permanent live counter; consult `status.json` for subsequent completion.

Scandi is registered against the exact expected atomic completion artifact
`data/dfm12/scandi-included-20260925-v1/integration.json`; its producer was still
converting/tokenizing at this snapshot. The watcher automatically validates and
launches it when published. Norwegian integration is pinned from
`data/dfm12/norwegian-benchmark-inclusion-20260925-v1/integration.json`.
Logs are `<watcher-root>/watcher.log` and
`<watcher-root>/norquad-fleurs/client.log`; each launched family has an exact
command/PID receipt in `launch.json`. The parent added the wiki index link;
OKF validation returned zero errors and zero warnings.

Audit completion must be verified from per-component job results. A waiting
registration is not a completed audit, and a model keep decision is not human
review. Pending CPU handoffs remain visible in watcher status rather than
being relabelled as queued row-level work.
