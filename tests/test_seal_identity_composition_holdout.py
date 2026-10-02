import pytest

from scripts.seal_identity_composition_holdout import cases_from, normalize


def spec():
    return {'cases': [dict(id=f'case{i}', facts=['name'], criteria=['one', 'two'],
        da=[f'dansk {i} a', f'dansk {i} b'], en=[f'English {i} a', f'English {i} b']) for i in range(20)]}


def test_pairing_and_no_training():
    cases = cases_from(spec(), set())
    assert len(cases) == 40
    assert sum(len(c['users']) for c in cases) == 80
    assert not any(c['training_allowed'] for c in cases)


def test_overlap_fails():
    with pytest.raises(ValueError, match='overlaps'):
        cases_from(spec(), {normalize(' ENGLISH  2  A ')})


def test_duplicate_families_fail():
    value = spec()
    value['cases'][-1]['id'] = 'case0'
    with pytest.raises(ValueError):
        cases_from(value, set())


def test_duplicate_turns_fail():
    value = spec()
    value['cases'][0]['da'][1] = value['cases'][0]['da'][0]
    with pytest.raises(ValueError, match='overlaps'):
        cases_from(value, set())
