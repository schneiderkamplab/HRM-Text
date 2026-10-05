"""Sealed final W4 top-up, independent workers and explicit absolute ceilings."""
import asyncio
import importlib
from pathlib import Path
from types import FunctionType

from . import wave4_shard_runtime as previous
from . import wave4_topup_ledger as ledger_policy
from .io import file_hash,load

MODULE='dfm12.wave4_topup_runtime'


def verify_partition(root):
    root=Path(root).resolve();bundle=root.parent
    prepared=load(bundle/'prepared.json');seal=load(bundle/'shard-runtime.json')
    if (prepared.get('version')!=3 or prepared.get('target')!=735000
            or prepared.get('recovery_complete') is not True
            or prepared.get('final_topup') is not True
            or seal.get('runtime_module')!=MODULE
            or seal.get('launch_authorized') is not True
            or seal['prepared_sha256']!=file_hash(bundle/'prepared.json')):
        raise ValueError('Explicit final-topup and completed recovery seal required')
    for path,sha in seal['implementation_pins'].items():
        if file_hash(path)!=sha:
            raise ValueError('Implementation drift: '+path)
    for module in (__import__(__name__,fromlist=['']),ledger_policy):
        if seal['implementation_pins'].get(str(Path(module.__file__).resolve()))!=file_hash(module.__file__):
            raise ValueError('Unpinned top-up implementation')
    shards=prepared['shards']
    keys=[tuple(k) for s in shards for k in s['groups']]
    policies={(r['language'],r['family']):r for r in prepared['quotas']}
    if (len(shards)!=8 or {s['worker'] for s in shards}!=set(range(8))
            or len(keys)!=66 or len(set(keys))!=66 or set(keys)!=set(policies)
            or sum(r['target'] for r in policies.values())!=735000):
        raise ValueError('Invalid disjoint quota ownership')
    selected=next(s for s in shards if root.name==f"shard-{s['worker']}")
    for shard in shards:
        if shard['endpoint']!=f"http://127.0.0.1:{8800+shard['worker']}/v1":
            raise ValueError('Endpoint ownership drift')
    ownership=load(root/'ownership.json')
    if any(ownership.get(k)!=v for k,v in selected.items()):
        raise ValueError('Ownership mismatch')
    if file_hash(root/'ownership.json')!=prepared['files'][root.name+'/ownership.json']:
        raise ValueError('Ownership pin drift')
    manifest=load(root/'manifest.json')
    if file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Manifest mismatch')
    if manifest.get('target')!=735000 or manifest.get('topup_policy')!='wave4-final-topup-v1':
        raise ValueError('Wrong runtime manifest')
    for section in ('implementation_pins','external_pins'):
        for path,sha in manifest[section].items():
            if file_hash(path)!=sha:
                raise ValueError('Manifest pin drift: '+path)
    for path,sha in manifest['input_pins'].items():
        if file_hash(root/path)!=sha:
            raise ValueError('Input drift: '+path)
    with previous.readonly(root/'jobs.sqlite') as db:
        actual={}
        for row in db.execute('SELECT language,family,target,original_target,attempt_limit,accepted_floor FROM groups'):
            key=row[:2];actual[key]=row[2:]
        expected={key:tuple(policies[key][k] for k in ('target','original_target','attempt_limit','accepted_floor'))
            for key in map(tuple,selected['groups'])}
        if actual!=expected:
            raise ValueError('Quota/attempt ceiling drift')
        if db.execute('''SELECT count(*) FROM groups WHERE accepted<accepted_floor OR active<0
                OR accepted+active>target OR attempts>attempt_limit''').fetchone()[0]:
            raise ValueError('Counter invariants violated')
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()!=(file_hash(root/'manifest.json'),):
            raise ValueError('Ledger seal mismatch')
        for language,family,accepted,active in db.execute('SELECT language,family,accepted,active FROM groups'):
            counts=dict(db.execute('SELECT status,count(*) FROM jobs WHERE language=? AND family=? GROUP BY status',(language,family)))
            if accepted!=counts.get('accepted',0) or active!=counts.get('running',0):
                raise ValueError('Job counter mismatch')
        db.execute('ATTACH DATABASE ? AS registry',((bundle/'fingerprints.sqlite').as_uri()+'?mode=ro',))
        if db.execute("SELECT count(*) FROM jobs j LEFT JOIN registry.fingerprints f ON j.fingerprint=f.fingerprint WHERE j.status='accepted' AND (f.owner IS NULL OR f.owner!=j.id)").fetchone()[0]:
            raise ValueError('Global accepted fingerprint ownership missing')
    return manifest,selected


def controller(owner,root,claims):
    c=previous.controller(owner,root,claims)
    c.verify=lambda path:verify_partition(path)[0]
    prepared=load(root.parent/'prepared.json')
    adapter=importlib.import_module(prepared['clean_keep_adapter'])
    pins=load(root.parent/'shard-runtime.json')['implementation_pins']
    if pins.get(str(Path(adapter.__file__).resolve()))!=file_hash(adapter.__file__):
        raise ValueError('Clean-keep adapter must be frozen and pinned')
    installed=adapter.install(c)
    if installed is not None and installed is not c:
        raise ValueError('Adapter must install on the private controller')
    allowed=load(root/'ownership.json')['runnable_groups']
    ledger_policy.install(c,owner,allowed)
    write=c.write_json
    def runtime_write(path,value):
        if path.name=='runtime.json':
            value=dict(value,topup_runtime_module=MODULE,topup_target=735000,
                original_family_attempt_multiplier=12,clean_keep_adapter=prepared['clean_keep_adapter'],
                final_topup=True)
        return write(path,value)
    c.write_json=runtime_write
    return c


async def run(root):
    runner=FunctionType(previous.run.__code__,dict(previous.run.__globals__,
        verify_partition=verify_partition,controller=controller),previous.run.__name__,
        previous.run.__defaults__,previous.run.__closure__)
    await runner(root)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    asyncio.run(run(parser.parse_args().root))
