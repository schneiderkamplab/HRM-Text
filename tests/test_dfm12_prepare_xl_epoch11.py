from types import SimpleNamespace

import numpy as np
import pytest

from dfm12.prepare_xl_epoch11 import count_steps, sampling_policy
from models.lr_rewarm import resolve_rewarm, rewarm_lr


def test_identity_zero_is_scoped_and_does_not_mutate_inventory():
    sources = [{'name': 'dfm12-identity-xl-full-bp-en', 'repeat': 10},
               {'name': 'dfm12-multilingual-synthetic-fo', 'repeat': 1}]
    assert [p['repeat'] for p in sampling_policy(sources)] == [0, 1]
    assert sources[0]['repeat'] == 10


def test_exact_count_uses_training_drop_last_and_gas(tmp_path):
    from multipack_sampler import MultipackDistributedBatchSampler
    lengths = np.array([4, 7, 3, 2, 6, 5, 3, 4] * 20, dtype=np.int64)
    np.save(tmp_path / 'inst_len.npy', lengths)
    np.save(tmp_path / 'resp_len.npy', np.ones(len(lengths), dtype=np.int64))
    expected = len(list(MultipackDistributedBatchSampler(16, lengths, 2, 0,
                                                        drop_last_batch=True).iter_with_info()))
    result = count_steps(tmp_path, batch_tokens=16, world_size=2, gas=2)
    assert result['microbatches'] == expected
    assert result['optimizer_steps'] == expected // 2
    assert result['dropped_accumulation_microbatches'] == expected % 2


def test_rewarm_hold_then_3250k_cosine():
    start, end = 2877261, 3325079
    config = SimpleNamespace(lr=3e-4, lr_min_ratio=1/30,
        lr_rewarm_steps=2900000-start, lr_rewarm_start_ratio=1/30,
        lr_rewarm_start_step=start, lr_decay_start_step=3250000,
        lr_decay_end_step=end)
    resolve_rewarm(config, start, {})
    for step, expected in [(start, 1e-5), ((start+2900000)/2, 1.55e-4),
                           (2900000, 3e-4), (3250000, 3e-4),
                           ((3250000+end)/2, 1.55e-4), (end, 1e-5)]:
        assert rewarm_lr(config, step) == pytest.approx(expected)
