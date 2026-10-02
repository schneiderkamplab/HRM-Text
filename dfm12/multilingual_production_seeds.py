"""CPU-only, incremental SQLite source preparation; never admission or sampling."""
import argparse
from bisect import bisect_right
from collections import Counter, deque
import json
import math
from pathlib import Path
import random
import re
import sqlite3

from .catalog import selected_source
from .io import digest, file_hash, load, lock, rows
from .multilingual_generation_v4 import _pairs
from .multilingual_seeds import LANGUAGES

VERSION = 'production-seeds-v1'
TARGETS = dict(nb=250000, nn=250000, **{'is': 250000}, fo=250000,
               nl=125000, sv=125000, pl=125000, openhermes=500000)
SCHEMA = '''
CREATE TABLE IF NOT EXISTS seeds (
 pool TEXT NOT NULL, seq INTEGER NOT NULL, source_id TEXT NOT NULL,
 payload TEXT NOT NULL,
 PRIMARY KEY(pool,seq), UNIQUE(pool,source_id));
CREATE TABLE IF NOT EXISTS documents (
 pool TEXT NOT NULL, doc_key TEXT NOT NULL, content_hash TEXT NOT NULL,
 PRIMARY KEY(pool,doc_key), UNIQUE(pool,content_hash));
CREATE TABLE IF NOT EXISTS exclusions (
 pool TEXT NOT NULL, language TEXT NOT NULL, key_type TEXT NOT NULL,
 value TEXT NOT NULL, PRIMARY KEY(pool,language,key_type,value));
CREATE INDEX IF NOT EXISTS exclusions_lookup ON exclusions(pool,key_type,value);
CREATE TABLE IF NOT EXISTS inputs (
 path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
 mtime_ns INTEGER NOT NULL, purpose TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS build_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (
 pool TEXT NOT NULL, path TEXT NOT NULL, row_group INTEGER NOT NULL,
 cursor INTEGER NOT NULL DEFAULT 0, exhausted INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(pool,path,row_group));
CREATE TABLE IF NOT EXISTS languages (language TEXT PRIMARY KEY);
CREATE VIEW IF NOT EXISTS available_seeds AS
 SELECT pool AS language,pool,seq,source_id,payload FROM seeds WHERE pool!='openhermes'
 UNION ALL
 SELECT l.language,s.pool,s.seq,s.source_id,s.payload FROM seeds s CROSS JOIN languages l
 WHERE s.pool='openhermes' AND NOT EXISTS (
 SELECT 1 FROM exclusions e WHERE e.pool='openhermes'
 AND e.language IN (l.language,'*') AND e.key_type='id' AND e.value=s.source_id);
'''


def connect(root):
    db = sqlite3.connect(Path(root) / 'seeds.sqlite', timeout=60)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript(SCHEMA)
    db.executemany('INSERT OR IGNORE INTO languages VALUES (?)', [(k,) for k in LANGUAGES])
    db.commit()
    return db


def state(db, key, value):
    db.execute('INSERT OR REPLACE INTO build_state VALUES (?,?)', (key, json.dumps(value)))


def pin(db, path, purpose):
    path = Path(path).resolve()
    stat = path.stat()
    prior = db.execute('SELECT sha256,size,mtime_ns FROM inputs WHERE path=?', (str(path),)).fetchone()
    if prior:
        if (stat.st_size, stat.st_mtime_ns) != prior[1:]:
            raise ValueError('Input changed: ' + str(path))
        return prior[0]
    sha = file_hash(path)
    after = path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Input changed while hashing: ' + str(path))
    db.execute('INSERT INTO inputs VALUES (?,?,?,?,?)',
               (str(path), sha, stat.st_size, stat.st_mtime_ns, purpose))
    db.commit()
    return sha


