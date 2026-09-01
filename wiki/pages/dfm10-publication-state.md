---
type: Dataset Inventory
title: DFM10 Publication and Sampling State
description: Current Hugging Face publication completeness, final sampling state, and training-data transfer record.
tags: [dfm10, datasets, hugging-face, sampling]
status: stable
last_updated: 2026-08-31
confidence: high
---
# DFM10 Publication and Sampling State

Direct reconciliation against the public `schneiderkamplab` Hugging Face
namespace on 2026-08-31 found all 72 materialized
`exports_dfm10/dfm10-*` packages present. No materialized package remains to
upload. The final addition is
`schneiderkamplab/dfm10-synthetic-values-model-charter-da` at revision
`f4d2dd8a62fd13a81b6972753d7837b9724f12ac`: 1,343 independently accepted
Danish rows from 1,360 English Model Charter scenarios. Its 623,325 unique
tokens are sampled at repeat ten, contributing 6,233,250 tokens per epoch.

**Superseded:** the earlier 2026-08-31 record described a 71-package inventory,
a stale 65-package generated summary, and a 103,143,215,009-token sample that
predated the final source integrations and Folketing caps.

The authoritative final union has 15,746 tokenized task directories. The
atomically promoted `data/sampled_dfm10` contains ten complete epoch index sets
and `92,658,813,451` tokens per epoch at a maximum stored sequence length of
4,097. Its materialized training footprint is approximately 878 GB. Training
requires this sampled directory; the converted and tokenized source trees are
construction artifacts rather than runtime inputs.

## Transfer to Mimir

On 2026-08-31 a resumable transfer was started to
`ssh.cloud.sdu.dk:2091:/work/mimir/HRM-Text/data/sampled_dfm10/`. The detached
client PID is recorded in `logs/transfers/dfm10_to_mimir.pid`; progress and
final statistics are written to the newest
`logs/transfers/dfm10_to_mimir_*.log`. The verified launch command is:

```bash
setsid rsync -a --partial --append-verify --human-readable \
  --info=progress2,stats2 \
  -e 'ssh -p 2091 -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6' \
  data/sampled_dfm10/ \
  ssh.cloud.sdu.dk:/work/mimir/HRM-Text/data/sampled_dfm10/
```

The initial measured throughput was approximately 576 MB/s. Re-running the
same command safely verifies and resumes a partial transfer.
