# Source7 26B bounded successor run

Date: 2026-10-03. Research only; no admission or production authorization.

Root: `data/dfm13/wave4/source-instruction-execution7-26b-v1`.
Detached client PID2699145 (start_ticks247873794) completed all seven cases.
Coordinator readiness: `logs/dfm13/gemma26-compiled-switchback-20261003-v1`.
All eight endpoints advertised canonical `google/gemma-4-26B-A4B-it`, 32768
context, snapshot `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`; the additional
alias did not require changing the pinned executor. Seven concurrent cases,
one per endpoint, reused production Stages/stream transport/indexed review.
No server or training process was changed.

## Verification

- 22 focused tests passed; all64 execution pins reverified after completion.
- Seven generations and seven automated reviews completed without technical
  failures. All seven candidates satisfy the successor schema/student checks.
- Complete canonical source occurs exactly once in each training user message;
  no truncation or escape normalization occurred in these fresh outputs.
- Full rendered student lengths: 519-1463 tokens, below4096.
- Automated results: four keeps, three semantic rejects. These are same-model
  reviews, not independent certification.
- Independent inspection below read all seven full user/assistant pairs,
  supplied sources and automated reviews. It is source-faithfulness assessment,
  not external factual verification or native-speaker certification.
- Summary SHA256: `8764e3d8ffb1d87886c98d7156bc3aad36de8a1897d6a677dd55f8b2674d41e1`.
  Exact candidate hashes remain in the immutable summary/outcomes. Independent
  findings here are additive; original outcomes retain their execution-time
  `independent_review: pending` field, superseded by this separate report.

## Casewise Findings

| Case prefix | Language/task | Tokens | Automated | Independent disposition |
|---|---|---:|---|---|
| 276f1583e9fd | HU summary | 1463 | reject | Repair: bat observations become observations concerning humanities scholars (`bölcsészékkel`). Also adds unsupported importance as a bat habitat and causally attributes absent records to a collapsed section. |
| 6d45c707a298 | HR extraction | 519 | keep | Supported against supplied source: champion/car, dates/location, best-three-of-each-four scoring and required Grand Prix points retained. |
| 6f7c4e6140f4 | BG painting summary | 657 | keep | Supported: requested two sentences, political/religious legitimacy and Byzantine elements retained. Minor pluralization of gold background does not alter the central account. |
| 7ec26c9581f9 | SL child summary | 616 | reject | Local repair: `dva reki` gender agreement should be `dve reki`. Reviewer identifies this but its alternative genitive explanation is unreliable; do not copy that explanation into a repair. Keep summary source-bound rather than adding visitor claims. |
| a551399b56f5 | SR rewrite/all numbers | 1408 | keep | Material repair: omits the source's spelled-out two-decade interval despite all-numbers instruction; changes serious damage to Phoenix palms into a most-susceptible ranking and changes plants with all symptoms into plants showing symptoms generally. Automated false keep. |
| d8d72bb414b7 | SQ Adler bullets | 1196 | keep | Local grounding repair: adds motive that Adler chose a poorer district to help the community; supplied text establishes location, not motive. Source itself is linguistically degraded, so retain source-quality caveat. Automated false keep. |
| f58eae2c17f8 | BG bibliography extraction | 695 | reject | Minor completeness repair: five bibliographic entries/four domains retained, but Google Book/Digitalisat annotations omitted. Reviewer treats this as meaning failure; it is a localized loss of access annotations, not invented bibliography or wrong-language output. |

Independent total: two source-supported, four substantive/local language or
grounding repairs, one minor bibliographic completeness repair. None admitted.
Serbian pesticide statements were inspected only for fidelity to the supplied
historical text, not endorsed as current treatment advice.

## Conclusion

The instruction-only generation field plus CPU source insertion resolves the
specific source-copy length artifact in all seven tested cases while preserving
source and full student budget. It does not resolve semantic/language quality:
two of four automated keeps still contain identifiable grounding/constraint
defects. Do not extrapolate seven selected historical failures to overall26B
quality or approve bulk from this run. Originals and all prior31B artifacts
remain unchanged. No further generation or repairs were launched.
