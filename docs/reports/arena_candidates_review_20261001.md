# DFM13 Arena Candidate Review

Date: 2026-10-01. These are manual assessments by this assistant, not model-judge
scores or measured training improvements. No new candidate has been added to
the training mix by this review. Existing DFM13 Arena exports are unchanged.

## Method And Reproduction

`scripts/review_dfm13_arena_candidates.py` selects three examples per group by
ascending SHA256 of `20261001:<source>:<id>`. It samples preferred sides,
explicit both-good sides where available, and high-rated chosen PRISM turns.
HelpSteer3's human-edit split is a separate supplemental group. Full prompts,
histories and responses are in `logs/arena_review/20261001/quality_samples.jsonl`;
selection counts are in `sampling.json` alongside it. Three examples cannot
estimate corpus-wide acceptance rates. Compar:IA uses the publisher's sample
file, not a random sample of the full corpus.

| HF source | Revision | Eligible review pool | Scope |
| --- | --- | ---: | --- |
| ministere-culture/comparia-fr-arena | 3cc8e20ae56fd0a4bc04d7f0e73244b9c353c6df | 469 | Preferred/both-good sides in upstream sample |
| nvidia/HelpSteer3 | f6d145777bcbde96137596340fab89793acd1031 | 36299 | Non-tied train preferences |
| nvidia/HelpSteer3 | same | 13740 | Train human edits; overlaps other subsets |
| lmarena-ai/arena-expert-5k | 171f77047d8d153c41b3f2c11bc910273f62f183 | 3550 | Explicit A/B winners |
| HannahRoseKirk/prism-alignment | 18ab5cfb37456f4ec8cbc00212ce54cf7b1239f6 | 18586 | Chosen responses rated at least 80 |

Preference sign for HelpSteer3 is important: negative selects response1,
positive selects response2. Expert5K's histories are NumPy/Python repr strings,
not JSON; the inspection script uses a restricted AST decoder, never `eval`.
PRISM histories retain only chosen earlier branches. Selection stops at the
rated turn; earlier assistant turns are context, not automatically SFT targets.

## Individual Assessments

IDs below locate the exact full conversation in the JSONL. Judgments apply to
these examples, not every row from their source. "Repair" means do not use the
current answer as an unquestioned positive target.

