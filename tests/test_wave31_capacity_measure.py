"""Synthetic CPU-only fixtures; no measurement here is real capacity evidence."""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from dfm12 import wave31_capacity_measure as m
from dfm12 import wave31_capacity as validator
from dfm12.io import digest,write_json,file_hash


def metric_text(kv=.4):
    return '\n'.join(f'{k} {v}' for k,v in {
        'vllm:kv_cache_usage_perc':kv,'vllm:num_requests_running':2,
        'vllm:num_requests_waiting':0,'vllm:num_preemptions_total':0,
        'vllm:request_success_total':3}.items())+'\n'


def test_metrics_and_percentile():
    assert m.metrics(metric_text())==dict(kv=.4,running=2,waiting=0,preemptions=0,completed=3)
    assert m.p95(list(range(1,101)))==95 and m.p95([]) is None


@pytest.mark.parametrize('text',['',metric_text(float('nan')),metric_text(1.1),metric_text(-.1)])
def test_bad_metrics_fail_closed(text):
    with pytest.raises(ValueError):m.metrics(text)


def test_full_native_budget():
    p=dict(model=m.health.MODEL,max_tokens=8192,chat_template_kwargs={'enable_thinking':True},
           messages=[{'role':'user','content':'full text'}],tools=[{'type':'function'}])
    class T:
        def apply_chat_template(self,messages,**kw):
            assert messages==p['messages'] and kw['tools']==p['tools'] and kw['enable_thinking']
            return [1]*24000
    assert m.measure_prompt(p,T())['total_tokens']==32192
    p['max_tokens']=9000
    with pytest.raises(ValueError):m.measure_prompt(p,T())


def test_unique_cache_salt_changes_only_wire_metadata():
    request=dict(model=m.health.MODEL,max_tokens=8192,chat_template_kwargs={'enable_thinking':True},
        messages=[dict(role='user',content='unchanged complete prompt')])
    case=dict(id='test',request=request)
    one,binding=m.wire_request(case,'run-one','8800',0)
    two,_=m.wire_request(case,'run-one','8800',1)
    three,_=m.wire_request(case,'run-two','8800',0)
    assert len({one['cache_salt'],two['cache_salt'],three['cache_salt']})==3
    assert {k:v for k,v in one.items() if k!='cache_salt'}==request
    assert 'cache_salt' not in request and binding['frozen_request_sha256']==digest(request)
    assert binding['request_sha256']==digest(one) and binding['request_sha256']!=digest(request)
    class T:
        def apply_chat_template(self,messages,**kwargs):return [1,2,3]
    old=m.measure_prompt(request,T());new=m.measure_prompt(one,T())
    assert old['token_ids_sha256']==new['token_ids_sha256'] and old['total_tokens']==new['total_tokens']


def test_preexisting_cache_salt_refused():
    with pytest.raises(ValueError):m.wire_request({'request':{'cache_salt':'reused'}},'run','8800',0)


def test_log_window_and_rotation(tmp_path):
    path=tmp_path/'server.log';path.write_bytes(b'previous OOM ignored\n')
    stream,start=m.log_start(path)
    with path.open('ab') as f:f.write(b'normal\nCUDA out of memory\n')
    result=m.log_finish(path,stream,start,tmp_path/'captured.log');stream.close()
    assert result['oom_matching_lines']==1
    assert (tmp_path/'captured.log').read_bytes()==b'normal\nCUDA out of memory\n'
    stream,start=m.log_start(path);path.unlink();path.write_bytes(b'replaced')
    with pytest.raises(ValueError):m.log_finish(path,stream,start,tmp_path/'bad.log')
    stream.close()


def lifecycle_fixture(root):
    manifest=dict(model=m.health.MODEL,revision='synthetic-test',snapshot='/synthetic/snapshot')
    config=dict(manifest,schema='wave31-server-lifecycle-v1',mode='ramp',pins={},
        tensor_parallel_size=1,gpu_memory_utilization=.95,max_model_len=32768,
        max_num_batched_tokens=16384,max_num_seqs=16,aggregate_client_concurrency_per_server=8)
    commands=[];documents={}
    for i,port in enumerate(m.PORTS):
        endpoint=f'http://127.0.0.1:{port}/v1';owner=root/f'owner{i}.json'
        cmd=[str(m.AUDIT_PYTHON),'vllm','--model',manifest['snapshot'],'--port',port,'--max-num-seqs','16',
             '--tensor-parallel-size','1','--gpu-memory-utilization','.95','--max-model-len','32768',
             '--max-num-batched-tokens','16384']
        write_json(owner,dict(server_session=100+i,command=cmd,owned=[dict(pid=100+i,start_ticks='123')]))
        commands.append(dict(endpoint=endpoint,ownership_path=str(owner),command=cmd,pid=100+i,
            log_path=str(root/f'server{i}.log'),gpu_uuid='test-'+str(i),internal_port=str(32000+i*100)))
        documents[endpoint]=dict(data=[dict(id=m.health.MODEL,root=manifest['snapshot'],max_model_len=32768)])
    write_json(root/'configuration.json',config);write_json(root/'commands.json',commands)
    write_json(root/'endpoints.json',dict(endpoints=list(documents),max_num_seqs=16,supervisor={'pid':1},
        metrics_endpoints=[e.removesuffix('/v1')+'/metrics' for e in documents]))
    write_json(root/'ready.json',dict(all_eight_verified=True,endpoints=documents))
    return manifest


