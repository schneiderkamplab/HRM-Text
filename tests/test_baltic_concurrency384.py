import pytest
from dfm12.baltic_concurrency384 import widen, controller


def test_private_guard_and_original_unchanged():
    from dfm12.compact_keep_recovery import controller as original
    before = original().execute.__code__.co_consts
    c = controller()
    assert 384 in c.execute.__code__.co_consts
    assert 128 not in c.execute.__code__.co_consts
    assert original().execute.__code__.co_consts == before
    assert c.validate_saved_keep is not None


def test_unknown_guard_closed():
    with pytest.raises(ValueError):
        widen(lambda: None)
