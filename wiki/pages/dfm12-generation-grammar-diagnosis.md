---
type: Diagnostic Report
title: DFM12 Generation Grammar Failure
description: Live streaming comparisons and CPU mask timing isolate malformed content and severe custom-grammar decoding overhead.
status: draft
last_updated: 2026-09-27
confidence: high
---
# Generation Grammar Diagnosis

This supersedes shared-server contention as the sole proposed explanation for
the stalled [v6 calibration](dfm12-multilingual-calibration-v6.md). Contention
exists, but a reproducible custom-grammar problem is now demonstrated.

## Controlled Probes

`scripts/debug_multilingual_generation.py` borrows existing ports8600--8607.
It saves exact requests, streamed chunks, first-token times, usage, finish
reasons and final content. No new servers, GPU allocations, W&B logging or
training changes. Sampling is temperature0.65, seed42, thinking disabled,
512 output tokens for every comparison, versus4096 in the original calibration.
The same prompt is compared with no constraint, ordinary JSON schema (without
string-length bounds), and the existing custom EBNF grammar. These are diagnostic
outputs, not training candidates or accepted calibration results.

Artifacts are `data/dfm12/generation-stream-debug-20260927-{v1,v2,v3,tool,same-server,cpu}`.

| Probe | Ordinary JSON schema | Existing custom grammar |
|---|---|---|
| Simple Dutch question/answer | Coherent text, 54 tokens, 3.95s | Punctuation-only fields, 13 tokens, 1.54s |
| Actual Dutch grounded prompt | Coherent text, 239 tokens, 16.87s | Both fields just a colon, 11 tokens, 0.93s |
| Dutch tool dialogue | Sensible question and grounded final, 65 tokens, 5.68s | User just a colon; final starts with stray colon, 54 tokens, 4.79s |

First content arrived in roughly0.17--0.58s. No-constraint responses were
linguistically useful but violated the exact contract through Markdown fences,
additional fields or different field names. Structural JSON schema remains
necessary; simply dropping constraints is not a reliable fix.

Repeated probes on different ports reproduced the custom-grammar failure.
Removing repetition bounds did not reliably fix punctuation-only fields.
Allowing normal JSON whitespace in the custom grammar fixed the simple response
content, but its59tokens took80.28s. Thus content degeneration and mask overhead
must be treated separately. The exact model/tokenization mechanism for compact
JSON degeneration is not fully established; valid strings are accepted by the
CPU matcher, so claiming that letters are literally forbidden would be wrong.

## CPU Bottleneck

Using the actual cached teacher tokenizer and installed audit-environment
xgrammar, the same valid25-token JSON answer was replayed token by token:

| Operation | Ordinary JSON schema | Custom bounded grammar |
|---|---:|---:|
| Compile | 0.0313s | 0.00737s |
| Total next-token mask construction | 0.000397s | 10.576s |
| Slowest token mask | 0.000118s | 0.890s |

The custom mask cost grows within each string, resetting at the next field.
This is decoding work, not a slow initial grammar compilation. CPU acceptance
tests alone did not test this performance path or generated linguistic quality.

Concurrent same-server probes (schema, compact grammar, whitespace grammar)
all took about164s; the ordinary-schema response was identical to the correct
whitespace-grammar response. This is consistent with expensive mask work delaying
the shared decoding batch. Do not interpret concurrent same-server wall times
as independent throughput measurements.

The final long whitespace-grammar diagnostic was explicitly cancelled after
capturing partial streaming progress, to avoid burdening other users. Its
`stopped.json` records the exact owned client PID; no vLLM or training process
was signalled. Its partial output is not a completed result.

## Recommended Recovery

