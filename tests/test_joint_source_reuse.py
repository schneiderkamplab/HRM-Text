import json
import sqlite3

import pytest

from dfm12.joint_source_reuse import SourceReuseProvider, SeedUnavailable
from dfm12.multilingual_production_specs import SourceProvider as Original
from dfm12.european_synthetic_specs import SourceProvider as European


def setup(tmp_path, language, cls, cap=3):
    seeds = tmp_path / 'seeds'
    seeds.mkdir(exist_ok=True)
    with sqlite3.connect(seeds / 'seeds.sqlite') as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS seeds
            (seq INTEGER PRIMARY KEY, pool TEXT, source_id TEXT, payload TEXT);
            CREATE VIEW IF NOT EXISTS available_seeds AS
            SELECT *,pool AS language FROM seeds WHERE source_id != 'excluded';''')
        for seq in (1, 2):
            db.execute('INSERT OR IGNORE INTO seeds VALUES (?,?,?,?)',
                (seq, language, str(seq), json.dumps(dict(id=str(seq), language=language,
                 text='A factual source passage.', url='https://example.test/'+str(seq)))))
    provider = cls(seeds, tmp_path/'original', dict(campaign='test', languages=[language]))
    return SourceReuseProvider(provider, tmp_path/'reuse', max_per_seed=cap)


@pytest.mark.parametrize('language,cls', [('fo', Original), ('is', Original),
    ('cs', European), ('ca', European), ('et', European), ('pt_pt', European)])
def test_round_robin_cap_restart_preserves_original(tmp_path, language, cls):
    p = setup(tmp_path, language, cls)
    first = [p.next_spec(language, 'grounded-instruct', n) for n in range(2)]
    original = list(p.provider.db.iterdump())
    specs = [p.next_spec(language, 'grounded-instruct', n) for n in range(2, 6)]
    assert [s['source']['id'] for s in specs] == ['1', '2', '1', '2']
    assert [s['source_reuse']['use_number'] for s in specs] == [2, 2, 3, 3]
    assert len({s['slot'] for s in first + specs}) == 6
    assert list(p.provider.db.iterdump()) == original
    if language == 'pt_pt':
        assert all('European Portuguese' in s['language_variant_requirements'] for s in specs)
    p.close()
    p = setup(tmp_path, language, cls)
    assert p.next_spec(language, 'grounded-instruct', 0) == first[0]
    assert p.next_spec(language, 'grounded-instruct', 2) == specs[0]
    with pytest.raises(SeedUnavailable, match='budget exhausted'):
        p.next_spec(language, 'summary-rewrite', 6)
    p.close()


def test_unique_append_preferred_and_exclusion_respected(tmp_path):
    p = setup(tmp_path, 'cs', European)
    for n in range(3):
        p.next_spec('cs', 'grounded-instruct', n)
    with sqlite3.connect(p.provider.seeds_path) as db:
        db.execute('INSERT INTO seeds VALUES (3,?,?,?)',
                   ('cs', '3', json.dumps(dict(id='3', text='New source'))))
    assert p.next_spec('cs', 'grounded-instruct', 3)['source']['id'] == '3'
    with sqlite3.connect(p.provider.seeds_path) as db:
        db.execute("DELETE FROM seeds WHERE source_id='2'")
    assert p.next_spec('cs', 'summary-rewrite', 4)['source']['id'] == '3'
    p.close()


def test_bad_payload_rolls_back_and_config_drift(tmp_path):
    p = setup(tmp_path, 'fo', Original)
    for n in range(2):
        p.next_spec('fo', 'grounded-instruct', n)
    with sqlite3.connect(p.provider.seeds_path) as db:
        db.execute('UPDATE seeds SET payload=? WHERE seq=1',
                   (json.dumps(dict(id='1', language='da', text='wrong')),))
    with pytest.raises(ValueError, match='mismatch'):
        p.next_spec('fo', 'grounded-instruct', 2)
    assert p.db.execute('SELECT count(*) FROM selections').fetchone()[0] == 0
    p.close()
    with pytest.raises(ValueError, match='drift'):
        setup(tmp_path, 'fo', Original, cap=4)


def test_openhermes_language_eligibility_and_scope(tmp_path):
    p = setup(tmp_path, 'fo', Original, cap=2)
    with sqlite3.connect(p.provider.seeds_path) as db:
        db.executescript('''DROP VIEW available_seeds;
            CREATE TABLE languages (language TEXT);
            INSERT INTO languages VALUES ('fo'),('is');
            CREATE VIEW available_seeds AS SELECT s.*,l.language FROM seeds s
            CROSS JOIN languages l WHERE (s.pool=l.language OR s.pool='openhermes')
            AND NOT (l.language='fo' AND s.source_id='excluded');''')
        for seq, sid in [(3, 'oh'), (4, 'excluded')]:
            db.execute('INSERT INTO seeds VALUES (?,?,?,?)',
                (seq, 'openhermes', sid, json.dumps(dict(id=sid, language='en', messages=[
                    dict(role='user', content='What is two plus two?'),
                    dict(role='assistant', content='Four.')]))))
    a = p.next_spec('fo', 'openhermes', 0)
    b = p.next_spec('fo', 'openhermes', 1)
    assert a['source'] == b['source']
    assert b['source_reuse']['use_number'] == 2
    with pytest.raises(SeedUnavailable):
        p.next_spec('fo', 'openhermes', 2)
    assert p.next_spec('is', 'openhermes', 0)['source']['id'] == 'oh'
    assert p.next_spec('is', 'openhermes', 1)['source']['id'] == 'excluded'
    assert p.next_spec('is', 'openhermes', 2)['source_reuse']['use_number'] == 2
    p.close()


def test_non_source_task_and_non_authorized_language_do_not_reuse(tmp_path):
    p = setup(tmp_path, 'fo', Original)
    assert 'source' not in p.next_spec('fo', 'multiturn', 1)
    assert p.db.execute('SELECT count(*) FROM uses').fetchone()[0] == 0
    with pytest.raises(SeedUnavailable):
        p.next_spec('nb', 'grounded-instruct', 0)
    assert p.db.execute('SELECT count(*) FROM uses').fetchone()[0] == 0
    p.close()
