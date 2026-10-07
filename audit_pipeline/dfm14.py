"""DFM14 data adapters; legacy journals remain readable and append-only."""
from collections import Counter, deque
import json
import os
from pathlib import Path
import time

import httpx
import jsonschema

from dfm12.io import file_hash, load, lock, rows, write_json
from dfm14 import audit as old_audit
from dfm14 import production as old_generation
from dfm14.catalog import LANGUAGES
from . import review


class Journals:
    model=old_generation.MODEL

    def __init__(self, root, output, endpoint):
        self.root,self.output,self.endpoint=Path(root),Path(output),endpoint
        self.opened={}
        self.ready=deque()
        self.jobs=iter(())
        self.last_report=0

    def initialize_cpu(self): pass

    def next_item(self):
        while not self.ready:
            try:job=next(self.jobs)
            except StopIteration:return None
            folder=self.folder(job)
            guard=lock(folder/'.lock')
            try:guard.__enter__()
            except BlockingIOError:continue
            try:
                if (folder/'receipt.json').exists():
                    self.verify_receipt(job,folder)
                    guard.__exit__(None,None,None)
                    continue
                pending,history=self.load_pending(job,folder)
                state=dict(job=job,folder=folder,guard=guard,history=history,
                    remaining=len(pending),journal=(folder/self.journal_name).open('a',encoding='utf-8'),
                    dirty=0,last_progress=0)
                self.opened[job['job_id']]=state
                if not pending:
                    self.finalize(job['job_id'])
                    continue
                self.ready.extend((job['job_id'],row) for row in pending)
            except BaseException:
                if job['job_id'] not in self.opened:guard.__exit__(None,None,None)
                raise
        return self.ready.popleft()

    def commit(self, item, result):
        state=self.opened[item[0]];key=self.result_key(result)
        if key in state['history']: raise ValueError('Duplicate result commit')
        state['journal'].write(json.dumps(result,ensure_ascii=False)+'\n')
        state['journal'].flush()
        # Keep durability guarantees without filesystem work in the async loop.
        os.fsync(state['journal'].fileno())
        state['history'][key]=self.compact(result)
        state['dirty']+=1
        if time.monotonic()-state['last_progress']>=2 or state['dirty']>=16:
            write_json(state['folder']/'progress.json',self.progress(state))
            state['last_progress']=time.monotonic();state['dirty']=0

    def finish_item(self,item):
        state=self.opened[item[0]];state['remaining']-=1
        if state['remaining']==0:self.finalize(item[0])

    def finalize(self,key):
        state=self.opened[key]
        state['journal'].flush();os.fsync(state['journal'].fileno())
        state['journal'].close()
        receipt=self.receipt(state)
        write_json(state['folder']/'progress.json',self.progress(state))
        write_json(state['folder']/'receipt.json',receipt)
        state['guard'].__exit__(None,None,None)
        del self.opened[key]

    def report(self,snapshot):
        port=self.endpoint.rsplit(':',1)[1].split('/')[0]
        write_json(self.output/'pipeline'/f'endpoint-{port}.json',dict(snapshot,
            open_chunks=len(self.opened),prepared_rows=len(self.ready),
            jobs=[dict(job_id=k,remaining=s['remaining']) for k,s in self.opened.items()]))

    def close(self):
        for state in self.opened.values():
            try:
                if not state['journal'].closed:
                    state['journal'].flush();os.fsync(state['journal'].fileno());state['journal'].close()
            finally:state['guard'].__exit__(None,None,None)
        self.opened.clear()


