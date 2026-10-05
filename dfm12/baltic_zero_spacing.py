"""Zero fixed admission spacing; retain all Baltic offloading/safety contracts."""
import argparse
import asyncio
from pathlib import Path
import sqlite3
import types
from . import baltic_io_runtime as previous
from . import baltic_async_io
from .io import file_hash, load, lock, write_json


def controller(owner=None):
    c = previous.controller(owner)
    prior = c.verify
    def verify(root):
        m = prior(root)
        if m.get('zero_spacing_runtime_module') != 'dfm12.baltic_zero_spacing' or m.get('admission_spacing_seconds') != 0:
            raise ValueError('Explicit zero-spacing seal required')
        return m
    c.verify = verify
    if owner is not None:
        gate = c.AdmissionGate
        class ZeroGate(gate):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.spacing = 0
        c.AdmissionGate = ZeroGate
        code = c.execute.__code__
        targets = [v for v in code.co_consts if isinstance(v, types.CodeType)
                   and 'runtime.json' in v.co_consts and v.co_consts.count(.01) == 1]
        if len(targets) != 1:
            raise ValueError('Unexpected runtime spacing metadata')
        target = targets[0]
        replacement = target.replace(co_consts=tuple(
            0 if type(v) is float and v == .01 else v for v in target.co_consts))
        c.execute.__code__ = code.replace(co_consts=tuple(
            replacement if v is target else v for v in code.co_consts))
    return c


def migrate(root, output):
    output.mkdir(parents=True, exist_ok=False)
    with lock(root/'controller.lock'), sqlite3.connect(root/'jobs.sqlite') as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0] or db.execute('SELECT sum(active) FROM groups').fetchone()[0]:
            raise ValueError('Drain required')
        m = previous.controller().verify(root)
        write_json(output/'previous-manifest.json', m)
        write_json(output/'previous-seal.json', load(root/'seal.json'))
        m.update(zero_spacing_runtime_module='dfm12.baltic_zero_spacing', admission_spacing_seconds=0)
        m['implementation_pins'][str(Path(__file__).resolve())] = file_hash(__file__)
        write_json(root/'manifest.json', m)
        sha = file_hash(root/'manifest.json')
        write_json(root/'seal.json', dict(manifest_sha256=sha))
        db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'", (sha,))
        db.commit()
        write_json(output/'receipt.json', dict(manifest_sha256=sha,
            accepted_before=db.execute('SELECT sum(accepted) FROM groups').fetchone()[0],
            ledger_rows_unchanged=True, admission_spacing_seconds=0))
    controller().verify(root)


async def run(root):
    owner = baltic_async_io.Owner()
    try:
        await controller(owner).execute(root,
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
    if a.action == 'migrate':migrate(a.root, a.output)
    else:asyncio.run(run(a.root))
