"""Nonadmitting, externally authorized31B capacity plateaus; no server lifecycle."""
import argparse
import asyncio
from collections import Counter
from collections.abc import Mapping
from contextlib import closing, ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import time
import uuid

from . import fars_summary_consumer as frozen
from . import fars_summary_handoff as tokenizer
from . import wave31_endpoint_health as health
from .io import digest, file_hash, load, lock, write_json
from .multilingual_calibration_v6 import raw_query, RawResponseWriter

PORTS = tuple(str(p) for p in range(8800,8808))
FAMILIES = {'grounded-instruct','math-code','multiturn','openhermes','summary-rewrite','tool-dialogue'}
OOM = re.compile(rb'OutOfMemoryError|CUDA out of memory|CUDA error: out of memory|\bOOM\b', re.I)
AUDIT_PYTHON = Path('/home/ucloud/miniforge3/envs/audit/bin/python')
VLLM = AUDIT_PYTHON.parent.parent/'lib/python3.13/site-packages/vllm'
CACHE_SALT_FILES = ('entrypoints/openai/chat_completion/protocol.py',
    'renderers/online_renderer.py','renderers/base.py','v1/core/kv_cache_utils.py')


class TimedStop(asyncio.Event):
    """Record the first dispatch stop, independently of telemetry polling/drain."""
    def __init__(self):
        super().__init__()
        self.requested_at=None

    def set(self):
        if self.requested_at is None:self.requested_at=time.monotonic()
        super().set()


def wire_request(case, run_id, port, sequence):
    if 'cache_salt' in case['request']:
        raise ValueError('Frozen request must not supply a reusable cache salt')
    salt=digest([run_id,port,sequence])
    payload=dict(case['request'],cache_salt=salt)
    return payload,dict(cache_salt=salt,frozen_case_sha256=digest(case),
        frozen_request_sha256=digest(case['request']),request_sha256=digest(payload))


def measure_prompt(payload, tok):
    mode=payload.get('chat_template_kwargs')
    if (payload.get('model')!=health.MODEL or mode not in
            ({'enable_thinking':True},{'enable_thinking':False})
            or type(mode['enable_thinking']) is not bool
            or type(payload.get('max_tokens')) is not int or payload['max_tokens']<=0):
        raise ValueError('Exact native31B model/mode/output budget required')
    kwargs=dict(tokenize=True,add_generation_prompt=True,**mode)
    if 'tools' in payload:kwargs['tools']=payload['tools']
    ids=tok.apply_chat_template(payload['messages'],**kwargs)
    if isinstance(ids,Mapping):ids=ids['input_ids']
    if not isinstance(ids,list) or not all(type(i) is int for i in ids):
        raise ValueError('Flat native token IDs required')
    result=dict(prompt_tokens=len(ids),max_tokens=payload['max_tokens'],
        total_tokens=len(ids)+payload['max_tokens'],context_limit=32768,
        token_ids_sha256=digest(ids),request_sha256=digest(payload),truncated=False)
    if result['total_tokens']>32768:raise ValueError('Full request overflow; no truncation')
    return result


