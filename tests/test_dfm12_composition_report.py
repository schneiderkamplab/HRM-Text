import pytest

from scripts.build_dfm12_composition_report import composition_page, error_page


def test_unknown_inherited_stays_visible():
    data = dict(language_family_rows=[],
                totals=dict(combined=dict(rendered_tokens=100, rows=10), inherited_dfm11=dict(rendered_tokens=90), dfm12_additions=dict(rendered_tokens=10)),
                unknowns=[dict(component='inherited_dfm11', family='unclassified', rendered_tokens=90, rows=9)])
    page = composition_page(data)
    assert page['rows'][-1][0] == 'Inherited DFM11'
    assert page['rows'][0][1] is None
    assert any('NOT zero' in note for note in page['notes'])


def test_refuses_running_statistics():
    with pytest.raises(ValueError, match='incomplete'):
        error_page({'status': 'in_progress'})


def test_recovered_sources_can_still_have_unknown_language():
    data = dict(language_family_rows=[], inherited_source_recovery={'source_tasks': 1},
                totals=dict(combined=dict(rendered_tokens=100, rows=10), inherited_dfm11=dict(rendered_tokens=90), dfm12_additions=dict(rendered_tokens=10)),
                unknowns=[dict(component='inherited_dfm11', family='qa', rendered_tokens=90, rows=9),
                          dict(component='dfm12_additions', family='unclassified', rendered_tokens=10, rows=1)])
    page = composition_page(data)
    assert page['rows'][-2][0] == 'Base: language unassigned'
    assert any('was recovered' in note for note in page['notes'])
    assert not any('no locally recoverable' in note for note in page['notes'])
