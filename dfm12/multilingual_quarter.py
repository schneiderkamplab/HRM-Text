"""Single-writer quota controller for retained-v6 multilingual production.

SourceProvider owns growing seed inventory; immutable per-slot specs and receipts
are pinned when allocated. No servers, training, export, or upload lifecycle.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import contextmanager
import importlib
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import time

from . import multilingual_calibration_v6 as v6
from . import multilingual_pilot_v6 as pilot
from .calibration_streaming import stream_query
from .io import digest, file_hash, load, lock, write_json

VERSION = 'multilingual-quarter-v6'
PROVIDER = 'dfm12.multilingual_production_specs'
CONFIG = Path(__file__).with_name('multilingual_extension.yaml')
POLICY = dict(automatic_upload=False, automatic_export=False, training_changed=False,
              native_quality_certified=False, accepted_basis='user-authorized retained-v6 automated gates')
MILESTONES = {'quarter': (4, 962500), 'tenth': (10, 385000)}


def milestone_targets(config, milestone='quarter', divisor=None):
    """Override only the cumulative divisor; never rewrite provider config."""
    import copy
    from .multilingual_targets import targets
    if milestone not in MILESTONES:
        raise ValueError('Unsupported production milestone')
    expected_divisor, total = MILESTONES[milestone]
    if divisor is not None and (type(divisor) is not int or divisor != expected_divisor):
        raise ValueError('Milestone divisor mismatch')
    specification = copy.deepcopy(config)
    specification['milestone_divisors'][milestone] = expected_divisor
    quotas = targets(specification, milestone)
    if len(quotas) != 42 or sum(q['accepted_target'] for q in quotas) != total:
        raise ValueError('Milestone authorization requires exact 42-group target')
    return quotas


def verify_ledger(db, manifest, config):
    expected = {(q['language'],q['family']):q['accepted_target'] for q in
                milestone_targets(config, manifest.get('milestone','quarter'), manifest.get('milestone_divisor'))}
    groups = db.execute('SELECT language,family,target,accepted,active,attempts FROM groups').fetchall()
    if {(g[0],g[1]):g[2] for g in groups} != expected:
        raise ValueError('Ledger targets disagree with sealed milestone')
    for _,_,target,accepted,active,attempts in groups:
        if min(accepted,active,attempts) < 0 or accepted+active > target or attempts > 6*target:
            raise ValueError('Ledger quota invariant violated')
    seal = db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
    if not seal:
        raise ValueError('Missing SQLite campaign seal')


def work_root(root, key):
    return Path(root) / 'work' / key[:2] / key[2:4]


def candidate_id(campaign, fingerprint):
    return digest({'campaign': campaign, 'fingerprint': fingerprint})


class Ledger:
    """All mutating calls run synchronously on the sole event-loop thread."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS groups (
            language TEXT, family TEXT, target INTEGER NOT NULL,
            accepted INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0, next_slot INTEGER NOT NULL DEFAULT 100000,
            retry_at REAL NOT NULL DEFAULT 0, blocked TEXT,
            PRIMARY KEY(language,family), CHECK(accepted >= 0 AND active >= 0),
            CHECK(accepted+active <= target), CHECK(attempts <= 6*target));
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, language TEXT, family TEXT, slot INTEGER,
            status TEXT NOT NULL, origin TEXT NOT NULL, spec_json TEXT,
            fingerprint TEXT, outcome_json TEXT, workdir TEXT,
            UNIQUE(language,family,slot,origin));
          CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
          CREATE TABLE IF NOT EXISTS fingerprints (fingerprint TEXT PRIMARY KEY, owner TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        self.allowed_groups = None

    def restrict_groups(self, groups):
        selected = frozenset(tuple(group) for group in groups)
        known = set(map(tuple, self.db.execute('SELECT language,family FROM groups')))
        if not selected or not selected <= known:
            raise ValueError('Approval must name existing language/family groups')
        self.allowed_groups = selected

    def remaining_groups(self):
        groups = self.db.execute('SELECT * FROM groups WHERE accepted < target AND attempts < 6*target').fetchall()
        return [g for g in groups if self.allowed_groups is None or
                (g['language'], g['family']) in self.allowed_groups]

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def initialize(self, targets):
        with self.transaction():
            for row in targets:
                self.db.execute('INSERT INTO groups(language,family,target) VALUES(?,?,?)',
                    (row['language'], row['family'], row['accepted_target']))

    def reserve(self, provider, unavailable, root):
        """Provider shortage does not advance slot or consume candidate budget."""
        now = time.time()
        groups = self.db.execute('''SELECT * FROM groups WHERE accepted+active < target
            AND attempts < target*6 AND retry_at <= ?
            ORDER BY CAST(attempts AS REAL)/target, language,family''', (now,)).fetchall()
        for group in groups:
            language, family, slot = group['language'], group['family'], group['next_slot']
            if self.allowed_groups is not None and (language, family) not in self.allowed_groups:
                continue
            try:
                spec = provider.next_spec(language, family, slot)
            except unavailable as exc:
                self.db.execute('UPDATE groups SET retry_at=?,blocked=? WHERE language=? AND family=?',
                    (now+5, 'seed_shortage: '+str(exc), language, family))
                continue
            if not isinstance(spec, dict) or (spec.get('language_code'), spec.get('family'), spec.get('slot')) != (language, family, slot):
                raise ValueError('Provider returned wrong slot identity')
            if type(spec.get('contract_version')) is not int or spec['contract_version'] != 4:
                raise ValueError('Provider must return contract-v4 spec')
            key = pilot.slot_key(spec)
            directory = work_root(root, key)
            with self.transaction():
                updated = self.db.execute('''UPDATE groups SET active=active+1,attempts=attempts+1,
                    next_slot=next_slot+1,blocked=NULL,retry_at=0 WHERE language=? AND family=?
                    AND accepted+active < target AND attempts < target*6 AND next_slot=?''',
                    (language, family, slot)).rowcount
                if updated != 1:
                    raise RuntimeError('Reservation race')
                self.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,spec_json,workdir) VALUES(?,?,?,?,?,?,?,?)',
                    (key, language, family, slot, 'running', 'production', json.dumps(spec, ensure_ascii=False), str(directory)))
            write_json(directory / 'specifications' / f'{key}.json', dict(spec=spec, spec_sha256=digest(spec)))
            return dict(id=key, spec=spec, workdir=directory)
        return None

    def finish(self, key, outcome):
        """Quota increment and terminal transition commit together, exactly once."""
        with self.transaction():
            job = self.db.execute('SELECT * FROM jobs WHERE id=?', (key,)).fetchone()
            if job is None:
                raise ValueError('Unknown job')
            if job['status'] != 'running':
                return False
            spec = json.loads(job['spec_json'])
            if outcome.get('id') != key or outcome.get('spec_sha256') != digest(spec) or outcome.get('terminal') is not True:
                raise ValueError('Terminal outcome identity mismatch')
            accepted = outcome.get('terminal') is True and outcome.get('status') == 'valid' and outcome.get('effective_keep') is True
            fingerprint = outcome.get('fingerprint')
            if accepted:
                owner = self.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?', (fingerprint,)).fetchone()
                if not owner or owner['owner'] != key:
                    raise ValueError('Accepted candidate lacks owned unique fingerprint')
            status = 'accepted' if accepted else outcome.get('status', 'abort_status_unknown')
            if status == 'running':
                status = 'abort_status_unknown'
            self.db.execute('UPDATE jobs SET status=?,fingerprint=?,outcome_json=? WHERE id=?',
                (status, fingerprint, json.dumps(outcome, ensure_ascii=False), key))
            self.db.execute('UPDATE groups SET active=active-1,accepted=accepted+? WHERE language=? AND family=?',
                (int(accepted), job['language'], job['family']))
            return accepted

    def recover(self, campaign=None):
        # Indexed query touches only interrupted allocations, never the full corpus.
        for job in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
            path = Path(job['workdir']) / 'outcomes' / f"{job['id']}.json"
            outcome = load(path) if path.exists() else {}
            spec = json.loads(job['spec_json'])
            if outcome.get('terminal') is not True:
                outcome = dict(pilot.base_outcome(spec), terminal=True, status='abort_status_unknown',
                               error='Interrupted production allocation; no automatic replay')
                write_json(path, outcome)
            elif outcome.get('id') != job['id'] or outcome.get('spec_sha256') != digest(spec):
                raise ValueError('Recovered outcome identity drift')
            if outcome.get('status') == 'valid' and outcome.get('effective_keep') is True:
                validate_saved_keep(Path(job['workdir']), job['id'], spec, outcome)
                if campaign is None:
                    raise ValueError('Campaign required to recover accepted record')
                materialize(Path(job['workdir']), job['id'], outcome, campaign)
            self.finish(job['id'], outcome)

    def report(self, root, phase):
        groups = [dict(row) for row in self.db.execute('SELECT * FROM groups ORDER BY language,family')]
        report = dict(version=VERSION, pid=os.getpid(), phase=phase, time=time.time(),
            target=sum(g['target'] for g in groups), accepted=sum(g['accepted'] for g in groups),
            active=sum(g['active'] for g in groups), candidates=sum(g['attempts'] for g in groups),
            candidate_limit=sum(6*g['target'] for g in groups), groups=groups, **POLICY)
        report['remaining'] = report['target'] - report['accepted']
        if self.allowed_groups is not None:
            report['approved_groups'] = sorted(self.allowed_groups)
            report['deferred_target'] = sum(g['target']-g['accepted'] for g in groups
                if (g['language'], g['family']) not in self.allowed_groups)
            report['approved_remaining'] = report['remaining'] - report['deferred_target']
        report['budget_exhausted_groups'] = sum(g['accepted'] < g['target'] and g['attempts'] >= 6*g['target'] and not g['active'] for g in groups)
        write_json(Path(root) / 'progress.json', report)
        return report

    def close(self):
        self.db.close()


