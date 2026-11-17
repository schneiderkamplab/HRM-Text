import numpy as np
from scripts.sample_dfm16 import eligible, interleave


def test_eligibility_complete_rows():
    arrays = {'inst_len': np.array([100, 4090, 100]), 'resp_len': np.array([10, 8, 0])}
    assert eligible(arrays, 4097).tolist() == [True, False, False]


def test_interleaving_preserves_base_and_repeats_across_chunks():
    old = np.array([10, 20, 30, 40], dtype=np.uint64)
    added = np.array([99, 99, 77], dtype=np.uint64)
    pos = np.array([0, 3, 6])
    order = np.array([2, 0, 1])
    result = np.concatenate([interleave(old, added, pos, order, i, min(i+2, 7))[0]
                             for i in range(0, 7, 2)])
    assert result.tolist() == [77, 10, 20, 99, 30, 40, 99]
    assert np.delete(result, pos).tolist() == old.tolist()
