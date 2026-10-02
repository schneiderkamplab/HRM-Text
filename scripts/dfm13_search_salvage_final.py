"""Close the 32-task salvage pool without modifying historical dispositions."""
from collections import Counter
from pathlib import Path
from scripts import dfm13_search_salvage32 as run
from scripts import dfm13_search_salvage_error4 as repair

ROOT = Path('data/dfm13/search-salvage-final-20261001')
FOUR = {
 '99fe14a8': 'held_final: formatting repaired but broad driver/software-support guarantees and unresolved chronology remain unsupported; no further retry',
 '0cfb74ac': 'held_final: URL repaired but retrospective season synthesis lacks original March-27 applicability; no further retry',
 '31dbdb34': 'deferred_final: bounded retry again lacks citations and mixes exercises with asserted benefits; no further retry',
 'b6dacbac': 'held_final: user requires fully accessible Russian scholarly sources without registration. Cached excerpt access does not establish that requirement; one-line CyberLeninka and generator-use excerpts do not support claimed source coverage. Answer also strengthens without significant wear to absence of wear. No further retry',
}
PARTIAL = {'e19e0b36','d331c427','56c21202','deb701de'}
CREATIVE = {'118fd78c','81484873'}


def main():
    if ROOT.exists(): raise ValueError('immutable final receipt exists')
    if run.prior.read(repair.ROOT/'runtime.json')['status']!='terminal': raise ValueError('recovery incomplete')
    inventory=run.prior.read(run.INVENTORY)
    reviews_path=Path('docs/reports/dfm13_search_salvage10_independent_review_20261001.json')
    reviews={r['id']:r for r in run.prior.read(reviews_path)['rows']}
    rows=[]
    for task in inventory['tasks']:
        if task['disposition'] not in ('manual_supported','automated_only'):continue
        prefix=task['id'][:8]
        if task['disposition']=='manual_supported':
            lane='retained_partial' if prefix in PARTIAL else 'retained_creative' if prefix in CREATIVE else 'retained_supported'
            candidates=[v for v in task['versions'] if v['manual_supported'] and v['student_fit_verified'] and v['complete_final'] and not v['exact_hold'] and not v['negative_same_content_reviews']]
            rows.append(dict(id=task['id'],lane=lane,existing_manual_versions=candidates,unchanged=True))
            continue
        folder=(repair.ROOT if prefix in FOUR else run.ROOT)/'records'/task['id']
        candidate=folder/'candidate.json'
        outcome=run.prior.read(folder/'outcome.json')
        if prefix in FOUR:
            lane='held_or_deferred_final';reason=FOUR[prefix]
        elif task['id'] in reviews:
            review=reviews[task['id']]
            lane={'supported_scoped':'new_supported_scoped','partial_only':'new_partial','hold':'held_or_deferred_final'}[review['assessment']]
            reason=review['reason']
        else:
            if outcome.get('verdict')!='reject':raise ValueError('unreviewed unexpected outcome')
            lane='rejected_final';reason='Automated rejection retained; no additional repair authorized in this bounded salvage.'
        rows.append(dict(id=task['id'],lane=lane,reason=reason,candidate=str(candidate),candidate_sha256=run.base.file_hash(candidate),
            latest_automated_outcome=outcome,further_retries=0,existing_holds_preserved=True))
    if len(rows)!=32:raise ValueError('expected distinct 32-task pool')
    counts=dict(Counter(r['lane'] for r in rows))
    run.base.atomic(ROOT/'inventory.json',dict(rows=rows,counts=counts,total_distinct_tasks=32,provider_calls=0,
        admitted_training_rows=0,human_certified_rows=0,active_search_clients=0,
        policy='Final dispositions for this salvage branch only. No prior hold is cleared. Supported means exact-version CPU agent assessment, not training admission.',
        source_pins={str(p):run.base.file_hash(p) for p in (run.INVENTORY,reviews_path,Path(__file__),run.ROOT/'jobs.json',repair.ROOT/'jobs.json')}))
    print(counts)


if __name__=='__main__':main()