class Audit(Journals):
    journal_name='results.jsonl'

    def initialize(self):
        self.jobs=iter(load(self.root/'manifest.json')['chunks'])

    def folder(self,job):return self.output/job['job_id']

    def verify_receipt(self,job,folder):
        receipt=load(folder/'receipt.json')
        if receipt['input_sha256']!=job['sha256'] or receipt['model']!=self.model:
            raise ValueError('Changed audit inputs/model')
        if file_hash(folder/self.journal_name)!=receipt['results_sha256']:
            raise ValueError('Changed completed audit results')

    def load_pending(self,job,folder):
        path=self.root/job['input']
        if file_hash(path)!=job['sha256']:raise ValueError('Changed audit input')
        records=list(rows(path));ids={r['audit_id'] for r in records}
        if len(ids)!=len(records) or len(records)!=job['rows']:raise ValueError('Invalid audit count/IDs')
        history=old_audit.recover_journal(folder/self.journal_name,ids)
        return [r for r in records if r['audit_id'] not in history],{k:self.compact(v) for k,v in history.items()}

    @staticmethod
    def result_key(result):return result['audit_id']

    @staticmethod
    def compact(result):
        return dict(status=result['status'],decision=result.get('review',{}).get('decision'),policy=result.get('policy') or 'legacy-unspecified')

    def progress(self,state):
        return dict(endpoint=self.endpoint,completed=len(state['history']),total=state['job']['rows'],task=state['job']['task'])

    def receipt(self,state):
        counts=Counter(r['decision'] if r['status']=='reviewed' else r['status'] for r in state['history'].values())
        return dict(input_sha256=state['job']['sha256'],model=self.model,endpoint=self.endpoint,
            policy=review.VERSION,policies=sorted({r['policy'] for r in state['history'].values()}),
            counts=dict(counts),rows=len(state['history']),training_ready=False,
            results_sha256=file_hash(state['folder']/self.journal_name))

    def prepare(self,row):
        names=dict(LANGUAGES,en='English',fo='Faroese',pl='Polish',fa='Persian')
        evidence=dict(language=names.get(row['language'],row['language']),task=row['task'],conversation=row['messages'],
                      evidence=row.get('audit_context'))
        if row.get('tools'):evidence['tools']=row['tools']
        return review.payload(evidence,self.model)

    async def process(self,item,http,cpu,disk):
        row=item[1];payload=await cpu.call(self.prepare,row)
        result=dict(audit_id=row['audit_id'],input_id=row['id'],policy=review.VERSION)
        for attempt in (1,2):
            try:
                body=await http.post(payload)
                value=await cpu.call(review.verdict,body)
                result.update(status='reviewed',review=value,attempt=attempt)
                break
            except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError) as exc:
                result.update(status='infrastructure_or_invalid_review',attempt=attempt,
                              error=dict(type=type(exc).__name__,message=str(exc)[:500]))
        await disk.call(self.commit,item,result)


