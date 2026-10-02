---
type: Runbook
title: DFM12 Multilingual Quarter Production
description: Accepted-quota production with durable source allocation, retained strict review and shared-server ownership limits.
status: draft
last_updated: 2026-09-28
confidence: high
---
# Quarter Production

**2026-09-28 runtime update:** standalone production is superseded by
[joint nineteen-language production](dfm12-joint-synthetic-production.md),
retaining this ledger and the Faroese waivers below. The joint dispatcher has
a shared 512-request ceiling per endpoint across both campaigns.

## Current Milestone: Tenth

**2026-09-28 accepted Faroese shortfall:** the owner explicitly accepts the
three source-exhausted Faroese families at their existing accepted counts:
grounded instruction **2,453**, multi-turn **601**, summary/rewrite **725**.
Do not replenish seeds, recycle sources or retry these groups to fill their
original quotas. Other Faroese families and other languages continue normally.
These groups are intentionally complete for the present campaign, not problems
requiring further GPU work. The sealed live ledger still reports their old
targets and source-shortage labels; it was not edited during active production.
For reporting, exclude their **41,221-row** waived deficit from remaining work:
the adjusted seven-language ceiling is **343,779**, rather than 385,000,
assuming all other groups meet their targets. At finalization, reconcile the
waived groups under the controller lock instead of waiting for nonexistent seeds.

**2026-09-27 superseding decision:** the user reduced the initial production
milestone to one tenth of the full 3,850,000-row plan: **385,000 accepted
conversations**, approximately **611,050,000 estimated rendered tokens**.
The quarter-scale table below is historical, not the current stopping target.
Keep the existing campaign directory and stable row IDs; retain passing pilots
and new production rows. The first pilot counts only after its new re-audit.

| Family | Each of NB/NN/IS/FO | Each of NL/SV/PL | Total |
|---|---:|---:|---:|
| Multi-turn | 15,000 | 7,500 | 82,500 |
| Grounded instruction | 20,000 | 10,000 | 110,000 |
| OpenHermes translation/adaptation | 15,000 | 7,500 | 82,500 |
| Summary/rewrite | 10,000 | 5,000 | 55,000 |
| Math/code | 6,000 | 3,000 | 33,000 |
| Native tool dialogue | 4,000 | 2,000 | 22,000 |
| Total | 70,000 | 35,000 | 385,000 |

Retarget only while the controller is fully drained, under its exclusive lock.
Preserve historical configuration/manifests and accepted records; do not change
source cursor signatures or generation/review policy to change a row quota.

The migration completed under the controller lock, preserving19,060accepted
rows and40,629counted candidates, with0active requests. Receipt:
`data/dfm12/multilingual-quarter-native-20260927/retarget-tenth-v1/completion.json`.
The first-pilot re-audit/import handoff then started; generation resumes afterward.

Initial measured production rate was101-102acceptedrows/minute across the first
80-95%of5,629new production decisions. A throughput-only estimate for the tenth
milestone is roughly2.5days, excluding supply stalls and review overhead.
**Not a guaranteed completion ETA:** seed preparation finished with only6,793
eligible Faroese windows,63,562Icelandic and77,889Nynorsk, against requested
250,000each. Short source rows caused most exclusions. Native-source quotas,
especially Faroese, need additional eligible supply to finish without recycling
windows or weakening gates. Startup re-audit also recorded66server-disconnect
failures; these are not quality rejections or accepted training rows.

The user explicitly authorized quarter production after the
[35K native-schema pilot](dfm12-multilingual-native-pilot.md). This supersedes
the earlier no-bulk-launch restriction. It does not certify the reviewer as
native-quality gold or authorize bypassing checks on rejected/invalid rows.
The [simpler-schema experiment](dfm12-generation-grammar-diagnosis.md) remains
unused. Production retains v6 native decoding, the original strict CPU schemas,
indexed evidence and semantic checks, deterministic grounding/tool checks and
Gemma student rendering validation. No automatic upload or final data sampling.

## Cumulative Targets

Historical quarter authorization, superseded by the tenth milestone above:

`dfm12/multilingual_extension.yaml` remains the target source of truth.
Total quarter target: 962,500 accepted conversations, approximately 1.528B
estimated rendered training tokens before actual accepted-row token accounting.

| Family | Each of NB/NN/IS/FO | Each of NL/SV/PL | Total |
|---|---:|---:|---:|
| Multi-turn | 37,500 | 18,750 | 206,250 |
| Grounded instruction | 50,000 | 25,000 | 275,000 |
| OpenHermes translation/adaptation | 37,500 | 18,750 | 206,250 |
| Summary/rewrite | 25,000 | 12,500 | 137,500 |
| Math/code | 15,000 | 7,500 | 82,500 |
| Native tool dialogue | 10,000 | 5,000 | 55,000 |
| Total | 175,000 | 87,500 | 962,500 |

Pilot rows count only after validation and deduplication. Failed attempts and
semantic rejections do not count. Candidate attempts are bounded; exhausted
groups and source shortages must be reported, not filled by relaxing checks.
Stable record identities do not include the milestone, so later half/full
expansions can retain existing rows rather than regenerate them.

## Sources and Memory

The pilot-only reservoirs are too small for production. Native source preparation
must scan broadly across the pinned DynaWord files/row groups and preserve each
window's provenance. Modernized English/Danish OpenHermes provides complete
conversation seeds, never truncated to fit. Already consumed pilot sources are
excluded. Identical native source windows cannot cycle across task families;
an OpenHermes source may intentionally be adapted into different target languages.

