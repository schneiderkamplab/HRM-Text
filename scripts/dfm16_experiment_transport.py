"""Shared, crash-persistent Odin send budget and usage ledger for one experiment."""
import asyncio
import json
import sqlite3
import time
from pathlib import Path
import httpx


class Budget:
    def __init__(self, path, limit=100, window=60):
        self.path, self.limit, self.window = str(path), limit, window
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sends (id INTEGER PRIMARY KEY, sent REAL NOT NULL, usage TEXT, status INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER, window REAL)')
            db.execute('INSERT OR IGNORE INTO settings VALUES (1,?,?)',(limit,window))
            if db.execute('SELECT cap,window FROM settings').fetchone() != (limit,window):
                raise ValueError('Shared rate settings changed')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def reserve(self, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute('SELECT sent FROM sends WHERE sent > ? ORDER BY sent',(now-self.window,)).fetchall()
            if len(active) >= self.limit:
                return None, max(.001, active[-self.limit][0]+self.window-now)
            cursor = db.execute('INSERT INTO sends(sent) VALUES (?)',(now,))
            return cursor.lastrowid, 0

    def complete(self, identifier, status, usage):
        with self.connect() as db:
            db.execute('UPDATE sends SET status=?,usage=? WHERE id=?',(status,json.dumps(usage),identifier))

    def summary(self, input_per_million=None, output_per_million=None):
        with self.connect() as db:
            records = db.execute('SELECT status,usage FROM sends').fetchall()
        usage = [json.loads(v) for _,v in records if v is not None]
        prompt = sum(v.get('prompt_tokens',0) for v in usage)
        completion = sum(v.get('completion_tokens',0) for v in usage)
        return dict(actual_send_reservations=len(records), incomplete_sends=sum(s is None for s,_ in records),
            prompt_tokens=prompt, completion_tokens=completion,
            estimated_cost=None if None in (input_per_million,output_per_million) else
                (prompt*input_per_million+completion*output_per_million)/1e6,
            cost_caveat='Missing provider usage and local GPU costs excluded; ambiguous crash sends remain charged to the rate budget.')


class ExperimentClient(httpx.AsyncClient):
    """All discovery, generation, audit and retry sends share the same ledger.

    Controller holds an experiment-wide lock; at most one active client, 64
    concurrent sends. Ledger survives restarts. No hidden transport retries or redirects.
    """
    def __init__(self, budget, **kwargs):
        super().__init__(follow_redirects=False, **kwargs)
        self.budget = budget
        self.slots = asyncio.Semaphore(64)

    async def send(self, *args, **kwargs):
        async with self.slots:
            while True:
                identifier, delay = await asyncio.to_thread(self.budget.reserve)
                if identifier is not None: break
                await asyncio.sleep(min(delay,1))
            response = await super().send(*args, **kwargs)
            try: usage = (await asyncio.to_thread(response.json)).get('usage',{})
            except (ValueError, AttributeError): usage = {}
            await asyncio.to_thread(self.budget.complete,identifier,response.status_code,usage)
            return response
