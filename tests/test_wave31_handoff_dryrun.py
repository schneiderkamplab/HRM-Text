"""CPU-only launch rehearsal: never bind ports, signal, or create processes."""
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import wave4_gemma31_transition as transition
from dfm12 import wave4_gemma31_fresh as fresh


def test_exact_server_commands(tmp_path, monkeypatch):
    import dfm12.diagnostic_server as diagnostic
    import scripts.serve_dfm13_tp8_headroom as headroom

    commands = []
    original_run_path = transition.runpy.run_path
    original_argv = list(transition.sys.argv)
    monkeypatch.setattr(transition.sys, 'argv', original_argv)
    monkeypatch.setattr(diagnostic, 'remember', lambda record: None)
    monkeypatch.setattr(diagnostic, 'cleanup', lambda *args: None)
    monkeypatch.setattr(headroom, 'remember', lambda record: None)
    monkeypatch.setattr(headroom, 'cleanup', lambda *args: None)
    monkeypatch.setattr(transition, 'model_files', lambda path: {})

    def popen(command, **kwargs):
        commands.append({'command': list(command), 'gpu': kwargs['env']['CUDA_VISIBLE_DEVICES'],
                         'internal_port': kwargs['env']['VLLM_PORT']})
        assert kwargs['start_new_session'] is True
        return SimpleNamespace(pid=900000 + len(commands), poll=lambda: None)

    monkeypatch.setattr(transition.subprocess, 'Popen', popen)

    def run_path(path):
        module = original_run_path(path)
        ns = module['main'].__globals__
        ns['available'] = lambda: (True, [{'uuid': f'mock-gpu-{i}'} for i in range(8)])
        ns['identity'] = lambda pid: {'pid': pid, 'create_time': 1}
        ns['signal'] = SimpleNamespace(SIGINT=2, SIGTERM=15, signal=lambda *args: None)
        class Socket:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def bind(self, address): pass
        ns['socket'] = SimpleNamespace(socket=Socket)
        # Exercise the real ready() parser with a fake HTTP response.
        ns['urllib'] = SimpleNamespace(request=SimpleNamespace(urlopen=lambda *a, **k:
            io.StringIO(json.dumps({'data': [{'id': transition.MODEL,
                                            'max_model_len': 32768}]}))))
        ns['time'] = SimpleNamespace(monotonic=lambda: 0, time=lambda: 0,
            sleep=lambda seconds: (tmp_path / 'servers' / 'stop.request').touch())
        return module

    monkeypatch.setattr(transition.runpy, 'run_path', run_path)
    snapshot = Path('/mock/verified-gemma31-snapshot')
    transition.serve(tmp_path / 'servers', snapshot)
    assert len(commands) == 8
    for i, row in enumerate(commands):
        cmd = row['command']
        for option, value in {'--model': str(snapshot), '--served-model-name': transition.MODEL,
                              '--port': str(8800+i), '--tensor-parallel-size': '1',
                              '--gpu-memory-utilization': '.95', '--max-num-seqs': '8',
                              '--max-model-len': '32768', '--max-num-batched-tokens': '16384',
                              '--tool-call-parser': 'gemma4', '--reasoning-parser': 'gemma4'}.items():
            assert cmd[cmd.index(option)+1] == value
        assert 'google/gemma-4-26B-A4B-it' not in cmd
        assert '--enforce-eager' not in cmd
        assert row['gpu'] == f'mock-gpu-{i}'
        assert row['internal_port'] == str(32000+100*i)
    endpoints = json.loads((tmp_path/'servers/endpoints.json').read_text())
    assert endpoints['source_model'] == transition.MODEL
    assert endpoints['max_num_seqs'] == 8
    assert json.loads((tmp_path/'servers/status.json').read_text())['ready'] == [True]*8
    if destination := os.environ.get('WAVE31_DRYRUN_RECEIPT'):
        Path(destination).write_text(json.dumps({'mock_only': True, 'gpu_calls': 0,
            'commands': commands, 'advertised_metadata': endpoints}, indent=2)+'\n')


@pytest.mark.parametrize('models', [[], [{'id': transition.MODEL, 'max_model_len': 8192}],
    [{'id': transition.MODEL, 'max_model_len': '32768'}],
    [{'id': 'google/gemma-4-26B-A4B-it', 'max_model_len': 32768}],
    [{'id': transition.MODEL, 'max_model_len': 32768}, {'id': 'old'}]])
def test_fresh_readiness_rejects_incompatible(models):
    with pytest.raises(ValueError):
        fresh.endpoint_limit({'data': models})


def test_fresh_readiness_accepts_31b_32k():
    assert fresh.endpoint_limit({'data': [{'id': transition.MODEL,
                                          'max_model_len': 32768}]}) == 32768


def test_transition_sequence_mocked(tmp_path, monkeypatch):
    import dfm12.european_campaign as campaign
    events = []
    old = {'pid': 123, 'start_ticks': '1'}
    contract = tmp_path/'contract.json'
    contract.write_text(json.dumps({'model': transition.MODEL, 'model_files': {},
                                    'supervisor': old}))
    old_root = tmp_path/'old'
    old_root.mkdir()
    (old_root/'endpoints.json').write_text(json.dumps({'supervisor': old}))
    monkeypatch.setattr(transition, 'OLD', old_root)
    monkeypatch.setattr(transition, 'model_files', lambda path: {})
    monkeypatch.setattr(transition, 'verify_comparison', lambda root: 76)
    monkeypatch.setattr(transition, 'readiness', lambda value: events.append('drain-check') or {})
    monkeypatch.setattr(transition, 'alive', lambda value: 'signal-owned' not in events)
    monkeypatch.setattr(transition, 'pidfd_open', lambda pid: 99999)
    monkeypatch.setattr(transition, 'pidfd_signal', lambda *args: events.append('signal-owned'))
    monkeypatch.setattr(transition.os, 'close', lambda fd: None)
    monkeypatch.setattr(campaign, 'available', lambda: (True, []))
    monkeypatch.setattr(transition, 'identity', lambda pid: {'pid': pid})
    monkeypatch.setattr(transition.subprocess, 'Popen', lambda *a, **k:
        events.append('start-supervisor') or SimpleNamespace(pid=888, poll=lambda: None))
    monkeypatch.setattr(transition.urllib.request, 'urlopen', lambda *a, **k:
        events.append('model-readiness') or io.StringIO(json.dumps({'data': [
            {'id': transition.MODEL, 'max_model_len': 32768, 'root': str(tmp_path/'model')}]})))
    def run(command, **kwargs):
        assert command[command.index('-m')+1] == 'dfm12.european_stage'
        assert command.count('--endpoint') == 8
        assert command[command.index('--max-concurrency')+1] == '8'
        events.append('run-76')
    monkeypatch.setattr(transition.subprocess, 'run', run)
    monkeypatch.setattr(transition, 'terminal_database', lambda root: {'done': 76})
    transition.transition(tmp_path/'transition', contract, tmp_path/'model')
    assert events == ['drain-check', 'drain-check', 'signal-owned', 'start-supervisor',
                      *(['model-readiness']*8), 'run-76']