def doc_keys(source):
    result = []
    repo = source.get('repo')
    if source.get('source_id') is not None:
        result.append('id:' + digest([repo, source['source_id']]))
    if all(key in source for key in ('file', 'row_group', 'row_in_group')):
        result.append('row:' + digest([repo, source['file'], source['row_group'], source['row_in_group']]))
    return result


def exclude(db, spec):
    spec = spec.get('spec', spec.get('provenance', spec))
    source = spec.get('source')
    if not isinstance(source, dict):
        return
    language = spec.get('language_code', spec.get('language'))
    if language not in LANGUAGES:
        raise ValueError('Unknown prior source language')
    oh = spec.get('family') == 'openhermes'
    if not source.get('id'):
        raise ValueError('Prior source without seed id')
    values = [('openhermes' if oh else 'native', language if oh else '*', 'id', source['id'])]
    if not oh:
        values += [('native', '*', 'doc', key) for key in doc_keys(source)]
    db.executemany('INSERT OR IGNORE INTO exclusions VALUES (?,?,?,?)', values)


def json_items(path):
    import ijson
    with Path(path).open('rb') as stream:
        first = next((b for b in iter(lambda: stream.read(1), b'') if not b.isspace()), b'')
        stream.seek(0)
        if first == b'[':
            yield from ijson.items(stream, 'item', use_float=True)
        elif first == b'{':
            for _, value in ijson.kvitems(stream, '', use_float=True):
                if isinstance(value, dict):
                    yield value
        else:
            raise ValueError('Unsupported specifications file: ' + str(path))


def import_prior(db, previous):
    """Reserve attempted slots too, not just successes; no old pool regeneration."""
    from .multilingual_tasks import spec_for
    for root in previous:
        root = Path(root)
        if not root.exists():
            raise FileNotFoundError(root)
        found = False
        for name in ('specifications.json', 'slot-specifications.json'):
            path = root / name
            if path.exists():
                found = True
                pin(db, path, 'prior_specifications')
                for n, spec in enumerate(json_items(path)):
                    exclude(db, spec)
                    if n % 1000 == 0:
                        db.commit()
        path = root / 'pilot.sqlite'
        if path.exists():
            found = True
            # Caller must provide quiescent legacy roots; snapshot is read-only.
            with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as old:
                old.execute('BEGIN')
                tables = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'slots' not in tables:
                    raise ValueError('Unsupported prior pilot schema')
                config = load(root / 'pilot-config.json') if (root / 'pilot-config.json').exists() else {}
                pools = {}
                for language, family, slot in old.execute('SELECT language,family,slot FROM slots'):
                    needed = 'openhermes' if family == 'openhermes' else language
                    if needed not in pools:
                        seed_path = root / f'seeds-{needed}.json'
                        pin(db, seed_path, 'prior_seed_pool')
                        pools[needed] = load(seed_path)
                    exclude(db, spec_for(language, family, slot, 0, pools, config))
                for (payload,) in old.execute('SELECT candidate FROM slots WHERE candidate IS NOT NULL'):
                    exclude(db, json.loads(payload))
                if 'events' in tables:
                    for (payload,) in old.execute("SELECT json_extract(detail,'$.candidate') FROM events WHERE json_extract(detail,'$.candidate') IS NOT NULL"):
                        exclude(db, json.loads(payload))
                state(db, 'prior_sqlite:' + str(path.resolve()), dict(
                    slots=old.execute('SELECT count(*) FROM slots').fetchone()[0],
                    exclusion_snapshot=True))
        if not found:
            raise ValueError('No source specifications or supported pilot DB: ' + str(root))
        db.commit()


def native_window(text, seed):
    if not isinstance(text, str) or not 500 <= len(text) <= 2000000:
        return None
    boundaries = [0] + [m.end() for m in re.finditer(r'(?:[.!?][\"\u201d\u2019\)]*\s+|\n+)', text)] + [len(text)]
    starts = list(dict.fromkeys(boundaries[:-1]))
    random.Random(str(seed)).shuffle(starts)
    for start in starts:
        end = boundaries[bisect_right(boundaries, start + 2400) - 1]
        raw = text[start:end]
        trimmed = raw.strip()
        if 500 <= len(trimmed) <= 2400:
            offset = start + len(raw) - len(raw.lstrip())
            return trimmed, offset
    return None


