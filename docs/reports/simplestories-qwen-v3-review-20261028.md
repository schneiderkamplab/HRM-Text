# Qwen SimpleStories v3: completed pilot and early quality gate

## Decision

**Do not scale this recipe unchanged.** The scheduled pilot completed normally.
CPU checks improve edit boundaries, but the independent judge still accepts
material linguistic defects. This is an early-stop manual triage, not a claim
that all 100 sampled conversations received a full manual review.

## Completed Work

| Stage | Result |
|---|---|
| Blind 27B judge comparison on v2 | Rejects 12/34 manually held examples; accepts 30/34 clear examples |
| Seed screening | 6,993 accepted; 1,007 rejected, out of 8,000 |
| Flash-Next candidate generation + CPU checks | 1,380 passed; 620 exhausted their allowed retry, out of 2,000 |
| Independent 27B whole-conversation audit | 1,073 accepted; 307 rejected; no unresolved reviews |
| Additional language-only diagnostic on 100 sampled accepts | 77 accepted; 23 rejected; no production admission |

An interim commentary said 1,078 accepted; the actual journal count is **1,073**.
All requests used the externally owned Qwen servers on ports 8500-8507 at
128 concurrent client requests per server. No servers were stopped or restarted.
Generator: `Qwen/Qwen3.8-Flash-Next-FP8`; auditor: `Qwen/Qwen3.8-27B`.
Both used non-thinking requests. Auditors returned plain accept/reject.

| Task | Accepted / 400 candidates |
|---|---:|
| Creative writing | 186 |
| Multi-turn revision | 75 |
| Rewrite | 80 |
| Summary | 375 |
| QA | 357 |

The raw accepted subset is heavily skewed toward QA/summary. Do not scale it
as if it delivered the desired creative/revision mix. Replenishment must be
task-specific, and acceptance counts alone are not a quality guarantee.

## Manual Inspection

Read all turns of sample 1 in every language/task cell (20 conversations), plus
Danish creative samples 2-5 and QA samples 2-5 (8 more). Labels below refer to
`data/dfm16/expansion-v1/stories/quality-v3-qwen/manual-review.md`; its adjacent
JSONL preserves IDs, provenance, specifications and exact messages. Linguistic
inspection is by an assistant, not native-speaker certification.

| Sample 1 | Assessment |
|---|---|
| Danish creative | Understandable, but awkward literal treatment of omniscient viewpoint; location of compass changes within a short exchange. |
| Danish QA | Grounded answer; broadly usable. |
| Danish revision | Explicit realistic-school request becomes supernatural fiction; multiple grammatical defects persist. Local paragraph edit itself works. |
| Danish rewrite | Malformed input wording and unnatural pronouns; target is more fluent but source is not clean instruction data. |
| Danish summary | Faithful two-sentence target; source contains a noun-gender error. |
| English creative | Coherent bittersweet story within requested format. |
| English QA | Correct cause/effect answer grounded in supplied story. |
| English revision | Exact local edits and selective undo work; meaningful multi-turn supervision. |
| English rewrite | Humorous and plot-preserving overall, but adds minor details despite an overly strict 'all facts exactly the same' request. |
| English summary | Faithful two-sentence summary. |
| Hindi creative | Coherent plot, but noun/gender agreement errors. |
| Hindi QA | Source retains severe mistranslation and nonsensical clauses despite plausible answer. |
| Hindi revision | User instruction says second person in Hindi but third person in its English gloss; other grammatical errors persist. |
| Hindi rewrite | Malformed source and unsupported embellishment in the rewrite. |
| Hindi summary | Severely garbled source, including repeated nonsensical clauses; a plausible summary does not repair it. |
| Japanese creative | Coherent historical setting and requested ending; no material issue found in this triage. |
| Japanese QA | Correct referent and explicitly qualified inference. |
| Japanese revision | Local edit and shortening work; most action is outside school despite requested school setting. |
| Japanese rewrite | Broadly faithful formal rewrite; somewhat over-formal but not obviously unusable. |
| Japanese summary | Faithful two-sentence summary. |

Additional Danish observations: creative 2 contains "i mørkt frakke",
"lommear ur" and "en ... suck"; creative 3 uses "en langskibsbord" and a
present-day school vignette for historical fiction; creative 4 is broadly
usable; creative 5 has adjective/adverb agreement problems. QA 2 and 3 are
broadly grounded; QA 4 includes "under ledelsen" where searching is intended;
QA 5 contains missing words and malformed clauses in the source.

## Focused Language Check

This was a separate diagnostic using the same runtime, no JSON constraints,
explanations or thinking, and at most one retry. It examines prose quality only,
rather than letting a correct answer overshadow a broken source. Results:

| Language | Accepted / 25 | Rejected / 25 |
|---|---:|---:|
| Danish | 18 | 7 |
| English | 25 | 0 |
| Hindi | 10 | 15 |
| Japanese | 24 | 1 |

It catches the first Hindi creative, QA, revision and rewrite examples, but
**still accepts the badly corrupted Hindi summary source**. It also accepts the
first Danish revision's grammatical errors. The Japanese rewrite marked rejected
looks broadly usable on inspection, so this is not simply a reliable stronger
gate. Do not infer population error rates from the stratified sample or turn
these diagnostic judgments into silent deletions.

## Next Decision

Keep all old and new rows and journals; keep production closed. Do not repeatedly
add more variations of the same judge prompt until it agrees with the sample.
The next meaningful comparison is a different capable language judge on these
same examples, or manually qualified per-language seeds/generation, before another
large campaign. The currently chosen pair has not demonstrated adequate filtering
for Danish/Hindi. English/Japanese look more promising in this small triage but
still need full accepted-sample inspection before language-specific scale-up.

Future candidate generation should preserve the CPU edit checks, reduce
contradictory genre/seed combinations, avoid rigid fact preservation alongside
requests for creative embellishment, and balance replenishment by task.

Artifacts: `quality-v3-qwen/{calibration-report.json,pilot-report.json,language-check/}`.
This pilot does not change DFM16 sampling, tokenization or training admission.
