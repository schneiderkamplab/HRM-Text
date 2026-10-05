# Frozen production successors and handoff matrix

Production code is now frozen. No more feature expansion is planned. New roots
were prepared, not repinned, and pass verification. Quotas/configs equal v2
exactly:910000 total,70000 for each of13 languages,78 language/family groups.
Both ledgers have zero accepted, zero active, zero jobs and no approval receipt.
Old26B lineage sidecars are preserved; no old acceptances imported.

Operational inventory addition (no frozen31B change): CPU Slovak additive root
`data/dfm13/wave4/slovak-additive-20261003-v1`, preparer2460511, continuation2465638.
Include `data/dfm13/wave4/slovak-additive-handoff.json` in the global handoff;
main parallel completion alone is insufficient. Its versioned jobs feed existing
wave4 audit/repair queues, then separate combined-budget accepted-only release.

Receipt: `data/dfm13/wave4/production31-successors-v3-receipt.json` binds final
production, capacity and endpoint code hashes plus new manifest hashes.

## Exact root matrix

| Phase | Root beneath data/dfm13/ | Count | State |
| --- | --- | ---: | --- |
| Capacity workload | gemma31-capacity-workload-20261003-v4 | 32 | CPU verified; stable authorization pins and separate plateau/drain rates; no live measurements |
| Existing-target review | wave4/gemma31-quality-comparison | 76 | Transition runs this after strict endpoint gate |
| Matched fresh wave4 | wave4/gemma31-fresh-comparison30-v5 | 30 | Independently verified |
| Matched fresh Baltic | baltic/gemma31-fresh-comparison12-v3 | 12 | Independently verified |
| Balanced source | gemma31-balanced-calibration-20261003-v4 | 234 | Fresh successor; all specifications/requests preserved |
| Balanced execution | gemma31-balanced-execution-20261003-v2 | 234 | Verified against final freeze; CPU-ready, not launched |
| Held Fars | wave4/fars-summary-31b-consumer-capacity-v2 | 89296 | Verified successor; measured capacity required above eight/server |
| Held P3 | latvian-p3-content-alignment-20261003-v1/blind-calibrated-v2 | 7680 | Eight-endpoint dispatcher; pairing calibration must pass first |
| Baltic QA diagnostic | baltic/qa31-article-diagnostic20-consumer-v3 | 20 | Full articles; all20 context-fit; semantic assessment pending |
| Baltic QA bulk | baltic/qa31-article-full-consumer-v3 | 118866 | Full articles;118369 context-fit,497 explicit unresolved overflow; new diagnostic approval required |
| Full wave4 production | wave4/synthetic31-full-staged-v3 | 770000 | Verified, unapproved, empty ledger |
| Full Baltic production | baltic/synthetic31-full-staged-v3 | 140000 | Verified, unapproved, empty ledger |

Balanced successor update, later2026-10-03: the prior source-v3/execution-v1
matrix entries are superseded, preserved and not repinned. Source-v4 and
execution-v2 now pass the final frozen implementation check, all234 exact
runtime-transport/context checks, and28focused tests. Recheck receipt:
`docs/reports/dfm13_balanced234_final_matrix_recheck_20261003.json`.
Commands: `docs/reports/dfm13_balanced234_execution_handoff_20261003.md`.
No execution, model call, server action or automatic production approval occurred.

Held-source update, later the same day: old Fars/QA consumer roots and P3
consumer-v1 are preserved but superseded as launch entry points. Use
`dfm12.held31_capacity_consumer` for the Fars/QA capacity successors and
`dfm12.latvian_p3_dispatch` for P3's two-pass calibrated workflow. Exact commands,
measured-capacity reservations and remaining quality gates are documented in
`docs/reports/dfm13_held31_capacity_successors_20261003.md` and
`docs/reports/dfm13_p3_blind_pairing_handoff_20261003.md`. No live capacity or
semantic approval is implied by CPU verification; all source holds remain.

Later article-aware QA update,2026-10-03: the two QA capacity-v2 entries above
are superseded by verified article-consumer-v3 roots, preserved rather than
repinned. Use `dfm12.baltic_qa31_article_consumer` for these QA roots, not the
older capacity wrapper's no-article engine. Fars and all other entries are
unchanged. Full coverage remains118866 including37653 no-hit cases; every
selected full article was measured using actual31B native rendering.497
over-budget rows remain unresolved and nondispatchable, with no truncation.
Both manifests and dependencies verified;46 focused tests pass. Commands,
manifest hashes and detailed coverage:
`docs/reports/dfm13_baltic_qa31_article_successors_20261003.md`.
No GPU launch: wait for source audits to drain and explicit31B handoff. New
article-aware semantic calibration and measured-capacity approval remain separate
requirements; original QA and retrieved articles are not factual gold.

