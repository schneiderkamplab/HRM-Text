"""Read-only SR publication/token verification and main/Poincare handoff."""
import argparse
import json
from pathlib import Path
import sqlite3
import time

from dfm12 import sr_manual_exclusion as sr
from dfm12.io import digest, file_hash, load, write_json
from scripts import assemble_dfm13_additions as assembler


def main(wait_seconds):
    out=Path(__file__).resolve().parent/'finalization'
    target=out/'verified-handoff.json'
    assert not target.exists(), 'Preserve frozen handoff'
    deadline=time.monotonic()+wait_seconds
    while True:
        entries=[e for e in load('config/dfm13_sources.json')['additions'] if e['name'].startswith('dfm13_wave4_wikipedia_sr_')]
        pending=[e['name'] for e in entries if not e.get('tokenization_performed')]
        assert len(entries)==4
        if not pending: break
        print('Waiting for existing tokenizer PID2134027:',pending,flush=True)
        if time.monotonic()>=deadline: raise TimeoutError('Existing tokenizer not finished; no duplicate started')
        time.sleep(15)
    reviews={x['id']:x for x in load(sr.REVIEW/'evidence.json')}
    removed=set(sr.CASES.values()); retained=[]; verified=[]
    for entry in sorted(entries,key=lambda x:x['task']):
        publication=load(entry['manifest']); source=Path(entry['output'])
        evidence=source.parent.parent/'manual-review-decisions.json'
        assert publication['attribution_files']==entry['attribution_files']=={file_hash(evidence):evidence.name}
        metadata=load(Path('exports_dfm13/sr-manual-review-evidence-20261003-v1')/entry['task']/'verified.json')
        assert metadata['hf_revision']==entry['hf_revision']==publication['hf_revision']
        assert file_hash(source)==entry['output_sha256']==metadata['unchanged_data_sha256']
        ids=set();count=0
        with source.open() as handle:
            for line in handle:
                row=json.loads(line); count+=1
                assert row['id'] not in ids and row['id'] not in removed
                ids.add(row['id'])
                if row['id']==sr.RETAINED_CASE45:
                    original=reviews[row['id']]['record']
                    assert row['messages']==original['messages']
                    assert all(row['provenance'][k]==v for k,v in original['provenance'].items())
                    retained.append(dict(id=row['id'],task=entry['task'],messages_sha256=digest(row['messages'])))
        assert count==entry['rows']
        pins={}
        contract=assembler.token_contract(load(Path(entry['tokenized_path'])/'tokenizer_info.json'),pins)
        checked=assembler.verify_entry(entry,contract,pins)
        verified.append(dict(entry=entry,verification=checked,pins=pins,
            export_rows_scanned=count,exact_manual_ids_absent=True,
            remote_verified_files=metadata['remote_verified_files']))
        print('Verified',entry['task'],count,entry['tokenized_tokens'],flush=True)
    assert len(retained)==1 and retained[0]['task']=='span-filling'
    root=Path('data/dfm13/wave4')
    ledger=sqlite3.connect((root/'release/wikipedia-sr/ledger.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    queue=sqlite3.connect((root/'repair/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    retry=[]
    fields=('id','status','attempts','owner','result','error','payload')
    for values in queue.execute('SELECT '+','.join(fields)+' FROM jobs WHERE owner=? AND json_extract(payload,\'$.record.component\')=?',
            ('66c9373d67ca40199c044a7f46bbc951','wikipedia-sr')):
        job=dict(zip(fields,values)); payload=json.loads(job.pop('payload'));key=payload['record']['id']
        job['candidate_id']=key
        job['final_ledger_status']=ledger.execute('SELECT status FROM rows WHERE id=?',(key,)).fetchone()[0]
        retry.append(job)
    assert len(retry)==22
    assert sum(j['status']=='done' for j in retry)==21
    assert sum(j['status']=='failed' and j['attempts']==4 and j['final_ledger_status']=='excluded_unreviewed' for j in retry)==1
    counts=dict(ledger.execute('SELECT status,count(*) FROM rows GROUP BY status'))
    assert counts['excluded_manual_review']==4 and not counts.get('audit_retry_pending')
    assert len(ledger.execute('SELECT id FROM manual_review_decisions').fetchall())==4
    ledger.close();queue.close()
    write_json(target,dict(status='accepted_uploaded_tokenized_verified',rows=sum(e['rows'] for e in entries),
        tokens=sum(e['tokenized_tokens'] for e in entries),ledger_counts=counts,
        retry_jobs=retry,manual_excluded_ids=sorted(removed),case45_retained=retained[0],entries=verified,
        gpu_actions=0,duplicate_tokenizers_started=0,training_or_epoch_sampling=False,
        correction_evidence_commit_scope='metadata_only_data_and_tokens_unchanged'))
    print('HANDOFF',target,file_hash(target),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wait-seconds',type=int,default=0)
    main(p.parse_args().wait_seconds)
