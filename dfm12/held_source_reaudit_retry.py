"""Fresh-root bounded technical recovery; never retries semantic evidence failures."""
import argparse
import asyncio
import json
from pathlib import Path

import aiohttp
from jsonschema import ValidationError

from . import held_source_reaudit as base
from .io import file_hash, load, lock, write_json


def technical(row):
    if row.get('status') != 'invalid':
        return False
    error = row.get('error','')
    # Wrong references/quotes are evidence failures, not formatting retries.
    if any(s in error for s in ('Nonliteral','Keep requires','Verdict/issues','Pinned','drift','exceeds')):
        return False
    return any(s in error for s in ('HTTPFailure','Timeout','Connection','ServerDisconnected',
        'JSONDecodeError','ValidationError','Nonkeep requires named issue','Nonempty reason',
        'Duplicate issues','Duplicate JSON key','Incomplete output'))


async def recover(row, payload, record, call):
    if not technical(row):
        return row, []
    prior = None
    try:
        prior = base.strict_json(row['raw']['content']).get('verdict')
    except (KeyError,ValueError,AttributeError):
        pass
    attempts=[]
    for attempt in (2,3):
        current=dict(id=row['id'],status='invalid',attempt=attempt,
            admission_authorized=False,source_holds_preserved=True)
        try:
            raw=await call(payload,attempt);current['raw']=raw
            if raw['finish_reason']!='stop':raise ValueError('Incomplete output')
            value=base.validate(base.strict_json(raw['content']),record)
            if prior in base.compact.VERDICTS and value['verdict'] != prior:
                current.update(error='Semantic verdict changed during technical recovery; withheld')
                attempts.append(current);return current,attempts
            current.update(status='valid',decision=value,technical_recovery=True)
            attempts.append(current);return current,attempts
        except (Exception,) as exc:
            current['error']=repr(exc);attempts.append(current)
            if not technical(current):break
    return current,attempts


async def run(parent,root):
    manifest=base.verify(parent)
    root.mkdir(parents=True,exist_ok=False)
    original={p.stem:load(p) for p in (parent/'outcomes').glob('*.json')}
    todo=[k for k,row in original.items() if technical(row)]
    write_json(root/'manifest.json',dict(parent=str(parent.resolve()),
        parent_manifest_sha256=file_hash(parent/'manifest.json'),
        parent_diagnostic_sha256=file_hash(parent/'diagnostic.json'),
        selected=todo,max_total_attempts=3,semantic_resampling=False,
        pins={str(Path(__file__).resolve()):file_hash(__file__),
              str(Path(base.__file__).resolve()):file_hash(base.__file__)},
        original_outcomes={k:file_hash(parent/'outcomes'/f'{k}.json') for k in original}))
    writer=base.RawResponseWriter(root/'raw');budget=base.Budget(str(base.DEFAULT_TOKENIZER))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=32,limit_per_host=4)) as session:
        for port in range(8800,8808):
            async with session.get(f'http://127.0.0.1:{port}/v1/models') as response:
                response.raise_for_status();doc=await response.json();base.endpoint_limit(doc)
                selected=next(m for m in doc['data'] if m['id']==base.compact.MODEL)
                if Path(selected.get('root','')).resolve()!=Path(base.DEFAULT_TOKENIZER).resolve():
                    raise ValueError('Wrong26B snapshot')
        queue=asyncio.Queue()
        for k in todo:queue.put_nowait(k)
        async def worker(port):
            while not queue.empty():
                key=queue.get_nowait();record,_=base.fetch(parent,key)
                payload=load(parent/'requests'/f'{key}.json')['request']
                budget.measure(payload)
                async def call(request,attempt):
                    return await base.raw_query(session,f'http://127.0.0.1:{port}/v1',request,
                        writer,dict(id=key,attempt=attempt))
                outcome,attempts=await recover(original[key],payload,record,call)
                write_json(root/'attempts'/f'{key}.json',attempts)
                write_json(root/'outcomes'/f'{key}.json',outcome);original[key]=outcome
        await asyncio.gather(*(worker(p) for p in range(8800,8808) for _ in range(4)))
    gates={kind:base.gate({k:v for k,v in manifest['controls'].items() if k.startswith(kind+'-')},original)
           for kind in base.COUNTS}
    write_json(root/'complete.json',dict(gates=gates,retried=len(todo),
        admission_authorized=False,bulk_launched=False,source_holds_preserved=True))


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    with lock(Path(str(a.root)+'.lock')):asyncio.run(run(a.parent,a.root))


if __name__=='__main__':main()