| Source / ID | Instruction and selected response | Assessment | Training decision |
| --- | --- | --- | --- |
| Compar:IA `9e991d87-888f-458b-b2d7-71ed0b9ae02e:b` | English comparison of Outlaw Star and Cowboy Bebop, explicitly requesting web verification. Long, confident comparison claims verification but invents dates and details. | Severe factual hallucination despite both-good vote. Official Sunrise lists the Outlaw Star start as 1998-01-08, not the answer's October start. No actual retrieval trace supports the answer. | Reject target; retain prompt only for independently grounded regeneration. |
| Compar:IA `f8ce5b70-9ec7-47bd-8b3c-768b83d972bc:b` | French course outline and competencies; asks for a final assessment. Response supplies written analysis (60 points), oral presentation (40), source checking and epistemic humility criteria. | Coherent French and good coverage of the requested competencies. Scoring totals are consistent. Practical timing could be refined but no major failure found. | Useful instructional-planning target. |
| Compar:IA `b933666c-aed3-497d-89f5-1d761e2e77ce:a` | French six-hour cultural-content training for trainee English teachers. Response proposes six sessions. | Fluent and relevant, but durations total seven hours: 1+1+1+1.5+1.5+1. A preferred answer can still violate an explicit constraint. | Repair the schedule before SFT. |
| HelpSteer3 preference `6117` | Multi-turn React discussion followed by converting a File object for an image source. Response presents object-URL examples. | One example uses a text/plain file as an image; another reads the file as text then passes the string to createObjectURL, which requires a Blob or MediaSource. Earlier context also contains questionable advice. | Reject technical target; executable checks are needed. |
| HelpSteer3 preference `26204` | Broad explanation of nerve biochemistry. | Generally clear educational structure. Resting-potential explanation overemphasizes the pump without clearly distinguishing gradient maintenance from membrane permeability. | Useful with factual qualification; not specialist gold data. |
| HelpSteer3 preference `11069` | Why Yoheved Kaplinsky is called Veda. | Invents a singer-songwriter biography and stage-name explanation. Juilliard identifies her as a pianist and teacher. The true nickname origin was not established by this review. | Reject factual target. |
| HelpSteer3 edit `3695` | Continuing a Power Rangers/anime crossover episode. Human edit improves character identities and dialogue continuity. | Harmless, readable creative multi-turn material. Generic but usable. | Useful creative instruction data. |
| HelpSteer3 edit `12875` | Traditional Chinese no-code product-update notifications with an example. Edited response gives an RSS/Zapier/email recipe. | Plausible conditional workflow, but assumes a product feed exists and does not provide a fully worked real feed. The fallback is underspecified. | Conditional; repair assumptions and example completeness. |
| HelpSteer3 edit `10975` | More classical-music recommendations in Traditional Chinese. | Fluent list format, but questionable work titles and inherited factual errors remain. Human editing has not established factual reliability. Not every title was externally verified here. | Hold for factual verification/repair. |
| Expert5K `976bc662-bec0-43a2-a199-0d71c05bde6e` | Improve the supplied Rust image encoder. | Suggested run flush changes 62 to 63 while still encoding 62 and resetting the counter, losing a pixel. Also proposes unsafe generic operations and invalid identifier concatenation; answer ends unfinished. | Reject as code SFT; use compilation, round-trip and property tests for candidate repairs. |
| Expert5K `153db298-ee59-403d-8ac2-917c9d3ed475` | Prove equivalence of modular-semilattice definitions. | Proof silently adds a missing bound on a variable. It also replaces strict inequalities; this change is acknowledged but equivalence to the original statement is not established. | Repair the problem statement explicitly before using the proof. |
| Expert5K `cfc5a79d-969e-4052-a8ea-a4888300e82e` | Chinese comparison of PS Vita OLED and modern OLED. | Readable explanation, but precise lifespan claims and broad claims that modern technology resolves burn-in are unsupported. Useful topic, overconfident technical target. | Factual verification and qualification required. |
| PRISM `c4696:4:1` (91/100) | Multi-turn booking of a Glasgow Christmas boat party. | Assistant promises to contact/book with the provider despite having no corresponding tool. This directly teaches false agency. | Reject for agentic training. |
| PRISM `c4146:2:0` (90/100) | Improve a blog's quality. | Sensible but generic advice, then substantially repeated at greater length. | Usable but low marginal value; prefer concise material. |
| PRISM `c4521:0:2` (98/100) | Quick recipe. Response suggests cheese quesadillas in ten minutes. | Simple, relevant, coherent response to a simple request. | Usable everyday instruction data. |

