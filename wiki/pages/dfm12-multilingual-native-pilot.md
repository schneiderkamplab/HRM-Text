---
type: Runbook
title: DFM12 Native-Schema 35K Pilot
description: Explicitly authorized seven-language pilot using the retained strict native-schema generation and review path.
status: draft
last_updated: 2026-09-27
confidence: high
---
# Native-Schema 35K Pilot

On 2026-09-27 the user explicitly requested keeping the previous version and
running the full 35K pilot. This supersedes the earlier prohibition on starting
35K generation, not the validation rules or the requirement to review results
before training admission. Calibration has NOT been declared passed.

The [simpler-schema experiment](dfm12-generation-grammar-diagnosis.md) remains
isolated and is not used. Retained behavior: v6 native JSON-schema transport,
strict original CPU schema and indexed evidence checks, native tool assembly,
student-template validation, and streaming loop guards. General generation
temperature 0.65, tool generation 0.75, repetition penalty 1.15; reviewer
temperature 0 and frequency penalty 0.5. No temperature-0.25 prompt experiment.

## Allocation

Seven languages: Bokmal, Nynorsk, Icelandic, Faroese, Dutch, Swedish and Polish.
Each gets 5,000 candidate slots:

| Family | Per language | All languages |
|---|---:|---:|
| Grounded instruction | 1,900 | 13,300 |
| Summary/rewrite | 1,100 | 7,700 |
| Multi-turn | 1,000 | 7,000 |
| OpenHermes translation/adaptation | 500 | 3,500 |
| Math/code | 300 | 2,100 |
| Native tool dialogue | 200 | 1,400 |
| Total | 5,000 | 35,000 |

This is 35K attempts, not a promise of 35K accepted rows. Loop failures,
invalid structures, failed deterministic checks, duplicates and semantic
rejections remain separately recorded; no repeated generation until success.

## Preparation and Ownership

`scripts/prepare_multilingual_pilot_v6.py` uses the unused failed
`multilingual-pilot-20260926-v3` reservoir, preserving its first-cohort exclusions
and prior accepted-hash ledger. Whole sources that fail contract/context checks
are recorded and replaced before sealing, not truncated. Source allocation is
non-wrapping, with full per-language/family quotas checked.

Root: `data/dfm12/multilingual-pilot35000-native-20260927`.
The sealed manifest pins specifications, source evidence, implementation and
test receipts. Diagnostic seed exposures are not independent held-out data.

Reuse borrowed Gemma 4 26B A4B servers on localhost ports 8600-8607, with a
maximum of 32 client requests per server. Do not launch, reconfigure, stop or
claim ownership of these shared servers. Identity training remains running
with its existing memory limits and W&B run. No automatic upload, final dataset
sampling, training admission, or successor campaign.

## Launch

Prepared all 35,000 unique slots; 427 overlong OpenHermes sources were replaced
without truncation. 209 runner/adapter tests passed before sealing. The runner
and immutable input hashes were verified before launch; tokenizer symlink
targets are pinned by resolved path as required by the runner.

```bash
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -B -u \
  -m dfm12.multilingual_pilot_v6 run \
  --root data/dfm12/multilingual-pilot35000-native-20260927 \
  --concurrency-per-server 32 --timeout 600 \
  > data/dfm12/multilingual-pilot35000-native-20260927/client.log 2>&1 < /dev/null &
```

Initial client PID: 3829071. Status is `progress.json`, including per-language
and per-family counts, terminal/remaining slots, effective keeps and runtime.
Raw requests/responses, stages, candidates and outcomes have unique slot IDs.
The exclusive `pilot.lock` prevents a second writer. SIGTERM/SIGINT drains
current workers without starting more slots; no shared server is signalled.
Resume skips terminal outcomes and reuses completed stages, while ambiguous
inflight work is marked unknown rather than silently rerun.

## Completed Pilot

The pilot completed all 35,000 slots on 2026-09-27. Of 27,244 valid final
outcomes, 16,850 passed all checks (48.14% of slots), and 10,394 did not.
There were 3,906 invalid generation/assembly outputs, 3,806 invalid reviews,
one review preflight failure and 43 unknown-abort requests (16 generation,
27 review). No rows were admitted or uploaded. The final progress snapshot's
`active` field is the last periodic worker count, not evidence of a live worker;
use `phase=completed_diagnostic`, remaining=0 and process state for completion.
