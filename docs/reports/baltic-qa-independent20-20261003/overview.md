# Independent Baltic QA Content Check

Date: 2026-10-03. Scope: 20 complete published conversations, 10 Lithuanian and
10 Latvian; each language has five accepted originals and five accepted repairs.
All question/answer turns and available upstream rows were read. No generation,
judge calls, registry/eligibility changes, publication changes or worker actions.

## Disposition

**The concern is confirmed outside P3. Do not treat current accepted/re-audit
labels as sufficient semantic evidence.** LT repairs introduce wrong referents,
lost geographic scope and broken Lithuanian. LV has both introduced repair
claims and inherited errors left in multi-turn history after a partial repair.
Recommended next action is an eligibility-owner decision on these QA components,
followed by source-constrained checks, not another unconstrained assistant rewrite.
This report itself does not change the existing global hold or source eligibility.

| Language / stratum | Material defect | Uncertain hold recommended | Minor/uncertain detail | No material issue observed |
| --- | ---: | ---: | ---: | ---: |
| LT original, 5 | 0 | 0 | 1 | 4 |
| LT repaired, 5 | 3 | 0 | 0 | 2 |
| LV original, 5 | 3 | 0 | 2 | 0 |
| LV repaired, 5 | 3 | 2 | 0 | 0 |
| Total, 20 | 9 | 2 | 3 | 6 |

These are **sample counts, not corpus error rates**. Repairs are deliberately
oversampled: five of ten per language versus 308/12,895 LT and 5,261/105,971 LV
published rows. No-material-issue-observed does NOT mean independently proven
correct; many obscure historical details lack independent reference text.
Two uncertain holds are NOT counted as proven hallucinations.

## Strongest Evidence

- LT case 7: source Trakai is a village 4 km east of Švenčionys. Repair substitutes
  the Galvė-lake town and 110–120 km. This is a source-referent regression, even
  though the bare question contains a potentially ambiguous place name.
- LT case 6: repair introduces `važkas`, `hempo`, `bebrai kailius`, `grūdos` and
  other malformed terms. Re-audit praises natural Lithuanian and quotes the
  correctly spelled `vaškas`, which is not what the actual answer says.
- LT case 9: repair drops the Lithuanian extent of historical Žiemgala and adds
  an unsupported city/river-bounds account. [VLE](https://www.vle.lt/straipsnis/ziemgala-1/)
  independently documents the historical Lithuanian portion.
- LV case 18: repair invents a confident career account including `Sassuolo`;
  re-audit explicitly endorses it. Contemporary [transfer reporting](https://www.ansa.it/amp/sito/notizie/sport/calcio/2023/07/15/cagliari-ufficiale-lacquisto-di-jankto-dal-getafe_9833b1a3-a613-4c5b-ae8c-3e39656ee2fe.html)
  identifies Udinese/Sampdoria/Getafe/Sparta, consistent with a mistaken club-name
  substitution rather than a supported repair. Current club status is not scored
  against 2026; the corpus has a historical snapshot.
- LV case 13: `2. līga` is called the second tier. The [Latvian Football Federation](https://lff.lv/zinas/?cid=52)
  identifies it as the third tier; its [2023 competition description](https://lff.lv/zinas/14752/onl/)
  also places 2. līga below the Nākotnes līga.
- LV case 19: absent-document opening, malformed medical terminology and incomplete
  rescue-safety wording survive a useful partial repair. [NHS guidance](https://www.nhs.uk/conditions/carbon-monoxide-poisoning/)
  emphasizes leaving the affected site and not returning until advice. The good
  removal of the original tea/coffee/smelling-spirit advice does not validate the
  entire conversation.

Other reference checks: [NOAA-hosted algae reproduction material](https://repository.library.noaa.gov/view/noaa/38228/noaa_38228_DS1.pdf)
supports sexual as well as asexual reproduction (case 11).
[Auru municipality](https://www.dobele.lv/lv/auru-pagasts),
[Dobele geography](https://www.dobele.lv/lv/dobeles-pilseta) and the
[Zemgale planning-region report](https://www.zemgale.lv/lv/media/142/download?attachment=)
support the region check for case 16. These bounded checks do not establish all
claims in the sampled biographies, geography answers or histories.

## Sampling and Binding

Within each language and quality stratum, sort **original quality-ledger IDs**
and choose ordinals `floor((N-1)*i/4)` for `i=0..4`. Then resolve the actual
published candidate IDs, including repaired IDs. This is deterministic spread,
not random sampling or post-hoc cherry-picking. The sample was fixed before reading.

`evidence.json` preserves full published records and exact local upstream rows,
upstream file SHA/revision/row, original ID, published candidate ID, canonical
record SHA and complete published-file SHA. SHA256:
`18e4c1cbc65ab078c96874210979439650db7a11bf6432abf7a48dcca1591d04`.
`findings.json` records the manual case dispositions. `review.json` joins each
disposition with its exact record binding; `receipt.json` hashes these artifacts.
The appendix uses zero-based message indices and zero-based case numbers.

Local upstream LT rows contain only question/answer; LV rows contain only
messages. Neither includes the originating Wikipedia article. Thus equality
to upstream demonstrates preservation, not factual truth. Added repair claims
without source support are distinguished from confirmed false facts. All supplied
turns were read, not only final targets; original source files were hash-checked.

## Training Exposure

Both packages declare final-assistant-only supervision. All LT material defects
are in the final target. LV case 12's broken explanation and case 19's rescue
answer are final targets. Several other LV material defects are in earlier
assistant history, not directly supervised targets; those errors still enter
the final example's prompt. A clean final one-line answer does not make that
history clean. No claim that all 9 materially defective conversations train
every defective assistant turn with loss.

All 20 published audit records assign keep=true and 5/5/5. The content evidence
contradicts those blanket endorsements. Case 17's re-audit additionally calls
Humašaha “Mihrimah Sultan”; this is a judge referent error, not a claim that the
candidate itself says Mihrimah. No proposed replacement answers are auto-admitted.

## Full Case Appendix

