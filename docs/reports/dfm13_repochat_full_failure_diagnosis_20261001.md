# RepoChat full-pass failure diagnosis, 2026-10-01

CPU-only inspection of sealed ledgers and saved OpenAI responses. No new inference,
retry, server change or training action. Both passes completed. Admission remains zero.

## Exact terminal counts

| Outcome | Original pass | Bounded follow-up |
|---|---:|---:|
| Reviewed | 2051 | 30 |
| Empty-stop generation | 428 | 395 |
| Audit output length | 288 | 3 |
| Generation output length | 8 | 0 |
| Source skip | 546 | 0 |
| Total | 3321 | 428 |

Original reviewed: 1134 automated passes, six automated passes held, 911 quality
rejects. Follow-up: 25 automated passes and five quality rejects. These are model
verdicts, not independently established correctness or training admission.
Combined unique outcomes: 2081 reviewed, 694 unresolved technical failures,
546 source skips. Follow-up rows overlap the original pass, not new tasks.

## Empty-stop root cause

Of the original 428, 373 ended at `generate-16`, where the client changes
`tool_choice` from `auto` to `none`; all 373 stopped on token 50. The other 55
ended earlier. Overall stop reasons: token 50 in 423, token 106 in four, null in
one. The installed model tokenizer maps 50 to `<|tool_response>` and 106 to
`<turn|>`. All 428 have no answer content or structured tool calls; 48 retain
reasoning and 380 do not. Thus `finish_reason=stop` does not imply a usable answer.

This strongly implicates the forced-final/native tool parsing boundary: the model
still emits a tool handoff instead of a final answer. It is not evidence of a
network outage. The saved responses have `token_ids=null`, so we cannot prove the
complete pre-parser text or identify an exact parser defect from these receipts.
Do not present that inference as a fully reproduced parser bug.

Example `0217ac7d7d6cf4d3bfe726269a465c2720a68fc3933e52037384d716db2e47c5`:
`generate-16.json` has 5646 prompt tokens, 32 completion tokens, stop reason 50,
no content/reasoning/tool calls, and request `tool_choice=none`. Its 16 prior
calls contain 12 distinct calls and repeated `tgl_do_send_message` searches.
The follow-up reproduced the same failure. This is far below the 32768 context
limit, not context exhaustion.

Among all 428 histories, using exact serialized function-name/arguments equality:
198 have repeated identical calls; 142 have tool-result errors; 55 have both.
Mutually exclusive: 143 repetition only, 87 errors only, 55 both, 143 neither.
These histories explain pressure on the 16-round limit, not every early empty stop.
Error occurrences (not distinct trajectories): 405 complete-line response-limit
errors, 80 requests for 50 lines despite a 30-line maximum, 30 requests for 100
lines, and 37 absent/unsafe snapshot paths. Other schema errors are rare.

Example `06ceec4492796b098853b6e0a011b6e4d5c64f42c93e98578fc0c1da827a70b7`
has an initial 50-line schema error followed by sequential reads of
`lightautoml/tasks/base.py`; it reaches the forced-final boundary despite 16
distinct calls. More rounds alone would not repair all repeated-call cases.

The bounded retry retained successful history but repeated the failed request
without repairing this boundary. It recovered 33 generated answers; 30 reached
a verdict and three exhausted audit output. Of 395 remaining empty stops, 372
are at turn 16; 394 stop on token 50, one on 106; 19 have reasoning only.
Repeated identical requests are therefore not a useful next intervention.

## Audit and generation length failures

All 288 original audit failures used exactly 8192 completion tokens. 280 have
reasoning but no content; eight have reasoning plus partial content. All three
follow-up audit failures likewise used 8192 tokens and have reasoning only.
The validator stops at `finish_reason=length` before JSON parsing. These are not
JSON-schema rejection counts, nor valid negative quality verdicts.

Example `078b4e884a602f061b54db0311edd2d25685b742ac6a9294caa6d8d2b040d020`
uses 3130 prompt tokens and 8192 completion tokens. Its audit repeatedly analyzes
a 64-character board encoding and identifies the answer's `pos < 63` boundary
problem, but never produces final JSON. Reasoning exhaustion, not total context
exhaustion, prevents a verdict.

All eight generation-length failures reached exactly 4096 completion tokens and
contain partial answer text. Example `9771ee5a651a70913b81e11d962b766e65616ac60ae3806edad5193cf0ca2555`
degenerates into many numbered `use_p2p_onion_announce_v...` configuration fields.
Increasing the output allowance blindly would prolong that repetition rather than
establish correctness. No terminal context-limit or JSON-parse failures occurred.

## Source skips are a separate bucket

546 task-level skips: 226 HTTP 401, 175 HTTP 403 rate-limit responses, 121 download
size limits, 11 unresolved explicit refs, seven missing required issue/pull
context, three refused redirects, one HTTP 410, one HTTP 404, and one remote
disconnect. A source receipt may serve multiple tasks; these are not unique-repo
counts. Rate limiting and disconnects are infrastructure failures, not proof a
repository is unavailable. HTTP 401 alone does not establish permanent privacy.

## Recommended fixes, not executed

1. Reproduce the finalization boundary on a small saved-history diagnostic with
   raw token/text capture. Test an explicit final-answer instruction and a
   tool-free finalization request while preserving evidence and provenance.
   Do not silently promote reasoning or hidden tool text to a final answer.
2. Detect exact repeated calls; return useful progress/budget feedback. Improve
   complete-line reader errors with an actionable smaller line count, without
   truncating evidence or allowing unsafe paths. Do not simply increase rounds.
3. Preserve the 291 generated candidates awaiting audits. Test a bounded review
   strategy that reserves room for final typed JSON, checking negative and
   positive controls before adopting it. Do not count truncated reasoning as a
   review or globally disable thinking without quality comparison.
4. Treat the eight long generations individually, separating legitimate long
   implementations from degenerate repetition. No automatic acceptance.
5. For rate-limited source preparation, use CPU cooldown/backoff and distinct-repo
   deduplication in a separate recovery, not permanent source-unavailable labels.
   Preserve explicit ref, archive-size and path-safety constraints.

## Authorities

- `data/dfm13/repochat-full-20261001/{jobs.sqlite,manifest.json,completion.json}`
- `data/dfm13/repochat-full-20261001-technical-retry-v1/{jobs.sqlite,selection.json,completion.json}`
- Each root's `trajectories/<id>/generate-NN{,-request}.json` and `audit.json`.
- Cached Gemma snapshot `4d7ae4984b7db7de8f8457170b3f1a419ee76d52/tokenizer.json`.

All original and retry artifacts remain unchanged. Parent owns server teardown
and XL training resumption; no further RepoChat GPU jobs are scheduled here.
