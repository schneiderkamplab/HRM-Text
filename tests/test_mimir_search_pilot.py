import pytest
from scripts.mimir_search_pilot import execute, seeds, LANGUAGES


def documents():
    return [dict(id='DNK:gdp', title='Denmark GDP', country_code='DNK', split='train',
        values=[{'year': '2018', 'value': 10}, {'year': '2023', 'value': 12}], definition='GDP',
        attribution='World Bank', projection='complete', provenance={'url': 'https://api.worldbank.org/x',
        'retrieved_at': '2026-10-01', 'sha256': 'abc'})]


def test_executed_search_then_read():
    visible = set()
    result = execute('search', {'query': 'Denmark'}, documents(), visible)
    assert result['results'][0]['document_id'] == 'DNK:gdp'
    assert execute('read', {'document_id': 'DNK:gdp'}, documents(), visible)['values'][1]['value'] == 12


def test_no_oracle_read_or_invalid_arguments():
    with pytest.raises(ValueError):
        execute('read', {'document_id': 'DNK:gdp'}, documents(), set())
    with pytest.raises(ValueError):
        execute('search', {'query': 'GDP', 'oracle': 'x'}, documents(), set())


def test_languages_and_no_heldout_seeds():
    docs = documents() + [dict(documents()[0], id='CAN:gdp', split='heldout', country_code='CAN')]
    queue = list(seeds(docs, 200))
    assert len(LANGUAGES) == 21
    assert sum(s['language'] == 'da' for s in queue) == 100
    assert sum(s['language'] == 'en' for s in queue) == 50
    assert len({s['language'] for s in queue}) == 21
    assert all(s['source_group'] == 'DNK' for s in queue)
