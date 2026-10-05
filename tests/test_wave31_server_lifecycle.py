"""Mocked lifecycle only: no GPU probes, sockets, HTTP, signals or servers."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import wave31_server_lifecycle as s
from dfm12.io import file_hash, load, write_json


def ready_fixture(tmp_path, monkeypatch):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    write_json(snapshot / 'model.safetensors.index.json', {'weight_map': {'x': 'weights'}})
    (snapshot / 'weights').write_bytes(b'mock')
    pins = {str(snapshot / 'model.safetensors.index.json'): file_hash(snapshot / 'model.safetensors.index.json')}
    monkeypatch.setattr(s, 'model_files', lambda path: pins)
    ready = tmp_path / 'ready.json'
    write_json(ready, dict(model=s.MODEL, all_files_verified=True, revision='mock-only',
        snapshot=str(snapshot), model_files=pins, files=[dict(name='weights', size=4)]))
    monkeypatch.setattr(s.capacity, 'DOWNLOAD', tmp_path)
    return ready


@pytest.mark.parametrize('seq', [16, 32, 64, 128])
def test_ramp_configuration(tmp_path, monkeypatch, seq):
    config = s.configuration('ramp', ready_fixture(tmp_path, monkeypatch), seq, 8)
    assert config['max_num_seqs'] == seq
    assert config['measurements_generated'] is False


@pytest.mark.parametrize('seq,c', [(8, 8), (256, 8), (True, 1), (16, 17), (128, 65), (16, 0)])
def test_invalid_ramp(tmp_path, monkeypatch, seq, c):
    with pytest.raises(ValueError):
        s.configuration('ramp', ready_fixture(tmp_path, monkeypatch), seq, c)


def profile_fixture(tmp_path, monkeypatch):
    ready = ready_fixture(tmp_path, monkeypatch)
    measurement = tmp_path / 'measurement.json'
    write_json(measurement, dict(model=s.MODEL, revision='mock-only', duration_seconds=300,
        servers={str(p): dict(aggregate_concurrency=32, max_num_seqs=64, completed=10,
            kv_high_water=.8, preemptions_delta=0, request_errors_delta=0,
            oom_count=0, p95_seconds=10) for p in range(8800, 8808)}))
    profile = tmp_path / 'profile.json'
    write_json(profile, dict(model=s.MODEL, revision='mock-only',
        aggregate_client_concurrency_per_server=32, server_max_num_seqs=64,
        client_allocations={'wave4':24, 'baltic':8},
        measurements=[dict(path=str(measurement), sha256=file_hash(measurement))],
        selected_after_ramp_review=True, reviewer='mock-only'))
    return ready, profile


def test_production_uses_measured_settings_no_overrides(tmp_path, monkeypatch):
    ready, profile = profile_fixture(tmp_path, monkeypatch)
    config = s.configuration('production', ready, profile_path=profile)
    assert config['max_num_seqs'] == 64
    assert config['aggregate_client_concurrency_per_server'] == 32
    assert config['client_allocations'] == {'wave4':24, 'baltic':8}
    for kwargs in ({}, {'profile_path':profile, 'max_num_seqs':128},
                   {'profile_path':profile, 'concurrency':16}):
        with pytest.raises(ValueError):
            s.configuration('production', ready, **kwargs)
    bad = load(profile); bad['measurements'] = []; write_json(profile, bad)
    with pytest.raises(ValueError):
        s.configuration('production', ready, profile_path=profile)


@pytest.mark.parametrize('change', ['model', 'snapshot', 'pins', 'shards'])
def test_wrong_snapshot_receipt(tmp_path, monkeypatch, change):
    ready = ready_fixture(tmp_path, monkeypatch); data = load(ready)
    if change == 'model': data['model'] = 'old26B'
    if change == 'snapshot': data['snapshot'] = 'relative'
    if change == 'pins': data['model_files'] = {}
    if change == 'shards': data['files'][0]['size'] = 99
    write_json(ready, data)
    with pytest.raises(ValueError): s.configuration('ramp', ready, 16, 8)


def mocked_lifecycle(tmp_path, monkeypatch, *, bad_health=False, busy=False, fail_spawn=None):
    calls, cleaned, checked, ports = [], [], [], []
    original = s.runpy.run_path
    root = tmp_path / 'lifecycle'
    config = dict(mode='ramp', model=s.MODEL, snapshot='/mock/snapshot', revision='mock-only',
        max_num_seqs=64, aggregate_client_concurrency_per_server=32, client_allocations=None, pins={})

    def popen(command, **kwargs):
        assert kwargs['start_new_session'] is True
        if fail_spawn is not None and len(calls) == fail_spawn:
            raise OSError('mock spawn failure')
        calls.append((list(command), kwargs['env']))
        return SimpleNamespace(pid=900000+len(calls), poll=lambda: None)

    def check(endpoint, snapshot, context):
        checked.append(endpoint)
        document = {'data':[dict(id=s.MODEL, root=snapshot, max_model_len=context)]}
        if bad_health and endpoint.endswith('8807/v1'):
            field, value = {'model':('id','old26B'), 'snapshot':('root','/wrong/snapshot'),
                            'context':('max_model_len',8192)}[bad_health]
            document['data'][0][field] = value
        return s.health.validate(document, snapshot, context)

    monkeypatch.setattr(s.subprocess, 'Popen', popen)
    monkeypatch.setattr(s.health, 'check', check)
    monkeypatch.setattr(s, 'remember', lambda record: None)
    monkeypatch.setattr(s, 'cleanup', lambda directory, record:
        cleaned.append(record) or {'survivors':[]})

    def run_path(path):
        module = original(path); ns = module['main'].__globals__
        ns['available'] = lambda: (not busy, [dict(index=i, uuid=f'mock-gpu-{i}') for i in range(8)])
        ns['identity'] = lambda pid: dict(pid=pid, create_time=1, start_ticks='1', session_id=pid)
        ns['signal'] = SimpleNamespace(SIGINT=2, SIGTERM=15, signal=lambda *args: None)
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def bind(self, address): ports.append(address)
        ns['socket'] = SimpleNamespace(socket=Socket)
        ns['time'] = SimpleNamespace(monotonic=lambda:0, time=lambda:0,
            sleep=lambda seconds:(root/'stop.request').touch())
        return module
    monkeypatch.setattr(s.runpy, 'run_path', run_path)
    return root, config, calls, cleaned, checked, ports


def test_actual_commands_receipts_all8_and_cleanup(tmp_path, monkeypatch):
    root, config, calls, cleaned, checked, ports = mocked_lifecycle(tmp_path, monkeypatch)
    s.serve(root, config)
    assert len(calls) == len(cleaned) == len(checked) == 8
    assert len(ports) == 16
    for i, (cmd, env) in enumerate(calls):
        for opt, val in {'--model':'/mock/snapshot', '--served-model-name':s.MODEL,
                         '--max-num-seqs':'64', '--max-model-len':'32768',
                         '--max-num-batched-tokens':'16384', '--tensor-parallel-size':'1',
                         '--gpu-memory-utilization':'.95', '--port':str(8800+i),
                         '--tool-call-parser':'gemma4', '--reasoning-parser':'gemma4'}.items():
            assert cmd[cmd.index(opt)+1] == val
        assert 'google/gemma-4-26B-A4B-it' not in cmd and '--enforce-eager' not in cmd
        assert env['CUDA_VISIBLE_DEVICES'] == f'mock-gpu-{i}'
        assert env['VLLM_PORT'] == str(32000+100*i)
        assert load(root/f'gpu{i}/ownership.json')['command'] == cmd
        receipt = load(root/'commands.json')[i]
        for key, folder in [('VLLM_CACHE_ROOT', 'vllm'),
                            ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
                            ('TRITON_CACHE_DIR', 'triton'), ('CUDA_CACHE_PATH', 'cuda')]:
            expected = root / 'compile-cache' / f'mock-gpu-{i}' / folder
            assert env[key] == str(expected.resolve())
            assert expected.is_dir()
            assert receipt['cache_environment'][key] == env[key]
        assert receipt['endpoint'] == f'http://127.0.0.1:{8800+i}/v1'
        assert Path(receipt['log_path']).is_file()
    endpoints = load(root/'endpoints.json')
    assert endpoints['max_num_seqs'] == 64 and endpoints['source_model'] == s.MODEL
    assert len(endpoints['metrics_endpoints']) == 8
    assert load(root/'ready.json')['all_eight_verified'] is True
    assert load(root/'stopped.json')['cleanup_survivors'] == []


@pytest.mark.parametrize('bad', ['model','snapshot','context'])
def test_bad_eighth_model_never_ready_cleans_owned(tmp_path, monkeypatch, bad):
    root, config, calls, cleaned, checked, _ = mocked_lifecycle(tmp_path, monkeypatch, bad_health=bad)
    with pytest.raises(ValueError): s.serve(root, config)
    assert len(calls) == len(cleaned) == len(checked) == 8
    assert not (root/'ready.json').exists()


def test_partial_launch_cleans_only_started(tmp_path, monkeypatch):
    root, config, calls, cleaned, _, _ = mocked_lifecycle(tmp_path, monkeypatch, fail_spawn=2)
    with pytest.raises(OSError): s.serve(root, config)
    assert len(calls) == len(cleaned) == 2


def test_busy_devices_no_spawn_or_signal(tmp_path, monkeypatch):
    root, config, calls, cleaned, _, ports = mocked_lifecycle(tmp_path, monkeypatch, busy=True)
    with pytest.raises(RuntimeError): s.serve(root, config)
    assert calls == cleaned == ports == []


def test_existing_root_refused(tmp_path, monkeypatch):
    root, config, calls, cleaned, _, _ = mocked_lifecycle(tmp_path, monkeypatch)
    root.mkdir(); write_json(root/'ownership.json', {'foreign':'preserve'})
    with pytest.raises(FileExistsError): s.serve(root, config)
    assert load(root/'ownership.json') == {'foreign':'preserve'}
    assert calls == cleaned == []


def test_drifted_input_prevents_launch(tmp_path, monkeypatch):
    root, config, calls, cleaned, _, _ = mocked_lifecycle(tmp_path, monkeypatch)
    pin = tmp_path/'pin'; pin.write_text('before')
    config['pins'] = {str(pin): file_hash(pin)}; pin.write_text('after')
    with pytest.raises(ValueError, match='Launch input changed'): s.serve(root, config)
    assert calls == cleaned == []


def test_reused_session_cannot_authorize_discovery(monkeypatch):
    record = dict(server_session=100, owner='token', created_at=1,
                  owned=[dict(pid=100, start_ticks='old', create_time=1, session_id=100)])
    monkeypatch.setattr(s.diagnostic, 'identity', lambda pid:
        dict(pid=pid, start_ticks='new', create_time=100, session_id=100))
    calls=[]
    monkeypatch.setattr(s.session_cleanup, 'remember', lambda r:calls.append('unsafe-session'))
    monkeypatch.setattr(s.diagnostic, 'remember', lambda r:calls.append('token-only'))
    s.remember(record)
    assert calls == ['token-only']


def test_cleanup_failure_does_not_skip_other_sessions(tmp_path, monkeypatch):
    root, config, calls, _, _, _ = mocked_lifecycle(tmp_path, monkeypatch)
    cleaned = []
    def cleanup(directory, record):
        cleaned.append(record['server_session'])
        if len(cleaned) == 1: raise OSError('mock cleanup failure')
        return {'survivors':[]}
    monkeypatch.setattr(s, 'cleanup', cleanup)
    with pytest.raises(RuntimeError, match='cleanup survivors'): s.serve(root, config)
    assert len(calls) == len(cleaned) == 8
    assert load(root/'stopped.json')['cleanup_survivors'][0]['pid'] == cleaned[0]


def test_exact_cleanup_never_signals_reused_pid(tmp_path, monkeypatch):
    h = s.session_cleanup
    record = dict(server_session=100, owner='token', created_at=1,
        owned=[dict(pid=p, start_ticks='old', create_time=1, session_id=100) for p in (100,101)])
    def identity(pid):
        return dict(pid=pid, start_ticks='new' if pid==100 else 'old',
                    create_time=20 if pid==100 else 1, session_id=100)
    signals=[]
    monkeypatch.setattr(s.diagnostic, 'identity', identity)
    monkeypatch.setattr(h, 'identity', identity)
    monkeypatch.setattr(h, 'remember', lambda r:None)
    monkeypatch.setattr(h, 'pidfd_open', lambda pid:pid)
    monkeypatch.setattr(h, 'pidfd_signal', lambda fd,sig:signals.append(fd))
    monkeypatch.setattr(h, 'os', SimpleNamespace(close=lambda fd:None))
    monkeypatch.setattr(h, 'time', SimpleNamespace(sleep=lambda seconds:None,time=lambda:0))
    monkeypatch.setattr(h, 'psutil', SimpleNamespace(Error=RuntimeError,STATUS_ZOMBIE='zombie',
        Process=lambda pid:SimpleNamespace(status=lambda:'running')))
    s.cleanup(tmp_path, record)
    assert signals == [101,101]


def test_symlinked_snapshot_metadata_pins(tmp_path, monkeypatch):
    ready = ready_fixture(tmp_path, monkeypatch)
    data = load(ready); original = Path(data['snapshot'])/'model.safetensors.index.json'
    backing = tmp_path/'index-blob'; original.rename(backing); original.symlink_to(backing)
    assert s.configuration('ramp', ready, 16, 8)['max_num_seqs'] == 16