def prepare(root, balanced, qa, fars, ready_path):
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'lock'):
        if any(p.name!='lock' for p in root.iterdir()):raise ValueError('Fresh workload root required')
        ready=load(ready_path)
        if ready.get('model')!=health.MODEL or ready.get('all_files_verified') is not True:
            raise ValueError('Verified31B download required')
        pins={str(ready_path.resolve()):file_hash(ready_path)}
        for source in (balanced,qa,fars):
            m=frozen.verify(source)
            if m['model']!=ready['model'] or m['revision']!=ready['revision']:
                raise ValueError('Frozen source identity mismatch')
            pins.update(m['pins'])
            for path in (source/'manifest.json',source/'seal.json'):
                pins[str(path.resolve())]=file_hash(path)
        for name in ('tokenizer.json','tokenizer_config.json','chat_template.jinja','config.json'):
            path=Path(ready['snapshot'])/name
            sha=next(f['local_sha256'] for f in ready['files'] if f['name']==name)
            if file_hash(path)!=sha:raise ValueError('Tokenizer asset drift')
            pins[str(path.resolve())]=sha
        tokenizer.tokenizer_init(ready['snapshot'])
        chosen=[]
        for wave in ('wave4','baltic'):
            child=balanced/wave;frozen.verify(child)
            requests=load(child/'generation-requests.json')
            specs=load(child/'specifications.json');budgets=load(child/'prompt-budgets.json')
            for name in ('manifest.json','seal.json','generation-requests.json','specifications.json','prompt-budgets.json'):
                path=child/name;pins[str(path.resolve())]=file_hash(path)
            for family in sorted(FAMILIES):
                options=[]
                for s in specs:
                    if s['family']!=family:continue
                    key=digest([s['language_code'],s['family'],s['slot']])
                    options.append((budgets[key]['prompt_tokens'],key,s))
                options.sort(key=lambda x:(x[0],x[1]))
                if len(options)<2:raise ValueError('Missing family representatives')
                for _,key,s in (options[(len(options)-1)//2],options[-1]):
                    chosen.append(dict(id=wave+':'+key,group=family,wave=wave,
                        source=str(child.resolve()),source_key=key,specification=s,
                        request=requests[key]['request']))
        with closing(tokenizer.readonly(qa/'catalog.sqlite')) as db:
            for key,raw in db.execute("SELECT c.id,c.packet FROM catalog c JOIN budgets b ON c.id=b.id "
                    "WHERE json_extract(b.result,'$.fits')=1 ORDER BY json_extract(b.result,'$.prompt_tokens') DESC,c.id LIMIT 4"):
                chosen.append(dict(id='qa:'+key,group='held-qa',source=str(qa.resolve()),
                    source_key=key,request=json.loads(raw)['audit_request']))
        with closing(tokenizer.readonly(fars/'catalog.sqlite')) as db:
            for key,raw in db.execute("SELECT id,packet FROM catalog ORDER BY "
                    "length(json_extract(packet,'$.audit_request.messages')) DESC,id LIMIT 4"):
                chosen.append(dict(id='fars:'+key,group='held-fars',source=str(fars.resolve()),
                    source_key=key,request=json.loads(raw)['audit_request']))
        if len(chosen)!=32 or len({c['id'] for c in chosen})!=32:
            raise ValueError('Require24 generation plus8 held-source requests')
        groups=sorted(FAMILIES|{'held-qa','held-fars'})
        grouped={g:[c for c in chosen if c['group']==g] for g in groups}
        chosen=[grouped[g][i] for i in range(4) for g in groups]
        for case in chosen:case['budget']=measure_prompt(case['request'],tokenizer.TOKENIZER)
        write_json(root/'requests.json',chosen)
        for path in (Path(__file__),Path(health.__file__),Path(tokenizer.__file__),
                     Path('dfm12/multilingual_calibration_v6.py'),Path('dfm12/multilingual_diagnose.py'),
                     Path('dfm12/io.py'),root/'requests.json'):
            pins[str(path.resolve())]=file_hash(path)
        for name in CACHE_SALT_FILES:
            path=VLLM/name;pins[str(path.resolve())]=file_hash(path)
        manifest=dict(model=ready['model'],revision=ready['revision'],snapshot=ready['snapshot'],pins=pins,
            count=len(chosen),groups=dict(Counter(c['group'] for c in chosen)),context_limit=32768,
            selection='median and longest frozen prompt/family/wave;4 longest fitting QA;4 globally longest serialized full Fars requests',
            repeated_prompts=True,unique_cache_salt_per_request=True,
            pressure_scope='conservative uncached-prefix ramp; not production cache-hit distribution',
            transport='production-matching keepalive; separate telemetry connector',
            admission_authorized=False,publication_allowed=False,capacity_approved=False)
        write_json(root/'manifest.json',manifest)
        write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
        return dict(count=len(chosen),groups=manifest['groups'],network_calls=0)


def metrics(text):
    from prometheus_client.parser import text_string_to_metric_families
    values={}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            values.setdefault(sample.name,[]).append(float(sample.value))
    aliases=dict(kv=('vllm:kv_cache_usage_perc','vllm:gpu_cache_usage_perc'),
        running=('vllm:num_requests_running',),waiting=('vllm:num_requests_waiting',),
        preemptions=('vllm:num_preemptions_total','vllm:num_preemptions'),
        completed=('vllm:request_success_total',))
    result={}
    for key,names in aliases.items():
        found=next((values[n] for n in names if n in values),None)
        if not found or any(not math.isfinite(v) or v<0 for v in found):
            raise ValueError('Missing/invalid telemetry: '+key)
        value=max(found) if key=='kv' else sum(found)
        if (key=='kv' and value>1) or (key!='kv' and value!=int(value)):
            raise ValueError('Invalid gauge/counter: '+key)
        result[key]=value
    return result


def flag(argv,name):
    for i,arg in enumerate(argv):
        if arg==name and i+1<len(argv):return argv[i+1]
        if arg.startswith(name+'='):return arg.split('=',1)[1]
    raise ValueError('Explicit server CLI flag required: '+name)


def process_identity(entry,port):
    pid=entry['pid']
    if type(pid) is not int or pid<=1:raise ValueError('Invalid owned PID')
    proc=Path('/proc')/str(pid)
    raw=(proc/'cmdline').read_bytes()
    argv=[s.decode() for s in raw.split(b'\0') if s]
    start=int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])
    if (start!=int(entry['start_ticks']) or flag(argv,'--port')!=port
            or int(flag(argv,'--max-num-seqs'))!=entry['max_num_seqs']
            or int(flag(argv,'--max-model-len'))<32768):
        raise ValueError('Owned server process/config drift')
    if 'command' in entry and argv!=entry['command']:
        raise ValueError('Live argv differs from lifecycle launch command')
    return dict(pid=pid,start_ticks=start,cmdline_sha256=hashlib.sha256(raw).hexdigest())


