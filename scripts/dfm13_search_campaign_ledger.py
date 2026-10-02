"""Unique-sample lineage inventory and bounded retrieval needs; no admission."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from scripts import dfm13_search_calibration as base

BASE=Path('data/dfm13')
STAGES=['search-calibration-100-20261001-v9-cited','search-calibration-100-20261001-followup2',
        'search-reviewer-v3-20261001','search-review-error-retry-20261001',
        'search-review-loop-retry-20261001','search-targeted-repair-v4-20261001',
        'search-supplement9-20261001']
HOLDS={
 '032d2d0c':'CPU counterexample disproves 32-bit guarantee; minimum-base argument also invalid.',
 '51c2360a':'Answer anchored May 5, 2025 lists June and May 14 events as current; independent temporal hold.',
 '06cd049f':'Independent report identifies post-prompt polling used as current under historical date policy.',
 'a1f76a3a':'Supplemental answer again uses September 2026 prices for March 26, 2025 earlier-this-week question; exact historical dates absent in full returned cache.',
}
NEEDS={
 '07b395e8':('source_traceability','Confirm each name element using already cached linguistic source; remove unsupported Wikipedia link.','staropolskie imiona dwuczlonowe czlony przedrostki przyrostki'),
 '25bdd9ac':('task_and_source_support','Show only logo image URLs actually present in cached text; dates alone do not prove fabrication.','AI company logo image gallery company names'),
 '34a715dc':('source_traceability','Check full cached QEMU Windows/ARM64/UEFI instructions before any retrieval.','QEMU Windows ARM64 UEFI audio networking official documentation'),
 '42c53538':('source_traceability','Need actual OpenShift AI documentation supporting web-service deployment; not invented doc paths.','Red Hat OpenShift AI deploy web application service route documentation'),
 '4cac4d37':('citation_repair_not_retrieval','Clearly label invented battle; cite only sourced character capabilities. No new search needed for missing link alone.',None),
 '5235c2dc':('parser_not_retrieval','Bracketed URL adjacent to Japanese punctuation/prose; CPU boundary correction needed.',None),
 '56c21202':('model_identity_evidence','Need Qwen2 57B A14B Instruct comparisons, not Qwen2.5 or generic reputation.','Qwen2 57B A14B Instruct benchmark comparison Qwen2 official'),
 '63f2b7df':('citation_repair_not_retrieval','Cite cached LynxJS API details only where supported; do not invent QR scanning APIs.',None),
 '65dff936':('edition_specific_evidence','Exact 2006 DVD edition/back-cover specifications need edition-specific evidence, not generic film facts.','Over the Hedge 2006 DVD back cover disc technical specifications edition'),
 '6c535d11':('entity_specific_evidence','Exact HelpX host identity/contact must be explicitly public in matching host record.','"helpx.net/host/1147473FR"'),
 '7e250edd':('navigation_not_evidence','Lichess homepage is a destination, not automatically a supporting source. Cite observed comparison; do not charge search merely for navigation link.',None),
 '82071459':('citation_repair_not_retrieval','Example.com in code is illustrative. Add a source only if cached documentation actually supports requests/BeautifulSoup behavior.',None),
 'a1f76a3a':('historical_price_evidence','Need SBUX prices for week of original March 26, 2025 query, not September 2026 analysis.','SBUX historical stock price March 24 March 25 March 26 2025'),
 'b6dacbac':('task_completeness','Need accessible Russian MHD-mixing monographs/articles, not just ultrasound sources and search suggestions.','магнитогидродинамическое перемешивание монография статья полный текст'),
}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise ValueError('new snapshot required')
    samples=json.loads((BASE/STAGES[0]/'samples.json').read_text())
    rows={s['id']:dict(id=s['id'],history=[],selected=None,independent_hold=HOLDS.get(s['id'][:8])) for s in samples}
    jobs={};pins={}
    for name in STAGES:
        root=BASE/name
        if (root/'jobs.json').exists():
            jobs[name]={j['id']:j for j in json.loads((root/'jobs.json').read_text())}
        for path in sorted((root/'records').glob('*/outcome.json')):
            outcome=json.loads(path.read_text());key=path.parent.name
            if key not in rows:raise ValueError('unknown sample')
            entry=dict(stage=name,outcome=str(path),status=outcome['status'],verdict=outcome.get('verdict'))
            pins[str(path.resolve())]=base.file_hash(path)
            candidate=path.parent/'candidate.json'
            if not candidate.exists() and name in STAGES[2:5]:
                candidate=BASE/STAGES[1]/'records'/key/'candidate.json'
            if candidate.exists():
                data=json.loads(candidate.read_text())
                answer=data['messages'][-1].get('content','')
                sourcejob=jobs.get(name,{}).get(key) or jobs.get(STAGES[2],{}).get(key)
                if name not in STAGES[2:5] or (sourcejob and answer==sourcejob['answer']):
                    entry['candidate']=str(candidate);entry['candidate_sha256']=base.file_hash(candidate)
            rows[key]['history'].append(entry)
            selected=rows[key]['selected']
            if selected and entry.get('candidate_sha256')==selected.get('candidate_sha256') and entry.get('verdict') in ('reject','needs_verification'):
                rows[key]['selected']=None
            if entry.get('verdict')=='keep' and entry.get('candidate') and not rows[key]['independent_hold']:
                rows[key]['selected']=entry
    for row in rows.values():
        row['disposition']='independent_hold' if row['independent_hold'] else (
            'automated_keep_candidate_not_admitted' if row['selected'] else 'no_verified_candidate_selected')
    repairroot=BASE/'search-targeted-repair-v4-20261001';repairjobs=jobs[repairroot.name];needs=[]
    for path in sorted((repairroot/'records').glob('*/outcome.json')):
        outcome=json.loads(path.read_text())
        if outcome.get('verdict')=='keep':continue
        key=path.parent.name;kind,requirement,query=NEEDS[key[:8]]
        needs.append(dict(id=key,kind=kind,requirement=requirement,proposed_query=query,
            query_not_authorized_or_executed_by_this_manifest=True,original_timestamp=repairjobs[key]['sample']['original_timestamp'],
            cached_sources=list(repairjobs[key]['pages']),prior_outcome=str(path)))
    db=sqlite3.connect('file:'+str(base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    cache=dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    owners=db.execute('SELECT count(DISTINCT owner) FROM searches WHERE status="done"').fetchone()[0]
    db.close()
    reserved=sum(cache.values())
    report=dict(at=base.now(),unique_samples=len(rows),counts=dict(Counter(r['disposition'] for r in rows.values())),
        rows=list(rows.values()),retrieval_needs=needs,retrieval_need_counts=dict(Counter(n['kind'] for n in needs)),
        paid_budget=dict(ceiling=100,reservations=reserved,remaining=max(0,100-reserved),successful_cached=cache.get('done',0),
            distinct_successful_owners=owners,
            maximum_distinct_successful_owners_if_remaining_are_new=owners+max(0,100-reserved),
            additional_reservations_since_initial87=max(0,reserved-87)),
        production_ready=False,admission_authorized=False,
        note='Selection is latest eligible automated keep lineage with an unchanged matching candidate, NOT independent factual certification. Independent holds override automatic keeps.',pins=pins)
    base.atomic(args.output/'ledger.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','retrieval_needs','pins')}))


if __name__=='__main__':main()
