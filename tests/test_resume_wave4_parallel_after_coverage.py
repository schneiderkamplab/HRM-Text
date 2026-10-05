import pytest
from scripts import resume_wave4_parallel_after_coverage as m


def test_psutil_exited_process(monkeypatch):
    def gone(pid):raise m.psutil.NoSuchProcess(pid)
    monkeypatch.setattr(m,'identity',gone)
    assert not m.alive({'pid':42})


def test_changed_identity_never_signals(monkeypatch):
    monkeypatch.setattr(m,'alive',lambda item:False)
    monkeypatch.setattr(m,'pidfd_open',lambda pid:pytest.fail('must not signal'))
    with pytest.raises(ValueError):m.stop_child({'pid':1},{'pid':2})


@pytest.mark.parametrize('complete',[False,True])
def test_marker_requires_coverage(tmp_path,monkeypatch,complete):
    from dfm12 import baltic_pivots,wave_job_coverage
    monkeypatch.setattr(baltic_pivots,'main',lambda root:None)
    def coverage(root):
        if not complete:raise ValueError('missing coverage')
        return {'exact_payload_coverage':True}
    monkeypatch.setattr(wave_job_coverage,'reconcile',coverage)
    phases=[]
    if complete:
        m.continue_work(tmp_path,phases.append)
        assert (tmp_path/'parallel-preparation.json').exists()
        assert phases==['pivot_build','pivot_enqueue','exact_coverage','complete']
    else:
        with pytest.raises(ValueError):m.continue_work(tmp_path,phases.append)
        assert not (tmp_path/'parallel-preparation.json').exists()
