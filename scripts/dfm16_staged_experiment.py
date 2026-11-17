"""Versioned staged-generation experiment controller; never promotes production.

init --root DIR
prepare --root DIR --sources reviewed.jsonl
run --root DIR --arm legacy|flash|qwen27b|odin
packet --root DIR
labels --root DIR --labels blinded-labels.jsonl
screen --root DIR

All model work goes through audit_pipeline.run, not another scheduler. Keep the
controller lock for each operation; the Odin ledger covers every actual send.
"""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import random
import time

import httpx
from audit_pipeline.runtime import run
from dfm12.io import file_hash,load,lock,rows,write_json
from scripts.dfm16_story_calibration import immutable,immutable_rows,sha
from scripts.dfm16_staged_stories import LANGUAGES,TASKS,TEMPLATES,POLICY,StagedGenerate,validate_source,initial_request,payload
from scripts.dfm16_judge_ensemble_study import MODELS
from scripts.dfm16_role_pilot import PilotGenerate
from scripts.dfm16_story_v3 import spec_for,request as legacy_request
from scripts.queue_dfm16_stories_qwen import prepare_stage,audited_records
from scripts.dfm16_experiment_transport import Budget,ExperimentClient
from scripts.dfm16_language_qualification import select_generator

ARMS=('legacy','flash','qwen27b','odin')
CODE=('scripts/dfm16_staged_stories.py','scripts/dfm16_staged_experiment.py',
      'scripts/dfm16_staged_audit.py','scripts/dfm16_language_qualification.py',
      'scripts/dfm16_staged_controls.py','scripts/dfm16_staged_validation.py','scripts/dfm16_staged_sources.py',
      'scripts/dfm16_staged_policy.py',
      'scripts/dfm16_experiment_transport.py','audit_pipeline/runtime.py',
      'audit_pipeline/dfm14.py','audit_pipeline/review.py',
      'scripts/dfm16_story_v3.py','scripts/dfm16_story_adapter.py','scripts/dfm16_story_quality.py',
      'scripts/dfm16_role_pilot.py',
      'scripts/dfm16_story_calibration.py','scripts/queue_dfm16_stories_qwen.py')


def design():
    return dict(policy=POLICY,models=MODELS,arms=ARMS,languages=LANGUAGES,tasks=TASKS,
        templates=TEMPLATES,source_process='Immutable manually reviewed target-language source; Danish translation once before reuse; reject unintelligible meaning.',
        development=dict(families_per_language=20,per_task=4,conversations=320,seed=2026102903,
            first_clear_minimum=10,task_and_legacy_gates=False,
            objective='Prioritize low false acceptance; development is exploratory.'),
        generation=dict(temperature=.3,completion_tokens=6144,thinking=False,objective_corrections=1,transport_retries=1,
            ignore_reported_reasoning_token_counts=True),
        review=dict(completion_tokens=32,thinking=False,retries=1,parser='exact stripped accept/reject',unit='complete conversation',self_review=False),
        policies=['first_other_judge','second_other_judge','both','either'],
        controls=dict(pairs_per_language=40,frozen_before_votes=True),
        validation=dict(per_language=800,per_task=160,min_clear=300,min_bad=100,
            supplementary=800,supplementary_trigger='one time only, blinded class counts insufficient',
            false_acceptance_upper95_lt=.05,clean_withholding_upper95_le=.20,
            task_point_estimates_required=True),
        concurrency=dict(local=128,odin=64),odin_rolling_minute_cap=100,
        monetary_cap=None,reference='provisional assistant-manual',production_authorized=False,
        software={p:file_hash(Path(p)) for p in CODE})


def initialize(root):
    immutable(root/'design.json',design())
    for directory in ('sources','templates','generation','labels','votes','decisions','reports'):
        (root/directory).mkdir(parents=True,exist_ok=True)
    immutable(root/'templates/native-requests.json',dict(templates=TEMPLATES,
        reviewer='assistant-manual',provisional=True,review_scope='surrounding wording; each source-specific slot requires separate review'))
    if not (root/'status.json').exists():
        write_json(root/'status.json',dict(phase='awaiting_reviewed_sources',languages={l:'held: development not complete' for l in LANGUAGES},production_authorized=False))


def verify(root):
    if load(root/'design.json') != json.loads(json.dumps(design())):
        raise ValueError('Changed software/design: create a new version, never reseal this experiment')


