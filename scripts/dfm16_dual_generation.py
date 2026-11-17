"""Disjoint chunk assignment for Odin and GLM; existing runtime owns scheduling."""
import argparse
import asyncio
import os
from pathlib import Path
import httpx
from audit_pipeline.runtime import run
from dfm12.io import load,lock,file_hash,write_json
from scripts.dfm16_story_calibration import immutable
from scripts.dfm16_english_fullscale import ROOT
from scripts.dfm16_english_fullscale_generate import FullscaleGenerate as OdinGenerate
from scripts.dfm16_glm_fullscale_adapter import FullscaleGenerate as GlmGenerate
from scripts.dfm16_experiment_transport import Budget,ExperimentClient
from scripts.dfm16_staged_validation_campaign import BASE

MODEL='zai-org/GLM-5.3-Flash'


def assign(jobs,output):
    plans={'odin':[],'glm':[]};completed=[]
    for job in jobs:
        folder=output/job['job_id']
        if (folder/'receipt.json').exists():completed.append(job['job_id']);continue
        # Pending/partly dispatched chunks retain Odin ownership and stage cache.
        started=folder.exists()
        owner='odin' if started or int(job['job_id'].rsplit('-',1)[1])%32==0 else 'glm'
        plans[owner].append(job)
    return plans,completed


def prepare(root):
    original=load(root/'generation-policy.json')
    for p,h in original['pins'].items():
        if file_hash(Path(p))!=h:raise ValueError('changed original generation freeze')
    plans,completed=assign(load(root/'production/manifest.json')['chunks'],root/'production/audit')
    paths=[Path(__file__),Path('scripts/dfm16_glm_fullscale_adapter.py'),Path('scripts/dfm16_glm_staged_stories.py'),
           root/'production/manifest.json',root/'generation-policy.json']
    immutable(root/'dual-generation/assignment.json',dict(plans=plans,completed=completed,
        source_candidates=502000,additional_candidates=0,
        policy='Preserve started chunks with Odin; route 31/32 untouched chunks to GLM. Immutable disjoint allocation.',
        models={'odin':'odin-2-large','glm':MODEL},pins={str(p):file_hash(p) for p in paths}))


async def execute(root,owner):
    assignment=load(root/'dual-generation/assignment.json')
    for p,h in assignment['pins'].items():
        if file_hash(Path(p))!=h:raise ValueError('changed assignment dependency')
    cls=OdinGenerate if owner=='odin' else GlmGenerate
    jobs=assignment['plans'][owner]
    class Assigned(cls):
        def initialize(self):self.jobs=iter(jobs)
    endpoint='https://api.odincore.ai/v1' if owner=='odin' else 'http://127.0.0.1:8890/v1'
    # Different telemetry directories avoid races; original per-chunk and stage
    # outputs stay shared so completed attempts are never regenerated.
    class Reported(Assigned):
        def report(self,snapshot):
            write_json(root/'dual-generation'/owner/'telemetry.json',snapshot)
    adapter=Reported(root/'production',root/'production/audit',endpoint)
    adapter.model=assignment['models'][owner]
    kwargs=dict(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=64 if owner=='odin' else 128))
    if owner=='odin':
        budget=Budget(BASE/'odin-requests.sqlite')
        client=ExperimentClient(budget,headers={'Authorization':'Bearer '+os.environ['ODIN_API_KEY']},**kwargs)
    else:client=httpx.AsyncClient(**kwargs)
    write_json(root/'dual-generation'/owner/'status.json',dict(phase='running',assigned_rows=sum(j['rows'] for j in jobs)))
    try:
        await run(adapter,endpoint,64 if owner=='odin' else 128,client=client,prefetch=1)
        for job in jobs:await asyncio.to_thread(adapter.verify_receipt,job,adapter.output/job['job_id'])
        await asyncio.to_thread(write_json,root/'dual-generation'/owner/'status.json',dict(phase='complete'))
    finally:await client.aclose()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','odin','glm']);p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args()
    if a.action=='prepare':
        with lock(BASE/'.controller.lock'),lock(a.root/'.controller.lock'):prepare(a.root)
    elif a.action=='odin':
        with lock(BASE/'.controller.lock'),lock(a.root/'dual-generation/.odin.lock'):
            asyncio.run(execute(a.root,a.action))
    else:
        with lock(a.root/'dual-generation/.glm.lock'):
            asyncio.run(execute(a.root,a.action))