def server_contract(receipt,manifest,concurrency):
    if type(concurrency) is not int or not 1<=concurrency<=64:
        raise ValueError('Aggregate concurrency must be1..64/server')
    if (any(receipt.get(k)!=manifest[k] for k in ('model','revision'))
            or Path(receipt.get('snapshot','')).resolve()!=Path(manifest['snapshot']).resolve()
            or set(receipt.get('servers',{}))!=set(PORTS)):
        raise ValueError('Exact all-eight server receipt required')
    sequences={}
    for port,entry in receipt['servers'].items():
        n=entry.get('max_num_seqs')
        if type(n) is not int or not concurrency<=n<=1024:
            raise ValueError('Actual sequence budget too small/invalid')
        if not Path(entry['log_path']).is_absolute():raise ValueError('Absolute owned log path required')
        sequences[port]=n
    if len(set(sequences.values()))!=1:raise ValueError('Matching sequence settings across endpoints required')
    return next(iter(sequences.values()))


def lifecycle_bundle(root,manifest,concurrency):
    """Read Boole's immutable launch configuration plus a captured readiness observation."""
    config=load(root/'configuration.json');commands=load(root/'commands.json')
    endpoints=load(root/'endpoints.json');ready=load(root/'ready.json')
    lifecycle_live(root,endpoints['supervisor'])
    for path,sha in config['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Lifecycle input/code drift: '+path)
    if (config.get('schema')!='wave31-server-lifecycle-v1' or config.get('mode')!='ramp'
            or config.get('tensor_parallel_size')!=1 or config.get('gpu_memory_utilization')!=.95
            or config.get('max_model_len')!=32768 or config.get('max_num_batched_tokens')!=16384
            or type(config.get('aggregate_client_concurrency_per_server')) is not int
            or not concurrency<=config['aggregate_client_concurrency_per_server']<=64
            or ready.get('all_eight_verified') is not True):
        raise ValueError('Owned ready ramp configuration required')
    expected={f'http://127.0.0.1:{p}/v1' for p in PORTS}
    if (set(endpoints.get('endpoints',[]))!=expected or len(commands)!=8
            or set(endpoints.get('metrics_endpoints',[]))!={e.removesuffix('/v1')+'/metrics' for e in expected}
            or set(ready.get('endpoints',{}))!=expected
            or endpoints.get('max_num_seqs')!=config['max_num_seqs']):
        raise ValueError('All-eight lifecycle endpoints/metrics/ready observations required')
    servers={}
    for item in commands:
        if item['endpoint'] not in expected:raise ValueError('Unexpected endpoint')
        port=item['endpoint'].split(':')[-1].split('/')[0]
        owner=load(item['ownership_path'])
        process=next(p for p in owner['owned'] if p['pid']==item['pid'])
        if (owner['server_session']!=item['pid'] or owner['command']!=item['command']
                or Path(item['command'][0]).resolve()!=AUDIT_PYTHON.resolve()
                or flag(item['command'],'--port')!=port
                or int(flag(item['command'],'--max-num-seqs'))!=config['max_num_seqs']
                or flag(item['command'],'--tensor-parallel-size')!='1'
                or float(flag(item['command'],'--gpu-memory-utilization'))!=.95
                or flag(item['command'],'--max-model-len')!='32768'
                or flag(item['command'],'--max-num-batched-tokens')!='16384'
                or Path(flag(item['command'],'--model')).resolve()!=Path(config['snapshot']).resolve()):
            raise ValueError('Lifecycle command/ownership/config mismatch')
        health.validate(ready['endpoints'][item['endpoint']],manifest['snapshot'])
        servers[port]=dict(pid=item['pid'],start_ticks=process['start_ticks'],
            max_num_seqs=config['max_num_seqs'],log_path=item['log_path'],command=item['command'],
            ownership_path=item['ownership_path'],ownership_snapshot=owner,ownership_snapshot_sha256=digest(owner),
            gpu_uuid=item['gpu_uuid'],internal_port=item['internal_port'])
    bundle_pins={str((root/n).resolve()):file_hash(root/n) for n in ('configuration.json','commands.json','endpoints.json')}
    receipt=dict(model=config['model'],revision=config['revision'],snapshot=config['snapshot'],servers=servers,
        lifecycle_root=str(root.resolve()),configuration=config,commands=commands,
        endpoints=endpoints,ready_observation=ready,
        bundle_pins=bundle_pins)
    server_contract(receipt,manifest,concurrency)
    return receipt


