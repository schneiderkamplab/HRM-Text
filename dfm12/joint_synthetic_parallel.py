"""One or two CPU processes per endpoint; one owner for every ledger operation.

Workers own HTTP and candidate artifacts only. Private socket pairs carry bounded
RPC; no worker opens SQLite. This runner never starts or stops GPU servers.
"""
import argparse
import asyncio
from collections import Counter
from contextlib import ExitStack, contextmanager
import fcntl
import importlib
import json
import multiprocessing
from multiprocessing.reduction import DupFd
import os
from pathlib import Path
import signal
import socket
import threading
import time

from . import joint_synthetic_campaign as joint
from . import joint_admission
from . import joint_async_process, joint_metrics_cache
from .io import digest, file_hash, load, lock, write_json

VERSION = 'joint-synthetic-parallel-v2'
MAX_RPC_BYTES = 4 * 1024 * 1024
RPC_TIMEOUT = 60
ADMISSION_HEARTBEAT = 5


def settings(concurrency=None,timeout=600,spacing=.002,max_kv=.90,workers_per_server=1):
    if type(workers_per_server) is not int or workers_per_server not in (1,2):
        raise ValueError('Require one or two workers per server')
    concurrency = 512*workers_per_server if concurrency is None else concurrency
    if (type(concurrency) is not int or concurrency < workers_per_server
            or concurrency > 1024 or concurrency % workers_per_server):
        raise ValueError('Endpoint concurrency must split evenly, with aggregate limit 1024')
    per_worker = concurrency//workers_per_server
    joint_admission.validate_max_kv(max_kv)
    config = joint.settings(per_worker,timeout,spacing,min(max_kv,.9))
    config.update(concurrency_per_server=concurrency,concurrency_per_worker=per_worker,
        max_http_requests=len(joint.ENDPOINTS)*concurrency,workers_per_server=workers_per_server,
        admission_owner='parent' if workers_per_server==2 else 'endpoint-worker',
        admission_waiting_limit=128, admission_poll_seconds=.01,
        admission_metrics_cache_seconds=.25, fingerprint_claim_transport='async',
        max_kv_cache_utilization=max_kv)
    return config


def worker_endpoints(endpoints,workers_per_server=1):
    return {endpoint if workers_per_server==1 else f'{endpoint}#{index}':endpoint
            for endpoint in endpoints for index in range(workers_per_server)}


@contextmanager
def retained_lock(path):
    """Closing the parent handle must not unlock worker-held duplicates."""
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield handle


def detach_locks(descriptors):
    held = []
    try:
        for descriptor in descriptors:
            held.append(descriptor.detach())
        return held
    except BaseException:
        for fd in held:
            os.close(fd)
        raise


def encode(value):
    data = json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()+b'\n'
    if len(data) > MAX_RPC_BYTES:
        raise ValueError('RPC byte limit exceeded')
    return data


def decode(data):
    if not data or len(data) > MAX_RPC_BYTES or not data.endswith(b'\n'):
        raise ValueError('Incomplete/oversized RPC frame')
    value = joint.original.v6.strict_json(data.decode())
    if not isinstance(value,dict):
        raise ValueError('RPC object required')
    return value


class AsyncRPC:
    def __init__(self, reader, writer):
        self.reader,self.writer = reader,writer
        self.lock = asyncio.Lock()
        self.sequence = 0

    async def call(self, op, **fields):
        try:
            async with asyncio.timeout(RPC_TIMEOUT), self.lock:
                self.sequence += 1
                self.writer.write(encode(dict(sequence=self.sequence,op=op,**fields)))
                await self.writer.drain()
                reply = decode(await self.reader.readline())
                if reply.get('sequence') != self.sequence or reply.get('ok') is not True:
                    raise RuntimeError('Owner RPC rejected: '+str(reply.get('error')))
                return reply['result']
        except BaseException:
            self.writer.close()
            raise


