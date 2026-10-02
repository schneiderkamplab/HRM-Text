import argparse
import asyncio
from types import SimpleNamespace

import pytest
from scripts import dfm13_repochat_replica_recovery as replica


def test_explicit_eight_local_endpoints():
    urls = ','.join(f'http://127.0.0.1:{8800+i}/v1' for i in range(8))
    assert len(replica.endpoints(urls)) == 8
    with pytest.raises(argparse.ArgumentTypeError):
        replica.endpoints('http://127.0.0.1:8810/v1')


def test_balanced_pending_and_cleanup(monkeypatch):
    seen = []
    class Fake:
        def __init__(self, session, args, stop):
            self.args = args
            assert args.concurrency == 256
        async def call(self, payload, path):
            seen.append(self.args.endpoint)
            await asyncio.sleep(0)
            return payload
    monkeypatch.setattr(replica, 'OriginalClient', Fake)
    async def check():
        client = replica.ReplicaClient(None, SimpleNamespace(endpoints=list(range(8)), per_endpoint=256), None)
        await asyncio.gather(*(client.call({}, None) for _ in range(16)))
        assert all(seen.count(i) == 2 for i in range(8))
        assert client.pending == [0] * 8
    asyncio.run(check())
