"""Hash-bind independent Serbian observations; no admission side effects."""
from pathlib import Path
import re
from dfm12.io import digest, file_hash, load, write_json

NOTES = {
32: ('source_window_defect', 'Gregor Mendel: selected window is English external-link titles plus Serbian categories, without biography prose. Denoising restores English titles rather than meaningful Serbian text. Exact source replay, but poor native-window selection; source has biography prose earlier. No blanket rejection of multilingual titles proposed.'),
33: ('minor', 'Braunlage: coherent municipality paragraph; figures are internally consistent (4866/21.7 approximately 224). Exact denoising with source conversion wrappers and footer retained. Ijekavian forms are legitimate Serbian, not evidence of wrong language.'),
34: ('minor', 'Norten-Hardenberg: meaningful geography/demography paragraph; 8343/54.1 approximately 154. Empty cooperation heading and conversion wrappers are source artifacts. No broad exclusion for that minor clutter.'),
35: ('limited', 'Tokyo tournament: meaningful participant/result lists and exact denoising; empty seed heading and isolated English def. remain. Lists should not be equated with category-only windows. Sporting facts not independently verified.'),
36: ('source_window_defect', 'Chinese constellations: four shuffled blocks are an external-links heading, English/Chinese link titles, another link title and a category. Zero prose paragraphs; no native astronomical exposition. Earlier source has Serbian prose. Propose exact-row review and paragraph-aware reselection, not general title/script deletion.'),
37: ('source_window_defect', 'Otto Sep: only one substantive commemorative paragraph, an empty references heading and category block. This is footer placement, not multiple meaningful paragraph reordering. Source biography has earlier prose. Mixed aprila script is secondary and not itself a reason for exclusion.'),
38: ('limited', 'Korilje: substantial geography/history and genealogy content, not footer-only. Numbered units include meaningful family entries; some independent entries admit alternate orders. Source has empty parentheses, typo and blank population/references headings. No external verification of genealogy or geopolitical framing.'),
39: ('minor', '1315 Bronislawa: multiple substantive asteroid description/orbit/discovery paragraphs. Exact source order and block preservation; wiki conversion wrappers survive. Orbital period/distance figures internally plausible but not independently verified.'),
40: ('limited', 'IC 4342: prefix contains native astronomical description; continuation completes identifiers then bibliography/footer. Task join is exact, even across conversion markup. Footer-heavy target is weaker than prose continuation but not certified metadata-only input. Ijekavian vocabulary is valid Serbian.'),
41: ('minor', 'Mixdorf: completes a demographic sentence then external links; 972/13 approximately 75 is consistent. Empty cooperation section and conversion wrappers remain; no strong source-fidelity defect.'),
42: ('minor', 'Natasa Lukovic: coherent sports biography continuation with multiple substantive paragraphs. Source typos in award/recognition/representative words persist. Native copy-edit concern, no independent factual verification.'),
43: ('no_clear_defect', 'Gunter Netzer: coherent club/national career continuation and structured trophies. Source sentence joins correctly; chronological content and meaningful lists. No clear task or structural defect found.'),
44: ('limited', 'Gliding/flying animals: coherent substantive exposition, gap crosses meaningful species entries and reconstructs precisely. Taxonomic and quantitative assertions are source claims, not independently verified. No structural mismatch.'),
45: ('source_extraction_defect', 'Zero Dark Thirty: user retains raw wiki-table row delimiters |-, || and |}, plus empty plot heading in target and empty original-title parentheses. Gap is ONE contiguous span; judge incorrectly describes two gaps. Recommend clean source window/representation, not invented plot or cast details.'),
46: ('limited', 'Hermitage: meaningful prose across satellite-museum sections. Literal satellite rendering in accommodation phrase is awkward; dates/opened-versus-planned claims not independently verified. Gap reconstruction exact; no unsupported factual rejection.'),
47: ('source_window_defect', 'Donji Junuzovici: window begins with five empty section headings, then bibliography and categories. Gap asks for a citation fragment, with no settlement prose; opening source paragraph with settlement facts was omitted. Prefer that meaningful prose window; do not fabricate missing geography/history sections.'),
}


def main():
    root=Path(__file__).resolve().parent/'sr-followup'
    assert not (root/'review.json').exists()
    evidence=load(root/'evidence.json'); review=[]
    assert {x['case'] for x in evidence}==set(NOTES)
    for item in evidence:
        row=item['record']; original=row['audit_context']['original']
        body=row['messages'][0]['content'].split('\n\n',1)[1]; target=row['messages'][-1]['content']
        task=row['task']
        if task=='denoising': assert target==original and body!=target
        elif task=='prefix-continuation': assert original.startswith(body) and original[len(body):].strip()==target
        elif task=='span-filling':
            left,right=body.split(' <GAP> '); assert body.count('<GAP>')==1
            assert (left+' '+target+' '+right).split()==original.split()
        else:
            blocks=re.split(r'\n\n\[\d+\] ',body);blocks[0]=re.sub(r'^\[1\] ','',blocks[0])
            assert target==original and sorted(blocks)==sorted(original.split('\n\n')) and blocks!=original.split('\n\n')
        category,note=NOTES[item['case']]
        review.append(dict(case=item['case'],id=item['id'],task=task,record_sha256=digest(row),
            messages_sha256=digest(row['messages']),provenance=row['provenance'],
            observation_category=category,observation=note,source_replay_exact=True,mechanical_checks_pass=True))
    write_json(root/'review.json',review)
    lines=['# Serbian accepted-transform follow-up (2026-10-03)',
        'Read-only independent review of all 16 frozen accepted rows, four per family. This completes 48 examples across SL/SQ/SR. All source and transformation replays pass. No new exclusion, hold or source modification is authorized/applied.',
        'Five rows have clear source-window/extraction or paragraph-task defects (32,36,37,45,47); these are exact-row observations, not a population rate. All full inputs/targets and source documents are preserved beside this report. Native-language certainty is limited; legitimate Ijekavian Serbian and meaningful lists are not rejected. Other factual claims are unverified unless explicitly checked internally.',
        'Selection: first four accepted IDs lexicographically per family, from one read-only release-ledger transaction. Snapshot: 197285 accepted, 28 audit_retry_pending, 34429 rejected. Accepted status/model review captured, not inferred from pending candidate metadata.',
        'Narrow recommendation: inspect these five exact windows for potential replacement/exclusion only under separate authorization. Prefer existing native prose before footer-only windows; require multiple substantive prose units for paragraph reordering; repair extraction without inventing missing content. No Serbian regex or population filter proposed.']
    for r in review:
        lines += [f"## Case {r['case']} / {r['task']}",f"ID: `{r['id']}`",f"Record SHA256: `{r['record_sha256']}`",r['observation']]
    (root/'report.md').write_text('\n\n'.join(lines)+'\n')
    write_json(root/'receipt.json',dict(rows_reviewed=16,source_replay_exact=16,mechanical_checks_pass=16,
        authorized_mutations=0,defect_cases=[32,36,37,45,47],population_inference=False,
        pins={p.name:file_hash(p) for p in (root/'evidence.json',root/'snapshot.json',root/'review.json',root/'report.md')}))


if __name__ == '__main__': main()