def test_real_lifecycle_schema_binding(tmp_path,monkeypatch):
    manifest=lifecycle_fixture(tmp_path)
    monkeypatch.setattr(m,'lifecycle_live',lambda *a:None)
    receipt=m.lifecycle_bundle(tmp_path,manifest,8)
    assert len(receipt['servers'])==8 and len(receipt['bundle_pins'])==3
    old_pins=dict(receipt['bundle_pins'])
    owner=m.load(tmp_path/'owner0.json')
    owner['owned'].append(dict(pid=999,start_ticks='999'))
    write_json(tmp_path/'owner0.json',owner)
    refreshed=m.lifecycle_bundle(tmp_path,manifest,8)
    assert refreshed['bundle_pins']==old_pins
    assert refreshed['servers']['8800']['ownership_snapshot_sha256']!=receipt['servers']['8800']['ownership_snapshot_sha256']
    assert m.server_contract(receipt,manifest,8)==16
    with pytest.raises(ValueError):m.lifecycle_bundle(tmp_path,manifest,32)
    config=m.load(tmp_path/'configuration.json');config['max_num_seqs']=32
    write_json(tmp_path/'configuration.json',config)
    with pytest.raises(ValueError):m.lifecycle_bundle(tmp_path,manifest,8)


@pytest.mark.parametrize('n',[0,True,65,1024])
def test_aggregate_bounds(n):
    with pytest.raises(ValueError):m.server_contract({}, {}, n)


def fake_plateau(tmp_path,monkeypatch,interrupt=False,fail=False):
    counts={p:0 for p in m.PORTS};active={p:0 for p in m.PORTS};peak={p:0 for p in m.PORTS}
    receipt=dict(lifecycle_root=str(tmp_path),endpoints={'supervisor':{}},bundle_pins={},servers={})
    for port in m.PORTS:
        log=tmp_path/f'input-{port}.log';log.touch()
        receipt['servers'][port]=dict(pid=100,start_ticks=1,max_num_seqs=16,log_path=str(log))
    monkeypatch.setattr(m,'process_identity',lambda *a:{'synthetic':True})
    monkeypatch.setattr(m,'lifecycle_live',lambda *a:None)
    async def health(*a):return {'synthetic':True}
    async def snapshot(session,port):
        return dict(time=0,raw='synthetic fixture',parsed=dict(kv=.2,running=active[port],waiting=0,preemptions=0,completed=counts[port]))
    async def query(session,endpoint,payload,writer,record):
        port=record['port'];active[port]+=1;peak[port]=max(peak[port],active[port])
        rid=writer.begin(endpoint,payload,record)
        await asyncio.sleep(.08 if interrupt else .002)
        active[port]-=1
        if fail:
            writer.finish(rid,status=500,transport_error='synthetic')
            raise RuntimeError('synthetic failure')
        counts[port]+=1;writer.finish(rid,status=200,raw_body_utf8='synthetic fixture')
        return dict(finish_reason='stop',content='{}',raw_request_id=rid)
    monkeypatch.setattr(m,'check_health',health);monkeypatch.setattr(m,'snapshot',snapshot);monkeypatch.setattr(m,'raw_query',query)
    cases=[dict(id=g,group=g,request={'synthetic-test':True}) for g in sorted(m.FAMILIES|{'held-qa','held-fars'})]
    async def go():
        stop=m.TimedStop()
        if interrupt:asyncio.get_running_loop().call_later(.015,stop.set)
        result=await m.plateau(tmp_path,dict(model=m.health.MODEL,revision='synthetic-test'),cases,
            receipt,2,.1,.005,None,stop)
        assert not any(active.values()) and max(peak.values())<=2
        return result
    return asyncio.run(go())


