# Search Source And Date Diagnosis

## Observed Failure

The tariff case `42c1b060` has original timestamp
`2025-04-15 15:54:40.383000`. Its actual generation request retained the
controller system sentence `Current retrieval date: 2026-10-01T06:35:02.423908+00:00.`
alongside the historical timestamp and instructions to respect it. The answer
explicitly begins `As of the current date in October 2026` and reports later
rates. This is a demonstrable instruction failure, not just a missing citation.

Three interacting causes are visible in saved artifacts:

1. The controller exposes two dates, giving retrieval time a salient current-date
   label. The instructions intended them to have different roles, but the model
   selected the wrong one.
2. Query-ranked evidence selection does not enforce historical applicability.
   The selected CRS passage concerns later tariff developments. An authoritative
   URL does not make those developments applicable at the original question date.
3. The reviewer accepted a source-matching answer despite explicit historical
   substitution. URL traceability and source agreement are necessary checks,
   not sufficient evidence of task fulfillment or truth.

The eight-case independent assessment is
`docs/reports/dfm13_search_remaining48_keeps8_manual_assessment_20261001.json`.
It is purposive domain coverage, not the random stratified packet prepared
separately. Its result is not a population error-rate estimate.

## Minimal Trial

`scripts/dfm13_search_asof_repair3.py` replaces only the recognized
controller-injected retrieval-date sentence in a new conversation branch with
an explicit original-question as-of timestamp. It refuses unknown system
provenance or an ambiguous match. Original user text and other system content
remain unchanged. Actual retrieval timing remains in provenance, not as the
answer date. Original artifacts remain immutable.

Each factual answer must remain within exact retained passages, with the source
scope visible in the learner's tool observation. There is no teacher-only factual
hint, new claim-ID output schema, or blanket acceptance rule. The reviewer checks
claim support, entity/variant, date, and whether partial evidence was presented as
a complete answer. Independent review remains necessary.

The three cases are:

- Tariffs: one complete cached KEIA retrospective passage reports the earlier
  auto-tariff period. It does not establish every tariff on every South Korean
  product as of April 15. The trial must preserve that limitation; the original
  complete-schedule interpretation is infeasible from this evidence.
- Qwen: the cached vendor release includes the exact Instruct benchmark table
  and within-Qwen2 multilingual comparison. This supports attributed benchmark
  statements, not community reception or popularity. That part remains missing.
- Polish domain dispute: the exact cached publication-date line is now retained
  together with the ruling and subsequent settlement passages. The year no longer
  comes solely from a teacher-side caution.

Root: `data/dfm13/search-asof-scoped-repair3-20261001`.
Command: `python -u -m scripts.dfm13_search_asof_repair3 run`.
PID at launch: `2899302`.
Log: `logs/arena_review/20261001/search-asof-scoped-repair3.log`.
One request per endpoint, three cases only, 1536 output tokens, 1600 reserved
inside the 4096-token student window. No new paid retrieval or admission.

The trial finished with two automated keeps (Qwen and Polish dispute) and one
needs-verification (tariffs). Agent inspection still finds a substantive tariff
failure: it now anchors April 2025 but calls the later retrospective report a
date discrepancy/projection and imports later economic effects. A fresh
hash-bound hold is recorded in
`docs/reports/dfm13_search_asof_repair3_hold_20261001.json`; no further retry.
Thus removing the current-date cue alone is not a sufficient fix. Qwen explicitly
states that reception evidence is absent and provides within-family benchmark
values. The Polish answer's year is now in retained evidence. These two new
candidates require independent review; automated keeps are not admission.

Validation: 188 Search tests passed; OKF validation has zero errors/warnings.

## Prior Technical Recovery

The completed 44-case run has 20 keeps, 3 rejects, 13 needs-verification and
8 errors. Seven errors returned null content with `finish_reason=stop` and
`stop_reason=50`, decoded locally as `<|tool_response>`. They used 22-39 output
tokens, not the context or length limit. One saved code answer completed normally,
but review emitted malformed JSON followed by a whitespace tail to 2048 tokens.
The available receipts do not prove whether the nulls originate in decoding,
tool parsing, or model role behavior; no server diagnosis is asserted.

One bounded recovery completed under PID `2896036`: three null-final cases now
have held answers, four remain errors. The code-answer review recovered and
rejected it. Original evidence and answers were not silently changed; no further
automatic retry is queued. Roots:
`data/dfm13/search-null-final-recovery7-20261001` and
`data/dfm13/search-review-decoder-recovery1-20261001`.

## Hold-Aware Inventory

`data/dfm13/search-postbatch-accounting-20261001-v2/inventory.json` includes the
new receipt's exact-hash holds. Across 100 tasks, 74 have saved candidate
versions and 75 owners have successful cached retrieval. Ten distinct tasks have
manually supported, context-fit candidate versions, including two creative tasks
where retrieval is optional. Twenty-one have context-fit, nonheld automated-keep
versions; the union is 23 distinct tasks, not 31. Automated keeps are not verified
usefulness. All admission flags are false.

The existing blind stratified eight-case packet remains at
`data/dfm13/search-postbatch-accounting-20261001/blind8/queue.json`, with exact
candidate and packet hashes. Selection uses seed 2026100148 and two per four
prespecified topic strata, without model verdicts in packets. The subsequent
manual receipt adds holds independently; a packet never overrides those holds.

The paid campaign remains 96/100 reservations. No broader generation is queued.

Post-trial snapshot `data/dfm13/search-postbatch-accounting-20261001-v3/inventory.json`
adds the two pending-review candidate versions and enforces the new tariff hold:
10 manually useful distinct IDs, 23 automated-keep IDs, union 25, zero admitted.
The manual-supported total did not increase merely because two model reviews kept
the new answers.
