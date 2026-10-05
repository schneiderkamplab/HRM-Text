import os
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from dfm12 import wave4_gemma31_transition as original
from dfm12.wave4_gemma31_transition_exited import load_transition
from dfm12 import wave4_gemma31_transition_exited as successor


def test_exited_identity_and_private_patch(monkeypatch):
    before = original.alive
    module = load_transition()

    def vanished(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(module, 'identity', vanished)
    assert module.alive({'pid': 123}) is False
    assert original.alive is before
    assert module.readiness.__globals__['alive'] is module.alive
    assert module.transition.__globals__['alive'] is module.alive


def test_live_and_reused_identity():
    module = load_transition()
    item = module.identity(os.getpid())
    assert module.alive(item) is True
    assert module.alive(dict(item, start_ticks='not-the-same-process')) is False


def test_access_denied_not_treated_as_exit(monkeypatch):
    module = load_transition()

    def denied(pid):
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(module, 'identity', denied)
    with pytest.raises(psutil.AccessDenied):
        module.alive({'pid': 123})


def test_exited_client_allows_other_readiness_checks(tmp_path, monkeypatch):
    module = load_transition()
    receipt = tmp_path / 'receipt.json'
    receipt.write_text('{}')

    def vanished(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(module, 'identity', vanished)
    monkeypatch.setattr(module, 'terminal_database', lambda p, auth: {'done': 1})
    contract = dict(cpu_preparation_complete=True, producers_frozen=True,
                    completion_receipts={str(receipt): module.file_hash(receipt)},
                    clients_and_producers=[{'pid': 123}], databases=['queue'])
    assert module.readiness(contract) == {'queue': {'done': 1}}
    contract['producers_frozen'] = False
    with pytest.raises(ValueError, match='not attested'):
        module.readiness(contract)


@pytest.mark.parametrize('fail', [False, True])
def test_serve_gpu_cache_isolation_and_restore(tmp_path, monkeypatch, fail):
    from dfm12 import diagnostic_server
    original_env = lambda memory, owner: (['original-command'], {'unchanged': owner})
    monkeypatch.setattr(diagnostic_server, 'command_env', original_env)
    captured = []

    def fake_serve(root, model):
        for uuid in ['gpu-a', 'gpu-b']:
            command, env = diagnostic_server.command_env({'devices': [{'uuid': uuid}]}, 'owner')
            assert command == ['original-command'] and env['unchanged'] == 'owner'
            for key, folder in [('VLLM_CACHE_ROOT', 'vllm'),
                                ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
                                ('TRITON_CACHE_DIR', 'triton'), ('CUDA_CACHE_PATH', 'cuda')]:
                assert Path(env[key]) == root.resolve() / 'compile-cache' / uuid / folder
                assert Path(env[key]).is_dir()
            captured.append(env)
        if fail:
            raise RuntimeError('mock startup failure')

    real_spec = successor.importlib.util.spec_from_file_location

    def instrumented_spec(*args):
        spec = real_spec(*args)
        execute = spec.loader.exec_module

        def execute_with_fake_serve(module):
            execute(module)
            module.serve = fake_serve

        spec.loader = SimpleNamespace(create_module=lambda spec: None,
                                      exec_module=execute_with_fake_serve)
        return spec

    monkeypatch.setattr(successor.importlib.util, 'spec_from_file_location', instrumented_spec)
    module = load_transition()
    if fail:
        with pytest.raises(RuntimeError, match='mock startup failure'):
            module.serve(tmp_path, tmp_path / 'model')
    else:
        module.serve(tmp_path, tmp_path / 'model')
    assert diagnostic_server.command_env is original_env
    assert captured[0]['VLLM_CACHE_ROOT'] != captured[1]['VLLM_CACHE_ROOT']
