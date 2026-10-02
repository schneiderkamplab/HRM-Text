import pytest
from scripts import dfm13_repochat_agnai_export_draft as m


def test_exact_localized_change():
    assert m.corrected('Before '+m.OLD+' After')=='Before '+m.NEW+' After'


@pytest.mark.parametrize('answer',['unrelated',m.OLD+m.OLD])
def test_no_guessed_replacement(answer):
    with pytest.raises(ValueError):m.corrected(answer)