class AdmissionRPC(AsyncRPC):
    """Heartbeat-framed permit waits never hold the control/finish channel."""
    async def call(self,op,**fields):
        async with self.lock:
            self.sequence += 1
            try:
                self.writer.write(encode(dict(sequence=self.sequence,op=op,**fields)))
                await asyncio.wait_for(self.writer.drain(),RPC_TIMEOUT)
                while True:
                    reply = decode(await asyncio.wait_for(self.reader.readline(),RPC_TIMEOUT))
                    if reply.get('sequence') != self.sequence or reply.get('ok') is not True:
                        raise RuntimeError('Owner admission RPC rejected: '+str(reply.get('error')))
                    if reply.get('pending') is not True:
                        return reply['result']
            except BaseException:
                self.writer.close()
                raise


class SyncRPC:
    """Dedicated claim channel: retained Seen methods are synchronous."""
    def __init__(self, sock):
        self.sock = sock
        self.sock.settimeout(RPC_TIMEOUT)
        self.reader = sock.makefile('rb')
        self.sequence = 0
        self.broken = False

    def call(self, op, **fields):
        self.sequence += 1
        try:
            self.sock.sendall(encode(dict(sequence=self.sequence,op=op,**fields)))
            reply = decode(self.reader.readline(MAX_RPC_BYTES+1))
            if reply.get('sequence') != self.sequence or reply.get('ok') is not True:
                raise RuntimeError('Owner claim RPC rejected: '+str(reply.get('error')))
            return reply['result']
        except BaseException:
            self.broken = True
            self.close()
            raise

    def close(self):
        self.reader.close()
        self.sock.close()


class RemoteSeen:
    """Membership atomically claims; add confirms, never performs a second insert."""
    def __init__(self,rpc,role,key):
        self.rpc,self.role,self.key = rpc,role,key

    def __contains__(self,fingerprint):
        return not self.rpc.call('claim',role=self.role,key=self.key,fingerprint=fingerprint)

    def add(self,fingerprint):
        if self.rpc.call('confirm',role=self.role,key=self.key,fingerprint=fingerprint) is not True:
            raise RuntimeError('Unowned fingerprint')


