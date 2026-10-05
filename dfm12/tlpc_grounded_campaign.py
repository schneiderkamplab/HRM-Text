"""Sixteen isolated TLPC clients, native Gemma4 generation and fresh-context audit."""
import argparse
import asyncio
import copy
from functools import lru_cache
import json
from pathlib import Path
import sqlite3
import time

from . import european_synthetic_campaign as isolation
from . import tlpc_grounded_specs as specs
from . import wave_synthetic_runtime as runtime
from . import multilingual_calibration_v6 as stages_api
from .io import digest, file_hash, load, lock, write_json, atomic

VERSION = 'tlpc-grounded-v1'
POLICY = dict(automatic_upload=False, automatic_export=False, training_changed=False,
    native_quality_certified=False, accepted_basis='independent automated full-source fidelity audit',
    exact_unique_target=100000, no_transformations=True)


def quotas(config, milestone=None, divisor=None):
    family = config['family']
    if family not in specs.FAMILIES or not 0 <= config['shard'] < 8:
        raise ValueError('Invalid shard/task')
    return [dict(language='fa', family=family,
                 accepted_target=7500 if family == specs.FAMILIES[0] else 5000)]


@lru_cache(maxsize=1)
def renderer():
    from .multilingual_generation_v4 import _renderer
    return _renderer()


def student_check(candidate):
    from .multilingual_pilot import student_validate
    return student_validate(renderer(), candidate)


async def process(spec, endpoint, root, stages, health, generation, review, seen):
    key = digest([spec['language_code'], spec['family'], spec['slot']])
    outcome = dict(id=key, spec_sha256=digest(spec), terminal=False, status='inflight',
                   language='fa', family=spec['family'], slot=spec['slot'])
    write_json(root / 'outcomes' / f'{key}.json', outcome)
    try:
        generated = await stages.call(key, 'generate', specs.generation_request(spec),
            specs.schema(spec['family']), endpoint, runtime.endpoint_limit(health[endpoint]))
        if generated['status'] != 'complete':
            outcome.update(status=generated['status'], error=generated.get('error'))
            return outcome
        candidate = specs.assemble(spec, generated['output'])
        await asyncio.to_thread(student_check, candidate)
        write_json(root / 'candidates' / f'{key}.json', candidate)
        fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
        outcome['fingerprint'] = fingerprint
        if fingerprint in seen:
            outcome['status'] = 'duplicate'
            return outcome
        seen.add(fingerprint)
        audited = await stages.call(key, 'review', specs.review_request(spec, candidate),
            specs.REVIEW_SCHEMA, endpoint, runtime.endpoint_limit(health[endpoint]))
        outcome['review_status'] = audited['status']
        if audited['status'] != 'complete':
            outcome.update(status='review_' + audited['status'], error=audited.get('error'))
        else:
            verdict = audited['output']['verdict']
            outcome.update(status='valid' if verdict == 'keep' else verdict,
                           effective_keep=verdict == 'keep', audit=audited['output'])
    except asyncio.CancelledError:
        outcome.update(status='abort_status_unknown', error='Interrupted; no blind replay')
        raise
    except Exception as exc:
        outcome.update(status='invalid_output', error=repr(exc))
    finally:
        outcome.update(terminal=True, completed=time.time())
        write_json(root / 'outcomes' / f'{key}.json', outcome)
    return outcome


def validate_saved_keep(directory, key, spec, outcome, adapters=None):
    import jsonschema
    candidate = load(directory / 'candidates' / f'{key}.json')
    states = {}
    for stage, schema in [('generate', specs.schema(spec['family'])), ('review', specs.REVIEW_SCHEMA)]:
        state = load(directory / 'stages' / f'{key}-{stage}.json')
        request = load(directory / 'requests' / f'{key}-{stage}.json')
        expected = specs.generation_request(spec) if stage == 'generate' else specs.review_request(spec, candidate)
        if (state.get('status') != 'complete' or state['raw']['finish_reason'] != 'stop'
                or stages_api.strict_json(state['raw']['content']) != state['output']
                or request['request'] != expected or request['schema'] != schema
                or state['request_sha256'] != digest(expected)):
            raise ValueError('Stage/raw/request binding failed')
        jsonschema.validate(state['output'], schema)
        states[stage] = state
    rebuilt = student_check(specs.assemble(spec, states['generate']['output']))
    if (rebuilt != candidate or states['review']['output']['verdict'] != 'keep'
            or digest({k: candidate[k] for k in ('messages', 'tools')}) != outcome['fingerprint']):
        raise ValueError('Accepted candidate binding failed')
    return candidate, []


