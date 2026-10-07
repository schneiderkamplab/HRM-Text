"""Owner-authorized synthesis with per-chunk locks, journals and bounded retries."""
import asyncio
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import shutil
import time

import httpx
import jsonschema
import typer

from dfm12.io import atomic, digest, file_hash, load, lock, write_json
from dfm12 import multilingual_tasks as tasks
from dfm12 import multilingual_generation_v4 as generation
from dfm12 import multilingual_review_indexed as checks
from dfm14.calibrate import MODEL, configure, audit_record
from dfm14.catalog import LANGUAGES
from dfm14.generation_prepare import factory
from dfm14.generation_contract import VERSION, generation_payload, review_payload, json_transport
from dfm14.synthetic_quality import assemble, source_issues
from dfm14.synthetic_review import keeps
from dfm14.production_seeds import ROOT

app = typer.Typer()
SMALL = {'ga','mt','mk','eu','gl','cy'}
KNOWLEDGE = dict(textbook=150000,science=100000,commonsense=100000,
                 explanatory_qa=75000,evidence=25000,math=50000)


def plan(chunk_size=128):
    groups = []
    for language in LANGUAGES:
        multiplier = 14 if language in SMALL else 7
        for family, count in tasks.QUOTAS.items():
            groups.append(dict(language=language,family=family,target=count*multiplier,kind='multilingual'))
    groups += [dict(language='en',family=k,target=v,kind='knowledge') for k,v in KNOWLEDGE.items()]
    jobs = []
    for start in range(0,max(g['target'] for g in groups),chunk_size):
        for g in groups:
            if start < g['target']:
                jobs.append(dict(g,start=start,end=min(start+chunk_size,g['target']),
                    job_id=f'{g["language"]}-{g["family"]}-{start:06d}'))
    return groups,jobs


def pins():
    paths = [Path(__file__),Path('dfm14/production_seeds.py'),Path('dfm14/calibrate.py'),
             Path('dfm14/generation_contract.py'),Path('dfm14/synthetic_quality.py'),
             Path('dfm14/synthetic_review.py'),Path(tasks.__file__),Path(generation.__file__),
             Path('dfm12/multilingual_calibration_v6.py'),Path('dfm12/multilingual_tool_dialogue.py'),
             Path('dfm12/multilingual_references.py')]
    return {str(p):file_hash(p) for p in paths}


@app.command()
def prepare(root:Path=ROOT):
    groups,jobs=plan()
    with lock(root/'.prepare.lock'):
        if (root/'manifest.json').exists():
            raise ValueError('Prepared production already exists; use run to resume')
        authorization=dict(decision='owner_closed_calibration_and_requested_all_pending_generation',
            date='2026-10-07',diagnostic_pass=False,production_authorized=True,training_admission_authorized=False,
            known_risk='v6 review regression: six false accepts and four errors among 18 exposed controls',
            evidence={str(p):file_hash(p) for p in [Path('data/dfm14/quality-calibration-v6/summary.json'),
                Path('data/dfm14/review-regression-v6/summary.json')]})
        write_json(root/'authorization.json',authorization)
        write_json(root/'manifest.json',dict(contract=VERSION,groups=groups,jobs=jobs,
            target=sum(g['target'] for g in groups),attempts_per_slot=2,
            concurrency_per_endpoint=128,model=MODEL,code_pins=pins(),
            authorization_sha256=file_hash(root/'authorization.json'),training_ready=False,
            note='70K for six smaller European languages; 35K for ten others; 500K English knowledge pilot. Review every candidate. Report exhausted slots, never silently lower targets.'))
    print(len(jobs),sum(g['target'] for g in groups),flush=True)


class Pools:
    def __init__(self,root): self.root,self.cache=root,{}
    def get(self,name):
        if name not in self.cache:
            path=self.root/'seeds'/(name+'.json')
            receipt=load(self.root/'seeds'/(name+'-receipt.json'))
            if file_hash(path)!=receipt['sha256']:
                raise ValueError('Changed pool '+name)
            self.cache[name]=load(path)
        return self.cache[name]


