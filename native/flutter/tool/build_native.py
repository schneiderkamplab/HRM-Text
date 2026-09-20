#!/usr/bin/env python3
"""Build the Apple Silicon and iOS simulator C ABI; keep generated binaries out of Git."""
import argparse
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / 'native/flutter'


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=pathlib.Path, required=True)
    args = parser.parse_args()
    model = args.model.resolve(strict=True)
    build = ROOT / 'logs/mimir-flutter-native'
    build.mkdir(parents=True, exist_ok=True)
    frameworks = []
    for platform in ('macos', 'simulator'):
        dest = build / platform
        flags = ['-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5']
        if platform == 'macos':
            flags += ['-DCMAKE_OSX_DEPLOYMENT_TARGET=14.0', '-DGGML_METAL=ON', '-DGGML_BLAS=ON']
            product = dest / 'Release/MimirRuntime.framework'
        else:
            flags += ['-DCMAKE_SYSTEM_NAME=iOS', '-DCMAKE_OSX_SYSROOT=iphonesimulator',
                      '-DCMAKE_OSX_DEPLOYMENT_TARGET=17.0', '-DGGML_METAL=OFF', '-DGGML_BLAS=OFF',
                      '-DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO']
            product = dest / 'Release-iphonesimulator/MimirRuntime.framework'
        run('cmake', '-S', ROOT / 'native/runtime', '-B', dest, '-G', 'Xcode', *flags)
        run('cmake', '--build', dest, '--config', 'Release', '--target', 'MimirRuntime', '-j', '6')
        frameworks.append(product)
    output = pathlib.Path(tempfile.mkdtemp(prefix='xcframework-', dir=build)) / 'MimirRuntime.xcframework'
    run('xcodebuild', '-create-xcframework', '-framework', frameworks[0], '-framework', frameworks[1], '-output', output)
    # CocoaPods does not traverse a Frameworks directory symlink for vendored binaries.
    for platform in ('macos', 'ios'):
        target = APP / 'packages/mimir_native' / platform / 'Frameworks/MimirRuntime.xcframework'
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = pathlib.Path(tempfile.mkdtemp(prefix=f'previous-{platform}-', dir=build))
            target.rename(backup / target.name)
        run('ditto', output, target)
    asset = APP / 'assets/model.gguf'
    if asset.is_symlink():
        if asset.resolve() == model:
            return
        asset.unlink()  # Replace only our generated resource link, never a model file.
    if asset.exists():
        raise SystemExit(f'Refusing to overwrite model file: {asset}')
    asset.symlink_to(model)


if __name__ == '__main__':
    main()
