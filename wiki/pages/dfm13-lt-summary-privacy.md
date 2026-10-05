---
type: Runbook
title: Lithuanian Summary Privacy Screening
description: Separate content-bound privacy queue for final Baltic Lithuanian summaries.
status: draft
confidence: high
last_updated: 2026-10-03
---
# Lithuanian Summary Privacy Screening

The scoped module `dfm12.baltic_lt_summary_privacy` processes only
`data/dfm13/baltic`, component `baltic_lt_summary`. The sealed quality input has
2,012 rows after 228 overlength exclusions. Sources are pinned train CSVs
`it`, `medicina`, `teise`, and `ziniasklaida`; source bytes and revision metadata
are checked, not inferred from filenames alone.

Run preparation with the hrm environment:

```bash
python -m dfm12.baltic_lt_summary_privacy
```

Preparation first calls the existing `wave_repair.process` quality workflow.
The existing repair monitor owns pending GPU repairs. Only accepted or
independently re-audited accepted repairs enter this separate privacy queue:
`data/dfm13/baltic/privacy/baltic_lt_summary-v1/jobs.sqlite`.
Every request includes the FULL final record: source/user and all assistant
messages. No truncation, redaction, or assistant-only review is performed.
Partial conversations and changed nonassistant messages fail closed.

Job identity binds canonical full-record hash, source provenance, sealed input
hash, and privacy contract version. A repaired answer or changed source cannot
reuse the old job. Old jobs remain historical evidence; the refreshed report
only considers jobs matching the current final record. Re-run preparation after
quality/repair or privacy jobs finish and before any publication review.

The response schema retains the existing audit fields for `european_stage` and
adds `direct_sensitive_pii`, `credentials`, and `uncertain`. The final report
validates these extra fields independently: missing fields or any true flag
hold the row, even if the model says keep. Public names and ordinary public
articles are not blanket rejections. Reasons should name category/message index,
not repeat private values. Queue payloads contain potentially private source
text and must remain local; do not upload raw screening artifacts.

Human reviewers may write `manual-holds.json` in the privacy directory as an
object mapping ORIGINAL candidate IDs to nonempty reasons, then rerun preparation.
These holds survive changed repairs and override model passes. Unknown IDs are
an error. The report covers every sealed row, including unresolved quality rows.
It never authorizes publication and never claims PII-free certification.

## Proposed Local Launch

Initial preparation on 2026-10-03: 1,939 accepted originals queued for privacy;
73 quality repairs pending and excluded from privacy admission until final
acceptance. All 2,012 inputs are represented in `report.json`. Thirteen focused
CPU tests passed. No privacy clients launched.

NOT launched by preparation. Owner must inspect implementation/tests first.
Use only the existing local eight servers, 32 requests per endpoint maximum:

```bash
python -m dfm12.european_stage \
  --database data/dfm13/baltic/privacy/baltic_lt_summary-v1/jobs.sqlite \
  --stage audit --concurrency 32 --max-concurrency 32 \
  --output data/dfm13/baltic/privacy/baltic_lt_summary-v1/client \
  --endpoint http://127.0.0.1:8800/v1 --endpoint http://127.0.0.1:8801/v1 \
  --endpoint http://127.0.0.1:8802/v1 --endpoint http://127.0.0.1:8803/v1 \
  --endpoint http://127.0.0.1:8804/v1 --endpoint http://127.0.0.1:8805/v1 \
  --endpoint http://127.0.0.1:8806/v1 --endpoint http://127.0.0.1:8807/v1
```

Tests: `python -m pytest -q tests/test_baltic_lt_summary_privacy.py`.
Coverage includes stale candidate/source binding, changed repairs, full-message
requirements, missing privacy flags, explicit uncertainty, manual overrides,
queue refresh and unresolved source coverage. No shared modules or live workers
are edited. Related: [Baltic source preparation](dfm13-baltic-language-sources.md).

## Executed Review, 2026-10-03

The owner reviewed the code, independently ran the 13 tests and launched the
initial 32/server privacy client on the eight existing local endpoints. All
1,939 initial jobs completed. Initial model decisions: 1,734 pass and 205 hold;
205 flagged sensitive PII and four also flagged uncertainty, zero credentials.
These are model flags, NOT confirmed exposure counts. Initial domains were IT
629/0 pass/hold, media 507/0, legal 312/8, and medical 286/197.

An independent agent read six complete records: the first job ID in each
nonempty domain/decision stratum. Public technology, writer-interview and
municipal-planning passes were reasonable. A medical pass was manually held
because its detailed individual clinical content left identifiability uncertain;
no direct patient identity was established. The model inconsistently held a
similar redacted clinical report. A legal hold's rationale misattributed a
corporate bank account to private-person PII; the hold remains unresolved due
to dated private legal/financial context, not because public corporate details
are automatically forbidden. This is not a blanket medical or named-person ban.

