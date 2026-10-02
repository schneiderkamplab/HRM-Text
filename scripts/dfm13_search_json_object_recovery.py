"""Recover failed adjudications with json_object, no penalties, strict CPU checks."""
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_json_mode_probe as probe
from scripts import dfm13_search_adjudication_retry as bounded

SOURCE=Path('data/dfm13/search-critique-adjudication-20261001')
ROOT=Path('data/dfm13/search-json-object-recovery-20261001')


async def run():
    if ROOT.exists():raise ValueError('new root required')
    os.environ.pop('JINA_API_KEY',None)
    probe_outcome=probe.ROOT/'json_object/outcome.json'
    result=json.loads(probe_outcome.read_text())
    if result.get('status')!='reviewed' or result.get('verdict')!='keep':raise ValueError('paired control did not validate')
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    for p,h in manifest['pins'].items():
        if base.file_hash(Path(p))!=h:raise ValueError('source pin mismatch')
    expected={x['id']:x['expected'] for x in json.loads((SOURCE/'expectations.json').read_text())}
    jobs=[];pins={}
    for job in json.loads((SOURCE/'jobs.json').read_text()):
        folder=SOURCE/'records'/job['id']
        if json.loads((folder/'outcome.json').read_text())['status']!='error':continue
        for p in (folder/'outcome.json',folder/'adjudication-request.json'):
            pins[str(p.resolve())]=base.file_hash(p)
        if job['id'].startswith('020d55'):
            base.atomic(ROOT/'records'/job['id']/'outcome.json',dict(status='reviewed',verdict='keep',passed=True,
                expected=expected[job['id']],reused_probe=str(probe_outcome),candidate_sha256=job['candidate_sha256'],admission_authorized=False))
            pins[str(probe_outcome.resolve())]=base.file_hash(probe_outcome)
            continue
        payload=json.loads(json.loads((folder/'adjudication-request.json').read_text())['messages'][-1]['content'])
        payload['verified_check_plain_text']=bounded.check_text(payload['verified_checks'])
        job['payload']=payload;jobs.append(job)
    for p in (Path(__file__),Path(probe.__file__),Path(bounded.__file__),SOURCE/'jobs.json'):
        pins[str(p.resolve())]=base.file_hash(p)
    base.atomic(ROOT/'manifest.json',dict(pins=pins,new_calls=len(jobs),reused=1,response_format='json_object',penalties='none',
        max_tokens=2048,paid_calls=0,generation_calls=0,max_attempts=1,answers_evidence_unchanged=True))
    base.atomic(ROOT/'runtime.json',dict(pid=os.getpid(),queued=len(jobs),concurrency_per_endpoint=8,paid_calls=0))
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index,job):
            folder=ROOT/'records'/job['id']
            try:
                model=base.Model(probe.ModeSession(session,'json_object',folder),tokenizer,manifest,manifest['endpoints'][index],600)
                raw=await model.ask(probe.messages(job['payload']),bounded.SCHEMA,None,folder,'adjudication')
                base.atomic(folder/'raw-adjudication.json',raw)
                try:review=bounded.derive(raw,job['pages'],job['answer'])
                except ValueError as error:review=dict(verdict='needs_verification',reason=str(error),raw_adjudication=raw)
                base.atomic(folder/'review.json',review)
                outcome=dict(status='reviewed',verdict=review['verdict'],expected=expected[job['id']],passed=review['verdict']==expected[job['id']])
            except Exception as error:outcome=dict(status='error',error=str(error),passed=False,expected=expected[job['id']])
            base.atomic(folder/'outcome.json',dict(**outcome,admission_authorized=False))
            rows=[json.loads(p.read_text()) for p in (ROOT/'records').glob('*/outcome.json')]
            base.atomic(ROOT/'progress.json',dict(terminal=len(rows),total=len(jobs)+1,passed=sum(r['passed'] for r in rows),counts=dict(Counter(r.get('verdict',r['status']) for r in rows))))
        await asyncio.gather(*(one(i,j) for i,j in enumerate(jobs)))
    rows=[json.loads(p.read_text()) for p in (ROOT/'records').glob('*/outcome.json')]
    base.atomic(ROOT/'finished.json',dict(total=len(rows),passed=sum(r['passed'] for r in rows),counts=dict(Counter(r.get('verdict',r['status']) for r in rows)),paid_calls=0,production_authorized=False))


if __name__=='__main__':asyncio.run(run())