class Seen:
    """Duck-typed set used by frozen pilot.process; durable global uniqueness."""
    def __init__(self, ledger, owner):
        self.ledger, self.owner = ledger, owner

    def __contains__(self, fingerprint):
        return self.ledger.db.execute('SELECT 1 FROM fingerprints WHERE fingerprint=?', (fingerprint,)).fetchone() is not None

    def add(self, fingerprint):
        self.ledger.db.execute('INSERT INTO fingerprints VALUES(?,?)', (fingerprint, self.owner))


def validate_saved_keep(directory, key, spec, outcome, adapters=None):
    """Use original strict schema and raw text, not merely saved keep booleans."""
    import jsonschema
    review, generation = adapters or v6.adapters()
    candidate_path = directory / 'candidates' / f'{key}.json'
    generate_path = directory / 'stages' / f'{key}-generate.json'
    review_path = directory / 'stages' / f'{key}-review.json'
    request_path = directory / 'requests' / f'{key}-review.json'
    candidate, gen, audited, request = map(load, (candidate_path, generate_path, review_path, request_path))
    fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
    if fingerprint != outcome.get('fingerprint') or gen.get('status') != 'complete' or audited.get('status') != 'complete':
        raise ValueError('Candidate or stage mismatch')
    for state in (gen, audited):
        if state.get('raw', {}).get('finish_reason') != 'stop' or v6.strict_json(state['raw']['content']) != state['output']:
            raise ValueError('Raw stage output mismatch or incomplete')
    if digest(v6.generation_assemble(spec, gen['output'], generation)) != digest(candidate):
        raise ValueError('Generation assembly mismatch')
    record = v6.audit_record(candidate)
    strict_schema = review.schema(record)
    if request['schema'] != strict_schema:
        raise ValueError('Pilot was not reviewed under retained strict schema')
    if audited.get('request_sha256') != digest(request['request']):
        raise ValueError('Review request hash mismatch')
    jsonschema.validate(audited['output'], strict_schema)
    if not v6.review_result(audited['output'], record, review)['effective_keep']:
        raise ValueError('Keep fails independent CPU recheck')
    return candidate, [candidate_path, generate_path, review_path, request_path]


