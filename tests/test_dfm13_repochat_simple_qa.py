import pytest
from scripts import dfm13_repochat_simple_qa as q


def test_scope_never_pads():
    assert len(q.EXCLUSIONS) == 21
    assert all(0 <= i < 68 for i in q.EXCLUSIONS)
    assert 68 - len(q.EXCLUSIONS) == 47


def test_missing_controls_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(q, 'CONTROLS', tmp_path)
    with pytest.raises(FileNotFoundError):
        q.controls_ready()


def test_bad_negative_blocks_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(q, 'CONTROLS', tmp_path)
    q.b.save(tmp_path / 'control-manifest.json', {'source_pins': {}, 'expected': {'negative': False}})
    q.b.save(tmp_path / 'results' / 'positive-controls.json', {'passed': True})
    q.b.save(tmp_path / 'results' / 'reviews' / 'negative' / 'outcome.json', {'status': 'reviewed', 'quality_pass': True})
    with pytest.raises(ValueError, match='scoped reviewer control failed'):
        q.controls_ready()
