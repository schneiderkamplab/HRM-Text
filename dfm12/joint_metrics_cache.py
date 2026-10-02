"""Short-lived validated admission metrics, used under each endpoint's lock."""
import time

import aiohttp

from .multilingual_quarter import admission_metrics


class MetricsCache:
    def __init__(self, ttl=.25):
        self.ttl = ttl
        self.samples = {}

    def invalidate(self, endpoint):
        self.samples.pop(endpoint, None)

    async def sample(self, session, endpoint, *, force=False):
        cached = self.samples.get(endpoint)
        if not force and cached and time.monotonic() - cached[0] < self.ttl:
            return dict(cached[1])
        self.invalidate(endpoint)
        started = time.monotonic()
        async with session.get(endpoint.removesuffix('/v1') + '/metrics',
                               timeout=aiohttp.ClientTimeout(total=4)) as response:
            response.raise_for_status()
            sample = admission_metrics(await response.text())
        self.samples[endpoint] = (started, sample)
        return dict(sample)
