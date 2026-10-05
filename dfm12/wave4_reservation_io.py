"""W4 reservation spec durability offload and owner-maintained gate hint."""
import ast
import inspect
import textwrap
import asyncio
from pathlib import Path
from . import wave4_parallel_io as parallel
from . import calibration_loop_guard_fast as fast_guard
from .io import digest, write_json


class Owner(parallel.Owner):
    def __init__(self, workers=16):
        super().__init__(workers)
        self.remaining_hint = True

    async def call(self, operation):
        code = getattr(operation, '__code__', None)
        if code and code.co_freevars == ('can_continue',):
            callback = operation.__closure__[0].cell_contents
            if getattr(callback, '__name__', None) == 'has_remaining':
                return self.remaining_hint
        result = await super().call(operation)
        if code and 'reserve' in code.co_names and 'ledger' in code.co_freevars and result is not None:
            # SQLite spec_json/slot committed first; no request may precede this await.
            job = result
            await super().call(lambda: write_json(job['workdir']/'specifications'/f"{job['id']}.json",
                dict(spec=job['spec'], spec_sha256=digest(job['spec']))))
        return result


def install(c, owner):
    base = c.Ledger
    tree = ast.parse(textwrap.dedent(inspect.getsource(base.reserve)))
    fn = tree.body[0]
    removed = 0
    for node in ast.walk(fn):
        if isinstance(node, (ast.For, ast.With, ast.If)):
            filtered = []
            for statement in node.body:
                if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                        and ast.unparse(statement.value.func) == 'write_json'):
                    removed += 1
                else:
                    filtered.append(statement)
            node.body = filtered
    if removed != 1:
        raise ValueError('Expected exactly one post-commit specification write')
    namespace = dict(base.reserve.__globals__)
    exec(compile(ast.fix_missing_locations(tree), __file__, 'exec'), namespace)
    reserve_sql = namespace['reserve']

    class Ledger(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.allocated_groups = {}
            self.refresh()

        def refresh(self):
            self.group_snapshot = {(r['language'],r['family']):dict(r)
                for r in self.db.execute('SELECT * FROM groups')}
            self.publish()

        def publish(self):
            owner.remaining_hint = any(r['accepted'] < r['target'] and r['attempts'] < 6*r['target']
                for key,r in self.group_snapshot.items()
                if self.allowed_groups is None or key in self.allowed_groups)

        def restrict_groups(self, groups):
            super().restrict_groups(groups)
            self.publish()

        def reserve(self, provider, unavailable, root):
            job = reserve_sql(self, provider, unavailable, root)
            if job is not None:
                key = (job['spec']['language_code'],job['spec']['family'])
                self.group_snapshot[key]['attempts'] += 1
                self.allocated_groups[job['id']] = key
            self.publish()
            return job

        def finish(self, key, outcome):
            accepted = super().finish(key, outcome)
            group = self.allocated_groups.pop(key, None)
            if group is None:
                self.refresh()  # Recovery of a pre-existing allocation.
            else:
                self.group_snapshot[group]['accepted'] += int(accepted)
                self.publish()
            return accepted
    c.Ledger = Ledger
    return c


def controller(owner=None):
    c = parallel.controller(owner)
    if owner is not None:
        c = install(c, owner)
        from .calibration_streaming import stream_query
        if c.stream_query.__globals__ is stream_query.__globals__:
            raise ValueError('Private stream globals required')
        c.stream_query.__globals__['LoopGuard'] = fast_guard.LoopGuard
        original_write = c.write_json
        def write(path, value):
            if path.name == 'runtime.json':
                value = dict(value, reservation_io_runtime_module='dfm12.wave4_reservation_io',
                             specification_write='parallel_durable_before_request',
                             gate_remaining='owner_published_hint_reserve_authoritative')
            return original_write(path, value)
        c.write_json = write
    return c


async def run(root, launch_mode):
    from .io import load, file_hash
    root = Path(root)
    manifest = parallel.verify_launch(root,16,launch_mode)
    if (manifest.get('reservation_io_runtime_module') != 'dfm12.wave4_reservation_io'
            or manifest['implementation_pins'].get(str(Path(__file__).resolve())) != file_hash(__file__)):
        raise ValueError('Explicit reservation I/O successor seal required')
    if manifest['implementation_pins'].get(str(Path(fast_guard.__file__).resolve())) != file_hash(fast_guard.__file__):
        raise ValueError('Fast loop guard implementation pin required')
    owner = Owner(16)
    async def report():
        while True:
            snapshot = owner.snapshot()
            await owner.call(lambda: write_json(root/'operation-timings.json',snapshot))
            await asyncio.sleep(15)
    reporting = asyncio.create_task(report())
    try:
        await controller(owner).execute(root,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            concurrency=768,timeout=600,max_kv_cache_utilization=.90)
    finally:
        reporting.cancel()
        await asyncio.gather(reporting,return_exceptions=True)
        snapshot = owner.snapshot()
        await owner.call(lambda: write_json(root/'operation-timings.json',snapshot))
        owner.close()


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--launch-mode',choices=['independent','completed'],required=True)
    args=p.parse_args()
    asyncio.run(run(args.root,args.launch_mode))
