"""Joint single-writer dispatcher; borrowed servers have no lifecycle here.

The user-authorized runtime supersedes standalone concurrency caps, never sealed
generation/review policies, quotas, identifiers, source allocations or retries.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
import importlib
import math
import os
from pathlib import Path
import signal
import time

from . import multilingual_quarter as original
from . import european_synthetic_campaign as european
from .calibration_streaming import stream_query
from .io import file_hash, load, lock, write_json

VERSION = 'joint-synthetic-campaign-v1'
ORIGINAL_ROOT = Path('data/dfm12/multilingual-quarter-native-20260927')
EUROPEAN_ROOT = Path('data/dfm12/european-synthetic-tenth-20260928')
WAIVED_FAMILIES = frozenset(('grounded-instruct', 'multiturn', 'summary-rewrite'))
ENDPOINTS = tuple(original.pilot.ENDPOINTS)


def settings(concurrency=512, timeout=600, spacing=.002, max_kv=.90):
    if type(concurrency) is not int or not 1 <= concurrency <= 1024:
        raise ValueError('Joint concurrency must be 1..1024 per endpoint')
    if type(timeout) is not int or not 1 <= timeout <= 600:
        raise ValueError('Request timeout must be 1..600 seconds')
    if type(spacing) not in (int, float) or not math.isfinite(spacing) or spacing < .002:
        raise ValueError('Admission spacing must be finite and at least .002 seconds')
    if type(max_kv) not in (int, float) or not 0 < max_kv <= .90:
        raise ValueError('KV threshold must be positive and <=.90')
    return dict(version=VERSION, endpoints=list(ENDPOINTS), concurrency_per_server=concurrency,
        max_http_requests=len(ENDPOINTS)*concurrency, timeout=timeout,
        inference_connection_reuse=False,
        admission_spacing_seconds=spacing, max_kv_cache_utilization=max_kv,
        admission_waiting_limit=0, circuit_cooldown_seconds=30,
        authorization='User authorized doubling the joint client ceiling to 1024 requests per GPU',
        supersedes='Standalone per-campaign client concurrency caps only',
        waived_groups=[dict(campaign='original', language='fo', family=f) for f in sorted(WAIVED_FAMILIES)],
        quotas_unchanged=True, generation_review_policies_unchanged=True,
        automatic_upload=False, automatic_export=False, training_changed=False,
        server_lifecycle_owned=False)


class WaivedProvider:
    def __init__(self, provider, unavailable, role):
        self.provider, self.unavailable, self.role = provider, unavailable, role

    def next_spec(self, language, family, slot):
        if self.role == 'original' and language == 'fo' and family in WAIVED_FAMILIES:
            raise self.unavailable('joint runtime waiver; no source selection')
        return self.provider.next_spec(language, family, slot)


@dataclass
class Campaign:
    role: str
    root: Path
    controller: object
    manifest: dict
    ledger: object
    provider: object
    unavailable: type
    budget: object = None
    review: object = None
    generation: object = None

    def waived(self, group):
        return self.role == 'original' and group['language'] == 'fo' and group['family'] in WAIVED_FAMILIES

    def has_remaining(self):
        groups = self.ledger.db.execute('SELECT language,family FROM groups '
            'WHERE accepted < target AND attempts < 6*target').fetchall()
        return any(not self.waived(group) for group in groups)


class FairReservations:
    """Synchronous round-robin: no await between source selection and reservation."""
    def __init__(self, campaigns):
        self.campaigns, self.next_index = campaigns, 0

    def has_remaining(self):
        return any(c.has_remaining() for c in self.campaigns)

    def reserve(self):
        for offset in range(len(self.campaigns)):
            index = (self.next_index+offset) % len(self.campaigns)
            campaign = self.campaigns[index]
            if not campaign.has_remaining():
                continue
            job = campaign.ledger.reserve(campaign.provider, campaign.unavailable, campaign.root)
            if job is not None:
                self.next_index = (index+1) % len(self.campaigns)
                return campaign, job
        return None


def pin_paths(root, campaigns):
    paths = {Path(__file__).resolve(), Path(original.__file__).resolve(),
             Path(european.__file__).resolve(), Path(__file__).with_name('io.py').resolve(),
             Path(__file__).with_name('calibration_streaming.py').resolve()}
    for campaign in campaigns:
        paths.update(Path(p).resolve() for p in campaign.manifest['implementation_pins'])
        paths.update(campaign.root / name for name in ('manifest.json', 'seal.json', 'config.json'))
    return sorted(paths)


def verify_runtime(root):
    manifest = load(root/'manifest.json')
    if manifest.get('version') != VERSION or file_hash(root/'manifest.json') != load(root/'seal.json').get('manifest_sha256'):
        raise ValueError('Joint runtime manifest seal drift')
    if file_hash(root/'config.json') != manifest['config_sha256']:
        raise ValueError('Joint runtime configuration drift')
    for path, expected in manifest['pins'].items():
        if file_hash(path) != expected:
            raise ValueError('Joint runtime pin drift: '+path)
    return manifest


def seal_runtime(root, campaigns, config):
    """Only the new root records cap supersession; old manifests stay immutable."""
    config = dict(config, campaigns={c.role: str(c.root) for c in campaigns})
    if (root/'manifest.json').exists():
        manifest = verify_runtime(root)
        if load(root/'config.json') != config:
            raise ValueError('Joint runtime arguments changed; use a fresh joint root')
        if set(manifest['pins']) != {str(p) for p in pin_paths(root, campaigns)}:
            raise ValueError('Joint runtime dependency inventory drift')
        return manifest
    if any(p.name != 'controller.lock' for p in root.iterdir()):
        raise ValueError('Joint preparation requires an empty root; no silent repin')
    write_json(root/'config.json', config)
    manifest = dict(version=VERSION, config_sha256=file_hash(root/'config.json'),
        campaigns={c.role:dict(root=str(c.root), manifest_sha256=file_hash(c.root/'manifest.json'),
                    sealed_policy=c.manifest['policy']) for c in campaigns},
        pins={str(p):file_hash(p) for p in pin_paths(root,campaigns)})
    write_json(root/'manifest.json', manifest)
    write_json(root/'seal.json', dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify_runtime(root)


def report(root, campaigns, phase, gate=None):
    reports = {}
    for campaign in campaigns:
        state = campaign.ledger.report(campaign.root, phase)
        state['waived_remaining'] = sum(g['target']-g['accepted'] for g in state['groups'] if campaign.waived(g))
        state['eligible_remaining'] = state['remaining']-state['waived_remaining']
        reports[campaign.role] = state
    combined = dict(version=VERSION, pid=os.getpid(), time=time.time(), phase=phase,
        campaigns=reports, **{key:sum(r[key] for r in reports.values()) for key in
        ('target','accepted','active','candidates','remaining','waived_remaining','eligible_remaining')})
    if gate is not None:
        combined['admission'] = gate.status
    write_json(root/'progress.json',combined)
    return combined


def campaign_query(controller):
    async def query(*args, **kwargs):
        try:
            return await stream_query(*args, **kwargs)
        except original.v6.HTTPFailure as exc:
            # Private v6 modules have distinct exception classes. Preserve the
            # retained stage's retry/rejection policy, including exact status.
            raise controller.v6.HTTPFailure(exc.status) from exc
    return query


async def process_one(campaign, job, endpoint, session, failures, health, gate):
    controller = campaign.controller
    stages = controller.v6.Stages(job['workdir'], campaign.budget,
        controller.v6.RawResponseWriter(job['workdir']/'raw'), session, query=campaign_query(controller))
    stages.failures = failures
    outcome = await controller.pilot.process(job['spec'],endpoint,job['workdir'],stages,
        health,campaign.generation,campaign.review,controller.Seen(campaign.ledger,job['id']))
    if failures[endpoint] >= 3:
        gate.trip(endpoint)
    if outcome.get('status','').endswith('http_rejected'):
        gate.paused[endpoint] = 'nontransient_http_rejection_requires_operator'
    if outcome.get('effective_keep') is True:
        controller.materialize(job['workdir'],job['id'],outcome,campaign.manifest['campaign'])
    campaign.ledger.finish(job['id'],outcome)


async def dispatch(campaigns, endpoints, concurrency, session, health, gate, failures, stop):
    queue = FairReservations(campaigns)
    def can_continue():
        return queue.has_remaining() and not all(e in gate.paused for e in endpoints)
    async def worker(endpoint):
        while not stop.is_set():
            if not await gate.admit(endpoint,can_continue):
                return
            reservation = queue.reserve()
            if reservation is None:
                if not queue.has_remaining():
                    return
                await original.stop_wait(stop,5)
                continue
            await process_one(*reservation,endpoint,session,failures,health,gate)
    workers = [asyncio.create_task(worker(endpoint)) for endpoint in endpoints for _ in range(concurrency)]
    try:
        await asyncio.gather(*workers)
    except BaseException:
        # Stop reservations, but let other owned HTTP requests finish normally.
        stop.set()
        await asyncio.gather(*workers,return_exceptions=True)
        raise


async def execute(root, original_root=ORIGINAL_ROOT, european_root=EUROPEAN_ROOT,
                  concurrency=512, timeout=600, spacing=.002, max_kv=.90):
    import aiohttp
    config = settings(concurrency,timeout,spacing,max_kv)
    root, original_root, european_root = (Path(p).resolve() for p in (root,original_root,european_root))
    roots = (root,original_root,european_root)
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a)
           for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('Joint and campaign roots must be distinct, non-nested directories')
    for path in (original_root,european_root):
        if not (path/'jobs.sqlite').is_file():
            raise ValueError('Existing prepared campaign ledger required: '+str(path))
    original.v6.validate_endpoints(list(ENDPOINTS))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    campaigns, signals = [], []
    phase, gate = 'preflight', None
    with ExitStack() as resources:
        # No verification, ledger write, recovery or network before BOTH locks.
        for path in sorted(roots):
            resources.enter_context(lock(path/'controller.lock'))
        controllers = [('original',original_root,original),
                       ('european',european_root,european.isolated_controller())]
        verified = [(role,path,controller,controller.verify(path)) for role,path,controller in controllers]
        # Authorize the joint runtime before opening mutable ledger/provider APIs.
        descriptions = [Campaign(role,path,controller,manifest,None,None,Exception)
                        for role,path,controller,manifest in verified]
        seal_runtime(root,descriptions,config)
        for sig in (signal.SIGTERM,signal.SIGINT):
            loop.add_signal_handler(sig,stop.set)
            signals.append(sig)
        try:
            for role,path,controller,manifest in verified:
                ledger = controller.Ledger(path/'jobs.sqlite')
                resources.callback(ledger.close)
                campaign = Campaign(role,path,controller,manifest,ledger,None,Exception)
                campaigns.append(campaign)
                ledger.recover(manifest['campaign'])
                module = importlib.import_module(manifest['provider'])
                provider = module.SourceProvider(Path(manifest['seeds_root']),path,load(path/'config.json'))
                resources.callback(provider.close)
                campaign.provider = WaivedProvider(provider,module.SeedUnavailable,role)
                campaign.unavailable = module.SeedUnavailable
                campaign.review,campaign.generation = controller.v6.adapters()
                campaign.budget = controller.v6.Budget(manifest['tokenizer_dir'])
            failures = Counter()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4),
                    connector=aiohttp.TCPConnector(limit=len(ENDPOINTS))) as monitor, \
                    aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=aiohttp.TCPConnector(limit=len(ENDPOINTS)*concurrency,
                                                   limit_per_host=concurrency,
                                                   force_close=True)) as session:
                async def healthcheck(endpoint):
                    async with monitor.get(endpoint+'/models') as response:
                        response.raise_for_status()
                        document = await response.json()
                        original.v6.endpoint_limit(document)
                        return endpoint,document
                health = dict(await asyncio.gather(*(healthcheck(e) for e in ENDPOINTS)))
                gate = original.AdmissionGate(monitor,ENDPOINTS,failures,health,stop,
                                               max_kv=max_kv,spacing=spacing)
                verify_runtime(root)
                runtime = dict(config,pid=os.getpid(),started=time.time(),health=health,
                    manifest_sha256=file_hash(root/'manifest.json'))
                write_json(root/f'runtime-{time.time_ns()}.json',runtime)
                write_json(root/'runtime.json',runtime)
                phase = 'running'
                async def reporter():
                    try:
                        while True:
                            verify_runtime(root)
                            report(root,campaigns,phase,gate)
                            await asyncio.sleep(15)
                    except Exception:
                        stop.set()
                        raise
                reporting = asyncio.create_task(reporter())
                try:
                    await dispatch(campaigns,ENDPOINTS,concurrency,session,health,gate,failures,stop)
                finally:
                    if not reporting.done():
                        reporting.cancel()
                    result = await asyncio.gather(reporting,return_exceptions=True)
                    if isinstance(result[0],Exception):
                        raise result[0]
                verify_runtime(root)
                state = report(root,campaigns,phase,gate)
                phase = ('drained' if stop.is_set() else 'complete' if not state['remaining'] else
                         'eligible_complete_with_waivers' if not state['eligible_remaining'] else 'blocked')
        except BaseException:
            phase = 'interrupted_or_failed'
            raise
        finally:
            stop.set()
            for sig in signals:
                loop.remove_signal_handler(sig)
            errors = []
            for campaign in campaigns:
                try:
                    campaign.ledger.recover(campaign.manifest['campaign'])
                except Exception as exc:
                    errors.append(dict(campaign=campaign.role,error=repr(exc)))
            if errors:
                phase = 'recovery_failed'
                write_json(root/'recovery-errors.json',errors)
            report(root,campaigns,phase,gate)
            if errors:
                raise RuntimeError('Joint cleanup failed; see recovery-errors.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--original-root',type=Path,default=ORIGINAL_ROOT)
    parser.add_argument('--european-root',type=Path,default=EUROPEAN_ROOT)
    parser.add_argument('--concurrency-per-server',type=int,default=512)
    parser.add_argument('--timeout',type=int,default=600)
    parser.add_argument('--admission-spacing',type=float,default=.002)
    parser.add_argument('--max-kv-cache-utilization',type=float,default=.90)
    args = parser.parse_args()
    asyncio.run(execute(args.root,args.original_root,args.european_root,
        args.concurrency_per_server,args.timeout,args.admission_spacing,args.max_kv_cache_utilization))


if __name__ == '__main__':
    main()
