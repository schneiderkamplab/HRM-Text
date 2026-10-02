"""Materialize unadmitted QA candidates, excluding exact manually held hashes."""
import json
from pathlib import Path
import os
import tempfile
import time
from scripts import dfm13_repochat_qa_filtered as f

b=f.n.b
ROOT=f.n.ROOT/'filtered-candidates'


def build():
    summary_path=f.n.ROOT/'readiness/summary.json'
    summary=b.load(summary_path)
    holds_path=f.n.ROOT/'manual-claim-repairs/holds.json'
    holds=b.load(holds_path)['holds']
    held_hashes={h['trajectory_sha256'] for h in holds}
    held_answers={h['answer_sha256'] for h in holds}
    selected=[];excluded=[]
    for record in summary['records']:
        if b.file_sha(record['trajectory'])!=record['trajectory_sha256'] or b.file_sha(record['review'])!=record['review_sha256']:
            raise ValueError('readiness input drift')
        trajectory=b.load(record['trajectory'])
        answer=f.n.previous.audit.probe.package(trajectory['messages'])['final_answer'] if record['review_pass'] else None
        if not record['review_pass']:
            excluded.append({'id':record['task']['id'],'reason':'not_independent_review_pass'})
        elif record['trajectory_sha256'] in held_hashes or b.sha(answer.encode()) in held_answers:
            excluded.append({'id':record['task']['id'],'reason':'exact_manual_hash_hold'})
        else:
            selected.append({'id':record['task']['id'],'repository':record['task']['repository'],
                'question':record['task']['query'],'answer':answer,
                'answer_sha256':b.sha(answer.encode()),'trajectory':record['trajectory'],
                'trajectory_sha256':record['trajectory_sha256'],'review':record['review'],
                'review_sha256':record['review_sha256'],'status':'filtered_candidate_not_admitted',
                'admission':False})
    ROOT.mkdir(parents=True,exist_ok=True)
    manifest={'readiness_sha256':b.file_sha(summary_path),'holds_sha256':b.file_sha(holds_path),
        'implementation_sha256':b.file_sha(__file__),'candidate_count':len(selected),'excluded':excluded,
        'scope':'Original eligible74 only; excludes held hashes and non-passes. Does not incorporate correction drafts or derivative retry evidence packets.',
        'further_scale_allowed':False,'admission':False}
    if (ROOT/'manifest.json').exists():
        old=b.load(ROOT/'manifest.json')
        if any(old[k]!=v for k,v in manifest.items()):raise ValueError('candidate output already sealed with different inputs')
        if b.file_sha(ROOT/'candidates.jsonl')!=old['candidates_sha256']:raise ValueError('sealed candidates drift')
        return
    with tempfile.NamedTemporaryFile(mode='w',dir=ROOT,delete=False,encoding='utf-8') as stream:
        temporary=Path(stream.name)
        for row in selected:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,ROOT/'candidates.jsonl')
    manifest['candidates_sha256']=b.file_sha(ROOT/'candidates.jsonl')
    b.save(ROOT/'manifest.json',manifest)
    print({'filtered_candidates':len(selected),'excluded':len(excluded),'admission':False},flush=True)


if __name__=='__main__':
    deadline=time.monotonic()+10800
    while not (f.n.ROOT/'readiness/parent-assignment-ready.json').exists():
        if time.monotonic()>=deadline:raise TimeoutError('readiness unavailable')
        time.sleep(10)
    build()
