"""Frozen CPU-only, distinct-task SearchArena readiness accounting."""
from collections import Counter
import json
from pathlib import Path
import sqlite3
from scripts import dfm13_search_postbatch_accounting as accounting

ROOT=Path('data/dfm13/search-final-inventory-20261001')
EXTRA=[Path('docs/reports')/name for name in (
    'dfm13_search_lastslots2_manual_assessment_20261001.json',
    'dfm13_search_targeted_cpu2_manual_assessment_20261001.json')]


def category(row):
    versions=row['versions']
    eligible=[v for v in versions if v['student_fit_verified'] and v['complete_final']
              and not v['exact_hold'] and not v['negative_same_content_reviews']]
    if any(v['manual_supported'] for v in eligible):return 'manual_supported'
    if any(v['automated_verdict']=='keep' for v in eligible):return 'automated_only'
    if any(v['exact_hold'] for v in versions):return 'held_no_eligible_keep'
    if any(v['automated_verdict']=='reject' for v in versions):return 'rejected_no_eligible_keep'
    return 'unresolved'


def main():
    if ROOT.exists():raise ValueError('new immutable root required')
    accounting.REPORTS += EXTRA
    accounting.SUPPORTED_ASSESSMENTS.update({
        'useful_scoped_limitation_prior_overclaims_resolved',
        'useful_jurisdiction_and_document_status_clarification'})
    # Cisco remains excluded pending explicit citation cleanup, despite useful
    # underlying retrieval. Its receipt is not a clean-answer approval.
    accounting.ROOT=ROOT/'lineage'
    accounting.main(inventory_only=True)
    inventory=accounting.read(accounting.ROOT/'inventory.json')
    tasks=[]
    for row in inventory['rows']:
        kind=category(row)
        tasks.append(dict(row,disposition=kind))
    counts=Counter(t['disposition'] for t in tasks)
    db=sqlite3.connect('file:'+str(accounting.base.CAMPAIGN/'cache.sqlite')+'?mode=ro',uri=True)
    budget=dict(db.execute('SELECT status,count(*) FROM searches GROUP BY status'))
    owners=db.execute('SELECT count(DISTINCT owner) FROM searches WHERE status="done"').fetchone()[0]
    cache_bytes=db.execute('SELECT sum(length(raw)) FROM searches WHERE status="done"').fetchone()[0]
    db.close()
    manual=[]
    for t in tasks:
        if t['disposition']!='manual_supported':continue
        candidates=[v for v in t['versions'] if v['manual_supported'] and v['student_fit_verified'] and
            not v['exact_hold'] and not v['negative_same_content_reviews']]
        refs=[r for r in inventory['supported_receipts'] if r['candidate_sha256'] in {v['candidate_sha256'] for v in candidates}]
        manual.append(dict(id=t['id'],candidates=candidates,assessments=refs))
    runs={}
    for name in ('search-parallel86-20261001','search-cached-recovery36-20261001','search-citation-repair6-20261001','search-followup4-20261001'):
        root=Path('data/dfm13')/name
        runs[name]=dict(runtime=accounting.read(root/'runtime.json'),finished=accounting.read(root/'finished.json'))
    summary=dict(original_tasks=len(tasks),distinct_tasks_with_candidates=sum(bool(t['versions']) for t in tasks),
        saved_candidate_versions=sum(len(t['versions']) for t in tasks),
        unique_training_contents=len({v['training_sha256'] for t in tasks for v in t['versions']}),
        exclusive_dispositions=dict(counts),
        manual_or_automated_union=counts['manual_supported']+counts['automated_only'],
        paid_reservations=sum(budget.values()),campaign_cap=200,cache_statuses=budget,
        completed_cached_unique_owners=owners,full_cached_response_bytes=cache_bytes,
        admitted_training_rows=0,human_certified_rows=0,
        scope='One original task counts once; manual support is exact-version agent assessment, includes partial/creative answers, not full task completion. Automated-only is not established usable.',
        recommendation='Do not bulk admit or scale. Review only source-supported, context-fit exact versions; retain all temporal/math/semantic holds. No further paid calls.')
    pins={str(p.resolve()):accounting.base.file_hash(p) for p in accounting.REPORTS+[Path(__file__),Path(accounting.__file__),accounting.ROOT/'inventory.json']}
    accounting.base.atomic(ROOT/'inventory.json',dict(summary=summary,tasks=tasks,manual_candidates=manual,
        manual_local_cleanup_pending_receipt=str(EXTRA[0]),runs=runs,pins=pins,admission_authorized=False))
    print(json.dumps(summary))


if __name__=='__main__':main()
