import json
import sqlite3

import pytest

from dfm12.multilingual_production_specs import SourceProvider, SeedUnavailable


def provider(tmp_path):
    seed = tmp_path/'seeds'
    seed.mkdir()
    db = sqlite3.connect(seed/'seeds.sqlite')
    db.execute('CREATE TABLE seeds(pool TEXT,seq INTEGER,source_id TEXT,payload TEXT)')
    db.execute('INSERT INTO seeds VALUES (?,?,?,?)', ('nl', 1, 'one', json.dumps({'id':'one','text':'example'})))
    db.commit()
    db.close()
    return SourceProvider(seed, tmp_path/'run', {'campaign':'dfm12-multilingual-v1'})


def test_resume_same_slot_and_no_repeated_source(tmp_path):
    p = provider(tmp_path)
    first = p.next_spec('nl', 'grounded-instruct', 100000)
    assert p.next_spec('nl', 'grounded-instruct', 100000) == first
    with pytest.raises(SeedUnavailable):
        p.next_spec('nl', 'summary-rewrite', 100000)
    assert p.db.execute('SELECT count(*) FROM selections').fetchone()[0] == 1
    p.close()


def test_seedless_groups_can_start(tmp_path):
    p = provider(tmp_path)
    spec = p.next_spec('fo', 'tool-dialogue', 100000)
    assert spec['contract_version'] == 4 and 'source' not in spec
    assert spec['cohort'] == 'dfm12-multilingual-v1'
    p.close()


def test_reopen_preserves_allocation(tmp_path):
    p = provider(tmp_path)
    first = p.next_spec('nl', 'grounded-instruct', 100000)
    p.close()
    p = SourceProvider(tmp_path/'seeds', tmp_path/'run', {'campaign':'dfm12-multilingual-v1'})
    assert p.next_spec('nl', 'grounded-instruct', 100000) == first
    p.close()


def test_openhermes_respects_language_specific_view(tmp_path):
    p = provider(tmp_path)
    db = sqlite3.connect(p.seeds_path)
    db.execute("CREATE VIEW available_seeds AS SELECT 'nl' AS language,* FROM seeds WHERE source_id!='excluded'")
    for seq, key in enumerate(('excluded', 'allowed'), 1):
        db.execute('INSERT INTO seeds VALUES (?,?,?,?)', ('openhermes', seq, key,
            json.dumps({'id': key, 'messages': [{'role': 'user', 'content': 'test'},
                                              {'role': 'assistant', 'content': 'answer'}]})))
    db.commit()
    db.close()
    assert p.next_spec('nl', 'openhermes', 100000)['source']['id'] == 'allowed'
    p.close()
