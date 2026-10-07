"""Replay exposed positive/negative controls through the new synthetic reviewer."""
import asyncio
from pathlib import Path

import httpx
import jsonschema
import typer

from dfm12.io import file_hash, load, lock, rows, write_json
from dfm12.multilingual_generation_v4 import _parse
from dfm14.calibrate import MODEL, configure, audit_record, query
from dfm14.generation_contract import review_payload, VERSION
from dfm14.synthetic_review import keeps

app=typer.Typer()
NEGATIVE={('hi','tool-dialogue'),('id','tool-dialogue'),('zh','summary-rewrite'),
          ('ru','summary-rewrite'),('ru','multiturn'),('ga','multiturn'),
          ('he','grounded-instruct'),('cy','summary-rewrite'),('mt','openhermes'),
          ('vi','math-code'),('gl','grounded-instruct'),('id','summary-rewrite')}
POSITIVE={('ja','grounded-instruct'),('zh','tool-dialogue'),('ko','openhermes'),
          ('hi','openhermes'),('ar','math-code'),('tr','tool-dialogue')}


async def execute(source, output, endpoints):
    budget=configure()
    semaphore=asyncio.Semaphore(len(endpoints)*2)
    selected=[r for r in rows(source) if (r['language'],r['family']) in NEGATIVE|POSITIVE]
    if len(selected)!=len(NEGATIVE|POSITIVE): raise ValueError('Missing/duplicate regression cells')
    async with httpx.AsyncClient(timeout=900) as client:
        async def one(i,row):
            async with semaphore:
                key=(row['language'],row['family'])
                record=audit_record(row['candidate'])
                payload=review_payload(record,MODEL)
                budget.measure(payload)
                result=dict(language=key[0],family=key[1],expected_keep=key in POSITIVE,
                            original_path=row['evidence_path'],training_ready=False)
                try:
                    body=await query(client,endpoints[i%len(endpoints)],payload,output/row['id']/'review.json')
                    choice=body['choices'][0]
                    if choice['finish_reason']!='stop':raise ValueError('Incomplete review')
                    value=_parse(choice['message']['content'])
                    keep=keeps(value,record)
                    result.update(status='complete',keep=keep,agreement=keep==result['expected_keep'],review=value)
                except (ValueError,KeyError,TypeError,httpx.HTTPError,jsonschema.ValidationError) as exc:
                    result.update(status='error',error=str(exc))
                write_json(output/row['id']/'result.json',result)
                print(key,result['status'],result.get('agreement'),flush=True)
                return result
        results=await asyncio.gather(*(one(i,r) for i,r in enumerate(selected)))
    write_json(output/'summary.json',dict(results=results,production_authorized=False,
        false_accepts=sum(r.get('keep',False) and not r['expected_keep'] for r in results),
        false_rejects=sum(r.get('keep') is False and r['expected_keep'] for r in results),
        errors=sum(r['status']=='error' for r in results)))


@app.command()
def run(output:Path, endpoints:list[str]=typer.Option(...,'--endpoint'),
        source:Path=Path('docs/reports/dfm14-accepted-inspection-20261007.jsonl')):
    config=dict(source_sha256=file_hash(source),contract=VERSION,code={str(p):file_hash(p) for p in
        [Path(__file__),Path('dfm14/generation_contract.py'),Path('dfm14/synthetic_review.py')]})
    with lock(output/'.controller.lock'):
        if (output/'configuration.json').exists() and load(output/'configuration.json')!=config:
            raise ValueError('Changed replay contract')
        write_json(output/'configuration.json',config)
        asyncio.run(execute(source,output,endpoints))


if __name__=='__main__':app()
