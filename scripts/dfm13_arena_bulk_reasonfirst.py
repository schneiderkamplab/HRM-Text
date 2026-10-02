"""Minimal full-pass adapter: tested reason-first thinking reviewer, isolated ledger."""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


HERE=Path(__file__).parent
recovery=module('_stronger_recovery',HERE/'dfm13_arena_bulk_recovery.py')
probe=module('_tested_reasonfirst',HERE/'dfm13_arena_reasonfirst_probe.py')
bulk=recovery.bulk;base=recovery.base
original_request=bulk.request


def request(row):
    payload=original_request(row)
    schema=base.obj(dict(reason={'type':'string','maxLength':2400},verdict={'type':'string','enum':list(base.DISPOSITIONS)}))
    payload['messages'][0]['content']=probe.PROMPT
    data=base.visible(row);data['output_schema']=schema
    payload['messages'][1]['content']=json.dumps(data,ensure_ascii=False)
    payload.update(max_tokens=8192,chat_template_kwargs={'enable_thinking':True})
    payload['response_format']['json_schema']['schema']=schema
    return payload


def main():
    import aiohttp
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--servers-ready',action='store_true');args=parser.parse_args()
    if not args.servers_ready:parser.error('--servers-ready required')
    root,previous=args.root.resolve(),args.previous.resolve()
    with base.lock(root/'controller.lock'):
        if not (root/'manifest.json').exists():
            old=base.load(previous/'manifest.json');db=bulk.database(root)
            if db.execute('SELECT count(*) FROM jobs').fetchone()[0]:raise ValueError('Partial preparation; refusing overwrite')
            db.execute('ATTACH DATABASE ? AS prior',('file:'+str(previous/'ledger.sqlite')+'?mode=ro',))
            # Only immutable row locations are copied; every prior result stays in its original root.
            db.execute('INSERT INTO main.jobs(seq,source,line,offset,length,source_id) SELECT seq,source,line,offset,length,source_id FROM prior.jobs')
            db.commit()
            if db.execute('SELECT count(*) FROM main.jobs').fetchone()[0]!=205242:raise ValueError('Expected full corpus')
            db.close();pins=dict(old['pins'])
            for path in (Path(__file__),HERE/'dfm13_arena_reasonfirst_probe.py',previous/'manifest.json',previous/'seal.json'):
                pins[str(path.resolve())]=base.file_hash(path)
            manifest=dict(old,version='arena-bulk-reasonfirst-thinking-v3',pins=pins,
                prior_pass_root=str(previous),prior_results_preserved_separately=True,
                full_corpus_second_pass=True,thinking=True,max_tokens=8192,timeout_seconds=600,
                reason_first=True,prompt_sha256=base.digest(probe.PROMPT),unchanged_reviewer=False,
                preserved_complete=0,requeued_unknown=0,reviewer_reference='tested reasonfirst-thinking32-v1')
            base.write_json(root/'manifest.json',manifest)
            base.write_json(root/'seal.json',dict(manifest_sha256=base.file_hash(root/'manifest.json')))
    bulk.request=request
    # Transport timeout only; preserve the existing ten-second health preflight.
    original_timeout=aiohttp.ClientTimeout
    def timeout(*a,**kw):
        if kw.get('total')==240:kw['total']=600
        return original_timeout(*a,**kw)
    aiohttp.ClientTimeout=timeout
    # Validate against this request's schema, not the earlier 2000-character reason limit.
    def validate(value):
        import jsonschema
        schema=base.obj(dict(reason={'type':'string','maxLength':2400},verdict={'type':'string','enum':list(base.DISPOSITIONS)}))
        jsonschema.validate(value,schema)
        if not value['reason'].strip():raise ValueError('Empty reason')
        return value
    bulk.simple.validate=validate
    sys.argv=[sys.argv[0],'--root',str(root),'--servers-ready']
    recovery.main()


if __name__=='__main__':main()
