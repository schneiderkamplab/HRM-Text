import copy
import json
import sqlite3

import pytest

from dfm12 import european_synthetic_specs as eu
from dfm12 import multilingual_tasks as tasks
from dfm12 import multilingual_seeds
from dfm12 import multilingual_generation_v4 as generation
from dfm12.multilingual_production_seeds import SCHEMA


def config():
    return dict(campaign='european-test-v1', languages=list(eu.LANGUAGES))


def seeds():
    source = dict(id='source-1', text='A library contains twelve books.',
                  repo='test/repo', revision='pinned-test', license='test-only')
    oh = dict(id='oh-1', messages=[dict(role='user', content='How many books?'),
                                  dict(role='assistant', content='Twelve books.')],
              repo='test/oh', revision='pinned-oh', license='test-only')
    return dict({language: [copy.deepcopy(source)] for language in eu.LANGUAGES}, openhermes=[oh])


def spec(language='de', family='grounded-instruct', slot=0):
    return eu.spec_for(language, family, slot, 0, seeds(),
        dict(contract_version=4, cohort='european-test-v1', quotas={'openhermes': 1}))


@pytest.mark.parametrize('language', eu.LANGUAGES)
@pytest.mark.parametrize('family', eu.FAMILIES)
def test_all_languages_families_preserve_live_factory(language, family):
    before = dict(tasks.LANGUAGES)
    result = spec(language, family)
    assert result['language_code'] == language
    assert result['language'] == eu.LANGUAGES[language]
    assert result['contract_version'] == 4
    assert tasks.LANGUAGES == before == multilingual_seeds.LANGUAGES
    assert result == spec(language, family)
    if 'source' in result:
        assert result['source']['revision'].startswith('pinned-')
    if family == 'tool-dialogue':
        assert result['subtype'] == 'single'
        assert result['scenario']['tools']


@pytest.fixture
def inventory(tmp_path):
    root = tmp_path/'seeds'
    root.mkdir()
    db = sqlite3.connect(root/'seeds.sqlite')
    db.executescript(SCHEMA)
    db.executemany('INSERT INTO languages VALUES (?)', [(x,) for x in eu.LANGUAGES])
    for pool, values in seeds().items():
        for index, value in enumerate(values, 1):
            db.execute('INSERT INTO seeds VALUES (?,?,?,?)', (pool,index,value['id'],json.dumps(value)))
    db.commit()
    yield root, db
    db.close()


def test_resume_no_wrap_shared_native_pool_and_append(inventory, tmp_path):
    root, db = inventory
    provider = eu.SourceProvider(root, tmp_path/'run', config())
    first = provider.next_spec('de', 'grounded-instruct', 0)
    with pytest.raises(eu.SeedUnavailable):
        provider.next_spec('de', 'summary-rewrite', 1)
    assert provider.db.execute('SELECT count(*) FROM selections').fetchone()[0] == 1
    provider.close()
    provider = eu.SourceProvider(root, tmp_path/'run', config())
    assert provider.next_spec('de', 'grounded-instruct', 0) == first
    added = dict(seeds()['de'][0], id='source-2')
    db.execute('INSERT INTO seeds VALUES (?,?,?,?)', ('de',2,added['id'],json.dumps(added)))
    db.commit()
    assert provider.next_spec('de', 'summary-rewrite', 1)['source'] == added
    provider.close()


def test_openhermes_target_exclusions_and_reuse(inventory, tmp_path):
    root, db = inventory
    db.execute('INSERT INTO exclusions VALUES (?,?,?,?)', ('openhermes','de','id','oh-1'))
    db.commit()
    provider = eu.SourceProvider(root, tmp_path/'run', config())
    with pytest.raises(eu.SeedUnavailable):
        provider.next_spec('de', 'openhermes', 0)
    assert provider.next_spec('fr', 'openhermes', 0)['source']['id'] == 'oh-1'
    assert provider.next_spec('es', 'openhermes', 0)['source']['id'] == 'oh-1'
    with pytest.raises(eu.SeedUnavailable):
        provider.next_spec('fr', 'openhermes', 1)
    provider.close()


def test_explicit_native_reuse_between_families_only(inventory, tmp_path):
    root, _ = inventory
    settings = dict(config(), source_reuse_by_family=True)
    provider = eu.SourceProvider(root, tmp_path/'run', settings)
    first = provider.next_spec('de', 'grounded-instruct', 0)
    assert provider.next_spec('de', 'summary-rewrite', 0)['source'] == first['source']
    with pytest.raises(eu.SeedUnavailable):
        provider.next_spec('de', 'grounded-instruct', 1)
    provider.close()
    provider = eu.SourceProvider(root, tmp_path/'run', settings)
    assert provider.next_spec('de', 'grounded-instruct', 0) == first
    provider.close()
    with pytest.raises(ValueError, match='drift'):
        eu.SourceProvider(root, tmp_path/'run', config())