class Owner:
    def __init__(self,campaigns,endpoints,concurrency,stop,workers_per_server=1):
        settings(concurrency,workers_per_server=workers_per_server)
        self.campaigns = {c.role:c for c in campaigns}
        self.queue = joint.FairReservations(campaigns)
        self.endpoints,self.concurrency,self.stop = tuple(endpoints),concurrency,stop
        if concurrency % workers_per_server:
            raise ValueError('Uneven worker concurrency')
        self.worker_endpoints = worker_endpoints(endpoints,workers_per_server)
        self.per_worker = concurrency//workers_per_server
        self.gate = None
        self.gate_stop = asyncio.Event()
        self.identity = (os.getpid(),threading.get_ident())
        self.assigned = {}
        self.active = Counter()
        self.ready,self.done,self.status = set(),set(),{}
        self.errors = []
        self.blocked = False

    def fail(self,error):
        self.errors.append(str(error))
        self.request_stop()

    def request_stop(self):
        self.stop.set()
        self.gate_stop.set()

    async def admit(self,worker):
        if worker not in self.worker_endpoints or self.gate is None:
            raise ValueError('Unknown admission worker or missing shared gate')
        if self.stop.is_set():
            return dict(kind='stop')
        if len(self.ready) != len(self.worker_endpoints):
            return dict(kind='wait')
        endpoint = self.worker_endpoints[worker]
        allowed = await self.gate.admit(endpoint,lambda:not self.stop.is_set()
            and endpoint not in self.gate.paused and self.queue.has_remaining())
        if not allowed:
            return dict(kind='stop')
        # No await between the shared permit and the sole-writer reservation.
        item = self.handle(worker,'reserve')
        if item['kind']=='job':
            item.update(circuit_generation=self.gate.circuit_generation[endpoint],
                        endpoint_health=self.gate.health[endpoint])
        return item

    def handle(self,worker,op,**fields):
        if self.identity != (os.getpid(),threading.get_ident()):
            raise RuntimeError('Ledger RPC dispatched outside owner thread')
        if worker not in self.worker_endpoints:
            raise ValueError('Unknown worker endpoint')
        if op == 'ready':
            self.ready.add(worker)
            return True
        if op == 'status':
            self.status[worker] = fields['status']
            if self.gate is None and all(self.status.get(w,{}).get('paused') for w in self.worker_endpoints):
                self.blocked = True
                self.request_stop()
            return True
        if op == 'done':
            if self.active[worker]:
                raise ValueError('Worker reports done with outstanding reservations')
            self.done.add(worker)
            return True
        if op == 'reserve':
            if worker in self.done:
                raise ValueError('Finished worker cannot reserve')
            if self.stop.is_set() or not self.queue.has_remaining():
                return dict(kind='stop')
            if len(self.ready) != len(self.worker_endpoints):
                return dict(kind='wait')
            endpoint = self.worker_endpoints[worker]
            endpoint_active = sum(self.active[w] for w,e in self.worker_endpoints.items() if e==endpoint)
            if self.active[worker] >= self.per_worker or endpoint_active >= self.concurrency:
                raise ValueError('Per-endpoint reservation cap exceeded')
            selected = self.queue.reserve()
            if selected is None:
                return dict(kind='wait')
            campaign,job = selected
            self.assigned[(campaign.role,job['id'])] = (worker,job)
            self.active[worker] += 1
            return dict(kind='job',role=campaign.role,id=job['id'],spec=job['spec'],workdir=str(job['workdir']))
        role,key = fields['role'],fields['key']
        assigned = self.assigned.get((role,key))
        if assigned is None or assigned[0] != worker:
            raise ValueError('Unowned reservation')
        campaign,job = self.campaigns[role],assigned[1]
        if op == 'stage_result':
            if self.gate is None:
                raise ValueError('Shared circuit event requires parent gate')
            endpoint = self.worker_endpoints[worker]
            status = fields['status']
            if status=='http_rejected':
                self.gate.paused[endpoint] = 'nontransient_http_rejection_requires_operator'
                self.gate.failures[endpoint] = 3
                self.gate.trip(endpoint)
            elif status in ('abort_status_unknown','retryable','infrastructure_exhausted'):
                self.gate.failures[endpoint] = 3
                self.gate.trip(endpoint)
            elif (status=='complete' and endpoint not in self.gate.recover_at
                    and endpoint not in self.gate.paused
                    and fields['circuit_generation']==self.gate.circuit_generation[endpoint]):
                self.gate.failures[endpoint] = 0
            if all(e in self.gate.paused for e in self.endpoints):
                self.blocked = True
                self.request_stop()
            return True
        if op in ('claim','confirm'):
            fingerprint = fields['fingerprint']
            if (not isinstance(fingerprint,str) or len(fingerprint)!=64
                    or any(c not in '0123456789abcdef' for c in fingerprint)):
                raise ValueError('Invalid fingerprint')
            row = campaign.ledger.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(fingerprint,)).fetchone()
            if op == 'claim' and row is None:
                campaign.ledger.db.execute('INSERT INTO fingerprints VALUES (?,?)',(fingerprint,key))
                return True
            owned = row is not None and row['owner'] == key
            if op == 'confirm' and not owned:
                raise ValueError('Unowned fingerprint confirmation')
            return owned
        if op == 'finish':
            # Read the retained processor's durable result, not an RPC-supplied keep.
            outcome = load(job['workdir']/'outcomes'/f'{key}.json')
            if (outcome.get('id') != key or outcome.get('spec_sha256') != digest(job['spec'])
                    or outcome.get('terminal') is not True):
                raise ValueError('Terminal outcome identity mismatch')
            if outcome.get('status') == 'valid' and outcome.get('effective_keep') is True:
                row = campaign.ledger.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',
                    (outcome.get('fingerprint'),)).fetchone()
                if row is None or row['owner'] != key:
                    raise ValueError('Accepted candidate lacks owned unique fingerprint')
                campaign.controller.materialize(job['workdir'],key,outcome,campaign.manifest['campaign'])
            accepted = campaign.ledger.finish(key,outcome)
            del self.assigned[(role,key)]
            self.active[worker] -= 1
            return dict(accepted=accepted)
        raise ValueError('Unknown RPC operation')