def materialize(directory, key, outcome, campaign):
    candidate = load(directory / 'candidates' / f'{key}.json')
    fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
    if fingerprint != outcome['fingerprint']:
        raise ValueError('Candidate fingerprint mismatch')
    candidate['id'] = candidate_id(campaign, fingerprint)
    write_json(directory / 'accepted' / f'{key}.json', candidate)


def pilot_import(ledger, source, root, expected=16850):
    """Revalidate completed pilot decisions, pin every imported evidence file."""
    manifest, specs, _ = pilot.verify(source)
    review, generation = v6.adapters()
    count, file_pins, group_attempts = 0, {}, Counter()
    # Imported accepts count within the original pilot's attempted-slot totals.
    with ledger.transaction():
        for fingerprint in load(source / 'previous-hashes.json'):
            ledger.db.execute('INSERT OR IGNORE INTO fingerprints VALUES(?,?)', (fingerprint, 'prior-history'))
        for spec in specs:
            key = pilot.slot_key(spec)
            path = source / 'outcomes' / f'{key}.json'
            outcome = load(path)
            if outcome.get('terminal') is not True:
                raise ValueError('Pilot must be entirely terminal before production import')
            if outcome.get('id') != key or outcome.get('spec_sha256') != digest(spec):
                raise ValueError('Pilot outcome identity mismatch')
            group_attempts[(spec['language_code'], spec['family'])] += 1
            if outcome.get('status') != 'valid' or outcome.get('effective_keep') is not True:
                continue
            candidate, evidence = validate_saved_keep(source, key, spec, outcome, (review, generation))
            fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
            if ledger.db.execute('SELECT 1 FROM fingerprints WHERE fingerprint=?', (fingerprint,)).fetchone():
                raise ValueError('Duplicate accepted pilot fingerprint')
            ledger.db.execute('INSERT INTO fingerprints VALUES(?,?)', (fingerprint, key))
            ledger.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,fingerprint,outcome_json,workdir) VALUES(?,?,?,?,?,?,?,?,?)',
                (key, spec['language_code'], spec['family'], spec['slot'], 'accepted', 'pilot', fingerprint,
                 json.dumps(outcome, ensure_ascii=False), str(source)))
            updated = ledger.db.execute('UPDATE groups SET accepted=accepted+1 WHERE language=? AND family=? AND accepted<target',
                (spec['language_code'], spec['family'])).rowcount
            if updated != 1:
                raise ValueError('Pilot group exceeds target')
            for pinned in (path, *evidence):
                file_pins[str(pinned.resolve())] = file_hash(pinned)
            count += 1
            if count % 1000 == 0:
                print(f'Pilot import: {count}/{expected} strict verified keeps', flush=True)
        if count != expected:
            raise ValueError(f'Expected {expected} verified pilot accepts, got {count}')
        for (language, family), attempts in group_attempts.items():
            ledger.db.execute('UPDATE groups SET attempts=? WHERE language=? AND family=?', (attempts, language, family))
        # Retain rejection fingerprints too; a repeated rejected conversation is not new supply.
        for path in (source / 'candidates').glob('*.json'):
            candidate = load(path)
            fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
            ledger.db.execute('INSERT OR IGNORE INTO fingerprints VALUES(?,?)', (fingerprint, 'pilot-history'))
    receipt = dict(accepted=count, candidate_attempts=sum(group_attempts.values()),
        source=str(source.resolve()), source_manifest_sha256=file_hash(source / 'manifest.json'),
        evidence_pins=file_pins, **POLICY)
    write_json(root / 'pilot-import.json', receipt)
    return manifest, receipt


