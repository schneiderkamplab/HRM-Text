"""Install and audit the pinned Apple engine before Xcode's final code signing.

Release builds fail closed if the separately built OS-TLS engine is missing.
Debug builds use it only with MIMIR_APPLE_OS_TLS=1. No binary surgery is used:
the engine was compiled with Dart secure sockets disabled.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
FLUTTER_REVISION = '6a19cca56475dbfba1478ee68d7bd0c2ef891da1'
DART_REVISION = 'b530c21f7de367b94fb04787bfed9d8e989d75e8'


def engine_root():
    return Path(os.environ.get('MIMIR_APPLE_ENGINE_ROOT',
                               ROOT / 'logs/toolchains/flutter-os-tls')).resolve(strict=True)


def text_sections(binary):
    """Fingerprint code/constants independently of signing and symbol stripping."""
    data = binary.read_bytes()
    if data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError(f'Expected thin 64-bit Mach-O: {binary}')
    sections, offset = {}, 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, offset)
        if command == 0x19:
            for index in range(struct.unpack_from('<I', data, offset + 64)[0]):
                start = offset + 72 + index * 80
                name = data[start:start + 16].split(b'\0')[0].decode()
                segment = data[start + 16:start + 32].split(b'\0')[0]
                length, position = struct.unpack_from('<QI', data, start + 40)
                if segment == b'__TEXT':
                    sections[name] = hashlib.sha256(data[position:position + length]).hexdigest()
        offset += size
    if '__text' not in sections:
        raise ValueError(f'No executable text: {binary}')
    return sections


def audit_binary(binary, *, debug_kernel=False):
    data = binary.read_bytes()
    # JIT kernels retain Dart library source comments mentioning BoringSSL.
    # This exception never applies to a distributed release executable.
    if b'boringssl/src/' in data or (b'BoringSSL' in data and not debug_kernel):
        raise ValueError(f'BoringSSL marker in {binary}')
    symbols = subprocess.check_output(['xcrun', 'nm', '-j', str(binary)],
                                      text=True, stderr=subprocess.DEVNULL)
    if re.search(r'^_+(?:SSL_|OPENSSL_|BORINGSSL_|EVP_|AES_|CRYPTO_|X509_|ChaCha20)',
                 symbols, re.MULTILINE):
        raise ValueError(f'Bundled crypto implementation in {binary}')


def engine_binary(platform, mode='release'):
    root = engine_root()
    dart = root / 'engine/src/flutter/third_party/dart'
    for source, revision in [(root, FLUTTER_REVISION), (dart, DART_REVISION)]:
        actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise ValueError(f'Unqualified engine source revision: {source}: {actual}')
    for patch, source in [('flutter.patch', root), ('apple-linker.patch', root), ('dart.patch', dart)]:
        subprocess.run(['git', '-C', str(source), 'apply', '--reverse', '--check',
                        str(Path(__file__).parent / 'apple_os_tls' / patch)], check=True)
    configurations = {
        ('macos', 'release'): ('host_release_arm64', 'FlutterMacOS.framework/Versions/A/FlutterMacOS', 'FlutterMacOS.framework'),
        ('ios', 'release'): ('ios_release', 'Flutter.framework/Flutter', 'flutter_framework'),
        ('simulator', 'debug'): ('ios_debug_sim_arm64', 'Flutter.framework/Flutter', 'flutter_framework'),
        ('server', 'release'): ('host_release_arm64', 'dartaotruntime_product', 'dartaotruntime_product'),
    }
    if (platform, mode) not in configurations:
        raise ValueError(f'Unqualified custom engine configuration: {platform}/{mode}')
    output, relative, target = configurations[(platform, mode)]
    output = root / 'engine/src/out' / output
    values = re.findall(r'^dart_disable_secure_socket\s*=\s*(true|false)',
                        (output / 'args.gn').read_text(), re.MULTILINE)
    if not values or values[-1] != 'true':
        raise ValueError('Engine must disable Dart secure sockets')
    graph = subprocess.check_output([str(root / 'third_party/ninja/ninja'), '-C', str(output),
                                     '-t', 'graph', target], text=True)
    if 'boringssl' in graph.lower():
        if platform != 'simulator':
            raise ValueError(f'BoringSSL dependency in {target}')
        # The JIT simulator build runs host-side Dart compiler tools. These are
        # not shipped. Only the explicitly identified macOS host toolchain may
        # have this dependency; the iOS framework must still pass binary audit.
        environment = dict(os.environ, DEPOT_TOOLS_UPDATE='0')
        environment['PATH'] = str(root.parent / 'depot_tools') + os.pathsep + environment['PATH']
        dependencies = subprocess.check_output([
            str(root / 'engine/src/flutter/third_party/gn/gn'), 'desc', str(output),
            '//flutter/shell/platform/darwin/ios:flutter_framework', 'deps', '--all',
            f'--root={root / "engine/src"}'], text=True, env=environment)
        crypto = [line for line in dependencies.splitlines() if 'boringssl' in line.lower()]
        if not crypto or any(not line.endswith('(//build/toolchain/mac:clang_arm64)') for line in crypto):
            raise ValueError('Unexpected simulator BoringSSL dependency')
    binary = (output / relative).resolve(strict=True)
    audit_binary(binary, debug_kernel=platform == 'simulator')
    return binary


def audit_app(app, platform):
    contents = app / 'Contents' if platform == 'macos' else app
    name = 'FlutterMacOS' if platform == 'macos' else 'Flutter'
    installed = contents / f'Frameworks/{name}.framework/{name}'
    reference = engine_binary(platform)
    if text_sections(installed) != text_sections(reference):
        raise ValueError('App does not contain the qualified OS-TLS engine')
    snapshot = contents / 'Frameworks/App.framework/App'
    if b'MIMIR_OS_TLS_PROBE_' in snapshot.read_bytes():
        raise ValueError('Diagnostic entry point must never be packaged')
    server = contents / 'MacOS/dfm-mimir-server'
    if platform == 'macos' and server.exists():
        if text_sections(server) != text_sections(engine_binary('server')):
            raise ValueError('Headless server does not contain the qualified OS-TLS runtime')
    audited = []
    for path in contents.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'):
            audit_binary(path)
            audited.append(str(path.relative_to(app)))
    return audited


def install():
    env = os.environ
    release = env.get('CONFIGURATION', '').lower().startswith('release')
    if not release and env.get('MIMIR_APPLE_OS_TLS') != '1':
        return
    revision = subprocess.check_output(
        ['git', '-C', env['FLUTTER_ROOT'], 'rev-parse', 'HEAD'], text=True).strip()
    if revision != FLUTTER_REVISION:
        raise ValueError('Flutter SDK and OS-TLS engine revisions must match')
    platform = {'macosx': 'macos', 'iphoneos': 'ios', 'iphonesimulator': 'simulator'}[env['PLATFORM_NAME']]
    source = engine_binary(platform, 'release' if release else 'debug')
    name = 'FlutterMacOS' if platform == 'macos' else 'Flutter'
    framework = Path(env['TARGET_BUILD_DIR']) / env['FRAMEWORKS_FOLDER_PATH'] / f'{name}.framework'
    destination = (framework / name).resolve(strict=True)
    shutil.copyfile(source, destination)
    destination.chmod(0o755)
    identity = env.get('EXPANDED_CODE_SIGN_IDENTITY')
    if env.get('CODE_SIGNING_ALLOWED') != 'NO' and identity:
        subprocess.run(['codesign', '--force', '--sign', identity, '--timestamp=none', str(framework)], check=True)
    if text_sections(destination) != text_sections(source):
        raise ValueError('Engine changed during installation')
    print(f'Installed BoringSSL-free {platform} engine before app signing')


def compile_server(dart, output):
    runtime = engine_binary('server')
    package = ROOT / 'native/app/packages/mimir_api'
    subprocess.run([str(dart), 'pub', 'get'], cwd=package, check=True)
    with tempfile.TemporaryDirectory(prefix='mimir-aot-') as directory:
        snapshot = Path(directory) / 'server.aot'
        subprocess.run([str(dart), 'compile', 'aot-snapshot', 'bin/server.dart', '-o', str(snapshot)],
                       cwd=package, check=True)
        packages = engine_root() / 'engine/src/flutter/third_party/dart/.dart_tool/package_config.json'
        subprocess.run([str(dart), f'--packages={packages}',
                        str(Path(__file__).parent / 'apple_os_tls/append_executable.dart'),
                        str(runtime), str(snapshot), str(output)], check=True)
    output.chmod(0o755)
    audit_binary(output)
    if text_sections(output) != text_sections(runtime):
        raise ValueError('Executable writer changed the qualified runtime code')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'audit'])
    parser.add_argument('--app', type=Path)
    parser.add_argument('--platform', choices=['macos', 'ios'])
    args = parser.parse_args()
    if args.command == 'install':
        install()
    else:
        print(audit_app(args.app, args.platform))