def prepare(root,source_path):
    verify(root)
    sources=list(rows(source_path))
    if len(sources)!=80 or len({s['family'] for s in sources})!=80:
        raise ValueError('Exactly 80 additional unique reviewed families required')
    if Counter((s['language'],s['task']) for s in sources)!=Counter({(l,t):4 for l in LANGUAGES for t in TASKS}):
        raise ValueError('20 per language, four per task required')
    from scripts.dfm16_staged_sources import verify_novelty
    novelty=verify_novelty(root,sources)
    for s in sources:
        validate_source(s)
        if s.get('novelty_receipt') != novelty:
            raise ValueError('Source family exclusion receipt required')
        initial_request(s)
    immutable_rows(root/'sources/reviewed.jsonl',sources)
    jobs=[]
    for source in sources:
        for arm in ARMS:
            identifier=sha([source['family'],arm,POLICY])
            jobs.append(dict(source,id=identifier,audit_id=identifier,arm=arm))
    random.Random(2026102903).shuffle(jobs)
    immutable_rows(root/'generation/order.jsonl',jobs)
    prepare_stage(root/'generation'/'matched',jobs,POLICY)
    for arm in ARMS:
        records=[r for r in jobs if r['arm']==arm]
        immutable_rows(root/'generation'/arm/'inputs.jsonl',records)
        prepare_stage(root/'generation'/arm,records,POLICY)
    write_json(root/'status.json',dict(phase='prepared_development',production_authorized=False))


class LegacyGenerate(StagedGenerate):
    """Historical whole-conversation prompt, same source and sampled limits.

    Keep the original prompt's assembly failure modes; override common decoding
    settings only. First response is never silently regenerated.
    """
    def prepare(self,row):
        from scripts.dfm16_staged_stories import band
        spec=dict(language_mode='monolingual')
        if row['task'] in ('creative','revision'):spec['topic']=row['topic']
        if row['task']=='rewrite':spec['operation']='change past narration to present tense; preserve events'
        if row['task']=='qa':spec['question']=row['question']
        if row['task'] in ('creative','rewrite','revision'):
            lo,hi=band(row['source']['text'],row['language'])
            spec['length_characters' if row['language']=='ja' else 'length_words']=f'{lo}-{hi}'
        if row['task']=='revision':
            spec['revision_operations']=['change only the opening paragraph','change only the ending paragraph','revert the first requested change while retaining the second']
            spec['paragraph_changes']=row['changes']
        row.update(seed=row['source']['text'],specification=spec,revisions=len(spec.get('revision_operations',[])))
        result=legacy_request(row,self.model)
        result['messages'][0]['content']=result['messages'][0]['content'].replace(
            'The supplied seed has been independently screened.',
            'The authoritative source has provisional assistant-manual review.')
        if row['task']=='revision':
            result['messages'][0]['content']+='\nUse the supplied paragraph_changes for the opening and ending edits. Restate the total length limits in every revision request. Do not invent different edit operations.'
        result.update(temperature=.3,max_tokens=6144,chat_template_kwargs={'enable_thinking':False})
        # Controlled task slots are shared across arms; whole-conversation prose
        # remains generated, the essential historical comparison.
        result['messages'][0]['content']+='\nUse this exact first user request as the task specification:\n'+initial_request(row)
        return result

    async def process(self,item,http,cpu,disk):
        from copy import deepcopy
        row=deepcopy(item[1])
        request=await cpu.call(self.prepare,row)
        record=await disk.call(self.begin,row,'legacy',0,request)
        if record is None:
            try:
                started=time.monotonic()
                record=dict(response=await http.post(request),seconds=time.monotonic()-started)
            except httpx.HTTPError as exc:record=dict(error=type(exc).__name__)
            await disk.call(self.finish_stage,row,'legacy',0,request,record)
        result=dict(audit_id=row['audit_id'],input_id=row['id'],policy=POLICY,status='unresolved',attempts=[record])
        if 'response' in record:
            try:
                candidate,contract=await cpu.call(PilotGenerate.decode,record['response'],row)
                result.update(status='generated',candidate=candidate,cpu=contract,messages=candidate['messages'],
                    first_attempt_contract_clear=contract['status']=='pass')
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                result['error']=type(exc).__name__
        result['seconds']=record.get('seconds',0)
        await disk.call(self.commit,item,result)


