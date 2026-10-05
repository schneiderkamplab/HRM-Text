"""Bounded current/revised reviewer comparison;32 total shared-server requests."""
import argparse
import asyncio
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sqlite3

import aiohttp

from dfm12 import baltic_semantic_review as revised
from dfm12 import wave_compact_review as baseline
from dfm12 import synthetic_repair_pilot as executor
from dfm12.calibration_streaming import stream_query
from dfm12.generation_constraints import DEFAULT_TOKENIZER
from dfm12.io import digest, file_hash, load, lock, write_json
from dfm12.multilingual_calibration_v6 import RawResponseWriter
from dfm12.wave_synthetic_runtime import Budget, compact_request, endpoint_limit

PARENT = Path('data/dfm13/baltic/synthetic-compact-26b-20261004-v1')
DIAGNOSTICS = ('000b47927c29', '00248c298b74', '0017c95be7d1', '001bf2286870')


def controls():
    # Paired contrasts differ only in the assistant; labels never enter requests.
    pairs = [
        ('lt-count','lt','Ataskaitoje nurodyta: 2020 metais buvo 12 darbuotojų.',
         'Kiek darbuotojų buvo 2020 metais? Atsakykite trumpai.', '12 darbuotojų.', '21 darbuotojas.'),
        ('lv-condition','lv','Grāmatu var aizņemties tikai tad, ja lasītāja karte ir derīga.',
         'Kad var aizņemties grāmatu?', 'Ja lasītāja karte ir derīga.', 'Grāmatu var aizņemties vienmēr, arī bez derīgas kartes.'),
        ('lt-brief','lt','Sostinė yra Vilnius. Mieste veikia muziejai ir teatrai.',
         'Įvardykite tik sostinę.', 'Vilnius.', 'Kaunas.'),
        ('lv-qualifier','lv','Pētījums liecina, ka izmaiņas varētu samazināt izmaksas. Garantijas nav.',
         'Vienā teikumā apkopojiet secinājumu.', 'Izmaiņas varētu samazināt izmaksas, bet tas nav garantēts.',
         'Izmaiņas garantē izmaksu samazinājumu.'),
        ('lt-scope','lt','Miestai: Vilnius ir Kaunas. Šalys: Lietuva ir Latvija.',
         'Išvardykite tik abu miestus.', 'Vilnius ir Kaunas.', 'Vilnius ir Ryga.'),
        ('lv-code','lv','The command prints the string: print("Hello")',
         'Izskaidrojiet latviski un precīzi saglabājiet kodu print("Hello").',
         'Kods print("Hello") izvada tekstu Hello.', 'Kods print("Sveiki") izvada tekstu Sveiki.'),
    ]
    result=[]
    for key,lang,source,user,good,bad in pairs:
        for variant,answer,expected in [('good',good,['keep']),('bad',bad,['repair','reject'])]:
            record=dict(language=lang,family='grounded-instruct',tools=[],
                messages=[dict(role='user',content=user+'\n\n'+source),dict(role='assistant',content=answer)],
                source=dict(text=source))
            result.append(dict(id=key+'-'+variant,kind='control',record=record,expected=expected))
    return result


