"""Explicit combined production policy; GPU requests are a separate manual action.

Reuse shared runtime/adapters; preserve the generation software freeze and receipts.
"""
import argparse
import asyncio
from pathlib import Path
import httpx
from audit_pipeline.runtime import run
from dfm12.io import load, lock, rows, file_hash, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows
from scripts import dfm16_english_production as production
from scripts.dfm16_staged_stories import StagedGenerate
from scripts.dfm16_staged_audit import StagedAudit, checks
from scripts.dfm16_staged_precision import PrecisionAudit, supplemental_checks
from scripts.dfm16_specialist_audit_v13 import VerifyFinding, verification_jobs, decisions
from scripts.dfm16_validation_audit import whole_vote
from scripts.queue_dfm16_stories_qwen import prepare_stage, audited_records
from scripts.dfm16_staged_experiment import MODELS
from scripts.dfm16_staged_validation_campaign import BASE


def validate_generation(root):
    production.verify(root)
    path=root/'generation'
    adapter=StagedGenerate(path,path/'audit',MODELS['odin'][1]);adapter.model=MODELS['odin'][0]
    for job in load(path/'manifest.json')['chunks']:
        adapter.verify_receipt(job,path/'audit'/job['job_id'])
    values=list(audited_records(path))
    expected=[dict(r,messages=v['messages']) for r,v in values if v['status']=='generated']
    parents=list(rows(root/'parents.jsonl'))
    if parents!=expected:
        raise ValueError('parents differ from receipted generation')
    return parents


def prepare(root):
    parents=validate_generation(root)
    policy=dict(policy='focused_v7_plus_verified_v13',generator='odin',
        independent_reviewers=['flash','qwen27b'],specialist='odin',
        specialist_scopes=['fidelity','instructions','grammar'],
        acceptance='All focused checks from both independent judges and verified specialist aggregation accept; missing/invalid required verdicts withheld.',
        selected_by='User: the best configuration, also if that means waiting for the GPUs.',
        production_authorized=True,statistically_qualified=False,
        development_false_acceptance='16/136',development_clear_withholding='146/594',
        development_retained='478/800',
        self_review_alone_can_admit=False,local_concurrency_per_server=128,
        capacity_split='4/4 requested; server allocation remains externally owned',
        software={str(p):file_hash(p) for p in [Path(__file__),
            Path('scripts/dfm16_staged_audit.py'),Path('scripts/dfm16_staged_precision.py'),
            Path('scripts/dfm16_specialist_audit_v13.py'),Path('scripts/dfm16_validation_audit.py')]})
    immutable(root/'selected-policy.json',policy)
    for kind,builder in [('base',checks),('precision',supplemental_checks)]:
        requests=[r for p in parents for r in builder(p)]
        immutable_rows(root/'focused'/f'{kind}-inputs.jsonl',requests)
        for judge in ('flash','qwen27b'):
            path=root/'focused'/kind/judge
            immutable_rows(path/'inputs.jsonl',requests)
            prepare_stage(path,requests,'english_production_focused')
    immutable(root/'combined-input-receipt.json',dict(pins={str(p):file_hash(p) for p in [
        root/'selected-policy.json',root/'parents.jsonl',root/'generation-outcomes.jsonl',
        root/'focused/base-inputs.jsonl',root/'focused/precision-inputs.jsonl']}))
    write_json(root/'combined-status.json',dict(phase='prepared_waiting_for_gpu_judges',admitted=0))


def verify(root):
    production.verify(root)
    for pins in (load(root/'selected-policy.json')['software'],load(root/'combined-input-receipt.json')['pins']):
        for path,digest in pins.items():
            if file_hash(Path(path))!=digest:raise ValueError('changed combined dependency: '+path)


def verified_stage(path,cls,judge):
    model,endpoint=MODELS[judge]
    adapter=cls(path,path/'audit',endpoint);adapter.model=model
    for job in load(path/'manifest.json')['chunks']:
        adapter.verify_receipt(job,path/'audit'/job['job_id'])
    return list(audited_records(path))


