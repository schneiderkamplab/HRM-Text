# Source7 repair5 compact-review freeze handoff

Prepared root: `data/dfm13/wave4/source7-repair5-compact-26b-v1`.
State: CPU ready, no GPU launch; awaiting Boole/coordinator confirmation that
the compact-review module is frozen at the hash below. No direct agent-message
tool is available to this worker; this artifact and parent relay coordinate it.

Module: `dfm12/wave_compact_review.py`
SHA256: `d5b276948e1bdcf9f83464042780d9e973613b8359317774f4b0a0865ba661a0`
Shared one-shot executor: `dfm12/synthetic_repair_pilot.py`
SHA256: `9434d9dbc5ccc4837782ae5ac880b2392b71a56de4a64d5501a470b2eb3ccb0b`

Do not edit either dependency while the bounded client is running. If a
dependency changes before confirmation, preserve this prepared root and build a
fresh successor; do not reseal historical artifacts.

## Treatment

- Five one-shot assistant repairs: hu276f, sl7ec2, sra551, sqd8d7, bgf58e.
- Two supported original candidates (hr6d45, bg6f7c) are retained by original
  path/hash in the manifest and never sent for generation.
- Original source/user/tools immutable; no source errors silently corrected.
- Existing one-shot transport, raw capture, compact repair/apply/request/keeps
  APIs. Fresh audit sees original evidence plus repaired answer, not repair note.
- One repair plus one compact256-token audit per case, maximum five simultaneous
  requests on different shared8800-series endpoints. No second repair loop;
  failed/inflight stages are not replayed. No admission even after audit keep.
- Full student4096-token validation and original2400-character assistant bound.
- 43 focused tests pass;90 pins verify. Repair budgets6023-7422 tokens including
  response reserve; baseline compact-review budgets1649-3001. Actual repaired
  requests are measured again before dispatch.

## Launch After Confirmed Freeze Only

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -u -m dfm12.source7_repair run \
  --root data/dfm13/wave4/source7-repair5-compact-26b-v1 \
  --confirmed-compact-sha256 d5b276948e1bdcf9f83464042780d9e973613b8359317774f4b0a0865ba661a0
```

Launch detached via the existing operational Popen/start_new_session pattern,
record PID/create-time/start-ticks, and inspect each terminal result. Passing a
hash is an explicit coordinator freeze attestation, not a request to infer
readiness merely from file presence. No server/training lifecycle changes.
