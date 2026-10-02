"""Generic gated Arena audit adapter; no changes to the active bulk engine."""
import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time

P = Path(__file__).with_name('dfm13_arena_repairs.py')
spec = importlib.util.spec_from_file_location('_next_repairs_helpers', P)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
strong = helpers.strong
base = strong.base
bulk = strong.bulk


def eligible(inventory, gate):
    known = {s['name']: s for s in inventory['sources']}
    selected = []
    seen = set()
    for entry in gate['sources']:
        name = entry['name']
        if name in seen or name not in known:
            raise ValueError('Duplicate/unknown gate source')
        seen.add(name)
        if entry.get('status') != 'ready':
            continue
        if entry.get('license_cleared') is not True or entry.get('heldout_overlap_cleared') is not True:
            raise ValueError('Ready source lacks license/overlap clearance: '+name)
        if entry.get('input_sha256') != known[name]['sha256']:
            raise ValueError('Gate input hash mismatch')
        if not entry.get('evidence'):
            raise ValueError('Clearance evidence required, including PRISM license decision')
        selected.append(entry)
    if not selected:
        raise ValueError('No ready eligible sources')
    return selected


def prepare(root, inventory_path, gate_path, after):
    root.mkdir(parents=True, exist_ok=True)
    with base.lock(root/'controller.lock'):
        if (root/'manifest.json').exists() or (root/'ledger.sqlite').exists():
            raise ValueError('Fresh root required')
        inventory = base.load(inventory_path)
        gate = base.load(gate_path)
        if gate['inventory_sha256'] != base.file_hash(inventory_path):
            raise ValueError('Gate inventory mismatch')
        selected = eligible(inventory, gate)
        previous = base.load(after/'plan.json')['manifest']
        pins = dict(previous['pins'])
        for path in (Path(__file__).resolve(), P.resolve(), inventory_path, gate_path,
                     base.ROOT/'tests/test_dfm13_arena_next_audit.py'):
            pins[str(path)] = base.file_hash(path)
        sources = []
        for entry in selected:
            for evidence in entry['evidence']:
                if base.file_hash(evidence['path']) != evidence['sha256']:
                    raise ValueError('Clearance evidence drift')
                pins[evidence['path']] = evidence['sha256']
            output = entry['eligible_source']
            if base.file_hash(output['path']) != output['sha256']:
                raise ValueError('Eligible source drift')
            sources.append(dict(output, name=entry['name'], input_sha256=entry['input_sha256']))
        db = bulk.database(root)
        total = 0
        identities = set()
        for index, source in enumerate(sources):
            offset = count = 0
            digest = hashlib.sha256()
            with open(source['path'], 'rb') as stream:
                for line, raw in enumerate(stream, 1):
                    digest.update(raw)
                    row = base.strict_json(raw.decode())
                    base.visible(row)
                    identity = (index, row['id'])
                    if identity in identities:
                        raise ValueError('Duplicate source ID')
                    identities.add(identity)
                    count += 1
                    total += 1
                    db.execute('INSERT INTO jobs(seq,source,line,offset,length,source_id) VALUES(?,?,?,?,?,?)',
                               (total,index,line,offset,len(raw),row['id']))
                    offset += len(raw)
            if count != source['rows'] or digest.hexdigest() != source['sha256']:
                raise ValueError('Eligible count/hash mismatch')
        if total == 0:
            raise ValueError('Empty eligible inventory')
        db.commit()
        db.close()
        manifest = dict(version='arena-generic-next-v1', total=total, sources=sources,
            tokenizer_dir=previous['tokenizer_dir'], context_limit=previous['context_limit'],
            endpoints=previous['endpoints'], model=previous['model'], pins=pins,
            concurrency_per_server=128, cpu_workers=8, thinking=True, max_tokens=8192,
            timeout_seconds=600, after_repairs=str(after), no_admission=True, no_upload=True,
            input_inventory_sha256=base.file_hash(inventory_path), eligibility_sha256=base.file_hash(gate_path))
        base.write_json(root/'manifest.json',manifest)
        base.write_json(root/'seal.json',dict(manifest_sha256=base.file_hash(root/'manifest.json')))
        return manifest


def predecessor_ready(after):
    if not (after/'complete.json').exists():
        return False
    try:
        with base.lock(after/'controller.lock'):
            receipt = base.load(after/'complete.json')
            total = base.load(after/'plan.json')['manifest']['total']
            with helpers.readonly(after/'ledger.sqlite') as db:
                counts = {t: db.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                          for t in ('accepted','rejected','needs_review')}
                unique = db.execute('SELECT count(*) FROM (SELECT seq FROM accepted UNION SELECT seq FROM rejected UNION SELECT seq FROM needs_review)').fetchone()[0]
            return counts == receipt['counts'] and sum(counts.values()) == unique == total
    except BlockingIOError:
        return False