class MatchedGenerate(StagedGenerate):
    model='staged-matched-experiment'
    async def process(self,item,http,cpu,disk):
        # Per-item adapter instances share only the disk-owned journal state.
        # Never mutate a shared model field while requests are concurrent.
        arm=item[1]['arm']
        child=(LegacyGenerate if arm=='legacy' else StagedGenerate)(self.root,self.output,self.endpoint)
        child.opened=self.opened
        child.model=MODELS['flash' if arm=='legacy' else arm][0]
        await child.process(item,http,cpu,disk)


class MatchedClient:
    def __init__(self,root,key):
        self.clients={}
        self.budget=Budget(root/'odin-requests.sqlite')
        for name in MODELS:
            kwargs=dict(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=64 if name=='odin' else 128))
            self.clients[name]=ExperimentClient(self.budget,headers={'Authorization':'Bearer '+key},**kwargs) if name=='odin' else httpx.AsyncClient(**kwargs)
        self.slots={name:asyncio.Semaphore(64 if name=='odin' else 128) for name in MODELS}

    async def get(self,url):
        # All discovery uses the same metered clients as completion requests.
        for name,(model,endpoint) in MODELS.items():
            response=await self.clients[name].get(endpoint+'/models')
            response.raise_for_status()
            if model not in {m['id'] for m in (await asyncio.to_thread(response.json))['data']}:raise ValueError('required model missing: '+name)
        return httpx.Response(200,json={'data':[{'id':MatchedGenerate.model,'max_model_len':0}]},request=httpx.Request('GET',url))

    async def post(self,url,content,headers):
        request=await asyncio.to_thread(json.loads,content)
        name=next(name for name,(model,_) in MODELS.items() if model==request['model'])
        async with self.slots[name]:
            return await self.clients[name].post(MODELS[name][1]+'/chat/completions',content=content,headers=headers)

    async def aclose(self):
        for client in self.clients.values():await client.aclose()


async def execute_matched(root,key):
    verify(root)
    if not key:raise ValueError('ODIN_API_KEY required')
    stage=root/'generation'/'matched'
    adapter=MatchedGenerate(stage,stage/'audit','http://matched.invalid/v1')
    client=MatchedClient(root,key)
    start=time.time()
    write_json(stage/'audit/pipeline/state.json',dict(phase='running'))
    try:
        await run(adapter,'http://matched.invalid/v1',256,client=client,prefetch=1)
        for job in load(stage/'manifest.json')['chunks']:adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
    except BaseException:
        write_json(stage/'audit/pipeline/state.json',dict(phase='interrupted_or_failed'));raise
    finally:
        write_json(stage/'timing.json',dict(seconds=time.time()-start))
        write_json(root/'reports/odin-usage.json',client.budget.summary(6.25,25))


def generated_records(root,arm):
    matched=root/'generation'/'matched'
    if (matched/'audit/pipeline/state.json').exists():
        return [(r,v) for r,v in audited_records(matched) if r['arm']==arm]
    return list(audited_records(root/'generation'/arm))


async def execute(root,arm,key=None):
    verify(root)
    stage=root/'generation'/arm
    name='flash' if arm=='legacy' else arm
    model,endpoint=MODELS[name]
    adapter=(LegacyGenerate if arm=='legacy' else StagedGenerate)(stage,stage/'audit',endpoint)
    adapter.model=model
    if name=='odin' and not key:raise ValueError('ODIN_API_KEY required')
    n=64 if name=='odin' else 128
    budget=Budget(root/'odin-requests.sqlite')
    kwargs=dict(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=n))
    client=ExperimentClient(budget,headers={'Authorization':'Bearer '+key},**kwargs) if name=='odin' else httpx.AsyncClient(**kwargs)
    start=time.time()
    write_json(stage/'audit/pipeline/state.json',dict(phase='running'))
    try:
        await run(adapter,endpoint,n,client=client,prefetch=1)
        for job in load(stage/'manifest.json')['chunks']:
            adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
    except BaseException:
        write_json(stage/'audit/pipeline/state.json',dict(phase='interrupted_or_failed'))
        raise
    finally:
        write_json(stage/'timing.json',dict(seconds=time.time()-start))
        write_json(root/'reports/odin-usage.json',budget.summary(6.25,25))


