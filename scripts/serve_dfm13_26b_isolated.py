"""Existing owned compiled26B replicas with per-run/per-GPU compilation caches."""
import argparse
from pathlib import Path

from dfm12 import diagnostic_server
from scripts.dfm13_repo_bulk_interlude import replica_entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve()
    if root.exists():
        raise ValueError('Fresh server root required')
    original = diagnostic_server.command_env

    def command_env(memory, owner):
        command, env = original(memory, owner)
        cache = root / 'compile-cache' / memory['devices'][0]['uuid']
        for key, folder in [('VLLM_CACHE_ROOT', 'vllm'),
                            ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
                            ('TRITON_CACHE_DIR', 'triton'), ('CUDA_CACHE_PATH', 'cuda')]:
            path = cache / folder
            path.mkdir(parents=True, exist_ok=True)
            env[key] = str(path)
        return command, env

    diagnostic_server.command_env = command_env
    try:
        replica_entry(root)
    finally:
        diagnostic_server.command_env = original


if __name__ == '__main__':
    main()