`dfm12.multilingual_production_specs.SourceProvider` durably records every
selected source/specification in SQLite before generation. Resuming a slot
returns its exact specification. Missing seeds raise `SeedUnavailable`, not a
wrap-around fallback. Native and OpenHermes readers use a separate append-only
seed SQLite database, allowing CPU preparation to proceed alongside generation.

Measured pinned native corpus row counts: NB 535,292; NN 146,447; IS 1,149,266;
FO 313,617; NL 250,549; SV 849,425; PL 1,623,521. These are source rows, not
guaranteed eligible windows or accepted conversations. In particular Nynorsk
needs careful source-supply accounting rather than assumptions of unlimited data.

## Execution Constraints

**2026-09-28 superseding client-concurrency decision:** user accepts the existing
Faroese source supply and requests more concurrency for available work. Do not
expand or recycle those sources. Raise the client ceiling from32to64requests
per server (512total), without restarting/reconfiguring the borrowed servers.
Shared-server measurements showed86-96%KVcache use and about160running requests
per endpoint while this campaign had only28active candidates. Its workers had
permanently exited after transient server disconnects (220recorded generation
or review disconnects at inspection).

The revised controller keeps workers alive through transient circuit failures,
with serialized endpoint recovery after30seconds. New candidate reservations
require measured KVusage<=90%, zero waiting server requests and0.2second
spacing. Existing generation/review stages can finish without that admission
gate. Failed metric probes pause new admissions; nontransient HTTPrejections
require operator attention. No replay of failed rows and no changes to quality
checks, quotas or identity training. `admission-status.json` explains throttling.

Verified launch: detached controller PID `1336576`, with
`--concurrency-per-server 64 --max-kv-cache-utilization 0.90 --timeout 600`.
The offline controller-pin migration preserved all 87,522 accepted rows;
its receipt is under `controller-upgrade-concurrency64-v1/` in the campaign
directory. After about 199 seconds, the controller reported 87,814 accepted
rows and 339 active candidates. Endpoint waiting queues were zero at that
snapshot; KV usage ranged from 69% to 93%, so some admissions were throttled.
The controller, admission, migration, retarget and import tests passed
(103 tests). No sustained throughput improvement is claimed from this short
startup measurement.

The old32request ceiling below describes the original launch, not the updated
client ceiling. The quarter directory name remains historical.

Use the existing eight borrowed `google/gemma-4-26B-A4B-it` servers, ports
8600-8607, with at most 32 requests per server and 600-second request timeouts.
No server startup, restart or teardown; no changes to identity training or
unrelated jobs. Keep the established memory ownership limits.
Generation temperatures are 0.65 general and 0.75 tool dialogue, repetition
penalty 1.15; reviews use temperature 0 and frequency penalty 0.5.

One controller owns quota/accepted bookkeeping. Concurrent requests must have
unique paths, atomic receipts and deterministic deduplication. Quota reservations
must include in-flight candidates to avoid overfilling. Terminal failures remain
recorded; unknown in-flight requests are never silently accepted or replayed.

## Launch on 2026-09-27

Campaign root: `data/dfm12/multilingual-quarter-native-20260927`.
CPU seed root: `data/dfm12/multilingual-production-seeds-20260927`.
All 16,850 passing pilot rows were revalidated against saved raw responses,
strict review checks and rendered student examples before import. Initial
remaining quota is 945,650 accepted conversations. The 35,000 pilot attempts
also count toward the bounded attempt budget.

Detached controller PID at launch: `4159737`; seed builder: `4156543`.
These are historical launch identifiers, not authority to signal processes.
The controller reached `phase=running`, allocated 256 new candidates and
saved generation responses and candidate/review artifacts. Its initial
progress snapshot showed 253 active candidates. Identity training continued.

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.multilingual_quarter verify \
  --root data/dfm12/multilingual-quarter-native-20260927

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
setsid /home/ucloud/miniforge3/envs/hrm/bin/python -B -u \
  -m dfm12.multilingual_quarter run \
  --root data/dfm12/multilingual-quarter-native-20260927 \
  --concurrency-per-server 32 --timeout 600 \
  > data/dfm12/multilingual-quarter-native-20260927/client.log 2>&1 < /dev/null &
```

Use that run command only when no controller owns the campaign lock.
`progress.json` is updated every 15 seconds; `jobs.sqlite` is the durable
quota ledger. Source preparation continues independently. Scarce language
source pools can pause groups rather than reuse seeds; the target is not a
guarantee of sufficient unique source supply. No upload or sampling is launched.
The controller/source-preparation/source-allocation test set passed 43 tests.

### First-Pilot Accounting Gap

The first pilot (`data/dfm12/multilingual-pilot-20260925`) completed with
33,305 accepted and 1,695 exhausted slots. Its accepted fingerprints protect
cross-cohort deduplication and its consumed sources are excluded from new
allocation, but its accepted rows are **not yet credited to this controller's
quota ledger**. Only the later 16,850 passing native-schema rows were imported.
The first pilot is preserved, not discarded. Reconcile its older-contract
accepted artifacts and per-family counts before final quota/build accounting;
do not assume deduplication seeding also imported training records.

The user subsequently authorized [re-auditing and including the first
pilot](dfm12-first-pilot-reaudit.md). Its passing rows will be credited after
the completed review/import transaction, not before.
