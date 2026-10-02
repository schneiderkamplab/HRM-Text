"""Local accepted-only packages from the completed European leased audit queue."""
import argparse
from collections import Counter
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import time

from .export_finished import descriptor, portable_provenance, views
from .export_validator import validate, validate_language
from .io import file_hash, load, lock, write_json
from .jobs import validate_audit
from .records import validate_messages


class Package:
    def __init__(self, root, component, evidence):
        if not re.fullmatch('[a-z0-9_-]+',component):
            raise ValueError('Unsafe component: '+component)
        self.name='dfm12-'+component
        self.destination=root/self.name
        self.root=root/('.building-'+self.name)
        if self.destination.exists() or self.root.exists():
            raise FileExistsError(self.name)
        (self.root/'data').mkdir(parents=True)
        (self.root/'metadata/evidence').mkdir(parents=True)
        self.component=component
        self.counts=Counter();self.languages=Counter();self.licenses=Counter()
        self.sources=Counter();self.cache={};self.files=[];self.shard=None;self.shard_count=0
        for path in evidence:
            shutil.copyfile(path,self.root/'metadata/evidence'/path.name)
        self.audits=gzip.open(self.root/'metadata/audits.jsonl.gz','wt',encoding='utf-8',compresslevel=1)
        self.exclusions=gzip.open(self.root/'metadata/exclusions.jsonl.gz','wt',encoding='utf-8',compresslevel=1)
        self.unresolved=gzip.open(self.root/'metadata/audit_unresolved.jsonl.gz','wt',encoding='utf-8',compresslevel=1)

    def close_shard(self):
        if self.shard:
            self.shard.close()
            self.files.append(descriptor(self.root,self.shard_path,rows=self.shard_count))
            self.shard=None

    def add(self, job):
        key,encoded,status,raw,attempts,error=job
        record=json.loads(encoded)['record']
        if record['component']!=self.component:raise ValueError('Wrong component')
        result=json.loads(raw) if raw else None
        if status=='done':validate_audit(result)
        if status!='done' or not result['keep']:
            disposition='audit_unresolved' if status!='done' else 'audit_rejected'
            self.counts[disposition]+=1
            # No source text or server error body in uploadable exclusions.
            item=dict(id=record['id'],status=status,attempts=attempts,error='request_failed' if error else None,
                      disposition=disposition,gate_reasons=[],audit=result)
            line=json.dumps(item,ensure_ascii=False)+'\n'
            self.exclusions.write(line)
            if status!='done':self.unresolved.write(line)
            return
        validate_language(record,european=True)
        validate_messages(record['messages'])
        if 'reverse_messages' in record:validate_messages(record['reverse_messages'])
        portable=portable_provenance(self.root,record['provenance'],self.cache)
        self.licenses[str(portable.get('license','unspecified; upstream terms apply'))]+=1
        self.sources[str(portable.get('repo',portable.get('source','see per-row provenance')))]+=1
        student_ids=[]
        for row in views(record):
            if self.shard is None or self.shard_count>=50000:
                self.close_shard()
                self.shard_path=self.root/'data'/f'train-{len(self.files):05d}.jsonl.gz'
                self.shard=gzip.open(self.shard_path,'wt',encoding='utf-8',compresslevel=1)
                self.shard_count=0
            self.shard.write(json.dumps(row,ensure_ascii=False)+'\n')
            self.shard_count+=1;self.counts['training_rows']+=1;self.languages[row['language']]+=1
            student_ids.append(row['id'])
        self.counts['accepted']+=1
        self.audits.write(json.dumps(dict(id=record['id'],job_id=key,record=record,status=status,
            attempts=attempts,audit=result,disposition='accepted',gate_reasons=[],
            export_provenance=portable,student_ids=student_ids),ensure_ascii=False)+'\n')

    def finish(self):
        self.close_shard()
        for f in (self.audits,self.exclusions,self.unresolved):f.close()
        shutil.copyfile(Path(__file__).with_name('export_validator.py'),self.root/'validate_dataset.py')
        manifest=dict(export_schema='dfm12-european-v1',component=self.component,name=self.name,
            counts=dict(self.counts),languages=dict(self.languages),licenses_per_accepted_record=dict(self.licenses),
            source_repositories=dict(self.sources),data_files=self.files,
            metadata_files=[descriptor(self.root,p) for p in sorted((self.root/'metadata').rglob('*')) if p.is_file()],
            audit_file='metadata/audits.jsonl.gz',unresolved_file='metadata/audit_unresolved.jsonl.gz',
            exclusions_file='metadata/exclusions.jsonl.gz',upload_performed=False,hf_repo_id=None,
            authorization=dict(scope='local_accepted_only_export',basis='owner_request_20260928'),
            hf_ready=bool(self.files),upload_ready=bool(self.files),
            admission_status='local_user_authorized_accepted_only_automated_audit',
            multilingual_quality_calibration_complete=False,benchmarks_clear=False)
        manifest['counts'].setdefault('training_rows',0)
        write_json(self.root/'metadata/manifest.json',manifest)
        header='---\nconfigs:\n- config_name: default\n  data_files:\n  - split: train\n    path: data/train-*.jsonl.gz\ntask_categories:\n- text-generation\n---\n' if self.files else ''
        (self.root/'README.md').write_text(header+'\n# '+self.name+'\n\n'+
            'Local accepted-only European expansion export. No upload performed.\n\n'+
            'Only audit keep=true decisions with all three scores at least 4 are included. '+
            'These are automated judgments, not native-speaker certification. Exact overlap screening was partial; '+
            'this package is not certified benchmark-clean.\n\n'+
            'Train on messages and optional target_message_index only. Provenance and audit judgments are in '+
            'metadata/audits.jsonl.gz, never appended to training text. Translation pairs with reverse_messages '+
            'retain both directions, linked by parent_pair_id. No validation/test split is manufactured.\n\n'+
            '## Sources and licensing\n\nNo blanket relicensing. Preserve per-row provenance and upstream terms. '+
            'Unspecified licenses remain unresolved, not asserted as permissive.\n\n'+
            '\n'.join('- '+repo for repo in sorted(self.sources))+'\n\n'+
            '## Validation\n\nRun `python validate_dataset.py` (standard library only).\n')
        result=validate(self.root)
        self.root.rename(self.destination)
        return dict(name=self.name,component=self.component,rows=self.counts['training_rows'],
            accepted_records=self.counts['accepted'],counts=dict(self.counts),languages=dict(self.languages),
            data_bytes=sum(x['bytes'] for x in self.files),validation=result,
            status='local_user_authorized_accepted_only_automated_audit')