def lifecycle_live(root,supervisor):
    if (root/'stopped.json').exists() or (root/'stop.request').exists():
        raise ValueError('Lifecycle stopping/stopped')
    status=load(root/'status.json')
    if (not 0<=time.time()-status['time']<=30 or status.get('ready')!=[True]*8
            or status.get('exit_codes')!=[None]*8):
        raise ValueError('Fresh all-eight live lifecycle status required')
    stat=(Path('/proc')/str(supervisor['pid'])/'stat').read_text().rsplit(')',1)[1].split()
    if int(stat[19])!=int(supervisor['start_ticks']) or stat[0]=='Z':
        raise ValueError('Lifecycle supervisor identity changed/exited')


def p95(values):
    return sorted(values)[math.ceil(.95*len(values))-1] if values else None


def completion_windows(events, started, cutoff, drained_at):
    """Events are (monotonic finish, latency, workload group, finish reason)."""
    timed=[e for e in events if e[0]<=cutoff]
    drain=[e for e in events if e[0]>cutoff]
    plateau_seconds=max(0,cutoff-started)
    drain_seconds=max(0,drained_at-cutoff)
    total_seconds=max(0,drained_at-started)
    return dict(completed=len(timed),plateau_completed=len(timed),drain_completed=len(drain),
        total_completed=len(events),plateau_seconds=plateau_seconds,drain_seconds=drain_seconds,
        total_seconds_including_drain=total_seconds,
        plateau_completed_per_second=len(timed)/plateau_seconds if plateau_seconds else None,
        drain_completed_per_second=len(drain)/drain_seconds if drain_seconds else None,
        total_completed_per_second=len(events)/total_seconds if total_seconds else None,
        p95_seconds=p95([e[1] for e in timed]),drain_p95_seconds=p95([e[1] for e in drain]),
        total_p95_seconds=p95([e[1] for e in events]),
        completed_groups=dict(Counter(e[2] for e in timed)),
        finish_reasons=dict(Counter(e[3] for e in timed)),
        total_finish_reasons=dict(Counter(e[3] for e in events)))


