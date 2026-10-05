import asyncio
import inspect

import pytest

from dfm12 import baltic_compact_successor as successor
from dfm12 import multilingual_quarter as shared


def test_private_runner_only_and_compact_review():
    before = shared.execute
    c = successor.controller()
    assert shared.execute is before
    assert 64 in shared.execute.__code__.co_consts
    assert 128 in c.execute.__code__.co_consts
    review, _ = c.v6.adapters()
    assert review is successor.compact
    assert c.pilot.v6 is c.v6


def test_cap_remains_bounded(tmp_path):
    c = successor.controller()
    endpoints = [f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
    with pytest.raises(ValueError, match='128'):
        asyncio.run(c.execute(tmp_path, endpoints=endpoints, concurrency=129))


def test_all_family_targets_unchanged():
    import yaml
    q = successor.base.quotas(yaml.safe_load(successor.base.CONFIG.read_text()))
    assert len(q) == 12
    assert {lang:sum(r['accepted_target'] for r in q if r['language']==lang)
            for lang in ('lt','lv')} == {'lt':70000,'lv':70000}
