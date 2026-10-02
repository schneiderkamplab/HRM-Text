"""Joint-client admission policy; sealed standalone campaign code stays unchanged."""
import asyncio
import time

from .multilingual_quarter import AdmissionGate as RetainedGate
from .multilingual_quarter import admission_metrics, stop_wait, v6
from .joint_metrics_cache import MetricsCache


def validate_max_kv(value):
    if type(value) not in (int, float) or not 0 < value <= 1:
        raise ValueError('KV admission threshold must be positive and <=1.0')
    return value


class AdmissionGate(RetainedGate):
    """Allow a small queue while retaining KV checks and failure recovery."""

    def __init__(self, *args, max_waiting=128, poll=.01, max_kv=.9, **kwargs):
        validate_max_kv(max_kv)
        super().__init__(*args, poll=poll, max_kv=min(max_kv, .9), **kwargs)
        self.max_kv = max_kv
        self.max_waiting = max_waiting
        self.metrics = MetricsCache()

    def trip(self, endpoint):
        self.metrics.invalidate(endpoint)
        super().trip(endpoint)

    async def admit(self, endpoint, can_continue=lambda: True):
        import aiohttp
        async with self.locks[endpoint]:
            info = self.status[endpoint]
            while not self.stop.is_set() and can_continue():
                if endpoint in self.paused:
                    info['reason'] = self.paused[endpoint]
                    if not await stop_wait(self.stop, self.poll):
                        return False
                    continue
                if self.failures[endpoint] >= 3 and endpoint not in self.recover_at:
                    self.trip(endpoint)
                deadline = max(self.next_at.get(endpoint,0), self.recover_at.get(endpoint,0))
                if deadline > time.monotonic():
                    info['reason'] = 'circuit_cooldown' if endpoint in self.recover_at else 'spacing'
                    if not await stop_wait(self.stop, min(deadline-time.monotonic(), self.poll)):
                        return False
                    continue
                try:
                    timeout = aiohttp.ClientTimeout(total=4)
                    recovery_deadline = self.recover_at.get(endpoint)
                    recovery_generation = self.circuit_generation[endpoint]
                    if recovery_deadline is not None:
                        async with self.session.get(endpoint+'/models', timeout=timeout) as response:
                            response.raise_for_status()
                            document = await response.json()
                            v6.endpoint_limit(document)
                    sample = await self.metrics.sample(self.session, endpoint,
                                                       force=recovery_deadline is not None)
                    info.update(sample, checked=time.time())
                    if endpoint in self.paused:
                        continue
                    if (self.circuit_generation[endpoint] != recovery_generation
                            or self.recover_at.get(endpoint) != recovery_deadline):
                        continue  # New trip invalidates even a completed health probe.
                    if recovery_deadline is None and (endpoint in self.recover_at or self.failures[endpoint] >= 3):
                        self.trip(endpoint)
                        continue  # A stage tripped while this probe was in flight.
                    if sample['kv'] > self.max_kv or sample['waiting'] > self.max_waiting:
                        info['reason'] = 'shared_server_busy'
                        self.next_at[endpoint] = time.monotonic()+self.poll
                        continue
                    # No awaits between recovery and permit: only this endpoint's
                    # serialized probe resets the circuit for new candidate work.
                    if endpoint in self.recover_at:
                        self.health[endpoint] = document
                        self.failures[endpoint] = 0
                        del self.recover_at[endpoint]
                        info['recoveries'] += 1
                    if self.stop.is_set() or not can_continue():
                        return False
                    self.next_at[endpoint] = time.monotonic()+self.spacing
                    info.update(reason='admitted', admissions=info['admissions']+1)
                    return True
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as exc:
                    info.update(reason='probe_failed', last_error=repr(exc), probe_failures=info['probe_failures']+1)
                    self.next_at[endpoint] = time.monotonic()+self.poll
                    if endpoint in self.recover_at:
                        self.recover_at[endpoint] = time.monotonic()+self.cooldown
            return False
