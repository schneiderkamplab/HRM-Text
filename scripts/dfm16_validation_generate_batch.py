"""Generate reviewed validation batches using the frozen adapter and shared ledger."""
import argparse,asyncio,os,time
from pathlib import Path
import httpx
from audit_pipeline.runtime import run
from dfm12.io import load,lock,file_hash,write_json
from scripts.dfm16_story_calibration import immutable,immutable_rows
from scripts.dfm16_staged_stories import StagedGenerate,POLICY
from scripts.dfm16_staged_validation import verify_freeze
from scripts.dfm16_staged_validation_campaign import ROOT,BASE
from scripts.dfm16_experiment_transport import Budget,ExperimentClient
from scripts.queue_dfm16_stories_qwen import prepare_stage
from scripts.dfm16_judge_ensemble_study import MODELS

async def generate(root,language,start,end):
    verify_freeze(root,language)
    protocol=load(root/'protocol.json')
    for path,digest in protocol['software'].items():
        if file_hash(Path(path))!=digest:raise ValueError('changed frozen software')
    stage=root/language/'validation/generation'/f'{start:04d}-{end:04d}'
    reviewed=[load(root/language/'validation/source-review'/f'{i:04d}.json') for i in range(start,end)]
    jobs=[r['generation_input'] for r in reviewed if 'generation_input' in r]
    # Every source can belong to exactly one prepared generation batch.
    for other in stage.parent.glob('*/inputs.jsonl'):
        if other.parent==stage:continue
        from dfm12.io import rows
        if {r['id'] for r in rows(other)} & {r['id'] for r in jobs}:raise ValueError('overlapping generation batch')
    immutable_rows(stage/'inputs.jsonl',jobs)
    immutable(stage/'source-receipt.json',dict(reviewed=len(reviewed),eligible=len(jobs),rejected=len(reviewed)-len(jobs),
        pins={str(root/language/'validation/source-review'/f'{i:04d}.json'):file_hash(root/language/'validation/source-review'/f'{i:04d}.json') for i in range(start,end)}))
    if not jobs:return
    prepare_stage(stage,jobs,POLICY)
    model,endpoint=MODELS['odin']
    adapter=StagedGenerate(stage,stage/'audit',endpoint);adapter.model=model
    budget=Budget(BASE/'odin-requests.sqlite')
    client=ExperimentClient(budget,headers={'Authorization':'Bearer '+os.environ['ODIN_API_KEY']},timeout=900,trust_env=False,limits=httpx.Limits(max_connections=64))
    start_time=time.time();write_json(stage/'state.json',dict(phase='running'))
    write_json(stage/'audit/pipeline/state.json',dict(phase='running'))
    try:
        await run(adapter,endpoint,64,client=client,prefetch=1)
        for job in load(stage/'manifest.json')['chunks']:adapter.verify_receipt(job,stage/'audit'/job['job_id'])
        write_json(stage/'state.json',dict(phase='complete',seconds=time.time()-start_time))
        write_json(stage/'audit/pipeline/state.json',dict(phase='complete'))
    finally:
        await client.aclose()
        write_json(root/'reports/odin-usage.json',budget.summary(6.25,25))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--language',required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True);p.add_argument('--root',type=Path,default=ROOT)
    a=p.parse_args()
    with lock(BASE/'.controller.lock'),lock(a.root/'.controller.lock'):
        asyncio.run(generate(a.root,a.language,a.start,a.end))
