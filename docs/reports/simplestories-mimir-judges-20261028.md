# Independent SimpleStories judge checks, 2026-10-28

These are diagnostic checks, not new dataset acceptance decisions. Mimir v1.8
is the XL step 3,800,000 EMA export, not Mimir2. Existing Qwen servers and
production data were left untouched; the owned diagnostic servers were stopped
after completion. No W&B logging.

## Are content and instruction-following judgments reliable?

Not sufficiently established. On nine clear non-language failures identified
in the earlier manual review, Qwen3.8-27B rejected six and accepted three.
The missed cases were an actor change (`en/rewrite/4`), wrong narrator
attribution (`ja/qa/2`), and editing outside the requested paragraph
(`ja/revision/1`). This is a targeted failure set, not an accuracy estimate
for the corpus. Correctness, source fidelity, edit scope, and cross-turn
constraint retention need separate calibration from grammaticality.

## Independent Mimir judgments

The same 200 conversations (100 v2 and 100 v3) were judged separately for
language acceptability and for content/instruction compliance. All fit the
4,096-token context without truncation.

| Check | Observed result | Interpretation |
|---|---|---|
| Whole-conversation language | 200 accept, zero reject | Misses known defective examples; not a qualified acceptance gate |
| Whole-conversation content | 12 accept, 188 invalid, zero reject | Long system-instruction/JSON conversation interface failed; invalid is not rejection |
| Short Danish grammaticality controls | 4 correct sentences accepted; 4 incorrect sentences also accepted | Exact DaLA-style prompt still fails these negative controls |
| Short English grammaticality controls | 4/4 correct | Too small for qualification |
| Short Hindi grammaticality controls | 1/2 correct | Missed the negative control |
| Short Japanese grammaticality controls | 2/2 correct | Too small for qualification |
| Short content/instruction controls | 8/8 correct | Simple user-only yes/no questions work on controls; not yet validated on real conversations |

Short controls cover arithmetic, exact word count, faithful summarization,
and changing only verb tense. Expected labels were never sent to the model.
The 24 short responses were valid yes/no answers. Whole-conversation content
failures were truncated or non-verdict outputs, so no content accuracy can
be inferred from them. These results do not establish that all Mimir language
benchmarks fail, nor distinguish model capability from prompt sensitivity.

## Decision and next validation

### Corrected paragraph/story-level run

The owner clarified that Mimir should judge prose units, not conversations.
The corrected run completed 590 checks: two independent questions for each
of 295 intact assistant responses from the same 200 conversations. Prompts
contained only the text and a short language or internal-coherence question.
Stories were not split into sentences. No units exceeded the context limit.

| Language | Texts | Language accept | Language reject | Invalid language verdict | Coherence accept |
|---|---:|---:|---:|---:|---:|
| Danish | 74 | 74 | 0 | 0 | 74 |
| English | 76 | 67 | 0 | 9 | 76 |
| Hindi | 72 | 72 | 0 | 0 | 72 |
| Japanese | 73 | 72 | 1 | 0 | 73 |
| Total | 295 | 285 | 1 | 9 | 295 |

The nine invalid verdicts remained invalid after the single allowed retry;
they are not rejects. All coherence verdicts were valid accepts. This is
acceptance distribution, not measured judge accuracy.

Confirmed missed defect: v3 Danish creative story
`7c0230d450e9fb5865726b526f623078767709186f23969d151a6bac81580e32`
was accepted despite "i mørkt frakke" and the English intrusion "suck".
The sole rejection was a Japanese summary about Reina entering a magical
world through an old book; the sentence appears acceptable on inspection,
so it is not established as a true positive.

Scope limitation: these are assistant outputs, including short answers and
summaries, not all source passages embedded in user prompts. The check does
not test source fidelity or instructions requiring context. In particular,
it cannot detect corrupt source text omitted from an otherwise fluent summary.
Paragraph/story-level Mimir judging is therefore still not qualified as an
automatic acceptance gate with these prompts. This conclusion now rests on
actual prose-unit checks, not the superseded conversation-level approach.

Evidence: `mimir-text-units/summary.json` and
`mimir-text-units/probe/audit/quality-*/results.jsonl` under the evidence base
below; input chunks preserve text, parent ID, turn index and aspect. Driver
completed normally and cleaned up its own Mimir server. Other GPU jobs were
untouched. No dataset decisions changed.

Keep Mimir judgments as independent diagnostic evidence, not an automatic
accept/reject override. Do not promote additional SimpleStories production
based on these checks. Next test short, targeted Mimir content questions on
actual known failures plus manually checked positives, and measure false
acceptance and false rejection independently by language/task. Deterministic
checks should continue enforcing count, length and edit constraints where
possible; a second model's agreement alone does not establish correctness.

## Evidence and reproduction

Under `data/dfm16/expansion-v1/stories/quality-v3-qwen/`:

- `mimir-comparison/summary.json`: per-example language and content decisions.
- `mimir-short-probe/summary.json`: per-control decisions and expected labels.
- Each run retains launch configuration, server log, pipeline receipts and
  result records; `status.json` records completion.
- `calibration/audit/`: Qwen judgments for the manually reviewed v2 examples.

Code: `scripts/dfm16_mimir_judge.py`,
`scripts/dfm16_mimir_probe_cases.py`, and
`scripts/run_dfm16_mimir_judge_comparison.py`. Run the driver as a module;
`--probe --root <new-directory>` selects the controlled short-prompt test.
The server uses spare GPU memory only and cleans up only its own process group.