def log_start(path):
    stream=open(path,'rb');stat=os.fstat(stream.fileno())
    return stream,dict(device=stat.st_dev,inode=stat.st_ino,offset=stat.st_size)


def log_finish(path,stream,start,destination):
    stat=Path(path).stat()
    if (stat.st_dev,stat.st_ino)!=(start['device'],start['inode']) or stat.st_size<start['offset']:
        raise ValueError('Server log rotated/truncated; OOM evidence unknown')
    end=stat.st_size;stream.seek(start['offset']);remaining=end-start['offset'];count=0;tail=b''
    with open(destination,'xb') as out:
        while remaining:
            data=stream.read(min(1<<20,remaining))
            if not data:raise ValueError('Server log unexpectedly short')
            out.write(data);remaining-=len(data)
            lines=(tail+data).split(b'\n');tail=lines.pop()
            count+=sum(bool(OOM.search(line)) for line in lines)
        count+=bool(OOM.search(tail));out.flush();os.fsync(out.fileno())
    return dict(path=str(path),**start,end_offset=end,copy=str(destination),
        sha256=file_hash(destination),oom_matching_lines=count)


async def snapshot(session,port):
    url=f'http://127.0.0.1:{port}/metrics'
    async with session.get(url,timeout=10) as response:
        response.raise_for_status();raw=await response.text()
    return dict(time=time.time(),raw=raw,parsed=metrics(raw))


async def check_health(session,port,manifest):
    async with session.get(f'http://127.0.0.1:{port}/v1/models',timeout=10) as response:
        response.raise_for_status();doc=await response.json()
    return health.validate(doc,manifest['snapshot'],32768)


