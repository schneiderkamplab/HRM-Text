#!/usr/bin/env python3
"""Prepare, archive and audit an Apple store build; never uploads automatically."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

from audit_feedback_bundle import audit
from apple_engine import FLUTTER_REVISION, audit_app, engine_binary

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'native/app'
MODEL_HASH = '38ecdf6303394b256037287f2caf9b334e6a20814fd07d11bdc24555dc5d01e6'


def run(*args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform', choices=['ios', 'macos'])
    parser.add_argument('--flutter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bundle-id', default='dk.sdu.dfm.mimir')
    parser.add_argument('--version', default='0.1.5')
    parser.add_argument('--build', default='11')
    parser.add_argument('--team-id', help='Verified 10-character Apple Developer Team ID; omit for unsigned preparation')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', args.bundle_id):
        parser.error('Invalid bundle ID')
    if args.team_id and not re.fullmatch(r'[A-Z0-9]{10}', args.team_id):
        parser.error('Use the signing Team ID, not the App Store Connect provider UUID')
    if not re.fullmatch(r'\d+\.\d+\.\d+', args.version) or not args.build.isdigit():
        parser.error('Expected x.y.z version and numeric build')
    flutter = args.flutter.resolve(strict=True)
    engine = engine_binary(args.platform)
    sdk_revision = subprocess.check_output(
        ['git', '-C', str(flutter.parent.parent), 'rev-parse', 'HEAD'], text=True).strip()
    if sdk_revision != FLUTTER_REVISION:
        raise ValueError('Flutter SDK must match the pinned custom engine revision')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'DFM Mimir.xcarchive'
    configure = [flutter, 'build', 'ios' if args.platform == 'ios' else 'macos',
                 '--release', '--config-only', '--target', 'lib/main.dart', '--build-name', args.version,
                 '--build-number', args.build]
    if args.platform == 'ios':
        configure.append('--no-codesign')
    run(*configure, cwd=APP)
    command = ['xcodebuild', '-workspace', APP / args.platform / 'Runner.xcworkspace',
               '-scheme', 'Runner', '-configuration', 'Release',
               '-destination', 'generic/platform=iOS' if args.platform == 'ios' else 'generic/platform=macOS',
               '-archivePath', archive, '-derivedDataPath', output / 'DerivedData',
               f'MIMIR_BUNDLE_ID={args.bundle_id}', 'CODE_SIGN_STYLE=Automatic',
               'DEBUG_INFORMATION_FORMAT=dwarf-with-dsym']
    if args.team_id:
        # macOS otherwise defaults to "Sign to Run Locally" even with a team.
        # Export re-signs the development archive for App Store distribution.
        command += [f'MIMIR_TEAM_ID={args.team_id}',
                    'CODE_SIGN_IDENTITY=Apple Development', '-allowProvisioningUpdates']
    else:
        command += ['CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'MIMIR_TEAM_ID=']
    run(*command, 'archive', cwd=APP)
    products = list((archive / 'Products/Applications').glob('*.app'))
    if len(products) != 1:
        raise ValueError('Expected exactly one archived application')
    product = products[0]
    contents = product if args.platform == 'ios' else product / 'Contents'
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    expected = {'CFBundleIdentifier': args.bundle_id, 'CFBundleShortVersionString': args.version,
                'CFBundleVersion': args.build}
    for key, value in expected.items():
        if info.get(key) != value:
            raise ValueError(f'Archive {key} mismatch: {info.get(key)!r} != {value!r}')
    weights = list(product.rglob('model.gguf'))
    if len(weights) != 1:
        raise ValueError('Expected one bundled model')
    with weights[0].open('rb') as stream:
        model_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    if model_hash != MODEL_HASH:
        raise ValueError('Unexpected model checksum')
    framework = contents / 'Frameworks/MimirRuntime.framework'
    native = framework / 'MimirRuntime'
    executable = contents / ('MacOS' if args.platform == 'macos' else '') / info['CFBundleExecutable']
    architectures = subprocess.check_output(['xcrun', 'lipo', '-archs', str(executable)], text=True).split()
    if architectures != ['arm64']:
        raise ValueError(f'Unqualified app architectures: {architectures}')
    if args.platform == 'macos' and not info.get('LSApplicationCategoryType'):
        raise ValueError('Missing Mac App Store category')
    symbol_source = ROOT / 'logs/mimir-app-native' / args.platform / (
        'Release-iphoneos' if args.platform == 'ios' else 'Release') / 'MimirRuntime.framework.dSYM'
    if not symbol_source.is_dir():
        raise ValueError('Missing native symbols: rebuild native runtime with dSYMs')
    run('ditto', symbol_source, archive / 'dSYMs/MimirRuntime.framework.dSYM')
    engine_name = 'FlutterMacOS' if args.platform == 'macos' else 'Flutter'
    engine_symbols = archive / f'dSYMs/{engine_name}.framework.dSYM'
    # Flutter's stock symbols no longer describe the replacement engine.
    if engine_symbols.exists():
        shutil.rmtree(engine_symbols)
    run('xcrun', 'dsymutil', engine, '-o', engine_symbols)
    def uuids(path):
        result = subprocess.check_output(['xcrun', 'dwarfdump', '--uuid', str(path)], text=True)
        return set(re.findall(r'UUID: ([A-F0-9-]+) \(([^)]+)\)', result))
    if not uuids(native) or uuids(native) != uuids(archive / 'dSYMs/MimirRuntime.framework.dSYM'):
        raise ValueError('MimirRuntime symbols do not match archived binary')
    if uuids(contents / f'Frameworks/{engine_name}.framework/{engine_name}') != uuids(engine_symbols):
        raise ValueError('Custom engine symbols do not match archive')
    for path in (contents / 'Frameworks').glob('*.framework'):
        metadata = next(iter(path.glob('**/Info.plist')), None)
        if metadata is None:
            raise ValueError(f'Missing framework metadata: {path.name}')
        values = plistlib.loads(metadata.read_bytes())
        if not values.get('CFBundleShortVersionString') or not values.get('CFBundleVersion'):
            raise ValueError(f'Missing framework versions: {path.name}')
    if not list(product.rglob('PrivacyInfo.xcprivacy')):
        raise ValueError('No privacy manifests in archive')
    audit(product)
    crypto_audit = audit_app(product, args.platform)
    if args.team_id:
        run('codesign', '--verify', '--deep', '--strict', product)
        entitlements = plistlib.loads(subprocess.check_output(
            ['codesign', '-d', '--entitlements', ':-', str(product)], stderr=subprocess.DEVNULL))
        signature = subprocess.run(['codesign', '-dvv', str(product)],
                                   check=True, capture_output=True, text=True).stderr
        signed_team = re.search(r'^TeamIdentifier=(.+)$', signature, re.MULTILINE)
        # A sandboxed Mac development archive can omit the team entitlement.
        # Its verified signing certificate still must belong to the requested team.
        if signed_team is None or signed_team.group(1) != args.team_id:
            raise ValueError('Signed application team does not match requested team')
        entitlement_team = entitlements.get('com.apple.developer.team-identifier')
        if (args.platform == 'ios' or entitlement_team is not None) and entitlement_team != args.team_id:
            raise ValueError('Application team entitlement does not match requested team')
        if args.platform == 'macos' and not entitlements.get('com.apple.security.app-sandbox'):
            raise ValueError('Mac App Store build must be sandboxed')
        options = {'method': 'app-store-connect', 'destination': 'export',
                   'teamID': args.team_id, 'signingStyle': 'automatic',
                   'manageAppVersionAndBuildNumber': False, 'uploadSymbols': True}
        (output / 'ExportOptions.plist').write_bytes(plistlib.dumps(options))
    report = {**expected, 'platform': args.platform, 'modelSHA256': model_hash,
              'teamID': args.team_id, 'signed': bool(args.team_id), 'uploaded': False,
              'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'workingTreeDirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
              'archive': str(archive), 'architectures': architectures,
              'nativeUUIDs': sorted(uuids(native)),
              'osTLSEngine': True, 'boringSSLFreeMachO': crypto_audit}
    (output / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