## Pin boundary

### Article-aware QA supersession, later2026-10-03

The two no-article QA capacity-v2 rows above remain preserved historical roots.
Actual article-aware replacements now exist, are sealed, and passed the existing
consumer's full pin verification during the operational documentation review:
`baltic/qa31-article-diagnostic20-consumer-v3` (20/20 dispatchable) and
`baltic/qa31-article-full-consumer-v3` (118866 catalog rows,118369 dispatchable,
497 explicit context holds). They use `dfm12.baltic_qa31_article_consumer` and
require NEW article-aware diagnostic approval; no old policy approval transfers.
See [current commands and Epicurus coordination](dfm13_31b_operational_handoff_20261003.md).
The same review found a missing configurable owned31B production/ramp launcher;
profile validation/client capacity support does not implement server restart.
No frozen code, root pins, launch approvals or live processes were changed.

**Launcher gap subsequently resolved2026-10-03:** the isolated
[wave31 server lifecycle](dfm13_31b_server_lifecycle_handoff_20261003.md) now
provides ramp and validated measured-profile production launches, without editing
any frozen dependency. CPU/mock verification is not a real capacity measurement
or GPU launch. Epicurus's measurement driver consumes its actual command,
ownership, endpoint, log and readiness receipts.

**Current measurement entry point:** `dfm12.wave31_capacity_measure`, using only
`data/dfm13/gemma31-capacity-workload-20261003-v4`. Workload-v1/v2/v3 are preserved
historical artifacts, not active launch inputs. The lifecycle receipt comes
from `dfm12.wave31_server_lifecycle ramp`, not the old comparison server or26B
launcher. Exact CPU-only check (safe without starting any server):

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m dfm12.wave31_capacity_measure verify --root data/dfm13/gemma31-capacity-workload-20261003-v4
```

Manifest SHA256:
`2ac489ee2f440b522756276dc3807807eb4a1eba86c0a8f36c878aa421fc3fe6`.
See the [current operational sequence](dfm13_31b_operational_handoff_20261003.md)
and [measurement contract](dfm13_31b_capacity_driver_interface_20261003.md).
Runtime prerequisites remain source-audit drain/release, explicit ownership and
authorization, actual all-eight31B readiness, exclusive measurement allocation,
and real300-second evidence. No profile or production approval exists merely
because the32 prompts and53 mocked tests pass. V4 supersedes v3 after independent
review: ownership snapshots are evidence, not mutable authorization pins, and
plateau/drain/total completion rates use their respective time windows. Requests
are unchanged; no old manifest was repinned.

### Frozen production implementation

Removed production's import/pin of the fresh-comparison implementation: only its
small endpoint-limit helper had been used. That strict model/context check now
lives with production, while actual endpoint acceptance delegates to the pinned
shared `wave31_endpoint_health.validate` with the expected snapshot. The fresh
experiment's preparation/selection churn no longer invalidates production.

Retained controller/quota/recovery/seed-adaptation/generation/reviewer/schema/
student-rendering dependencies, capacity gates and model/tokenizer assets.
No meaningful guard was dropped. In particular, wrong snapshot, bool/string or
short context, missing second audit, target cuts and missing comparison approval
still fail closed. Broad unrelated pin trimming was deliberately avoided.

Capacity CODE is tested/pinned, not live-certified: no actual31B capacity profile
or throughput measurement was fabricated. Above8 requests/server requires the
existing measured aggregate allocation profile; all production additionally
requires genuine all-group comparison approval. Targets are not reduced for
finite seed shortages, and the LB seed supply issue remains explicit.

Focused production/capacity/health tests:28 passed. Fresh30/12 verify again after
production preparation. No GPU calls, server/client interventions, production
approval, tokenization, sampling or upload occurred.

```bash
python -m dfm12.wave31_production verify --root data/dfm13/wave4/synthetic31-full-staged-v3
python -m dfm12.wave31_production verify --root data/dfm13/baltic/synthetic31-full-staged-v3
```
