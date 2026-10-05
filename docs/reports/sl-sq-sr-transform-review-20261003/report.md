# Slovenian, Albanian and Serbian accepted-transform spot review

2026-10-03. CPU-only, no model calls, no edits to source data, audit queues,
release ledgers, exports, registries or workers.

## Scope and evidence

Read all input/target messages for **32 accepted rows**: four per transformation
family for Slovenian and Albanian. Selection was the first four accepted IDs in
lexicographic order per family, within one read-only SQLite transaction per
language. This is deterministic for the frozen snapshot, not a representative
quality survey. Acceptance means `release/wikipedia-<lang>/ledger.sqlite`
`status=accepted`; these are not claimed to be published exports. Embedded
candidate `audit_status=pending` is an old candidate field; the accepted ledger
status and associated review were captured separately.

At snapshot time SL had 187,551 accepted rows and SQ 88,928. SR's release ledger
was empty and its release status was nonterminal/not export-ready. An additional
bounded lookup of the first 256 sealed SR candidates found all audit jobs pending
(65 denoising, 65 prefix, 65 span, 61 reordering). No Serbian candidates were
misrepresented as accepted. This does not prove that no later acceptance exists
elsewhere in the changing audit queue. Review SR once accepted rows materialize.

All **32/32** source IDs, titles, URLs, selected windows, candidate IDs and
messages matched replay against hash-verified local Wikimedia parquet at revision
`b04c8d1ceb2f5cd4588862100d08de323dccfbaa`. Additional checks passed for exact
denoising targets, prefix/suffix joins, single-gap reconstruction, and preserved,
nonidentity paragraph-block permutations. Source fidelity does not establish
source quality or uniquely recoverable answers.

Evidence: `evidence.json` freezes complete candidates, judge responses and source
documents; `snapshot.json` pins inputs and selection. `sl-read.md` and
`sq-read.md` show all reviewed inputs/targets. `review.json` and `case-review.md`
give every case's observation, exact ID, candidate/message hashes and source row.
`receipt.json` binds these artifacts. Neither full source archives nor live
databases were copied or altered. No external factual verification was attempted.

## Clear defects and narrow remedies

1. **SL prefix, missing mathematical content**, case 1,
   `00006a4aba1e1927de20182cf5a3ea7edaa680be036320a20df5e49604be4225`,
   *Tristrana ortobikupola*, source row 133882. The target announces expressions
   for volume and surface area under `Prostornina in površina`, but neither
   expression appears before the circumradius sentence. This is incomplete
   extraction inherited from the source, not a model fabrication. Reselect
   intact prose, or restore source mathematical content before deriving a new
   candidate; do not invent the missing formulas in this target.
2. **SL reordering, broken HTML and missing tables**, case 14,
   `000bffa8d3d55f61241e1b2d83ef0cc16dec7c5b55123a669020452239a25b4e`,
   *Slovenija v kvalifikacijah ... 2010*, source row 84828. Independent shuffled
   blocks include `<table style=...><tr><td>` and
   `</div></td></tr><small>... </table>`. Statistics headings and legends have
   no corresponding tables. The judge explicitly accepted preserved HTML with
   5/5 scores; that verifies copying, not content suitability. Review this exact
   row and derive a clean prose window, rather than removing all table/list data.
3. **SQ reordering, substantially garbled source prose**, case 18,
   `0001e58b1ad0904d94a0468a5c70dfda299e547071cd187fb55932cc49867ba1`,
   *Sllepçë*, source row 10388. The history passage includes `marte marte`,
   `etj pche oktal`, and `razigravat` amid malformed clauses. This is not merely
   an accent or inflection preference. Exact source copying does not justify the
   judge's language-quality 5. Recommend exact-window review/exclusion or
   replacement with independently sound source prose, not speculative rewriting
   of demographic/history claims.
4. **SQ prefix, largely empty continuation structure**, case 28,
   `000b5c85522b42285a4ccbc30d5d894500d29a73b4a348c7f181bd1c4799bb27`,
   *Pirenetë*, source row 16209. After one remaining economic sentence, the target
   contains empty natural-resources/climate/flora/demography sections and a
   ski-centre introduction without centres, then links/categories. Earlier source
   paragraphs have geographic prose. Prefer a complete earlier window; this is
   not a proposal to remove every row with a heading or list.

## Task-scope concerns, not automatic exclusions

- **SQ reordering**, case 19,
  `0003311aeceb17443f9bf474e80a7cdf123daf66fe17b36ccb471a7e248b8b1a`,
  *Faik Krasniqi*: selected window contains exhibition/award lists, gallery and
  book-cover labels, links and categories, **no prose paragraphs**. The original
  document has substantial biography prose before the window. Independent section
  ordering is not recoverable uniquely. Prefer paragraph-aware window reselection;
  the meaningful list content itself is not worthless or a blanket-filter target.
- **SL reordering**, case 12,
  `0006fd1aa006f4916806c2be19a384f7c7c87d615b6ab972f0c25a14be516273`,
  *Trdinova pot*: one narrative paragraph plus useful route/information-point
  lists and headings. This is not equivalent to category-only debris, but neither
  is it a clean multi-prose-paragraph example. Review task fit separately from
  source usefulness. Do not silently relabel a list task as prose paragraphs.

Other reordering examples contain substantive prose. Conventional ordering of
club/national-team sections, right/left inscriptions, or minority descriptions
can still have multiple sensible permutations. The reference order is known;
it is not necessarily uniquely implied by the user prompt. Similarly, exact
long spans/named lists cannot always be inferred, but that alone does not
invalidate source-continuation/infill training objectives.

## Lesser concerns and limits

Visible source artifacts include `[gostota]]` (SL case 2), empty parentheses
(SL case 5), and an untranslated Cyrillic annotation `со коавтори` in an SQ
bibliography (case 21). Foreign book titles, names and meaningful lists are not
automatically language contamination. Several targets retain spelling/agreement
problems because the denoiser restores the source exactly. Native judgment is
needed before converting these lesser observations into admission decisions.

The spot review found useful coherent material too, including the SL sales
examples and SQ scientist biography/rockism prose. No factual accuracy rate is
claimed. Possible historical, medical, fictional or numeric concerns without
local corroboration are marked unverified in the per-case ledger, not declared
false. No population rates, language-wide holds, new regex exclusions or live
repairs follow from this small non-native review.

## Verification

The extraction and finalization scripts completed successfully with fail-closed
source-pin, replay and task-mechanics assertions. Both refuse overwriting their
frozen evidence/review outputs. These are evidence checks, not a claim that the
quality judgments are automated tests. Reproduction against changing live
ledgers requires a new output directory and a new snapshot.