class Generation(Journals):
    journal_name='attempts.jsonl'

    def initialize(self):
        self.manifest=load(self.root/'manifest.json')
        self.jobs=iter(self.manifest['jobs'])

    def initialize_cpu(self):
        self.budget=old_generation.configure()
        self.pools=old_generation.Pools(self.root)

    def folder(self,job):return self.root/'jobs'/job['job_id']

    def verify_receipt(self,job,folder):
        receipt=load(folder/'receipt.json')
        if receipt['job']!=job or file_hash(folder/self.journal_name)!=receipt['journal_sha256']:
            raise ValueError('Changed generation job/results')

    def load_pending(self,job,folder):
        history=old_generation.recover(folder/self.journal_name)
        accepted=set();attempts={}
        for key,r in history.items():
            if not job['start']<=r['slot']<job['end']:raise ValueError('Slot outside job')
            if r['status']=='accepted':
                if r['slot'] in accepted:raise ValueError('Duplicate accepted slot')
                accepted.add(r['slot'])
            attempts.setdefault(r['slot'],set()).add(r['attempt'])
        pending=[dict(job=job,slot=slot,attempts=[a for a in range(self.manifest['attempts_per_slot']) if a not in attempts.get(slot,set())])
                 for slot in range(job['start'],job['end']) if slot not in accepted]
        return [r for r in pending if r['attempts']],{k:self.compact(v) for k,v in history.items()}

    @staticmethod
    def result_key(result):return (result['slot'],result['attempt'])

    @staticmethod
    def compact(result):return dict(status=result['status'])

    def progress(self,state):
        return dict(endpoint=self.endpoint,attempts=len(state['history']),
            accepted=sum(r['status']=='accepted' for r in state['history'].values()),
            target=state['job']['end']-state['job']['start'])

    def receipt(self,state):
        counts=Counter(r['status'] for r in state['history'].values())
        target=state['job']['end']-state['job']['start']
        return dict(job=state['job'],counts=dict(counts),endpoint=self.endpoint,target=target,
            shortfall=target-counts['accepted'],journal_sha256=file_hash(state['folder']/self.journal_name),
            training_ready=False,review_policy=review.VERSION)

    def prepare(self,job,slot,attempt):
        g=old_generation
        spec=g.specification(job,slot,attempt,self.pools)
        result=dict(slot=slot,attempt=attempt,language=job['language'],family=job['family'],
                    spec_sha256=g.digest(spec),training_ready=False,raw={},review_policy=review.VERSION)
        if job['kind']=='multilingual':
            if g.source_issues(spec):raise ValueError('Source preflight failed')
            payload,schema=g.generation_payload(spec,g.generation,self.model)
        else:payload,schema=g.knowledge_request(spec)
        self.budget.measure(payload)
        return spec,result,payload,schema

    def assemble(self,job,spec,result,payload,schema,body):
        g=old_generation
        result['raw']['generation']=dict(payload_sha256=g.digest(payload),response=body)
        choice=body['choices'][0]
        if choice['finish_reason']!='stop':raise ValueError('Incomplete generation')
        value=g.generation._parse(choice['message']['content']);jsonschema.validate(value,schema)
        candidate=g.assemble(spec,value,g.generation) if job['kind']=='multilingual' else g.knowledge_assemble(spec,value)
        if job['kind']=='multilingual':
            record=g.audit_record(candidate);deterministic=g.checks.deterministic_checks(record)
            result['checks']=deterministic
            if not all(c['passed'] for c in deterministic):raise ValueError('Reference/trajectory check failed')
        else:
            record=dict(language='en',language_name='English',family=spec['family'],messages=candidate['messages'],tools=[],source=spec['source'])
            if spec['family']=='commonsense':record['source']=dict(text=json.dumps(spec['source'],ensure_ascii=False))
        result['candidate']=candidate
        # Preserve full review evidence, not the legacy per-turn output scaffold.
        evidence={k:v for k,v in record.items() if k not in ('required_turn_keys',)}
        payload=review.payload(evidence,self.model);self.budget.measure(payload)
        return payload

    def finish_review(self,result,payload,body):
        result['raw']['review']=dict(payload_sha256=old_generation.digest(payload),response=body)
        value=review.verdict(body)
        if not any(m['role']=='assistant' for m in result['candidate']['messages']):raise ValueError('No assistant target')
        result.update(status='accepted' if value['decision']=='accept' else 'rejected',review=value)

    async def process(self,item,http,cpu,disk):
        row=item[1];job=row['job']
        for attempt in row['attempts']:
            result=dict(slot=row['slot'],attempt=attempt,language=job['language'],family=job['family'],
                        training_ready=False,raw={},review_policy=review.VERSION)
            try:
                spec,result,payload,schema=await cpu.call(self.prepare,job,row['slot'],attempt)
                body=await http.post(payload)
                payload=await cpu.call(self.assemble,job,spec,result,payload,schema,body)
                body=await http.post(payload)
                await cpu.call(self.finish_review,result,payload,body)
            except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError,jsonschema.ValidationError) as exc:
                result.update(status='error',error_type=type(exc).__name__,error=str(exc)[:1200])
            await disk.call(self.commit,item,result)
            if result['status']=='accepted':break