def specification(job,slot,attempt,pools):
    language,family=job['language'],job['family']
    if job['kind']=='multilingual':
        seeds={language:pools.get(language),'openhermes':pools.get('openhermes')}
        config=dict(contract_version=4,cohort='dfm14-production-v1',
            quotas={k:v*(14 if language in SMALL else 7) for k,v in tasks.QUOTAS.items()})
        spec=factory(language,family,slot,attempt,seeds,config)
        if spec.get('source') and family!='openhermes':spec.pop('topic',None)
        return spec
    seeds=pools.get('knowledge-'+family)
    source=seeds[(slot+attempt*7919)%len(seeds)]
    types=['explain a concept','apply the idea to a hypothetical example','compare or distinguish concepts',
           'diagnose a misconception','answer an evidence-based question','explain a cause and its limits']
    return dict(language='English',language_code='en',family=family,slot=slot,variant=attempt,
                source=source,task=types[slot%len(types)],cohort='dfm14-knowledge-v1')


def knowledge_request(spec):
    source=spec['source']
    properties={k:dict(type='string',minLength=1) for k in ('user','assistant')}
    schema=dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
    task=('Create a new English instruction and a correct, self-contained answer. '
          'Vary the wording, level and scenario. Actually perform the task, not promise it. '
          'Do not mention data generation, audits, source IDs or CPU scaffolding. '
          'No tool-call or chat delimiters. No fabricated evidence or external facts. '
          'Use at most 1500 tokens for the answer. Return only user and assistant JSON fields. ')
    if spec['family']=='commonsense':
        task+=('Use the provided event and plausible relations to create a concrete hypothetical scenario. '
               'Replace PersonX/PersonY/placeholders consistently; do not present plausible outcomes as certainties. ')
    elif spec['family']=='math':
        task+=('Adapt ONE supplied math problem, preserving its mathematical meaning, constants and correct solution. '
               'The user must explicitly request brief reasoning and exactly one final \\boxed{...} answer. '
               'The assistant must fulfill that format. Do not put reference answers in the user message. ')
    else:
        task+=('The evidence text will be appended verbatim to the student user request. Do not copy it into your JSON user field. '
               'Ground all answer claims in that text; distinguish author claims from established facts. ')
    payload=dict(model=MODEL,temperature=.5,max_tokens=4096,chat_template_kwargs=dict(enable_thinking=False),
        messages=[dict(role='system',content=task),dict(role='user',content=json.dumps(spec,ensure_ascii=False))])
    return json_transport(payload,schema),schema


def knowledge_assemble(spec,value):
    from dfm12.records import validate_messages
    from dfm14.native_instructions import count
    user=value['user']
    if spec['source'].get('text'):
        user+='\n\nSource text:\n'+spec['source']['text']
    messages=[dict(role='user',content=user),dict(role='assistant',content=value['assistant'])]
    validate_messages(messages)
    if spec['family']=='math' and ('\\boxed{' not in user or value['assistant'].count('\\boxed{')!=1):
        raise ValueError('Math answer contract missing')
    candidate=dict(language='en',family=spec['family'],messages=messages,tools=[],provenance=spec,
                   training_ready=False,admission_authorized=False)
    renderer=generation._renderer()
    candidate['rendered_tokens']=count(candidate,renderer,4096)
    return candidate