def eligible_openhermes(row):
    messages = row.get('messages')
    if row.get('tools') or not isinstance(messages, list):
        return None
    spec = dict(contract_version=4, family='openhermes', subtype='translate', source={'messages': messages})
    try:
        _pairs(spec)
    except (ValueError, TypeError, KeyError):
        return None
    if (sum(len(m['content']) for m in messages) > 7000
            or any(not m['content'].strip() or len(m['content']) > (900 if m['role'] == 'user' else 2400)
                   for m in messages)):
        return None
    return messages


def insert(db, pool, payload, doc_key, content_hash):
    source_id = payload['id']
    if pool != 'openhermes':
        keys = doc_keys(payload)
        if db.execute("SELECT 1 FROM exclusions WHERE pool='native' AND key_type='id' AND value=?", (source_id,)).fetchone():
            return False
        for key in keys:
            if db.execute("SELECT 1 FROM exclusions WHERE pool='native' AND key_type='doc' AND value=?", (key,)).fetchone():
                return False
    elif db.execute("SELECT 1 FROM exclusions WHERE pool='openhermes' AND key_type='id' AND value=?", (source_id,)).fetchone():
        return False  # Conservative cross-language exclusion for direct pool readers.
    if db.execute('SELECT 1 FROM seeds WHERE pool=? AND source_id=?', (pool, source_id)).fetchone():
        return False
    cursor = db.execute('INSERT OR IGNORE INTO documents VALUES (?,?,?)', (pool, doc_key, content_hash))
    if not cursor.rowcount:
        return False
    seq = db.execute('SELECT coalesce(max(seq)+1,1) FROM seeds WHERE pool=?', (pool,)).fetchone()[0]
    cursor = db.execute('INSERT INTO seeds VALUES (?,?,?,?)',
        (pool, seq, source_id, json.dumps(payload, ensure_ascii=False)))
    return cursor.rowcount == 1


def native_tasks(db, data_root, language, seed):
    import pyarrow.parquet as pq
    name = 'dynaword-' + ('no' if language in ('nb', 'nn') else language)
    source = selected_source(data_root, name)
    files = source['files']
    if language in ('nb', 'nn'):
        mapping = source['review_receipt']['language_by_file']
        files = [f for f in files if mapping.get(f) == language]
    rng = random.Random(f'{seed}/{language}/files')
    files = sorted(files)
    rng.shuffle(files)
    queues = []
    for relative in files:
        path = data_root / 'downloads' / name / relative
        if path.suffix != '.parquet':
            continue
        if not path.exists():
            raise FileNotFoundError(path)
        count = pq.ParquetFile(path).num_row_groups
        groups = list(range(count))
        rng.shuffle(groups)
        queues.append(deque((relative, str(path.resolve()), group) for group in groups))
    schedule = []
    while any(queues):
        for queue in queues:
            if queue:
                schedule.append(queue.popleft())
    db.executemany('INSERT OR IGNORE INTO tasks(pool,path,row_group) VALUES (?,?,?)',
                   [(language, path, group) for _, path, group in schedule])
    db.commit()
    return source, schedule


