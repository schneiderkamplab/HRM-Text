"""Development acceptance selection using only the other two model judges."""
import asyncio
from collections import defaultdict
import time
import httpx
from audit_pipeline.runtime import run
from dfm12.io import rows,load,write_json,file_hash
from scripts.dfm16_story_calibration import immutable,immutable_rows
from scripts.dfm16_staged_experiment import MODELS,generated_records,verify
from scripts.dfm16_staged_controls import controls
from scripts.dfm16_staged_audit import StagedAudit,checks
from scripts.dfm16_language_qualification import select_policy
from scripts.dfm16_experiment_transport import Budget,ExperimentClient
from scripts.queue_dfm16_stories_qwen import prepare_stage,audited_records


def prepare(root):
    verify(root)
    selection=load(root/'decisions/generator-screen.json')['selected']
    labels={r['id']:r for r in rows(root/'labels/manual-labels.jsonl')}
    mapping={r['source_id']:r['id'] for r in rows(root/'labels/provenance-private.jsonl')}
    bank=list(controls())
    immutable_rows(root/'sources/controls.jsonl',bank)
    records=[]
    for language,generator in selection.items():
        if generator is None:continue
        for source,result in generated_records(root,generator):
            if source['language']!=language:continue
            label=labels[mapping[source['id']]]
            records.append(dict(source,messages=result.get('messages',[]),cohort='development',
                label=label['final_label'],generator=generator,
                deterministic_pass=result['status']=='generated'))
        records.extend(dict(r,generator=generator) for r in bank if r['language']==language)
    immutable_rows(root/'votes/parents-private.jsonl',records)
    requests=[]
    for record in records:
        if record['messages']:
            requests.extend(checks(record))
    immutable_rows(root/'votes/checks.jsonl',requests)
    by_id={r['id']:r for r in records}
    for name in MODELS:
        selected=[r for r in requests if by_id[r['parent_id']]['generator']!=name]
        prepare_stage(root/'votes'/name,selected,'staged_role_checks')
    immutable(root/'votes/prejudge-receipt.json',dict(controls_sha256=file_hash(root/'sources/controls.jsonl'),
        manual_labels_sha256=file_hash(root/'labels/manual-labels.jsonl'),checks_sha256=file_hash(root/'votes/checks.jsonl')))


async def execute(root,name,key=None):
    verify(root)
    receipt=load(root/'votes/prejudge-receipt.json')
    for field,path in [('controls_sha256','sources/controls.jsonl'),('manual_labels_sha256','labels/manual-labels.jsonl'),('checks_sha256','votes/checks.jsonl')]:
        if receipt[field]!=file_hash(root/path):raise ValueError('blinded evidence changed')
    stage=root/'votes'/name
    model,endpoint=MODELS[name]
    adapter=StagedAudit(stage,stage/'audit',endpoint);adapter.model=model
    n=64 if name=='odin' else 128
    budget=Budget(root/'odin-requests.sqlite')
    if name=='odin' and not key:raise ValueError('ODIN_API_KEY required')
    kwargs=dict(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=n))
    client=ExperimentClient(budget,headers={'Authorization':'Bearer '+key},**kwargs) if name=='odin' else httpx.AsyncClient(**kwargs)
    start=time.monotonic()
    write_json(stage/'audit/pipeline/state.json',dict(phase='running'))
    try:
        await run(adapter,endpoint,n,client=client,prefetch=1)
        for job in load(stage/'manifest.json')['chunks']:adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
    except BaseException:
        write_json(stage/'audit/pipeline/state.json',dict(phase='interrupted_or_failed'));raise
    finally:
        write_json(stage/'timing.json',dict(seconds=time.monotonic()-start))
        write_json(root/'reports/odin-usage.json',budget.summary(6.25,25))


def report(root):
    verify(root)
    parents=list(rows(root/'votes/parents-private.jsonl'))
    all_checks=list(rows(root/'votes/checks.jsonl'))
    votes={name:{r['id']:result.get('review',{}).get('decision','unresolved')
        for r,result in audited_records(root/'votes'/name)} for name in MODELS}
    scored=[]
    for parent in parents:
        relevant=[c['id'] for c in all_checks if c['parent_id']==parent['id']]
        whole={}
        for name in MODELS:
            if name==parent['generator']:continue
            values=[votes[name].get(identifier,'unresolved') for identifier in relevant]
            whole[name]='unresolved' if not values or any(v not in ('accept','reject') for v in values) else 'reject' if 'reject' in values else 'accept'
        scored.append(dict(parent,votes=whole))
    immutable_rows(root/'votes/votes.jsonl',scored)
    selection=load(root/'decisions/generator-screen.json')['selected']
    reports={language:select_policy([r for r in scored if r['language']==language],generator)
        for language,generator in selection.items() if generator is not None}
    immutable(root/'decisions/policy-selection.json',dict(languages=reports,development_only=True,
        synthetic_controls_correlated=True,bounds_are_not_population_qualification=True,production_authorized=False))
    return reports
