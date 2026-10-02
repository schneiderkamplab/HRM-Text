import pytest
from scripts.dfm13_search_lastslots2 import Budget, relevant_payload


def test_original_global_cap_counts_reserved_failures(tmp_path):
    budget = Budget(tmp_path, {'a':'query a','b':'query b'})
    with budget.db:
        budget.db.executemany('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
            [(str(i),'old'+str(i),'old query '+str(i),'reserved') for i in range(99)])
    budget.reserve('query a','a')
    with pytest.raises(ValueError, match='ceiling'):
        budget.reserve('query b','b')
    assert budget.db.execute('SELECT count(*) FROM searches').fetchone()[0] == 100
    budget.db.close()


def test_out_of_scope_queries_fail_without_reservation(tmp_path):
    budget = Budget(tmp_path, {'a':'query a','b':'query b'})
    with pytest.raises(ValueError, match='scope'):
        budget.reserve('different','a')
    assert budget.db.execute('SELECT count(*) FROM searches').fetchone()[0] == 0
    budget.db.close()


def test_cisco_not_neighbor_product_or_lookalike_host():
    pages = [dict(url='https://cisco.com.example.org/a',title='IE 1000',content='stuff'),
             dict(url='https://www.cisco.com/a',title='IE 3400',content='stuff'),
             dict(url='https://www.cisco.com/b',title='IE 1000 data sheet',content='stuff')]
    assert relevant_payload(dict(data=pages),'e5913568')['data'] == pages[2:]
