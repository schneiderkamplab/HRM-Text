"""Nine explicitly authorized supplemental queries under the original 100-call cap."""
import argparse
import asyncio
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import stat

import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup as prior
from scripts import dfm13_search_targeted_repair_v4 as repair
from scripts import dfm13_search_review_validation_v4 as validation


class SupplementBudget(base.SearchBudget):
    """Same charged reservations, scoped allowance for one additional query/owner."""
    def __init__(self,root,allowed):
        super().__init__(root)
        self.allowed=dict(allowed)
        if len(self.allowed)>9: raise ValueError('supplement exceeds nine authorized queries')
        self.authorization=base.digest(self.allowed)
        self.db.execute('CREATE TABLE IF NOT EXISTS supplement9_reservations (key TEXT PRIMARY KEY, owner TEXT, authorization TEXT)')
        self.db.commit()

    def reserve(self,query,owner):
        if self.allowed.get(owner)!=query: raise ValueError('query/owner outside explicit supplement scope')
        key=base.digest(dict(provider='jina',endpoint='https://s.jina.ai/',query=query,accept='application/json'))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT status,raw,provenance FROM searches WHERE key=?',(key,)).fetchone()
            if row:
                if row[0]!='done':raise ValueError('previous paid query unresolved; no paid retry')
                self.db.commit();return key,(row[1],json.loads(row[2]))
            if self.db.execute('SELECT count(*) FROM searches').fetchone()[0]>=base.ceiling(self.db):
                raise ValueError('campaign paid-call ceiling exhausted')
            if self.db.execute('SELECT count(*) FROM supplement9_reservations WHERE authorization=?',(self.authorization,)).fetchone()[0]>=9:
                raise ValueError('nine supplementary reservations exhausted')
            if self.db.execute('SELECT 1 FROM supplement9_reservations WHERE owner=? AND authorization=?',(owner,self.authorization)).fetchone():
                raise ValueError('owner already charged for this supplement')
            self.db.execute('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',(key,owner,query,'reserved'))
            self.db.execute('INSERT INTO supplement9_reservations VALUES(?,?,?)',(key,owner,self.authorization))
            self.db.commit();return key,None
        except BaseException:
            self.db.rollback();raise


HINTS={
 '032d2d0c':dict(kind='CPU-verified counterexample',text='3215031751 = 151*751*28351 < 2^32 is composite and passes strong Miller-Rabin tests for 2,3,5,7. Do not repeat their false universal 32-bit guarantee. Failure of the specific set 2,3,5 does not prove every three-base set fails. Do not assert a minimum absent a proof or reliable support.'),
 '51c2360a':dict(kind='Internal chronological contradiction',text='The question is anchored May 5, 2025. June 10, June 6 and May 14, 2025 events cannot be presented as already current at that date. A fresh 2026 release-note page is not itself historical evidence. If no valid earlier release is established, explicitly preserve uncertainty.'),
 '06cd049f':dict(kind='Pinned independent temporal review',text='The question is anchored May 9, 2025. A February 2026 article using December 2025 polling cannot establish the earlier current situation. Do not relabel the original question current. If historical evidence is absent, say so.'),
}


