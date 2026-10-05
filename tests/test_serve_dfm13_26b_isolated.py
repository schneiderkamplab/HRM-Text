from pathlib import Path
import sys

import pytest

from scripts import serve_dfm13_26b_isolated as m


@pytest.mark.parametrize('fail', [False, True])
def test_cache_paths_and_restore(tmp_path, monkeypatch, fail):
    root = tmp_path / 'new'
    original = lambda memory, owner: (['original'], {'owner': owner})
    monkeypatch.setattr(m.diagnostic_server, 'command_env', original)
    monkeypatch.setattr(sys, 'argv', ['serve', '--root', str(root)])

    def replicas(actual):
        assert actual == root
        for gpu in ['GPU-a', 'GPU-b']:
            cmd, env = m.diagnostic_server.command_env({'devices': [{'uuid': gpu}]}, 'owned')
            assert cmd == ['original'] and env['owner'] == 'owned'
            for key, folder in [('VLLM_CACHE_ROOT', 'vllm'),
                                ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
                                ('TRITON_CACHE_DIR', 'triton'), ('CUDA_CACHE_PATH', 'cuda')]:
                assert Path(env[key]) == root / 'compile-cache' / gpu / folder
                assert Path(env[key]).is_dir()
        if fail:
            raise RuntimeError('mock failure')

    monkeypatch.setattr(m, 'replica_entry', replicas)
    if fail:
        with pytest.raises(RuntimeError, match='mock failure'):
            m.main()
    else:
        m.main()
    assert m.diagnostic_server.command_env is original
