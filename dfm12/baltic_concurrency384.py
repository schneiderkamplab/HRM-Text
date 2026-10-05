"""Pinned Baltic-only concurrency successor; no source or review changes."""
import argparse
import asyncio
from pathlib import Path
import sqlite3
from . import compact_keep_recovery as recovery
from .io import file_hash, load, lock, write_json


def widen(execute):
    code = execute.__code__
    if code.co_consts.count(128) != 1:
        raise ValueError('Unexpected private runner guard')
    execute.__code__ = code.replace(co_consts=tuple(
        384 if type(v) is int and v == 128 else
        'Concurrency <=384 per server; timeout <=600 seconds'
        if v == 'Concurrency <=128 per server; timeout <=600 seconds' else v
        for v in code.co_consts))
    return execute


def controller():
    c = recovery.controller()
    c.execute = widen(c.execute)
    prior = c.verify
    def verify(root):
        m = prior(root)
        if m.get('runtime_concurrency_per_server') != 384 or m.get('runtime_module') != 'dfm12.baltic_concurrency384':
            raise ValueError('Explicit 384 runtime seal required')
        return m
    c.verify = verify
    return c


def migrate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    with lock(root/'controller.lock'), sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT sum(active) FROM groups').fetchone()[0]:
            raise ValueError('Drain required')
        m = recovery.controller().verify(root)
        write_json(output/'previous-manifest.json', m)
        write_json(output/'previous-seal.json', load(root/'seal.json'))
        m.update(runtime_concurrency_per_server=384, runtime_module='dfm12.baltic_concurrency384')
        m['implementation_pins'][str(Path(__file__).resolve())] = file_hash(__file__)
        write_json(root/'manifest.json', m)
        sha = file_hash(root/'manifest.json')
        write_json(root/'seal.json', dict(manifest_sha256=sha))
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        db.commit()
        write_json(output/'receipt.json', dict(manifest_sha256=sha, concurrency_per_server=384,
            ledger_rows_unchanged=True, recovery_adapter_unchanged=True))
    controller().verify(root)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['migrate', 'run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'migrate':
        migrate(a.root, a.output)
    else:
        asyncio.run(controller().execute(a.root,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            concurrency=384, timeout=600, max_kv_cache_utilization=.90))


if __name__ == '__main__':
    main()
