"""Bind manually written case observations to the frozen records."""
import json
import re
from pathlib import Path
from dfm12.io import digest, file_hash, write_json

ROOT = Path(__file__).resolve().parent
NOTES = {
0: ('limited', 'Shipping routes and historical fleet list, not category-only. Gap spans destinations, a heading and ship names; exact source recovery but not uniquely inferable from context. Source typo francsokoitalijanska remains. Do not reject merely for useful lists.'),
1: ('defect', 'Target announces expressions for volume and surface area, but neither expression is present before the circumradius sentence. Source extraction loses substantive mathematical content; also visible source typos. Prefer intact prose window or restore source math before regeneration.'),
2: ('minor', 'Continuation joins correctly at rimske/mitologije. Target retains malformed source wiki-link [gostota]] and spacing velikost16. Local markup cleanup is warranted; no claim to independently verify astronomy.'),
3: ('limited', 'Gap joins coherent prose about a fictional curse and sacrifice. Localized fictional names are not language contamination. Broad fictional rule is not independently verified; no structural defect found.'),
4: ('minor', 'Substantive castle history, synthetic damage restored exactly, including corrupted Roman numeral Ulrik I. to source II. Target retains source agreement problems such as se je priselili and se je odpovedali. Native copy-edit review, not a transformation mismatch.'),
5: ('minor', 'Village demographic continuation joins correctly. Input contains empty izvirno parentheses inherited from source; otherwise useful prose and figures. No unsupported demographic accuracy certification.'),
6: ('limited', 'Medical continuation joins at pa/se and preserves source. Reference/footer clutter, but meaningful prose remains. Medical claims not independently validated; this is not medical advice or factual certification.'),
7: ('limited', 'Literary biography gap crosses prose into awards list. Target is faithful; specific pseudonyms and dates cannot be uniquely inferred. Lists contain meaningful content, not grounds for blanket rejection.'),
8: ('limited', 'Gap contains final band name, section heading and sentence prefix; exact reconstruction. The surrounding sweeping claim about original groups and racism deserves source review but is not established false here.'),
9: ('minor', 'Denoising restores readable historical discussion while preserving uncertainty in the source. Source grammatical problems remain (Dolgo so domnevati; svojo garnizon); reject no population on this non-native judgment.'),
10: ('no_clear_defect', 'Useful coherent upselling/cross-selling/down-selling examples. Restores deletions and casing without changing source claims. Trailing categories do not make this metadata-only.'),
11: ('minor', 'Substantive castle history and architectural paragraph. Exact restoration, but source phrase Leta 1564 gospostvo pridobil lacks a finite auxiliary. Source copy-edit concern, not fabricated target.'),
12: ('task_scope_concern', 'One narrative paragraph plus meaningful route and information-point lists, standalone headings and footer. Not a clean multiple-prose-paragraph task; list contents remain useful. Do not equate with furniture-only or automatically exclude.'),
13: ('limited', 'Two meaningful football biography paragraphs plus empty references/external-link headings and categories. Club career then national-team career is plausible but not uniquely forced. Preserve useful prose; trim footer only with derived provenance.'),
14: ('defect', 'Reordering includes raw table opening and unmatched closing div/table markup as separate numbered blocks. Several statistics headings/legends have no tables. High-confidence extraction damage, despite exact reconstruction and judge acceptance.'),
15: ('limited', 'Two substantive locomotive paragraphs with a coherent description/history relation. Empty technical-data heading and footer clutter, but not a one-prose-paragraph example. No independent verification of historical manufacturer dispute.'),
16: ('minor', 'Bibliography is meaningful, not metadata-only. Denoising restores names and titles; English In 2002 remains in otherwise Albanian annotation. Foreign book titles themselves are legitimate.'),
17: ('limited', 'Monument continuation attaches correctly. Source description of headwear/bird may merit fact checking; not verified from local evidence, so not counted as a factual defect. Punctuation and grammar are rough.'),
18: ('defect', 'History prose contains incoherent fragments marte marte, etj pche oktal and razigravat; broad malformed syntax, not isolated spelling. Exact copying cannot support judge language_quality=5. Review this exact source window before use.'),
19: ('task_scope_concern', 'No prose paragraphs in selected window: exhibitions/awards lists, gallery/book-cover labels, links and categories. Source document has biography prose before the selected window. Useful lists, but exact ordering of independent sections is not supplied by discourse; propose prose-window reselection, not broad list removal.'),
20: ('no_clear_defect', 'Coherent scientist biography with continuous sentence join, career chronology and bibliography. Minor language roughness; no clear structural or source-fidelity defect.'),
21: ('minor', 'Mostly French/English book titles, legitimately multilingual bibliography. Cyrillic annotation со коавтори is not a title and remains unlocalized. Birth-year category 1875 is inherited; no independently sourced factual correction asserted here.'),
22: ('no_clear_defect', 'Two coherent explanatory paragraphs on rockism. Synthetic typos restored. Evaluative phrasing comes from source, not an added assistant judgment.'),
23: ('limited', 'Door-inscription introduction and right/left quotations form a coherent cluster, followed by architectural prose. Swapping right/left descriptions remains coherent, so exact source order is not unique. Numeric parenthesis appears incomplete in source.'),
24: ('limited', 'Chronological birth/death list is meaningful denoising content; damage restored. Dates are not independently checked. Pa data section has months but no days, not necessarily a contradiction.'),
25: ('limited', 'Substantial multi-paragraph relations/history content and dates provide ordering cues. Minority sections could swap without incoherence; last-census wording is dated and 0.1% e 100% awkward, not a replay bug or proven numerical error here.'),
26: ('minor', 'Continuous football-history narrative and exact prefix/suffix join. Multiple inherited Albanian grammar/spelling problems (e.g. lëzivi, u mpshtën); understandable but native review desirable, no invented sports fact corrections.'),
27: ('limited', 'Substantive historical narrative and quotation; span joins around nga fati ... shumë të/kënaqshme. Long specific quotation not uniquely inferable; source wording rough. No external historical verification performed.'),
28: ('defect', 'After one remaining economic sentence, target is dominated by empty headings, unpopulated ski-centre/peak introductions, links and categories. High-confidence incomplete extracted structure, not solely a grammar judgment. Prefer earlier complete prose window.'),
29: ('minor', 'Gap reconstructs scoring list exactly. Target begins baruesit (apparent source typo for garuesit); input has empty race/driver sections. Useful scoring content remains; not a confirmed arithmetic error.'),
30: ('limited', 'Long coherent account of schools; gap restores a date, school names and sentence prefix. Exact history recovery verified; school dates/attributions not independently checked. No structural defect found.'),
31: ('limited', 'Gap reconstructs bacterial-envelope discussion with correct textual join. Minor source spelling Kllasifikimi. Biomedical terminology and antibiotic claim not independently validated, not certified factually correct.'),
}