**Implemented, 2026-09-27:** user authorized the native-schema fix and a new
calibration at32concurrent requests per server. The calibration runner now
routes non-tool generation, tools and indexed reviews through native JSON
schema. Original bounded schemas still validate decoded responses on CPU;
raw decoding and all content/rendering/semantic checks remain. The underlying
legacy generator is unchanged for other callers. All190adapter/integration
tests pass, and all354prepared requests were verified to contain native JSON
schema, not custom grammar. New run root:
`data/dfm12/multilingual-calibration-native-schema-v2-20260927`, log`client.log`.
The first native-schema preparation was superseded and its client stopped:
the final request audit caught242review controls still using their adapter's
explicit grammar. The v2 runner overrides this route too, including reviews
of generated candidates; a dedicated regression test covers it.
Old calibration artifacts remain untouched. This fresh run repeats all242
controls and112generation cases for a consistent transport comparison.

The native-schema rerun completed all354cases with no transport/timeouts.
Controls:223valid,19invalid;196semantic agreements,9false accepts and18positive
rejections among valid reviews. Generation cases:96assembled,75with valid final
reviews,51semantic keeps;37cases ended invalid across generation/review stages.
Across all450request stages there were394complete and56invalid;49invalid stages
hit an output-token limit (46at4096, three tool generations at2048). Remaining failures:four invalid text controls,
two overlong fields andone unterminated JSON string. Thus native schema resolves
the observed infrastructure stall, not reviewer calibration or output-length
quality. All results remain diagnostic: zero rows/tokens admitted, no automatic
35K successor. Do not call75structurally valid final reviews75accepted examples.

Further inspection of all49length stops found45with more than500trailing
whitespace characters (all40review failures andfivegeneration failures).
The other four are generation cases, with repetitive prose observed in sampled
tails. Raising the token budget would mostly prolong degeneration, not complete
useful long answers. Next test should constrain structural whitespace without
restoring the problematic compact custom grammar, detect streamed repetition,
and retry affected stages with preserved evidence. Any backend whitespace option
must be verified on this installed vLLM rather than assumed effective.

### Penalty and Streaming Retry

User authorized repetition penalties and retry on2026-09-27. Generation now
uses repetition_penalty1.05; reviews use frequency_penalty0.1, avoiding a
prompt-token repetition penalty on verbatim evidence. Native JSON schema and
all CPU/semantic validation remain. Limits remain2048/4096, not increased.

`dfm12/calibration_streaming.py` preserves raw SSE responses and aborts at128
consecutive whitespace characters outside JSON strings, or eight repeated
64--256character blocks (at least512characters). These are conservative failed
attempt diagnoses, never repaired or accepted outputs. Guards process chunks
incrementally and close only their own HTTP request.195tests pass, including
split-stream parsing, quoted whitespace and repetition cases.

The installed xgrammar backend reads its whitespace setting from global server
configuration, not the per-request whitespace fields; no unsupported claim of
bounded decoding or shared-server restart was made. Streaming guards plus
penalties are the current mitigation, not a guaranteed prevention of looping.

Fresh retry root `data/dfm12/multilingual-calibration-loopguard-20260927`
retains305outcomes and21successfully generated candidates. Only49length-stopped
cases are retried, at32requests per server. `retry-lineage.json` and manifest
hashes preserve ancestry. Completed generations awaiting review go directly to
review; they are not regenerated. This is a targeted rescue, not an independent
full recalibration. No automatic retries of semantic failures or data admission.

Use native `structured_outputs.json` with required keys, types, array structure
and no additional properties. Avoid lowering it into a custom compact EBNF.
Keep decoded string-length limits, meaningful-text checks, repetition checks,
source preservation and Gemma rendering limits in CPU validation. This also
avoids the installed bounded JSON-schema lowering's previously documented escape
issue. Do not weaken semantic review or repair rejected text silently.

Before full regeneration, validate this route on multilingual, multi-turn,
escaped math/code and all tool subtypes. Preserve the old calibration and
version the changed request contract; its old failures are not a valid model
quality estimate. The current debug work does not restart bulk calibration or
admit any rows. Review the review-request compactor too, which also converts
JSON schemas to compact grammars, before a new full calibration.