Local evidence: `data/dfm13/baltic/privacy/baltic_lt_summary-v1/independent-review.md`
and `manual-holds.json`. Do not publish these raw queue artifacts or model reasons,
which can themselves repeat sensitive values despite the prompt instruction.

Seven quality-accepted repairs subsequently completed privacy screening in two
sequential local client runs (`client-repair-tail-1` and `client-repair-tail-2`),
both with zero request errors. No initial-client overlap occurred. Three pending
quality re-audits were processed with explicit job-ID restrictions using the
existing audit interface; the existing repair-generation worker was untouched.

Owner clarification supersedes any implication of an indefinite blanket review
gate: publish only the CURRENT quality-and-privacy accepted subset with source
attribution/license notices and screening limitations. Holds and unresolved
repairs are excluded; they do not indefinitely block accepted records. This
module does not itself upload or authorize publication. `report.json` remains
the current count/binding source and must be refreshed before selection.

Final completion: all 2,012 inputs resolved, 1,939 quality-accepted originals,
seven accepted repairs, 66 rejected repairs. All 1,946 privacy jobs are done,
none pending or failed. After the single manual override: **1,740 accepted**,
205 model holds, one manual hold. Accepted domains: IT 633, medicine 285,
legal 314, media 508. No privacy clients remain active. Publication has not been
performed here; accepted-only publication may proceed with the required notices,
without waiting for the excluded rows. No PII-free certification is claimed.

Final local receipt: `privacy/baltic_lt_summary-v1/completion-review.json` under
the Baltic root. Final report SHA256:
`7d33c1ddafa70e2a4aafb2d0c2508e4df9e6689a0a711a3777c8e7ad41806f7e`.
The privacy model's medical-record inconsistency is documented as a limitation;
the six-row independent review is not full manual certification of 1,740 rows.

## Accepted-Only Publication, 2026-10-03

Supersedes the preceding not-yet-published state: the owner explicitly authorized
export/upload/registry/tokenization of the 1,740 current passes. The scoped
publisher is `dfm12.lt_summary_publish`; it does not remove or rewrite the
original source, quality ledger, privacy queue, holds, or historical preparation.
It rechecks complete 2,012-row coverage, quality acceptance, upstream CSV row
equality, exact full-final-record privacy job identity, completed flags, and
manual overrides. Changed repairs, partial conversations, changed sources,
pending jobs and all holds fail admission. The exported receipt binds both the
screened candidate hash and the published record/messages hashes; held text and
privacy model reasons are not uploaded. Model screening remains fallible.

Frozen publication: `exports_dfm13/lt-summary-publication-v2` (v1 is an unpublished
local build retained for provenance). Dataset:
`schneiderkamplab/dfm13-wave3-baltic-lt-summary-newgenltu`, verified commit
`ea1b1efec206a4e1bac8caf7be542751182e2c51`.
All nine uploaded attachments, including manifest, were downloaded at that
commit and SHA256-verified before registry integration. Attachments carry the
full unchanged license and source card, attribution, dated modification notices,
mandatory downstream/model conditions and accepted-only privacy receipt.
No PII-free certification or claim that model privacy safeguards were certified.

```bash
python -m dfm12.lt_summary_publish --build --output exports_dfm13/lt-summary-publication-v2
python -m dfm12.lt_summary_publish --upload --output exports_dfm13/lt-summary-publication-v2
python -m pytest -q tests/test_lt_summary_publish.py tests/test_baltic_lt_summary_privacy.py tests/test_assemble_dfm13_additions.py tests/test_tokenize_wave_releases.py
```

Build requires a fresh directory; do not rerun build over this frozen package.
68 tests passed. The registry uses `accepted_uploaded`, an actual Hub revision,
repeat 1 and explicit final-assistant `target_message_index`. Existing bounded
CPU tokenizer watcher owns tokenization; no duplicate tokenizer was launched.
The narrowly named summary assembler adapter verifies every mandatory attachment
and exact accepted privacy coverage and carries license/model conditions forward.
Preflight rendered tokens total 3,081,653; materialized token verification follows
the existing watcher's completion, rather than assuming preflight equals storage.

Completed at approximately 15:12 UTC: the existing watcher materialized **1,740
rows / 3,081,653 tokens**, one shard, zero skipped rows. Registry tokenization
is complete. Storage root:
`data/dfm13/tokenized_wave_releases/dfm13_wave3_baltic_lt_summary_newgenltu/tokens`.
The assembler's `verify_entry` passed full array structural/hash checks and its
deterministic native parity sample; receipt:
`exports_dfm13/lt-summary-publication-v2/assembly-verification.json`.
Separate `native-preflight.json` verifies native rerender lengths for ALL 1,740
final targets (maximum 4,092 tokens), not just the assembler sample.
Publication manifest SHA256:
`247d6094a52e718b36e2f731426e23270f298d60fac491dc282c13c31795f748`.
Final expanded regression suite: **84 passed**, including BLKT and Latvian P3
publisher tests and changed-message/missing-privacy-receipt tests. OKF validation
passed without warnings. No full assembly/sampling, training or GPU actions.