async def serve_socket(sock,owner,worker,claim_channel=False,admission_channel=False):
    reader,writer = await asyncio.open_connection(sock=sock,limit=MAX_RPC_BYTES)
    sequence = 0
    allowed = ({'reserve'} if admission_channel else {'claim','confirm'} if claim_channel else
               {'ready','finish','status','done','stage_result'} if owner.gate is not None else
               {'ready','reserve','finish','status','done'})
    pending = None
    try:
        while True:
            data = await reader.readline()
            if not data:
                if worker not in owner.done:
                    owner.fail('Worker RPC disconnected before done: '+worker)
                return
            request = decode(data)
            sequence += 1
            if request.pop('sequence',None) != sequence or request.get('op') not in allowed:
                raise ValueError('RPC sequence/channel mismatch')
            op = request.pop('op')
            try:
                if admission_channel:
                    if request:
                        raise ValueError('Admission RPC takes no supplied job/permit')
                    pending = asyncio.create_task(owner.admit(worker))
                    while not pending.done():
                        await asyncio.wait({pending},timeout=ADMISSION_HEARTBEAT)
                        if not pending.done():
                            writer.write(encode(dict(sequence=sequence,ok=True,pending=True)))
                            await writer.drain()
                    result = pending.result()
                    pending = None
                else:
                    result = owner.handle(worker,op,**request)
                response = dict(sequence=sequence,ok=True,result=result)
            except Exception as exc:
                owner.fail(repr(exc))
                response = dict(sequence=sequence,ok=False,error=repr(exc))
            writer.write(encode(response))
            await writer.drain()
    except Exception as exc:
        owner.fail(repr(exc))
    finally:
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending,return_exceptions=True)
        writer.close()
        await writer.wait_closed()


