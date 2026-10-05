"""Non-admitting sidecars and post-completion retries; never modify source audits."""
import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import time

import aiohttp

from dfm12.io import file_hash, load, lock, write_json
from dfm12.multilingual_calibration_v6 import raw_query, strict_json, RawResponseWriter
from dfm12.wave_compact_review import ISSUES, VERDICTS, MODEL
from dfm12.wave_synthetic_runtime import endpoint_limit


def classify(row):
    raw=row.get('raw',{})
    if raw.get('finish_reason')!='stop':
        return dict(status='incomplete_or_unknown',admission_authorized=False)
    value=row.get('raw_decision')
    if value is None:
        try: value=strict_json(raw['content'])
        except (ValueError,KeyError,TypeError):
            return dict(status='invalid_json',admission_authorized=False)
    if (not isinstance(value,dict) or set(value)-{'verdict','issues','reason'}
            or value.get('verdict') not in VERDICTS or not isinstance(value.get('issues'),list)
            or any(not isinstance(i,str) or i not in ISSUES for i in value['issues'])
            or ('reason' in value and not isinstance(value['reason'],str))):
        return dict(status='invalid_schema',admission_authorized=False)
    if value['verdict']=='keep' and value['issues']:
        return dict(status='contradictory_keep',decision=value,admission_authorized=False)
    warnings=[]
    if not value.get('reason','').strip(): warnings.append('missing_rationale')
    if len(value['issues'])!=len(set(value['issues'])): warnings.append('duplicate_issue_labels')
    if value['verdict']!='keep' and not value['issues']: warnings.append('missing_issue_label')
    if len(value.get('reason',''))>500: warnings.append('overlong_rationale')
    return dict(status='usable_model_verdict',decision=value,warnings=warnings,
        semantic_quality_verified=False,source_holds_preserved=True,admission_authorized=False)


def snapshot(root,output,limit=0):
    output.mkdir(parents=True,exist_ok=False)
    paths=sorted((root/'outcomes').glob('*.json'))
    if limit: paths=paths[:limit]
    counts=Counter(); retry=[]
    with (output/'classifications.jsonl').open('w') as f:
        for path in paths:
            row=load(path); result=classify(row)
            counts[result['status']]+=1
            if result['status']=='usable_model_verdict':
                counts['verdict:'+result['decision']['verdict']]+=1
                for warning in result['warnings']: counts['warning:'+warning]+=1
                if row['status']=='invalid': counts['recovered_from_invalid']+=1
            if row['status']=='interrupted_unknown':
                request=root/'requests'/path.name
                if file_hash(request)!=row['request_sha256']: raise ValueError('Interrupted request drift')
                retry.append(dict(id=path.stem,request=str(request.resolve()),sha256=file_hash(request)))
            f.write(json.dumps(dict(id=path.stem,parent_sha256=file_hash(path),**result),ensure_ascii=False)+'\n')
    write_json(output/'retry-after-completion.json',dict(source=str(root.resolve()),requests=retry,
        requires_completion=str((root/'complete.json').resolve()),admission_authorized=False))
    write_json(output/'summary.json',dict(snapshot_rows=len(paths),counts=dict(counts),
        source=str(root.resolve()),retry_count=len(retry),snapshot_only=True,
        classifications_sha256=file_hash(output/'classifications.jsonl'),admission_authorized=False))


async def retry_after_completion(root,output,invalid_only=False,concurrency=4):
    # No inference while the original bulk client remains incomplete.
    while not (root/'complete.json').exists(): await asyncio.sleep(10)
    output.mkdir(parents=True,exist_ok=False)
    pending=[]
    for path in sorted((root/'outcomes').glob('*.json')):
        row=load(path)
        if row['status']==('invalid' if invalid_only else 'interrupted_unknown'):
            request=root/'requests'/path.name
            sha=file_hash(request)
            if not invalid_only and sha!=row['request_sha256']: raise ValueError('Interrupted request drift')
            pending.append((path.stem,request,sha))
    write_json(output/'manifest.json',dict(total=len(pending),source=str(root.resolve()),
        completion_sha256=file_hash(root/'complete.json'),runner_sha256=file_hash(__file__),
        admission_authorized=False,concurrency_per_server=concurrency,invalid_only=invalid_only))
    queue=asyncio.Queue()
    for item in pending: queue.put_nowait(item)
    writer=RawResponseWriter(output/'raw')
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
        endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status(); document=await response.json()
            endpoint_limit(document)
        async def worker(endpoint):
            while not queue.empty():
                key,path,sha=queue.get_nowait(); envelope=await asyncio.to_thread(load,path)
                if await asyncio.to_thread(file_hash,path)!=sha or envelope['request']['model']!=MODEL:
                    raise ValueError('Retry request/model drift')
                row=dict(id=key,parent_request_sha256=sha,admission_authorized=False)
                try:
                    row['raw']=await raw_query(session,endpoint,envelope['request'],writer,
                        dict(id=key,stage='interrupted_retry',**envelope['budget']))
                    row['assessment']=classify(row)
                except Exception as exc: row['error']=repr(exc)
                await asyncio.to_thread(write_json,output/'outcomes'/f'{key}.json',row)
        await asyncio.gather(*(worker(e) for e in endpoints for _ in range(concurrency)))
    write_json(output/'complete.json',dict(total=len(pending),admission_authorized=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--retry-after-completion',action='store_true')
    p.add_argument('--invalid-only',action='store_true')
    p.add_argument('--concurrency',type=int,choices=range(1,129),default=4)
    a=p.parse_args()
    with lock(a.output.parent/(a.output.name+'.lock')):
        if a.retry_after_completion: asyncio.run(retry_after_completion(a.root,a.output,a.invalid_only,a.concurrency))
        else: snapshot(a.root,a.output,a.limit)
