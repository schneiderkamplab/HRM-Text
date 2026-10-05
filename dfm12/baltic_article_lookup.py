"""CPU-only SQLite lookup over existing full Baltic article snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .io import atomic, digest, file_hash, load, rows, write_json
from .latvian_p3_export import check


def build(root, sources):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    dbpath = root / 'articles.sqlite'
    check(not dbpath.exists(), 'Use a new root; existing indexes are preserved')
    db = sqlite3.connect(dbpath)
    db.executescript('''CREATE TABLE articles (
      id INTEGER PRIMARY KEY, source_document_id TEXT, language TEXT, title TEXT,
      text TEXT, url TEXT, source_file TEXT, snapshot TEXT, source_record_sha256 TEXT,
      text_sha256 TEXT, source_corpus_sha256 TEXT);
      CREATE UNIQUE INDEX article_identity ON articles(language, source_document_id);
      CREATE VIRTUAL TABLE search USING fts5(title,text,content='articles',content_rowid='id',
        tokenize='unicode61 remove_diacritics 2');''')
    inventory = []
    try:
        for source in load(sources):
            if source['name'] not in ('Wikipedia_lt', 'Wikipedia_lv'): continue
            sha = hashlib.sha256(); count = 0
            with open(source['path'], 'rb') as stream:
                for raw in stream:
                    sha.update(raw); row = json.loads(raw)
                    cursor = db.execute('INSERT INTO articles VALUES(NULL,?,?,?,?,?,?,?,?,?,?)', (
                        row['source_document_id'], row['language'], row['title'], row['text'], row['url'],
                        row['source_file'], row['source_file'].split('/')[0],
                        hashlib.sha256(raw).hexdigest(), hashlib.sha256(row['text'].encode()).hexdigest(), source['sha256']))
                    db.execute('INSERT INTO search(rowid,title,text) VALUES(?,?,?)',
                               (cursor.lastrowid, row['title'], row['text']))
                    count += 1
                    if count % 2000 == 0: db.commit()
            check(sha.hexdigest() == source['sha256'], 'Source changed: ' + source['path'])
            db.commit(); inventory.append(dict(path=source['path'], sha256=sha.hexdigest(), rows=count))
            print(source['name'], count, flush=True)
        check(len(inventory) == 2, 'Expected both LT/LV article corpora')
        db.execute("INSERT INTO search(search) VALUES('integrity-check')"); db.commit()
    finally:
        db.close()
    result = dict(schema='baltic-local-article-index-v1', sources=inventory,
        source_manifest=str(sources), source_manifest_sha256=file_hash(sources),
        database_sha256=file_hash(dbpath), builder_sha256=file_hash(__file__),
        original_generation_source_verified=False, network_calls=0)
    write_json(root / 'manifest.json', result)
    return result


def query(db, language, terms, title_only=True, limit=5):
    tokens = re.findall(r'[^\W_]+', terms, re.UNICODE)
    check(tokens and 1 <= limit <= 20, 'Empty query or unbounded result limit')
    expression = ' AND '.join('"' + t.replace('"', '""') + '"*' for t in tokens)
    if title_only: expression = 'title:(' + expression + ')'
    db.row_factory = sqlite3.Row
    ordering = 'length(a.title),score,a.source_document_id' if title_only else 'score,a.source_document_id'
    result = db.execute('''SELECT a.*,bm25(search,10,1) score FROM search
      JOIN articles a ON a.id=search.rowid WHERE search MATCH ? AND a.language=?
      ORDER BY ''' + ordering + ' LIMIT ?', (expression, language, limit)).fetchall()
    return [dict(r) for r in result]


def pilot(root, packet_path, query_path):
    root = Path(root); manifest = load(root / 'manifest.json')
    check(file_hash(root / 'articles.sqlite') == manifest['database_sha256'], 'Index drift')
    packets = [r['packet'] for r in rows(packet_path)]; specs = load(query_path)
    check(len(specs) == len(packets) == 20, 'Expected diagnostic20')
    output = root / 'pilot-v2'; output.mkdir(exist_ok=True)
    db = sqlite3.connect(f'file:{root / "articles.sqlite"}?mode=ro', uri=True)
    entries = []
    try:
        for i, (packet, spec) in enumerate(zip(packets, specs)):
            found = {}; executed = []
            for terms, title_only in spec['queries']:
                hits = query(db, packet['language'], terms, title_only)
                executed.append(dict(terms=terms, title_only=title_only, ids=[h['source_document_id'] for h in hits]))
                for hit in hits:
                    hit.pop('score')  # Query-specific scores must not change shared article attachments.
                    key = digest([hit['language'], hit['source_document_id']])
                    path = output / 'articles' / (key + '.json')
                    write_json(path, hit)
                    found[key] = dict(path=str(path), sha256=file_hash(path),
                        source_document_id=hit['source_document_id'], title=hit['title'],
                        url=hit['url'], snapshot=hit['snapshot'], text_sha256=hit['text_sha256'],
                        source_corpus_sha256=hit['source_corpus_sha256'], original_match_verified=False)
            entries.append(dict(case=i, candidate_id=packet['candidate_id'], packet=packet,
                queries=executed, articles=list(found.values()), retrieval_status='candidates_only',
                original_generation_source_verified=False))
        with atomic(output / 'packets.jsonl') as out:
            for entry in entries: out.write(json.dumps(entry, ensure_ascii=False) + '\n')
        receipt = dict(cases=len(entries), cases_with_candidates=sum(bool(e['articles']) for e in entries),
            references=sum(len(e['articles']) for e in entries),
            packets_sha256=file_hash(output / 'packets.jsonl'), input_packets_sha256=file_hash(packet_path),
            query_spec_sha256=file_hash(query_path), index_manifest_sha256=file_hash(root / 'manifest.json'),
            lookup_code_sha256=file_hash(__file__),
            truncation=False, original_matches_certified=0, model_calls=0)
        write_json(output / 'receipt.json', receipt); return receipt
    finally:
        db.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__); sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('build'); a.add_argument('--root', required=True); a.add_argument('--sources', required=True)
    a = sub.add_parser('pilot'); a.add_argument('--root', required=True)
    a.add_argument('--packets', required=True); a.add_argument('--queries', required=True)
    a = p.parse_args()
    print(json.dumps(build(a.root, a.sources) if a.command == 'build' else pilot(a.root, a.packets, a.queries), indent=2))
