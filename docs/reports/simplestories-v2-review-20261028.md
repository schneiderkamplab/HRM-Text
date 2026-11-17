# SimpleStories v2: review of 100 accepted conversations

## Decision

**Do not scale the current recipe unchanged.** The revised opening instructions
are substantially better, but automatic acceptance still misses source corruption,
revision-state loss, and changes to facts during constrained rewriting.

Reviewed all turns in the 100 conversations in
`data/dfm16/expansion-v1/stories/quality-v2/pilot/manual-review-100.md`
and its adjacent JSONL. Sample labels below refer to that file's headings.
There are five accepted examples per language/task cell: four languages and
five tasks. This is a stratified diagnostic sample, not an estimate of the
production rejection rate. This is an assistant textual inspection, not native
speaker certification, particularly for Hindi and Japanese.

The automatic pilot accepted 1,869/2,000 candidates, rejected 85, and left 46
unresolved. Those acceptance decisions are not a sufficient production gate.
The separate re-audit of the old 300K accepted 283,842 and rejected 16,158;
these results alone do not establish that its retained subset is free of the
same weaknesses. Preserve the original 300K and their audit evidence.

## Main Findings

1. All 20 revision conversations now start with an actual writing request.
2. All 40 creative/revision initial answers meet sampled length ranges:
   whitespace-delimited words for Danish/English/Hindi, non-whitespace Unicode
   characters for Japanese. This corrects initial visual suspicions about length.
3. Hindi source-dependent tasks contain conspicuously corrupted seeds, even when
   the final answer looks superficially reasonable. Do not audit only targets.
4. Danish examples frequently use English source passages despite monolingual
   metadata. Translation/rewrite tasks can be useful, but must be labeled and
   prompted as cross-lingual, not counted as monolingual coverage.
5. Some tense/viewpoint operations are no-ops: the source already has the requested
   form. Other multi-turn examples lose a previously requested viewpoint or tense.
6. English and Japanese also have concrete fidelity failures. This is not solely
   a low-resource-language problem.

## Per-Example Findings

`clear`: no material issue found in this inspection, not a correctness guarantee.
`caveat`: useful content with a minor, ambiguous, or recipe-label issue.
`hold`: concrete defect that should be filtered or repaired before admission.
These are review annotations only; no source rows or audit decisions were deleted.

