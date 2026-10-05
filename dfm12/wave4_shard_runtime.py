"""Whole-language W4 processes with independent ledgers and global dedup."""
import asyncio
from pathlib import Path
import sqlite3

from . import wave4_admission_fast as previous
from . import wave4_batched_runtime as batching
from . import wave4_disk_pipeline as disk
from .baltic_async_io import claim as local_claim
from .io import file_hash, load, write_json
from .wave4_shard_prepare import FingerprintRegistry

MODULE = 'dfm12.wave4_shard_runtime'


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)


def verify_partition(root):
    root = Path(root).resolve()
    parent = root.parent
    receipt = load(parent/'prepared.json')
    seal = load(parent/'shard-runtime.json')
    source = Path(receipt['source_root'])
    if (seal.get('runtime_module') != MODULE or seal.get('launch_authorized') is not True
            or seal.get('prepared_sha256') != file_hash(parent/'prepared.json')
            or receipt['source_manifest_sha256'] != file_hash(source/'manifest.json')):
        raise ValueError('Explicit shard launch/source seal required')
    from .wave4_compact_handoff import verify_independent_launch
    verify_independent_launch(source)
    pins = seal['implementation_pins']
    for module in (__import__(__name__, fromlist=['']), previous, batching, disk,
                   __import__('dfm12.wave4_shard_prepare', fromlist=[''])):
        if pins.get(str(Path(module.__file__).resolve())) != file_hash(module.__file__):
            raise ValueError('Shard dependency pin drift')
    for path, sha in pins.items():
        if file_hash(path) != sha:
            raise ValueError('Shard implementation drift: '+path)
    manifest = load(source/'manifest.json')
    for path, sha in manifest['implementation_pins'].items():
        if pins.get(path) != sha or file_hash(path) != sha:
            raise ValueError('Original implementation pin drift')
    if file_hash(root/'manifest.json') != receipt['source_manifest_sha256']:
        raise ValueError('Shard must retain original manifest unchanged')
    for name, sha in manifest['input_pins'].items():
        if file_hash(root/name) != sha:
            raise ValueError('Original input pin drift')
    ownership = load(root/'ownership.json')
    shards = receipt['shards']
    if len(shards) != 8 or {s['worker'] for s in shards} != set(range(8)):
        raise ValueError('Exactly eight disjoint workers required')
    languages = [language for shard in shards for language in shard['languages']]
    if len(languages) != len(set(languages)):
        raise ValueError('Overlapping language ownership')
    selected = next((s for s in shards if root.name == f"shard-{s['worker']}"), None)
    if selected is None or any(ownership.get(k) != v for k,v in selected.items()):
        raise ValueError('Ownership slice mismatch')
    if file_hash(root/'ownership.json') != receipt['files'][root.name+'/ownership.json']:
        raise ValueError('Ownership pin drift')
    for shard in shards:
        if shard['endpoint'] != f"http://127.0.0.1:{8800+shard['worker']}/v1":
            raise ValueError('Endpoint ownership mismatch')
    with readonly(source/'jobs.sqlite') as db:
        expected = {(l,f):t for l,f,t in db.execute('SELECT language,family,target FROM groups')}
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
            raise ValueError('Original controller must remain drained')
    if set(languages) != {l for l,f in expected} or sum(expected.values()) != receipt['target']:
        raise ValueError('Partition does not cover original quotas')
    subset = {key:value for key,value in expected.items() if key[0] in selected['languages']}
    with readonly(root/'jobs.sqlite') as db:
        actual = {(l,f):t for l,f,t in db.execute('SELECT language,family,target FROM groups')}
        if actual != subset:
            raise ValueError('Shard quota mismatch')
        if db.execute('SELECT count(*) FROM groups WHERE accepted<0 OR active<0 OR accepted+active>target').fetchone()[0]:
            raise ValueError('Invalid shard counters')
        if db.execute("""SELECT count(*) FROM groups g WHERE
                accepted != (SELECT count(*) FROM jobs j WHERE j.language=g.language
                    AND j.family=g.family AND j.status='accepted') OR
                active != (SELECT count(*) FROM jobs j WHERE j.language=g.language
                    AND j.family=g.family AND j.status='running')""").fetchone()[0]:
            raise ValueError('Shard counters disagree with jobs')
        if db.execute('''SELECT count(*) FROM jobs j LEFT JOIN groups g
                ON j.language=g.language AND j.family=g.family
                WHERE g.language IS NULL''').fetchone()[0]:
            raise ValueError('Job outside shard ownership')
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone() != (receipt['source_manifest_sha256'],):
            raise ValueError('Shard ledger source seal mismatch')
        registry = parent/'fingerprints.sqlite'
        db.execute('ATTACH DATABASE ? AS registry', (registry.resolve().as_uri()+'?mode=ro',))
        if db.execute("SELECT count(*) FROM jobs j LEFT JOIN registry.fingerprints f ON j.fingerprint=f.fingerprint WHERE j.status='accepted' AND (f.owner IS NULL OR f.owner!=j.id)").fetchone()[0]:
            raise ValueError('Accepted global ownership missing')
    return manifest, selected


class Owner(batching.Owner):
    async def submit(self, operation):
        info = batching.context(operation)
        if info is not None and info[2] == 'claim':
            # Do not acquire the global registry while holding a local batch transaction.
            return await disk.Owner.submit(self, operation)
        return await super().submit(operation)


class GlobalClaims:
    def __init__(self, path):
        self.path = Path(path)
        self.registry = None

    def claim(self, seen, fingerprint):
        if seen.ledger.db.in_transaction:
            raise ValueError('Global claim inside local transaction forbidden')
        if self.registry is None:
            self.registry = FingerprintRegistry(self.path)
        if not self.registry.claim(fingerprint, seen.owner):
            return False
        return local_claim(seen, fingerprint)

    def close(self):
        if self.registry is not None:
            self.registry.close()


def controller(owner, root, claims):
    c = previous.controller(owner)
    c.verify = lambda path: verify_partition(path)[0]
    c.pilot.__dict__['_claim'] = claims.claim
    endpoint = load(root/'ownership.json')['endpoint']
    def validate_endpoints(endpoints):
        if list(endpoints) != [endpoint]:
            raise ValueError('Only the assigned shard endpoint is permitted')
    c.v6.validate_endpoints = validate_endpoints
    original = c.write_json
    def write(path, value):
        if path.name == 'runtime.json':
            value = dict(value, shard_runtime_module=MODULE,
                         ownership_sha256=file_hash(root/'ownership.json'),
                         global_registry=str(root.parent/'fingerprints.sqlite'))
        return original(path, value)
    c.write_json = write
    return c


async def run(root):
    root = Path(root).resolve()
    _, selected = verify_partition(root)
    owner, claims = Owner(), GlobalClaims(root.parent/'fingerprints.sqlite')
    async def report():
        while True:
            value = owner.snapshot()
            await owner.call(lambda: write_json(root/'operation-timings.json', value))
            await asyncio.sleep(5)
    reporting = asyncio.create_task(report())
    try:
        await controller(owner, root, claims).execute(root,
            endpoints=[selected['endpoint']], concurrency=768, timeout=600,
            max_kv_cache_utilization=.90)
    finally:
        reporting.cancel()
        await asyncio.gather(reporting, return_exceptions=True)
        if owner.dispatch is not None:
            await asyncio.shield(owner.dispatch)
        await owner.call(claims.close)
        owner.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.root))