def main():
    assert not (ROOT / 'review.json').exists()
    evidence = json.loads((ROOT / 'evidence.json').read_text())
    assert set(NOTES) == {x['case'] for x in evidence}
    reviewed = []
    for item in evidence:
        row = item['record']; task = row['task']
        original = row['audit_context']['original']
        body = row['messages'][0]['content'].split('\n\n', 1)[1]
        target = row['messages'][-1]['content']
        checks = dict(item['checks'])
        if task == 'denoising':
            checks.update(target_exact=target == original, corruption_changed=body != target)
        elif task == 'prefix-continuation':
            checks.update(prefix_exact=original.startswith(body), suffix_exact=original[len(body):].strip() == target)
        elif task == 'span-filling':
            left, right = body.split(' <GAP> ')
            checks.update(gap_unique=body.count('<GAP>') == 1,
                reconstruction_exact=(left+' '+target+' '+right).split() == original.split())
        else:
            shuffled = re.split(r'\n\n\[\d+\] ', body)
            shuffled[0] = re.sub(r'^\[1\] ', '', shuffled[0])
            parts = original.split('\n\n')
            checks.update(target_exact=target == original, blocks_preserved=sorted(parts)==sorted(shuffled),
                changed_order=parts != shuffled)
        assert all(checks.values()), (item['case'], checks)
        category, note = NOTES[item['case']]
        reviewed.append(dict(case=item['case'], id=item['id'], language=item['language'], task=task,
            record_sha256=digest(row), messages_sha256=digest(row['messages']),
            source_path=item['source_path'], provenance=row['provenance'],
            observation_category=category, observation=note, mechanical_checks=checks))
    write_json(ROOT / 'review.json', reviewed)
    lines = ['# Per-case observations', '', 'Categories are observations, not population quality scores or automatic exclusion decisions.', '']
    for r in reviewed:
        lines.extend([f"## Case {r['case']}: {r['language']} / {r['task']}",
            f"ID: `{r['id']}`", f"Record SHA256: `{r['record_sha256']}`",
            f"**{r['observation_category']}**: {r['observation']}", ''])
    (ROOT / 'case-review.md').write_text('\n\n'.join(lines))
    write_json(ROOT / 'receipt.json', dict(reviewed_rows=len(reviewed),
        languages={'sl':16, 'sq':16, 'sr':0}, all_mechanical_checks_pass=True,
        sr_availability='Empty release ledger; additional first 256 candidate audit jobs all pending (65 denoising,65 prefix,65 span,61 reorder); not a census of the live audit queue',
        pins={p.name:file_hash(p) for p in (ROOT/'evidence.json', ROOT/'snapshot.json', ROOT/'review.json', ROOT/'case-review.md', ROOT/'extract.py', ROOT/'finalize.py')}))


if __name__ == '__main__':
    main()