def worker(number,inbox,output,evidence):
    packages={}
    while True:
        message=inbox.get()
        if message is None:break
        component,job=message
        if component not in packages:packages[component]=Package(output,component,evidence)
        packages[component].add(job)
    results=[]
    for package in packages.values():
        results.append(package.finish())
        write_json(output/f'worker-{number}.json',dict(packages=results,finished=False))
    write_json(output/f'worker-{number}.json',dict(packages=results,finished=True))


def run(root,output,workers):
    output.mkdir(parents=True,exist_ok=True)
    with lock(output/'.export.lock'):
        if list(output.glob('.building-*')) or list(output.glob('dfm12-*')):
            raise FileExistsError('Existing output; use a clean staging directory')
        db=sqlite3.connect((root/'screened/jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
        db.execute('PRAGMA cache_size=-32768')
        db.execute('BEGIN')
        status=dict(db.execute("SELECT status,count(*) FROM jobs WHERE stage='audit' GROUP BY status"))
        if any(k not in ('done','failed') for k in status):raise ValueError('Audit not terminal')
        evidence=[root/'sources.lock.json',root/'config.json',root/'screened/audit-manifest.json',root/'screened/reference-inputs.json']
        write_json(output/'input.json',dict(database=str(root/'screened/jobs.sqlite'),status=status,
            evidence=[dict(path=str(p),sha256=file_hash(p)) for p in evidence],upload_performed=False))
        ctx=mp.get_context('spawn');queues=[ctx.Queue(maxsize=32) for _ in range(workers)]
        processes=[ctx.Process(target=worker,args=(i,queues[i],output,evidence)) for i in range(workers)]
        for p in processes:p.start()
        components={};n=0
        def send(i,value):
            while True:
                if any(p.exitcode not in (None,0) for p in processes):raise RuntimeError('Export worker failed; staging retained')
                try:queues[i].put(value,timeout=1);return
                except queue.Full:pass
        try:
            for row in db.execute("SELECT id,payload,status,result,attempts,error FROM jobs WHERE stage='audit' ORDER BY rowid"):
                component=json.loads(row[1])['record']['component']
                if component not in components:components[component]=len(components)%workers
                send(components[component],(component,row));n+=1
                if n%10000==0:write_json(output/'progress.json',dict(scanned=n,total=sum(status.values()),phase='packaging',time=time.time()))
            for i in range(workers):send(i,None)
            db.close()
            while any(p.is_alive() for p in processes):
                if any(p.exitcode not in (None,0) for p in processes):raise RuntimeError('Validation worker failed')
                time.sleep(1)
            for p in processes:
                p.join()
                if p.exitcode:raise RuntimeError('Export worker failed')
            packages=[x for i in range(workers) for x in load(output/f'worker-{i}.json')['packages']]
            write_json(output/'manifest.json',dict(packages=sorted(packages,key=lambda p:p['name']),
                accepted_records=sum(p['accepted_records'] for p in packages),training_rows=sum(p['rows'] for p in packages),
                upload_performed=False,finished=True))
            write_json(output/'progress.json',dict(scanned=n,total=sum(status.values()),phase='complete',time=time.time()))
        finally:
            for p in processes:
                if p.is_alive():p.terminate()
            for p in processes:p.join()


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--root',type=Path,default=Path('data/dfm12/european-expansion-20260926'))
    p.add_argument('--output',type=Path,default=Path('exports_dfm12/european-expansion'))
    p.add_argument('--workers',type=int,default=8)
    a=p.parse_args()
    if not 1<=a.workers<=16:p.error('workers must be 1..16')
    run(a.root,a.output,a.workers)
