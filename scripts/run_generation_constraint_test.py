"""Bounded sealed26B prompt test using the existing pilot stages; no servers."""
import argparse
import asyncio
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import aiohttp

from dfm12.generation_constraints import ROOT, DEFAULT_MODEL, verify
from dfm12.io import file_hash, load, lock, write_json
from dfm12 import wave4_synthetic_campaign
from dfm12.wave_compact_review import install


def inputs(source, arm):
    manifest = verify(source)
    if manifest['default_preparation_model'] != DEFAULT_MODEL:
        raise ValueError('This bounded runner requires selected26B inputs')
    requests = load(source/arm/'generation-requests.json')
    specs = load(source/'specifications.json')
    c = install(wave4_synthetic_campaign.controller())
    if len(specs) != 12 or set(requests) != {c.pilot.slot_key(s) for s in specs}:
        raise ValueError('Expected exactly12 frozen cases')
    def request(spec, generation, endpoint_models=None):
        envelope = requests[c.pilot.slot_key(spec)]
        payload = deepcopy(envelope['request'])
        payload['response_format'] = dict(type='json_schema',json_schema=dict(
            name='conversation',strict=True,schema=envelope['schema']))
        return payload
    c.v6.generation_request = request
    # Pilot applies decoding defaults before compact transport; prove final bytes.
    for spec in specs:
        payload=request(spec,None)
        payload.update(temperature=.75 if spec['family']=='tool-dialogue' else .65,repetition_penalty=1.15)
        transport,schema=c.v6.compact_request(payload)
        expected=requests[c.pilot.slot_key(spec)]
        if transport != expected['request'] or schema != expected['schema']:
            raise ValueError('Existing pilot changes frozen request')
    return manifest,c,specs


async def run(source, output, arm, review_existing=None, pending_database=None):
    manifest,c,specs = inputs(source,arm)
    if output.exists():
        raise ValueError('Fresh execution output required; preserve prior results')
    endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)]
    budget=c.v6.Budget(manifest['tokenizer_dir'])
    review,generation=c.v6.adapters()
    candidates={}
    if pending_database is not None:
        from dfm12.io import digest
        db=sqlite3.connect(pending_database.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            for key,encoded in db.execute("SELECT id,payload FROM jobs WHERE stage='audit' AND status IN ('pending','failed')"):
                row=json.loads(encoded)['record']
                if row.get('task')=='instruction':
                    candidates[key]=(row,digest(row))
        finally:
            db.close()
        if not candidates:
            raise ValueError('No pending/failed instruction records')
    if review_existing is not None:
        paths=sorted(review_existing.glob('**/candidates/*.json'))
        for path in paths:
            key=path.stem
            if key in candidates:
                raise ValueError('Duplicate candidate keys')
            candidates[key]=(load(path),file_hash(path))
        if not candidates:
            raise ValueError('No saved candidates')
    total=len(candidates) if candidates else len(specs)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
        health={}
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status()
                document=await response.json()
            c.v6.endpoint_limit(document)
            match=[m for m in document['data'] if m['id']==DEFAULT_MODEL]
            if len(match)!=1 or Path(match[0].get('root','')).resolve()!=Path(manifest['tokenizer_dir']).resolve():
                raise ValueError('Actual26B snapshot mismatch')
            health[endpoint]=document
        output.mkdir(parents=True)
        write_json(output/'execution.json',dict(source=str(source.resolve()),arm=arm,
            source_manifest_sha256=file_hash(source/'manifest.json'),
            runner_sha256=file_hash(__file__),total=total,concurrency_per_server=1,max_concurrency=8,health=health,
            reviewer='jjzha-style-whole-conversation-256',
            review_adapter_sha256=file_hash(Path(__file__).resolve().parents[1]/'dfm12/wave_compact_review.py'),
            admission_authorized=False,independent_review_required=True))
        if candidates:
            write_json(output/'candidate-inputs.json',dict(root=str((pending_database or review_existing).resolve()),
                hashes={k:v[1] for k,v in candidates.items()},generation_calls=0))
        write_json(output/'source-holds.json',load(source/'source-holds.json'))
        stages=c.v6.Stages(output,budget,c.v6.RawResponseWriter(output/'raw'),session,query=c.stream_query)
        seen=set()
        pending=asyncio.Queue()
        for spec in (list(candidates) if candidates else specs):
            pending.put_nowait(spec)
        completed=[]
        async def worker(endpoint):
            while not pending.empty():
                spec=pending.get_nowait()
                if candidates:
                    key=spec
                    candidate=candidates[key][0]
                    if pending_database is not None:
                        record=deepcopy(candidate)
                        record.setdefault('family','instruction')
                        record.setdefault('tools',[])
                        write_json(output/'candidates'/f'{key}.json',candidate)
                    elif candidate['language'] in ('lt','lv'):
                        from dfm12.baltic_synthetic_specs import audit_record
                        record=audit_record(candidate)
                    else:
                        record=c.v6.audit_record(candidate)
                    payload,schema=c.v6.compact_request(c.v6.review_request(record,review))
                    state=await stages.call(key,'review',payload,schema,endpoint,
                        c.v6.endpoint_limit(health[endpoint]))
                    outcome=dict(id=key,status=state['status'],terminal=True,
                        candidate_sha256=candidates[key][1],admission_authorized=False)
                    if state['status']=='complete':
                        try:
                            if pending_database is not None:
                                value=review.validate(state['output'])
                                outcome.update(compact_verdict=value['verdict'],compact_reason=value['reason'],
                                    semantic_keep=value['verdict']=='keep',effective_keep=False,
                                    source_holds_preserved=True)
                            else:
                                outcome.update(c.v6.review_result(state['output'],record,review))
                        except (ValueError, TypeError) as exc:
                            outcome.update(status='invalid_review',error=str(exc),
                                raw_decision=state['output'],effective_keep=False)
                    else:
                        outcome['review_state']=state
                    write_json(output/'outcomes'/f'{key}.json',outcome)
                else:
                    outcome=await c.pilot.process(spec,endpoint,output,stages,health,generation,review,seen)
                completed.append(outcome)
                write_json(output/'progress.json',dict(total=total,terminal=len(completed),
                    kept=sum(o.get('effective_keep') is True for o in completed),
                    verdicts=[o.get('compact_verdict',o.get('status')) for o in completed],
                    admission_authorized=False))
        await asyncio.gather(*(worker(endpoint) for endpoint in endpoints))
        write_json(output/'complete.json',dict(terminal=total,admission_authorized=False,
            independent_review_required=True,source_holds_preserved=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=ROOT)
    p.add_argument('--arm',choices=['baseline','constrained'],default='constrained')
    p.add_argument('--output',type=Path)
    p.add_argument('--execute',action='store_true',help='Only after switchback owner releases endpoints')
    p.add_argument('--review-existing',type=Path,help='Audit saved candidates only; no generation')
    p.add_argument('--pending-database',type=Path,help='Read-only pending/failed instruction audit jobs; never admit or clear holds')
    a=p.parse_args()
    if not a.execute:
        print('CPU ready:',len(inputs(a.source,a.arm)[2]),'cases; no endpoint calls')
    else:
        if a.output is None:
            p.error('--output fresh directory required')
        with lock(a.output.parent/(a.output.name+'.launch.lock')):
            asyncio.run(run(a.source,a.output,a.arm,a.review_existing,a.pending_database))


if __name__=='__main__':
    main()
