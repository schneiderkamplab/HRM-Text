import pytest

from dfm12.io import write_json
from dfm12.multilingual_second_run import require_complete, gpu_pids, check_frozen


def test_complete_requires_all_accepted_and_full_gate(tmp_path):
    write_json(tmp_path / 'completion.json', dict(interrupted=False,
        counts=[dict(status='accepted', count=700)]))
    write_json(tmp_path / 'review-calibration.json', dict(passed=True))
    require_complete(tmp_path, 700)
    write_json(tmp_path / 'review-calibration.json', dict(passed=False))
    with pytest.raises(RuntimeError):
        require_complete(tmp_path, 700)


@pytest.mark.parametrize('counts,interrupted', [
    ([dict(status='accepted', count=699)], False),
    ([dict(status='accepted', count=699), dict(status='exhausted', count=1)], False),
    ([dict(status='accepted', count=700)], True)])
def test_partial_or_exhausted_never_advances(tmp_path, counts, interrupted):
    write_json(tmp_path / 'completion.json', dict(counts=counts, interrupted=interrupted))
    with pytest.raises(RuntimeError):
        require_complete(tmp_path, 700)


def test_gpu_query_deduplicates_without_signaling(monkeypatch):
    monkeypatch.setattr('subprocess.check_output', lambda *a, **kw: '12\n12\n34\n')
    assert gpu_pids() == [12, 34]


def test_old_freeze_refuses_new_contract():
    with pytest.raises(ValueError, match='implementation drift'):
        check_frozen()
