"""Deterministic accepted-only pair selection across direct and pivot routes."""
import json
import sqlite3

from .io import digest
from .jobs import validate_audit
from .records import validate_messages


class PairSelection:
    def __init__(self, database, languages, token_cap):
        if len(languages) != 2 or len(set(languages)) != 2:
            raise ValueError('Exactly two languages required')
        if type(token_cap) is not int or token_cap <= 0:
            raise ValueError('Positive integer combined token cap required')
        self.languages = set(languages)
        self.token_cap = token_cap
        self.db = sqlite3.connect(database)
        self.db.execute('CREATE TABLE IF NOT EXISTS config(value TEXT NOT NULL)')
        config = json.dumps(dict(languages=sorted(languages), token_cap=token_cap), sort_keys=True)
        previous = self.db.execute('SELECT value FROM config').fetchone()
        if previous and previous[0] != config:
            raise ValueError('Selection configuration changed')
        if not previous:
            self.db.execute('INSERT INTO config VALUES(?)', (config,))
        self.db.execute('CREATE TABLE IF NOT EXISTS pairs '
            '(id TEXT PRIMARY KEY, priority INTEGER, tokens INTEGER, record TEXT, review TEXT, component TEXT)')
        self.db.commit()

    def add(self, record, review, component, route):
        validate_audit(review)
        if not review['keep']:
            raise ValueError('Nonpositive review cannot enter selection')
        if route not in ('direct', 'institutional', 'pivot') or record['task'] != 'translation':
            raise ValueError('Invalid translation route or task')
        if {record['language'], record['reverse_language']} != self.languages:
            raise ValueError('Language pair mismatch')
        for field in ('messages', 'reverse_messages'):
            validate_messages(record[field])
            if len(record[field]) != 2 or record[field][-1]['role'] != 'assistant':
                raise ValueError('Expected one translation target per direction')
        tokens = record['rendered_tokens']
        if type(tokens) is not int or tokens <= 0:
            raise ValueError('Missing preflight combined token count')
        key = digest({record['language']: record['messages'][-1]['content'],
                      record['reverse_language']: record['reverse_messages'][-1]['content']})
        priority = 1 if route == 'pivot' else 0
        self.db.execute('INSERT INTO pairs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
            'priority=excluded.priority,tokens=excluded.tokens,record=excluded.record,'
            'review=excluded.review,component=excluded.component '
            'WHERE (excluded.priority,excluded.component)<(pairs.priority,pairs.component)',
            (key, priority, tokens, json.dumps(record, ensure_ascii=False),
             json.dumps(review, ensure_ascii=False), component))
        return key

    def selected(self):
        self.db.commit()
        used = 0
        # Hash order is reproducible and does not favor the first source file.
        for key, tokens, raw, review, component in self.db.execute(
                'SELECT id,tokens,record,review,component FROM pairs ORDER BY priority,id'):
            if used + tokens > self.token_cap:
                continue
            used += tokens
            yield dict(id=key, record=json.loads(raw), review=json.loads(review),
                       component=component, combined_tokens=tokens, cumulative_tokens=used)

    def close(self):
        self.db.close()