def build_native(db, data_root, language, target, seed, batch_size):
    import pyarrow.parquet as pq
    source, schedule = native_tasks(db, data_root, language, seed)
    quota = max(1, math.ceil(target / max(1, len(schedule))))
    count = db.execute('SELECT count(*) FROM seeds WHERE pool=?', (language,)).fetchone()[0]
    stats = Counter()
    # First cover all file/row-group strata, then continue unconsumed groups once.
    for sweep in range(2):
        for relative, path, group in schedule:
            if count >= target:
                break
            start, exhausted = db.execute('SELECT cursor,exhausted FROM tasks WHERE pool=? AND path=? AND row_group=?',
                                          (language, path, group)).fetchone()
            if exhausted:
                continue
            sha = pin(db, path, 'native_parquet')
            parquet = pq.ParquetFile(path)
            columns = [c for c in ('id', 'text', 'source') if c in parquet.schema_arrow.names]
            scanned, kept, hit_cap = 0, 0, False
            for batch in parquet.iter_batches(batch_size=batch_size, row_groups=[group], columns=columns, use_threads=False):
                size = batch.num_rows
                if scanned + size <= start:
                    scanned += size
                    continue
                batch_rows = batch.to_pylist()
                order = list(range(size))
                random.Random(f'{seed}/{language}/{relative}/{group}/{scanned}').shuffle(order)
                processed = 0
                for position, index in enumerate(order):
                    processed = position + 1
                    if scanned + position < start:
                        continue
                    row = batch_rows[index]
                    stats['scanned'] += 1
                    identity = dict(repo=source['repo'], file=relative, row_group=group,
                                    row_in_group=scanned + index, source_id=row.get('id'))
                    keys = doc_keys(identity)
                    window = native_window(row.get('text'), f'{seed}/{keys[0]}')
                    if window is None:
                        stats['no_full_window'] += 1
                        continue
                    text, offset = window
                    payload = dict(identity, id=digest(text), text=text, offset=offset,
                        revision=source['revision'], file_sha256=sha, document_sha256=digest(row['text']),
                        source_label=row.get('source'), preparation_version=VERSION)
                    if count < target and insert(db, language, payload, keys[0], digest(text)):
                        count += 1
                        kept += 1
                    if count >= target or (sweep == 0 and kept >= quota):
                        hit_cap = True
                        break
                scanned += processed
                db.execute('UPDATE tasks SET cursor=? WHERE pool=? AND path=? AND row_group=?',
                           (scanned, language, path, group))
                state(db, language, dict(status='building', count=count, target=target, stats=dict(stats)))
                db.commit()
                if hit_cap:
                    break
            if not hit_cap:
                db.execute('UPDATE tasks SET exhausted=1 WHERE pool=? AND path=? AND row_group=?', (language, path, group))
                db.commit()
    state(db, language, dict(status='complete', count=count, target=target, shortfall=max(0, target-count), stats=dict(stats)))
    db.commit()


def build_openhermes(db, paths, target, seed, batch_size):
    paths = sorted(Path(p).resolve() for p in paths)
    random.Random(f'{seed}/openhermes').shuffle(paths)
    queue = deque()
    for path in paths:
        sha = pin(db, path, 'openhermes_local')
        db.execute('INSERT OR IGNORE INTO tasks(pool,path,row_group) VALUES (?,?,0)', ('openhermes', str(path)))
        start, exhausted = db.execute("SELECT cursor,exhausted FROM tasks WHERE pool='openhermes' AND path=?", (str(path),)).fetchone()
        if not exhausted:
            iterator = iter(rows(path))
            for _ in range(start):
                next(iterator)
            queue.append((path, sha, iterator, start))
    count = db.execute("SELECT count(*) FROM seeds WHERE pool='openhermes'").fetchone()[0]
    stats = Counter()
    while queue and count < target:
        path, sha, iterator, ordinal = queue.popleft()
        exhausted = False
        for _ in range(batch_size):
            try:
                row = next(iterator)
            except StopIteration:
                exhausted = True
                break
            current = ordinal
            ordinal += 1
            stats['scanned'] += 1
            messages = eligible_openhermes(row)
            if messages is None:
                stats['ineligible'] += 1
                continue
            key = digest(messages)
            payload = dict(messages=messages, id=key, repo='schneiderkamplab/' + path.parent.parent.name,
                file=str(path), ordinal=current, file_sha256=sha, preparation_version=VERSION,
                source_metadata={k:v for k,v in row.items() if k not in ('messages', 'tools')})
            if insert(db, 'openhermes', payload, key, key):
                count += 1
            if count >= target:
                break
        db.execute("UPDATE tasks SET cursor=?,exhausted=? WHERE pool='openhermes' AND path=?", (ordinal, exhausted, str(path)))
        state(db, 'openhermes', dict(status='building', count=count, target=target, stats=dict(stats)))
        db.commit()
        if not exhausted:
            queue.append((path, sha, iterator, ordinal))
    state(db, 'openhermes', dict(status='complete', count=count, target=target, shortfall=max(0,target-count), stats=dict(stats)))
    db.commit()


