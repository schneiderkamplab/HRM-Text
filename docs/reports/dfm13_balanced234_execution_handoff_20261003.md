# Balanced 234 Execution Handoff

## Current Roots

| Purpose | Root under data/dfm13 | Cases/target | Approval |
| --- | --- | ---: | --- |
| Exposed wave4 comparisons | wave4/gemma31-fresh-comparison30-v5 | 30 | Diagnostic only |
| Exposed Baltic comparisons | baltic/gemma31-fresh-comparison12-v3 | 12 | Diagnostic only |
| Fresh balanced specifications | gemma31-balanced-calibration-20261003-v4 | 234 | No production approval |
| Fresh balanced execution | gemma31-balanced-execution-20261003-v2 | 234 | No production approval |
| Wave4 production, Tesla-owned | wave4/synthetic31-full-staged-v3 | 770,000 | Unapproved |
| Baltic production, Tesla-owned | baltic/synthetic31-full-staged-v3 | 140,000 | Unapproved |

Use only after the final CPU receipt
`docs/reports/dfm13_balanced234_execution_preflight_20261003.json` names execution
v2 and verifies all 234 runtime payloads. No GPU run was launched by this work.
The transition owner controls resource release and server startup. Run these
bounded calibration jobs sequentially with other consumers, not concurrently
with separate per-server allocations.

```bash
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
$PY -m dfm12.wave31_balanced_run verify \
  --root data/dfm13/gemma31-balanced-execution-20261003-v2
$PY -m dfm12.wave31_balanced_run run \
  --root data/dfm13/gemma31-balanced-execution-20261003-v2 \
  --concurrency-per-server 2
```

`--wave wave4` or `--wave baltic` restricts execution; default `all` runs them
sequentially. Resume uses the same command and existing stage/outcome evidence.
No blanket retry occurs: the retained fresh lifecycle marks ambiguous orphan
stages interrupted instead of silently replaying them. Previously kept outcomes
must pass frozen generation-request binding, strict raw/schema/assembly review
revalidation, and the second production audit's candidate/request/raw checks.

The adapter reuses the fresh runtime through private function globals, not a
shared-module monkeypatch. It uses the production controller's generation,
student assembly and strict first/second review. Requests are restored from the
sealed envelopes; actual post-pilot compact transport equality is checked on
CPU. `/models` must advertise exclusively the verified Gemma4-31B model, its
absolute snapshot path and at least32768 context, using Tesla's shared endpoint
validator. Every call retains full context checking; no truncation or template
regex correction is introduced.

Raw/stage/request/candidate/outcome files and independent-review queues remain
under each execution wave directory. `execution-status.json` reports terminal
or drained state with all admission/publication/production flags false. Same31B
second review is not independent semantic certification. This runner cannot
create a bulk approval or export/upload data.

## Preserved History

Balanced input v1 is superseded for reused fixed code references. Input v2 and
v3 and execution v1 are preserved, not repinned: shared endpoint/production
implementation changes invalidated their execution pins. V4 retains the same
234 specifications and generation requests as v2/v3; only a new root records
the final dependency versions. The 42 exposed comparisons remain separate.
Freeze evidence: `data/dfm13/wave4/transition-frozen-v2.json`.

28 focused tests cover request restoration without mutation, spec drift,
bounded concurrency, strict resume/second-audit refusal, sequential/drained
lifecycle, endpoint snapshot checks, fresh coverage and existing production
contracts. Final actual-tokenizer parity results belong to the CPU receipt
above, not a GPU-result claim.