def controller(config):
    c = isolation._private_module('multilingual_quarter')
    v6 = isolation._private_module('multilingual_calibration_v6')
    v6.Budget, v6.endpoint_limit = runtime.Budget, runtime.endpoint_limit
    expected = f"http://127.0.0.1:{8800 + config['shard']}/v1"
    def endpoints(values):
        if values != [expected]:
            raise ValueError('Client may only use its designated shared endpoint')
    v6.validate_endpoints = endpoints
    v6.adapters = lambda: (None, None)
    pilot = isolation._private_module('multilingual_pilot_v6')
    pilot.v6, pilot.process = v6, process
    c.v6, c.pilot = v6, pilot
    c.VERSION, c.POLICY = VERSION, POLICY
    c.milestone_targets = quotas
    c.verify = lambda root: verify(root, c)
    c.validate_saved_keep = validate_saved_keep
    # The private streaming module uses the equivalence-tested faster guard.
    streaming = isolation._private_module('calibration_streaming')
    from .calibration_loop_guard_fast import LoopGuard
    streaming.LoopGuard = LoopGuard
    c.stream_query = streaming.stream_query
    original_gate = c.AdmissionGate
    class Gate(original_gate):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, spacing=0)
            # This new campaign is explicitly authorized alongside the existing
            # 90%-KV clients. Only the private gate uses the higher threshold.
            self.max_kv = .98
    c.AdmissionGate = Gate
    base_metrics = c.admission_metrics
    def metrics(text):
        from prometheus_client.parser import text_string_to_metric_families
        values = [float(s.value) for f in text_string_to_metric_families(text)
                  for s in f.samples if s.name == 'vllm:num_requests_running']
        if not values:
            raise ValueError('Missing running-request metric')
        result = base_metrics(text)
        # Per-process64 is a hard bound; the sibling adds at most another64.
        if max(values) >= 1024 or result['waiting'] > 128:
            result['waiting'] = max(1, result['waiting'])
        else:
            result['waiting'] = 0
        return result
    c.admission_metrics = metrics
    def report(path, value):
        if Path(path).name in ('runtime.json', 'admission-status.json'):
            value = dict(value, max_kv_cache_utilization=.98, admission_waiting_limit=128,
                admission_running_limit=1024, admission_spacing_seconds=0,
                combined_tlpc_concurrency_per_endpoint=128)
        write_json(path, value)
    c.write_json = report
    return c


def dependencies():
    names = ['tlpc_grounded_campaign', 'tlpc_grounded_specs', 'tlpc_sources',
        'multilingual_quarter', 'multilingual_pilot_v6', 'wave_synthetic_runtime',
        'calibration_streaming', 'calibration_loop_guard_fast', 'io',
        'european_synthetic_campaign', 'multilingual_pilot', 'multilingual_generation_v4', 'prepare']
    paths = {Path(__file__).with_name(n + '.py').resolve() for n in names}
    paths.update(p.resolve() for p in stages_api.implementation_paths())
    paths.add(Path('scripts/tokenize_chat_template.py').resolve())
    return sorted(paths)


