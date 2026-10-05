import json
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from dfm12.io import write_json
from dfm12.multilingual_quarter import Ledger
from dfm12.wave4_shard_prepare import assignment, FingerprintRegistry, partition_locked, verify_output


def fixture(tmp_path):
    root = tmp_path/'original'
    root.mkdir()
    languages = [f'l{i:02}' for i in range(11)]
    ledger = Ledger(root/'jobs.sqlite')
    ledger.initialize([dict(language=l, family='math', accepted_target=10) for l in languages])
    for i, language in enumerate(languages):
        ledger.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,fingerprint) VALUES(?,?,?,?,?,?,?)',
                          (language,language,'math',i,'accepted','production','fp-'+language))
        ledger.db.execute('UPDATE groups SET accepted=1,attempts=2,next_slot=100002 WHERE language=?', (language,))
        ledger.db.execute('INSERT INTO fingerprints VALUES(?,?)', ('fp-'+language,language))
    ledger.db.execute("INSERT INTO fingerprints VALUES('historical-reject','prior-history')")
    ledger.close()
    with sqlite3.connect(root/'spec-selections.sqlite') as db:
        db.executescript('CREATE TABLE metadata(key PRIMARY KEY,value);CREATE TABLE selections(id PRIMARY KEY,spec,seed_hash);'
                         'CREATE TABLE cursors(scope PRIMARY KEY,seq);CREATE TABLE used_sources(scope,source_id,PRIMARY KEY(scope,source_id));')
        for language in languages:
            db.execute('INSERT INTO selections VALUES(?,?,?)', (language,json.dumps(dict(language_code=language)), 'hash'))
            db.execute('INSERT INTO cursors VALUES(?,?)', (language+'/openhermes',99))
            db.execute('INSERT INTO used_sources VALUES(?,?)', (language+'/openhermes','seed'))
    write_json(root/'manifest.json', dict(campaign='fixture'))
    write_json(root/'seal.json', dict(manifest_sha256='fixture'))
    return root


def test_whole_languages_exact_ownership():
    shards = assignment([(f'l{i}',70000,0) for i in range(11)])
    assert len(shards) == 8
    assert sorted(len(s['languages']) for s in shards) == [1]*5+[2]*3
    assert len({l for s in shards for l in s['languages']}) == 11
    assert sum(s['remaining'] for s in shards) == 770000


def test_partition_preserves_counts_cursors_history_and_source(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path/'shards'
    result = partition_locked(root, output, tmp_path/'staging', expected_target=110)
    assert result['accepted'] == 11 and result['target'] == 110
    assert result['launch_authorized'] is False
    count = 0
    for shard in result['shards']:
        directory = output/f"shard-{shard['worker']}"
        with sqlite3.connect(directory/'jobs.sqlite') as db:
            assert {r[0] for r in db.execute('SELECT language FROM groups')} == set(shard['languages'])
            assert all(r == (1,2,100002) for r in db.execute('SELECT accepted,attempts,next_slot FROM groups'))
            count += db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        with sqlite3.connect(directory/'spec-selections.sqlite') as db:
            assert all(r[0] == 99 for r in db.execute('SELECT seq FROM cursors'))
            assert db.execute('SELECT count(*) FROM selections').fetchone()[0] == len(shard['languages'])
    assert count == 11
    registry = FingerprintRegistry(output/'fingerprints.sqlite')
    assert not registry.claim('historical-reject','new')
    assert not registry.claim('fp-l00','new')
    registry.close()
    with sqlite3.connect(root/'jobs.sqlite') as db:
        assert db.execute('SELECT sum(accepted) FROM groups').fetchone()[0] == 11


def test_active_refused_before_output(tmp_path):
    root = fixture(tmp_path)
    with sqlite3.connect(root/'jobs.sqlite') as db:
        db.execute('UPDATE groups SET active=1')
    with pytest.raises(ValueError, match='drained'):
        partition_locked(root,tmp_path/'out',tmp_path/'stage')
    assert not (tmp_path/'stage').exists()


def test_global_claim_race_one_owner_and_restart(tmp_path):
    path = tmp_path/'fingerprints.sqlite'
    FingerprintRegistry(path).close()
    def claim(owner):
        registry = FingerprintRegistry(path)
        try:
            return owner,registry.claim('same',owner)
        finally:
            registry.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, [str(i) for i in range(8)]))
    winners = [owner for owner, won in results if won]
    assert len(winners) == 1
    assert claim(winners[0])[1]


def test_drift_and_partial_output_fail_closed(tmp_path):
    root=fixture(tmp_path)
    partition_locked(root,tmp_path/'out',tmp_path/'stage', expected_target=110)
    write_json(tmp_path/'out'/'shard-0'/'ownership.json', {})
    with pytest.raises(ValueError,match='drift'):
        verify_output(tmp_path/'out')
    (tmp_path/'partial').mkdir()
    with pytest.raises(FileExistsError):
        partition_locked(root,tmp_path/'out2',tmp_path/'partial', expected_target=110)


def test_supervisor_aggregate_and_native_thread_caps(tmp_path):
    from scripts.supervise_wave4_shards import aggregate, command, THREAD_CAPS
    root=fixture(tmp_path)
    output=tmp_path/'out'
    receipt=partition_locked(root,output,tmp_path/'stage', expected_target=110)
    state=aggregate(output,receipt['shards'])
    assert (state['accepted'],state['target'],state['active']) == (11,110,0)
    assert len(state['groups']) == 11
    assert THREAD_CAPS == dict(RAYON_NUM_THREADS='2',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    assert command(output,3)[-2:] == ['--root',str(output/'shard-3')]
    assert len({s['endpoint'] for s in receipt['shards']}) == 8


def test_production_target_guard(tmp_path):
    root=fixture(tmp_path)
    with pytest.raises(ValueError,match='campaign target'):
        partition_locked(root,tmp_path/'out',tmp_path/'stage')
    assert not (tmp_path/'stage').exists()
