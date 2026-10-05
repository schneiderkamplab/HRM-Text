"""Deterministic question-only Baltic article sidecars; no judge or consumer edits."""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sqlite3
import unicodedata

from .io import digest, file_hash, load, rows, write_json
from .latvian_p3_export import check

STOP = set('''kas ir yra ar par man apie vai ka ko kad kada kur kurs kuri kuru kuris kurie
koks kokia kokie kokios kokiu kodel kiek cik kads kada kadi kadu kam kuo kaip kas
pastasti pastastiet papasakok papasakokite ludzu prasau placiau plasak galvenais
galvenie galvena pagrindiniai pagrindines svarbiausi svarbiausias buvo buvojo bija
butu butu galima gali vari var veikia notiek nozime nozimes kodel kapec si sie
sis sia sios suo so sie siek tiek tai tas tie tuo to ta lai un bei su pie uz nuo
iki vai ne no per viena viens vin irgi isti dati datiem informacija veida veids
zinams zinoma raksturo raksturojiet apibudink apibudinkite kurio kurie kadas
kokius koki kokias kokio kam tieka izveido pastastit but galvenam'''.split())
STOP.update('teksts tekstu teksta teksts temats temu tema datu datos siskak sikak galvenokart'.split())


@lru_cache(maxsize=131072)
def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def words(text):
    return re.findall(r'[^\W_]+', text, re.UNICODE)


def stem(token):
    return normalize(token)[:4] if len(normalize(token)) >= 4 else normalize(token)


@lru_cache(maxsize=262144)
def compatible(a, b):
    a, b = normalize(a), normalize(b)
    if a == b: return True
    if min(len(a), len(b)) < 4: return False
    common = 0
    for x, y in zip(a, b):
        if x != y: break
        common += 1
    return common >= 4 and common >= max(len(a), len(b)) - 2


class Titles:
    def __init__(self, db):
        self.titles = {}; self.postings = defaultdict(set)
        for key, lang, title in db.execute('SELECT id,language,title FROM articles'):
            tokens = [w for w in words(normalize(title)) if w not in STOP]
            stems = set(stem(w) for w in tokens if len(w) >= 3)
            self.titles[key] = (lang, title, stems, tokens)
            for term in stems: self.postings[lang, term].add(key)

    def retrieve(self, questions, lang, limit=3):
        first = questions[0] if questions else ''
        tokens = [w for w in words(first) if normalize(w) not in STOP and
                  (len(w) >= 3 or w.isdigit() or (len(w) >= 2 and w.isupper()))]
        # Query bounds only; full original questions and articles remain in the evidence.
        tokens = tokens[:24]
        terms = set(stem(w) for w in tokens)
        entities = [w for w in tokens if w[0].isupper() and normalize(w) not in ('ii','iii','iv','xvi','xvii','xviii')]
        rare = sorted((s for s in terms if 0 < len(self.postings[lang, s]) <= 2000),
                      key=lambda s: (len(self.postings[lang, s]), s))[:8]
        candidates = set()
        for term in rare: candidates.update(self.postings[lang, term])
        ranked = []; question_words = set(words(normalize(first)))
        for key in candidates:
            _, title, title_terms, title_words = self.titles[key]
            matched = {stem(w) for w in tokens if any(compatible(w, t) for t in title_words)}
            entity_matches = {stem(w) for w in entities if any(compatible(w, t) for t in title_words)}
            if entities and len(entity_matches) < min(2, len(set(stem(w) for w in entities))):
                continue
            exact = normalize(title) in normalize(first) and set(words(normalize(title))) <= question_words
            if not (len(matched) >= 2 or exact or (entity_matches and len(title_terms) == 1)):
                continue
            score = sum(math.log(1 + len(self.titles) / max(1, len(self.postings[lang, s]))) for s in matched)
            score += 4 * len(entity_matches) + 8 * exact
            coverage = len(matched) / max(1, len(title_terms))
            score *= coverage
            ranked.append(dict(article_rowid=key, title=title, score=score,
                matched_stems=sorted(matched), title_token_coverage=coverage,
                question_token_coverage=len(matched) / max(1, len(terms)),
                exact_title_in_question=exact, entity_stems=sorted(entity_matches),
                relevance='lexical_candidate_unverified', original_match_verified=False))
        ranked.sort(key=lambda r: (-r['score'], r['title'], r['article_rowid']))
        return dict(question=first, query_tokens=tokens, query_stems=rare,
            method='question_only_title_entity_suffix2_v2', top=ranked[:limit],
            uncertainty='Prefix collisions, homonyms, inflection and absent articles are unresolved; scores are not probabilities',
            additional_user_questions_available=len(questions)-1)


def evidence(packet):
    candidate = packet['candidate']
    return dict(candidate_id=packet['id'], component=packet['component'],
        language=candidate['language'], messages=candidate['messages'],
        target_message_index=candidate['target_message_index'],
        provenance=candidate['provenance'], original_record_sha256=packet['candidate_sha256'],
        upstream_record=packet['upstream_record'], upstream_sha256=packet['upstream_sha256'],
        original_generation_source_verified=False)


