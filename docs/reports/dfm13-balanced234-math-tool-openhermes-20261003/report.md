# Independent Review: Balanced 234 Math, Tools and OpenHermes

Root: `data/dfm13/gemma31-balanced-execution-20261003-v2`.
Scope: every `effective_keep=true` outcome in math-code, tool-dialogue and
OpenHermes, across `baltic` and `wave4`. All 83 selected conversations were read
in full against their specification references, tool scenarios or original
OpenHermes turns. Selection used the keep bit; model review rationale was not
used to make these judgments. This is an independent assistant review, **not
native-speaker certification, production approval or an admission receipt**.

## Results

| Family | Keeps reviewed | No material issue found | Repair recommended | Needs verification |
|---|---:|---:|---:|---:|
| Math-code | 28 | 20 | 8 | 0 |
| Tool-dialogue | 31 | 23 | 6 | 2 |
| OpenHermes | 24 | 7 | 11 | 6 |
| Total | 83 | 50 | 25 | 8 |

Baltic coverage: 8 keeps (3 math, 4 tools, 1 OpenHermes). Wave4 coverage: 75
keeps (25 math, 27 tools, 23 OpenHermes). The three families contain 117 terminal
cases overall; 34 non-keeps are not reviewed here. The other 117 cases in the
balanced run are outside this assignment. These numbers cannot estimate a full
false-reject rate. Repair recommendations include localized input/prose defects,
not only factual errors, so **25 is not a count of mathematical or tool failures**.

All per-case IDs, exact candidate hashes, source paths, dispositions and notes
are in [review.json](review.json). The manually authored judgments are in
[assessments.tsv](assessments.tsv); the 39 language/family group counts, including
groups with zero keeps, are in [group-counts.md](group-counts.md).

## Material Findings

1. **Unsupported parcel location after lookup-only calls**, FA tool slot 1000002
   (`06a40f07...`) and SQ tool slot 1000002 (`d284d7f2...`). The result contains
   `available_locker_id` and `redirect_allowed=true`, not the parcel's current
   location. FA says the parcel is present in locker-11; SQ says it is currently
   available in locker-18. Both are unsupported facts despite correct native
   tool structure. SK's corresponding wording says redirection is available,
   which does not have this defect.
2. **Inherited CSV explanation errors**, FA OpenHermes slot 1000030
   (`58f3d7ba...`). `row = next(reader)` does not skip a header, yet source and
   translated prose claim to read after the header. They also falsely say `a1`
   uses `row[2]`; the displayed user code assigns `row[1]`. Faithful translation
   alone is insufficient quality evidence for this source.
3. **Incorrect axis-label interpretation**, BG OpenHermes slot 1000011
   (`758a1ff5...`). `set()` fixes the API-method error, but with `x='val'` and
   `y='cat'`, labels `Colors`/`Values` are reversed relative to the data. The
   source already has this problem. Keeping the user's supplied label ordering
   is distinguishable from claiming that it correctly labels the quantities.
4. **Translation changes technical content**, SQ OpenHermes slot 1000000
   (`50668ad1...`): cast iron becomes `hekuri i gjetur` (found iron), alongside
   malformed phrasing for brittle/prone. SL OpenHermes slot 1000027
   (`9fe268aa...`) changes function/variable names and example strings under a
   preserve-code translation contract. SR slot 1000021 (`dbf543d7...`) changes
   the explicitly requested literal `Hello, World!` to a localized string in
   both prompt and code. The latter two remain internally functional but do
   not preserve the frozen source contract.
5. **Source-example substitutions**, FA OpenHermes slot 1000031
   (`cdb1f035...`): meal examples and the scope of the juice warning change.
   This is a source-fidelity finding under `translate`, not an independent
   medical judgment or a claim that the substitutions are necessarily harmful.
6. **Native-language defects missed by keeps** include Korean `박` inside BE
   math slot 1000002; Ukrainian `потрібна` in BE OpenHermes slot 1000004;
   German/malformed Luxembourgish in several LB cases; Lithuanian gender
   agreement in the NLP translation; and malformed localized math instructions.
   Medium-confidence idiomatic judgments are labeled as such. Minor isolated
   spelling/format labels were not automatically treated as factual rejection.

## Uncertain or Inherited Assumptions

Eight cases are explicitly `needs_verification`, not asserted definitive errors:
BE/LB tool venue phrasing; BG typical object-size ordering without dimensions;
BS table-versus-final-question formatting ambiguity; HR investment
generalizations and unverified historical particulars; SR boiling-time
generalization; and SR `COUNT(orderId)` equaling all rows only if IDs are
non-null. Full reasons and confidence are per case. No external sources were
consulted and no model-generated code was executed.

## Independent CPU Checks

- Exact 83-case coverage against both outcome directories; no default inferred
  disposition for unreviewed cases. Each candidate hash matches its queued hash.
- Frozen specification fields match candidate provenance. Source turns are
  bound to the supplied OpenHermes source, not substituted retrievals.
- All 28 math/code outputs passed exact checks: arithmetic recomputed from
  parameters for 26 numeric cases; the two code blocks equal their fixed
  references byte-for-byte. Code inspection confirms threshold, uniqueness,
  sorting, empty-input and nonmutation behavior; model code was not executed.
- All 31 tool candidates: exact tool definitions, JSON-schema-valid arguments,
  arguments equal scenario values, unique call IDs, linked tool results, and
  exact retry/single/clarification/no-call result sequences. Final prose was
  separately read for unsupported action/location claims.
- No native template rerender was performed by this review; these are
  structured-record and prose checks, not a new tokenizer certification.

## Handoff

Keep diagnostic outputs immutable. The report recommends repairs or further
verification; it does not edit ledgers, clear holds, approve groups, launch GPUs,
or permit publication. Other family reviews and the owner's final verification
remain separate. Parent may link this focused report from the calibration wiki;
this assignment changed report documents only.
