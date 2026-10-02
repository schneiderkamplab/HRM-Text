import sqlite3

import pytest

from dfm12.european_anchors import matches
from dfm12.european_handoff import cpu_ready, materialize
from dfm12.io import write_json
from dfm12.jobs import Queue


def test_anchor_join_requires_one_translation_and_same_release():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE anchors(lang,corpus,version,english,target,provenance)')
    db.executemany('INSERT INTO anchors VALUES (?,?,?,?,?,?)', [
        ('de','Tatoeba','v1','Hello','Hallo','{}'),
        ('fo','Tatoeba','v1','Hello','Hey','{}'),
        ('de','Tatoeba','v1','Ambiguous','A','{}'),
        ('de','Tatoeba','v1','Ambiguous','B','{}'),
        ('fo','Tatoeba','v1','Ambiguous','C','{}'),
        ('de','Tatoeba','v1','Other release','D','{}'),
        ('fo','Tatoeba','v2','Other release','E','{}'),
    ])
    assert list(matches(db,'de','fo')) == [('Hello','Hallo','Hey','{}','{}')]


def test_cpu_handoff_rejects_incomplete_screening(tmp_path):
    write_json(tmp_path/'text-replenishment/completion.json',dict(complete=True))
    write_json(tmp_path/'screened/status.json',dict(stage='indexing_references'))
    with pytest.raises(ValueError,match='not finished'):
        cpu_ready(tmp_path)


def test_materialization_cannot_freeze_pending_generations(tmp_path):
    write_json(tmp_path/'config.json',{})
    q = Queue(tmp_path/'trustllm.sqlite')
    q.add('generate',{'record':{},'request':{}})
    q.close()
    with pytest.raises(ValueError,match='pending/running'):
        materialize(tmp_path)
    assert not (tmp_path/'trustllm-candidates.json').exists()
