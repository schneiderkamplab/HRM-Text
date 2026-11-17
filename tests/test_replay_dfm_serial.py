import json
from pathlib import Path

import numpy as np
import pytest

from scripts.replay_dfm_serial import check_backing, run_serial, tree_command


def test_serial_failure_never_starts_successor(tmp_path):
    seen = []

    def boundary(version, output, progress):
        seen.append(version)
        if version == 2:
            assert (output / 'dfm1/verified.json').exists()
            raise ValueError('mismatch')
        return {'status': 'matched'}

    with pytest.raises(ValueError, match='mismatch'):
        run_serial(tmp_path, 3, boundary)
    assert seen == [1, 2]
    assert not (tmp_path / 'dfm2/verified.json').exists()
    assert json.loads((tmp_path / 'progress.json').read_text())['phase'] == 'blocked'


def test_predecessors_are_replay_paths(tmp_path):
    for version in (2, 3, 4, 7, 8, 10, 11):
        assert str(tmp_path / f'dfm{version-1}/tokenized') in tree_command(version, tmp_path)
    with pytest.raises(RuntimeError, match='refusing to substitute'):
        tree_command(9, tmp_path)


def test_backing_checks_actual_values(tmp_path):
    tree, reference = tmp_path / 'tree', tmp_path / 'reference'
    task = tree / 'example'
    task.mkdir(parents=True)
    reference.mkdir()
    (task / 'metadata.json').write_text('{}')
    np.save(task / 'tokens.npy', np.array([1, 2, 3], dtype=np.int32))
    np.save(task / 'inst_len.npy', np.array([1]))
    np.save(task / 'resp_len.npy', np.array([2]))
    np.save(reference / 'tokens.npy', np.array([1, 2, 3], dtype=np.int32))
    assert check_backing(tree, reference, lambda _: None)['tokens'] == 3
    np.save(reference / 'tokens.npy', np.array([1, 9, 3], dtype=np.int32))
    with pytest.raises(ValueError, match='Token mismatch'):
        check_backing(tree, reference, lambda _: None)
