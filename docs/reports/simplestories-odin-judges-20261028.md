# Odin paragraph/story comparison, 2026-10-28

## Setup

User-authorized remote comparison through `https://api.odincore.ai/v1`.
The API lists `odin-2-large` (not `odin-2-l`); response model IDs confirmed
`odin-2-large`. Used the identical 295 intact assistant text units from the
Mimir comparison, with separate language and internal-coherence questions.
No conversation wrappers, no source fidelity checks, no hidden manual labels.
Requested temperature zero and eight output tokens. No schema/grammar constraint.
Parser accepts a single yes/no verdict with an optional trailing period;
Mimir's earlier parser did not allow the period. Raw responses are retained.

## Results

| Language | Texts | Language accept | Language reject | Coherence accept | Coherence reject |
|---|---:|---:|---:|---:|---:|
| Danish | 74 | 58 | 16 | 71 | 3 |
| English | 76 | 76 | 0 | 76 | 0 |
| Hindi | 72 | 60 | 12 | 72 | 0 |
| Japanese | 73 | 67 | 6 | 73 | 0 |
| Total | 295 | 261 | 34 | 292 | 3 |

All 590 final verdicts valid; 553 accepts and 37 rejects. These are judgment
counts, not accuracy estimates. Multiple versions of a story are correlated.

Mimir accepted all 34 language cases rejected by Odin, and all three coherence
cases rejected by Odin. Odin accepted Mimir's sole rejected Japanese summary,
which looked acceptable on inspection. Odin also accepted all nine cases whose
Mimir language verdicts were invalid; the punctuation-parser difference means
these format results should not be presented as a model-quality comparison.

## Manual spot checks

- Odin rejects the known Danish story containing "i mørkt frakke" and the
  English intrusion "suck", previously accepted by Mimir. Parent ID:
  `7c0230d450e9fb5865726b526f623078767709186f23969d151a6bac81580e32`.
- Other Danish rejections include "den lille, støvede antikvariat" and
  "Da han viser det frem, gispende folk samles om ham": clear agreement and
  clause-order issues respectively.
- A rejected Hindi passage starts "स्कूल की गलियारे", an agreement problem.
- Rejected Japanese revisions include the malformed "れいなのは". However,
  the short answer rejected under parent ID
  `1e9259af25fbf714835083bf8b3b3e56fc39e654b296037981ee04e3d1c162c9`
  appears understandable and grammatical, though redundant. Do not assume
  every rejection is a real defect.

Conclusion: more promising than Mimir under these prose prompts, with several
confirmed catches, but not yet a qualified production gate. Precision/recall
require independent labels on accepted and rejected examples. English's zero
rejections do not establish perfect English quality. Source passages embedded
in user prompts and instruction/source fidelity remain outside this check.

## Concurrency and API caveats

Per owner instruction, tried 8, 16, 32, then 64 concurrent requests. HTTP 429
at 64 triggered a single halving to 32. Headers exposed a request allowance of
180 and remaining requests zero, while token allowance was unused. This does
not prove a 32-request concurrency limit: quota exhaustion is distinct from
concurrent capacity. No reset/window duration was provided in those headers.

The shared fail-fast guard stopped on bursts of outstanding 429 responses.
Resumed only unfinished rows, preserving all valid verdicts. A conservative
160-request/60-second cap and 65-second cooldown did not fully avoid further
quota exhaustion; the final 136-row continuation completed without HTTP errors.
Do not advertise 160/minute as a verified sustainable rate. Confirm provider
quota/window semantics before a larger campaign.

The API reports hidden reasoning despite short visible verdicts and the
eight-token request limit. Across the 590 saved verdicts it reports 239,046
prompt tokens and 407,522 completion tokens, of which 405,550 are reasoning
tokens. This excludes preflights and canceled/unsaved attempts and is not a
billing estimate. Non-thinking operation is not established for this endpoint.

## Evidence

Base: `data/dfm16/expansion-v1/stories/quality-v3-qwen/odin-text-units/`.

- `summary.json`: counts and Mimir/Odin agreement table.
- `probe/chunks/*.jsonl`: unchanged inputs with parent/turn/aspect provenance.
- `probe/audit/quality-*/results.jsonl`: per-example verdicts and API responses.
- Chunk receipts verify input/result hashes; `status.json` records completion.
- `concurrency.json`: doubling/backoff history; `launch.json`: non-secret config.
- Runner: `python -m scripts.run_dfm16_odin_judge`, using `ODIN_API_KEY` or
  a no-echo prompt. Credentials are not written to project files/logs.

No W&B logging, GPU process changes, or training-data acceptance changes.
