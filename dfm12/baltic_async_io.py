"""Private CPU/I/O offloading; unchanged durable operations and retry policy."""
import ast
import asyncio
from concurrent.futures import ThreadPoolExecutor
import inspect
import textwrap


def trip_once(self, endpoint):
    if endpoint not in self.recover_at:
        self.circuit_generation[endpoint] += 1
        self.recover_at[endpoint] = __import__('time').monotonic() + self.cooldown


class Owner:
    """Create and use SQLite/provider/tokenizer state on one dedicated thread."""
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='baltic-owner')

    async def call(self, operation):
        future = asyncio.get_running_loop().run_in_executor(self.pool, operation)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # A cancelled await must not race cleanup against an unfinished write.
            await asyncio.shield(future)
            raise

    def close(self):
        self.pool.shutdown(wait=True)


class Offload(ast.NodeTransformer):
    def __init__(self, selected):
        self.selected = selected
        self.count = 0

    def visit_FunctionDef(self, node):
        # Synchronous callbacks are invoked explicitly through the owner below.
        return node

    def visit_Call(self, node):
        name = ast.unparse(node.func)
        if self.selected(name):
            self.count += 1
            return ast.copy_location(ast.Await(value=ast.Call(
                func=ast.Name(id='_cpu', ctx=ast.Load()),
                args=[ast.Lambda(args=ast.arguments(posonlyargs=[], args=[],
                    kwonlyargs=[], kw_defaults=[], defaults=[]), body=node)], keywords=[])), node)
        return self.generic_visit(node)


def compile_async(function, namespace, selected, expected):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    transformer = Offload(selected)
    tree = transformer.visit(tree)
    if transformer.count != expected:
        raise ValueError('Expected offload sites missing')
    exec(compile(ast.fix_missing_locations(tree), __file__, 'exec'), namespace)
    return namespace[function.__name__]


def install(c, owner):
    """Install only into an already-private controller, never imported globals."""
    from .calibration_streaming import stream_query
    from .multilingual_quarter import execute as original_execute
    c.__dict__['_cpu'] = owner.call
    c.v6.__dict__['_cpu'] = owner.call
    c.pilot.__dict__['_cpu'] = owner.call
    stream_globals = dict(stream_query.__globals__, _cpu=owner.call)
    c.stream_query = compile_async(stream_query, stream_globals,
        lambda n: n in ('writer.begin', 'writer.finish'), 2)
    stage_globals = dict(c.v6.Stages.call.__globals__, _cpu=owner.call)
    stage_call = compile_async(c.v6.Stages.call, stage_globals,
        lambda n: n in ('load', 'write_json', 'self.budget.measure',
                        'jsonschema.validate', 'generator.decode'), 13)
    c.v6.Stages = type('OffloadedStages', (c.v6.Stages,), {'call': stage_call})
    # Membership and insertion must remain one operation despite yielding.
    source = textwrap.dedent(inspect.getsource(c.pilot.process))
    if source.count('if fingerprint in seen:') != 1 or source.count('        seen.add(fingerprint)\n') != 1:
        raise ValueError('Unexpected fingerprint claim sites')
    source = source.replace('if fingerprint in seen:',
        'if not await _cpu(lambda: _claim(seen, fingerprint)):')
    source = source.replace('        seen.add(fingerprint)\n', '')
    tree = ast.parse(source)
    process_transform = Offload(lambda n: n == 'write_json' or n in (
        'v6.generation_request', 'v6.generation_assemble', 'v6.audit_record',
        'v6.review_request', 'v6.review_result', 'v6.compact_request'))
    tree = process_transform.visit(tree)
    if process_transform.count != 10:
        raise ValueError('Unexpected process offload sites')
    c.pilot.__dict__['_claim'] = claim
    exec(compile(ast.fix_missing_locations(tree), __file__, 'exec'), c.pilot.__dict__)
    gate_globals = dict(c.AdmissionGate.admit.__globals__, _cpu=owner.call)
    gate_source = textwrap.dedent(inspect.getsource(c.AdmissionGate.admit))
    if gate_source.count("sample['waiting'] != 0") != 1:
        raise ValueError('Unexpected queue admission guard')
    gate_tree = ast.parse(gate_source.replace("sample['waiting'] != 0", "sample['waiting'] > 128"))
    gate_transform = Offload(lambda n: n == 'can_continue')
    gate_tree = gate_transform.visit(gate_tree)
    if gate_transform.count != 2:
        raise ValueError('Unexpected admission callback count')
    exec(compile(ast.fix_missing_locations(gate_tree), __file__, 'exec'), gate_globals)
    admit = gate_globals['admit']
    base_gate = c.AdmissionGate
    def gate_init(self, *args, **kwargs):
        kwargs.update(spacing=.01, cooldown=5, poll=.01)
        base_gate.__init__(self, *args, **kwargs)
    c.AdmissionGate = type('OffloadedAdmissionGate', (base_gate,),
                          {'admit': admit, 'trip': trip_once, '__init__': gate_init})
    # inspect returns the original file source; reapply the authorized guard only.
    tree = ast.parse(textwrap.dedent(inspect.getsource(original_execute)))
    guards = connectors = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and ast.unparse(node) == '1 <= concurrency <= 64':
            node.comparators[-1].value = 384
            guards += 1
        if isinstance(node, ast.Call) and ast.unparse(node.func) == 'aiohttp.TCPConnector':
            node.keywords.append(ast.keyword(arg='keepalive_timeout', value=ast.Constant(value=2)))
            connectors += 1
        if isinstance(node, ast.keyword) and node.arg == 'admission_spacing_seconds':
            node.value = ast.Constant(value=.01)
        if isinstance(node, ast.keyword) and node.arg == 'circuit_cooldown_seconds':
            node.value = ast.Constant(value=5)
        if isinstance(node, ast.keyword) and node.arg == 'admission_waiting_limit':
            node.value = ast.Constant(value=128)
    selected = lambda n: (n.startswith('ledger.') or n in (
        'Ledger', 'provider_module.SourceProvider', 'provider.close', 'v6.Budget', 'v6.RawResponseWriter',
        'write_json', 'materialize', 'verify', 'v6.verify_pins'))
    runner_transform = Offload(selected)
    tree = runner_transform.visit(tree)
    if runner_transform.count != 22 or guards != 1 or connectors != 2:
        raise ValueError('Unexpected runner offload/transport sites')
    exec(compile(ast.fix_missing_locations(tree), __file__, 'exec'), c.__dict__)
    return c


def claim(seen, fingerprint):
    if fingerprint in seen:
        return False
    seen.add(fingerprint)
    return True