async def endpoint_worker(endpoint,descriptions,config,health,stop_event,async_sock,claim_sock,
                          worker_id=None,admission_sock=None):
    import aiohttp
    reader,writer = await asyncio.open_connection(sock=async_sock,limit=MAX_RPC_BYTES)
    claim_reader,claim_writer = await asyncio.open_connection(sock=claim_sock,limit=MAX_RPC_BYTES)
    rpc,claims = AsyncRPC(reader,writer),AsyncRPC(claim_reader,claim_writer)
    admission,admission_writer = None,None
    if admission_sock is not None:
        admission_reader,admission_writer = await asyncio.open_connection(sock=admission_sock,limit=MAX_RPC_BYTES)
        admission = AdmissionRPC(admission_reader,admission_writer)
    local_stop = asyncio.Event()
    controllers = {'original':joint.original,'european':joint.european.isolated_controller()}
    adapters = {}
    for role,description in descriptions.items():
        controller = controllers[role]
        review,generation = controller.v6.adapters()
        adapters[role] = (controller,review,generation,controller.v6.Budget(description['tokenizer_dir']))
    failures = Counter()
    recovery_epoch = -1
    concurrency = config.get('concurrency_per_worker',config['concurrency_per_server'])
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):
        loop.add_signal_handler(sig,local_stop.set)
    tasks,watcher = [],None
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4),
                connector=aiohttp.TCPConnector(limit=1)) as monitor, \
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=config['timeout']),
                connector=aiohttp.TCPConnector(limit=concurrency,limit_per_host=concurrency,
                                               force_close=True)) as session:
            gate = (joint_admission.AdmissionGate(monitor,[endpoint],failures,health,local_stop,
                max_kv=config['max_kv_cache_utilization'],spacing=config['admission_spacing_seconds'])
                if admission is None else None)
            await rpc.call('ready')
            async def watch():
                while not local_stop.is_set():
                    if stop_event.is_set():
                        local_stop.set()
                    await rpc.call('status',status=dict(paused=gate is not None and endpoint in gate.paused,
                        admission=gate.status[endpoint] if gate else 'parent',worker_id=worker_id,
                        endpoint=endpoint,pid=os.getpid(),time=time.time()))
                    await asyncio.sleep(.5)
            async def worker():
                nonlocal recovery_epoch
                while not local_stop.is_set():
                    if admission is None:
                        if not await gate.admit(endpoint,lambda:not stop_event.is_set() and endpoint not in gate.paused):
                            return
                        item = await rpc.call('reserve')
                    else:
                        item = await admission.call('reserve')
                    if item['kind'] == 'stop':
                        local_stop.set()
                        return
                    if item['kind'] == 'wait':
                        await joint.original.stop_wait(local_stop,1)
                        continue
                    controller,review,generation,budget = adapters[item['role']]
                    if admission is not None:
                        if item['circuit_generation'] > recovery_epoch:
                            failures[endpoint] = 0
                            recovery_epoch = item['circuit_generation']
                        health[endpoint] = item['endpoint_health']
                    directory = Path(item['workdir'])
                    stage_type = controller.v6.Stages
                    if admission is not None:
                        class ReportingStages(stage_type):
                            async def call(self,*args,**kwargs):
                                state = await super().call(*args,**kwargs)
                                await rpc.call('stage_result',role=item['role'],key=item['id'],
                                    status=state['status'],circuit_generation=item['circuit_generation'])
                                return state
                        stage_type = ReportingStages
                    stages = stage_type(directory,budget,
                        controller.v6.RawResponseWriter(directory/'raw'),session,
                        query=joint.campaign_query(controller))
                    stages.failures = failures
                    seen = joint_async_process.AsyncRemoteSeen(claims,item['role'],item['id'])
                    outcome = await joint_async_process.process(item['spec'],endpoint,directory,stages,
                        health,generation,review,seen,pilot=controller.pilot)
                    if seen.broken:
                        raise RuntimeError('Claim transport failed; do not continue candidate admission')
                    if gate is not None and failures[endpoint] >= 3:
                        gate.trip(endpoint)
                    if gate is not None and outcome.get('status','').endswith('http_rejected'):
                        gate.paused[endpoint] = 'nontransient_http_rejection_requires_operator'
                    await rpc.call('finish',role=item['role'],key=item['id'])
            watcher = asyncio.create_task(watch())
            def watch_done(task):
                if not task.cancelled() and task.exception() is not None:
                    local_stop.set()
            watcher.add_done_callback(watch_done)
            tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
            try:
                await asyncio.gather(*tasks)
            except BaseException:
                local_stop.set()
                await asyncio.gather(*tasks,return_exceptions=True)
                raise
            if watcher.done() and not watcher.cancelled():
                watcher.result()
            await rpc.call('status',status=dict(paused=gate is not None and endpoint in gate.paused,
                admission=gate.status[endpoint] if gate else 'parent',worker_id=worker_id,
                endpoint=endpoint,pid=os.getpid(),time=time.time()))
            await rpc.call('done')
    finally:
        local_stop.set()
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher,return_exceptions=True)
        claim_writer.close()
        await claim_writer.wait_closed()
        if admission_writer is not None:
            admission_writer.close()
            await admission_writer.wait_closed()
        writer.close()
        await writer.wait_closed()
        for sig in (signal.SIGTERM,signal.SIGINT):
            loop.remove_signal_handler(sig)


