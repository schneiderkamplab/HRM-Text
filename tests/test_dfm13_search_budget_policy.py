from concurrent.futures import ThreadPoolExecutor
import pytest
from scripts.dfm13_search_calibration import SearchBudget
from scripts.dfm13_search_supplement9 import SupplementBudget
from scripts.dfm13_search_budget_policy import migrate, ceiling


def seeded(root, count):
    b = SearchBudget(root)
    with b.db:
        b.db.executemany('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
                        [(str(i), str(i), str(i), 'reserved') for i in range(count)])
    return b


def test_migration_preserves_and_is_idempotent(tmp_path):
    b = seeded(tmp_path, 98)
    before = b.db.execute('SELECT * FROM searches ORDER BY key').fetchall()
    receipt = migrate(tmp_path)
    assert receipt['preserved_reservations'] == 98
    assert ceiling(b.db) == 200
    assert migrate(tmp_path) == receipt
    assert b.db.execute('SELECT * FROM searches ORDER BY key').fetchall() == before
    b.db.close()


def test_boundary_cache_hit_and_failed_no_refund(tmp_path):
    b = seeded(tmp_path, 98)
    migrate(tmp_path)
    key, _ = b.reserve('cached', 'cached')
    b.complete(key, b'{"data":[]}', {})
    with b.db:
        b.db.executemany('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
                        [('extra'+str(i), 'extra'+str(i), 'extra'+str(i), 'reserved') for i in range(101)])
    assert b.reserve('cached', 'cached')[1][0] == b'{"data":[]}'
    with pytest.raises(ValueError, match='budget exhausted'):
        b.reserve('new', 'new')
    b.db.close()


def test_racing_base_and_supplement_share_last_slot(tmp_path):
    b = seeded(tmp_path, 98)
    migrate(tmp_path)
    with b.db:
        b.db.executemany('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
                        [('extra'+str(i), 'extra'+str(i), 'extra'+str(i), 'reserved') for i in range(101)])
    b.db.close()
    def reserve(i):
        budget = SearchBudget(tmp_path) if i % 2 else SupplementBudget(tmp_path, {str(i):'query'+str(i)})
        try:
            budget.reserve('query'+str(i), str(i))
            return True
        except ValueError:
            return False
        finally:
            budget.db.close()
    # New owners must not collide with the seeded owner IDs.
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(1000, 1008))) == 1
    b = SearchBudget(tmp_path)
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0] == 200
    b.db.close()
