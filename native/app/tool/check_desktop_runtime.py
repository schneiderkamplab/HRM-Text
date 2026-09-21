#!/usr/bin/env python3
"""Probe a packaged desktop C ABI from an unrelated working directory, without Flutter."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time


def probe(bundle, missing_cpu):
    windows = sys.platform == 'win32'
    directory = bundle if windows else bundle / 'lib'
    # Windows loads backend dependencies beside the executable in real app use;
    # Python is elsewhere, so scope dependency lookup to the package for this probe.
    cookie = os.add_dll_directory(str(directory)) if windows else None
    try:
        lib = ctypes.CDLL(str(directory / ('MimirRuntime.dll' if windows else 'libMimirRuntime.so')))
        lib.mimir_create.restype = ctypes.c_void_p
        lib.mimir_submit.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.mimir_poll.argtypes = [ctypes.c_void_p]
        lib.mimir_poll.restype = ctypes.c_void_p
        lib.mimir_free.argtypes = [ctypes.c_void_p]
        lib.mimir_destroy.argtypes = [ctypes.c_void_p]
        engine = lib.mimir_create()
        assert engine, 'Could not create engine'
        try:
            assert lib.mimir_submit(engine, b'{"op":"devices"}') == 1
            events = []
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                pointer = lib.mimir_poll(engine)
                if not pointer:
                    time.sleep(.01)
                    continue
                event = json.loads(ctypes.string_at(pointer))
                lib.mimir_free(pointer)
                if event['type'] == 'done':
                    break
                events.append(event)
            else:
                raise TimeoutError('Packaged backend enumeration')
            if missing_cpu:
                assert any(e['type'] == 'error' and 'CPU backend' in e['message'] for e in events), events
            else:
                assert not any(e['type'] == 'error' for e in events), events
                assert any(d['id'] == 'cpu' for e in events if e['type'] == 'devices' for d in e['devices']), events
            print(json.dumps(events))
        finally:
            lib.mimir_destroy(engine)
    finally:
        if cookie:
            cookie.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--missing-cpu', action='store_true')
    args = parser.parse_args()
    bundle = args.bundle.resolve(strict=True)
    if args.child:
        probe(bundle, args.missing_cpu)
        return
    with tempfile.TemporaryDirectory(prefix='mimir-probe-') as temporary:
        env = dict(os.environ)
        # Do not let developer overrides satisfy an incomplete package.
        for key in ('GGML_BACKEND_PATH', 'LD_LIBRARY_PATH'):
            env.pop(key, None)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(bundle), '--child'],
                       cwd=temporary, env=env, check=True, timeout=90)
    # Every probe has a fresh process/registry. Do not damage the packaged files.
    with tempfile.TemporaryDirectory(prefix='mimir-no-cpu-') as temporary:
        copy = Path(temporary) / 'bundle'
        directory = bundle if sys.platform == 'win32' else bundle / 'lib'
        native = copy if sys.platform == 'win32' else copy / 'lib'
        native.mkdir(parents=True)
        for path in directory.iterdir():
            if path.is_file() and ('.so' in path.name or path.suffix.lower() == '.dll') and 'ggml-cpu' not in path.name:
                shutil.copy2(path, native / path.name)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(copy), '--child', '--missing-cpu'],
                       cwd=temporary, env=env, check=True, timeout=90)
    print('Packaged CPU startup and missing-CPU diagnostics passed.')


if __name__ == '__main__':
    main()