### Stronger-penalty targeted retry (2026-09-27)

Launched `data/dfm12/multilingual-calibration-strong-penalty-20260927`
for 33 cases: 30 structural-whitespace loops, one repeated-text guard failure,
and two length failures whose saved outputs were inspected and repetitive.
Retained 321 other outcomes and 15 successful generation candidates, sending
those candidates directly to review. Hash-pinned lineage preserves the original
results; this is not an independent full recalibration or data admission.

Generation repetition penalty is 1.15; review frequency penalty is 0.5.
Temperatures remain 0.65 for general generation, 0.75 for tool dialogue, and
0 for review. Concurrency remains 32 per borrowed server (ports 8600-8607).
No server restart or identity-training change. Streaming loop guards and CPU
validation remain enabled; stronger penalties do not guarantee better quality.

### Review of the remaining 25 (2026-09-27)

The stronger-penalty retry finished: eight of 33 cases recovered valid outcomes,
25 remained invalid. Inspected all 25 saved HTTP request/response pairs and
their stage/outcome records. These are not 25 demonstrated bad training rows.
Twenty-two failures are incomplete reviewer outputs; their candidates have no
completed semantic verdict. No rows were admitted and no further retry launched
as part of this inspection.

| Failure | Count | Observation | Recommended next test |
|---|---:|---|---|
| Reviewer structural whitespace | 22 | 21 stop after the closed literal_quote string, before closing the evidence object; one reaches language_correct then loops | CPU grammar/token-mask replay at the exact failing boundary; compare a simpler transport schema, preserving the full CPU validator |
| Bokmal code explanation too long | 1 | Valid JSON, 421-character user and 5,142-character explanation; correct core sum/divisibility logic buried in redundant prose | Explicit short explanation instruction and lower generation temperature; regenerate, do not truncate/accept |
| Icelandic code explanation length stop | 1 | 11,678 characters, unclosed response; irrelevant music narrative, degraded language and repetitive prose | Regenerate concise explanation; retain language-quality review |
| Faroese code explanation loop | 1 | 13,715 characters, explanation switches to English and ends in repeated Self-contained phrases | Regenerate in target language with short explanation; retain language and repetition checks |

All 22 whitespace failures received HTTP 200 and were stopped by the streaming
guard. Twenty-one saved responses have 155 trailing spaces (a chunk can cross
the 128-character threshold); the other has 129 mixed whitespace characters.
This is not a timeout, context overflow, or evidence that longer budgets help.
The repeated boundary strongly implicates constrained decoding/schema behavior,
but does not prove a grammar dead end: allowed next-token masks need inspection.
Further penalty escalation alone is not the preferred next experiment.

Per-case inventory (ID prefixes resolve against retry-lineage.json):

| ID prefix | Language | Stage | Failure |
|---|---|---|---|
| ca977f8c1edb | nb | review | whitespace after evidence quote |
| 3674674ce377 | nn | review | whitespace after evidence quote |
| dfea92c1a59b | is | review | whitespace after evidence quote |
| 117de65e4cad | fo | review | whitespace after evidence quote |
| eb5ee4919599 | fo | review | whitespace after evidence quote |
| a08ce7bdd6ba | sv | review | whitespace after evidence quote |
| 693f781119b6 | sv | review | whitespace after evidence quote |
| 91843786edb7 | fo | review | whitespace after evidence quote |
| 84c0ad5f2274 | sv | review | whitespace after evidence quote |
| 7843f237cafb | is | review | whitespace after evidence quote |
| bffec61d5536 | nb | review | whitespace after evidence quote |
| d2151e603458 | nb | review | whitespace after evidence quote |
| 9918b0e96202 | nn | review | whitespace after evidence quote |
| fc77680a5577 | is | review | whitespace after evidence quote |
| 182eedce904c | is | review | whitespace after evidence quote |
| cc640aedcf1d | fo | review | whitespace after evidence quote |
| 473a16eb609c | fo | review | whitespace after evidence quote |
| 9f774ee15670 | fo | review | whitespace before language_correct value |
| 01dd8e493428 | sv | review | whitespace after evidence quote |
| b92ce1f0d3b5 | sv | review | whitespace after evidence quote |
| 1b9e34655b44 | pl | review | whitespace after evidence quote |
| 6b928d0c86c6 | pl | review | whitespace after evidence quote |
| ff9453ec7d63 | nb | generate | explanation too long |
| 69adca604ac5 | is | generate | repetitive output hit token limit |
| 0d860924f11c | fo | generate | repeated text and English explanation |

