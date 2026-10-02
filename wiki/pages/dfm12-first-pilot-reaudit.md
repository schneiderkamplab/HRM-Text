---
type: Runbook
title: DFM12 First Pilot Re-audit
description: Recheck historical pilot accepts and credit passing rows toward quarter production without regeneration.
status: draft
last_updated: 2026-09-27
confidence: high
---
# First Pilot Re-audit

The user authorized including the first multilingual pilot after re-auditing.
The subsequent milestone decision is one tenth of the full plan (385,000
accepted rows); "quarter" in existing directory/module names is historical.
This resolves the accounting gap recorded in
[quarter production](dfm12-multilingual-quarter-production.md), not by trusting
old keep flags, but by applying the current review checks to original examples.

Source: `data/dfm12/multilingual-pilot-20260925`.
Its completion receipt contains 33,305 accepted and 1,695 exhausted slots.
Re-audit the accepted candidates only, without rewriting conversations or
regenerating failed rows. Preserve original files and provenance. Tool arguments
must be grounded in user messages or prior tool results; hidden seed metadata
must not be treated as information supplied by the user.

Re-audit root: `data/dfm12/multilingual-first-pilot-reaudit-20260927`.
Quarter root: `data/dfm12/multilingual-quarter-native-20260927`.

## Execution and Inclusion

Drain only the quarter generation controller before the re-audit. Do not stop
identity training, shared vLLM servers or unrelated work. Borrow ports 8600-8607
at 32 requests per server, with no new GPU model allocations.

`scripts/reaudit_first_pilot_handoff.py` requires a drained quarter ledger,
holds its controller lock while the separate re-audit client runs, invokes the
offline importer, then resumes quarter generation. Audit/import errors are
recorded and do not admit incomplete results; generation resumes without those
credits. The handoff does not send process signals or operate servers.

`dfm12.multilingual_quarter_import` requires a completed, pinned re-audit and
independently verified review receipts. Accepted content keeps a stable campaign
ID. Quota credit, fingerprint ownership transfer and an import receipt commit
in one SQLite transaction. Repeated import cannot double-count. Existing
quarter targets and pinned implementation files remain unchanged.

No final sampling or HF upload is authorized by this operation. Rejected and
invalid reviews remain excluded. Neither old nor new automated approvals are
native-speaker certification.

## Commands and Verification

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u \
  -m dfm12.multilingual_first_pilot_reaudit prepare \
  --root data/dfm12/multilingual-first-pilot-reaudit-20260927 \
  --source data/dfm12/multilingual-pilot-20260925 \
  --quarter-root data/dfm12/multilingual-quarter-native-20260927
```

After preparation and an explicitly verified drain of the quarter controller:

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -B -u \
  scripts/reaudit_first_pilot_handoff.py --arm \
  --quarter-root data/dfm12/multilingual-quarter-native-20260927 \
  --audit-root data/dfm12/multilingual-first-pilot-reaudit-20260927 \
  > data/dfm12/multilingual-first-pilot-reaudit-20260927/handoff.log 2>&1 < /dev/null &
```

Progress is in the audit root's `progress.json`; orchestration is in
`handoff-status.json`. `client.log` contains review-client errors, `import.log`
contains the import result, and `handoff-finished.json` records whether quarter
generation actually resumed. Never rerun a completed handoff blindly.

The combined re-audit, importer, handoff and existing quarter test suite passed
57 tests before launch. A real CPU smoke rendered one example from each family;
an old tool example was correctly flagged for a warehouse argument present only
in generator metadata. The first-pilot's 33,305 fingerprints were confirmed to
have `prior-history` ownership in the production ledger before re-auditing.

CPU preparation finished for all 33,305 rows: 31,710 pending model review,
1,595 rejected by deterministic checks. No model-review passes have yet been
credited at this preparation point.

The handoff was launched after the tenth-milestone migration, supervisor PID
21851 and review client PID21924 (historical launch identifiers). Runtime
confirmed eight endpoints with32requests/server; initial model-review accepts
and rejections were written. Import accepts the archived quarter context only
when the committed migration proves quota/controller-only changes with all
other manifest fields unchanged. Combined tests passed72cases.

## Completed Re-audit and Import

All33,305rows reached terminal decisions:20,892accepted,6,440semantic
rejections,1,595CPUrejections,4,026invalid model review outputs,240invalid
review-content checks,109unknown-status infrastructure failures and3invalid
preflights. Failures are not accepted or counted as semantic rejections.

The handoff successfully imported all20,892passing rows and confirmed production
resumption (PID299247 at launch). Together with16,850second-pilot keeps, the
two pilots contribute37,742accepted rows. Existing production accepts remain
in the same385,000-row campaign. See `handoff-finished.json` and `import.log`
in the re-audit root for the committed result; do not rerun the handoff.
