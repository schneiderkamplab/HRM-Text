"""Bounded live reviewer checks with CPU-verifiable math and temporal fixtures."""
import asyncio
import json
from pathlib import Path
import aiohttp
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_reviewer_v3 as reviewer

ROOT=Path('data/dfm13/search-reviewer-controls-20261001')
URL='https://example.org/evidence'
CASES=[
    dict(id='historical_date_false_accept', expected='reject',
         prompt='Earlier this week, did the stock rise? Original question date: 2025-03-26.',
         body='A stock quote dated 2026-09-29 reports a five-day gain of 0.44%. No March 2025 prices are available.',
         answer='Yes, earlier this week it rose 0.44%, according to the September 29, 2026 quote.'),
    dict(id='later_document_not_fabricated',expected='keep',
         prompt='Give the logo link from this page; no historical date restriction.',
         body='Retrieved 2026-10-01. The article was published 2026-06-12 and contains the company logo.',
         answer='This article contains the logo. It was published June 12, 2026, before retrieval on October 1, 2026.'),
    dict(id='miller_rabin_false_coverage',expected='reject',
         prompt='Do bases 2,3,5,7 guarantee Miller-Rabin correctness for every integer below 2^32?',
         body='CPU verified: 3215031751 = 151 * 751 * 28351 < 2^32. This composite passes the strong probable-prime test for bases 2,3,5,7.',
         answer='Yes, these four bases guarantee correctness for every integer below 2^32.'),
    dict(id='supported_address_no_label_rejection',expected='keep',
         prompt='Give the address and access directions listed for Takayama Old Town in this source.',
         body='Access to Takayama Old Town: 20 Kamisannomachi, Takayama, Gifu 506-0846. Walk from Takayama Station.',
         answer='The source lists 20 Kamisannomachi, Takayama, Gifu 506-0846 and says to walk from Takayama Station. This is its listed access address, not a unique address for the whole district.'),
]


def strong_test(n, a):
    d=n-1; s=0
    while d%2==0:
        d//=2; s+=1
    x=pow(a,d,n)
    if x in (1,n-1): return True
    for _ in range(s-1):
        x=pow(x,2,n)
        if x==n-1: return True
    return False


async def run():
    if ROOT.exists(): raise ValueError('new control root required')
    assert 151*751*28351==3215031751<2**32
    assert all(strong_test(3215031751,a) for a in (2,3,5,7))
    manifest=json.loads(Path('data/dfm13/search-reviewer-v3-20261001/manifest.json').read_text())
    base.atomic(ROOT/'manifest.json',dict(cases=CASES,paid_calls=0,generation_calls=0,
        pins={str(p.resolve()):base.file_hash(p) for p in (Path(__file__),Path(reviewer.__file__))}))
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(manifest['tokenizer_dir'],local_files_only=True)
    async with aiohttp.ClientSession(trust_env=False) as session:
        async def one(i,case):
            folder=ROOT/case['id']; pages={URL:dict(url=URL,body=case['body'])}
            answer=case['answer']+' [source]('+URL+')'
            model=base.Model(session,tokenizer,manifest,manifest['endpoints'][i],600)
            try:
                value=await model.ask([dict(role='system',content=reviewer.RUBRIC),dict(role='user',content=json.dumps(dict(
                    prompt=case['prompt'],answer=answer,pages=pages,retrieval_date='2026-10-01')))],reviewer.SCHEMA,None,folder,'review')
                review=reviewer.validate(value,pages,answer)
                result=dict(expected=case['expected'],review=review,passed=review['verdict']==case['expected'])
            except Exception as error:
                result=dict(passed=False,error=str(error))
            base.atomic(folder/'outcome.json',result)
            return result
        results=await asyncio.gather(*(one(i,c) for i,c in enumerate(CASES)))
    base.atomic(ROOT/'finished.json',dict(passed=sum(r['passed'] for r in results),total=len(results),
        production_authorized=False,paid_calls=0))


if __name__=='__main__': asyncio.run(run())
