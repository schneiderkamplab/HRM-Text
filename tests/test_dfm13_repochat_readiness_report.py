import pytest
from scripts import dfm13_repochat_readiness_report as r


def test_distributions_are_actual_counts():
    assert r.distribution([]) == {'count':0}
    assert r.distribution([3,0,1]) == {'count':3,'sum':4,'min':0,'median':1,'p90':3,'max':3}


def test_report_requires_terminal_followups(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='not terminal'):
        r.report()


def test_strata():
    assert r.scope('Which library handles files?') == 'navigation'
    assert r.scope('How does this work?') == 'implementation_explanation'
    assert r.scope('Describe the project') == 'overview'
