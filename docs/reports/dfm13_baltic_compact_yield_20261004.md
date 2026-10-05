# Baltic Compact Yield: Read-Only Diagnosis

Root: `data/dfm13/baltic/synthetic-compact-26b-20261004-v1`.
Only outcomes with `completed >= 1791078108` are included. Frozen count snapshot
at1791081416.886:44,429 terminal,6,508 accepted (14.65%). No running code, ledger,
server or process was changed. Counts and120 exact raw-review hashes are in
[counts.json](dfm13-baltic-compact-yield-20261004/counts.json).

## Failure Accounting

| Fresh outcome | Count |
| --- | ---: |
| Accepted keep | 6508 |
| Valid repair | 6841 |
| Valid needs_verification | 13245 |
| Valid reject | 2074 |
| Review invalid output | 10747 |
| Generic invalid_output | 4454 |
| Generation/review infrastructure unknown | 560 |

10,539 review failures specifically have empty reason. Of4454 generic invalid
outputs,4094 failed generation,183 failed assembly and177 failed **post-review**
duplicate-issue validation. Calling all4454 generation failures is inaccurate.
Leading actual generation problems:1213 schema echoes,563 duplicate user keys,
502 missing assistant fields,343 structural-whitespace loops. Raw infrastructure
errors are predominantly server disconnects; no inference about ownership/cause.

## Empty Reasons

The first120 eligible IDs sorted lexicographically all contain the exact complete
decision `{"verdict":"keep","issues":[],"reason":""}`, finish_reason=stop.
This is a deterministic bounded sample, not all10,539 raw responses inspected.
Three corresponding conversations were read against their supplied source:

- `0004355083a8`: LV refugee-policy bullet answer follows the supplied Europarl
  proposal and preserves the necessary/safe repatriation qualifiers.
- `00082d6de42b`: LV three-bullet art-history answer follows its source. The
  source starts mid-fragment and its historical claims are not independently
  certified here; rationale recovery cannot certify source truth.
- `000f51251b96`: LT Aara conversation retains the supplied identity/history and
  hypothesis qualifiers. No obvious source contradiction found in this reading.

**Minimal fix:** permit empty/missing rationale for an otherwise valid complete
keep with empty issues, record a warning, then apply the unchanged deterministic,
duplicate, source-hold and native-render gates. This removes a formatting veto,
not a substantive quality criterion. Prefer hash-bound CPU recovery of preserved
decisions over repeated generation or repeated judging merely to elicit a reason.
It does not justify automatically accepting every empty-reason candidate: known
bad candidates and source holds still override the model keep. Retain raw evidence.

## Eight Needs-Verification Examples

These are the first8 NV IDs in lexical order in a subsequent read-only snapshot;
claims concern the inspected examples only, not the entire NV population.

- `00023f0cf251`: false stated hold rationale. The separate word `Depresija`
  supplies the requested condition, exactly as `Depression` does in the English
  source. It is not evidence of a malformed task. This is source comparison,
  not independent medical validation of the symptom list.
- `000b47927c29`: nonsensical stated hold rationale quotes the same Latvian phrase
  as both correct and erroneous. The answer extracts the two cities actually
  mentioned. The user wording is imperfect; no missing external evidence is named.
- `00248c298b74`: clear false stated hold rationale says the summary is accurate
  and that exactly two requested sentences is correct. It supplies no defect.
- `000198537db1`: real repair candidate, not an external verification dependency.
  The assistant adds an interpretation of Parliament's ability to prevent abuse
  that the source does not establish, and has visible agreement problems.
- `0017c95be7d1`: real language repair/reject candidate, not missing evidence.
  Python reversal code is intact, but prose includes malformed words such as
  `pievolejiet` and `patniedziet` (actual file spelling includes Latvian accents).
- `001ddf9009d4`: real repair candidate. The final answer contains malformed
  wording (`nesatiklas`) while rephrasing the source's no-harm constraint.
- `0026a1afdc71`: real language repair/reject candidate. Numerous malformed
  culinary terms and an English parenthetical occur through the conversation;
  the review's focus on a combining character understates the defect.
- `001bf2286870`: debatable summary-coverage objection, not unavailable evidence.
  The requested three-point comparison need not enumerate every source detail;
  visible language problems still warrant review rather than automatic promotion.

Thus3/8 have unjustified stated NV rationales,4/8 contain concrete repairable or
rejectable defects,1/8 has a debatable coverage rationale plus language problems.
Do not turn NV wholesale into keep. Minimal rubric clarification for a future
pinned successor: use NV only when a **named essential fact/evidence is missing**;
observable language/omission/source errors are repair/reject, and a reason affirming
all requirements is not an uncertainty. No new calibration stack is required.

## Generation Examples And Minimal Fixes

- `0085c87d38ed`: raw output includes JSON Schema keys together with actual user
  and assistant text. Actual transport is `json_object`, not constrained to the
  requested conversation schema. Use the already-supported instance schema on a
  future successor, retaining unsupported-decoder keyword sanitization; minimally
  state “return an instance, not the schema; user and assistant share one object”.
- `0033149d6f91`: user/assistant split into separate turn objects, plus malformed
  language. Do not blindly splice this into an accepted conversation.
- `0042fe32eb5b`: unclosed assistant JSON string. Preserve raw; one schema-bound
  retry of the same source is appropriate, not silent quote completion.
- `004a17422949`: LaTeX box escape becomes a text-control failure. Fix escaping
  requirements in the future generation contract, not the target's mathematics.

Keep semantic checks, full student length, mathematical consistency and source
fidelity unchanged. At most one targeted repair plus fresh blind audit handles
the6841 valid repair decisions; it is not guaranteed additional acceptance.

## ETA

Observed accepted throughput is118.0/min since the original start and114.2/min
over the latest600s. A naive remaining140K-target ETA is18.9–19.5 hours, **not a
defensible completion promise**:8/12 groups are below the16.67% yield needed to
meet their target under the existing six-attempts-per-target cap. Projecting each
current group yield to its cap leaves approximately27,255 rows short overall.
Optional-rationale recovery could materially improve this, but its deterministic
pass count and group distribution must be measured before publishing a revised
ETA. Attempts/sec alone is not accepted-row throughput.
