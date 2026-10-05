import sqlite3
import pytest
from dfm12.wave4_recovery_parallel import partition_number,SCHEMA


def test_32_partitions_per_source_no_overlap():
    values=[(s,f'{n:08x}'+'0'*56) for s in range(8) for n in range(64)]
    counts={i:0 for i in range(256)}
    for shard,key in values:
        part=partition_number(shard,key)
        assert part//32==shard
        counts[part]+=1
    assert set(counts.values())=={2}


def test_committed_proofs_survive_backup_and_uncommitted_rollback(tmp_path):
    source=sqlite3.connect(tmp_path/'old.sqlite');source.execute('PRAGMA journal_mode=WAL');source.execute(SCHEMA)
    source.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',('old','fa','math-code',1,'proof',None,'fp'));source.commit()
    source.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',('pending','fa','math-code',0,None,'error',None));source.rollback()
    dest=sqlite3.connect(tmp_path/'new.sqlite');source.backup(dest)
    assert dest.execute('SELECT id,receipt FROM results').fetchall()==[('old','proof')]
    with pytest.raises(sqlite3.IntegrityError):dest.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',('old','fa','math-code',1,'other',None,'fp'))
    source.close();dest.close()
