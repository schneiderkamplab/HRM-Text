import pytest
from scripts import dfm13_repochat_native25_dispositions as m


@pytest.mark.parametrize('label,expected',[('hard_hold_false_absence','independent_hard_hold'),('useful_partial_scope','independent_repair_hold'),('useful_supported_getuser_scope','supported_core_not_admitted')])
def test_dispositions(label,expected):
    assert m.disposition(label)==expected


def test_unknown_fails_closed():
    with pytest.raises(ValueError):m.disposition('automatically_admit')


def test_pin_and_seal_drift(tmp_path):
    path=tmp_path/'receipt.json';m.sealed(path,{'admission':False})
    with pytest.raises(ValueError):m.sealed(path,{'admission':True})
    with pytest.raises(ValueError):m.verify([{'path':str(path),'sha256':'0'*64}])
