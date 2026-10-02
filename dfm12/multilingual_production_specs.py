"""Durable non-wrapping source allocation for cumulative multilingual targets."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

from .io import digest
from .multilingual_seeds import LANGUAGES
from .multilingual_tasks import spec_for


class SeedUnavailable(RuntimeError):
    """Pause this group; never substitute a repeated source or burn a slot."""


class SourceProvider:
    def __init__(self, seeds_root, root, config):
        self.seeds_path = Path(seeds_root) / 'seeds.sqlite'
        self.config = dict(contract_version=4, cohort=config['campaign'],
                           quotas={'openhermes': 1})
        Path(root).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(root)/'spec-selections.sqlite', timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS selections (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, seed_hash TEXT);
            CREATE TABLE IF NOT EXISTS cursors (
                scope TEXT PRIMARY KEY, seq INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS used_sources (
                scope TEXT NOT NULL, source_id TEXT NOT NULL,
                PRIMARY KEY(scope, source_id));
        ''')
        signature = digest({'config': self.config, 'seeds_path': str(self.seeds_path.resolve())})
        row = self.db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()
        if row and row[0] != signature:
            raise ValueError('Source provider configuration drift')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('signature',?)", (signature,))

    def close(self):
        self.db.close()

    def next_spec(self, language, family, slot):
        key = digest([language, family, slot])
        found = self.db.execute('SELECT spec FROM selections WHERE id=?', (key,)).fetchone()
        if found:
            return json.loads(found[0])
        placeholder = {'id': 'unallocated', 'text': 'unallocated', 'messages': []}
        seeds = {lang: [placeholder] for lang in (*LANGUAGES, 'openhermes')}
        spec = spec_for(language, family, slot, 0, seeds, self.config)
        seed_hash = None
        with self.db:
            if 'source' in spec:
                pool = 'openhermes' if family == 'openhermes' else language
                # Reusing an English source in distinct target languages is
                # intentional; within one target language sources never wrap.
                scope = f'{language}/{pool}'
                row = self.db.execute('SELECT seq FROM cursors WHERE scope=?', (scope,)).fetchone()
                cursor = row[0] if row else 0
                if not self.seeds_path.is_file():
                    raise SeedUnavailable(pool + ': seed preparation not ready')
                with closing(sqlite3.connect(self.seeds_path.resolve().as_uri()+'?mode=ro', uri=True, timeout=30)) as source:
                    while True:
                        if pool == 'openhermes':
                            row = source.execute('SELECT seq,source_id,payload FROM available_seeds WHERE language=? AND pool=? AND seq>? ORDER BY seq LIMIT 1',
                                                 (language, pool, cursor)).fetchone()
                        else:
                            row = source.execute('SELECT seq,source_id,payload FROM seeds WHERE pool=? AND seq>? ORDER BY seq LIMIT 1',
                                                 (pool, cursor)).fetchone()
                        if not row:
                            raise SeedUnavailable(pool + ': waiting for additional unique sources')
                        cursor, source_id, payload = row
                        if not self.db.execute('SELECT 1 FROM used_sources WHERE scope=? AND source_id=?',
                                               (scope, source_id)).fetchone():
                            break
                spec['source'] = json.loads(payload)
                if spec['source']['id'] != source_id:
                    raise ValueError('Seed ID/payload mismatch')
                seed_hash = digest(spec['source'])
                self.db.execute('INSERT INTO used_sources VALUES (?,?)', (scope, source_id))
                self.db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)', (scope, cursor))
            self.db.execute('INSERT INTO selections VALUES (?,?,?)',
                            (key, json.dumps(spec, ensure_ascii=False), seed_hash))
        return spec
