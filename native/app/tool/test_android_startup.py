#!/usr/bin/env python3
"""Exercise CPU-only registry initialization using a built APK on an Android emulator/device."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]

def run(*args):
    subprocess.run([str(a) for a in args], check=True, timeout=60)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    args = parser.parse_args()
    compiler = next(args.ndk.glob('toolchains/llvm/prebuilt/*/bin/aarch64-linux-android28-clang++'))
    adb = [args.adb, '-s', args.serial]
    remote = '/data/local/tmp/dfm-mimir-startup-test'
    with tempfile.TemporaryDirectory(prefix='mimir-startup-') as temporary:
        directory = Path(temporary)
        with zipfile.ZipFile(args.apk) as archive:
            for name in archive.namelist():
                if name in ('lib/arm64-v8a/libMimirRuntime.so', 'lib/arm64-v8a/libc++_shared.so'):
                    (directory / Path(name).name).write_bytes(archive.read(name))
        run(compiler, '-std=c++17', '-static-libstdc++', '-I'+str(ROOT/'native/runtime'),
            ROOT/'native/runtime/tests/android_startup.cpp', '-L'+str(directory), '-lMimirRuntime',
            '-Wl,-rpath,$ORIGIN', '-o', directory/'startup-test')
        run(*adb, 'shell', 'mkdir', '-p', remote)
        try:
            for path in directory.iterdir():
                run(*adb, 'push', path, remote+'/')
            run(*adb, 'shell', 'chmod', '755', remote+'/startup-test')
            run(*adb, 'shell', f'LD_LIBRARY_PATH={remote} timeout 30 {remote}/startup-test')
        finally:
            run(*adb, 'shell', 'rm', '-rf', remote)

if __name__ == '__main__':
    main()