def prepare(root, data_root, previous, oh_paths, seed=20260927, targets=None, batch_size=128):
    root, data_root = Path(root), Path(data_root)
    if not previous or not oh_paths:
        raise ValueError('Explicit prior roots and local OpenHermes files required')
    if not 1 <= batch_size <= 1024:
        raise ValueError('batch_size must be 1..1024')
    targets = targets or TARGETS
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / '.prepare.lock'), connect(root) as db:
        manifest = dict(version=VERSION, seed=seed, targets=targets, batch_size=batch_size,
            previous=[str(Path(p).resolve()) for p in previous], oh_paths=[str(Path(p).resolve()) for p in oh_paths],
            data_root=str(data_root.resolve()), implementation_sha256=file_hash(__file__))
        old = db.execute("SELECT value FROM build_state WHERE key='manifest'").fetchone()
        if old and json.loads(old[0]) != manifest:
            raise ValueError('Preparation configuration drift; use a new root')
        for path, size, mtime in db.execute('SELECT path,size,mtime_ns FROM inputs'):
            stat = Path(path).stat()
            if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
                raise ValueError('Pinned input changed: ' + path)
        state(db, 'manifest', manifest)
        state(db, 'phase', 'preflight')
        db.commit()
        pin(db, data_root / 'sources.lock.json', 'catalog')
        for path in sorted((data_root / 'approvals').glob('dynaword-*.json')):
            pin(db, path, 'approval')
        if not db.execute("SELECT 1 FROM build_state WHERE key='exclusions_ready'").fetchone():
            import_prior(db, previous)
            state(db, 'exclusions_ready', True)
            db.commit()
        state(db, 'phase', 'building')
        db.commit()
        # Publish a small committed supply for every pool before expanding any
        # one language to its full target; all seeds are immutable once visible.
        for language in LANGUAGES:
            build_native(db, data_root, language, min(2048, targets[language]), seed, batch_size)
        build_openhermes(db, oh_paths, min(2048, targets['openhermes']), seed, batch_size)
        for language in LANGUAGES:
            build_native(db, data_root, language, targets[language], seed, batch_size)
        build_openhermes(db, oh_paths, targets['openhermes'], seed, batch_size)
        state(db, 'phase', 'complete')
        db.commit()
    return status(root)


def status(root):
    path = Path(root) / 'seeds.sqlite'
    with sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True) as db:
        return dict(counts=dict(db.execute('SELECT pool,count(*) FROM seeds GROUP BY pool')),
                    state={k: json.loads(v) for k,v in db.execute('SELECT key,value FROM build_state')},
                    exclusions=db.execute('SELECT count(*) FROM exclusions').fetchone()[0],
                    admission_authorized=False)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('prepare', 'status'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, default=Path('data/dfm12'))
    parser.add_argument('--previous', type=Path, action='append', default=[])
    parser.add_argument('--oh-path', type=Path, action='append', default=[])
    parser.add_argument('--seed', type=int, default=20260927)
    parser.add_argument('--batch-size', type=int, default=128)
    args = parser.parse_args()
    result = status(args.root) if args.action == 'status' else prepare(args.root, args.data_root,
        args.previous, args.oh_path, args.seed, batch_size=args.batch_size)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
