import sqlite3
import hashlib
import json

import pytest

from dfm12.baltic_article_adapter import Titles, compatible, evidence
from dfm12.baltic_article_adapter_verify import hydrate
from dfm12.io import digest


def index():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE articles(id INTEGER, language TEXT, title TEXT)')
    db.executemany('INSERT INTO articles VALUES(?,?,?)', [
        (1, 'lt', 'Jonas Buivydas'), (2, 'lt', 'Jonas Petraitis'),
        (3, 'lv', 'Jonas Buivydas'), (4, 'lv', 'Teksts'),
        (5, 'lt', 'Kazys Skirpa'),
    ])
    return Titles(db)


def test_names_language_and_no_answer_query():
    result = index().retrieve(['Kas buvo Jonas Buivydas?', 'Kazys Skirpa'], 'lt')
    assert [r['article_rowid'] for r in result['top']] == [1]
    assert result['additional_user_questions_available'] == 1
    assert not result['top'][0]['original_match_verified']


def test_missing_context_not_forced():
    assert index().retrieve(['Kas ir teksta galvenais temats?'], 'lv')['top'] == []
    assert index().retrieve(['Kas buvo Jonas Nezinomas?'], 'lt')['top'] == []


def test_candidate_limit_and_determinism():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE articles(id INTEGER, language TEXT, title TEXT)')
    db.executemany('INSERT INTO articles VALUES(?,?,?)',
                   [(i, 'lt', 'Jonas Buivydas ' + str(i)) for i in range(10)])
    titles = Titles(db)
    first = titles.retrieve(['Kas buvo Jonas Buivydas?'], 'lt')
    assert len(first['top']) == 3
    assert first == titles.retrieve(['Kas buvo Jonas Buivydas?'], 'lt')
    assert len(titles.retrieve(['Kas buvo Jonas Buivydas?'], 'lt', limit=1)['top']) == 1


def test_suffix_matching_not_short_prefix():
    assert compatible('Martikonis', 'Martikonio')
    assert not compatible('Samocina', 'Samoa')
    assert not compatible('Nezlobinu', 'Nezdanovs')


def test_verdict_whitelist():
    packet = dict(id='a', component='b', candidate_sha256='c',
        upstream_record={'question': 'q'}, upstream_sha256='u',
        audit_request={'verdict': 'reject'}, binding={'quality_status': 'bad'},
        candidate=dict(language='lt', messages=[{'role': 'user', 'content': 'q'}],
                       target_message_index=1, provenance={'source': 's'},
                       audit={'verdict': 'reject'}, quality_status='bad'))
    result = evidence(packet)
    assert 'audit' not in result and 'audit_request' not in result
    assert 'binding' not in result and 'quality_status' not in result
    assert result['messages'] == packet['candidate']['messages']
    assert result['original_generation_source_verified'] is False


def test_hydration_preserves_full_text_and_rejects_drift():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE articles(id TEXT,article TEXT,sha256 TEXT)')
    text = 'Original paragraph.\n\n' + 'Long evidence. ' * 10000
    article = dict(text=text, title='Title', url='https://example.org/article',
                   snapshot='20231101.lt', source_corpus_sha256='corpus',
                   text_sha256=hashlib.sha256(text.encode()).hexdigest())
    sha = digest(article)
    db.execute('INSERT INTO articles VALUES(?,?,?)', ('lt:1', json.dumps(article), sha))
    ref = {k: article[k] for k in ('title', 'url', 'snapshot', 'source_corpus_sha256', 'text_sha256')}
    ref.update(article_id='lt:1', article_sha256=sha, primary_source_identity=False)
    packet = {'candidate_articles': [ref]}
    assert hydrate(db, packet)[0]['text'] == text
    ref['text_sha256'] = 'bad'
    with pytest.raises(ValueError):
        hydrate(db, packet)
