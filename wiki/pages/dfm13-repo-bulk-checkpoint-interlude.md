---
type: Runbook
title: Repo Bulk Checkpoint Interlude
description: Fully written checkpoint gate and automatic training resume after all Repo GPU stages.
tags: [dfm13, training, operations]
status: stable
last_updated: 2026-10-01
confidence: high
---
# Repo Bulk Checkpoint Interlude

User authorization on 2026-10-01 supersedes co-resident inference for this bulk
run: stop auxiliary TP8, soft-stop the existing scheduler, wait for fully written
`ephemeral_step_2981000`, then stop the exact torchrun and use eight independent
Gemma servers. Training is automatically resumed after all Repo GPU work.

Watcher: `scripts/dfm13_repo_bulk_interlude.py`.
Receipts: `logs/dfm13/repo-bulk-interlude-2981000/`.
Plan: `logs/scheduler/dfm12_XL_epoch11_noidentity`.
Row: `dfm12-xl-e11-step_3000000-train`.

The existing completeness checker validates sidecar, DCP metadata and all shard
byte extents. Hardlinks preserve the checkpoint. Only identity-verified torchrun
is signaled; scheduler exit and GPU release are required. `PlanLock` protects
the resume-row update to the new tag/path, pending status, retry count and log
directory. The original command and W&B configuration are unchanged; the obsolete
manual-pause reason is removed. No new scheduler plan is created.

The existing eight-server launcher uses ports 8800-8807, alias `dfm13-gemma4`,
utilization .95, max sequences 1024, context 32768. Owned private-session cleanup
also discovers vLLM workers that discard environment tokens. Client cap: 256 per
endpoint. The watcher does not launch Repo or search clients itself.

## Completion Contract

Harvey waits for `servers-ready.json` in the receipt root. After generation,
review, bounded repairs and their reviews are terminal and GPU clients have
exited, atomically write `bulk-gpu-terminal.json` there:

```json
{"status":"complete","all_gpu_stages_terminal":true,"gpu_clients_stopped":true}
```

Terminal errors use `status: failed`, preserving failed rows. First-stage exit
alone is insufficient. CPU exports may continue afterward. Server startup has a
30-minute timeout; bulk GPU work has a 24-hour watchdog. Errors and timeouts enter
the same `finally` teardown. No unrelated GPU processes are killed.

Resume requires owned-server cleanup, no remaining GPU compute processes, intact
checkpoint and unchanged owned stop marker. The scheduler CLI clears the stop;
the same plan restarts with persistent vLLM and explicit GPU visibility 0-7.
Cleanup or ownership failures leave training paused rather than creating overlap.
`training-resumed.json` records the runner; `interlude-error.json` preserves errors.

Armed watcher 3077322 was superseded before checkpoint completion by 3077599 to
handle absent process identities safely. Current identity is in
`watcher-launch.json`. Nine CPU tests passed, covering rejection of first-stage
completion and acceptance of all-stage terminal failure for cleanup/resume.
