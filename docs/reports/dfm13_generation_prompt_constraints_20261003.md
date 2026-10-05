# Generation-side constraint calibration handoff

## Model-choice supersession, later 2026-10-03

**Bounded test launch handoff, subsequent update:** Epicurus owns26B switchback.
The thin `scripts.run_generation_constraint_test` wrapper now consumes the sealed
26B artifact using the existing wave-four controller/pilot/stage pipeline. Its
default command is CPU-only and passed all12 frozen request/schema round trips.
No GPU launch was performed. After the switchback owner releases the endpoints:

```bash
/home/ucloud/miniforge3/envs/hrm/bin/python -m scripts.run_generation_constraint_test \
  --execute --arm constrained \
  --output data/dfm13/generation-constraints-26b-test12-20261003-v1
```

This is exactly12 generation cases (plus standard reviews), one request in flight,
distributed across the existing eight endpoints. All-eight26B model/context and
snapshot checks precede calls; no servers are started. Source holds remain copied
to output. A second matched baseline run is optional with `--arm baseline` and a
different fresh output; historical cases are already pinned. Outputs require
independent comparison, not automatic approval. No schema or repair-pilot changes.
Bulk can consume `apply_request` after the owner assesses this bounded test;
there is no automatic bulk launch in this wrapper. The module below still has
no run CLI; this wrapper is the only added execution entry point.

User questions31B; bulk model choice is pending, with **26B the default**.
The older31B execution instructions below are historical, not a launch request.
No GPU launch is authorized by this CPU preparation; do not dispatch either
variant during capacity work or infer31B selection from the old artifact name.

The reusable API is now model-neutral:

```python
from dfm12.generation_constraints import apply_request
payload = apply_request(payload)  # copy; only system text changes
```

It preserves model ID, source/user turns, decoding settings and schema, and
rejects accidental duplicate application. It can be applied before compact
transport in either chosen generator without changing Harvey's schema work or
Poincare's source-repair pilot. No shared production module was modified.

Actual new CPU artifact:
`data/dfm13/generation-constraints-26b-cpu-20261003-v1`.
Same12 exposed specifications /24 paired requests, now explicitly targeting
`google/gemma-4-26B-A4B-it`. Full26B-tokenizer preflight used local revision
`4d7ae4984b7db7de8f8457170b3f1a419ee76d52`, with asset hashes pinned. Maxima:
baseline1,636 prompt/5,732 total; constrained1,887 prompt/5,983 total, limit32,768.
Equal counts to31B do not imply identical models or equivalent quality.
The manifest records `execution_ready=false`, no run command, pending bulk
choice, no admission, and the two unchanged source holds.

Manifest SHA256:
`bc72a4cfa20898b42047019a471bf23562892d7a8b0d778faa33ff0b710ac3b9`.
Eleven combined tests pass, including model-ID/schema preservation for26B,31B
and an arbitrary model name. The original31B artifact and seal remain unchanged.
Student4096 validation still awaits actual generated messages, and no improvement
claim follows from prompt-token preflight.

```bash
python -m dfm12.generation_constraints verify
# CPU-only re-preparation, fresh destination; --model/--tokenizer-dir explicit:
python -m dfm12.generation_constraints prepare --root NEW_ROOT
```

This module deliberately has only prepare/verify CLI commands. Parent owns
model choice and subsequent isolated runner integration; no server allocation,
endpoint calls, automatic fallback or launch was added.

2026-10-03. CPU-only preparation after the independent
[grounded/summary/multiturn50](dfm13_wave4_balanced31b_grounded_summary_multiturn50_20261003.md)
and [math/tool/OpenHermes83](dfm13-balanced234-math-tool-openhermes-20261003/report.md)
reports. No GPU requests, process/server changes, source repairs or approvals.

## Minimal generation change

The old generation system already says not to invent policies. Repeating that
generic warning is insufficient: tighten the specific evidence/meaning boundary.
The new isolated module `dfm12/wave31_generation_constraints.py` appends one
system suffix, leaving the complete original request, schema, source/scenario,
decoding parameters and reviewers otherwise unchanged:

1. Do not impersonate an actual institution or invent its fees, eligibility,
   loan periods, document requirements, transport rules or app prices. Ask for
   the missing institution/location or explain how to check. Hypothetical rules
   need an explicitly fictional user scenario established before using them,
   not a retroactive disclaimer.
2. Without a suitable tool and successful action receipt, do not claim or promise
   external document updates, email sending, booking or redirection. Offer a
   draft/instructions instead. An available locker is a possible destination,
   not the parcel's current location; permission to redirect is not execution.
3. Translate explanatory prose, not code/technical literals. Preserve source
   code blocks, inline executable identifiers, CSV headers/column order, literal
   data/axis labels, indices, filenames and requested output strings. Do not
   invent a reconciliation of source prose that contradicts its code.

