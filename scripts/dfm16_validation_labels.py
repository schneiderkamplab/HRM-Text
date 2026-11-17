"""Blinded whole-conversation labeling; model votes are never label inputs."""
import argparse
from pathlib import Path
from dfm12.io import rows,load,file_hash,lock
from scripts.dfm16_story_calibration import immutable,immutable_rows
from scripts.dfm16_staged_validation_campaign import ROOT
from scripts.dfm16_staged_validation import verify_freeze

def evidence(root,language):
    c=root/language/'validation';p={r['id']:r for r in rows(c/'blind-packet.jsonl')}
    return c,[(r,p[r['id']]) for r in rows(c/'provenance-private.jsonl')]

def record(root,language,annotations):
    verify_freeze(root,language);c,items=evidence(root,language)
    by_index={r['index']:(r,p) for r,p in items}
    for a in annotations:
        r,p=by_index[a['index']]
        if p['status']!='generated':raise ValueError('semantic labels require complete generation')
        if a['label'] not in ('clear','bad','borderline'):raise ValueError('invalid semantic label')
        if not a.get('note'):raise ValueError('manual note required')
        result=dict(id=p['id'],index=r['index'],first_label=a['label'] if p['first_attempt_contract_clear'] else 'bad',
            final_label=a['label'],note=a['note'],category=a.get('category','none'),reviewer='assistant-manual',
            provisional=True,blind_to_judge_votes=True,review_basis='semantic complete-conversation review',
            packet_sha256=file_hash(c/'blind-packet.jsonl'))
        immutable(c/'manual-assessments'/f'{r["index"]:04d}.json',result)

def seal(root,language):
    verify_freeze(root,language);c,items=evidence(root,language);labels=[]
    if any((c/p).exists() for p in ['votes.jsonl','decisions.jsonl']):raise ValueError('votes already exposed')
    for r,p in items:
        if p['status']=='generated':d=load(c/'manual-assessments'/f'{r["index"]:04d}.json')
        else:
            label='unresolved' if p['status']=='source_rejected' else 'bad' if p['status']=='deterministic_failure' else 'unresolved'
            d=dict(id=p['id'],index=r['index'],first_label=label,final_label=label,
                note=p.get('source_review',{}).get('reason','Saved objective stage/contract failure; semantic completeness not certified.'),
                reviewer='assistant-manual',provisional=True,blind_to_judge_votes=True,
                review_basis='source intake evidence' if p['status']=='source_rejected' else 'deterministic evidence only')
        labels.append(d)
    if len(labels)!=800:raise ValueError('all 800 required')
    immutable_rows(c/'manual-labels.jsonl',labels)
    immutable(c/'label-receipt.json',dict(packet_sha256=file_hash(c/'blind-packet.jsonl'),labels_sha256=file_hash(c/'manual-labels.jsonl'),reference='provisional assistant-manual',judge_votes_exposed=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['show','record','seal']);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--language',default='en');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=20);p.add_argument('--annotations',type=Path)
    a=p.parse_args()
    if a.action=='show':
        c,items=evidence(a.root,a.language)
        for r,v in items:
            if not a.start<=r['index']<a.end or v['status']!='generated':continue
            print('\n###',r['index'],r['task'],'first_contract',v['first_attempt_contract_clear'])
            for m in v['messages']:print(m['role']+':',m['content'])
    else:
        with lock(a.root/'.controller.lock'):
            if a.action=='record':record(a.root,a.language,load(a.annotations))
            else:seal(a.root,a.language)