async def attempt_one(client,endpoint,job,slot,attempt,pools,budget):
    spec=specification(job,slot,attempt,pools)
    result=dict(slot=slot,attempt=attempt,language=job['language'],family=job['family'],
                spec_sha256=digest(spec),training_ready=False,raw={})
    async def request(payload,kind):
        budget.measure(payload)
        # The slot loop owns the one-retry budget, including transport failures.
        response=await client.post(endpoint+'/chat/completions',json=payload)
        response.raise_for_status();body=response.json()
        result['raw'][kind]=dict(payload_sha256=digest(payload),response=body)
        choice=body['choices'][0]
        if choice['finish_reason']!='stop':raise ValueError('Incomplete '+kind)
        return generation._parse(choice['message']['content'])
    try:
        if job['kind']=='multilingual':
            if source_issues(spec):raise ValueError('Source preflight failed')
            payload,schema=generation_payload(spec,generation,MODEL)
        else:payload,schema=knowledge_request(spec)
        value=await request(payload,'generation');jsonschema.validate(value,schema)
        candidate=assemble(spec,value,generation) if job['kind']=='multilingual' else knowledge_assemble(spec,value)
        if job['kind']=='multilingual':
            record=audit_record(candidate)
            deterministic=checks.deterministic_checks(record)
            result['checks']=deterministic
            if not all(c['passed'] for c in deterministic):raise ValueError('Reference/trajectory check failed')
        else:
            record=dict(language='en',language_name='English',family=spec['family'],messages=candidate['messages'],
                        tools=[],source=spec['source'])
            if spec['family']=='commonsense':
                record['source']=dict(text=json.dumps(spec['source'],ensure_ascii=False))
        result['candidate']=candidate
        review=await request(review_payload(record,MODEL),'review')
        result.update(status='accepted' if keeps(review,record) else 'rejected',review=review)
    except (ValueError,KeyError,TypeError,httpx.HTTPError,jsonschema.ValidationError) as exc:
        result.update(status='error',error_type=type(exc).__name__,error=str(exc)[:1200])
    return result


def recover(path):
    records={}
    if path.exists():
        with path.open('r+b') as f:
            while True:
                pos=f.tell();line=f.readline()
                if not line:break
                if not line.endswith(b'\n'):f.truncate(pos);break
                r=json.loads(line);key=(r['slot'],r['attempt'])
                if key in records:raise ValueError('Duplicate journal attempt')
                records[key]=r
    return records


