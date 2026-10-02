import sys
from types import SimpleNamespace

import pytest

from scripts import log_dfm5_headline_averages as headline
from scripts import backfill_external_eval_to_wandb as backfill


@pytest.fixture
def metrics(monkeypatch):
    values = {headline.STRICT_DALA_KEY: 0.2, headline.SEMANTIC_DALA_KEY: 0.8,
              'eval/ARC/acc': 0.4}
    monkeypatch.setattr(headline, 'gather_metrics', lambda item: values)
    return values


def test_semantic_membership_and_legacy_unchanged(metrics):
    item = SimpleNamespace(epoch=1, step=10)
    legacy = headline.build_row(item, 'headline_avg_v3')
    semantic = headline.build_row(item, 'headline_avg_semantic_v1')
    assert legacy['headline_avg_v3/danish'] == 0.2
    assert semantic['headline_avg_semantic_v1/danish'] == 0.8
    assert semantic['headline_avg_semantic_v1/overall'] == pytest.approx(0.6)
    assert legacy['headline_avg_v3/overall'] == pytest.approx(0.3)
    suite = headline.build_row(item, 'suite_avg_semantic_v1')
    assert suite['suite_avg_semantic_v1/dfm'] == 0.8
    assert suite['suite_avg_semantic_v1/dfm/count'] == 1
    assert headline.build_row(item, 'headline_avg_v3') == legacy
    assert headline.STRICT_DALA_KEY in headline.DANISH_KEYS
    assert headline.SEMANTIC_DALA_KEY not in headline.DANISH_KEYS


def test_no_strict_fallback_and_overall_only(metrics):
    del metrics[headline.SEMANTIC_DALA_KEY]
    item = SimpleNamespace(epoch=1, step=10)
    row = headline.build_row(item, 'headline_avg_semantic_v1')
    assert row['headline_avg_semantic_v1/danish/count'] == 0
    assert 'headline_avg_semantic_v1/danish' not in row
    assert row['headline_avg_semantic_v1/dfm/count'] == 0
    assert 'headline_avg_semantic_v1/dfm' not in row
    row = headline.build_row(item, 'headline_avg_semantic_v1',
                             include_sections=False, include_suites=False, overall_only=True)
    assert 'headline_avg_semantic_v1/overall' not in row


@pytest.mark.parametrize('value', [None, float('nan'), float('inf')])
def test_missing_semantic_suppresses_affected_partial_averages(metrics, value):
    if value is None:
        del metrics[headline.SEMANTIC_DALA_KEY]
    else:
        metrics[headline.SEMANTIC_DALA_KEY] = value
    metrics['dfm_eval/gec_dala/exact_match/mean'] = 0.6
    item = SimpleNamespace(epoch=1, step=10)
    for prefix in headline.SEMANTIC_PREFIXES:
        row = headline.build_row(item, prefix)
        assert row[prefix + '/danish/count'] == 1
        assert row[prefix + '/dfm/count'] == 1
        assert row[prefix + '/english'] == 0.4
        for affected in ('danish', 'overall', 'dfm'):
            assert prefix + '/' + affected not in row
    legacy = headline.build_row(item, 'headline_avg_v3')
    assert legacy['headline_avg_v3/danish'] == pytest.approx(0.4)
    assert 'headline_avg_v3/overall' in legacy


@pytest.mark.parametrize('atomic', [False, True])
def test_cli_fake_wandb_atomic_registration(tmp_path, monkeypatch, metrics, atomic):
    monkeypatch.setitem(sys.modules, 'log_dfm5_headline_averages', headline)
    logged, defined = [], []
    fake = SimpleNamespace(init=lambda **kw: SimpleNamespace(summary={}),
        define_metric=lambda key, **kw: defined.append((key, kw)),
        log=lambda row, **kw: logged.append((row, kw)), finish=lambda: None)
    monkeypatch.setitem(sys.modules, 'wandb', fake)
    monkeypatch.setattr(backfill, 'collect_dfm', lambda root: metrics)
    argv = ['backfill', '--project', 'fixture', '--run-id', 'fixture', '--run-name', 'fixture',
            '--standard-root', str(tmp_path), '--dfm-root', str(tmp_path),
            '--euroeval-root', str(tmp_path), '--log-averages', '--averages-only',
            '--average-scope', 'all',
            '--average-prefix', 'headline_avg_v3' if atomic else 'headline_avg_semantic_v1',
            '--extra-average-prefix', 'suite_avg_semantic_v1']
    if atomic:
        argv += ['--atomic-v3-averages', '--extra-average-prefix', 'headline_avg_semantic_v1']
    monkeypatch.setattr(sys, 'argv', argv)
    backfill.main()
    assert len(logged) == 1 and logged[0][1]['commit'] is True
    row = logged[0][0]
    assert row['headline_avg_semantic_v1/danish'] == 0.8
    assert row['suite_avg_semantic_v1/dfm'] == 0.8
    assert ('suite_avg_semantic_v1/dfm',
            dict(step_metric='suite_avg_semantic_v1/epoch', summary='last')) in defined
    if atomic:
        assert row['headline_avg_v3/danish'] == row['suite_avg_v3/dfm'] == 0.2
        assert headline.SEMANTIC_DALA_KEY in row
    else:
        # Exact additive-clone contract: no raw/legacy keys and no cross-namespace
        # section/suite copies. Epoch and train_step belong to each namespace.
        assert all(key.startswith(('headline_avg_semantic_v1/', 'suite_avg_semantic_v1/'))
                   for key in row)
        assert not any('headline_avg_semantic_v1/' + suite in row
                       for suite in headline.SUITE_KEYS)
        assert not any('suite_avg_semantic_v1/' + section in row
                       for section in (*headline.SECTION_KEYS, 'overall'))
        assert row['headline_avg_semantic_v1/overall'] == pytest.approx(0.6)
        assert not any(key.startswith(('headline_avg_v3/', 'suite_avg_v3/'))
                       for key, _ in defined)
