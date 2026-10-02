"""Isolated bulk recovery: preserve v1, fresh HTTP connections, bounded retries."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import sqlite3

PATH=Path(__file__).with_name('dfm13_arena_bulk_audit.py')
spec=importlib.util.spec_from_file_location('_bulk_recovery_engine',PATH)
bulk=importlib.util.module_from_spec(spec);spec.loader.exec_module(bulk)
base=bulk.base


def prepare(root,previous):
    root,previous=Path(root).resolve(),Path(previous).resolve()
    with base.lock(previous/'controller.lock'),base.lock(root/'controller.lock'):
        if (root/'manifest.json').exists():raise ValueError('Recovery requires a new root')
        old=base.load(previous/'manifest.json')
        if base.file_hash(previous/'manifest.json')!=base.load(previous/'seal.json')['manifest_sha256']:raise ValueError('Source seal drift')
        source=sqlite3.connect(previous/'ledger.sqlite');dest=bulk.database(root)
        source.backup(dest);source.close()
        dest.execute('CREATE TABLE recovery_attempts AS SELECT seq,status,result FROM jobs WHERE status IN ("abort_status_unknown","inflight")')
        retry=dest.execute('SELECT count(*) FROM recovery_attempts').fetchone()[0]
        complete=dest.execute('SELECT count(*) FROM jobs WHERE status="complete"').fetchone()[0]
        dest.execute('UPDATE jobs SET status="pending",result=NULL WHERE seq IN (SELECT seq FROM recovery_attempts)');dest.commit();dest.close()
        pins=dict(old['pins'])
        for path in (Path(__file__),Path(__file__).parents[1]/'tests/test_dfm13_arena_bulk_recovery.py',previous/'manifest.json',previous/'seal.json'):
            pins[str(path.resolve())]=base.file_hash(path)
        manifest=dict(old,version='arena-bulk-semantic-recovery-v2',pins=pins,prior_root=str(previous),
            preserved_complete=complete,requeued_unknown=retry,force_close=True,max_transport_attempts=3,
            unchanged_reviewer=True,prior_raw_responses_root=str(previous/'raw'))
        base.write_json(root/'manifest.json',manifest)
        base.write_json(root/'seal.json',dict(manifest_sha256=base.file_hash(root/'manifest.json')))
        return manifest


async def retry_query(original,session,endpoint,payload,writer,metadata,root):
    import aiohttp
    trace=[]
    for attempt in range(1,4):
        try:
            response=await original(session,endpoint,payload,writer,dict(metadata,transport_attempt=attempt))
            if trace:base.write_json(root/'transport-attempts'/f"{metadata['seq']}.json",dict(seq=metadata['seq'],failed=trace,successful_raw_request_id=response['raw_request_id']))
            return response
        except (aiohttp.ClientConnectionError,aiohttp.ClientPayloadError,asyncio.TimeoutError) as exc:
            trace.append(dict(attempt=attempt,error=repr(exc),status='unknown',endpoint=endpoint))
            base.write_json(root/'transport-attempts'/f"{metadata['seq']}.json",dict(seq=metadata['seq'],failed=trace))
            if attempt==3:raise
            await asyncio.sleep(.5*attempt)


def main():
    import aiohttp
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--previous',type=Path);p.add_argument('--servers-ready',action='store_true');a=p.parse_args()
    if not a.servers_ready:p.error('--servers-ready required')
    root=a.root.resolve()
    if a.previous:prepare(root,a.previous)
    with base.lock(root/'controller.lock'):
        m=base.load(root/'manifest.json')
        if base.file_hash(root/'manifest.json')!=base.load(root/'seal.json')['manifest_sha256']:raise ValueError('Seal drift')
        for path,h in m['pins'].items():
            if base.file_hash(path)!=h:raise ValueError('Dependency drift')
        original_connector=aiohttp.TCPConnector
        def connector(*args,**kwargs):
            kwargs['force_close']=True
            return original_connector(*args,**kwargs)
        aiohttp.TCPConnector=connector
        original=base.raw_query
        async def query(session,endpoint,payload,writer,metadata):
            return await retry_query(original,session,endpoint,payload,writer,metadata,root)
        base.raw_query=query
        asyncio.run(bulk.run(root,m))


if __name__=='__main__':main()