def packet(root):
    verify(root)
    provenance=[];packet=[]
    for arm in ARMS:
        for source,result in generated_records(root,arm):
            identifier=sha(['blind',source['id']])
            provenance.append(dict(id=identifier,source_id=source['id'],family=source['family'],arm=arm))
            packet.append(dict(id=identifier,language=source['language'],task=source['task'],
                authoritative_source=source['source']['text'],messages=result.get('messages',result.get('candidate',{}).get('messages')),
                status=result['status'],stages={name:dict(attempts=[dict(text=a.get('text'),findings=a.get('findings'),error=a.get('error')) for a in stage.get('attempts',[])]) for name,stage in result.get('stages',{}).items()}))
    random.Random(2026102904).shuffle(packet)
    immutable_rows(root/'labels/blind-packet.jsonl',packet)
    immutable_rows(root/'labels/provenance-private.jsonl',provenance)


def import_labels(root,path):
    verify(root)
    labels=list(rows(path));packet=list(rows(root/'labels/blind-packet.jsonl'))
    if len(labels)!=320 or {r['id'] for r in labels}!={r['id'] for r in packet}:raise ValueError('Label all 320 complete examples exactly once')
    if len({r['id'] for r in labels})!=320:raise ValueError('duplicate labels')
    for r in labels:
        if r.get('reviewer')!='assistant-manual' or r.get('blind') is not True or not r.get('note'):raise ValueError('blind provisional manual assessment required')
        for field in ('first_label','final_label'):
            if r.get(field) not in ('clear','bad','borderline','unresolved'):raise ValueError('separate first/final labels required')
        if not all(k in r for k in ('inherited_source_defects','new_user_defects','answer_defects','deterministic_failures','unresolved_attempts')):raise ValueError('all defect categories required')
    immutable_rows(root/'labels/manual-labels.jsonl',labels)
    immutable(root/'labels/receipt.json',dict(packet_sha256=file_hash(root/'labels/blind-packet.jsonl'),labels_sha256=file_hash(root/'labels/manual-labels.jsonl'),provisional=True))


def screen(root):
    verify(root)
    labels={r['id']:r for r in rows(root/'labels/manual-labels.jsonl')}
    provenance={r['source_id']:r for r in rows(root/'labels/provenance-private.jsonl')}
    records=[]
    for arm in ARMS:
        stage=root/'generation'/arm
        timing=root/'generation'/'matched'/'timing.json'
        elapsed=load(timing if timing.exists() else stage/'timing.json')['seconds']/80
        for source,result in generated_records(root,arm):
            key=provenance[source['id']]['id'];label=labels[key]
            usage=[a.get('response',{}).get('usage',{}) for s in result.get('stages',{}).values() for a in s.get('attempts',[])]
            cost=sum((u.get('prompt_tokens',0)*6.25+u.get('completion_tokens',0)*25)/1e6 for u in usage) if arm=='odin' else 0
            records.append(dict(id=key,family=source['family'],language=source['language'],task=source['task'],arm=arm,
                label=label['first_label'],deterministic_pass=result.get('first_attempt_contract_clear',result.get('cpu',{}).get('status')=='pass'),cost=cost,seconds=result.get('seconds',elapsed)))
    result={lang:select_generator([r for r in records if r['language']==lang]) for lang in LANGUAGES}
    immutable(root/'decisions/generator-screen.json',dict(selected=result,records=records,provisional=True,
        cost_note='Local incremental API cost zero; GPU cost unpriced. Odin historical list-price estimate, not an invoice.',production_authorized=False))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['init','prepare','run','run-matched','packet','labels','screen','prepare-judges','judge','policy'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--sources',type=Path)
    p.add_argument('--labels',type=Path);p.add_argument('--arm',choices=ARMS)
    p.add_argument('--judge',choices=list(MODELS))
    a=p.parse_args()
    with lock(a.root/'.controller.lock'):
        if a.action=='init':initialize(a.root)
        elif a.action=='prepare':prepare(a.root,a.sources)
        elif a.action=='run':asyncio.run(execute(a.root,a.arm,os.environ.get('ODIN_API_KEY')))
        elif a.action=='run-matched':asyncio.run(execute_matched(a.root,os.environ.get('ODIN_API_KEY')))
        elif a.action=='packet':packet(a.root)
        elif a.action=='labels':import_labels(a.root,a.labels)
        elif a.action=='screen':print(screen(a.root))
        else:
            from scripts import dfm16_staged_policy as policy
            if a.action=='prepare-judges':policy.prepare(a.root)
            elif a.action=='judge':asyncio.run(policy.execute(a.root,a.judge,os.environ.get('ODIN_API_KEY')))
            else:print(policy.report(a.root))

if __name__=='__main__':main()