async def odin(root):
    verify(root)
    await production.audit(root)
    parents=await asyncio.to_thread(validate_generation,root)
    values=await asyncio.to_thread(verified_stage,root/'specialists',production.Specialist,'odin')
    screen,jobs=await asyncio.to_thread(verification_jobs,parents,values)
    values=await production.execute_stage(root,'verification',VerifyFinding,jobs)
    votes={r['id']:v.get('review',{}).get('decision','unresolved') for r,v in values}
    await asyncio.to_thread(immutable_rows,root/'verified-specialist-decisions.jsonl',[
        dict(id=p['id'],decision=decisions(p['id'],screen,votes)[1]) for p in parents])
    await asyncio.to_thread(write_json,root/'combined-status.json',dict(phase='odin_complete_waiting_for_gpu_judges',admitted=0))


async def local(root):
    verify(root)
    async def judge(name):
        model,endpoint=MODELS[name]
        for kind,cls in [('base',StagedAudit),('precision',PrecisionAudit)]:
            path=root/'focused'/kind/name
            adapter=cls(path,path/'audit',endpoint);adapter.model=model
            client=httpx.AsyncClient(timeout=900,trust_env=False,limits=httpx.Limits(max_connections=128))
            try:await run(adapter,endpoint,128,client=client,prefetch=1)
            finally:await client.aclose()
            await asyncio.to_thread(verified_stage,path,cls,name)
            await asyncio.to_thread(write_json,path/'audit/pipeline/state.json',dict(phase='complete'))
    await asyncio.gather(judge('flash'),judge('qwen27b'))
    await asyncio.to_thread(write_json,root/'combined-status.json',dict(phase='gpu_audits_complete',admitted=0))


def aggregate(parent_id,requests,votes,specialist):
    relevant=[r['id'] for r in requests if r['parent_id']==parent_id]
    return whole_vote([specialist.get(parent_id,'unresolved'),
        *[whole_vote(votes[name].get(i,'unresolved') for i in relevant) for name in ('flash','qwen27b')]])


def materialize(root):
    verify(root)
    parents=validate_generation(root)
    specialist_values=verified_stage(root/'specialists',production.Specialist,'odin')
    screen,jobs=verification_jobs(parents,specialist_values)
    verified=verified_stage(root/'verification',VerifyFinding,'odin')
    if [r for r,_ in verified]!=jobs:
        # Chunk scheduling order may differ, but requests must match exactly.
        if {r['id']:r for r,_ in verified}!={r['id']:r for r in jobs}:
            raise ValueError('verification requests differ from findings')
    verdicts={r['id']:v.get('review',{}).get('decision','unresolved') for r,v in verified}
    specialist={p['id']:decisions(p['id'],screen,verdicts)[1] for p in parents}
    requests=[r for kind in ('base','precision') for r in rows(root/'focused'/f'{kind}-inputs.jsonl')]
    votes={name:{} for name in ('flash','qwen27b')}
    for name in votes:
        for kind,cls in [('base',StagedAudit),('precision',PrecisionAudit)]:
            values=verified_stage(root/'focused'/kind/name,cls,name)
            if {r['id']:r for r,_ in values}!={r['id']:r for r in rows(root/'focused'/f'{kind}-inputs.jsonl')}:
                raise ValueError('focused audit inputs changed')
            votes[name].update({r['id']:v.get('review',{}).get('decision','unresolved') for r,v in values})
    decisions_out=[dict(id=p['id'],decision=aggregate(p['id'],requests,votes,specialist)) for p in parents]
    immutable_rows(root/'combined-decisions.jsonl',decisions_out)
    admitted={r['id'] for r in decisions_out if r['decision']=='accept'}
    accepted=[dict(id=p['id'],family=p['family'],language='en',task=p['task'],messages=p['messages']) for p in parents if p['id'] in admitted]
    immutable_rows(root/'accepted/conversations.jsonl',accepted)
    receipt_paths=[root/'selected-policy.json',root/'combined-input-receipt.json',root/'combined-decisions.jsonl',root/'accepted/conversations.jsonl',*root.glob('**/audit/quality-*/receipt.json')]
    immutable(root/'accepted/receipt.json',dict(count=len(accepted),statistically_qualified=False,
        production_authorized=True,pins={str(p):file_hash(p) for p in receipt_paths}))
    write_json(root/'combined-status.json',dict(phase='materialized',admitted=len(accepted)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run-odin','run-local','materialize'])
    parser.add_argument('--root',type=Path,default=production.ROOT);args=parser.parse_args()
    with lock(BASE/'.controller.lock'),lock(args.root/'.controller.lock'):
        if args.action=='prepare':prepare(args.root)
        elif args.action=='materialize':materialize(args.root)
        else:asyncio.run((odin if args.action=='run-odin' else local)(args.root))
