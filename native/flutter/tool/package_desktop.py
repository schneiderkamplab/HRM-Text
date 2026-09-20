#!/usr/bin/env python3
"""Build a relocatable Linux/Windows Flutter bundle on its native host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'native/flutter'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(*args, env=None):
    subprocess.run([str(a) for a in args], cwd=APP, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    model = parser.add_mutually_exclusive_group(required=True)
    model.add_argument('--model', type=Path)
    model.add_argument('--without-model', action='store_true', help='Build an import-only package')
    parser.add_argument('--flutter', default='flutter')
    parser.add_argument('--backends', default='cpu', help='cpu, cuda, vulkan or comma-separated combination')
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/packages')
    args = parser.parse_args()
    target = {'Linux': 'linux', 'Windows': 'windows'}.get(platform.system())
    if not target:
        parser.error('Run this tool on Linux or Windows; Flutter desktop builds are native-host builds.')
    backends = set(args.backends.lower().split(','))
    if not backends <= {'cpu', 'cuda', 'vulkan'}:
        parser.error('Supported build backends: cpu,cuda,vulkan')
    backends.add('cpu')
    model_path = args.model.resolve(strict=True) if args.model else None
    flutter = shutil.which(args.flutter)
    if not flutter:
        parser.error('Flutter executable not found')
    env = dict(os.environ, MIMIR_BACKENDS=';'.join(sorted(b.upper() for b in backends if b != 'cpu')))
    asset = APP / 'assets/model.gguf'
    # Restore any existing local model link/file, even after a failed build.
    with tempfile.TemporaryDirectory(prefix='mimir-package-', dir=APP / 'assets') as temporary:
        backup = Path(temporary) / 'previous-model.gguf'
        had_asset = asset.exists() or asset.is_symlink()
        if had_asset:
            asset.rename(backup)
        try:
            if model_path:
                # Copy rather than symlink: Windows developer mode is not required.
                shutil.copyfile(model_path, asset)
            else:
                asset.touch()
            run(flutter, 'pub', 'get', env=env)
            run(flutter, 'build', target, '--release', env=env)
        finally:
            asset.unlink(missing_ok=True)
            if had_asset:
                backup.rename(asset)
    arch = 'arm64' if platform.machine().lower() in ('aarch64', 'arm64') else 'x64'
    bundle = APP / 'build' / target / arch / ('release/bundle' if target == 'linux' else 'runner/Release')
    if not bundle.is_dir():
        raise RuntimeError(f'Missing Flutter bundle: {bundle}')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    name = f'dfm-mimir-{target}-{arch}'
    with tempfile.TemporaryDirectory(prefix='package-', dir=output) as temporary:
        stage = Path(temporary) / name
        shutil.copytree(bundle, stage)
        subprocess.run([sys.executable, str(APP / 'tool/check_desktop_runtime.py'), str(stage)], check=True)
        shutil.copy2(APP / 'PACKAGING-PLAN.md', stage / 'PACKAGING-PLAN.md')
        shutil.copytree(APP / 'assets/licenses', stage / 'licenses', dirs_exist_ok=True)
        (stage / 'README.txt').write_text(
            'DFM Mimir\nRun mimir_flutter' + ('.exe' if target == 'windows' else '') +
            '.\nKeep the complete folder together. No SDK/compiler is required.\n'
            'A compatible OS and system GPU driver are still required for acceleration.\n'
            'Use Model and settings to import a PrefixLM Mimir GGUF or select CPU.\n'
            'This is an unsigned development package; hardware qualification is recorded separately.\n', encoding='utf-8')
        manifest = {
            'schemaVersion': 1, 'platform': target, 'architecture': arch,
            'backendsBuilt': sorted(backends), 'hardwareQualified': False,
            'sourceDirty': bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip()),
            'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'llamaCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT / 'llama.cpp', text=True).strip(),
            'modelSHA256': digest(model_path) if model_path else None,
            'files': {p.relative_to(stage).as_posix(): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()},
        }
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        # A complete archive replaces its previous version only after creation succeeds.
        archive = Path(shutil.make_archive(str(Path(temporary) / name), 'gztar' if target == 'linux' else 'zip', temporary, name))
        destination = output / archive.name
        os.replace(archive, destination)
        (output / (destination.name + '.sha256')).write_text(digest(destination) + '  ' + destination.name + '\n', encoding='utf-8')
        print(destination)


if __name__ == '__main__':
    main()
