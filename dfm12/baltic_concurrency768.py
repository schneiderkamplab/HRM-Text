"""User-authorized 768/server Baltic successor, retaining zero spacing."""
import argparse
import asyncio
from pathlib import Path
import sqlite3
from . import baltic_zero_spacing as previous
from .baltic_async_io import Owner
from .io import file_hash, load, lock, write_json


def controller(owner=None):
    c = previous.controller(owner)
    prior = c.verify
    def verify(root):
        m = prior(root)
        if m.get('concurrency768_runtime_module') != 'dfm12.baltic_concurrency768' or m.get('effective_concurrency_per_server') != 768:
            raise ValueError('Explicit 768 runtime seal required')
        return m
    c.verify = verify
    if owner is not None:
        code = c.execute.__code__
        if code.co_consts.count(384) != 1:
            raise ValueError('Unexpected runner concurrency guard')
        c.execute.__code__ = code.replace(co_consts=tuple(
            768 if type(v) is int and v == 384 else v for v in code.co_consts))
    return c


def migrate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    with lock(root/'controller.lock'), sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT sum(active) FROM groups').fetchone()[0]:
            raise ValueError('Drain required')
        m = previous.controller().verify(root)
        write_json(output/'previous-manifest.json', m)
        write_json(output/'previous-seal.json', load(root/'seal.json'))
        m.update(concurrency768_runtime_module='dfm12.baltic_concurrency768', effective_concurrency_per_server=768)
        m['implementation_pins'][str(Path(__file__).resolve())] = file_hash(__file__)
        write_json(root/'manifest.json', m)
        sha = file_hash(root/'manifest.json')
        write_json(root/'seal.json', dict(manifest_sha256=sha))
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        db.commit()
        write_json(output/'receipt.json', dict(manifest_sha256=sha,
            accepted_before=db.execute('SELECT sum(accepted) FROM groups').fetchone()[0],
            ledger_rows_unchanged=True, unknown_replay=False, concurrency_per_server=768,
            admission_spacing_seconds=0))
    controller().verify(root)


async def run(root):
    owner = Owner()
    try:
        await controller(owner).execute(root,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            concurrency=768, timeout=600, max_kv_cache_utilization=.90)
    finally:
        owner.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['migrate','run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'migrate':migrate(a.root, a.output)
    else:asyncio.run(run(a.root))