| Example | Assessment | Finding |
|---|---|---|
| da/creative 1 | hold | Library scene shifts to brother's bedroom without a clear transition; prompt references an unavailable seed. |
| da/creative 2 | caveat | Coherent school story, but English seed conflicts with monolingual recipe. |
| da/creative 3 | hold | Incorrect noun gender: "den lille, stovede antikvariat" (the source uses the Danish accented spelling). |
| da/creative 4 | hold | Realism/continuity problems: North Jutland mountains, unexplained discovery under floorboards, name drift. |
| da/creative 5 | clear | Appropriate restrained garden scene; minor redundant phrasing. |
| da/qa 1 | caveat | Correct sequence answer; source wording for the character's emotion is awkward. |
| da/qa 2 | caveat | Correct pronoun answer; English source, Danish response. |
| da/qa 3 | caveat | Correct event order; English source, Danish response. |
| da/qa 4 | hold | Answer leaves a quotation unclosed; translated riddle also weakens its wordplay. |
| da/qa 5 | caveat | Grounded answer; English source, Danish response. |
| da/revision 1 | clear | Perspective, shortening, and selective undo work. |
| da/revision 2 | hold | Broken Danish phrase and unsupported mystery resolution in initial story. |
| da/revision 3 | hold | Grammatical corruption persists through revisions; local edit itself is preserved correctly. |
| da/revision 4 | hold | Broken word order in the opening answer persists across later answers. |
| da/revision 5 | hold | Undo restores present tense in the body but leaves the retained opening in past tense. |
| da/rewrite 1 | caveat | Useful explicit translation/rewrite, not monolingual supervision. |
| da/rewrite 2 | caveat | Main plot and viewpoint retained; cross-lingual recipe. |
| da/rewrite 3 | hold | Requested present-to-past operation on a source already in past tense. |
| da/rewrite 4 | hold | Drops puppy-house construction; 186 whitespace words versus requested 120-180. |
| da/rewrite 5 | caveat | Main plot preserved within 172 words; cross-lingual recipe. |
| da/summary 1 | caveat | Faithful one-sentence summary of English source. |
| da/summary 2 | clear | Faithful two-sentence summary. |
| da/summary 3 | caveat | Faithful short summary of English source. |
| da/summary 4 | caveat | Faithful summary; source contains some awkward/mixed-language wording. |
| da/summary 5 | caveat | Good concise summary; narrator gender is inferred rather than explicit. |
| en/creative 1 | clear | Coherent fantasy and requested ending. |
| en/creative 2 | clear | Coherent short hopeful story. |
| en/creative 3 | clear | Appropriate bittersweet fantasy. |
| en/creative 4 | caveat | Good prose; positive component of requested bittersweet ending is weak. |
| en/creative 5 | caveat | Good story; user mentions a seed not included in the conversation. |
| en/qa 1 | clear | Grounded motivation answer. |
| en/qa 2 | clear | Grounded factual answer. |
| en/qa 3 | clear | Correct sequence. |
| en/qa 4 | clear | Correct discovery answer. |
| en/qa 5 | clear | Correct pronoun resolution. |
| en/revision 1 | hold | Tense operation is effectively a no-op on already-past narrative. |
| en/revision 2 | clear | Ending/opening edits and selective undo work. |
| en/revision 3 | hold | Already-past narrative; changes direct speech unnecessarily during tense conversion. |
| en/revision 4 | hold | Already-past narrative yields another ineffective tense operation. |
| en/revision 5 | caveat | Final explicit instruction is followed, but user misnumbers prior changes. |
| en/rewrite 1 | clear | Formal rewrite preserves story. |
| en/rewrite 2 | hold | Omits return home and sharing the lesson, changing the plot endpoint. |
| en/rewrite 3 | caveat | Useful rewrite; sampled length is absent from user prompt, so 248 words is not a user-contract violation. |
| en/rewrite 4 | hold | Changes building a house alone into building it with friends. |
| en/rewrite 5 | hold | Requests first-to-third person although source is already third person. |
| en/summary 1 | clear | Faithful, two sentences. |
| en/summary 2 | clear | Faithful, two sentences. |
| en/summary 3 | clear | Faithful, two sentences. |
| en/summary 4 | caveat | Compresses two distinct events into a less precise causal account. |
| en/summary 5 | caveat | Adds "delicious" where source establishes edibility only. |
| hi/creative 1 | caveat | Coherent story; local noun agreement issue. |
| hi/creative 2 | clear | Coherent playful story. |
| hi/creative 3 | caveat | Pronoun/honorific agreement shifts; comic tone is weak. |
| hi/creative 4 | caveat | Noun gender issue; historical setting underspecified. |
| hi/creative 5 | clear | Coherent fantasy within length range. |
| hi/qa 1 | hold | Correct broad answer but malformed source grammar/pronouns. |
| hi/qa 2 | hold | Corrupt source wording and repetition leak into answer. |
| hi/qa 3 | hold | Source ends mid-sentence and contains pronoun problems. |
| hi/qa 4 | caveat | Correct answer, mildly awkward translated source. |
| hi/qa 5 | hold | Source semantic corruption produces an unclear moral answer. |
| hi/revision 1 | hold | Child-friendly revision loses Meera's requested viewpoint and changes events. |
| hi/revision 2 | clear | Ending edit and first-person conversion are coherent. |
| hi/revision 3 | clear | Simplification and requested scene expansion work. |
| hi/revision 4 | caveat | Tense instruction lacks a direction; resulting transformation is weak. |
| hi/revision 5 | caveat | Selective undo works; initial answer has a local agreement error. |
| hi/rewrite 1 | hold | Source corruption and already-third-person input undermine conversion. |
| hi/rewrite 2 | hold | Corrupted source; rewrite also compresses growth chronology ambiguously. |
| hi/rewrite 3 | hold | Changes children running away to dancing. |
| hi/rewrite 4 | caveat | Understandable but awkward source; target preserves main plot. |
| hi/rewrite 5 | hold | Repeated/garbled source passages despite cleaner target. |
| hi/summary 1 | hold | Adds magical robot and stronger conclusion; target also has case-agreement error. |
| hi/summary 2 | hold | Source has extensive corruption/repetition despite plausible summary. |
| hi/summary 3 | hold | Severe source corruption prevents reliable grounding. |
| hi/summary 4 | hold | Source repetition and intrusive viewpoint changes. |
| hi/summary 5 | hold | Repetitive, semantically broken source. |
| ja/creative 1 | clear | Coherent hopeful science fiction; length satisfied. |
| ja/creative 2 | clear | Coherent fantasy; length satisfied. |
| ja/creative 3 | caveat | Minor implication of a previous encounter not established in story. |
| ja/creative 4 | caveat | Grandfather returns without an explicit departure; otherwise coherent. |
| ja/creative 5 | clear | Coherent playful story; length satisfied. |
| ja/qa 1 | clear | Grounded motivation answer. |
| ja/qa 2 | hold | Attributes narration to teacher although source says teacher and children heard it. |
| ja/qa 3 | caveat | Plausible causal inference, not explicitly stated. |
| ja/qa 4 | clear | Supported explanation of friendship/theme. |
| ja/qa 5 | clear | Correct flooded-road explanation. |
| ja/revision 1 | hold | Ending-only edit also deletes earlier sentences; local edit boundary not respected. |
| ja/revision 2 | clear | Opening-only edit preserves remainder; shortening preserves main events. |
| ja/revision 3 | caveat | Main operations work; mechanical tense conversion introduces awkward conditional grammar. |
| ja/revision 4 | clear | Dialogue addition and new ending broadly preserve requested context. |
| ja/revision 5 | hold | Happy-ending revision reverts from requested first-person viewpoint to third person. |
| ja/rewrite 1 | clear | Actual tense conversion works; hidden 600-800 length is absent from prompt. |
| ja/rewrite 2 | caveat | Gentle rewrite slightly compresses escape/return; hidden length absent from prompt. |
| ja/rewrite 3 | clear | Natural dialogue and preserved plot within explicit range. |
| ja/rewrite 4 | caveat | Source is already mostly past tense; genuine style change but weak tense task. |
| ja/rewrite 5 | hold | Opening assigns concealment skill to fish, conflicting with source's octopus distinction. |
| ja/summary 1 | clear | Faithful one-sentence summary. |
| ja/summary 2 | clear | Faithful one-sentence summary. |
| ja/summary 3 | caveat | Good two-sentence answer; user age-range wording contains a typo. |
| ja/summary 4 | clear | Faithful three-sentence summary. |
| ja/summary 5 | clear | Faithful two-sentence summary. |

## Minimal Next Changes

- Screen seed passages before generation, especially Hindi. Reuse compact
  accept/reject review; no verbose judge outputs or new judging framework.
- Choose tense/viewpoint transformations compatible with the actual source;
  put every enforced requirement in the user's visible instruction.
- Keep useful cross-lingual tasks, but explicitly label them; do not disguise
  them as monolingual generation.
- Add CPU checks for explicit length limits and unchanged text outside an
  opening/ending-only edit. Do not apply obsolete length limits after shortening.
- Make the existing whole-conversation review focus on source quality, unchanged
  facts, and accumulated revision constraints. Acceptance must cover every turn.
- Repeat a small stratified manual check after these fixes before scaling.

No generation, audit, or training processes were restarted for this review.
No original conversations were discarded. No production scale-up was authorized.
