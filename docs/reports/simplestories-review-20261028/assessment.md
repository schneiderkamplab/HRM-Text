# SimpleStories pilot: manual review of 20 conversations

Date: 2026-10-28. Reviewed by the coding assistant, not an additional GPU judge.

## Method and Verdict

Deterministic reservoir sample (seed 20261028), one conversation from each of
four languages and five task families. Population: 300,000 accepted conversations.
All user and assistant turns were read. Raw rows are in `samples.jsonl`; readable
full conversations are in `conversations.txt`. Reproduce with
`python -m scripts.sample_simplestories_review`.

**Do not scale the current recipe unchanged.** The pilot has useful supervision:
answers are generally coherent, revisions respond to the latest request, and
the summaries/QA are mostly grounded. However, the revision setup teaches
unsolicited copying or rewriting, and task/style diversity is narrower than the
five task labels suggest. These are recipe problems, not a reason to discard
all 300K accepted conversations.

Qualitative triage: **7 clean, 7 usable with caveats, 6 repair before scaling**.
These are conversation-level manual labels, not a measured corpus rejection rate.
Equal sampling of task/language cells is deliberately not population-weighted.
Hindi and Japanese assessments are model-based linguistic judgments, not native
speaker certification. Twenty rows cannot establish low corpus-wide defect rates.

## Individual Assessments

Numbers match `conversations.txt` and JSONL row order.

| # | Language/task | Assessment | Evidence |
|---|---|---|---|
| 1 | Danish creative | Clean | First-person science fiction, source-inspired search, and a genuinely melancholy ending satisfy the three instructions. |
| 2 | Danish QA | Caveat | Correctly attributes Jose's change to Lena and self-acceptance. English passage inside Danish prompt is legitimate cross-lingual QA, but should be labeled deliberately rather than counted as fully Danish input. Slightly wordy. |
| 3 | Danish revision | Repair | Initial user turn mixes English and Danish and asks nothing; assistant translates unprompted. Later darkness, perspective, shortening, and peaceful-ending revisions work. Awkward final phrase about the man who caused sorrow. |
| 4 | Danish rewrite | Repair | Correct first person and stronger emotion, but target contains grammatical/lexical defects: `hvert dråbe`, and `uimodståelig byrde` where an unbearable burden is intended. Source also switches language. |
| 5 | Danish summary | Repair | One sentence and faithful core meaning, but `er værd at det beskidte rod` is unidiomatic Danish. The accepted target should be repaired. |
| 6 | English creative | Clean | Low-gravity moon base, first-person shared creation, and melancholy ending all present. Fluent, though familiar synthetic sci-fi imagery. |
| 7 | English QA | Clean | Direct, correct causal answer supported by the supplied passage. |
| 8 | English revision | Repair | Initial assistant repeats the user's entire story despite no instruction. Subsequent dark rewrite and Lena-focused hopeful rewrite are responsive and coherent. Remove or mask the first copying target, or add an honest explicit task. |
| 9 | English rewrite | Caveat | First-person suspenseful rewrite largely keeps events, but drops the departure/next-year promise and over-dramatizes a harmless party. Minor conflict with `keeping the plot the same`. |
| 10 | English summary | Caveat | Concise, faithful gist; calls the narrator `elderly`, which is plausible but not explicitly established. Avoid unnecessary inference in faithful summaries. |
| 11 | Hindi creative | Clean | First-person science fiction with music, identity, and tragic memory-reset ending. Coherent instruction satisfaction. |
| 12 | Hindi QA | Caveat | Correct, grounded answer about encouragement not being enough. Source has translation-like agreement/pronoun problems, so input-language quality is weaker than target quality. |
| 13 | Hindi revision | Repair | No explicit initial request, yet assistant rewrites. Initial output retains awkward agreement (`रात अंधेरा`, `एक अजीब सी लालच`). Later rescue ending and first-person dialogue revision are useful and responsive. |
| 14 | Hindi rewrite | Caveat | Satisfies first-person tense retelling and preserves the central plot. Source is visibly translation-like/grammatically damaged; useful as editing only if that is intentional. |
| 15 | Hindi summary | Caveat | Good one-sentence summary. Source contains mistranslation-like wording, including using the telephone sense of `called`; target avoids it. |
| 16 | Japanese creative | Caveat | Meets dystopia, important note, and poignant ending. Physical paper being sent into a terminal is spatially ambiguous; otherwise fluent/coherent. |
| 17 | Japanese QA | Clean | Correctly identifies the creatures' question as the trigger; concise and grounded. |
| 18 | Japanese revision | Repair | Initial user provides only a story; assistant expands it unasked. Subsequent melancholy and small-animals' perspective revisions follow instructions well. Repair/mask the initial target. |
| 19 | Japanese rewrite | Clean | Requested first person (`僕`), tension, and mystery are supplied while retaining the friendship arc. |
| 20 | Japanese summary | Clean | Concise summary preserves the unresolved trial rather than inventing its outcome. |

## What To Change Before Scaling

1. **Repair revision openings.** All four sampled revision conversations start
   with a bare story, not an instruction. Either explicitly request the intended
   initial rewrite, or keep the story as context and supervise only the requested
   revisions. Do not teach bare-input echo as a default response.
2. **Expand task variation explicitly.** All four sampled creative prompts ask
   for science fiction and a sad/melancholy ending. All four sampled rewrites ask
   for first person and heightened intensity. Draw independent genre, mood,
   perspective, audience, length, and preservation constraints; include mundane,
   humorous, hopeful, and understated writing. This sample signals a diversity
   issue; it does not prove every generated row has the same constraints.
3. **Separate cross-lingual from monolingual tasks.** English source text with a
   Danish instruction is useful when intentional. Mixed-language fragments and
   damaged Hindi source text should be repaired or explicitly framed as editing.
4. **Tighten concise review criteria**, not review verbosity: target-language
   grammar, requested operation, grounded summary, preservation constraints,
   and continuity across turns. Keep non-thinking accept/reject and at most one
   retry; no lengthy JSON evidence requirements.
5. **Validate the revised recipe with another stratified pilot** before a large
   production increase. Keep the accepted pilot intact while identifying repair
   subsets. No new large generation campaign was authorized or launched here.

The positive result is that multi-turn revisions generally work. The main gap is
the quality and diversity of the supervision we ask the teacher to generate,
not a need for a larger teacher or longer reasoning during audit.
