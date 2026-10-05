"""Isolated Baltic compact-review successor; preserves historical ledgers."""
import argparse
import ast
import asyncio
import inspect
from pathlib import Path
import sqlite3

from . import baltic_synthetic_campaign as base
from . import wave_compact_review as compact
from .generation_constraints import apply_request
from .io import file_hash, load, lock, write_json


def controller():
    c = compact.install(base.controller())
    original = c.v6.generation_request
    c.v6.generation_request = lambda *a, **k: apply_request(original(*a, **k))
    # Change only the literal concurrency guard in this private module's runner.
    tree = ast.parse(inspect.getsource(c.execute))
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)
              and isinstance(n.left, ast.Constant) and n.left.value == 1
              and any(isinstance(x, ast.Name) and x.id == 'concurrency' for x in n.comparators)]
    if len(guards) != 1 or guards[0].comparators[-1].value != 64:
        raise ValueError('Unexpected runner concurrency guard')
    guards[0].comparators[-1].value = 128
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 'Concurrency <=64 per server; timeout <=600 seconds':
            node.value = 'Concurrency <=128 per server; timeout <=600 seconds'
    exec(compile(ast.fix_missing_locations(tree), __file__, 'exec'), c.__dict__)
    c.verify = lambda root: verify(root, c)
    return c


def verify(root, c=None):
    c = c or controller()
    m = base.verify(root, c)
    if m.get('successor') != 'baltic-compact-128-v1' or m['max_concurrency_per_server'] != 128:
        raise ValueError('Wrong successor policy')
    return m


def backup(source, target):
    with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as old:
        with sqlite3.connect(target) as new:
            old.backup(new)


def prepare(parent, root):
    if root.exists():
        raise ValueError('Fresh successor root required')
    with lock(parent / 'controller.lock'):
        old = load(parent / 'manifest.json')
        if file_hash(parent / 'manifest.json') != load(parent / 'seal.json')['manifest_sha256']:
            raise ValueError('Historical manifest seal mismatch')
        with sqlite3.connect((parent / 'jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
                raise ValueError('Historical controller not drained')
        root.mkdir(parents=True)
        backup(parent / 'jobs.sqlite', root / 'jobs.sqlite')
        backup(parent / 'spec-selections.sqlite', root / 'spec-selections.sqlite')
        write_json(root / 'config.json', load(parent / 'config.json'))
        write_json(root / 'historical-manifest.json', old)
        write_json(root / 'historical-holds.json', load(parent / 'independent-review-holds.json'))
        c = controller()
        # Preserve every prior record/fingerprint/cursor, but no unverified quota
        # credit. Exact-hash independent clearance can credit retained rows later.
        with sqlite3.connect(root / 'jobs.sqlite') as db:
            previous = db.execute("SELECT language,count(*) FROM jobs WHERE status='accepted' GROUP BY language").fetchall()
            db.execute("UPDATE jobs SET status='prior_quality_hold' WHERE status='accepted'")
            db.execute('UPDATE groups SET accepted=0,active=0,blocked=NULL,retry_at=0')
        m = dict(old)
        paths = base.dependencies(c) + [Path(__file__).resolve(), Path(compact.__file__).resolve(),
                                        Path('dfm12/generation_constraints.py').resolve()]
        m.update(successor='baltic-compact-128-v1',
            implementation_pins={str(p): file_hash(p) for p in paths},
            input_pins={n:file_hash(root/n) for n in ('config.json', 'historical-manifest.json', 'historical-holds.json')},
            max_concurrency_per_server=128, default_concurrency_per_server=128,
            calibration_required_before_bulk=False,
            authorization='User 2026-10-04: start Baltic70K per language, compact review,128/server shared generation/review budget',
            prior=dict(root=str(parent.resolve()), preserved_accepted=dict(previous),
                       credit=0, disposition='Await Poincare exact-hash prior keep clearance; preserve all old artifacts'),
            policy=c.POLICY)
        write_json(root / 'manifest.json', m)
        sha = file_hash(root / 'manifest.json')
        write_json(root / 'seal.json', dict(manifest_sha256=sha))
        with sqlite3.connect(root / 'jobs.sqlite') as db:
            db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        ledger = c.Ledger(root / 'jobs.sqlite')
        try:
            ledger.report(root, 'prepared')
        finally:
            ledger.close()
    return verify(root)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','verify','run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--parent', type=Path, default=Path('data/dfm13/baltic/synthetic-production-staged-v3'))
    a = p.parse_args()
    if a.command == 'prepare':
        print(prepare(a.parent, a.root)['target'])
    elif a.command == 'verify':
        print(verify(a.root)['target'])
    else:
        c = controller()
        asyncio.run(c.execute(a.root, endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)],
                              concurrency=128, timeout=600, max_kv_cache_utilization=.90))


if __name__ == '__main__':
    main()
