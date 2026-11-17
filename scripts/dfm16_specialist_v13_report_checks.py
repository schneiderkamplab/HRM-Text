"""Verify specialist reports and separate actual spend from inherited responses."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

from dfm12.io import file_hash, load, lock, rows
from scripts.dfm16_story_calibration import immutable, immutable_rows, metrics
from scripts.dfm16_specialist_audit_v13 import ROOT, BASE
from scripts.dfm16_validation_audit import whole_vote
from scripts.queue_dfm16_stories_qwen import audited_records


def finish(root=ROOT):
    for receipt in (root/'design.json',root/'receipt.json'):
        for path,digest in load(receipt)['pins'].items():
            if file_hash(Path(path))!=digest:raise ValueError(f'changed pinned evidence: {path}')
    inherited=load(root/'inherited-response-receipt.json')
    for path,digest in inherited['pins'].items():
        if file_hash(Path(path))!=digest:
            raise ValueError('inherited response changed')
    report=load(root/'report.json')
    reference=list(rows(root/'reference.jsonl'))
    identifiers={r['id'] for r in reference}
    scored={}
    for name in report['results']:
        records=list(rows(root/'scored'/f'{name}.jsonl'))
        if len(records)!=800 or {r['id'] for r in records}!=identifiers:
            raise ValueError('scored cohort incomplete or duplicated')
        measured=metrics(records)
        if any(report['results'][name][k]!=v for k,v in measured.items()):
            raise ValueError('reported metrics differ from scored records')
        scored[name]={r['id']:r for r in records}
    paired={}
    for label in ('bad','clear','borderline','unresolved'):
        paired[label]=dict(Counter(
            scored['raw_specialist_veto'][r['id']]['decision']+' -> '+scored['verified_defect_veto'][r['id']]['decision']
            for r in reference if r['label']==label))
    screen=load(root/'screen.json')
    verified={r['id']:v.get('review',{}).get('decision','unresolved')
              for r,v in audited_records(root/'verification')}
    roles=sorted({v['specialty'] for v in screen.values()})
    individual={}
    for role in roles:
        decisions={}
        for r in reference:
            if not r['deterministic_pass']:decisions[r['id']]='reject';continue
            s=screen[r['id']+'/'+role]
            decisions[r['id']]=('unresolved' if s['decision']=='unresolved' else
                whole_vote(verified.get(i,'unresolved') for i in s['verification_ids'])
                if s['verification_ids'] else 'accept')
        individual[role]=decisions
    unique={role:{label:sum(r['label']==label and r['deterministic_pass'] and
                    individual[role][r['id']]=='reject' and
                    all(individual[other][r['id']]=='accept' for other in roles if other!=role)
                    for r in reference) for label in ('bad','clear','borderline')}
            for role in roles}
    previous=BASE.parent/'staged-stories-odin-evidence-v9-20261029/postflight-receipt.json'
    start=load(previous)['aggregate_Odin_sends']
    with sqlite3.connect(f'file:{BASE / "odin-requests.sqlite"}?mode=ro',uri=True) as db:
        sends=[dict(id=i,sent=t,status=s,usage=json.loads(u) if u else {})
               for i,t,s,u in db.execute('SELECT id,sent,status,usage FROM sends WHERE id>? ORDER BY id',(start,))]
        times=[r[0] for r in db.execute('SELECT sent FROM sends ORDER BY sent')]
    left=0;peak=0
    for right,t in enumerate(times):
        while t-times[left]>=60:left+=1
        peak=max(peak,right-left+1)
    if peak>100:raise ValueError('aggregate rate exceeded')
    def charged(group):
        prompt=sum(r['usage'].get('prompt_tokens',0) for r in group)
        completion=sum(r['usage'].get('completion_tokens',0) for r in group)
        return dict(actual_sends=len(group),status_counts=dict(Counter(str(r['status']) for r in group)),
            prompt_tokens=prompt,completion_tokens=completion,estimated_DKK=(prompt*6.25+completion*25)/1e6)
    value=dict(verified_report=True,paired_raw_to_verified=paired,
        uniquely_rejected_examples_after_verification=unique,
        v11_v12_v13_actual_usage=charged(sends),
        v13_new_actual_usage=charged([r for r in sends if r['id']>inherited['ledger_before_v13']]),
        inherited_attempt_records=inherited['cached_attempts'],
        aggregate_rolling_minute_peak=peak,qualified=False,production_authorized=False,
        caveat='Historical token-price estimates; includes superseded v11/v12 calls and unused retries and all actual discovery/retry sends; unreported usage and manual costs excluded. Inherited responses are not billed twice.')
    immutable_rows(root/'actual-send-snapshot.jsonl',sends)
    immutable(root/'postflight-report.json',value)
    paths=[root/'postflight-report.json',root/'actual-send-snapshot.jsonl',root/'inherited-response-receipt.json',
           root/'receipt.json',previous,Path(__file__)]
    immutable(root/'postflight-receipt.json',dict(pins={str(p):file_hash(p) for p in paths}))
    return value


if __name__=='__main__':
    with lock(BASE/'.controller.lock'),lock(ROOT/'.controller.lock'):
        print(finish())
