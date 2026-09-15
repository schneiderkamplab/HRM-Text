import numpy as np
import json
import sys

from scripts.analyze_training_log_uncertainty import bootstrap_means, holm
from scripts.analyze_training_log_uncertainty import main
from scripts.analyze_training_log_uncertainty import trend_estimate


def test_linear_trend_units():
    steps = np.arange(5, 20001, 5)
    t = trend_estimate(steps, 1 - .01 * steps / 10000, 500)
    np.testing.assert_allclose(t['slope_per_10k'], -.01)
    assert t['se'] < 1e-12


def test_hac_accounts_for_correlated_noise():
    rng = np.random.default_rng(42)
    steps = np.arange(5, 20001, 5)
    errors = np.zeros(len(steps))
    for i in range(1, len(errors)):
        errors[i] = .9 * errors[i-1] + rng.normal()
    assert trend_estimate(steps, errors, 500)['se'] > 2 * trend_estimate(steps, errors, 0)['se']


def test_constant_series():
    samples = bootstrap_means(np.ones(123), 20, 1000, np.random.default_rng(0))
    np.testing.assert_allclose(samples, 1)


def test_block_bootstrap_mean_and_reproducibility():
    x = np.arange(100, dtype=float)
    a = bootstrap_means(x, 9, 5000, np.random.default_rng(1))
    b = bootstrap_means(x, 9, 5000, np.random.default_rng(1))
    np.testing.assert_equal(a, b)
    assert abs(a.mean() - x.mean()) < .5


def test_correlated_series_needs_wider_interval():
    x = np.repeat(np.arange(20, dtype=float), 50)
    iid = bootstrap_means(x, 1, 2000, np.random.default_rng(0))
    blocks = bootstrap_means(x, 50, 2000, np.random.default_rng(0))
    assert blocks.std() > 3 * iid.std()


def test_holm():
    np.testing.assert_allclose(holm([.04, .001, .03]), [.06, .003, .06])


def test_configurable_windows_and_explicit_ranges(tmp_path, monkeypatch):
    source = tmp_path / 'history.jsonl'
    source.write_text(''.join(json.dumps(dict(_step=i, **{'train/loss': 1., 'train/accuracy': .8,
                                                        'train/exact_accuracy': .3})) + '\n' for i in range(1, 101)))
    for options, expected in [(['--window-steps', '20'], 5),
                               (['--ranges', '0:30', '50:100'], 2)]:
        output = tmp_path / 'report'
        monkeypatch.setattr(sys, 'argv', ['analyze', str(source), '--block-steps', '2', '--draws', '1000',
                                         '--output', str(output)] + options)
        main()
        result = json.loads(output.with_suffix('.json').read_text())
        assert len(result['windows']) == expected
        assert not any(c['holm_detected'] for c in result['adjacent_comparisons'])