def prepare(args):
    if args.root.exists():raise ValueError('new root required')
    ledger=Path('data/dfm13/search-campaign-ledger-20261001-final/ledger.json')
    needs=json.loads(ledger.read_text())['retrieval_needs']
    needs=[n for n in needs if n['proposed_query']]
    if len(needs)!=9:raise ValueError('expected exactly nine scoped queries')
    source=Path('data/dfm13/search-reviewer-v3-20261001')
    alljobs={j['id']:j for j in json.loads((source/'jobs.json').read_text())}
    jobs=[]
    for need in needs:
        job=alljobs[need['id']]
        job.update(supplement_query=need['proposed_query'],supplement_need=need,mode='new_retrieval_repair')
        jobs.append(job)
    for key,job in alljobs.items():
        if key[:8] in HINTS:
            job.update(verified_correction=HINTS[key[:8]],mode='cached_case_specific_correction')
            job['pages']={u:{k:p[k] for k in ('url','title','body') if k in p} for u,p in job['pages'].items()}
            jobs.append(job)
    base.atomic(args.root/'jobs.json',jobs)
    manifest=json.loads((source/'manifest.json').read_text())
    for p in (Path(__file__),Path(repair.__file__),Path(validation.__file__),ledger,args.root/'jobs.json'):
        manifest['pins'][str(p.resolve())]=base.file_hash(p)
    manifest.update(total=len(jobs),supplement_queries=9,paid_call_ceiling=100,paid_calls_allowed=9,
                    cache_root=str(base.CAMPAIGN.resolve()),created_at=base.now(),max_attempts=1,
                    admission_authorized=False,scope='Nine additional queries explicitly authorized; preserve prior 87 reservations')
    base.atomic(args.root/'manifest.json',manifest)
    print(json.dumps(dict(queued=len(jobs),queries=9,cached_holds=3)))


def load_key(path):
    if os.environ.get('JINA_API_KEY'):return os.environ['JINA_API_KEY']
    try: fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return None
    with os.fdopen(fd) as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
            raise ValueError('credential file must be owned private regular file')
        value=stream.read(4096).strip()
    return value or None


class ScopedModel:
    def __init__(self,model,hint):
        self.model=model;self.tokenizer=model.tokenizer;self.manifest=model.manifest;self.hint=hint
    async def ask(self,messages,schema,tools,folder,stage):
        messages=json.loads(json.dumps(messages))
        if stage=='repair':
            oldtext='and do not give a proof of a mathematical minimum unless established; in particular bases 2,3,5,7 do NOT guarantee Miller-Rabin correctness for all 32-bit integers: 3215031751 is a composite counterexample. '
            if oldtext not in messages[0]['content']:raise ValueError('teacher-hint scope anchor changed')
            messages[0]['content']=messages[0]['content'].replace(oldtext,'Do not assert a mathematical minimum without sufficient support. ')
            if self.hint:messages[0]['content']+=' Case-specific independently verified correction: '+self.hint['text']
        return await self.model.ask(messages,schema,tools,folder,stage)