def verify(root):
    manifest = base.load(root/'manifest.json')
    if base.file_hash(root/'manifest.json') != base.load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Seal drift')
    for path, digest in manifest['pins'].items():
        if base.file_hash(path) != digest:
            raise ValueError('Dependency drift: '+path)
    for source in manifest['sources']:
        if base.file_hash(source['path']) != source['sha256']:
            raise ValueError('Eligible source drift')
    return manifest


def admission_credits(values, active, recent=0):
    required = ('vllm:num_requests_running', 'vllm:num_requests_waiting', 'vllm:kv_cache_usage_perc')
    if any(k not in values for k in required):
        return 0
    running, waiting, kv = (values[k] for k in required)
    if not (0 <= running <= 256 and waiting == 0 and 0 <= kv < .80):
        return 0
    # Recent dispatch may not yet be reflected in the server's metric sample.
    return max(0, min(128-active, int(256-running-recent)))


class EndpointGate:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.active = self.credits = 0
        self.sampled = 0
        self.dispatched = {}
        self.serial = 0

    def recent(self, sampled):
        return sum(started >= sampled-2 for started in self.dispatched.values())

    def release(self, token):
        del self.dispatched[token]
        self.active -= 1

    async def acquire(self, session, endpoint, timeout_factory):
        while True:
            async with self.lock:
                if time.monotonic()-self.sampled >= 2:
                    self.credits = 0
                    try:
                        async with session.get(endpoint.removesuffix('/v1')+'/metrics',
                                timeout=timeout_factory(total=3)) as response:
                            response.raise_for_status()
                            values = {}
                            for line in (await response.text()).splitlines():
                                if line and not line.startswith('#'):
                                    name = line.split('{')[0].split()[0]
                                    if name.startswith('vllm:'):
                                        try:
                                            values[name] = values.get(name, 0)+float(line.rsplit(' ',1)[1])
                                        except ValueError:
                                            pass
                            self.credits = admission_credits(values,self.active,self.recent(time.monotonic()))
                    except Exception:
                        self.credits = 0
                    self.sampled = time.monotonic()
                if self.credits > 0 and self.active < 128 and time.monotonic()-self.sampled < 2:
                    self.credits -= 1
                    self.active += 1
                    self.serial += 1
                    self.dispatched[self.serial] = time.monotonic()
                    return self.serial
            await asyncio.sleep(.25)


async def run(root, manifest):
    import aiohttp
    import jsonschema
    original_query = base.raw_query
    original_timeout = aiohttp.ClientTimeout
    original_connector = aiohttp.TCPConnector
    gates = {endpoint: EndpointGate() for endpoint in manifest['endpoints']}
    def request(row):
        return helpers.transport(strong.request(row))
    def validate(value):
        schema = base.obj(dict(reason={'type':'string','maxLength':2400},
                               verdict={'type':'string','enum':list(base.DISPOSITIONS)}))
        jsonschema.validate(value,schema)
        if not value['reason'].strip():
            raise ValueError('Empty reason')
        return value
    async def guarded_query(session,endpoint,payload,writer,metadata):
        gate = gates[endpoint]
        token = await gate.acquire(session,endpoint,original_timeout)
        try:
            return await original_query(session,endpoint,payload,writer,metadata)
        finally:
            gate.release(token)
    async def query(session,endpoint,payload,writer,metadata):
        return await strong.recovery.retry_query(guarded_query,session,endpoint,payload,writer,metadata,root)
    def timeout(*args,**kwargs):
        if kwargs.get('total') == 240:
            kwargs['total'] = 600
        return original_timeout(*args,**kwargs)
    def connector(*args,**kwargs):
        return original_connector(*args,**dict(kwargs,force_close=True))
    bulk.request = request
    bulk.simple.validate = validate
    base.raw_query = query
    aiohttp.ClientTimeout = timeout
    aiohttp.TCPConnector = connector
    try:
        await bulk.run(root,manifest)
    finally:
        base.raw_query = original_query
        aiohttp.ClientTimeout = original_timeout
        aiohttp.TCPConnector = original_connector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','watch'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--inventory',type=Path)
    parser.add_argument('--eligibility',type=Path)
    parser.add_argument('--after-repairs',type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == 'prepare':
        prepare(root,args.inventory.resolve(),args.eligibility.resolve(),args.after_repairs.resolve())
        return
    with base.lock(root/'controller.lock'):
        manifest = verify(root)
        while not manifest.get('gated_overlap', False) and not predecessor_ready(Path(manifest['after_repairs'])):
            base.write_json(root/'queue-status.json',dict(status='waiting_for_repairs_complete',time=time.time()))
            time.sleep(30)
        verify(root)
        asyncio.run(run(root,manifest))


if __name__ == '__main__':
    main()
