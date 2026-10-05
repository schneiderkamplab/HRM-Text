import sqlite3
from types import SimpleNamespace

import pytest

from dfm12.multilingual_quarter import Ledger
from dfm12.wave4_topup_ledger import migrate_groups, install


def prepared(tmp_path):
    original=Ledger(tmp_path/'jobs.sqlite')
    original.db.execute("INSERT INTO groups(language,family,target,accepted,attempts) VALUES('lb','math-code',6,2,36)")
    row=dict(original.db.execute('SELECT * FROM groups').fetchone())
    policy=dict(row,target=3,original_target=6,attempt_limit=72,accepted_floor=2)
    return original,policy


def test_absolute_cap_and_acceptance_floor(tmp_path):
    old,policy=prepared(tmp_path)
    migrate_groups(old.db,[policy])
    row=dict(old.db.execute('SELECT * FROM groups').fetchone())
    assert row['attempts']==36 and row['attempt_limit']==72 and row['target']==3
    old.db.execute('UPDATE groups SET attempts=72')
    with pytest.raises(sqlite3.IntegrityError):old.db.execute('UPDATE groups SET attempts=73')
    with pytest.raises(sqlite3.IntegrityError):old.db.execute('UPDATE groups SET accepted=1')
    old.close()


def test_failed_migration_rolls_back_schema_and_rows(tmp_path):
    old,policy=prepared(tmp_path)
    with pytest.raises(ValueError):migrate_groups(old.db,[dict(policy,accepted_floor=1)])
    assert dict(old.db.execute('SELECT * FROM groups').fetchone())['target']==6
    assert 'attempt_limit' not in {r[1] for r in old.db.execute('PRAGMA table_info(groups)')}
    old.close()


def test_underfilled_old_cap_is_now_runnable(tmp_path):
    old,policy=prepared(tmp_path);migrate_groups(old.db,[policy]);old.close()
    c=SimpleNamespace(Ledger=Ledger)
    install(c,SimpleNamespace(remaining_hint=True),[('lb','math-code')])
    ledger=c.Ledger(tmp_path/'jobs.sqlite')
    assert len(ledger.remaining_groups())==1
    ledger.db.execute('UPDATE groups SET attempts=72')
    assert not ledger.remaining_groups()
    ledger.close()
