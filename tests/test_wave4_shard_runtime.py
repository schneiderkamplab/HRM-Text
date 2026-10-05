import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from types import SimpleNamespace

import pytest
from dfm12 import wave4_shard_runtime as runtime
from dfm12.io import file_hash, write_json
from dfm12.multilingual_quarter import Ledger, Seen
from dfm12.wave4_shard_prepare import FingerprintRegistry


def test_cross_shard_claim_has_one_winner(tmp_path):
    registry = tmp_path/'fingerprints.sqlite'
    FingerprintRegistry(registry).close()
    def work(i):
        ledger = Ledger(tmp_path/f'{i}.sqlite')
        claims = runtime.GlobalClaims(registry)
        try:
            result = claims.claim(Seen(ledger, str(i)), 'same')
            return result, ledger.db.execute('SELECT count(*) FROM fingerprints').fetchone()[0]
        finally:
            claims.close(); ledger.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, range(8)))
    assert sum(r[0] for r in results) == 1
    assert sum(r[1] for r in results) == 1


def test_global_commit_survives_local_failure(tmp_path):
    claims = runtime.GlobalClaims(tmp_path/'global.sqlite')
    ledger = Ledger(tmp_path/'local.sqlite')
    class Broken(Seen):
        def add(self, fingerprint):
            raise RuntimeError('local failure')
    try:
        with pytest.raises(RuntimeError):
            claims.claim(Broken(ledger, 'a'), 'fp')
        assert not claims.claim(Seen(ledger, 'b'), 'fp')
        assert claims.claim(Seen(ledger, 'a'), 'fp')
        assert not claims.claim(Seen(ledger, 'a'), 'fp')
        ledger.db.execute('BEGIN IMMEDIATE')
        with pytest.raises(ValueError, match='transaction'):
            claims.claim(Seen(ledger, 'a'), 'other')
        ledger.db.rollback()
    finally:
        claims.close(); ledger.close()


def test_actual_claim_lambda_not_batched_and_owner_thread(tmp_path):
    async def run():
        owner = runtime.Owner()
        claims = runtime.GlobalClaims(tmp_path/'global.sqlite')
        try:
            ledger = await owner.call(lambda: Ledger(tmp_path/'local.sqlite'))
            seen = Seen(ledger, 'candidate')
            _claim = claims.claim
            values = await asyncio.gather(*(owner.call(lambda: _claim(seen, 'fp')) for _ in range(20)))
            assert sum(values) == 1
            assert owner.batch_counts['committed_operations'] == 0
            await owner.call(ledger.close)
            await owner.call(claims.close)
        finally:
            owner.close()
    asyncio.run(run())


def fixture_partition(tmp_path, monkeypatch):
    from dfm12 import wave4_compact_handoff, wave4_shard_prepare
    monkeypatch.setattr(wave4_compact_handoff, 'verify_independent_launch', lambda root: None)
    source = tmp_path/'source'; source.mkdir()
    partition = tmp_path/'partition'; partition.mkdir()
    root = partition/'shard-0'; root.mkdir()
    pins = {str(__import__('pathlib').Path(m.__file__).resolve()):file_hash(m.__file__)
            for m in (runtime, runtime.previous, runtime.batching, runtime.disk, wave4_shard_prepare)}
    for directory in (source, root):
        write_json(directory/'config.json', {})
        write_json(directory/'manifest.json', dict(implementation_pins=pins,
            input_pins={'config.json':file_hash(directory/'config.json')}))
    sha = file_hash(source/'manifest.json')
    for directory, languages in ((source, range(8)), (root, [0])):
        ledger = Ledger(directory/'jobs.sqlite')
        ledger.initialize([dict(language=str(i),family='test',accepted_target=10) for i in languages])
        ledger.db.execute('INSERT INTO metadata VALUES (?,?)', ('manifest_sha256',sha))
        ledger.close()
    shards = [dict(worker=i,languages=[str(i)],remaining=10,endpoint=f'http://127.0.0.1:{8800+i}/v1') for i in range(8)]
    write_json(root/'ownership.json', shards[0])
    write_json(partition/'prepared.json', dict(source_root=str(source),source_manifest_sha256=sha,
        shards=shards,target=80,files={'shard-0/ownership.json':file_hash(root/'ownership.json')}))
    write_json(partition/'shard-runtime.json', dict(runtime_module=runtime.MODULE,
        launch_authorized=True,prepared_sha256=file_hash(partition/'prepared.json'),implementation_pins=pins))
    FingerprintRegistry(partition/'fingerprints.sqlite').close()
    return root