def sample(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[(row[1],row[2])].append(row)
    rng=random.Random(20261004)
    chosen=[]
    for group in sorted(groups):
        pool=sorted(groups[group])
        chosen.extend(rng.sample(pool,min(2,len(pool))))
    return chosen


def prepare(root):
    if root.exists():raise ValueError('New diagnostic root required')
    with sqlite3.connect((PARENT/'jobs.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        rows=db.execute("SELECT id,language,family,workdir,outcome_json FROM jobs WHERE json_extract(outcome_json,'$.compact_verdict')='needs_verification' ORDER BY id").fetchall()
    cases=controls(); picked=sample(rows); selected={r[0] for r in picked}
    picked += [r for r in rows if any(r[0].startswith(p) for p in DIAGNOSTICS) and r[0] not in selected]
    if len(picked)>28:raise ValueError('Diagnostic bound exceeded')
    pins={str(p.resolve()):file_hash(p) for p in (Path(__file__),Path(revised.__file__),
        Path(baseline.__file__),Path(executor.__file__),Path('dfm12/wave_synthetic_runtime.py'),
        Path('dfm12/calibration_streaming.py'))}
    for key,lang,family,workdir,outcome in picked:
        path=Path(workdir)/'candidates'/f'{key}.json'; request=Path(workdir)/'requests'/f'{key}-review.json'
        candidate=load(path); original=load(request)
        if json.loads(original['request']['messages'][1]['content']) != baseline.visible(candidate):
            # Production audit_record can add source aliases; exact saved request
            # is authoritative and is used unchanged for BOTH comparison arms.
            record=json.loads(original['request']['messages'][1]['content'])
            if record['messages'] != candidate['messages']:raise ValueError('Candidate/request mismatch')
        else:record=baseline.visible(candidate)
        cases.append(dict(id=key,kind='random_nv' if key in selected else 'diagnostic_nv',record=record,
            candidate_path=str(path),candidate_sha256=file_hash(path),prior_outcome=json.loads(outcome)))
        for p in (path,request):pins[str(p.resolve())]=file_hash(p)
    budget=Budget(DEFAULT_TOKENIZER)
    requests={}
    for case in cases:
        for arm,adapter in [('current',baseline),('revised',revised)]:
            payload=adapter.request(case['record'])
            # Same complete evidence and production decoding settings in both arms.
            payload['messages'][1]['content']=json.dumps(case['record'],ensure_ascii=False)
            payload['frequency_penalty']=.5
            payload,schema=compact_request(payload)
            requests[case['id']+'-'+arm]=dict(request=payload,schema=schema,budget=budget.measure(payload))
    write_json(root/'cases.json',cases);write_json(root/'requests.json',requests)
    for p in (root/'cases.json',root/'requests.json'):pins[str(p.resolve())]=file_hash(p)
    write_json(root/'manifest.json',dict(total_cases=len(cases),requests=len(requests),
        old_nv_population=len(rows),selection_seed=20261004,pins=pins,concurrency_per_server=4,
        admission_authorized=False,production_installation=False))
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify(root)


def verify(root):
    if file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:raise ValueError('Seal drift')
    m=load(root/'manifest.json')
    for p,h in m['pins'].items():
        if file_hash(p)!=h:raise ValueError('Pin drift: '+p)
    if m['requests']>80 or m['concurrency_per_server']!=4:raise ValueError('Bound changed')
    return m


async def run(root):
    m=verify(root);requests=load(root/'requests.json');budget=Budget(DEFAULT_TOKENIZER)
    writer=RawResponseWriter(root/'raw');queue=asyncio.Queue()
    for key,value in requests.items():queue.put_nowait((key,value))
    endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=32,limit_per_host=4)) as session:
        for e in endpoints:
            async with session.get(e+'/models') as response:
                response.raise_for_status(); endpoint_limit(await response.json())
        async def worker(e):
            while not queue.empty():
                key,envelope=queue.get_nowait()
                op=root/'outcomes'/f'{key}.json'
                if op.exists():continue
                state=await executor.once(root,key,'review',envelope['request'],envelope['schema'],e,
                    session,writer,budget,stream_query)
                result=dict(id=key,status=state['status'],admission_authorized=False)
                if state['status']=='complete':
                    try:result['decision']=baseline.validate(state['output'])
                    except Exception as exc:result.update(status='invalid_contract',error=repr(exc),raw_decision=state['output'])
                else:result['error']=state.get('error')
                write_json(op,result);print(result,flush=True)
        await asyncio.gather(*(worker(e) for e in endpoints for _ in range(4)))
    verify(root)
    outcomes=[load(p) for p in sorted((root/'outcomes').glob('*.json'))]
    counts=Counter((r['id'].rsplit('-',1)[1],r.get('decision',{}).get('verdict',r['status'])) for r in outcomes)
    write_json(root/'summary.json',dict(total=len(outcomes),expected=m['requests'],
        counts={str(k):v for k,v in counts.items()},admission_authorized=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':print(prepare(a.root))
    else:
        with lock(a.root/'run.lock'):asyncio.run(run(a.root))


if __name__=='__main__':main()
