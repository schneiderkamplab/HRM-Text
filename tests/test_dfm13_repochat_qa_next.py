import asyncio
import pytest
from scripts import dfm13_repochat_qa_next as n


def test_scope_is_bounded_and_unused():
    tasks, available = n.candidates()
    assert len(tasks) == 100
    assert available == 1669
    assert len({t['id'] for t in tasks}) == 100
    assert all(not n.b.task_exclusion(t) for t in tasks)


def test_rest_requires_manual_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'ROOT', tmp_path)
    n.b.save(tmp_path/'selection.json', {'tasks': []})
    n.b.save(tmp_path/'ready.json', {'pins': {}, 'selection_sha256': n.b.file_sha(tmp_path/'selection.json')})
    with pytest.raises(FileNotFoundError):
        asyncio.run(n.run('rest'))


def test_pin_drift_fails_before_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(n, 'ROOT', tmp_path)
    n.b.save(tmp_path/'ready.json', {'pins': {__file__: 'wrong'}})
    with pytest.raises(ValueError, match='pin drift'):
        asyncio.run(n.run('first'))