async def run(args):
    manifest=json.loads((args.root/'manifest.json').read_text())
    for p,h in manifest['pins'].items():
        if base.file_hash(Path(p))!=h:raise ValueError('input pin mismatch')
    if manifest['endpoints']!=[f'http://127.0.0.1:{p}/v1/chat/completions' for p in range(8800,8808)]:
        raise ValueError('unexpected endpoints')
    jobs=json.loads((args.root/'jobs.json').read_text())
    allowed={j['id']:j['supplement_query'] for j in jobs if 'supplement_query' in j}
    base.atomic(args.root/'runtime.json',dict(pid=os.getpid(),status='waiting_for_credential',queued=len(jobs),
        concurrency_per_endpoint=args.concurrency_per_server,paid_call_ceiling=100))
    # Cached corrections can proceed even when credential is unavailable.
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def process(job,index):
            folder=args.root/'records'/job['id']
            if (folder/'outcome.json').exists():return
            if (folder/'started.json').exists():
                base.atomic(folder/'outcome.json',dict(status='interrupted',admission_authorized=False));return
            base.atomic(folder/'started.json',dict(at=base.now(),endpoint=manifest['endpoints'][index%8],mode=job['mode']))
            # Existing cached observation is retained for the three correction-only cases.
            if 'extraction_provenance' not in job:job['extraction_provenance']=dict(job['pages'])
            if 'cache_sha256' not in job:job['cache_sha256']=job['candidate'].get('evidence_replay',{}).get('raw_cache_sha256','')
            job['candidate']['case_specific_verified_correction']=job.get('verified_correction')
            model=ScopedModel(base.Model(session,tokenizer,manifest,manifest['endpoints'][index%8],args.timeout),job.get('verified_correction'))
            try:result=await repair.execute(job,model,folder)
            except Exception as error:result=dict(status='error',error=str(error))
            base.atomic(folder/'outcome.json',dict(**result,admission_authorized=False))
        await asyncio.gather(*(process(j,i) for i,j in enumerate(jobs) if 'supplement_query' not in j))
        key=load_key(args.credential_file)
        while not key:
            await asyncio.sleep(15);key=load_key(args.credential_file)
        os.environ['JINA_API_KEY']=key
        base.atomic(args.root/'runtime.json',dict(pid=os.getpid(),status='retrieving_scoped_queries',queued=9,
            concurrency_per_endpoint=args.concurrency_per_server,paid_call_ceiling=100))
        ready=[]
        async with base.Web('jina',args.root/'provider-snapshots') as web:
            web.budget=SupplementBudget(base.CAMPAIGN,allowed)
            for job in jobs:
                if 'supplement_query' not in job:continue
                folder=args.root/'records'/job['id']
                if (folder/'outcome.json').exists():continue
                try:
                    result=await web.search(job['supplement_query'],owner=job['id'])
                    base.atomic(folder/'retrieval.json',result)
                    row=web.budget.db.execute('SELECT raw FROM searches WHERE query=? AND owner=? AND status="done"',
                        (job['supplement_query'],job['id'])).fetchone()
                    if row is None:raise ValueError('completed scoped cache row missing')
                    import hashlib
                    payload=base.strict_json(row[0]);pages=repair.select_pages(payload,job['supplement_query'])
                    job['extraction_provenance']=pages
                    job['pages']={u:{k:p[k] for k in ('url','title','body')} for u,p in pages.items()}
                    job['cache_sha256']=hashlib.sha256(row[0]).hexdigest()
                    history=job['candidate']['messages']
                    if history[-1]['role']=='assistant' and not history[-1].get('tool_calls'):history.pop()
                    callid='supplement-'+job['id'][:16]
                    history.append(dict(role='assistant',content='',tool_calls=[dict(id=callid,type='function',
                        function=dict(name='search',arguments=dict(query=job['supplement_query'])))]))
                    history.append(dict(role='tool',name='search',tool_call_id=callid,content=json.dumps(result,ensure_ascii=False)))
                    job['candidate']['supplement_provenance']=dict(query=job['supplement_query'],planner='controller-authored actual executed query',
                        assistant_tool_call_is_not_model_generated=True,target_policy='final answer only; controller search call excluded')
                    base.atomic(folder/'prepared-job.json',job);ready.append(job)
                except Exception as error:
                    # Never print credentials or response bodies in exception summaries.
                    message=str(error).replace(key,'[REDACTED]')
                    base.atomic(folder/'outcome.json',dict(status='retrieval_error',error=message,admission_authorized=False))
        os.environ.pop('JINA_API_KEY',None)
        await asyncio.gather(*(process(j,i) for i,j in enumerate(ready)))
    for path in (args.root/'records').glob('*/candidate.json'):
        candidate=json.loads(path.read_text())
        if candidate.get('supplement_provenance'):
            candidate['target_message_indices']=[len(candidate['messages'])-1]
            base.atomic(path,candidate)
    outcomes=[json.loads(p.read_text()) for p in (args.root/'records').glob('*/outcome.json')]
    base.atomic(args.root/'finished.json',dict(total=len(outcomes),counts=dict(Counter(o.get('verdict',o['status']) for o in outcomes)),
        paid_call_ceiling=100,admission_authorized=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,default=Path('data/dfm13/search-supplement9-20261001'))
    p.add_argument('--credential-file',type=Path,default=Path.home()/'.config/dfm13/jina-api-key')
    p.add_argument('--concurrency-per-server',type=int,default=8);p.add_argument('--timeout',type=int,default=600)
    args=p.parse_args()
    if args.command=='prepare':prepare(args)
    else:
        with (args.root/'run.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);asyncio.run(run(args))


if __name__=='__main__':main()
