"""Isolated failure/control probe; no live campaign mutations or admission."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import os
from pathlib import Path
import re
import unicodedata
import aiohttp
from . import wave4_synthetic_campaign as campaign
from .io import load, write_json, file_hash, lock, rows, digest

BASE=Path('data/dfm13/wave4/production-probe-expanded-keepalive')
ROOT=Path('data/dfm13/wave4/literal-preservation-probe-20261003-v2')
CASES=[('be','grounded-instruct',0),('be','openhermes',0),('be','multiturn',1),
       ('be','math-code',1),('be','tool-dialogue',1),('lb','summary-rewrite',0),
       ('lb','openhermes',1),('lb','math-code',1),('hu','summary-rewrite',0),
       ('hu','openhermes',0),('sk','grounded-instruct',1),('sk','openhermes',0),
       ('sl','openhermes',4),('sl','summary-rewrite',0),
       ('be','grounded-instruct',1),('lb','grounded-instruct',0),
       ('hr','grounded-instruct',0),('fa','openhermes',0)]
NOTE='''
Additional literal-preservation check before returning JSON (do not print the check):
1. Read every generated user and assistant sentence literally in the requested
language, not as an intended translation. Rewrite uncertain prose into short,
ordinary sentences. Do not splice words or endings from another language into
your narration. Preserve quoted source names, code and identifiers unchanged.
2. A translated user request MUST retain all task input (sentences to classify,
numbers, examples and constraints). Never answer an input absent from that user
turn. Scenario adaptation retains the same task and subject: a web-page loading
explanation remains a web-page loading explanation, not a different hobby.
3. Preserve who did what, object versus instrument, negation, and source
relationships. Implementing a title through an insignia does not mean replacing
the title. Do not change a population into a different population. Do not fill
gaps in damaged source text with guesses. No new source facts.
4. For code tasks, ask for the function specified in the reference, not an
integer-only answer without input. Explain directly to the user, not with a
third-person analysis of what the user wants. For tool dates, preserve the exact
ISO date in prose if you cannot confidently render it naturally. A lookup is
not a booking. Preserve all requested turns and complete final answers.
Return the same required JSON schema, with no extra commentary or truncation.
'''


def script_flags(candidate):
    """Diagnostic only: scripts do not establish language or justify rejection."""
    lang=candidate['language']
    allowed={'LATIN'} if lang in ('lb','hu','sk','sl','hr') else {'CYRILLIC','LATIN'} if lang=='be' else {'ARABIC','LATIN'}
    source=candidate.get('provenance',{}).get('source',{}).get('text','')
    flags=[]
    for i,m in enumerate(candidate['messages']):
        if m['role'] not in ('user','assistant'):continue
        text=m.get('content','')
        if source:text=text.replace(source,'')
        text=re.sub(r'```.*?```|https?://\S+|`[^`]*`','',text,flags=re.S)
        for match in re.finditer(r'[^\W\d_]+',text):
            scripts={unicodedata.name(ch,'').split(' ')[0] for ch in match.group() if ch.isalpha()}
            if scripts-allowed:
                flags.append(dict(message_index=i,text=match.group(),scripts=sorted(scripts),diagnostic_only=True))
    return flags


def prepare(root):
    if root.exists():raise ValueError('new isolated root required')
    outcomes=[load(p) for p in (BASE/'outcomes').glob('*.json')]
    source=Path('data/dfm13/wave4/calibration/generation-requests.jsonl')
    originals={(s['language_code'],s['family'],s['slot']):s for item in rows(source) for s in [item['spec']]}
    specs=[];pins={};pairs=[]
    for case in CASES:
        o=next(o for o in outcomes if (o['language'],o['family'],o['slot'])==case)
        if not o.get('effective_keep'):raise ValueError('baseline is not accepted')
        request=BASE/'requests'/(o['id']+'-generate.json')
        spec=originals[case]
        if digest(spec)!=o['spec_sha256']:raise ValueError('original specification changed')
        specs.append(spec)
        paths=[request,BASE/'candidates'/(o['id']+'.json'),BASE/'outcomes'/(o['id']+'.json')]
        pins.update({str(p.resolve()):file_hash(p) for p in paths})
        pairs.append(dict(id=o['id'],language=case[0],family=case[1],slot=case[2],
                          baseline_candidate=str(paths[1]),control=case in CASES[-4:]))
    pins[str(source.resolve())]=file_hash(source)
    c=campaign.controller()
    for p in [Path(__file__),Path(campaign.__file__),*c.v6.implementation_paths(),Path('dfm12/wave_synthetic_runtime.py'),Path('dfm12/wave4_synthetic_specs.py'),Path('dfm12/calibration_streaming.py')]:
        pins[str(p.resolve())]=file_hash(p)
    write_json(root/'specifications.json',specs);write_json(root/'pairs.json',pairs)
    for p in [root/'specifications.json',root/'pairs.json']:pins[str(p.resolve())]=file_hash(p)
    write_json(root/'manifest.json',dict(pins=pins,total=len(specs),note=NOTE,concurrency_per_server=2,
        baseline='historical accepted outputs, not a same-seed randomized A/B estimate',
        admission_authorized=False,production_approved=False,publication_allowed=False))


async def run(root,concurrency):
    if type(concurrency) is not int or not 1<=concurrency<=8:raise ValueError('concurrency must be1..8')
    m=load(root/'manifest.json')
    for p,sha in m['pins'].items():
        if file_hash(Path(p))!=sha:raise ValueError('pin drift '+p)
    c=campaign.controller();v6=c.v6
    original=v6.generation_request
    def request(*args,**kwargs):
        payload=deepcopy(original(*args,**kwargs))
        payload['messages'][0]['content']+=NOTE
        return payload
    v6.generation_request=request
    specs=load(root/'specifications.json');seen=set()
    outcomes,pending=c.pilot.recover(root,specs,seen)
    endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
    runtime=dict(pid=os.getpid(),concurrency_per_server=concurrency,endpoints=endpoints,phase='running')
    write_json(root/'runtime.json',runtime)
    def progress():
        write_json(root/'progress.json',dict(total=len(specs),terminal=len(outcomes),
            statuses=dict(Counter(o['status'] for o in outcomes.values())),
            effective_keeps=sum(o.get('effective_keep') is True for o in outcomes.values()),
            production_approved=False,admission_authorized=False))
    review,generation=v6.adapters();budget=v6.Budget(campaign.european.TOKENIZER_DIR)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=8*concurrency,limit_per_host=concurrency),timeout=aiohttp.ClientTimeout(total=600)) as session:
        health={}
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status();health[endpoint]=await response.json()
        write_json(root/'endpoint-health.json',health)
        stages=v6.Stages(root,budget,v6.RawResponseWriter(root/'raw'),session,query=c.stream_query)
        gates=[asyncio.Semaphore(concurrency) for _ in endpoints]
        async def one(i,spec):
            lane=i%8
            async with gates[lane]:
                o=await c.pilot.process(spec,endpoints[lane],root,stages,health,generation,review,seen)
                outcomes[o['id']]=o
                path=root/'candidates'/(o['id']+'.json')
                if path.exists():write_json(root/'diagnostics'/(o['id']+'.json'),dict(script_flags=script_flags(load(path)),automatic_rejection=False))
                progress();print(spec['language_code'],spec['family'],o['status'],o.get('effective_keep'),flush=True)
        progress();await asyncio.gather(*(one(i,s) for i,s in enumerate(pending)))
    write_json(root/'runtime.json',dict(runtime,phase='terminal',pid=None,previous_pid=os.getpid()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--concurrency-per-server',type=int,default=2);a=p.parse_args()
    if a.command=='prepare':prepare(a.root)
    else:
        with lock(a.root/'run.lock'):asyncio.run(run(a.root,a.concurrency_per_server))