def prepare(root, packet_root, article_root, diagnostic, sample=False, seed=20261004):
    root, packet_root, article_root = map(Path, (root, packet_root, article_root))
    root.mkdir(parents=True, exist_ok=True)
    source_path = packet_root / 'packets.sqlite'; index_path = article_root / 'articles.sqlite'
    source_manifest = load(packet_root / 'manifest.json')
    check(file_hash(source_path) == source_manifest['packets_sha256'], 'Source packets drift')
    check(file_hash(index_path) == load(article_root / 'manifest.json')['database_sha256'], 'Index drift')
    pins = dict(files={str(p): file_hash(p) for p in (Path(__file__), source_path, index_path, Path(diagnostic))},
                sample=sample, seed=seed, max_articles=3, schema='baltic-article-sidecar-v1')
    if (root / 'pins.json').exists(): check(load(root / 'pins.json') == pins, 'Resume pins changed')
    else: write_json(root / 'pins.json', pins)
    src = sqlite3.connect(f'file:{source_path}?mode=ro', uri=True)
    articles = sqlite3.connect(f'file:{index_path}?mode=ro', uri=True)
    out = sqlite3.connect(root / 'evidence.sqlite')
    out.executescript('''CREATE TABLE IF NOT EXISTS packets(id TEXT PRIMARY KEY,language TEXT,packet TEXT,sha256 TEXT);
      CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY,article TEXT,sha256 TEXT);''')
    try:
        title_index = Titles(articles)
        selection = None
        if sample:
            excluded = {r['candidate_id'] for r in rows(diagnostic)}
            rng = random.Random(seed); selection = set()
            for language in ('lt', 'lv'):
                ids = [r[0] for r in src.execute('SELECT id FROM packets WHERE component=? ORDER BY id', ('baltic_' + language + '_qa',)) if r[0] not in excluded]
                selection.update(rng.sample(ids, 25))
            write_json(root / 'selection.json', dict(seed=seed, per_language=25, excluded_diagnostic_ids=sorted(excluded), ids=sorted(selection)))
        processed = 0
        for key, encoded, sha, error in src.execute('SELECT id,packet,sha256,error FROM packets ORDER BY component,id'):
            if selection is not None and key not in selection: continue
            if out.execute('SELECT 1 FROM packets WHERE id=?', (key,)).fetchone(): continue
            check(not error, 'Input packet error: ' + key)
            packet = json.loads(encoded); check(digest(packet) == sha, 'Input row hash drift')
            clean = evidence(packet)
            questions = [m['content'] for m in clean['messages'] if m['role'] == 'user']
            retrieval = title_index.retrieve(questions, clean['language'])
            refs = []
            for hit in retrieval['top']:
                cursor = articles.execute('SELECT * FROM articles WHERE id=?', (hit['article_rowid'],))
                article = dict(zip([c[0] for c in cursor.description], cursor.fetchone()))
                check(hashlib.sha256(article['text'].encode()).hexdigest() == article['text_sha256'], 'Article text drift')
                article_key = article['source_document_id']; article_sha = digest(article)
                out.execute('INSERT OR IGNORE INTO articles VALUES(?,?,?)', (article_key, json.dumps(article, ensure_ascii=False), article_sha))
                refs.append(dict(article_id=article_key, article_sha256=article_sha, title=article['title'],
                    url=article['url'], snapshot=article['snapshot'], text_sha256=article['text_sha256'],
                    source_corpus_sha256=article['source_corpus_sha256'], primary_source_identity=False))
            clean.update(retrieval=retrieval, candidate_articles=refs,
                         source_packet_sha256=sha, article_storage='evidence.sqlite:articles',
                         review_verdicts_included=False, admission_authorized=False)
            out.execute('INSERT INTO packets VALUES(?,?,?,?)', (key, clean['language'], json.dumps(clean, ensure_ascii=False), digest(clean)))
            processed += 1
            if processed % 1000 == 0:
                out.commit(); print('Prepared', processed, flush=True)
                write_json(root / 'progress.json', dict(rows=out.execute('SELECT count(*) FROM packets').fetchone()[0], complete=False))
        out.commit()
        counts = dict(out.execute('SELECT language,count(*) FROM packets GROUP BY language'))
        expected = 50 if sample else 118866
        check(sum(counts.values()) == expected, 'Incomplete source inventory')
        hits = Counter()
        for encoded, in out.execute('SELECT packet FROM packets'):
            p = json.loads(encoded); hits[len(p['candidate_articles'])] += 1
        result = dict(schema='baltic-article-sidecar-v1', counts=counts, rows=expected,
            candidate_count_histogram=dict(hits), unique_articles=out.execute('SELECT count(*) FROM articles').fetchone()[0],
            input_pins_sha256=file_hash(root / 'pins.json'), original_sources_certified=0,
            model_calls=0, no_article_truncation=True, prior_review_verdicts_included=False,
            sample=sample, complete=True)
    finally:
        src.close(); articles.close(); out.close()
    result['database_sha256'] = file_hash(root / 'evidence.sqlite')
    write_json(root / 'manifest.json', result); write_json(root / 'progress.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    for k in ('root', 'packet-root', 'article-root', 'diagnostic'): p.add_argument('--'+k, required=True)
    p.add_argument('--sample', action='store_true'); p.add_argument('--seed', type=int, default=20261004)
    a = p.parse_args(); print(json.dumps(prepare(a.root, a.packet_root, a.article_root, a.diagnostic, a.sample, a.seed), indent=2))
