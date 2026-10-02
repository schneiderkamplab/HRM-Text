"""Bounded post-terminal whitespace review recovery; never generates corrections."""
import argparse
import asyncio
import importlib.util
from pathlib import Path
import sys
import time

P=Path(__file__).with_name('dfm13_arena_length_pilot_v2.py')
spec=importlib.util.spec_from_file_location('_review_only_contract',P)
contract=importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
pilot=contract.pilot
base=pilot.base


def eligible(stage, result, has_completed):
    return (stage in ('retry_audit','fresh_reaudit') and not has_completed
            and pilot.bucket(result,stage)=='whitespace')


def terminal(db, expected):
    counts={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
            for t in ('accepted','rejected','needs_review')}
    unique=db.execute('SELECT count(*) FROM (SELECT seq FROM accepted UNION SELECT seq FROM rejected UNION SELECT seq FROM needs_review)').fetchone()[0]
    active=db.execute('SELECT count(*) FROM attempts WHERE status="inflight"').fetchone()[0]
    return sum(counts.values())==unique==expected and active==0


def plan(root,source,limit):
    if not 1<=limit<=128:
        raise ValueError('Bounded diagnostic limit must be 1..128')
    root.mkdir(parents=True,exist_ok=True)
    if (root/'plan.json').exists():
        raise ValueError('Existing plan must not be overwritten')
    source_plan=pilot.repair.verify(source)
    paths=[Path(__file__).resolve(),P.resolve(),Path(pilot.__file__).resolve(),
           pilot.P.resolve(),base.ROOT/'tests/test_dfm13_arena_review_only_recovery.py',
           source/'plan.json',source/'seal.json']
    pins=dict(source_plan['pins'])
    pins.update({str(p):base.file_hash(p) for p in paths})
    for module in tuple(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path and Path(path).suffix=='.py' and Path(path).resolve().is_relative_to(base.ROOT):
            pins[str(Path(path).resolve())]=base.file_hash(path)
    value=dict(version='arena-review-only-whitespace-v1',source=str(source),limit=limit,
        source_total=source_plan['manifest']['total'],pins=pins,
        status='planned_not_launched',terminal_receipt_required=True,
        stages=['retry_audit','fresh_reaudit'],thinking=True,max_tokens=8192,
        response_format='json_object',strict_cpu_validation=True,max_attempts_per_stage=1,
        correction_generation=False,no_admission=True,no_upload=True,
        full_followup_automatic=False,created=time.time())
    base.write_json(root/'plan.json',value)
    base.write_json(root/'plan-seal.json',dict(sha256=base.file_hash(root/'plan.json')))
    return value


def verify_plan(root):
    value=base.load(root/'plan.json')
    if base.file_hash(root/'plan.json')!=base.load(root/'plan-seal.json')['sha256']:
        raise ValueError('Plan drift')
    for path,digest in value['pins'].items():
        if base.file_hash(path)!=digest:
            raise ValueError('Pinned dependency drift: '+path)
    return value


def materialize(root):
    value=verify_plan(root)
    source=Path(value['source'])
    if (root/'manifest.json').exists():
        raise ValueError('Already materialized')
    if not (source/'complete.json').exists():
        raise ValueError('Source repair run is not terminal; no jobs selected')
    with base.lock(source/'controller.lock'):
        db=pilot.repair.readonly(source/'ledger.sqlite')
        if not terminal(db,value['source_total']):
            raise ValueError('Source tables/attempts are not terminal')
        pins=dict(value['pins'])
        jobs=[]
        seen=set()
        candidates=db.execute('SELECT a.seq,a.stage,a.n,a.record FROM attempts a JOIN needs_review n ON n.seq=a.seq WHERE a.n=(SELECT max(b.n) FROM attempts b WHERE b.seq=a.seq AND b.stage=a.stage) ORDER BY a.seq,a.stage').fetchall()
        for seq,stage,n,record in candidates:
            result=base.strict_json(record)
            complete=db.execute('SELECT 1 FROM attempts WHERE seq=? AND stage=? AND status="complete"',(seq,stage)).fetchone()
            if seq in seen or not eligible(stage,result,bool(complete)):
                continue
            raw=source/'raw'/str(seq%8)/(result['raw_request_id']+'.request.json')
            response=raw.with_name(raw.name.replace('.request.json','.response.json'))
            payload=base.load(raw)['request']
            schema=base.obj(dict(reason={'type':'string','maxLength':2400},
                                verdict={'type':'string','enum':list(base.DISPOSITIONS)}))
            # Preserve exact target/history; restore CPU contract for JSON-object prompting.
            payload['response_format']['json_schema']['schema']=schema
            jobs.append(dict(seq=seq,stage=stage,attempt=n,kind='whitespace',
                original_request=payload,cpu_schema=schema,original_failure=result,
                raw_request_path=str(raw),raw_response_path=str(response),
                final_source_outcome=base.strict_json(db.execute('SELECT record FROM needs_review WHERE seq=?',(seq,)).fetchone()[0])))
            for p in (raw,response):
                pins[str(p)]=base.file_hash(p)
            seen.add(seq)
            if len(jobs)==value['limit']:
                break
        db.close()
    original=base.load(source/'plan.json')['manifest']
    base.write_json(root/'jobs.json',jobs)
    for p in (root/'jobs.json',root/'plan.json',root/'plan-seal.json',source/'complete.json'):
        pins[str(p)]=base.file_hash(p)
    manifest=dict(value,version='arena-review-only-whitespace-materialized-v1',
        total=len(jobs),pins=pins,endpoints=original['endpoints'],tokenizer_dir=original['tokenizer_dir'],
        context_limit=original['context_limit'],status='prepared_not_launched',
        per_endpoint_concurrency=1,whole_target_review=True)
    base.write_json(root/'manifest.json',manifest)
    base.write_json(root/'seal.json',dict(sha256=base.file_hash(root/'manifest.json')))
    return manifest


def whole_target(payload,**kwargs):
    result=contract.compact(payload,**kwargs)
    result['messages'][0]['content']+=(
        '\nReview the WHOLE target, including new and retained factual claims, names, dates, '
        'numerical/code boundary cases, explicit constraints, completeness and unsupported premises. '
        'Do not only confirm the previously flagged defect. Essential unverified claims are not '
        'made safe by calling them lore. Do not emit a corrected answer.')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['plan','materialize','run'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--limit',type=int,default=32)
    parser.add_argument('--authorized-review-only',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve()
    with base.lock(root/'controller.lock'):
        if args.command=='plan':
            plan(root,args.source.resolve(),args.limit)
        elif args.command=='materialize':
            materialize(root)
        else:
            if not args.authorized_review_only:
                parser.error('Explicit --authorized-review-only required; no automatic launch')
            manifest=pilot.verify(root)
            jobs=base.load(root/'jobs.json')
            if any(j['kind']!='whitespace' or j['stage'] not in ('retry_audit','fresh_reaudit') for j in jobs):
                raise ValueError('Review-only job invariant violated')
            pilot.compact=whole_target
            asyncio.run(pilot.run(root,manifest))


if __name__=='__main__':
    main()