async def execute(root,endpoint,concurrency):
    manifest=load(root/'manifest.json');budget=configure();pools=Pools(root)
    async with httpx.AsyncClient(timeout=900,limits=httpx.Limits(max_connections=concurrency,max_keepalive_connections=concurrency)) as client:
        models=await client.get(endpoint+'/models');models.raise_for_status()
        if not any(m['id']==MODEL and m.get('max_model_len',0)>=32768 for m in models.json()['data']):
            raise ValueError('Wrong shared teacher')
        for job in manifest['jobs']:
            folder=root/'jobs'/job['job_id']
            try:
                with lock(folder/'.lock'):
                    if (folder/'receipt.json').exists():continue
                    journal=folder/'attempts.jsonl';records=recover(journal)
                    semaphore=asyncio.Semaphore(concurrency)
                    write_json(folder/'progress.json',dict(endpoint=endpoint,phase='running',job=job))
                    with journal.open('a') as out:
                        async def slot_work(slot):
                            if any(r['slot']==slot and r['status']=='accepted' for r in records.values()):
                                return
                            for attempt in range(manifest['attempts_per_slot']):
                                previous=records.get((slot,attempt))
                                if previous:
                                    if previous['status']=='accepted':return
                                    continue
                                async with semaphore:
                                    result=await attempt_one(client,endpoint,job,slot,attempt,pools,budget)
                                out.write(json.dumps(result,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno())
                                records[(slot,attempt)]=result
                                write_json(folder/'progress.json',dict(endpoint=endpoint,attempts=len(records),
                                    accepted=sum(r['status']=='accepted' for r in records.values()),target=job['end']-job['start']))
                                if result['status']=='accepted':return
                        await asyncio.gather(*(slot_work(s) for s in range(job['start'],job['end'])))
                    counts=dict(Counter(r['status'] for r in records.values()))
                    write_json(folder/'receipt.json',dict(job=job,counts=counts,endpoint=endpoint,
                        target=job['end']-job['start'],shortfall=job['end']-job['start']-counts.get('accepted',0),
                        journal_sha256=file_hash(journal),training_ready=False))
                    print(json.dumps(dict(job=job['job_id'],counts=counts)),flush=True)
            except BlockingIOError:continue


def worker(root,endpoint,concurrency):asyncio.run(execute(root,endpoint,concurrency))


@app.command()
def restart_contract(root:Path=ROOT):
    """Archive old attempts, retain accepted rows verbatim, reset other slots."""
    with lock(root/'.controller.lock'):
        archive=root/'history'/VERSION
        archive.mkdir(parents=True,exist_ok=True)
        if (archive/'receipt.json').exists():
            raise ValueError('Contract restart already completed; use run')
        previous=archive/'manifest.json'
        if not previous.exists():shutil.copy2(root/'manifest.json',previous)
        count=0
        for folder in (root/'jobs').iterdir():
            if not folder.is_dir():continue
            with lock(folder/'.lock'):
                backup=archive/'jobs'/folder.name
                backup.mkdir(parents=True,exist_ok=True)
                for name in ('attempts.jsonl','receipt.json','progress.json'):
                    source=folder/name;target=backup/name
                    if source.exists() and not target.exists():shutil.copy2(source,target)
                journal=backup/'attempts.jsonl'
                if journal.exists():
                    accepted=[];slots=set()
                    with journal.open() as handle:
                        for line in handle:
                            if not line.endswith('\n'):break
                            row=json.loads(line)
                            if row['status']=='accepted':
                                if row['slot'] in slots:raise ValueError('Duplicate accepted slot')
                                slots.add(row['slot']);accepted.append(line)
                    with atomic(folder/'attempts.jsonl') as handle:handle.writelines(accepted)
                    count+=len(accepted)
                for name in ('receipt.json','progress.json'):(folder/name).unlink(missing_ok=True)
        manifest=load(previous)
        manifest.update(contract=VERSION,attempts_per_slot=2,code_pins=pins(),
                        restart_archive=str(archive),retained_accepted=count)
        write_json(root/'manifest.json',manifest)
        write_json(archive/'receipt.json',dict(retained_accepted=count,old_manifest_sha256=file_hash(previous),
            new_manifest_sha256=file_hash(root/'manifest.json'),source_audits_changed=False))
        write_json(root/'state.json',dict(phase='ready_to_restart',retained_accepted=count))
        print(json.dumps(dict(retained_accepted=count,archive=str(archive))),flush=True)


@app.command()
def run(root:Path=ROOT,concurrency:int=128):
    if not 1<=concurrency<=128:raise ValueError('Concurrency 1..128')
    manifest=load(root/'manifest.json')
    if manifest['code_pins']!=pins():raise ValueError('Production code changed')
    if file_hash(root/'authorization.json')!=manifest['authorization_sha256']:raise ValueError('Approval changed')
    if not load(root/'authorization.json')['production_authorized']:raise ValueError('No owner authorization')
    with lock(root/'.controller.lock'):
        while not (root/'seed-manifest.json').exists():
            write_json(root/'state.json',dict(phase='waiting_for_seeds',pid=os.getpid()));time.sleep(10)
        write_json(root/'state.json',dict(phase='running',pid=os.getpid(),concurrency_per_endpoint=concurrency))
        with ProcessPoolExecutor(max_workers=8) as pool:
            futures=[pool.submit(worker,root,f'http://127.0.0.1:{p}/v1',concurrency) for p in range(8800,8808)]
            for future in futures:future.result()
        counts=Counter();shortfall=0
        for path in (root/'jobs').glob('*/receipt.json'):
            receipt=load(path);counts.update(receipt['counts']);shortfall+=receipt['shortfall']
        write_json(root/'state.json',dict(phase='finished_attempts',counts=dict(counts),shortfall=shortfall,
            training_ready=False,remaining=['cross-shard/inherited deduplication','accepted-only export','tokenization']))


if __name__=='__main__':app()