def prepare(root, sources, tokenizer=isolation.TOKENIZER_DIR):
    root, sources, tokenizer = map(lambda p: Path(p).resolve(), (root, sources, tokenizer))
    receipt = load(sources / 'receipt.json')
    if not receipt['complete'] or not receipt['generation_ready']:
        raise ValueError('Source preparation not complete')
    root.mkdir(parents=True, exist_ok=False)
    pins = {str(p): file_hash(p) for p in dependencies()}
    assets = {str(p): file_hash(p) for p in isolation._asset_paths(tokenizer)}
    clients = []
    for shard in range(8):
        source = receipt['shards'][shard]
        if file_hash(source['path']) != source['sha256']:
            raise ValueError('Source SQLite changed')
        for family in specs.FAMILIES:
            client = root / f"shard-{shard}-{'qa' if family == specs.FAMILIES[0] else 'chat'}"
            client.mkdir()
            config = dict(shard=shard, family=family, campaign=f'{VERSION}-{shard}-{family}')
            c = controller(config)
            provider = specs.SourceProvider(Path(source['path']).parent, client, config)
            available = len(provider.keys); provider.close()
            target = quotas(config)[0]['accepted_target']
            if available * 6 < target:
                raise ValueError(f'Insufficient bounded source supply: {client.name} {available}')
            with lock(client / 'controller.lock'):
                ledger = c.Ledger(client / 'jobs.sqlite')
                try:
                    ledger.initialize(quotas(config))
                    write_json(client / 'config.json', config)
                    manifest = dict(version=VERSION, campaign=config['campaign'], policy=POLICY,
                        target=target, groups=1, candidate_multiplier=6, source_documents=available,
                        provider='dfm12.tlpc_grounded_specs', seeds_root=str(Path(source['path']).parent),
                        tokenizer_dir=str(tokenizer), shard=shard, family=family,
                        endpoint=f'http://127.0.0.1:{8800+shard}/v1', max_concurrency_per_server=64,
                        max_kv_cache_utilization=.98, admission_waiting_limit=128, admission_running_limit=1024,
                        implementation_pins=pins, external_pins=dict(assets, **{
                            source['path']: source['sha256'], str(sources / 'receipt.json'): file_hash(sources / 'receipt.json')}),
                        input_pins={'config.json': file_hash(client / 'config.json')},
                        overlap_complete=False, export_requires_terminal_review_and_overlap=True)
                    write_json(client / 'manifest.json', manifest)
                    seal = file_hash(client / 'manifest.json')
                    write_json(client / 'seal.json', {'manifest_sha256': seal})
                    ledger.db.execute('INSERT INTO metadata VALUES(?,?)', ('manifest_sha256', seal))
                    ledger.report(client, 'prepared')
                finally:
                    ledger.close()
            clients.append(dict(root=str(client), manifest_sha256=seal, target=target))
    write_json(root / 'campaign.json', dict(version=VERSION, target=100000, clients=clients,
        tasks={'grounded-qa':60000, 'grounded-chat':40000}, policy=POLICY))
    return clients