async def plateau(root,manifest,cases,receipt,concurrency,duration,poll,session,stop,monitor_session=None):
    import aiohttp
    monitor_session=session if monitor_session is None else monitor_session
    run_id=uuid.uuid4().hex
    started=time.monotonic();deadline=started+duration;dispatch_end=None
    drained=asyncio.Event()
    errors=[];counters={p:dict(completed=0,request_errors=0,events=[]) for p in PORTS}
    baseline={};latest={};high={};identities={};health_docs={};issued=Counter();sample_number=0
    writer=RawResponseWriter(root/'raw')
    with ExitStack() as stack:
        logs={}
        for port in PORTS:
            entry=receipt['servers'][port]
            identities[port]=process_identity(entry,port)
            stream,start=log_start(entry['log_path']);stack.callback(stream.close)
            logs[port]=(stream,start)
            health_docs[port]=await check_health(monitor_session,port,manifest)
            sample=await snapshot(monitor_session,port);baseline[port]=sample['parsed'];latest[port]=sample['parsed'];high[port]=sample['parsed']['kv']
            if baseline[port]['running'] or baseline[port]['waiting'] or baseline[port]['kv']>.90:
                raise ValueError('Endpoints must be exclusively idle before plateau')
            write_json(root/'telemetry'/f'{port}-000000.json',sample)
        write_json(root/'health-start.json',dict(endpoints=health_docs,identities=identities))
        started=time.monotonic();started_at=time.time();deadline=started+duration
        async def worker(port,slot):
            nonlocal dispatch_end
            while not stop.is_set() and time.monotonic()<deadline:
                seq=issued[port];issued[port]+=1;case=cases[(seq+int(port)-8800)%len(cases)]
                payload,binding=wire_request(case,run_id,port,seq)
                record=dict(port=port,sequence=seq,case_id=case['id'],group=case['group'],
                    **binding,started=time.time(),admission_authorized=False)
                t=time.monotonic()
                try:
                    result=await raw_query(session,f'http://127.0.0.1:{port}/v1',payload,writer,record)
                    record.update(status='complete',result=result)
                    counters[port]['completed']+=1
                    finished=time.monotonic()
                    counters[port]['events'].append((finished,finished-t,case['group'],str(result['finish_reason'])))
                    record['completed_offset_seconds']=finished-started
                except Exception as exc:
                    unknown=isinstance(exc,(asyncio.TimeoutError,aiohttp.ClientError))
                    record.update(status='abort_status_unknown' if unknown else 'request_error',error=repr(exc))
                    counters[port]['request_errors']+=1
                    errors.append(f'{port}: request error {exc!r}')
                    if dispatch_end is None:dispatch_end=time.monotonic()
                    stop.set()
                record.update(latency_seconds=time.monotonic()-t,finished=time.time())
                write_json(root/'outcomes'/f'{port}-{seq:08d}.json',record)
        async def monitor():
            nonlocal sample_number,dispatch_end
            while not drained.is_set():
                if dispatch_end is None and stop.is_set():dispatch_end=min(time.monotonic(),deadline)
                if not stop.is_set() and time.monotonic()>=deadline:
                    dispatch_end=deadline;stop.set()
                try:await asyncio.wait_for(drained.wait(),timeout=poll)
                except asyncio.TimeoutError:pass
                if drained.is_set():break
                sample_number+=1
                for port in PORTS:
                    try:
                        lifecycle_live(Path(receipt['lifecycle_root']),receipt['endpoints']['supervisor'])
                        if process_identity(receipt['servers'][port],port)!=identities[port]:
                            raise ValueError('Server identity changed')
                        sample=await snapshot(monitor_session,port);m=sample['parsed']
                        write_json(root/'telemetry'/f'{port}-{sample_number:06d}.json',sample)
                        if m['preemptions']<latest[port]['preemptions'] or m['completed']<latest[port]['completed']:
                            raise ValueError('Telemetry counter reset')
                        latest[port]=m;high[port]=max(high[port],m['kv'])
                        if m['running']+m['waiting']>concurrency:
                            raise ValueError('Observed traffic exceeds exclusive client bound')
                        if m['kv']>.90 or m['preemptions']>baseline[port]['preemptions']:
                            raise ValueError('Unsafe measured load; drain plateau')
                    except Exception as exc:
                        errors.append(f'{port}: telemetry {exc!r}')
                        if dispatch_end is None:dispatch_end=min(time.monotonic(),deadline)
                        stop.set();break
                write_json(root/'progress.json',dict(issued=dict(issued),completed_including_drain={p:counters[p]['completed'] for p in PORTS},
                    elapsed=time.monotonic()-started,errors=errors,admission_authorized=False))
            if dispatch_end is None:dispatch_end=min(time.monotonic(),deadline)
        watcher=asyncio.create_task(monitor())
        clients=[asyncio.create_task(worker(p,i)) for p in PORTS for i in range(concurrency)]
        try:
            await asyncio.gather(*clients)
        except BaseException:
            stop.set()
            await asyncio.gather(*clients,return_exceptions=True)
            drained.set()
            await watcher
            raise
        # A signal may end dispatch early; do not count the drain as plateau time.
        if dispatch_end is None:dispatch_end=min(time.monotonic(),deadline)
        drained_at=time.monotonic()
        stop.set();drained.set();await watcher
        if getattr(stop,'requested_at',None) is not None:
            dispatch_end=max(started,min(deadline,stop.requested_at))
        actual=max(0,dispatch_end-started)
        servers={}
        for port in PORTS:
            oom=None;log_evidence=None
            # Preserve the failure window even when an OOM has killed the server.
            try:
                stream,start=logs[port]
                log_evidence=log_finish(receipt['servers'][port]['log_path'],stream,start,root/f'server-{port}.log')
                oom=log_evidence['oom_matching_lines']
            except Exception as exc:errors.append(f'{port}: log evidence {exc!r}')
            try:
                lifecycle_live(Path(receipt['lifecycle_root']),receipt['endpoints']['supervisor'])
                for path,sha in receipt['bundle_pins'].items():
                    if file_hash(path)!=sha:raise ValueError('Lifecycle bundle drift')
                if process_identity(receipt['servers'][port],port)!=identities[port]:raise ValueError('Server changed')
                await check_health(monitor_session,port,manifest)
                sample=await snapshot(monitor_session,port);final=sample['parsed']
                write_json(root/'telemetry'/f'{port}-final.json',sample)
                if final['preemptions']<latest[port]['preemptions'] or final['completed']<latest[port]['completed']:
                    raise ValueError('Final telemetry counter reset')
                latest[port]=final;high[port]=max(high[port],final['kv'])
                if final['running'] or final['waiting'] or final['completed']-baseline[port]['completed']!=counters[port]['completed']:
                    raise ValueError('Nonidle/foreign or unknown completion after client drain')
            except Exception as exc:errors.append(f'{port}: final evidence {exc!r}')
            values=counters[port]
            servers[port]=dict(aggregate_concurrency=concurrency,max_num_seqs=receipt['servers'][port]['max_num_seqs'],
                **completion_windows(values['events'],started,dispatch_end,drained_at),kv_high_water=high[port],
                preemptions_delta=latest[port]['preemptions']-baseline[port]['preemptions'],
                request_errors_delta=values['request_errors'],oom_count=oom,
                telemetry_baseline=baseline[port],telemetry_final=latest[port],
                issued=issued[port],server_log_evidence=log_evidence)
        covered={g for values in servers.values() for g in values['completed_groups']}
        if covered!=FAMILIES|{'held-qa','held-fars'}:
            errors.append('Plateau did not complete every workload group; no representative capacity claim')
        # Existing profile validator does not inspect arbitrary validity flags.
        # Null error count explicitly prevents approval when evidence is incomplete.
        if errors or actual<duration:
            for s in servers.values():s['request_errors_delta']=None
        return dict(model=manifest['model'],revision=manifest['revision'],duration_seconds=actual,
            run_id=run_id,unique_cache_salt_per_request=True,
            pressure_scope='conservative uncached-prefix ramp; not production cache-hit distribution',
            started_at=started_at,dispatch_ended_at=started_at+actual,finished_at=time.time(),
            total_seconds_including_drain=drained_at-started,
            evidence_finalization_seconds=time.monotonic()-drained_at,servers=servers,errors=errors,
            evidence_complete=not errors and actual>=duration,capacity_approved=False,
            admission_authorized=False,publication_allowed=False)