def prepare(root, source, seeds_root, config_path=CONFIG, expected_pilot=16850, milestone='quarter'):
    import yaml
    root, source, seeds_root = map(lambda p: Path(p).resolve(), (root, source, seeds_root))
    if root.exists():
        raise ValueError('Prepare requires a new production root')
    provider = importlib.import_module(PROVIDER)
    config = yaml.safe_load(Path(config_path).read_text())
    quotas = milestone_targets(config, milestone)
    root.mkdir(parents=True)
    with lock(root / 'controller.lock'):
        ledger = Ledger(root / 'jobs.sqlite')
        try:
            ledger.initialize(quotas)
            donor, receipt = pilot_import(ledger, source, root, expected_pilot)
            write_json(root / 'config.json', config)
            dependencies = [Path(__file__), Path(pilot.__file__), Path(provider.__file__),
                Path(__file__).with_name('multilingual_targets.py'), *v6.implementation_paths()]
            manifest = dict(version=VERSION, campaign=config['campaign'], pilot=str(source), seeds_root=str(seeds_root),
                tokenizer_dir=donor['tokenizer_dir'], target=MILESTONES[milestone][1], candidate_multiplier=6,
                milestone=milestone, milestone_divisor=MILESTONES[milestone][0],
                provider=PROVIDER, external_pins=donor['external_pins'],
                implementation_pins={str(p.resolve()): file_hash(p) for p in dependencies},
                input_pins={name: file_hash(root / name) for name in ('config.json', 'pilot-import.json')},
                policy=POLICY, seed_inventory='growing; exact provider specifications pinned per allocation')
            write_json(root / 'manifest.json', manifest)
            write_json(root / 'seal.json', {'manifest_sha256': file_hash(root / 'manifest.json')})
            ledger.db.execute('INSERT INTO metadata VALUES(?,?)', ('manifest_sha256', file_hash(root / 'manifest.json')))
            ledger.report(root, 'prepared')
        finally:
            ledger.close()


