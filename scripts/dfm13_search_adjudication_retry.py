"""One bounded adjudication-only recovery; source answers and critiques unchanged."""
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import aiohttp
from scripts import dfm13_search_critique_adjudication as original
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_links_v5 as links

SOURCE=Path('data/dfm13/search-critique-adjudication-20261001')
ROOT=Path('data/dfm13/search-adjudication-retry-20261001')
SCHEMA=dict(type='object',properties={**{k:dict(type='array',maxItems=3,items=dict(type='string',maxLength=500))
    for k in ('confirmed_errors','unresolved_questions','dismissed_criticisms')},'summary':dict(type='string',maxLength=500)},
    required=['confirmed_errors','unresolved_questions','dismissed_criticisms','summary'],additionalProperties=False)


def check_text(checks):
    out=[]
    for check in checks:
        if 'number' in check:
            out.append(f"CPU verified {check['number']} = 151 * 751 * 28351 is composite, is below 2^32 = {2**32}, and passes strong Miller-Rabin tests for every base in {check['passes_strong_tests_for']}. Therefore a statement that these bases correctly classify ALL 32-bit integers has this specific counterexample. This does not prove a minimum base count below 10^9.")
        else:
            out.append(f"Calendar check: {check['later_date']} is later than the original question date {check['original_date']}. A source published later may be real, but a later event cannot already have happened at the earlier date.")
    return out


def derive(value,pages,answer):
    if not isinstance(value,dict) or set(value)!=set(SCHEMA['required']):raise ValueError('invalid schema')
    for key in SCHEMA['required'][:-1]:
        if not isinstance(value[key],list) or len(value[key])>3 or not all(isinstance(v,str) and v.strip() and len(v)<=500 for v in value[key]):raise ValueError('invalid bounded finding list')
    if not isinstance(value['summary'],str) or not value['summary'].strip() or len(value['summary'])>500:raise ValueError('invalid summary')
    verdict='reject' if value['confirmed_errors'] else 'needs_verification' if value['unresolved_questions'] else 'keep'
    citation_check=None
    if verdict=='keep':citation_check=links.check(answer,pages,list(pages))
    return dict(value,verdict=verdict,citation_traceability_only=citation_check)


async def run():
    if ROOT.exists():raise ValueError('new recovery root required')
    os.environ.pop('JINA_API_KEY',None)
    manifest=json.loads((SOURCE/'manifest.json').read_text())
    for p,h in manifest['pins'].items():
        if base.file_hash(Path(p))!=h:raise ValueError('source pin mismatch')
    expected={x['id']:x['expected'] for x in json.loads((SOURCE/'expectations.json').read_text())}
    jobs=[];pins={}
    for job in json.loads((SOURCE/'jobs.json').read_text()):
        folder=SOURCE/'records'/job['id']
        if json.loads((folder/'outcome.json').read_text())['status']!='error':continue
        request_path=folder/'adjudication-request.json'
        request=json.loads(request_path.read_text())
        payload=json.loads(request['messages'][-1]['content'])
        payload['verified_check_plain_text']=check_text(payload['verified_checks'])
        job['retry_payload']=payload;jobs.append(job)
        for p in (request_path,folder/'outcome.json',folder/'critique.json'):pins[str(p.resolve())]=base.file_hash(p)
    for p in (Path(__file__),Path(original.__file__),SOURCE/'jobs.json'):pins[str(p.resolve())]=base.file_hash(p)
    base.atomic(ROOT/'manifest.json',dict(total=len(jobs),pins=pins,paid_calls=0,generation_calls=0,
        max_attempts=1,changes=['bounded three-element finding arrays','no output URL list','CPU facts also expressed as plain text'],
        answers_and_evidence_unchanged=True,expectations_not_sent=True))
    base.atomic(ROOT/'runtime.json',dict(pid=os.getpid(),cases=len(jobs),concurrency_per_endpoint=8,paid_calls=0))
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index,job):
            folder=ROOT/'records'/job['id']
            try:
                model=base.Model(original.FrequencySession(session),tokenizer,manifest,manifest['endpoints'][index],600)
                raw=await model.ask([dict(role='system',content=original.COMMON+
                    'Independently adjudicate this fallible critique against the answer, original task and evidence. '
                    'Pay explicit attention to supplied CPU counterexamples and calendar comparisons. Do not accept a source assertion contradicted by verified computation. '
                    'Return only short confirmed_errors, unresolved_questions, dismissed_criticisms lists and a summary. '
                    'Use English for findings. At most three concise items per list. Supported claims need not be repeated. '
                    'Do not generate URLs or a verdict label; CPU derives disposition and separately checks existing citations.'),
                    dict(role='user',content=json.dumps(job['retry_payload'],ensure_ascii=False))],SCHEMA,None,folder,'adjudication')
                base.atomic(folder/'raw-adjudication.json',raw)
                try:review=derive(raw,job['pages'],job['answer'])
                except ValueError as error:review=dict(verdict='needs_verification',reason=str(error),original_adjudication=raw)
                base.atomic(folder/'review.json',review)
                result=dict(status='reviewed',verdict=review['verdict'],expected=expected[job['id']],passed=review['verdict']==expected[job['id']])
            except Exception as error:result=dict(status='error',error=str(error),expected=expected[job['id']],passed=False)
            base.atomic(folder/'outcome.json',dict(**result,admission_authorized=False))
            rows=[json.loads(p.read_text()) for p in (ROOT/'records').glob('*/outcome.json')]
            base.atomic(ROOT/'progress.json',dict(terminal=len(rows),total=len(jobs),passed=sum(r['passed'] for r in rows),counts=dict(Counter(r.get('verdict',r['status']) for r in rows))))
            return result
        results=await asyncio.gather(*(one(i,j) for i,j in enumerate(jobs)))
    base.atomic(ROOT/'finished.json',dict(total=len(results),passed=sum(r['passed'] for r in results),results=results,
        paid_calls=0,production_authorized=False))


if __name__=='__main__':asyncio.run(run())
