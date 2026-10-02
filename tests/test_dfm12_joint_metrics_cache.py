import asyncio

import pytest

from dfm12 import joint_metrics_cache as cache_module


class Response:
    def __init__(self, body):
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    async def text(self):
        return self.body


class Session:
    def __init__(self, bodies):
        self.bodies = iter(bodies)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return Response(next(self.bodies))


GOOD = 'vllm:kv_cache_usage_perc 0.5\nvllm:num_requests_waiting 0\n'
BUSY = 'vllm:kv_cache_usage_perc 0.95\nvllm:num_requests_waiting 129\n'


def test_cached_metrics_expire_and_are_endpoint_scoped(monkeypatch):
    now = [0.]
    monkeypatch.setattr(cache_module.time, 'monotonic', lambda: now[0])
    async def run():
        cache = cache_module.MetricsCache()
        session = Session([GOOD, BUSY, BUSY])
        assert (await cache.sample(session, 'http://a/v1'))['waiting'] == 0
        now[0] = .24
        assert (await cache.sample(session, 'http://a/v1'))['waiting'] == 0
        assert session.calls == 1
        assert (await cache.sample(session, 'http://b/v1'))['waiting'] == 129
        now[0] = .25
        assert (await cache.sample(session, 'http://a/v1'))['waiting'] == 129
        assert session.calls == 3
    asyncio.run(run())


def test_recovery_forces_probe_and_failure_discards_old_sample():
    async def run():
        cache = cache_module.MetricsCache()
        session = Session([GOOD, 'invalid', BUSY])
        await cache.sample(session, 'http://a/v1')
        with pytest.raises(ValueError):
            await cache.sample(session, 'http://a/v1', force=True)
        assert 'http://a/v1' not in cache.samples
        assert (await cache.sample(session, 'http://a/v1'))['waiting'] == 129
    asyncio.run(run())
