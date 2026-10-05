"""Exit-safe transition CLI; preserve pinned original module and its gates."""
import importlib.util
from pathlib import Path

import psutil


def load_transition():
    path = Path(__file__).with_name('wave4_gemma31_transition.py')
    spec = importlib.util.spec_from_file_location('dfm12._transition_exited_private', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_alive = module.alive

    def alive(item):
        try:
            return original_alive(item)
        except psutil.NoSuchProcess:
            return False

    module.alive = alive
    original_serve = module.serve

    def serve(root, model_path):
        from . import diagnostic_server
        original_command = diagnostic_server.command_env

        def command_env(memory, owner):
            command, env = original_command(memory, owner)
            cache = Path(root).resolve() / 'compile-cache' / memory['devices'][0]['uuid']
            for variable, directory in (
                ('VLLM_CACHE_ROOT', 'vllm'),
                ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
                ('TRITON_CACHE_DIR', 'triton'),
                ('CUDA_CACHE_PATH', 'cuda'),
            ):
                path = cache / directory
                path.mkdir(parents=True, exist_ok=True)
                env[variable] = str(path)
            return command, env

        diagnostic_server.command_env = command_env
        try:
            return original_serve(root, model_path)
        finally:
            diagnostic_server.command_env = original_command

    module.serve = serve
    return module


def main():
    load_transition().main()


if __name__ == '__main__':
    main()
