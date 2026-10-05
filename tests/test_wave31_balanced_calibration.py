import json
import sqlite3

import pytest

from dfm12.wave31_balanced_calibration import (
    FAMILIES, check_groups, exposure_snapshot, identity, prepare,
)


def test_source_identity_ignores_new_allocation_and_id():
    a = dict(slot=1, source=dict(id='old', text='same text'))
    b = dict(slot=200, source=dict(id='new', text='same text'))
    assert identity(a) == identity(b)
    b['source']['text'] = 'fresh text'
    assert identity(a) != identity(b)


def test_non_source_identity_does_not_hide_reference_drift():
    a = dict(slot=1, cohort='old', language_code='lt', family='math-code', reference={'answer': 15})
    assert identity(a) == identity(dict(a, slot=999, cohort='new'))
    assert identity(a) == identity(dict(a, tone='different', language_code='lv'))
    assert identity(a) != identity(dict(a, reference={'answer': 16}))


def test_all_groups_required_not_just_total():
    specs = [dict(language_code=l, family=f) for l in ('lt', 'lv') for f in FAMILIES for _ in range(3)]
    assert len(check_groups(specs, ['lt', 'lv'], 3)) == 12
    specs[-1] = specs[0]
    with pytest.raises(ValueError, match='coverage'):
        check_groups(specs, ['lt', 'lv'], 3)


def test_exposure_reads_specs_without_scores(tmp_path):
    d = tmp_path/'prior'
    d.mkdir()
    spec = dict(language_code='lt', family='multiturn', slot=2)
    with sqlite3.connect(d/'jobs.sqlite') as db:
        db.execute('CREATE TABLE jobs(spec_json TEXT, outcome_json TEXT)')
        db.execute('INSERT INTO jobs VALUES (?,?)', (json.dumps(spec), 'NOT JSON: must not read'))
    specs, inventory = exposure_snapshot(tmp_path)
    assert specs == [spec]
    assert inventory[0]['specs'] == 1


def test_existing_root_and_low_coverage_rejected(tmp_path):
    with pytest.raises(ValueError, match='Fresh immutable'):
        prepare(tmp_path)
    with pytest.raises(ValueError, match='At least three'):
        prepare(tmp_path/'new', 2)