def worker_entry(endpoint,descriptions,config,health,stop_event,async_sock,claim_sock,lock_descriptors,
                 worker_id=None,admission_sock=None):
    # These are CPU orchestration processes, never local inference engines.
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = '1'
    held = detach_locks(lock_descriptors)
    try:
        asyncio.run(endpoint_worker(endpoint,descriptions,config,health,stop_event,async_sock,claim_sock,
                                    worker_id,admission_sock))
    finally:
        for fd in held:
            os.close(fd)


def runtime_pins(campaigns):
    from . import joint_source_expansion, joint_source_reuse
    return sorted({Path(__file__).resolve(),Path(joint_admission.__file__).resolve(),
                   Path(joint_source_expansion.__file__).resolve(),Path(joint_source_reuse.__file__).resolve(),
                   Path(joint_async_process.__file__).resolve(),Path(joint_metrics_cache.__file__).resolve(),
                   *joint.pin_paths(None,campaigns)})


def seal(root,campaigns,config):
    config = dict(config,version=VERSION,worker_processes=8*config.get('workers_per_server',1),ledger_owner='parent-only',
                  rpc_timeout=RPC_TIMEOUT,worker_retains_controller_locks=True,
                  campaigns={c.role:str(c.root) for c in campaigns})
    pins = {str(p):file_hash(p) for p in runtime_pins(campaigns)}
    if (root/'manifest.json').exists():
        verify(root)
        if load(root/'config.json') != config or load(root/'manifest.json')['pins'] != pins:
            raise ValueError('Parallel runtime drift; use a fresh root')
        return
    if any(p.name != 'controller.lock' for p in root.iterdir()):
        raise ValueError('Fresh parallel root required; no silent repin')
    write_json(root/'config.json',config)
    write_json(root/'manifest.json',dict(version=VERSION,pins=pins,config_sha256=file_hash(root/'config.json')))
    write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
    verify(root)


def verify(root):
    manifest = load(root/'manifest.json')
    if (manifest.get('version') != VERSION
            or file_hash(root/'manifest.json') != load(root/'seal.json')['manifest_sha256']
            or file_hash(root/'config.json') != manifest['config_sha256']):
        raise ValueError('Parallel runtime seal drift')
    for path,sha in manifest['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Parallel runtime pin drift: '+path)


async def supervise(owner,processes,services,root,campaigns):
    last_report,last_verify = 0,0
    try:
        while any(p.is_alive() for p in processes.values()):
            for endpoint,process in processes.items():
                if process.exitcode is not None and (process.exitcode != 0 or endpoint not in owner.done):
                    if not owner.errors:
                        owner.fail(f'Endpoint worker exited without clean completion: {endpoint} ({process.exitcode})')
            now = time.monotonic()
            if now-last_verify >= 60:
                verify(root)
                last_verify = now
            if now-last_report >= 15:
                state = joint.report(root,campaigns,'draining' if owner.stop.is_set() else 'running')
                state.update(version=VERSION,workers={e:dict(pid=p.pid,exitcode=p.exitcode,
                    active=owner.active[e],status=owner.status.get(e,{})) for e,p in processes.items()})
                write_json(root/'progress.json',state)
                last_report = now
            await asyncio.sleep(.5)
    finally:
        if any(p.is_alive() for p in processes.values()):
            owner.request_stop()
        # Never recover/close the ledgers while a worker can still write artifacts.
        while any(p.is_alive() for p in processes.values()):
            await asyncio.sleep(.1)
        for p in processes.values():
            p.join()
        await asyncio.gather(*services,return_exceptions=True)
    for endpoint,process in processes.items():
        if process.exitcode != 0 or endpoint not in owner.done:
            owner.fail(f'Unclean endpoint completion: {endpoint} ({process.exitcode})')
    if owner.errors:
        raise RuntimeError('; '.join(owner.errors))


