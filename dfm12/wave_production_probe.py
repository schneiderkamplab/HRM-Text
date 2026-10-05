"""Exercise the actual production stage runner before approving bulk generation."""
import argparse
import asyncio
from collections import Counter
from pathlib import Path

import aiohttp

from . import baltic_synthetic_campaign, wave4_synthetic_campaign
from .io import lock, rows, write_json


def select_specs(source, per_family):
    if type(per_family) is not int or not 1 <= per_family <= 10:
        raise ValueError('Require 1..10 examples per language/family')
    selected = {}
    for item in rows(source):
        spec = item['spec']
        group = selected.setdefault((spec['language_code'], spec['family']), [])
        if len(group) < per_family:
            group.append(spec)
    if not selected or any(len(group) != per_family for group in selected.values()):
        raise ValueError('Insufficient calibration examples for a complete family')
    return [spec for group in selected.values() for spec in group]


async def run(root,wave,per_family=1):
    campaign=wave4_synthetic_campaign if wave=='wave4' else baltic_synthetic_campaign
    c=campaign.controller();v6=c.v6
    source=Path('data/dfm13')/wave/('calibration/generation-requests.jsonl')
    selected=select_specs(source, per_family)
    endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
    review,generation=v6.adapters()
    budget=v6.Budget(campaign.european.TOKENIZER_DIR)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=64, limit_per_host=8),
            timeout=aiohttp.ClientTimeout(total=600)) as session:
        health={}
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status();health[endpoint]=await response.json()
        stages=v6.Stages(root,budget,v6.RawResponseWriter(root/'raw'),session,query=c.stream_query)
        gates=[asyncio.Semaphore(8) for _ in endpoints];seen=set()
        async def one(index,spec):
            lane=index%8
            async with gates[lane]:
                outcome=await c.pilot.process(spec,endpoints[lane],root,stages,health,generation,review,seen)
                print(spec['language_code'],spec['family'],outcome['status'],outcome.get('effective_keep'),flush=True)
                return outcome
        result=await asyncio.gather(*(one(i,s) for i,s in enumerate(selected)))
    write_json(root/'summary.json',dict(wave=wave,total=len(result),
        per_family=per_family, transport='production_keepalive',
        accepted=sum(r.get('effective_keep') is True for r in result),
        statuses=dict(Counter(r['status'] for r in result)),production_approved=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wave',choices=['baltic','wave4'],required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--per-family',type=int,default=1)
    args=parser.parse_args()
    with lock(args.root/'run.lock'):
        asyncio.run(run(args.root,args.wave,args.per_family))
