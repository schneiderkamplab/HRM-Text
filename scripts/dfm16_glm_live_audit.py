"""Additional GLM specialist evidence for the entire ongoing production queue.

Uses shared audit_pipeline scheduling. Waits per row for its durable generation
result; records generator identity. This new model's votes cannot promote data.
"""
import argparse
import asyncio
import json
from pathlib import Path
import httpx
from audit_pipeline import review
from audit_pipeline.runtime import run
from dfm12.io import file_hash,load,lock,rows,write_json
from scripts.dfm16_story_calibration import immutable,sha
from scripts.dfm16_english_fullscale import ROOT
from scripts.dfm16_glm_staged_stories import decode, StagedGenerate
from scripts.dfm16_glm_fullscale_adapter import FullscaleGenerate
from scripts.dfm16_specialist_audit_v13 import SCOPES,COMMON,parse_findings,valid_quotes,evidence
from scripts.dfm16_validation_audit import whole_vote
from scripts.dfm16_staged_audit import StagedAudit
from scripts.dfm16_dual_generation import MODEL


def generated(root,job_id,identifier):
    journal=root/'production/audit'/job_id/'results.jsonl'
    if not journal.exists():return None
    with journal.open() as stream:
        for line in stream:
            try:value=json.loads(line)
            except ValueError:continue
            if value.get('audit_id')==identifier:
                if value['status']!='generated':return value,None,None
                source=root/'production/audit/versions'/sha(identifier)/'prepared-source.json'
                parent=dict(load(source),messages=value['messages'])
                reviewer=parent['source']['reviewer']
                model=MODEL if reviewer=='glm-source-and-request-audit' else 'odin-2-large'
                return value,parent,model
    return None


class LiveAudit(StagedAudit):
    context_length=0
    begin=StagedGenerate.begin
    finish_stage=StagedGenerate.finish_stage
    async def process(self,item,http,cpu,disk):
        identifier=item[1]['id']
        value=None
        while value is None:
            value=await cpu.call(generated,ROOT,item[0],identifier)
            if value is None:await asyncio.sleep(5)
        generation,parent,generator=value
        if parent is None:
            await disk.call(self.commit,item,dict(audit_id=identifier,input_id=identifier,
                status='not_generated',generation_status=generation['status'],production_admitted=False));return
        reports={}
        for scope in SCOPES:
            request=review.payload(evidence(parent),MODEL)
            request['messages'][0]['content']=COMMON+'\n'+SCOPES[scope]
            request.pop('chat_template_kwargs',None)
            request.update(max_tokens=4096,reasoning_effort='low',chat_template_kwargs={'reasoning_effort':'low'})
            def parse(body):
                result=parse_findings(decode(body))
                if not valid_quotes(parent,result.get('findings',[])):raise ValueError('nonliteral quotation')
                return result
            result=await FullscaleGenerate.auxiliary(self,item[1],'specialist-'+scope,request,parse,http,cpu,disk)
            reports[scope]=result or dict(decision='unresolved')
        decision=whole_vote(r['decision'] for r in reports.values())
        await disk.call(self.commit,item,dict(audit_id=identifier,input_id=identifier,status='reviewed',
            review=dict(decision=decision),specialists=reports,generator=generator,
            independent_from_generator=generator!=MODEL,generation_sha256=sha(generation),
            production_admitted=False,policy='glm-additional-specialist-v1-unqualified'))


async def execute(root):
    path=root/'glm-additional-audit'
    # Same immutable source chunks preserve correspondence to generation jobs.
    manifest=load(root/'production/manifest.json')
    manifest['chunks']=[dict(j,input=str((root/'production'/j['input']).resolve())) for j in manifest['chunks']]
    immutable(path/'manifest.json',manifest)
    immutable(path/'policy.json',dict(model=MODEL,source_candidates=502000,production_admitted=False,
        thinking='mandatory low effort; final content only is parsed; raw responses retain reasoning',
        purpose='Additional specialist evidence; no inherited accuracy claim or self-review admission',
        pins={str(p):file_hash(p) for p in [Path(__file__),Path('scripts/dfm16_glm_fullscale_adapter.py'),root/'production/manifest.json']}))
    adapter=LiveAudit(path,path/'audit','http://127.0.0.1:8891/v1');adapter.model=MODEL
    client=httpx.AsyncClient(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=128))
    try:await run(adapter,adapter.endpoint,128,client=client,prefetch=1)
    finally:await client.aclose()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args()
    if a.root!=ROOT:raise ValueError('This pinned live follower uses the full-scale root')
    with lock(a.root/'glm-additional-audit/.controller.lock'):asyncio.run(execute(a.root))
