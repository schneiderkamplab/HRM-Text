import sqlite3
import pytest
from scripts.package_dala_languages import select, package


def test_cross_pool_dedup_preserves_tasks_and_rejects_split_conflict():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE seen(id TEXT PRIMARY KEY,split TEXT,pool TEXT)')
    row=dict(task='acceptability',messages=[{'role':'user','content':'Q'},{'role':'assistant','content':'yes'}],target_message_index=1)
    assert select(db,row,'train_representative','recovery')[0]
    assert select(db,dict(row,provenance={'other':1}),'train_representative','baseline') == (False,select(db,row,'train_representative','baseline')[1],'recovery')
    assert select(db,dict(row,task='correction'),'train_representative','baseline')[0]
    with pytest.raises(ValueError,match='crosses'):
        select(db,row,'test_representative','baseline')


def test_nl_and_fa_require_both_pools(tmp_path):
    for language in ('nl','fa'):
        with pytest.raises(ValueError,match='Incomplete'):
            package(language,{'baseline':tmp_path},tmp_path/'out')