def test_partition_quota_and_pins(tmp_path, monkeypatch):
    root = fixture_partition(tmp_path, monkeypatch)
    assert runtime.verify_partition(root)[1]['worker'] == 0
    with sqlite3.connect(root/'jobs.sqlite') as db:
        db.execute('UPDATE groups SET target=9')
    with pytest.raises(ValueError, match='quota'):
        runtime.verify_partition(root)


def test_private_one_endpoint_controller(tmp_path):
    write_json(tmp_path/'ownership.json', {'endpoint':'http://127.0.0.1:8803/v1'})
    owner = runtime.Owner()
    try:
        c = runtime.controller(owner, tmp_path, runtime.GlobalClaims(tmp_path/'global.sqlite'))
        c.v6.validate_endpoints(['http://127.0.0.1:8803/v1'])
        with pytest.raises(ValueError):
            c.v6.validate_endpoints(['http://127.0.0.1:8800/v1'])
        assert c.pilot.process.__globals__['_claim'].__self__.__class__ is runtime.GlobalClaims
        assert c.execute.__globals__ is c.__dict__
        assert c.execute.__globals__['verify'] is c.verify
    finally:
        owner.close()


def test_full_execute_mock_http_real_ledger(tmp_path, monkeypatch):
    import json
    import sys
    import aiohttp
    from dfm12.io import load
    root = tmp_path/'shard-0'; root.mkdir()
    endpoint = 'http://127.0.0.1:8800/v1'
    write_json(root/'ownership.json', {'endpoint':endpoint})
    manifest = dict(campaign='test',provider='shard_test_provider',
                    seeds_root=str(root),tokenizer_dir=str(root))
    write_json(root/'manifest.json', manifest); write_json(root/'config.json', {})
    ledger = Ledger(root/'jobs.sqlite')
    ledger.initialize([dict(language='lt',family='tool-dialogue',accepted_target=1)])
    ledger.db.execute('INSERT INTO metadata VALUES (?,?)',
        ('manifest_sha256',file_hash(root/'manifest.json')))
    ledger.close()
    class Provider:
        def __init__(self,*args):self.db=sqlite3.connect(':memory:', isolation_level=None)
        def next_spec(self, language, family, slot):
            return dict(language_code=language,family=family,slot=slot,contract_version=4)
        def close(self):self.db.close()
    monkeypatch.setitem(sys.modules,'shard_test_provider',SimpleNamespace(SourceProvider=Provider,SeedUnavailable=ValueError))
    class Response:
        status=200
        def __init__(self):self.content=self
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def json(self):return {'data':[]}
        async def text(self):return 'vllm:kv_cache_usage_perc 0.01\nvllm:num_requests_waiting 0\n'
        async def iter_any(self):
            yield ('data: '+json.dumps({'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]})+'\n').encode()
    class Session:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def get(self,*args,**kwargs):return Response()
        def post(self,*args,**kwargs):return Response()
    class Budget:
        def __init__(self,*args):pass
        def measure(self,*args):return {'prompt_tokens':1}
    monkeypatch.setattr(aiohttp,'ClientSession',Session)
    async def run():
        owner = runtime.Owner(); claims = runtime.GlobalClaims(tmp_path/'fingerprints.sqlite')
        c = runtime.controller(owner,root,claims)
        c.verify=lambda path:manifest
        c.v6.verify_pins=lambda *args:None
        c.v6.Budget=Budget;c.v6.endpoint_limit=lambda *args:4096
        c.v6.adapters=lambda:(None,None)
        c.v6.generation_request=lambda *args,**kwargs:{}
        c.v6.compact_request=lambda p:(p,{'type':'object'})
        c.v6.generation_assemble=lambda *args:dict(messages=[{'role':'assistant','content':'ok'}],tools=[],provenance={})
        c.v6.audit_record=lambda value:value
        c.v6.review_request=lambda *args:{}
        c.v6.review_result=lambda *args:dict(effective_keep=True,status='valid',content_constraints_valid=True)
        try:
            await asyncio.wait_for(c.execute(root,endpoints=[endpoint],concurrency=1), 15)
            assert load(root/'progress.json')['phase']=='complete'
            with sqlite3.connect(root/'jobs.sqlite') as db:
                assert db.execute('SELECT accepted,active FROM groups').fetchone()==(1,0)
                fp,key=db.execute('SELECT fingerprint,id FROM jobs').fetchone()
            with sqlite3.connect(tmp_path/'fingerprints.sqlite') as db:
                assert db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(fp,)).fetchone()==(key,)
            assert len(list(root.glob('work/*/*/raw/*.response.json')))==2
            assert load(root/'runtime.json')['endpoints']==[endpoint]
        finally:
            if owner.dispatch is not None:await owner.dispatch
            await owner.call(claims.close)
            owner.close()
    asyncio.run(run())
