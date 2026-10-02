import pytest
from scripts import dfm13_repochat_grounded_repair_retry as m


def fixture(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(m.parent, 'ROOT', tmp_path)
    records = [{'task': {'id': str(i), 'repository': repo}} for i, repo in enumerate(['agnaistic/agnai', 'vedalai/neuro-game-sdk'])]
    m.b.save(tmp_path / 'ready.json', {'records': records})
    for record in records:
        path = tmp_path / 'first-four/trajectories' / record['task']['id']
        m.b.save(path / 'outcome.json', {'error': reason})
        m.b.save(path / 'response.json', {'choices': [{'finish_reason': 'length'}]})
        m.b.save(path / 'request.json', {})


def test_only_length_failures(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch, 'non_stop:length')
    records, pins = m.eligible()
    assert len(records) == 2 and len(pins) == 7


@pytest.mark.parametrize('reason', ['semantic_rejection', 'empty_answer', None])
def test_other_failures_held(tmp_path, monkeypatch, reason):
    fixture(tmp_path, monkeypatch, reason)
    with pytest.raises(ValueError):
        m.eligible()
