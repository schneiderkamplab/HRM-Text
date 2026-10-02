"""Isolated, incremental CPU seed inventory for twelve European languages."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import random
import sqlite3

from .catalog import selected_source
from .european_expansion import NEW
from .european_texts import corege_allowed
from .io import digest, file_hash, load, lock, rows
from . import multilingual_production_seeds as shared

VERSION = 'european-synthetic-seeds-v1'
LANGUAGES = dict(NEW)
DEFAULT_SOURCE = Path('data/dfm12/european-expansion-20260926')
DEFAULT_OH = Path('data/dfm11_source_cache/dfm8-openhermes-en')


def connect(root):
    db = sqlite3.connect(Path(root) / 'seeds.sqlite', timeout=60)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript(shared.SCHEMA)
    db.executemany('INSERT OR IGNORE INTO languages VALUES (?)', [(lang,) for lang in LANGUAGES])
    db.commit()
    return db


def native_payload(row, source, language, relative, group, ordinal, sha, seed):
    if language == 'pt_pt':
        if source.get('review_receipt', {}).get('document_filter') != 'corege_pt':
            raise ValueError('pt-PT requires its pinned document-level approval')
        if not corege_allowed(row):
            return None, 'variant_or_rights'
    text = row.get('text')
    identity = dict(repo=source['repo'], revision=source['revision'], file=relative,
        row_group=group, row_in_group=ordinal, source_id=row.get('id', row.get('dc.identifier.uri')))
    key = shared.doc_keys(identity)[0]
    window = shared.native_window(text, f'{seed}/{language}/{key}')
    if window is None:
        return None, 'no_full_window'
    selected, offset = window
    payload = dict(identity, id=digest([language, selected]), text=selected, offset=offset,
        language=language, document_sha256=digest(text), file_sha256=sha,
        document_url=row.get('url', row.get('dc.identifier.uri')),
        title=row.get('title'), preparation_version=VERSION,
        rights_basis='Inherited pinned European expansion source policy; attribution retained',
        document_rights=row.get('dc.rights.uri') if language == 'pt_pt' else 'Wikipedia source attribution/licenses retained',
        paragraph_boundaries_claimed=False, generation_and_review_required=True)
    return payload, None


def oh_payload(row, path, ordinal, sha):
    if row.get('language') != 'en' or row.get('source') != 'dfm8_openhermes_en':
        return None, 'not_repaired_english_source'
    messages = shared.eligible_openhermes(row)
    if messages is None:
        return None, 'ineligible_conversation'
    key = digest(messages)
    return dict(id=key, messages=messages, language='en', repo='schneiderkamplab/dfm8-openhermes-en',
        file=str(path), ordinal=ordinal, file_sha256=sha, preparation_version=VERSION,
        source_metadata={k:v for k,v in row.items() if k not in ('messages','tools')},
        generation_and_review_required=True), None


def schedule(db, data_root, oh_root, seed):
    import pyarrow.parquet as pq
    sources = {}
    shared.pin(db, data_root / 'sources.lock.json', 'European catalog')
    for language in LANGUAGES:
        name = 'text-' + language
        source = selected_source(data_root, name)
        if source['kind'] != 'documents' or source.get('language') != language:
            raise ValueError('Wrong native source mapping')
        if language != 'pt_pt' and source['repo'] != 'wikimedia/wikipedia':
            raise ValueError('Unexpected native source; review separately')
        approval = data_root / 'approvals' / (name + '.json')
        if approval.exists():
            shared.pin(db, approval, 'source approval')
        sources[language] = source
        tasks = []
        for relative in source['files']:
            path = (data_root / 'downloads' / name / relative).resolve()
            if not path.is_relative_to((data_root / 'downloads' / name).resolve()):
                raise ValueError('Unsafe source path')
            parquet = pq.ParquetFile(path)
            tasks.extend((language, str(path), group) for group in range(parquet.num_row_groups))
        random.Random(f'{seed}/{language}').shuffle(tasks)
        db.executemany('INSERT OR IGNORE INTO tasks(pool,path,row_group) VALUES (?,?,?)', tasks)
        db.commit()
    shared.pin(db, oh_root / 'README.md', 'repaired English OpenHermes source description')
    paths = sorted((oh_root / 'data').glob('train-*.jsonl.gz'))
    if not paths:
        raise ValueError('No repaired English OpenHermes training shards')
    random.Random(f'{seed}/openhermes').shuffle(paths)
    db.executemany('INSERT OR IGNORE INTO tasks(pool,path,row_group) VALUES (?,?,0)',
        [('openhermes', str(p.resolve())) for p in paths])
    db.commit()
    return sources


def stream(path, group, start, batch_size, pool):
    if pool == 'openhermes':
        for ordinal, row in enumerate(rows(path)):
            if ordinal >= start:
                yield ordinal, row
        return
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    wanted = ('id', 'text', 'url', 'title', 'pt.auto', 'pt.pt.auto',
        'pt.mean.confidence.auto', 'pt.pt.mean.confidence.auto', 'dc.rights.uri', 'dc.identifier.uri')
    columns = [k for k in wanted if k in parquet.schema_arrow.names]
    ordinal = 0
    for batch in parquet.iter_batches(batch_size=batch_size, row_groups=[group], columns=columns, use_threads=False):
        if ordinal + batch.num_rows <= start:
            ordinal += batch.num_rows
            continue
        for index in range(batch.num_rows):
            if ordinal >= start:
                yield ordinal, batch.slice(index, 1).to_pylist()[0]
            ordinal += 1


def prepare(root, data_root=DEFAULT_SOURCE, oh_root=DEFAULT_OH, native_target=60000,
            oh_target=30000, batch_size=32, seed=20260928, max_rows=None):
    root, data_root, oh_root = [Path(p).resolve() for p in (root, data_root, oh_root)]
    if not 1 <= batch_size <= 256 or min(native_target, oh_target) < 1 or (max_rows is not None and max_rows < 1):
        raise ValueError('Invalid bounded preparation parameters')
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.prepare.lock'), closing(connect(root)) as db:
        manifest = dict(version=VERSION, data_root=str(data_root), oh_root=str(oh_root),
            native_target=native_target, oh_target=oh_target, batch_size=batch_size, seed=seed,
            implementation_sha256=file_hash(__file__), schema_sha256=digest(shared.SCHEMA),
            helper_sha256=file_hash(shared.__file__), languages=LANGUAGES,
            prior_target_language_campaigns=[], accepted_generation_quotas_not_seed_counts=True)
        old = db.execute("SELECT value FROM build_state WHERE key='manifest'").fetchone()
        if old and json.loads(old[0]) != manifest:
            raise ValueError('Preparation configuration drift; use a separate root')
        for path, size, mtime in db.execute('SELECT path,size,mtime_ns FROM inputs'):
            stat = Path(path).stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise ValueError('Pinned source changed: ' + path)
        shared.state(db, 'manifest', manifest)
        shared.state(db, 'phase', 'scheduling')
        db.commit()
        sources = schedule(db, data_root, oh_root, seed)
        counts = Counter(dict(db.execute('SELECT pool,count(*) FROM seeds GROUP BY pool')))
        targets = {**{lang:native_target for lang in LANGUAGES}, 'openhermes':oh_target}
        active, scanned, stats = {}, 0, Counter()
        try:
            while True:
                progressed = False
                for pool, target in targets.items():
                    if counts[pool] >= target:
                        continue
                    if pool not in active:
                        task = db.execute('SELECT path,row_group,cursor FROM tasks WHERE pool=? AND exhausted=0 ORDER BY rowid LIMIT 1', (pool,)).fetchone()
                        if not task:
                            continue
                        path, group, cursor = task
                        sha = shared.pin(db, path, 'English repaired OH' if pool == 'openhermes' else 'pinned native document shard')
                        active[pool] = (path, group, sha, stream(path, group, cursor, batch_size, pool))
                    path, group, sha, iterator = active[pool]
                    progressed = True
                    for _ in range(batch_size):
                        try:
                            ordinal, row = next(iterator)
                        except StopIteration:
                            db.execute('UPDATE tasks SET exhausted=1 WHERE pool=? AND path=? AND row_group=?', (pool, path, group))
                            del active[pool]
                            break
                        scanned += 1
                        stats[pool + '/scanned'] += 1
                        if pool == 'openhermes':
                            payload, reason = oh_payload(row, path, ordinal, sha)
                        else:
                            relative = str(Path(path).relative_to(data_root / 'downloads' / ('text-' + pool)))
                            payload, reason = native_payload(row, sources[pool], pool, relative, group, ordinal, sha, seed)
                        if payload is not None:
                            key = payload['id'] if pool == 'openhermes' else shared.doc_keys(payload)[0]
                            content = payload['id'] if pool == 'openhermes' else digest(' '.join(payload['text'].split()))
                            if shared.insert(db, pool, payload, key, content):
                                counts[pool] += 1
                            else:
                                stats[pool + '/duplicate'] += 1
                        else:
                            stats[pool + '/' + reason] += 1
                        db.execute('UPDATE tasks SET cursor=? WHERE pool=? AND path=? AND row_group=?', (ordinal+1, pool, path, group))
                        if counts[pool] >= target or (max_rows is not None and scanned >= max_rows):
                            break
                    shared.state(db, pool, dict(count=counts[pool], target=target, shortfall=max(0,target-counts[pool])))
                    shared.state(db, 'phase', 'building')
                    shared.state(db, 'last_invocation_stats', dict(stats))
                    db.commit()
                    if max_rows is not None and scanned >= max_rows:
                        shared.state(db, 'phase', 'paused_at_scan_bound')
                        db.commit()
                        return status(root)
                if not progressed:
                    break
            shared.state(db, 'phase', 'complete_with_reported_shortfalls' if any(counts[p] < t for p,t in targets.items()) else 'complete')
            db.commit()
        finally:
            for _, _, _, iterator in active.values():
                iterator.close()
    return status(root)


def status(root):
    with closing(sqlite3.connect(Path(root).resolve().joinpath('seeds.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
        return dict(counts=dict(db.execute('SELECT pool,count(*) FROM seeds GROUP BY pool')),
            state={k:json.loads(v) for k,v in db.execute('SELECT key,value FROM build_state')},
            inputs=db.execute('SELECT count(*) FROM inputs').fetchone()[0],
            generation_launched=False, training_admitted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','status'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--oh-root', type=Path, default=DEFAULT_OH)
    parser.add_argument('--native-target', type=int, default=60000)
    parser.add_argument('--oh-target', type=int, default=30000)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20260928)
    parser.add_argument('--max-rows', type=int)
    args = vars(parser.parse_args())
    action = args.pop('action')
    print(json.dumps(status(args['root']) if action == 'status' else prepare(**args), indent=2))
