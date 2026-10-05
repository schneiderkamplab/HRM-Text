"""Verify and hydrate an article sidecar without changing source/consumer files."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from .io import digest, file_hash, load, write_json
from .latvian_p3_export import check


def hydrate(db, packet):
    result = []
    for ref in packet['candidate_articles']:
        row = db.execute('SELECT article,sha256 FROM articles WHERE id=?',
                         (ref['article_id'],)).fetchone()
        check(row is not None, 'Missing article')
        article = json.loads(row[0])
        check(digest(article) == row[1] == ref['article_sha256'], 'Article hash drift')
        check(hashlib.sha256(article['text'].encode()).hexdigest() == ref['text_sha256']
              == article['text_sha256'], 'Article text drift')
        for field in ('title', 'url', 'snapshot', 'source_corpus_sha256'):
            check(ref[field] == article[field], 'Article reference drift: ' + field)
        check(ref['primary_source_identity'] is False, 'Identity certification forbidden')
        result.append(article)
    return result


def verify(root, source_root):
    root, source_root = Path(root), Path(source_root)
    manifest = load(root / 'manifest.json')
    check(file_hash(root / 'evidence.sqlite') == manifest['database_sha256'], 'Sidecar drift')
    pins = load(root / 'pins.json')
    check(file_hash(root / 'pins.json') == manifest['input_pins_sha256'], 'Pin receipt drift')
    source_path = source_root / 'packets.sqlite'
    check(file_hash(source_path) == pins['files'][str(source_path)], 'Source drift')
    counts, hist = Counter(), Counter()
    db = sqlite3.connect(f'file:{root / "evidence.sqlite"}?mode=ro', uri=True)
    src = sqlite3.connect(f'file:{source_path}?mode=ro', uri=True)
    index_path = next(p for p in pins['files'] if Path(p).name == 'articles.sqlite')
    check(file_hash(index_path) == pins['files'][index_path], 'Index drift')
    index = sqlite3.connect(f'file:{index_path}?mode=ro', uri=True)
    try:
        check(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity')
        for key, encoded, sha in db.execute('SELECT * FROM articles'):
            article = json.loads(encoded)
            check(key == article['source_document_id'] and digest(article) == sha, 'Stored article drift')
            cursor = index.execute('SELECT * FROM articles WHERE id=?', (article['id'],))
            original = dict(zip([c[0] for c in cursor.description], cursor.fetchone()))
            check(original == article, 'Full indexed article changed')
        for key, lang, encoded, sha in db.execute('SELECT * FROM packets'):
            packet = json.loads(encoded)
            check(digest(packet) == sha, 'Packet drift')
            original, original_sha = src.execute('SELECT packet,sha256 FROM packets WHERE component=? AND id=?',
                (packet['component'], key)).fetchone()
            original = json.loads(original)
            check(digest(original) == original_sha == packet['source_packet_sha256'], 'Source binding drift')
            for field in ('messages', 'language', 'target_message_index', 'provenance'):
                check(packet[field] == original['candidate'][field], 'Candidate changed: ' + field)
            check(packet['upstream_record'] == original['upstream_record'], 'Upstream changed')
            check(not set(packet) & {'audit', 'audit_request', 'binding', 'quality_status', 'audit_status'}, 'Verdict leakage')
            check(packet['original_generation_source_verified'] is False and
                  packet['review_verdicts_included'] is False and
                  packet['admission_authorized'] is False, 'Admission/identity drift')
            articles = hydrate(db, packet)
            check(len(articles) <= 3, 'Article count bound')
            check(all(a['language'] == lang for a in articles), 'Cross-language evidence')
            counts[lang] += 1; hist[len(articles)] += 1
        check(dict(counts) == manifest['counts'], 'Row counts')
        check(sum(counts.values()) == manifest['rows'], 'Total count')
    finally:
        db.close(); src.close(); index.close()
    result = dict(rows=sum(counts.values()), counts=dict(counts), candidate_count_histogram=dict(hist),
        database_sha256=manifest['database_sha256'], manifest_sha256=file_hash(root / 'manifest.json'),
        verifier_sha256=file_hash(Path(__file__)),
        full_article_hashes_verified=True, source_messages_unchanged=True,
        review_labels_excluded=True, primary_sources_certified=0, admission_authorized=False)
    write_json(root / 'verification.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--source-root', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.source_root), indent=2))
