"""Opt-in bounded candidate reuse; original selections/cursors remain authoritative.

Wrap an original or European SourceProvider with SourceReuseProvider(provider,
root). Use one wrapper per worker connection, and route every allocator for that
campaign through this wrapper. This is not an admission or duplicate-check bypass.
"""
import importlib
import json
from pathlib import Path
import sqlite3

from .io import digest
from .multilingual_production_specs import SeedUnavailable

LANGUAGES = ('cs', 'ca', 'is', 'pt_pt', 'et', 'fo')


class SourceReuseProvider:
    def __init__(self, provider, root, *, max_per_seed=32, languages=LANGUAGES):
        if type(max_per_seed) is not int or not 2 <= max_per_seed <= 32:
            raise ValueError('max_per_seed must be an integer in [2,32]')
        if not languages or not set(languages) <= set(LANGUAGES):
            raise ValueError('Reuse only authorized for blocked languages')
        self.provider = provider
        self.max_per_seed = max_per_seed
        self.languages = tuple(sorted(set(languages)))
        module = importlib.import_module(type(provider).__module__)
        self.factory = module.spec_for
        self.names = module.LANGUAGES
        Path(root).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(Path(root) / 'source-reuse.sqlite', timeout=60)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        original = provider.db.execute('PRAGMA database_list').fetchone()[2]
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (signature TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS selections (id TEXT PRIMARY KEY, spec TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS uses (
                scope TEXT, source_id TEXT, additional INTEGER NOT NULL,
                PRIMARY KEY(scope,source_id));
            CREATE TABLE IF NOT EXISTS cursors (scope TEXT PRIMARY KEY, seq INTEGER NOT NULL);
        ''')
        signature = digest(dict(version=1, original=str(Path(original).resolve()),
            seeds=str(provider.seeds_path.resolve()), config=provider.config,
            languages=self.languages, max_per_seed=max_per_seed,
            provider=type(provider).__module__))
        with self.db:
            old = self.db.execute('SELECT signature FROM metadata').fetchone()
            if old and old[0] != signature:
                raise ValueError('Source reuse configuration drift')
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?)', (signature,))
        self.lookup = sqlite3.connect(':memory:', uri=True, timeout=60)
        for name, path in [('original', Path(original)), ('inventory', provider.seeds_path),
                           ('ledger', Path(root) / 'source-reuse.sqlite')]:
            self.lookup.execute(f'ATTACH DATABASE ? AS {name}',
                                (path.resolve().as_uri() + '?mode=ro',))

    def close(self):
        self.lookup.close()
        self.db.close()
        self.provider.close()

    def next_spec(self, language, family, slot):
        if type(slot) is not int or slot < 0:
            raise ValueError('Slot must be a nonnegative integer')
        key = digest([language, family, slot])
        # The sidecar serializes cooperating allocators, including unique-source
        # allocation. Do not write attached databases or hold locks on them while
        # calling the original provider.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT spec FROM selections WHERE id=?', (key,)).fetchone()
            if row:
                return json.loads(row[0])
            try:
                return self.provider.next_spec(language, family, slot)
            except SeedUnavailable:
                if language not in self.languages:
                    raise
            placeholder = dict(id='unallocated', text='unallocated', messages=[])
            spec = self.factory(language, family, slot, 0,
                {name: [placeholder] for name in (*self.names, 'openhermes')}, self.provider.config)
            if 'source' not in spec:
                raise SeedUnavailable('No source-backed task to reuse')
            pool = 'openhermes' if family == 'openhermes' else language
            scope = f'{language}/{pool}'
            cursor = self.db.execute('SELECT seq FROM cursors WHERE scope=?', (scope,)).fetchone()
            cursor = cursor[0] if cursor else 0
            # available_seeds retains language-specific exclusions for BOTH pools.
            query = '''SELECT s.seq,s.source_id,s.payload,COALESCE(u.additional,0)
                FROM inventory.available_seeds s
                JOIN original.used_sources o ON o.scope=? AND o.source_id=s.source_id
                LEFT JOIN ledger.uses u ON u.scope=? AND u.source_id=s.source_id
                WHERE s.language=? AND s.pool=? AND COALESCE(u.additional,0)<?
                  AND s.seq>? ORDER BY s.seq LIMIT 1'''
            args = (scope, scope, language, pool, self.max_per_seed - 1)
            row = self.lookup.execute(query, (*args, cursor)).fetchone()
            if row is None:
                row = self.lookup.execute(query, (*args, 0)).fetchone()
            if row is None:
                raise SeedUnavailable(scope + ': eligible source reuse budget exhausted')
            seq, source_id, payload, additional = row
            source = json.loads(payload)
            if (not isinstance(source, dict) or not source_id or source.get('id') != source_id
                    or source.get('language', 'en' if pool == 'openhermes' else language)
                    != ('en' if pool == 'openhermes' else language)):
                raise ValueError('Seed ID/language/pool mismatch')
            if pool == 'openhermes':
                from .multilingual_generation_v4 import _pairs
                _pairs(dict(spec, source=source))
            elif not isinstance(source.get('text'), str) or not source['text'].strip():
                raise ValueError('Native seed requires nonblank text')
            spec['source'] = source
            spec['source_reuse'] = dict(version=1, scope=scope, source_hash=digest(source),
                use_number=additional + 2, max_per_seed=self.max_per_seed,
                requires_same_audit_and_duplicate_checks=True)
            self.db.execute('INSERT INTO selections VALUES (?,?)',
                            (key, json.dumps(spec, ensure_ascii=False)))
            self.db.execute('INSERT OR REPLACE INTO uses VALUES (?,?,?)',
                            (scope, source_id, additional + 1))
            self.db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)', (scope, seq))
            return spec
