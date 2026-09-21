#!/usr/bin/env python3
"""Check a built app/package directory for accidentally bundled feedback administration data."""
import argparse
import mmap
import re
import zipfile
from pathlib import Path

FORBIDDEN_NAMES = {'.wrangler', 'wrangler.jsonc', 'wrangler.toml', 'worker-configuration.d.ts',
                   'admin.mjs', 'database.mjs', '.dev.vars', '.env'}
# Public infrastructure identifiers aren't credentials, but the client doesn't need them.
FORBIDDEN_BYTES = [b'fe4f6f32-9602-4215-80a6-848b0027f28b',
                   b'7e1501c9ee3068b861f8246ae67d8b17',
                   b'CLOUDFLARE_API_TOKEN=', b'oauth_token =']

PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]{64,}-----END (?:RSA |EC )?PRIVATE KEY-----')

def contains_sensitive(contents):
    return any(contents.find(marker) >= 0 for marker in FORBIDDEN_BYTES) or PRIVATE_KEY.search(contents) is not None

def audit(root: Path):
    errors = []
    count = 0
    if root.is_file() and zipfile.is_zipfile(root):
        with zipfile.ZipFile(root) as archive:
            for entry in archive.infolist():
                if any(part in FORBIDDEN_NAMES for part in Path(entry.filename).parts):
                    errors.append(f'Unexpected administration file: {entry.filename}')
                if entry.is_dir() or entry.filename.endswith('.gguf'):
                    continue
                if contains_sensitive(archive.read(entry)):
                    errors.append(f'Unexpected administration identifier or credential marker: {entry.filename}')
                count += 1
        if errors:
            raise SystemExit('\n'.join(errors))
        print(f'Feedback bundle audit passed: {count} archive files scanned; model weights excluded.')
        return
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if any(part in FORBIDDEN_NAMES for part in relative.parts):
            errors.append(f'Unexpected administration file: {relative}')
        if not path.is_file() or path.suffix == '.gguf' or path.stat().st_size == 0:
            continue
        with path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as contents:
            if contains_sensitive(contents):
                errors.append(f'Unexpected administration identifier or credential marker: {relative}')
        count += 1
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Feedback bundle audit passed: {count} files scanned; model weights excluded.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    if not args.directory.is_dir() and not zipfile.is_zipfile(args.directory):
        parser.error('Expected a built app directory, ZIP or APK')
    audit(args.directory)