Factual cross-checks: [Sunrise official work entry](https://www.sunrise-inc.co.jp/work/detail.php?cid=94),
[Juilliard faculty biography](https://www.juilliard.edu/music/faculty/kaplinsky-yoheved),
[MDN createObjectURL](https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static).

## Will These Help?

They can add real-user topic variety, French writing, creative dialogue and
specialized requests. Preference votes are relative judgments, not correctness
certificates. These samples do not support adding every winning answer as
clean SFT. Expert users and human edits do not remove that concern.

Recommended order: audited Compar:IA and HelpSteer3 first; Expert5K with
domain-specific verification; PRISM lower priority given both the observed
agency problem and its response-license restriction. Do not sum HelpSteer3
subset sizes as independent data. Compare with inherited DFM sources before
mixing to avoid duplicate sampling. Start with repeat 1 if later approved.
This is an integration recommendation, not a new source-policy decision.

For correctness-sensitive targets, verify named facts, explicit constraints,
code execution and context sufficiency separately from fluency/preference.
Require evidence for claimed actions; do not teach models to promise completed
bookings or searches without tools. Keep both-good sides only when the source
explicitly labels them that way. Do not promote neutral ties into positives.

## SearchArena24K: URLs, Not Recoverable Native Tool Traces

Full local scan of `lmarena-ai/search-arena-24k` revision
`fac8dcf86146c8773ef020095c5694c9b2bc98d7`:

- 24069 battles; 8613 explicitly preferred sides, of which 7556 have citation entries.
- All 48138 side configurations describe built-in search/scraping/context management.
- Zero structured tool calls, tool-role messages or tool definitions in the inspected schema/traces.
- 366087 citation entries: all are label/URL pairs (four use FTP rather than HTTP).
- Traces contain user and assistant text, sometimes reasoning text, not executable search calls.

The [official analysis repository](https://github.com/lmarena/search-arena)
adds claim-attribution judgments. Its published subset's inspected record has
claims, URLs, support labels and reasoning, not original retrieved documents.
The annotation program expects a separate `scraped_urls.jsonl`; that file is
not in the published repository tree. Re-fetching a URL today would not recover
the exact historical snippet, ranking or page version seen by the model.

Therefore: **not ready for faithful tool-call-plus-answer supervision**.
Ask upstream for search queries, tool schemas, result bodies and snapshots.
Alternatively use the prompts to generate new grounded search rollouts with
real recorded calls and results, then re-answer and audit. That is a new
synthetic dataset, not a lossless conversion. Citation-attribution labels can
assist filtering but cannot replace the evidence itself.

## RepoChatArena: Actual File Context, But No Native Calls

Full local scan of `lmarena-ai/repochat-arena-preference-4k` revision
`72adb77b23e41d2a0e5e5a5783c3cec3dfe14dd5`:

| Property | Count |
| --- | ---: |
| Battles | 3844 |
| Explicit A/B winner rows | 2607 |
| Winner conversations with embedded file blocks | 2567 |
| Winner rows with GitHub links | 2607 |
| Winner conversations containing a redaction marker in user context | 2465 |
| Structured tool calls / tool-role messages | 0 / 0 |

The input includes `<details>` file blocks, file paths and actual source text,
followed by instruction and user-query markers. This is sufficient to preserve
the *observed evidence* for context-conditioned code answers. It is not enough
to recover the retriever's decision process or the original repository tree.
The examined schema contains a retriever model name but no explicit revision
field or tool schema. Some URLs might pin a revision; do not assume all do.

Redactions require inspection, not blanket rejection: the first example
replaces `Clone` in a Go documentation comment with a person-redaction marker
while leaving the function intact. Other redactions may remove crucial code.
Median selected conversation length is 45545 characters; p90 126582 and
p99 286363. These are characters, not tokens. Measure with our tokenizer and
reject over-budget records rather than dropping necessary files silently.

Two honest integration paths:

1. **Grounded answer SFT:** retain original file context and query as user input,
   supervise only the voted answer. Audit whether the provided files actually
   support it. Render through the existing Gemma4 chat template. No tool-call
   learning is claimed.
2. **New tool-use rollouts:** obtain a pinned repository snapshot, expose real
   OpenAI-compatible list/read/search tools, generate calls and record results,
   then regenerate and verify the answer. Preserve repository license notices.
   This is necessary if we want genuine retrieval-action supervision.

A deterministic synthetic `read_files` call that simply names all already
retrieved files can be serialized, but it is fabricated behavior supervision.
Do not describe it as an observed tool trajectory. Do not clone and execute
arbitrary repositories during conversion.

## Gemma4 Compatibility

`data_io/chat_templates/gemma4_native_chat.jinja` already supports structured
OpenAI function declarations, assistant tool calls and tool responses, with
Gemma-native tool-call/tool-response and yield markers. Both ordinary
context-conditioned conversations and newly collected real tool trajectories
can use this template. A template cannot restore absent evidence or actions.
For preference SFT, preserve context and select the rated final target;
supervising every earlier assistant turn would include unapproved answers.

Inventory reproduction: `scripts/inspect_arena_tool_context.py`, output
`logs/arena_review/20261001/tool_context_inventory.json`. The inventory's
`web_entries_label_url_only` counter counts HTTP(S) entries; the four unusual
entries are also URL pairs, using FTP. No GPU, training, scheduler or W&B state
was changed for this inspection.