def verify(root):
    root = Path(root)
    manifest = load(root / 'manifest.json')
    milestone = manifest.get('milestone','quarter')
    if (milestone not in MILESTONES or manifest.get('version') != VERSION
            or manifest.get('target') != MILESTONES[milestone][1] or manifest.get('policy') != POLICY
            or manifest.get('candidate_multiplier') != 6):
        raise ValueError('Production policy drift')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Production manifest seal drift')
    v6.verify_pins(root, manifest)
    for path, expected in load(root / 'pilot-import.json')['evidence_pins'].items():
        if file_hash(path) != expected:
            raise ValueError('Imported pilot evidence drift: ' + path)
    with sqlite3.connect((root / 'jobs.sqlite').resolve().as_uri()+'?mode=ro', uri=True) as db:
        verify_ledger(db,manifest,load(root/'config.json'))
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] != file_hash(root/'manifest.json'):
            raise ValueError('SQLite campaign seal mismatch; complete any offline migration')
    return manifest


def admission_metrics(text):
    from prometheus_client.parser import text_string_to_metric_families
    samples = {'kv': [], 'waiting': []}
    names = {'vllm:kv_cache_usage_perc': 'kv', 'vllm:gpu_cache_usage_perc': 'kv',
             'vllm:num_requests_waiting': 'waiting'}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            key = names.get(sample.name)
            if key:
                value = float(sample.value)
                if not math.isfinite(value) or value < 0 or (key == 'kv' and value > 1):
                    raise ValueError('Invalid admission metric: ' + sample.name)
                samples[key].append(value)
    if not all(samples.values()):
        raise ValueError('Missing KV utilization or waiting metric')
    return {key: max(values) for key, values in samples.items()}


async def stop_wait(stop, seconds):
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(0, seconds))
        return False
    except asyncio.TimeoutError:
        return not stop.is_set()


