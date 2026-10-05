import pytest
from dfm12.io import write_json, load
from scripts import watch_finished_wave_assembly as watcher


def test_no_receipt_no_promotion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(watcher, 'identity', lambda pid: None)
    root = tmp_path/'assembly'
    with pytest.raises(RuntimeError):
        watcher.run(root, 123)
    assert not (tmp_path/'data/dfm13/authoritative-additions.json').exists()


@pytest.mark.parametrize('reason,allowed', [('quality_hold_source_fidelity', True), ('verification_failed', False)])
def test_only_explicit_holds_allow_promotion(tmp_path, monkeypatch, reason, allowed):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(watcher, 'identity', lambda pid: None)
    root = tmp_path/'assembly'
    missing = [dict(name='held', reason=reason)]
    totals = dict(ready_sources=1)
    write_json(root/'assembly.json', dict(totals=totals, unready_additions=missing, ready_additions=[]))
    write_json(tmp_path/'assembly-control/verified.json', dict(totals=totals, missing=missing))
    if allowed:
        watcher.run(root, 123)
        assert load('data/dfm13/authoritative-additions.json')['status'] == 'verified'
    else:
        with pytest.raises(ValueError):
            watcher.run(root, 123)
        assert not (tmp_path/'data/dfm13/authoritative-additions.json').exists()
