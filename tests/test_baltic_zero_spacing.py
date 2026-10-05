import asyncio
from collections import Counter
from dfm12.baltic_async_io import Owner
from dfm12.baltic_zero_spacing import controller


def test_zero_spacing_retains_safety():
    owner = Owner()
    try:
        c = controller(owner)
        gate = c.AdmissionGate(None, ['endpoint'], Counter(), {}, asyncio.Event(), .90)
        assert gate.spacing == 0
        assert gate.poll == .01
        assert gate.cooldown == 5
        assert gate.max_kv == .90
        assert .01 not in c.execute.__code__.co_consts
        assert 384 in c.execute.__code__.co_consts
    finally:owner.close()
