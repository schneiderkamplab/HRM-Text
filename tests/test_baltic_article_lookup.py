import sqlite3
import json
import pytest
from dfm12.baltic_article_lookup import build, query
from dfm12.io import file_hash


def test_fts_language_full_text_and_prefix():
    db = sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE articles(id INTEGER PRIMARY KEY,source_document_id,language,title,text);'
        "CREATE VIRTUAL TABLE search USING fts5(title,text,content='articles',content_rowid='id');")
    text = 'complete evidence ' * 2000
    for i, language in enumerate(['lv', 'lt'], 1):
        db.execute('INSERT INTO articles VALUES(?,?,?,?,?)', (i, str(i), language, 'Distinct Entity', text))
        db.execute('INSERT INTO search(rowid,title,text) VALUES(?,?,?)', (i, 'Distinct Entity', text))
    hits = query(db, 'lv', 'Dist Ent')
    assert len(hits) == 1 and hits[0]['text'] == text
    assert not query(db, 'lv', 'evidence', title_only=True)
    assert query(db, 'lv', 'evidence', title_only=False)
    with pytest.raises(ValueError): query(db, 'lv', '---')
    db.close()


def test_build_pins_sources_and_preserves_article(tmp_path):
    sources = []
    for language in ('lt', 'lv'):
        path = tmp_path / (language + '.jsonl')
        path.write_text(json.dumps(dict(source_document_id=language + ':1', language=language,
            title='Entity', text='full article evidence', url='https://example.invalid/article',
            source_file='20231101.' + language + '/train.parquet')) + '\n')
        sources.append(dict(name='Wikipedia_' + language, path=str(path), sha256=file_hash(path)))
    source_path = tmp_path / 'sources.json'; source_path.write_text(json.dumps(sources))
    root = tmp_path / 'index'; receipt = build(root, source_path)
    assert sum(s['rows'] for s in receipt['sources']) == 2
    with sqlite3.connect(root / 'articles.sqlite') as db:
        hit = query(db, 'lv', 'Entity')[0]
        assert hit['snapshot'] == '20231101.lv'
        assert hit['text'] == 'full article evidence'
        assert hit['source_corpus_sha256'] == sources[1]['sha256']
    with pytest.raises(ValueError): build(root, source_path)
    sources[0]['sha256'] = 'wrong'; source_path.write_text(json.dumps(sources))
    with pytest.raises(ValueError, match='Source changed'): build(tmp_path / 'bad', source_path)
    assert not (tmp_path / 'bad/manifest.json').exists()