def verify(root, c=None):
    root = Path(root).resolve()
    m = load(root / 'manifest.json'); config = load(root / 'config.json')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Manifest seal drift')
    if m['version'] != VERSION or m['policy'] != POLICY or m['target'] != quotas(config)[0]['accepted_target']:
        raise ValueError('Policy drift')
    stages_api.verify_pins(root, m)
    c = c or controller(config)
    with sqlite3.connect((root / 'jobs.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        c.verify_ledger(db, m, config)
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] != file_hash(root / 'manifest.json'):
            raise ValueError('Ledger seal drift')
    return m


async def run(root):
    root = Path(root).resolve(); m = verify(root)
    renderer()
    c = controller(load(root / 'config.json'))
    await c.execute(root, endpoints=[m['endpoint']], concurrency=64, timeout=600,
                    max_kv_cache_utilization=.80)


async def pilot(root):
    """One real allocation per task/client, same contracts and durable ledger."""
    import aiohttp
    root = Path(root).resolve(); m = verify(root)
    c = controller(load(root / 'config.json')); renderer()
    with lock(root / 'controller.lock'):
        ledger = c.Ledger(root / 'jobs.sqlite')
        provider = specs.SourceProvider(Path(m['seeds_root']), root, load(root / 'config.json'))
        try:
            ledger.recover(m['campaign'])
            if ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]:
                raise ValueError('Pilot only on a fresh client ledger; never repeat controls silently')
            endpoint = m['endpoint']
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.get(endpoint + '/models', timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response.raise_for_status(); health = {endpoint: await response.json()}
                runtime.endpoint_limit(health[endpoint])
                gate = c.AdmissionGate(session,[endpoint],__import__('collections').Counter(),health,asyncio.Event(),.8)
                await gate.admit(endpoint)
                job = ledger.reserve(provider, specs.SeedUnavailable, root)
                if job is None:
                    raise ValueError('No pilot source')
                stage = c.v6.Stages(job['workdir'],runtime.Budget(m['tokenizer_dir']),
                    c.v6.RawResponseWriter(job['workdir']/'raw'),session,query=c.stream_query)
                outcome = await process(job['spec'],endpoint,job['workdir'],stage,health,None,None,c.Seen(ledger,job['id']))
                if outcome.get('effective_keep'):
                    c.materialize(job['workdir'],job['id'],outcome,m['campaign'])
                ledger.finish(job['id'],outcome)
                write_json(root/'pilot-result.json',outcome)
                ledger.report(root,'pilot_finished')
        finally:
            provider.close(); ledger.close()


def export(root, output, overlap_receipt):
    """Terminal-only, strict revalidation; no automatic upload or training mutation."""
    root, output = Path(root), Path(output)
    campaign = load(root / 'campaign.json')
    screen = load(overlap_receipt)
    if (screen.get('campaign_sha256') != file_hash(root / 'campaign.json')
            or screen.get('inherited_complete') is not True or screen.get('heldout_complete') is not True
            or not screen.get('evidence_pins')):
        raise ValueError('Full hash-bound inherited/heldout screening evidence required')
    for path, sha in screen['evidence_pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Overlap evidence drift')
    denied = set(screen.get('excluded_candidate_ids', []))
    output.mkdir(parents=True, exist_ok=False)
    seen = sqlite3.connect(output / 'fingerprints.sqlite')
    seen.execute('CREATE TABLE seen(hash TEXT PRIMARY KEY)')
    counts = {f:0 for f in specs.FAMILIES}; excluded = duplicates = 0
    from contextlib import ExitStack
    with ExitStack() as stack:
        for item in campaign['clients']:
            stack.enter_context(lock(Path(item['root']) / 'controller.lock'))
        with atomic(output / 'accepted.jsonl') as handle:
            for item in campaign['clients']:
                client = Path(item['root']); m = verify(client)
                if file_hash(client / 'manifest.json') != item['manifest_sha256']:
                    raise ValueError('Client binding drift')
                with sqlite3.connect((client / 'jobs.sqlite').as_uri()+'?mode=ro', uri=True) as db:
                    if db.execute('SELECT sum(active),sum(accepted),sum(target) FROM groups').fetchone() != (0,m['target'],m['target']):
                        raise ValueError('Client unfinished; no partial target claim')
                    for key, spec_json, outcome_json, workdir in db.execute("SELECT id,spec_json,outcome_json,workdir FROM jobs WHERE status='accepted'"):
                        row, _ = validate_saved_keep(Path(workdir), key, json.loads(spec_json), json.loads(outcome_json))
                        identity = digest({k: row[k] for k in ('messages','tools')})
                        if identity in denied:
                            excluded += 1; continue
                        from .tlpc_sources import normalize
                        fp = digest([(m['role'], normalize(m['content'])) for m in row['messages']])
                        if not seen.execute('INSERT OR IGNORE INTO seen VALUES(?)', (fp,)).rowcount:
                            duplicates += 1; continue
                        counts[row['family']] += 1
                        row.update(id=identity, audit_evidence=dict(workdir=workdir, key=key),
                                   campaign_manifest_sha256=item['manifest_sha256'])
                        handle.write(json.dumps(row, ensure_ascii=False)+'\n')
    seen.commit(); seen.close()
    ready = counts == campaign['tasks']
    write_json(output / 'receipt.json', dict(ready=ready, counts=counts, duplicates=duplicates,
        excluded=excluded, deficits={f:campaign['tasks'][f]-counts[f] for f in counts},
        sha256=file_hash(output / 'accepted.jsonl'), overlap_receipt_sha256=file_hash(overlap_receipt),
        automatic_upload=False, certified=False,
        next_action='release review' if ready else 'replenish deficits in separately sealed successor; do not integrate'))
    return ready


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','verify','run','pilot','export'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--sources', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--overlap-receipt', type=Path)
    a = p.parse_args()
    if a.command == 'prepare':
        print(prepare(a.root, a.sources))
    elif a.command == 'verify':
        print(verify(a.root))
    elif a.command == 'run':
        asyncio.run(run(a.root))
    elif a.command == 'pilot':
        asyncio.run(pilot(a.root))
    else:
        print(export(a.root, a.output, a.overlap_receipt))
