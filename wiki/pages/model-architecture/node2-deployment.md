---
type: Runbook
title: Additional B200 experiment node deployment
status: draft
confidence: high
last_updated: 2026-11-17
---
# Additional B200 experiment node deployment

Implementation started on2026-11-17. Prepare all architectures; assign remaining
objective ablations first. Whole experiments and evaluations remain node-local.
No duplicate writable scheduler database or multi-node trainer is intended.

Source inventory and tracked recovery patch:
`logs/deployment/node2-20261117/`. The detailed inventory includes9933 entries;
most untracked files belong to incoming repository copies and generated caches.
Do not stage these wholesale. Tokenizer assets in data_io are external artifacts;
the dfm-evals submodule has a source modification requiring separate review.

Deployment branch: `deployment/node2-20261117`, isolated worktree
`/work/dfm/HRM-Text-node2-deployment`. No source commits or remote updates have
yet been qualified. User performs pushes after commit review.

Remote endpoint: `ucloud@ssh.cloud.sdu.dk:2426`, checkout
`/work/mimir/HRM-Text`. User-approved ED25519 fingerprint:
`SHA256:XbZvj6OCPyJRByMzQYuRazuqGYzQQvMGI3WVSPam2tw`.
Pinned host key is in the deployment receipt directory. CPU node has an hrm
Python environment; GPU validation awaits user allocation of8 B200 GPUs.

Remaining: complete source/submodule review and topic commits, artifact closure
and verified transfers, remote environment reproduction, exclusive experiment
ownership partition, GPU qualification and supervised launch. Preserve active
training and existing pause/resume requests throughout preparation.

## Source preparation completed for push — 2026-11-17

Supersedes the initial not-yet-committed status above. Review used an isolated
worktree; all deliverable commits are intended for **main**, including the
separate dfm-evals submodule main commit. Nothing is pushed automatically.

Reviewed topic groups cover shared training/sampled recursion/MixedLM, Sandwich
and Ouro, Embla and kernels, evaluation lifecycle/publication, experiment
operations, DFM16 audit tooling, historical data rebuilds and durable wiki/report
knowledge. The large generated decision-volume JSON stays external; its hash and
size are recorded in `config/deployment/external-artifacts.json`. Imported
repository mirrors, caches, generated predictions and credentials are not source.

Portable recipe snapshots live in `config/deployment/dfm11`; four full configs
were recovered from ignored diagnostics directories. `config/deployment/node2.json`
records the approved SSH identity and initial ablation ownership proposal with
launch disabled. `config/deployment/source-environment-20261117.json` records
package versions and the pinned FA4 source revision; it is an inventory, not a
claim of a qualified remote environment. Render recipes without launching:

```bash
python scripts/render_experiment_node.py --output /new/absolute/preparation-directory
```

The renderer rebases repository/environment paths and refuses an existing output
or an enabled launch profile. Actual resume checkpoint selection, scheduler
ownership migration, artifact closure/transfers and remote GPU qualification
remain post-push work. No current experiment was moved to the other node.

Verification:111 core architecture tests passed (one skip);282 scheduler and
suspension tests passed;23 Danish semantic tests passed in the eval environment;
634 changed-file tests passed (three skips), with15 external-asset failures in
the clean worktree. Re-running those15 against original workspace assets passed
13; the remaining two already fail there because the DFM12 frozen combine module
and Kaenguruen parquet are missing. These are recorded prerequisite limitations,
not silently skipped checks. Two deployment-renderer tests passed. All441 reviewed
Python source files parsed. Initial wiki validation retains the known oversized
scheduler-page error; extra clean-worktree warnings reference excluded artifacts.

Detailed receipts remain in `logs/deployment/node2-20261117/` on the source node.
The user's next action is push; transfers and execution remain disabled until
pushed revisions can be verified from the destination.