class AdmissionGate:
    """Only new reservations wait here; in-flight generation/review never does."""
    def __init__(self, session, endpoints, failures, health, stop, max_kv=.90,
                 spacing=.2, cooldown=30, poll=2):
        if type(max_kv) not in (int, float) or not 0 < max_kv <= .90:
            raise ValueError('KV admission threshold must be positive and <=0.90')
        self.session, self.failures, self.health, self.stop = session, failures, health, stop
        self.max_kv, self.spacing, self.cooldown, self.poll = max_kv, spacing, cooldown, poll
        self.locks = {e: asyncio.Lock() for e in endpoints}
        self.next_at, self.recover_at, self.paused = {}, {}, {}
        self.circuit_generation = Counter()
        self.status = {e: dict(reason='awaiting_metrics', admissions=0, recoveries=0, probe_failures=0) for e in endpoints}

    def trip(self, endpoint):
        self.circuit_generation[endpoint] += 1
        self.recover_at[endpoint] = time.monotonic() + self.cooldown

    async def admit(self, endpoint, can_continue=lambda: True):
        import aiohttp
        async with self.locks[endpoint]:
            info = self.status[endpoint]
            while not self.stop.is_set() and can_continue():
                if endpoint in self.paused:
                    info['reason'] = self.paused[endpoint]
                    if not await stop_wait(self.stop, self.poll):
                        return False
                    continue
                if self.failures[endpoint] >= 3 and endpoint not in self.recover_at:
                    self.trip(endpoint)
                deadline = max(self.next_at.get(endpoint,0), self.recover_at.get(endpoint,0))
                if deadline > time.monotonic():
                    info['reason'] = 'circuit_cooldown' if endpoint in self.recover_at else 'spacing'
                    if not await stop_wait(self.stop, min(deadline-time.monotonic(), self.poll)):
                        return False
                    continue
                try:
                    timeout = aiohttp.ClientTimeout(total=4)
                    recovery_deadline = self.recover_at.get(endpoint)
                    recovery_generation = self.circuit_generation[endpoint]
                    if recovery_deadline is not None:
                        async with self.session.get(endpoint+'/models', timeout=timeout) as response:
                            response.raise_for_status()
                            document = await response.json()
                            v6.endpoint_limit(document)
                    async with self.session.get(endpoint.removesuffix('/v1')+'/metrics', timeout=timeout) as response:
                        response.raise_for_status()
                        sample = admission_metrics(await response.text())
                    info.update(sample, checked=time.time())
                    if endpoint in self.paused:
                        continue
                    if (self.circuit_generation[endpoint] != recovery_generation
                            or self.recover_at.get(endpoint) != recovery_deadline):
                        continue  # New trip invalidates even a completed health probe.
                    if recovery_deadline is None and (endpoint in self.recover_at or self.failures[endpoint] >= 3):
                        self.trip(endpoint)
                        continue  # A stage tripped while this probe was in flight.
                    if sample['kv'] > self.max_kv or sample['waiting'] != 0:
                        info['reason'] = 'shared_server_busy'
                        self.next_at[endpoint] = time.monotonic()+self.poll
                        continue
                    # No awaits between recovery and permit: only this endpoint's
                    # serialized probe resets the circuit for new candidate work.
                    if endpoint in self.recover_at:
                        self.health[endpoint] = document
                        self.failures[endpoint] = 0
                        del self.recover_at[endpoint]
                        info['recoveries'] += 1
                    if self.stop.is_set() or not can_continue():
                        return False
                    self.next_at[endpoint] = time.monotonic()+self.spacing
                    info.update(reason='admitted', admissions=info['admissions']+1)
                    return True
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as exc:
                    info.update(reason='probe_failed', last_error=repr(exc), probe_failures=info['probe_failures']+1)
                    self.next_at[endpoint] = time.monotonic()+self.poll
                    if endpoint in self.recover_at:
                        self.recover_at[endpoint] = time.monotonic()+self.cooldown
            return False


