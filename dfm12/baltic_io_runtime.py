"""Isolated sealed Baltic offloading runtime, retaining 384/server policy."""
import argparse
import asyncio
from pathlib import Path
import sqlite3
from . import baltic_concurrency384 as previous
from . import baltic_async_io as offload
from .io import file_hash, load, lock, write_json


def controller(owner=None):
    c = previous.controller()
    prior = c.verify
    def verify(root):
        m = prior(root)
        if m.get('io_runtime_module') != 'dfm12.baltic_io_runtime':
            raise ValueError('Explicit I/O runtime migration required')
        return m
    c.verify = verify
    return offload.install(c, owner) if owner is not None else c


def migrate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    with lock(root/'controller.lock'), sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT sum(active) FROM groups').fetchone()[0]:
            raise ValueError('Drain required')
        m = previous.controller().verify(root)
        write_json(output/'previous-manifest.json', m)
        write_json(output/'previous-seal.json', load(root/'seal.json'))
        m.update(io_runtime_module='dfm12.baltic_io_runtime',
                 io_owner_threads=1, http_keepalive_seconds=2,
                 circuit_deadline_policy='first_failure_nonextending',
                 admission_spacing_seconds=.01, circuit_cooldown_seconds=5,
                 admission_waiting_limit=128, admission_poll_seconds=.01)
        for p in (Path(__file__).resolve(), Path(offload.__file__).resolve()):
            m['implementation_pins'][str(p)] = file_hash(p)
        write_json(root/'manifest.json', m)
        sha = file_hash(root/'manifest.json')
        write_json(root/'seal.json', dict(manifest_sha256=sha))
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        db.commit()
        accepted = db.execute('SELECT sum(accepted) FROM groups').fetchone()[0]
        write_json(output/'receipt.json', dict(manifest_sha256=sha,accepted_before=accepted,
            ledger_rows_unchanged=True, unknown_replay=False,concurrency_per_server=384))
    controller().verify(root)


async def run(root):
    owner = offload.Owner()
    try:
        c = controller(owner)
        return await c.execute(root,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            concurrency=384, timeout=600, max_kv_cache_utilization=.90)
    finally:
        owner.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['migrate','run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    if a.action == 'migrate':
        migrate(a.root, a.output)
    else:
        asyncio.run(run(a.root))
