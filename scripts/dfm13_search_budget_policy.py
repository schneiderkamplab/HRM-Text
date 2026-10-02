"""Transactional campaign ceiling; historical campaigns default to 100."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def ceiling(db):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='paid_search_policy'").fetchone()
    if not exists:
        return 100
    row = db.execute('SELECT ceiling FROM paid_search_policy WHERE id=1').fetchone()
    if row is None or type(row[0]) is not int or row[0] not in (100, 200):
        raise ValueError('invalid paid search policy')
    return row[0]


def migrate(root):
    db = sqlite3.connect(f'file:{root / "cache.sqlite"}?mode=rw', uri=True, timeout=30)
    try:
        db.execute('BEGIN IMMEDIATE')
        old = ceiling(db)
        count = db.execute('SELECT count(*) FROM searches').fetchone()[0]
        db.execute('CREATE TABLE IF NOT EXISTS paid_search_policy (id INTEGER PRIMARY KEY CHECK(id=1), ceiling INTEGER NOT NULL, receipt TEXT NOT NULL)')
        if old == 200:
            receipt = json.loads(db.execute('SELECT receipt FROM paid_search_policy WHERE id=1').fetchone()[0])
        else:
            if count > 100:
                raise ValueError('unexpected pre-migration reservation count')
            receipt = dict(schema='dfm13-paid-cap-authorization-v1', at=datetime.now(timezone.utc).isoformat(),
                authorization='Explicit user instruction 2026-10-01: raise TOTAL paid search cap from 100 to 200.',
                old_ceiling=100, new_ceiling=200, preserved_reservations=count,
                cache_reset=False, failed_reservations_refunded=False,
                scope='Purposeful missing relevant/historical evidence; no mass blind search.',
                historical_manifests_rewritten=False)
            db.execute('INSERT OR REPLACE INTO paid_search_policy VALUES(1,200,?)', (json.dumps(receipt),))
        db.commit()
        return receipt
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    receipt = migrate(args.root)
    from scripts.dfm13_search_calibration import atomic
    atomic(args.root / 'cap-200-authorization.json', receipt)
    print(json.dumps(receipt))