async def run(root,workload,server_receipt,authorization,concurrency,duration=300,poll=2):
    import aiohttp
    if type(duration) is not int or not 300<=duration<=1800 or not .1<=poll<=10:
        raise ValueError('Require300..1800 second plateau and0.1..10 second telemetry interval')
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'lock'):
        if any(p.name!='lock' for p in root.iterdir()):raise ValueError('Fresh plateau root required; no blind replay')
        manifest=frozen.verify(workload);approval=load(authorization)
        if not server_receipt.is_dir():raise ValueError('Owned lifecycle receipt directory required')
        receipt=lifecycle_bundle(server_receipt,manifest,concurrency)
        receipt_hash=digest(receipt['bundle_pins'])
        server_contract(receipt,manifest,concurrency)
        if (approval.get('measurement_authorized') is not True or approval.get('exclusive_endpoints') is not True
                or approval.get('source_audits_drained') is not True
                or approval.get('workload_manifest_sha256')!=file_hash(workload/'manifest.json')
                or approval.get('server_receipt_sha256')!=receipt_hash):
            raise ValueError('Explicit exclusive measurement authorization required')
        cases=load(workload/'requests.json')
        tokenizer.tokenizer_init(manifest['snapshot'])
        for case in cases:
            if measure_prompt(case['request'],tokenizer.TOKENIZER)!=case['budget']:
                raise ValueError('Frozen full prompt/native budget drift')
        config=dict(workload=str(workload.resolve()),workload_manifest_sha256=file_hash(workload/'manifest.json'),
            server_receipt=receipt,server_receipt_sha256=receipt_hash,authorization=approval,
            concurrency_per_server=concurrency,requested_seconds=duration,poll_seconds=poll,
            code_sha256=file_hash(__file__),admission_authorized=False)
        write_json(root/'run.json',config)
        stop=TimedStop();loop=asyncio.get_running_loop()
        for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop.set)
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
                    connector=aiohttp.TCPConnector(limit=8*concurrency,limit_per_host=concurrency)) as session, \
                    aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4),
                    connector=aiohttp.TCPConnector(limit=8)) as monitor:
                result=await plateau(root,manifest,cases,receipt,concurrency,duration,poll,session,stop,monitor)
            result['run_sha256']=file_hash(root/'run.json')
            evidence={str(p.relative_to(root)):dict(sha256=file_hash(p),bytes=p.stat().st_size)
                for p in sorted(root.rglob('*')) if p.is_file() and p.name!='lock'}
            write_json(root/'evidence-index.json',evidence)
            result['evidence_index_sha256']=file_hash(root/'evidence-index.json')
            write_json(root/'measurement.json',result)
            write_json(root/'seal.json',dict(measurement_sha256=file_hash(root/'measurement.json'),
                run_sha256=file_hash(root/'run.json'),capacity_approved=False))
            return result
        except BaseException as exc:
            write_json(root/'failed.json',dict(error=repr(exc),capacity_approved=False,admission_authorized=False))
            raise
        finally:
            for sig in (signal.SIGINT,signal.SIGTERM):loop.remove_signal_handler(sig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--balanced',type=Path,default=Path('data/dfm13/gemma31-balanced-execution-20261003-v2'))
    p.add_argument('--qa',type=Path,default=Path('data/dfm13/baltic/qa31-article-full-consumer-v3'))
    p.add_argument('--fars',type=Path,default=Path('data/dfm13/wave4/fars-summary-31b-consumer-capacity-v2'))
    p.add_argument('--ready',type=Path,default=Path('data/dfm13/wave4/gemma31-download/ready.json'))
    p.add_argument('--workload',type=Path);p.add_argument('--server-receipt',type=Path);p.add_argument('--authorization',type=Path)
    p.add_argument('--concurrency',type=int,default=2);p.add_argument('--duration',type=int,default=300);p.add_argument('--poll',type=float,default=2)
    a=p.parse_args()
    if a.command=='prepare':result=prepare(a.root,a.balanced,a.qa,a.fars,a.ready)
    elif a.command=='verify':
        m=frozen.verify(a.root);result=dict(valid=True,count=m['count'])
    else:
        if None in (a.workload,a.server_receipt,a.authorization):raise ValueError('Workload,server receipt and authorization required')
        result=asyncio.run(run(a.root,a.workload,a.server_receipt,a.authorization,a.concurrency,a.duration,a.poll))
    print(json.dumps(result))


if __name__=='__main__':main()
