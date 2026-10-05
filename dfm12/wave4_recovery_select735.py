"""Select a bounded735K union from drained accepts and sealed CPU recovery."""
import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import time

from .io import digest,file_hash,load,lock,write_json
from .wave4_topup_policy import plan


def readonly(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db


def check_selected(row,job,owner):
    proof=json.loads(row['receipt'])
    if (not row['eligible'] or job is None or owner is None or owner[0]!=row['id']
            or job['status']!='review_invalid_output'
            or job['fingerprint']!=row['fingerprint']
            or digest(json.loads(job['outcome_json']))!=proof['original_outcome_sha256']
            or digest(json.loads(job['spec_json']))!=proof['spec_sha256']
            or proof['id']!=row['id'] or proof['fingerprint']!=row['fingerprint']
            or proof['raw_decision']!={'verdict':'keep','issues':[],'reason':''}
            or proof['deterministic_checks'] or proof['fabricated_rationale'] is not False
            or proof['rendered_training_tokens']>4096):
        raise ValueError('Selected recovery proof/current ledger mismatch: '+row['id'])
    candidate=proof['candidate_path']
    if candidate not in proof['pins']:
        raise ValueError('Candidate hash absent')
    return proof,proof['pins'][candidate]


def select(bundle,recovery,output):
    bundle,recovery,output=map(lambda p:Path(p).resolve(),(bundle,recovery,output))
    output.mkdir(parents=True,exist_ok=False)
    with lock(output/'selection.lock'):
        prepared=load(recovery/'prepared.json');initial=load(recovery/'initial.json')
        if initial['bundle']!=str(bundle) or file_hash(recovery/'initial.json')!=prepared['initial_sha256']:
            raise ValueError('Recovery binding mismatch')
        if file_hash(recovery/'report.json')!=prepared['report_sha256']:
            raise ValueError('Recovery report drift')
        if file_hash(recovery/'partition-plan.json')!=prepared['partition_plan_sha256']:
            raise ValueError('Partition plan drift')
        pins={**initial['pins'],**prepared['result_pins']}
        for path,sha in pins.items():
            if file_hash(path)!=sha:
                raise ValueError('Recovery pin drift: '+path)
        write_json(output/'progress.json',dict(phase='waiting_drain',recovery_pins_verified=True))
        deadline=time.monotonic()+1800
        while True:
            try:
                with ExitStack() as stack:
                    stack.enter_context(lock(bundle/'supervisor.lock'))
                    for i in range(8):
                        stack.enter_context(lock(bundle/f'shard-{i}'/'controller.lock'))
                    terminal=load(bundle/'terminal.json')
                    if terminal.get('active')!=0 or terminal.get('runnable_pass_success') is not True:
                        raise ValueError('Require successful drained terminal')
                    return selected_locked(bundle,recovery,output,prepared,stack)
            except BlockingIOError:
                if time.monotonic()>deadline:
                    raise TimeoutError('Campaign did not drain')
                time.sleep(5)


def selected_locked(bundle,recovery,output,prepared,stack):
    jobs=[];results=[];groups=[];eligible={}
    for i in range(8):
        db=stack.enter_context(readonly(bundle/f'shard-{i}'/'jobs.sqlite'))
        result=stack.enter_context(readonly(recovery/f'shard-{i}.sqlite'))
        if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
            raise ValueError('Running rows remain')
        rows=[dict(r,shard=i) for r in db.execute('SELECT * FROM groups')]
        groups.extend(rows);jobs.append(db);results.append(result)
        for r in result.execute('SELECT language,family,count(*) AS n FROM results WHERE eligible=1 GROUP BY language,family'):
            eligible[(r['language'],r['family'])]=r['n']
    quotas=plan(groups,eligible)
    registry=stack.enter_context(readonly(bundle/'fingerprints.sqlite'))
    counts=[]
    with sqlite3.connect(output/'selection.sqlite') as dest:
        dest.execute('CREATE TABLE selected(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE,language TEXT,family TEXT,source_shard INTEGER,receipt_sha256 TEXT,candidate_path TEXT,candidate_sha256 TEXT)')
        for quota in quotas:
            language,family,i=quota['language'],quota['family'],quota['shard']
            needed=quota['target']-quota['accepted'];added=0
            for row in results[i].execute('SELECT * FROM results WHERE eligible=1 AND language=? AND family=? ORDER BY id LIMIT ?',
                    (language,family,needed)):
                job=jobs[i].execute('SELECT status,fingerprint,outcome_json,spec_json FROM jobs WHERE id=?',(row['id'],)).fetchone()
                owner=registry.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(row['fingerprint'],)).fetchone()
                proof,candidate_hash=check_selected(row,job,owner)
                dest.execute('INSERT INTO selected VALUES(?,?,?,?,?,?,?,?)',(row['id'],row['fingerprint'],language,family,i,
                    digest(proof),proof['candidate_path'],candidate_hash))
                added+=1
                if added%1000==0:
                    dest.commit()
            dest.commit()
            counts.append(dict(quota,selected_recovery=added,actual_deficit=needed-added))
            write_json(output/'progress.json',dict(phase='selecting',groups=counts,
                selected=sum(r['selected_recovery'] for r in counts)))
    existing=sum(r['accepted'] for r in counts);recovered=sum(r['selected_recovery'] for r in counts)
    deficit=sum(r['actual_deficit'] for r in counts)
    report=dict(version='wave4-cpu-selection735-v1',bundle=str(bundle),recovery_root=str(recovery),
        recovery_prepared_sha256=file_hash(recovery/'prepared.json'),groups=counts,
        existing_accepted=existing,selected_recovery=recovered,total_selected=existing+recovered,
        target=735000,actual_deficit=deficit,additional_gpu_required=deficit>0,
        selection_sha256=file_hash(output/'selection.sqlite'),
        source_terminal_sha256=file_hash(bundle/'terminal.json'),
        selected_recovery_only=True,original_files_unchanged=True,ledger_applied=False,
        publication_requires_selected_raw_evidence_verification=True,time=time.time())
    write_json(output/'selection-complete.json',report)
    write_json(output/'progress.json',dict(phase='complete',**report))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--recovery',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(select(args.bundle,args.recovery,args.output),indent=2))
