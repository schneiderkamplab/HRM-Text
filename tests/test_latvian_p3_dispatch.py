import threading
import time

import pytest

from dfm12.io import write_json
from dfm12 import latvian_p3_dispatch as d


def test_aggregate_budget_not_multiplied():
    work = d.allocation([f'http://127.0.0.1:{p}/v1' for p in range(8800, 8808)], 1, 8, 140)
    assert len(work) == 8 and sum(n for _, n in work) == 140
    assert sorted(n for _, n in work) == [17] * 4 + [18] * 4
    with pytest.raises(ValueError): d.allocation(['http://localhost:8800/v1', 'http://127.0.0.1:8800/v1/'], 1, 8, 10)
    with pytest.raises(ValueError): d.allocation([str(i) for i in range(8)], 2, 8, 10)


def setup(tmp_path, monkeypatch):
    root = tmp_path / 'root'; root.mkdir()
    ready = tmp_path / 'ready.json'; transition = tmp_path / 'transition.json'
    write_json(ready, dict(model=d.pairing.MODEL, all_files_verified=True, snapshot=str(tmp_path)))
    write_json(transition, dict(counts={'done': 75, 'failed': 1}, production_approved=False))
    monkeypatch.setattr(d.pairing, 'verified_inputs', lambda root: None)
    monkeypatch.setattr(d.health, 'check', lambda *a, **k: {'model': 'mock'})
    return dict(root=root, endpoints=[f'http://localhost:{p}/v1' for p in range(8800, 8808)],
        stage=d.pairing.CALIBRATION, tokenizer=tmp_path, ready=ready,
        transition_terminal=transition, budget_lock=tmp_path / 'shared.lock', limit=140)


def test_eight_workers_concurrent_with_bounded_total(tmp_path, monkeypatch):
    kwargs = setup(tmp_path, monkeypatch); barrier = threading.Barrier(8); calls = []
    def worker(root, endpoint, stage, tokenizer, quota):
        calls.append((endpoint, quota)); barrier.wait(timeout=5); time.sleep(.01)
    monkeypatch.setattr(d.pairing.consumer, 'run', worker)
    receipt = d.run(**kwargs)
    assert len(set(e for e, _ in calls)) == 8
    assert sum(n for _, n in calls) == 140
    assert receipt['active_workers'] == 8


def test_any_wrong_endpoint_blocks_all_dispatch(tmp_path, monkeypatch):
    kwargs = setup(tmp_path, monkeypatch)
    def health(endpoint, *a, **k):
        if '8807' in endpoint: raise ValueError('Wrong model/context')
        return {}
    monkeypatch.setattr(d.health, 'check', health)
    monkeypatch.setattr(d.pairing.consumer, 'run', lambda *a: pytest.fail('No dispatch allowed'))
    with pytest.raises(ValueError, match='Wrong model'): d.run(**kwargs)


def test_nonterminal_transition_blocks_before_health(tmp_path, monkeypatch):
    kwargs = setup(tmp_path, monkeypatch)
    write_json(kwargs['transition_terminal'], dict(counts={'pending': 76}))
    monkeypatch.setattr(d.health, 'check', lambda *a, **k: pytest.fail('No HTTP allowed'))
    with pytest.raises(ValueError, match='terminal'): d.run(**kwargs)


def test_shared_budget_lock_prevents_duplicate_launch(tmp_path, monkeypatch):
    from dfm12.io import lock
    kwargs = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(d.health, 'check', lambda *a, **k: pytest.fail('No duplicate dispatch'))
    with lock(kwargs['budget_lock']):
        with pytest.raises(BlockingIOError): d.run(**kwargs)