This is a prepared prompt variant, **not measured evidence of improvement** and
not a change to production generation. Inherited erroneous explanations require
source repair or exclusion; prompting cannot make conflicting source claims true.

## Prepared artifact

`data/dfm13/gemma31-generation-constraints-20261003-v1`

- 12 exposed diagnostic specifications, two matched arms (`baseline`,
  `constrained`): **24 generation requests**, plus the existing runner's reviews.
- Nine languages: HR, FA, BS, LB, SQ, SL, SR, BG, SK.
- Four multiturn, four OpenHermes, three tool dialogues, one grounded extraction.
- Eight targeted generation failures, two source-fault diagnostics, two passing
  regression controls. These are not fresh heldout cases or a population sample.
- Actual31B tokenizer full-context CPU preflight: baseline maximum prompt1,636 /
  total5,732; constrained maximum prompt1,887 / total5,983; limit32,768. No cuts.
- The native student4096 check remains mandatory on **actual generated** full
  messages/tools through the reused runner; it cannot be certified before generation.
- Six focused tests passed. Both arms'12 requests separately round-trip exactly
  through the existing balanced execution adapter (transport and full schema).
- Manifest SHA256:
  `ff19441de2b616ff432b8064bd13b1925ebfb06bf8a2233575bb19a0b93f254b`.

Each arm has specifications, stored requests, actual-tokenizer preparation
budgets, paired historical candidate hashes, source holds, manifest and seal.
The existing full request pins remain checked. Baseline regenerates the original
prompt; constrained differs only in the appended system text. Single draws at
temperature0.3 are diagnostic comparisons, not a statistically isolated effect.
Old generated answers/review decisions are never supplied as prompt examples.

## Cases

| Candidate prefix | Purpose |
|---|---|
| 01cb9acbac42 | HR unidentified library: fabricated policy |
| fdfa97e5b409 | FA library: invented eligibility/document requirements |
| cc4c40761618 | BS transport: unsupported route/ticket/app rules |
| aeb5d25e74c0 | LB document/email work promised without tools |
| 06a40f07 | FA parcel: destination mistaken for current location |
| d284d7f2 | SQ parcel: same semantic distinction |
| 9fe268aa | SL translation: preserve code names/example strings |
| dbf543d7 | SR translation: preserve literal Hello, World! |
| 58f3d7ba | FA CSV: literal-retention diagnostic, inherited explanation hold |
| 758a1ff5 | BG axes: literal-retention diagnostic, inherited label interpretation hold |
| f18b605c | SK parcel passing control |
| bef5c80c0044 | BG quoted Latin passing control |

The two source-fault diagnostics remain held in `source-holds.json` regardless
of any future automated keep. They evaluate preservation only, not the claim
that unchanged source explanations are correct. No generic automated outcome
clears these holds, and neither arm authorizes admission/publication.

## Main / Harvey / Poincare coordination

- **Harvey:** no shared schema files changed. This contrast deliberately freezes
  the historical schema. If a schema successor is required, regenerate both
  arms against the same verified successor; never silently patch one arm or
  repin this seal. `prepare(root, source=...)` accepts an alternate verified
  source root with the same selected case coverage. Dependency drift fails closed.
- **Poincare:** no repair pilot or source targets changed. CSV/axis source errors
  stay in the repair owner's scope. Existing held candidates are not repaired
  or readmitted here. The paired source-fault cases must not contribute to a
  clean-generation metric merely because a reviewer keeps them.
- **Main:** hold dispatch while capacity measurement owns endpoints. The new
  runner wrapper reuses `wave4_gemma31_fresh.run` with the existing balanced
  adapter, preserving raw capture, full schema validation, actual student limits,
  second review/recovery checks, strict31B endpoint identity and independent
  review queue. It does not launch or stop servers. Concurrency is1/server on
  the existing eight8800..8807 endpoints, not an additional model allocation.

CPU commands (prepare refuses an existing root):

```bash
python -m dfm12.wave31_generation_constraints prepare --root NEW_ROOT
python -m dfm12.wave31_generation_constraints verify
python -m pytest -q tests/test_wave31_generation_constraints.py
```

Only after the capacity owner explicitly releases the endpoints, the owner may
run these arms sequentially; **neither command was executed in this task**:

```bash
python -m dfm12.wave31_generation_constraints run --arm baseline --capacity-released
python -m dfm12.wave31_generation_constraints run --arm constrained --capacity-released
```

`--capacity-released` is an explicit operator acknowledgment, not a sensor or a
fabricated release receipt. Verify current endpoint ownership before dispatch.
Assess complete new conversations against original evidence/literals, with arm
labels and automated decisions hidden where practical; count useful nonanswers
separately from blanket refusals. Require natural follow-ups rather than a policy
disclaimer repeated each turn. No throughput/quality/acceptance claim until run
and independent assessment. No reviewer prompt changes or bulk approval here.
