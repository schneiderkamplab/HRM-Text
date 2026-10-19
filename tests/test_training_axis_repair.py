import pytest

from scripts.repair_xl_training_axis import add_observation


def test_duplicate_api_rows_do_not_duplicate_payload():
    rows = {}
    add_observation(rows, 5, 'train/loss', 1.2)
    add_observation(rows, 5, 'train/loss', 1.2)
    add_observation(rows, 5, 'train/accuracy', 0.5)
    assert rows == {5: {'train/step': 5, 'train/loss': 1.2, 'train/accuracy': 0.5}}


def test_conflicting_rows_are_not_silently_overwritten():
    rows = {}
    add_observation(rows, 5, 'train/loss', 1.2)
    with pytest.raises(RuntimeError, match='Conflicting'):
        add_observation(rows, 5, 'train/loss', 1.3)
