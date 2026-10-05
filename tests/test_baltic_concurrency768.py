import asyncio
from collections import Counter
from dfm12.baltic_async_io import Owner
from dfm12.baltic_concurrency768 import controller
from dfm12.baltic_zero_spacing import controller as previous


def test_768_private_guard_safety_and_previous_unchanged():
    owner = Owner()
    try:
        c = controller(owner)
        assert 768 in c.execute.__code__.co_consts
        assert 384 not in c.execute.__code__.co_consts
        assert 384 in previous(owner).execute.__code__.co_consts
        gate = c.AdmissionGate(None, ['endpoint'], Counter(), {}, asyncio.Event(), .90)
        assert (gate.spacing, gate.poll, gate.cooldown, gate.max_kv) == (0,.01,5,.90)
    finally:owner.close()
