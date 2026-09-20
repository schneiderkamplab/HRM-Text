#!/usr/bin/env python3
"""Create and verify a bundled-model Flutter macOS development DMG."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import shutil
import tempfile

from package_archive import compile_server, digest, package_name

ROOT = Path(__file__).resolve().parents[3]


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=ROOT / 'native/flutter/build/macos/Build/Products/Release/DFM Mimir.app')
    parser.add_argument('--model-sha256', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/packages/with-model/macos')
    parser.add_argument('--dart', default='dart', help='Dart SDK executable from Flutter')
    args = parser.parse_args()
    app, output = args.app.resolve(strict=True), args.output.resolve()
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    arch = subprocess.check_output(['lipo', '-archs', str(app / 'Contents/MacOS' / info['CFBundleExecutable'])], text=True).strip()
    if arch != 'arm64':
        raise ValueError(f'Expected Apple Silicon app, got {arch}')
    model = Path('Contents/Frameworks/App.framework/Resources/flutter_assets/assets/model.gguf')
    if digest(app / model) != args.model_sha256:
        raise ValueError('Bundled model checksum mismatch')
    run('codesign', '--verify', '--deep', '--strict', app)
    output.mkdir(parents=True, exist_ok=True)
    name = package_name(info['CFBundleShortVersionString'], 'macos', arch) + '.dmg'
    destination = output / name
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(prefix='dmg-', dir=output) as temporary:
        work = Path(temporary)
        stage, mount = work / 'stage', work / 'mount'
        stage.mkdir(); mount.mkdir()
        run('ditto', app, stage / app.name)
        dart = shutil.which(args.dart)
        if not dart:
            raise ValueError('Dart compiler not found; pass --dart from your Flutter SDK')
        server = stage / app.name / 'Contents/MacOS/dfm-mimir-server'
        compile_server(dart, server)
        run(server, '--help')
        run('codesign', '--force', '--sign', '-', server)
        run('codesign', '--force', '--sign', '-', '--entitlements',
            ROOT / 'native/flutter/macos/Runner/Release.entitlements', stage / app.name)
        (stage / 'Applications').symlink_to('/Applications')
        (stage / 'Read Me.txt').write_text(
            f"DFM Mimir — development preview\n\nApple Silicon; macOS {info['LSMinimumSystemVersion']} or later.\n"
            f"Drag {app.name} to Applications, then open it there and eject this disk image.\n"
            'Mimir Q4_K_M weights are included. Chat works offline with Metal or CPU.\n'
            'This preview is not Developer ID signed or notarized. If Gatekeeper blocks it,\n'
            'use the per-app Open Anyway option in System Settings > Privacy & Security\n'
            'only if you trust this download. Do not disable Gatekeeper globally.\n'
            'Model and dependency licenses are included in the app assets/licenses folder.\n', encoding='utf-8')
        manifest = {
            'platform': 'macos', 'architecture': arch, 'modelSHA256': args.model_sha256,
            'minimumOS': info['LSMinimumSystemVersion'], 'appVersion': info['CFBundleShortVersionString'],
            'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'llamaCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT / 'llama.cpp', text=True).strip(),
            'notarized': False,
        }
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        image = work / name
        run('hdiutil', 'create', '-volname', 'DFM Mimir', '-srcfolder', stage, '-format', 'UDZO', '-fs', 'HFS+', image)
        run('hdiutil', 'verify', image)
        run('hdiutil', 'attach', image, '-readonly', '-nobrowse', '-mountpoint', mount)
        try:
            run('codesign', '--verify', '--deep', '--strict', mount / app.name)
            if digest(mount / app.name / model) != args.model_sha256:
                raise ValueError('Packaged model checksum mismatch')
            if (mount / 'Applications').readlink() != Path('/Applications'):
                raise ValueError('Applications shortcut missing')
        finally:
            run('hdiutil', 'detach', mount)
        image.replace(destination)
    destination.with_name(name + '.sha256').write_text(digest(destination) + '  ' + name + '\n', encoding='utf-8')
    print(destination)


if __name__ == '__main__':
    main()