def test_mock_plateau_schema_and_profile_compatibility(tmp_path,monkeypatch):
    result=fake_plateau(tmp_path,monkeypatch)
    assert result['evidence_complete'] and not result['capacity_approved']
    assert all(s['completed']>0 and s['oom_count']==0 for s in result['servers'].values())
    raw=[m.load(p) for p in (tmp_path/'raw').glob('*.request.json')]
    assert len({r['request']['cache_salt'] for r in raw})==len(raw)
    assert all(digest(r['request'])==r['metadata']['request_sha256'] for r in raw)
    # Explicit synthetic300s fixture: never written into production artifacts.
    synthetic=copy.deepcopy(result);synthetic['duration_seconds']=300
    write_json(tmp_path/'ready.json',dict(revision='synthetic-test'))
    monkeypatch.setattr(validator,'DOWNLOAD',tmp_path)
    write_json(tmp_path/'measurement.json',synthetic)
    profile=dict(model=m.health.MODEL,revision='synthetic-test',aggregate_client_concurrency_per_server=2,
        server_max_num_seqs=16,client_allocations=dict(wave4=1,baltic=1),
        measurements=[dict(path=str(tmp_path/'measurement.json'),sha256=file_hash(tmp_path/'measurement.json'))],
        selected_after_ramp_review=True,reviewer='SYNTHETIC UNIT TEST NOT APPROVAL')
    assert validator.validate(profile)==(2,16)


def test_interruption_drains_without_counting_drain_as_plateau(tmp_path,monkeypatch):
    result=fake_plateau(tmp_path,monkeypatch,interrupt=True)
    assert result['duration_seconds']<.07 and result['total_seconds_including_drain']>=.08
    assert not result['evidence_complete']
    assert all(s['request_errors_delta'] is None for s in result['servers'].values())
    assert all(s['completed']==0 and s['drain_completed']==2 and s['total_completed']==2 for s in result['servers'].values())


def test_completion_rate_uses_matching_plateau_and_drain_windows():
    events=[(100,10,'test','stop'),(299,20,'test','stop'),(301,30,'test','length'),(329,40,'test','stop')]
    result=m.completion_windows(events,0,300,330)
    assert result['completed']==result['plateau_completed']==2
    assert result['drain_completed']==2 and result['total_completed']==4
    assert result['plateau_completed_per_second']==pytest.approx(2/300)
    assert result['drain_completed_per_second']==pytest.approx(2/30)
    assert result['total_completed_per_second']==pytest.approx(4/330)
    assert result['p95_seconds']==20 and result['total_p95_seconds']==40


def test_request_failures_stop_dispatch_and_remain_invalid(tmp_path,monkeypatch):
    result=fake_plateau(tmp_path,monkeypatch,fail=True)
    assert result['errors'] and not result['evidence_complete']
    assert all(s['request_errors_delta'] is None for s in result['servers'].values())


def test_run_uses_keepalive_and_separate_telemetry_pool(tmp_path,monkeypatch):
    import aiohttp
    workload=tmp_path/'workload';workload.mkdir()
    manifest=dict(model=m.health.MODEL,revision='synthetic-test',snapshot='/synthetic')
    write_json(workload/'manifest.json',manifest)
    write_json(workload/'requests.json',[dict(request={},budget={})])
    lifecycle=tmp_path/'lifecycle';lifecycle.mkdir()
    receipt=dict(manifest,bundle_pins={},servers={p:dict(max_num_seqs=16,
        log_path=str(tmp_path/(p+'.log'))) for p in m.PORTS})
    approval=tmp_path/'approval.json'
    write_json(approval,dict(measurement_authorized=True,exclusive_endpoints=True,
        source_audits_drained=True,workload_manifest_sha256=file_hash(workload/'manifest.json'),
        server_receipt_sha256=digest({})))
    monkeypatch.setattr(m.frozen,'verify',lambda _:manifest)
    monkeypatch.setattr(m,'lifecycle_bundle',lambda *a:receipt)
    monkeypatch.setattr(m.tokenizer,'tokenizer_init',lambda _:None)
    monkeypatch.setattr(m.tokenizer,'TOKENIZER',object(),raising=False)
    monkeypatch.setattr(m,'measure_prompt',lambda *a:{})
    sessions=[]
    class Session:
        def __init__(self,*,timeout,connector):
            self.timeout=timeout;self.connector=connector;sessions.append(self)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):await self.connector.close()
    monkeypatch.setattr(aiohttp,'ClientSession',Session)
    async def plateau(*args):
        client,monitor=args[7],args[9]
        assert client is not monitor
        assert client.connector.limit==64 and client.connector.limit_per_host==8
        assert monitor.connector.limit==8
        assert not client.connector.force_close and not monitor.connector.force_close
        return dict(synthetic_fixture=True,capacity_approved=False)
    monkeypatch.setattr(m,'plateau',plateau)
    result=asyncio.run(m.run(tmp_path/'probe',workload,lifecycle,approval,8))
    assert result['synthetic_fixture'] and len(sessions)==2
    assert all(s.connector.closed for s in sessions)
