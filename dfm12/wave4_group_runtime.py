"""Pinned group-owned W4 successor; one endpoint and one 768-worker budget."""
import asyncio
from pathlib import Path
import sqlite3
from types import FunctionType

from . import wave4_shard_runtime as previous
from .io import file_hash,load

MODULE='dfm12.wave4_group_runtime'


def verify_partition(root):
    root=Path(root).resolve();bundle=root.parent
    receipt=load(bundle/'prepared.json');seal=load(bundle/'shard-runtime.json')
    if receipt.get('version')!=2 or receipt['target']!=770000:
        raise ValueError('Explicit group rebalance required')
    if seal.get('runtime_module')!=MODULE or seal.get('launch_authorized') is not True or seal['prepared_sha256']!=file_hash(bundle/'prepared.json'):
        raise ValueError('Group runtime seal mismatch')
    predecessor=Path(receipt['predecessor_root']);source=Path(receipt['source_root'])
    if file_hash(predecessor/'shard-runtime.json')!=receipt['predecessor_runtime_sha256']:
        raise ValueError('Predecessor seal drift')
    for path,sha in seal['implementation_pins'].items():
        if file_hash(path)!=sha:raise ValueError('Implementation drift: '+path)
    if seal['implementation_pins'].get(str(Path(__file__).resolve()))!=file_hash(__file__):
        raise ValueError('Group runtime unpinned')
    manifest=load(source/'manifest.json')
    if file_hash(source/'manifest.json')!=receipt['source_manifest_sha256'] or file_hash(root/'manifest.json')!=receipt['source_manifest_sha256']:
        raise ValueError('Source manifest drift')
    for name,sha in manifest['input_pins'].items():
        if file_hash(root/name)!=sha:raise ValueError('Input drift')
    for path,sha in manifest['implementation_pins'].items():
        if seal['implementation_pins'].get(path)!=sha:raise ValueError('Inherited pin missing')
    shards=receipt['shards'];allkeys=[tuple(k) for s in shards for k in s['groups']]
    if len(shards)!=8 or {s['worker'] for s in shards}!=set(range(8)) or len(allkeys)!=len(set(allkeys)):
        raise ValueError('Duplicate ownership')
    selected=next((s for s in shards if root.name==f"shard-{s['worker']}"),None)
    ownership=load(root/'ownership.json')
    if selected is None or any(ownership.get(k)!=v for k,v in selected.items()):raise ValueError('Ownership mismatch')
    if file_hash(root/'ownership.json')!=receipt['files'][root.name+'/ownership.json']:raise ValueError('Ownership drift')
    expected={}
    for i in range(8):
        with previous.readonly(predecessor/f'shard-{i}'/'jobs.sqlite') as db:
            if db.execute('SELECT sum(active) FROM groups').fetchone()[0] or db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:raise ValueError('Predecessor active')
            expected.update({(l,f):t for l,f,t in db.execute('SELECT language,family,target FROM groups')})
    if set(allkeys)!=set(expected) or sum(expected.values())!=770000:raise ValueError('Missing quota ownership')
    for shard in shards:
        if shard['endpoint']!=f"http://127.0.0.1:{8800+shard['worker']}/v1":raise ValueError('Endpoint overlap')
        if not shard['runnable_groups'] or not {tuple(k) for k in shard['runnable_groups']}<={tuple(k) for k in shard['groups']}:raise ValueError('Invalid runnable subset')
    with previous.readonly(root/'jobs.sqlite') as db:
        actual={(l,f):t for l,f,t in db.execute('SELECT language,family,target FROM groups')}
        if actual!={k:expected[k] for k in map(tuple,selected['groups'])}:raise ValueError('Quota mismatch')
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()!=(receipt['source_manifest_sha256'],):raise ValueError('Ledger seal drift')
        if db.execute('SELECT count(*) FROM groups WHERE accepted<0 OR active<0 OR accepted+active>target OR attempts>6*target').fetchone()[0]:raise ValueError('Invalid counters')
        for l,f,a,n in db.execute('SELECT language,family,accepted,active FROM groups'):
            counts=dict(db.execute('SELECT status,count(*) FROM jobs WHERE language=? AND family=? GROUP BY status',(l,f)))
            if a!=counts.get('accepted',0) or n!=counts.get('running',0):raise ValueError('Counter mismatch')
        if db.execute('SELECT count(*) FROM jobs j LEFT JOIN groups g ON j.language=g.language AND j.family=g.family WHERE g.language IS NULL').fetchone()[0]:raise ValueError('Foreign job')
        db.execute('ATTACH DATABASE ? AS registry',((bundle/'fingerprints.sqlite').as_uri()+'?mode=ro',))
        if db.execute("SELECT count(*) FROM jobs j LEFT JOIN registry.fingerprints f ON j.fingerprint=f.fingerprint WHERE j.status='accepted' AND (f.owner IS NULL OR f.owner!=j.id)").fetchone()[0]:raise ValueError('Global ownership missing')
    return manifest,selected


def controller(owner,root,claims):
    c=previous.controller(owner,root,claims)
    c.verify=lambda path:verify_partition(path)[0]
    allowed={tuple(k) for k in load(root/'ownership.json')['runnable_groups']}
    base=c.Ledger
    class Ledger(base):
        def remaining_groups(self):
            return [r for r in super().remaining_groups() if (r['language'],r['family']) in allowed and not r['blocked']]
        def publish(self):
            owner.remaining_hint=any((r['language'],r['family']) in allowed and not r['blocked'] and r['accepted']<r['target'] and r['attempts']<6*r['target'] for r in self.group_snapshot.values())
        def reserve(self,provider,unavailable,root):
            self.allowed_groups=frozenset((r['language'],r['family']) for r in self.remaining_groups())
            if not self.allowed_groups:
                self.publish();return None
            result=super().reserve(provider,unavailable,root)
            self.refresh()
            return result
    c.Ledger=Ledger
    write=c.write_json
    def runtime_write(path,value):
        if path.name=='runtime.json':value=dict(value,group_runtime_module=MODULE,runnable_groups=sorted(allowed))
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    asyncio.run(run(p.parse_args().root))
