from scripts import backfill_available_eval_averages as b
import json
import pytest


def test_missing_scores_not_imputed_or_old_alias():
    row, report = b.compute({b.tal.OLD: 1}, dict(epoch=1, train_step=10))
    assert 'headline_avg_dala_v2/danish' not in row
    assert 'headline_avg_talemaader_v2/danish' not in row
    assert not any(k.endswith('/score') for k in row)
    assert row['headline_avg_dala_v2/danish/count'] == 0


def test_available_expanded_and_population():
    key = 'dfm_eval/dala_v2_da/semantic_v1/macro_f1'
    row, report = b.compute({key: .75}, dict(epoch=1, train_step=10))
    assert row['headline_avg_dala_v2/danish'] == .75
    assert row['suite_avg_dala_v2/dfm'] == .75
    assert row['headline_avg_dala_v2/danish/count'] == 1
    assert not row['headline_avg_dala_v2/danish/complete']
    assert row['avg_population/dfm13_all_languages_v2/score'] == .75
    assert 'avg_population/dfm13_multilingual_v2/score' not in row


def test_raw_v2_enables_replacement():
    row, _ = b.compute({b.tal.NEW: .5, b.tal.OLD: 1}, dict(epoch=1, train_step=10))
    assert row['headline_avg_talemaader_v2/danish'] == .5
    assert row['headline_avg_dala_v2/danish'] == .5


def test_missing_v2_does_not_block_other_available_talemaader_recipe_inputs():
    key = next(k for k in b.tal.legacy.SECTION_KEYS['danish'] if k != b.tal.OLD)
    row, report = b.compute({key: .25, b.tal.OLD: 1}, dict(epoch=1, train_step=10))
    assert row['headline_avg_talemaader_v2/danish'] == .25
    assert row['headline_avg_talemaader_v2/danish/count'] == 1
    assert not row['headline_avg_talemaader_v2/danish/complete']
    assert b.tal.NEW in report['talemaader_only']['missing_or_invalid']


def test_axis_binding_and_latest_no_carry_forward():
    points = [dict(id='a', train_step=100, epoch=1), dict(id='b', train_step=200, epoch=2)]
    def event(step, epoch, history_step, value):
        return dict(train_step=step, epoch=epoch, history_step=history_step, key='k', value=value)
    selected, rejected = b.select(points, [event(100, 1, 1, .1), event(100, 1, 2, .2),
                                         event(100, 2, 3, .9), event(None, 1, 0, .3)])
    assert selected['a']['k']['value'] == .2
    assert selected['b'] == {}
    assert len(rejected) == 1


def test_zero_step_epoch_end_known_mapping():
    p = dict(id='end', train_step=754208, epoch=2)
    selected, rejected = b.select([p], [dict(train_step=0, epoch=2, history_step=9, key='k', value=.5)])
    assert selected['end']['k']['value'] == .5
    assert not rejected


def test_invalid_numeric_omitted():
    for value in (True, float('nan'), -1, 1.1):
        row, _ = b.compute({b.tal.NEW: value}, dict(epoch=1, train_step=10))
        assert 'headline_avg_talemaader_v2/danish' not in row
        assert 'headline_avg_dala_v2/danish' not in row


def test_sync_rejects_wrong_permit_before_wandb_init(tmp_path, monkeypatch):
    import wandb
    monkeypatch.setattr(wandb, 'init', lambda **kw: pytest.fail('Must not start writer'))
    payload = dict(run_path=b.RUNS['xl'], pins={}, points=[])
    payload['payload_sha256'] = b.canonical_hash(payload)
    path = tmp_path/'payload.json'
    path.write_text(json.dumps(payload))
    permit = tmp_path/'permit.json'
    permit.write_text(json.dumps(dict(run_path=b.RUNS['xxl'],
                                     payload_sha256=payload['payload_sha256'], exclusive_writer_confirmed=True)))
    with pytest.raises(ValueError, match='serialized'):
        b.sync(path, permit)


def test_sync_rejects_changed_payload(tmp_path):
    path = tmp_path/'payload.json'
    path.write_text(json.dumps(dict(payload_sha256='wrong', run_path=b.RUNS['xl'])))
    with pytest.raises(ValueError, match='Payload changed'):
        b.sync(path, tmp_path/'not-read.json')


def test_discovery_includes_non_talemaader_and_rejects_conflicting_axes():
    events = [dict(key='eval/math/accuracy', train_step=100, epoch=1),
              dict(key='euroeval/scala/mcc', train_step=200, epoch=2),
              dict(key='dfm_eval/task/score', train_step=200, epoch=3)]
    points, conflicts = b.discover_points('xxl', events)
    assert [p['train_step'] for p in points] == [100]
    assert conflicts[0]['train_step'] == 200


def test_discovery_zero_epoch_end_and_authoritative_seed():
    events = [dict(train_step=0, epoch=2), dict(train_step=100, epoch=2)]
    points, conflicts = b.discover_points('xxl', events, [dict(id='a', train_step=100, epoch=1)])
    assert [p['train_step'] for p in points] == [100, 754208]
    assert points[0]['epoch'] == 1
    assert conflicts


def test_history_count_guard():
    assert b.check_history_count('k', 2, [{'_step': 1}, {'_step': 2}], 100)['returned'] == 2
    with pytest.raises(ValueError, match='Incomplete'):
        b.check_history_count('k', 3, [{'_step': 1}], 100)
    with pytest.raises(ValueError, match='capped'):
        b.check_history_count('k', 1, [{'_step': 1}], 1)