def test_missing_inventory_only_pauses_source_families(tmp_path):
    provider = eu.SourceProvider(tmp_path/'missing', tmp_path/'run', config())
    assert provider.next_spec('uk','math-code',0)['reference']
    with pytest.raises(eu.SeedUnavailable):
        provider.next_spec('uk','grounded-instruct',0)
    provider.close()


@pytest.mark.parametrize('bad', [dict(id='wrong',text='Text'), dict(id='source-1',text=''),
                               dict(id='source-1',text='Text',language='fr')])
def test_bad_seed_rolls_back(inventory, tmp_path, bad):
    root, db = inventory
    db.execute('UPDATE seeds SET payload=? WHERE pool=?', (json.dumps(bad),'de'))
    db.commit()
    provider = eu.SourceProvider(root,tmp_path/'run',config())
    with pytest.raises(ValueError):
        provider.next_spec('de','grounded-instruct',0)
    assert provider.db.execute('SELECT count(*) FROM selections').fetchone()[0] == 0
    assert provider.db.execute('SELECT count(*) FROM used_sources').fetchone()[0] == 0
    provider.close()


@pytest.mark.parametrize('language', eu.LANGUAGES)
def test_actual_template_assembly_audit_no_admission(language):
    case = spec(language)
    raw = json.dumps(dict(user='Summarize this source.', assistant='The library has twelve books.'))
    row = eu.assemble(case, eu.decode(case, raw, 'stop'))
    assert row['admission_authorized'] is False
    assert row['native_speaker_review'] == 'pending'
    record = eu.audit_record(row)
    assert record['language_name'] == eu.LANGUAGES[language]
    assert record['source'] == case['source']
    assert case['source']['text'] in row['messages'][0]['content']
    request = eu.review_request(row)
    assert request['model'] == tasks.MODEL
    assert request['chat_template_kwargs']['enable_thinking'] is False
    assert eu.LANGUAGES[language] in request['messages'][1]['content']
    if language == 'pt_pt':
        assert 'not Brazilian Portuguese' in request['messages'][0]['content']
        assert 'not Brazilian Portuguese' in record['language_variant_requirements']


@pytest.mark.parametrize('slot', range(6))
def test_native_tools_natural_final_and_strict_raw(slot):
    case = spec('pt_pt','tool-dialogue',slot)
    result = dict(user='Please look up the supplied information.',final='The lookup outcome is described here.')
    if case['subtype'] == 'clarify':
        result.update(clarification='Which record should I look up?',clarification_reply='Use the supplied record.')
    elif case['subtype'] == 'no-call':
        result = dict(user='How might this fictional service work?',explanation='Such a service could look up availability.')
    row = eu.assemble(case, eu.decode(case,json.dumps(result),'stop'))
    assert row['messages'][-1]['content'] == result.get('final',result.get('explanation'))
    record = eu.audit_record(row)
    assert record['tool_dialogue_grounding']['semantic_review_required']
    assert record['language_name'] == 'European Portuguese (pt-PT)'
    assert not row['admission_authorized']
    with pytest.raises(ValueError):
        eu.decode(case,json.dumps(result),'length')
    with pytest.raises(ValueError):
        eu.decode(case,'{"user":"First","user":"Second","final":"Done"}','stop')


def test_language_and_config_fail_closed(inventory, tmp_path):
    root, _ = inventory
    provider = eu.SourceProvider(root,tmp_path/'run',config())
    for language in ('pt','pt_br','nb','en'):
        with pytest.raises(ValueError):
            provider.next_spec(language,'math-code',0)
    with pytest.raises(ValueError):
        provider.next_spec('de','unknown',0)
    provider.close()
    with pytest.raises(ValueError, match='drift'):
        eu.SourceProvider(root,tmp_path/'run',dict(config(),languages=['de']))


def test_request_uses_existing_generation_contract(monkeypatch):
    monkeypatch.setattr(generation,'measure_prompt',lambda *args, **kwargs: 100)
    request = eu.request(spec('pt_pt'))
    assert request['model'] == tasks.MODEL
    assert 'European Portuguese (pt-PT)' in request['messages'][1]['content']
    assert request['max_tokens'] == 4096
    assert 'grammar' in request['structured_outputs']
    assert 'not Brazilian Portuguese' in request['messages'][0]['content']