Totals: Faroese seven, Icelandic five, Swedish five, Bokmal four, Nynorsk two,
Polish two, Dutch zero. This breakdown is conditional on the selected failures,
not a fair cross-language quality comparison. Some saved candidate prose also
looks linguistically suspect; fixing review transport must not auto-accept it.

### Boundary replay and simpler-schema test (2026-09-27)

User authorized the proposed next tests. The isolated
`dfm12.calibration_boundary_retry` runner reused the borrowed eight servers and
retained strict original JSON-schema validation, indexed evidence validation,
semantic review, deterministic checks and generation assembly. No production
default or training setting changed. 42 focused tests passed, including a test
that a structurally valid invented evidence ID is rejected by the original CPU
schema. No rows admitted.

CPU probe `scripts/probe_reviewer_boundary_20260927.py` saved results under
`data/dfm12/reviewer-boundary-probe-20260927`. All 22 whitespace failures were
replayed before and after the whitespace suffix (44 boundaries). All prefixes
were accepted. For the 21 evidence-quote cases, closing `}` was allowed before
and after the loop; for the Boolean case both true and false were allowed.
Maximum measured mask time was approximately 60 microseconds. This does NOT
support a grammar dead end or slow-mask explanation for these failures.
Important limitation: saved SSE records have no actual sampled token IDs;
the replay retokenizes exact-roundtripping text and cannot inspect live logits.
The simpler-schema follow-up replayed another 79 boundaries: all 32 pre-escape
positions permit a plain closing quote as well as an escaped quote. Escaped
field-like content inside a JSON string is schema-legal content corruption,
not proof of tokenizer corruption. All 123 replayed prefixes round-trip exactly.
See the probe's `findings.md` for reproduction and limitations. The complete
related test suites passed 198 tests (two existing SWIG deprecation warnings).

The GPU test root is
`data/dfm12/multilingual-calibration-simple-review-20260927` (sibling `.log`).
All 25 cases completed: three valid final outcomes (two semantic keeps, one
semantic rejection), 22 invalid. Failures: 11 reviewer whitespace loops,
eight evidence-text mismatches, two contradictory true-flag/non-null-issue
reviews, and one overlong generation. Thus removing schema branches merely
trades some loops for invalid copied evidence; do not promote this transport.

Three code generations used temperature 0.25 (previously 0.65) and an explicit
one/two-sentence, 300-character target. Bokmal and Faroese passed generation
validation but failed review consistency; Icelandic still exceeded the original
1,200-character explanation limit. The review correctly noticed the Bokmal
phrase "en generatoruttrykk" should be "et generatoruttrykk", but contradicted
itself by setting language_correct=true. Do not silently flip its verdict.

Next investigation should isolate actual sampler/token behavior or trial a
smaller reviewer contract with CPU-resolved evidence IDs and independently
validated verdicts. Do not solve this by accepting altered quotes, contradictory
reviews, adding tokens, or treating the two diagnostic semantic keeps as data
admission. The earlier constrained-decoding suspicion is narrowed by the CPU
replay, not established as the cause.

Reproduce the CPU measurement:

```bash
/home/ucloud/miniforge3/envs/audit/bin/python scripts/debug_multilingual_generation.py \
  --cpu-masks --output data/dfm12/new-grammar-mask-probe
```
