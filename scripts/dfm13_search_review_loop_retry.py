"""One changed-parameter retry of observed whitespace-loop failures only."""
import asyncio
import json
from pathlib import Path
import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_review_validation_v4 as validation

SOURCE=Path('data/dfm13/search-review-error-retry-20261001')
ROOT=Path('data/dfm13/search-review-loop-retry-20261001')


def changed_request(request, prior_response):
    usage=prior_response['usage']
    if usage['prompt_tokens']+3072+512>32768:
        raise ValueError('insufficient context headroom; refuse unchanged overlong input')
    if prior_response['choices'][0]['finish_reason']!='length':
        raise ValueError('not an observed length failure')
    text=prior_response['choices'][0]['message']['content']
    if len(text[-500:].replace('\\n','').strip())>30:
        raise ValueError('not an observed whitespace-loop tail')
    result=json.loads(json.dumps(request))
    result.update(frequency_penalty=0.5,max_tokens=3072)
    return result


async def run():
    if ROOT.exists(): raise ValueError('new root required')
    jobs={j['id']:j for j in json.loads((SOURCE/'jobs.json').read_text())}
    pending=[];pins={}
    for folder in sorted((SOURCE/'records').iterdir()):
        outcome=folder/'outcome.json'
        if json.loads(outcome.read_text())['status']!='error':continue
        request_path=folder/'review-request.json';response_path=folder/'review-response.json'
        raw=json.loads(json.loads(response_path.read_text())['body'])
        request=changed_request(json.loads(request_path.read_text()),raw)
        pending.append((folder.name,request))
        for p in (outcome,request_path,response_path):pins[str(p.resolve())]=base.file_hash(p)
    for p in (Path(__file__),Path(validation.__file__),SOURCE/'jobs.json'):pins[str(p.resolve())]=base.file_hash(p)
    base.atomic(ROOT/'manifest.json',dict(total=len(pending),pins=pins,paid_calls=0,generation_calls=0,
        settings=dict(frequency_penalty=0.5,max_tokens=3072,timeout=600),max_attempts=1))
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(index,item):
            key,request=item;folder=ROOT/'records'/key
            base.atomic(folder/'request.json',request)
            try:
                async with session.post(f'http://127.0.0.1:{8800+index}/v1/chat/completions',json=request,
                        timeout=aiohttp.ClientTimeout(total=600)) as response:
                    text=await response.text()
                    base.atomic(folder/'response.json',dict(status=response.status,body=text))
                    if response.status!=200:raise ValueError('HTTP '+str(response.status))
                parsed=base.strict_json(text);choice=parsed['choices'][0]
                if choice['finish_reason']!='stop':raise ValueError('incomplete output '+choice['finish_reason'])
                raw=base.strict_json(choice['message']['content'])
                try:review=validation.validate_review(raw,jobs[key]['pages'],jobs[key]['answer'])
                except ValueError as error:review=dict(verdict='needs_verification',reason=str(error),original_review=raw)
                base.atomic(folder/'review.json',review)
                result=dict(status='reviewed',verdict=review['verdict'])
            except Exception as error:result=dict(status='error',error=str(error))
            base.atomic(folder/'outcome.json',dict(**result,admission_authorized=False));return result
        results=await asyncio.gather(*(one(i,item) for i,item in enumerate(pending)))
    base.atomic(ROOT/'finished.json',dict(results=results,paid_calls=0,generation_calls=0))


if __name__=='__main__':asyncio.run(run())