async def execute(root,original_root=joint.ORIGINAL_ROOT,european_root=joint.EUROPEAN_ROOT,
                  concurrency=None,timeout=600,spacing=.002,max_kv=.90,workers_per_server=1,
                  source_expansion=False):
    import aiohttp
    from . import joint_source_expansion as expansion
    from .joint_source_reuse import SourceReuseProvider
    config = settings(concurrency,timeout,spacing,max_kv,workers_per_server)
    config['source_expansion'] = expansion.POLICY if source_expansion else None
    concurrency = config['concurrency_per_server']
    root,original_root,european_root = [Path(p).resolve() for p in (root,original_root,european_root)]
    roots = (root,original_root,european_root)
    if any(a==b or a.is_relative_to(b) or b.is_relative_to(a)
           for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('Distinct non-nested roots required')
    for path in roots[1:]:
        if not (path/'jobs.sqlite').is_file():
            raise ValueError('Prepared campaign ledger required')
    context = multiprocessing.get_context('spawn')
    stop = context.Event()
    campaigns,processes,services,signals = [],{},[],[]
    phase,owner,monitor = 'preflight',None,None
    gate_stop = asyncio.Event()
    def request_stop():
        stop.set()
        gate_stop.set()
    with ExitStack() as resources:
        handles = [resources.enter_context(retained_lock(path/'controller.lock')) for path in sorted(roots)]
        for path in roots[1:]:
            expansion.require_opt_in(path,source_expansion)
        original_controller,european_controller = (expansion.private_controllers() if source_expansion
            else (joint.original,joint.european.isolated_controller()))
        controllers = [('original',original_root,original_controller),
                       ('european',european_root,european_controller)]
        verified = [(role,path,c,c.verify(path)) for role,path,c in controllers]
        descriptions = [joint.Campaign(role,path,c,m,None,None,Exception) for role,path,c,m in verified]
        seal(root,descriptions,config)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM,signal.SIGINT):
            loop.add_signal_handler(sig,request_stop)
            signals.append(sig)
        try:
            for role,path,controller,manifest in verified:
                ledger_type = expansion.ledger_class(controller) if source_expansion else controller.Ledger
                ledger = ledger_type(path/'jobs.sqlite')
                resources.callback(ledger.close)
                campaign_type = expansion.ExpandedCampaign if source_expansion else joint.Campaign
                c = campaign_type(role,path,controller,manifest,ledger,None,Exception)
                campaigns.append(c)
                ledger.recover(manifest['campaign'])
                if source_expansion:
                    expansion.migrate(ledger,path)
                    controller.verify(path)
                module = importlib.import_module(manifest['provider'])
                provider = module.SourceProvider(Path(manifest['seeds_root']),path,load(path/'config.json'))
                if source_expansion:
                    try:
                        provider = SourceReuseProvider(provider,path,max_per_seed=expansion.POLICY['max_candidates_per_source'])
                    except BaseException:
                        provider.close()
                        raise
                resources.callback(provider.close)
                c.provider = provider if source_expansion else joint.WaivedProvider(provider,module.SeedUnavailable,role)
                c.unavailable = module.SeedUnavailable
            monitor = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
            async def healthcheck(endpoint):
                async with monitor.get(endpoint+'/models') as response:
                    response.raise_for_status()
                    document = await response.json()
                    joint.original.v6.endpoint_limit(document)
                    return endpoint,document
            health = dict(await asyncio.gather(*(healthcheck(e) for e in joint.ENDPOINTS)))
            verify(root)
            owner = Owner(campaigns,joint.ENDPOINTS,concurrency,stop,workers_per_server)
            owner.gate_stop = gate_stop
            if workers_per_server > 1:
                owner.gate = joint_admission.AdmissionGate(monitor,joint.ENDPOINTS,Counter(),health,
                    gate_stop,max_kv=max_kv,spacing=spacing)
            worker_descriptions = {c.role:dict(tokenizer_dir=c.manifest['tokenizer_dir']) for c in campaigns}
            for worker_id,endpoint in owner.worker_endpoints.items():
                parent_async,child_async = socket.socketpair()
                parent_claim,child_claim = socket.socketpair()
                parent_admission,child_admission = socket.socketpair() if owner.gate else (None,None)
                for sock in (parent_async,parent_claim):
                    sock.setblocking(False)
                process = context.Process(target=worker_entry,args=(endpoint,worker_descriptions,config,
                    health,stop,child_async,child_claim,[DupFd(h.fileno()) for h in handles],
                    worker_id,child_admission),name='synthetic-'+worker_id)
                try:
                    process.start()
                except BaseException:
                    parent_async.close()
                    parent_claim.close()
                    if parent_admission is not None:
                        parent_admission.close()
                    raise
                finally:
                    child_async.close()
                    child_claim.close()
                    if child_admission is not None:
                        child_admission.close()
                processes[worker_id] = process
                services.extend((asyncio.create_task(serve_socket(parent_async,owner,worker_id)),
                                 asyncio.create_task(serve_socket(parent_claim,owner,worker_id,True))))
                if parent_admission is not None:
                    parent_admission.setblocking(False)
                    services.append(asyncio.create_task(serve_socket(parent_admission,owner,worker_id,
                                                                    admission_channel=True)))
            runtime = dict(version=VERSION,pid=os.getpid(),workers={e:p.pid for e,p in processes.items()},
                worker_endpoints=owner.worker_endpoints,concurrency_per_worker=config['concurrency_per_worker'],
                concurrency_per_server=concurrency,
                started=time.time(),health=health,manifest_sha256=file_hash(root/'manifest.json'))
            write_json(root/f'runtime-{time.time_ns()}.json',runtime)
            write_json(root/'runtime.json',runtime)
            phase = 'running'
            await supervise(owner,processes,services,root,campaigns)
            state = joint.report(root,campaigns,phase)
            phase = ('blocked' if owner.blocked else 'complete' if not state['remaining'] else
                     'eligible_complete_with_waivers' if not state['eligible_remaining'] else
                     'drained' if stop.is_set() else 'blocked')
        except BaseException:
            phase = 'interrupted_or_failed'
            raise
        finally:
            request_stop()
            while any(p.is_alive() for p in processes.values()):
                await asyncio.sleep(.1)
            for p in processes.values():
                p.join()
            await asyncio.gather(*services,return_exceptions=True)
            if monitor is not None:
                await monitor.close()
            for sig in signals:
                loop.remove_signal_handler(sig)
            errors = []
            for c in campaigns:
                try:
                    c.ledger.recover(c.manifest['campaign'])
                except Exception as exc:
                    errors.append(dict(campaign=c.role,error=repr(exc)))
            if errors:
                phase = 'recovery_failed'
            state = joint.report(root,campaigns,phase)
            state.update(version=VERSION,worker_errors=owner.errors if owner else [],recovery_errors=errors)
            write_json(root/'progress.json',state)
            if errors:
                raise RuntimeError('Parallel ledger recovery failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--original-root',type=Path,default=joint.ORIGINAL_ROOT)
    parser.add_argument('--european-root',type=Path,default=joint.EUROPEAN_ROOT)
    parser.add_argument('--concurrency-per-server',type=int,default=None)
    parser.add_argument('--workers-per-server',type=int,choices=(1,2),default=1)
    parser.add_argument('--source-expansion',action='store_true',
                        help='Authorize six-language source reuse, 24x attempt budgets and lifted FO waivers')
    parser.add_argument('--timeout',type=int,default=600)
    parser.add_argument('--admission-spacing',type=float,default=.002)
    parser.add_argument('--max-kv-cache-utilization',type=float,default=.90)
    args = parser.parse_args()
    asyncio.run(execute(args.root,args.original_root,args.european_root,args.concurrency_per_server,
                       args.timeout,args.admission_spacing,args.max_kv_cache_utilization,args.workers_per_server,
                       args.source_expansion))


if __name__ == '__main__':
    main()
