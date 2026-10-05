# Wave4 Literal-Preservation Probe

## Execution and Limits

New isolated module `dfm12/wave4_literal_probe.py`; root
`data/dfm13/wave4/literal-preservation-probe-20261003-v2`.
Command: `python -u -m dfm12.wave4_literal_probe run --concurrency-per-server 2`.
PID2255174 finished18/18 on existing26B ports8800..8807 at maximum two requests
per server,600s request timeout. No server restarts/live campaign edits.
Three tests pass. Full targets, sources, raw streams and outcomes preserved.
No admission, production approval or publication.

Comparison uses14 previously exposed failures and4 comparatively good controls
against historical accepted outputs, not randomized same-seed A/B results.
Original specs are hash-verified. `pairs.json` gives complete IDs and baseline
paths; new candidate paths are `ROOT/candidates/<id>.json`. All18 complete new
conversations were individually read against source/reference and prior findings.
This is agent review, not native-editor certification or a population error rate.

The first preparation root (without-v2) is retained: a tool transport payload
was mistakenly used as a spec. CPU execution failed before any model calls.
Preparation now uses the original generation-requests.jsonl and checks spec SHA.

## Changes Tested

Generation-only suffix asks for literal source relationships, all source-user
input, same subject/task for scenario adaptation, ordinary shorter prose, function
outputs rather than integer-only requests for code, direct answers instead of
third-person analysis, and ISO dates if native wording is uncertain. Existing
schema/rendering/tool/semantic gates remain unchanged. The suffix explicitly
mentions exposed webpage and title/insignia defects: any local gains on those
cases are not independent generalization.

Added diagnostic-only script flags, excluding code, URLs, inline identifiers and
exact quoted source text. No automatic rejection or target truncation. Same-script
foreign words can escape this check; legitimate quotations may require exemption.

## Semantic Comparison

Automated outcomes:11 keeps,6 rejections,1 invalid review. All18 generations
assembled. Only3 of11 keeps have no clear material issue in this reading:
SK grounded1 (local repair), LB grounded0 and FA OpenHermes0 (controls).
The other8 still need language/meaning correction or native adjudication.

| Case | ID prefix | Judge | Independent reading |
| --- | --- | --- | --- |
| BE grounded0 | aa507562 | keep | Removes Egyptian-women/desire corruption. Still awkward `аднаго жа бажаства` / `яшчэ далей`, and overgeneralizes the local-cult pattern as polytheism's definition. Partial improvement only. |
| BE OpenHermes0 | 405408f1 | keep | Still `Кит, Повітряная шарык`, `павітровая шарык`, Russian `бризом`; repeated native-language defects. |
| BE multiturn1 | b876181a | reject | Sinhala character disappears, but `нязрочнасць`, `хімічныя сурмавы` and unsupported generalized glaze-chemistry advice replace it. |
| BE code1 | 059307a | keep | Code exact; user `датаймі`, `кратныхны`, integer-output request and third-person analysis persist. |
| BE tool1 | acb0be89 | keep | Still `2 сарада 2030` / `У якій`. Reviewer literally translates `2 sarada` and nevertheless sets all dimensions true. Concrete false accept. |
| LB summary0 | 91acef89 | reject | Still replaces title (`ersat`); `Anzwendlend`, `befindet`, `posthum verleeft` remain despite explicit cue. |
| LB OpenHermes1 | 8da2ae21 | keep | Returns to webpage loading: real subject improvement. Still `fir ... zouzegrëff`, `empfanget`, `dynamesch lädt`; native quality not repaired. |
| LB code1 | 3fcbf61e | keep | Integer-only instruction fixed; exact code. `soll hei genauen Numm ... hei`, `Zahlen`, `berücksichtegen`, `lösen` and third-person explanation remain. |
| HU summary0 | 276f1583 | reject | Removes Cyrillic intrusion but source1998-2006 becomes `több évtizeden keresztül` (several decades); visit-permission condition omitted and significance overstated. |
| HU OpenHermes0 | e55bca92 | reject | Indonesian `berubah`, Thai letters in `szนั้น`, malformed Hungarian remain. Script diagnostic catches Thai, not Indonesian. |
| SK grounded1 | 06151e6b | keep | Polish `występ` removed;2000/2002/2003 and requested categories preserved. Clear local improvement. |
| SK OpenHermes0 | 989f0952 | invalid | `crescu`, `ploutvou`, `poharďoval sa`, `v jemnom vetry` persist; one agreement improved. Review failed `structural_whitespace_loop`; candidate still defective, so no blind retry. |
| SL OpenHermes4 | 083ed11b | reject | Restores input sentence but translates it, losing English article classification; still `Zamenica`. Partial preservation fix, not faithful full task. |
| SL summary0 | 7ec26c95 | keep | Removes `popodroviš`, introduces user `prepričite spodnji besedilo` and answer `je tu živel ljudski skupina`. |
| BE grounded1 control | 481c03ae | keep | Regresses: `гад ... станоўства`, `пачатак узгаднення` instead of first mention; administrative dates remain correct. |
| LB grounded0 control | 2717f445 | keep | Discovery date/name,107km and0.25 faithfully retained; straightforward answer. |
| HR grounded0 control | 6d45c707 | reject | Four requested facts/qualifier preserved; rejected for intro `izvještenih`. Valid editorial concern, not factual failure; strictness contrasts with severe false accepts. |
| FA OpenHermes0 control | 9f35de55 | keep | Story/words retained, no new clear material issue in this reading. |

## Decision

Do not promote the suffix or its11 keeps to production. Gains are local and
inconsistent, native prose remains unreliable, and a previously good control
regresses. Keep script checks diagnostic, not a destructive filter. Prior
BE/LB/HU/SK/SL production holds remain warranted.

Next useful evidence would come from independent native editing/assessment or
a stronger teacher on fresh heldout tasks, not another generic same-model
self-check loop. Missing-input/output-type validators can catch narrow failures
but cannot certify morphology or meaning. No further calls scheduled.