async def execute(root, endpoints=pilot.ENDPOINTS, concurrency=32, timeout=600, max_kv_cache_utilization=.90,
                  allowed_groups=None):
    import aiohttp
    root = Path(root).resolve()
    v6.validate_endpoints(endpoints)
    if type(concurrency) is not int or not 1 <= concurrency <= 64 or not 1 <= timeout <= 600:
        raise ValueError('Concurrency <=64 per server; timeout <=600 seconds')
    if type(max_kv_cache_utilization) not in (int,float) or not 0 < max_kv_cache_utilization <= .90:
        raise ValueError('KV admission threshold must be positive and <=0.90')
    with lock(root / 'controller.lock'):
        manifest = verify(root)
        ledger = Ledger(root / 'jobs.sqlite')
        if allowed_groups is not None:
            ledger.restrict_groups(allowed_groups)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        phase, tasks = 'preflight', []
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        try:
            seal = ledger.db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()
            if not seal or seal['value'] != file_hash(root / 'manifest.json'):
                raise ValueError('SQLite campaign seal mismatch')
            ledger.recover(manifest['campaign'])
            provider_module = importlib.import_module(manifest['provider'])
            provider = provider_module.SourceProvider(Path(manifest['seeds_root']), root, load(root / 'config.json'))
            review, generation = v6.adapters()
            budget = v6.Budget(manifest['tokenizer_dir'])
            failures = Counter()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4),
                    connector=aiohttp.TCPConnector(limit=len(endpoints))) as monitor, \
                    aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=aiohttp.TCPConnector(limit=8*concurrency, limit_per_host=concurrency)) as session:
                async def healthcheck(endpoint):
                    async with monitor.get(endpoint + '/models') as response:
                        response.raise_for_status()
                        document = await response.json()
                        v6.endpoint_limit(document)
                        return endpoint, document
                health = dict(await asyncio.gather(*(healthcheck(e) for e in endpoints)))
                gate = AdmissionGate(monitor,endpoints,failures,health,stop,max_kv_cache_utilization)
                write_json(root / f'health-{time.time_ns()}.json', health)
                v6.verify_pins(root, manifest)
                write_json(root / 'runtime.json', dict(pid=os.getpid(), started=time.time(),
                    endpoints=endpoints, concurrency_per_server=concurrency,
                    max_http_requests=len(endpoints)*concurrency, timeout=timeout,
                    max_kv_cache_utilization=max_kv_cache_utilization, admission_waiting_limit=0,
                    admission_spacing_seconds=.2, circuit_cooldown_seconds=30,
                    manifest_sha256=file_hash(root / 'manifest.json'), **POLICY))
                phase = 'running'

                async def worker(endpoint):
                    def has_remaining():
                        return bool(ledger.remaining_groups())
                    while not stop.is_set():
                        if not await gate.admit(endpoint,has_remaining):
                            return
                        job = ledger.reserve(provider, provider_module.SeedUnavailable, root)
                        if job is None:
                            unfinished = ledger.remaining_groups()
                            if not unfinished:
                                return
                            await stop_wait(stop,5)
                            continue
                        stages = v6.Stages(job['workdir'], budget,
                            v6.RawResponseWriter(job['workdir'] / 'raw'), session, query=stream_query)
                        stages.failures = failures
                        outcome = await pilot.process(job['spec'], endpoint, job['workdir'], stages,
                            health, generation, review, Seen(ledger, job['id']))
                        if failures[endpoint] >= 3:
                            gate.trip(endpoint)
                        if outcome.get('status','').endswith('http_rejected'):
                            gate.paused[endpoint] = 'nontransient_http_rejection_requires_operator'
                        if outcome.get('effective_keep') is True:
                            # Stable identity independent of milestone or campaign progress.
                            materialize(job['workdir'], job['id'], outcome, manifest['campaign'])
                        ledger.finish(job['id'], outcome)

                async def reporter():
                    while True:
                        ledger.report(root, phase)
                        write_json(root/'admission-status.json',dict(time=time.time(),pid=os.getpid(),
                            max_kv_cache_utilization=max_kv_cache_utilization,endpoints=gate.status))
                        await asyncio.sleep(15)

                tasks = [asyncio.create_task(worker(e)) for e in endpoints for _ in range(concurrency)]
                reporting = asyncio.create_task(reporter())
                try:
                    await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    reporting.cancel()
                    await asyncio.gather(reporting, return_exceptions=True)
                state = ledger.report(root, phase)
                phase = ('drained' if stop.is_set() else 'complete' if not state['remaining']
                         else 'approved_groups_finished' if allowed_groups is not None
                         and state['approved_remaining'] == 0 else 'blocked')
        except BaseException:
            phase = 'interrupted_or_failed'
            raise
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
            try:
                ledger.recover(manifest['campaign'])
                ledger.report(root, phase)
            finally:
                if 'provider' in locals() and callable(getattr(provider, 'close', None)):
                    provider.close()
                ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--pilot', type=Path)
    parser.add_argument('--seeds-root', type=Path)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--expected-pilot', type=int, default=16850)
    parser.add_argument('--milestone', choices=tuple(MILESTONES), default='quarter')
    parser.add_argument('--concurrency-per-server', type=int, default=32)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--max-kv-cache-utilization', type=float, default=.90)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.pilot is None or args.seeds_root is None:
            parser.error('prepare requires --pilot and --seeds-root')
        prepare(args.root, args.pilot, args.seeds_root, args.config, args.expected_pilot, args.milestone)
    elif args.command == 'verify':
        print(verify(args.root)['campaign'])
    else:
        asyncio.run(execute(args.root, concurrency=args.concurrency_per_server, timeout=args.timeout,
                            max_kv_cache_utilization=args.max_kv_cache_utilization))


if __name__ == '__main__':
    main()
