import pytest
from scripts import dfm13_arena_authorized_release as m


def valid():
    return dict(user_release_authorized=True,quality_certified=False,
        manual_per_row_verified=False,diagnostic100_merged=False,
        exclude_all_current_holds=True,pins={},selections=[],total=0)


@pytest.mark.parametrize('key',['user_release_authorized','quality_certified',
    'manual_per_row_verified','diagnostic100_merged','exclude_all_current_holds'])
def test_scope_fail_closed(key,monkeypatch):
    value=valid();value[key]=not value[key]
    monkeypatch.setattr(m.guard,'load',lambda _:value)
    with pytest.raises(ValueError):m.validate_release('unused')


def test_release_count_and_pin_fail_closed(monkeypatch):
    value=valid();value['total']=1
    monkeypatch.setattr(m.guard,'load',lambda _:value)
    with pytest.raises(ValueError,match='total'):m.validate_release('unused')
    value['pins']={'a':'expected'}
    monkeypatch.setattr(m.guard,'file_hash',lambda _:'changed')
    with pytest.raises(ValueError,match='pin drift'):m.validate_release('unused')
