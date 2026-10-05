# Full-target31B successor production, prepared NOT authorized

**Superseded capacity recipe later2026-10-03:** the v1roots and four-request/server
bootstrap below are historical, not permanent production ceilings. Current
capacity-capable unapproved roots are `synthetic31-full-staged-v2` for each wave.
See `docs/reports/dfm13_31b_capacity_and_lb_supply_20261003.md` for measured ramp,
profile/aggregate allocation support and5,538proposed extra LB evidence windows.
No target cuts or production launch/approval accompanied this change.

## Objective preserved

Thirteen languages, six families,70,000accepted conversations/language:
**910,000 total**. Isolated prepared successor roots:

* `data/dfm13/wave4/synthetic31-full-staged-v1`:66groups,770,000target.
* `data/dfm13/baltic/synthetic31-full-staged-v1`:12groups,140,000target.

Each language retains grounded20,000; summary10,000; multiturn15,000;
OpenHermes15,000; math/code6,000; tools4,000. Repeat1, student context4096,
six-times candidate budget, full targets and source/reference evidence retained.
No accepted target, source requirement or content validator was weakened.

New `dfm12.wave31_production` privately adapts the existing single-writer quota
ledger, source providers, raw stages, admission gate and native student assembly.
It pins actual31B weights/tokenizer and a generated per-root config. Dynamic
generation request CPU preflight passed all30wave4 plus12Baltic comparison specs.
No requests sent. Current production adapters reject26B and target cuts. Existing
live26B modules/configs/queues remain unchanged. No production process launched.

## Independent re-audit semantics

Every candidate uses the existing strict indexed review, deterministic checks and
student validation. A prospective keep receives a second separate native-language
and source-fidelity audit request containing the full candidate/source/reference,
but NOT the first verdict/reason. Only both valid keeps count toward quotas.
Raw response completeness, request binding, candidate hash and typed scores are
rechecked. A first-stage keep cannot survive a crash as an accepted ledger row
without second-audit evidence. Errors/rejects preserve outcomes and consume their
bounded attempt; no silent regeneration loops or fake approvals.

The second audit uses31B too: independent context/request, NOT independent model,
human or native-speaker certification. Correlated false accepts remain possible.
Independent semantic review of comparison results is a mandatory external launch
gate, and production samples still require independent quality monitoring.

No26B outputs are automatically credited. `preserved26b-lineage.json` points to
unchanged predecessor manifests/seals/holds; prior provenance and quality holds
remain intact. This is a new-model successor, not mutation/resumption of the
26B ledger under a different teacher identity. The new31B ledger itself resumes
with its existing exact-once recovery/cursor/fingerprint rules. Any future salvage
of26B-held candidates needs explicit independent re-audit and a separate reviewed
import path; none is implemented or authorized here. Full objective can instead
be filled entirely with newly generated31B candidates.

## Preparation and launch gates

CPU prepare/verify already completed for both roots. Initial accepted0, imported0;
no `comparison-reviewed-approval.json` exists, and launch fails closed without it.
The future evidence receipt must contain the exact campaign manifest SHA256,
model revision, nonempty independent reviewer identity/description, pinned real
comparison evidence, `independent_semantic_review_complete=true`,
`production_authorized=true`, and all corresponding language/family pairs in
`approved_groups`. The program never generates this authorization receipt.
Do not sign all groups based only on aggregate judge acceptance or exposed cases.
If a language/family fails comparison, its target remains unmet, not cut.

After genuine semantic approval and the separately guarded31B server handoff:

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave31_production verify --root data/dfm13/wave4/synthetic31-full-staged-v1
$PY -m dfm12.wave31_production verify --root data/dfm13/baltic/synthetic31-full-staged-v1
# Launch ONLY with reviewed approval files and exclusively31B endpoints:
setsid $PY -u -m dfm12.wave31_production run --root data/dfm13/wave4/synthetic31-full-staged-v1 --concurrency-per-server 2 > logs/dfm13/wave4-31b-production.log 2>&1 < /dev/null &
setsid $PY -u -m dfm12.wave31_production run --root data/dfm13/baltic/synthetic31-full-staged-v1 --concurrency-per-server 2 > logs/dfm13/baltic-31b-production.log 2>&1 < /dev/null &
```

Together4requests/server, below the8/server cap. Do not overlap these with an
8/server comparison client. Existing KV<=.90 admission/circuits,600s timeout,
graceful signal drain and durable outcomes retained. No server ownership, upload,
training, final sampling or automatic production permission in this module.

## Supply and feasibility, not an unconditional yield promise

Pinned native seed counts: sq50,686; be128,824; bs68,950; bg208,586;
hr135,351; hu358,519; lb34,013; sr259,506; sk117,860; sl122,180;
fa381,472; lt181,402; lv134,597. Each has more than the largest single-family
20Ktarget, but acceptance yield is not established. Existing explicit
`source_reuse_by_family=true` permits reuse across DIFFERENT task families;
the same source is not implicitly repeated within a family to fill quotas.
OpenHermes pool100K; math/tool cases do not require native article pools.

LB grounded20K requires at least58.80% accepted yield from34,013unique sources;
with lower yield, full coverage needs additional independently eligible unique
seeds. Wave4 seed receipt already says `sufficient_for_full_targets=false`.
The6x cap is an upper bound, not a promise that every group has that many seeds.
Finite source exhaustion exits explicitly blocked, preserves all targets and
shortfalls, and does not wait forever or inflate repeats. Extending a frozen
seed pool requires separately reviewed/pinned provenance and a receipt-led
cursor/blocked-state migration; do not edit SQLite counters ad hoc.

Remaining prerequisites: current26B audit/repair/CPU drain; independently reviewed
31B comparison evidence for both waves; actual live31B decoding/second-audit
validation; enough source/yield per group; semantic production monitoring. These
are visible gates, not a plan to replace910K with42comparison examples.

Tests cover exact78groups/910K quotas, target-cut rejection, model isolation,
new ledgers without imports, bounded exhaustion, missing second-audit fail-closed
quota credit and missing approval. No GPU work performed.
