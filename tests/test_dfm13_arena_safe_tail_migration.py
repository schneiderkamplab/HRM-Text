import importlib.util
import sys
import sqlite3
from pathlib import Path
import pytest
from scripts.dfm13_arena_safe_tail_migration import archive_interrupted


def test_only_current_inflight_is_exempt_and_records_unchanged(tmp_path):
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE attempts(seq,stage,n,status,hash,record)')
    rows=[(1,'correction',3,'inflight','h','{"raw":"preserved"}'),
          (2,'retry_audit',1,'complete','h2','{"result":{}}'),
          (3,'retry_audit',2,'abort_status_unknown','h3','{"error":"TimeoutError"}')]
    db.executemany('INSERT INTO attempts VALUES(?,?,?,?,?,?)',rows)
    path=tmp_path/'allowance.json'
    assert archive_interrupted(db,path)==1
    after=db.execute('SELECT * FROM attempts ORDER BY seq').fetchall()
    assert after[0]==(1,'correction',3,'interrupted_unknown','h',rows[0][-1])
    assert after[1:]==rows[1:]
    with pytest.raises(ValueError):archive_interrupted(db,path)


def test_staged_runner_cache_precedes_budget_and_records_route():
    p=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_repairs_migrated.py'
    source=p.read_text()
    compile(source,str(p),'exec')
    assert source.index("return json.loads(record)['result']") < source.index('for n in retry_numbers(')
    assert "endpoint_index=i, endpoint=manifest['endpoints'][i]" in source
    assert "raw_directory=str(root/'raw'/str(i))" in source
    assert 'queues[queue_index].task_done()' in source
    assert "UPDATE attempts SET status='interrupted_unknown'" not in source
