#!/usr/bin/env python3
"""Test symbol stripping on a copy of an ARM64 Apple engine, never the original."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile


def _inspect(path):
    data = path.read_bytes()
    if struct.unpack_from('<I', data)[0] != 0xFEEDFACF:
        raise ValueError('Expected a thin little-endian 64-bit Mach-O binary')
    offset = 32
    sections = {}
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, offset)
        if command == 0x19:  # LC_SEGMENT_64
            count = struct.unpack_from('<I', data, offset + 64)[0]
            for index in range(count):
                start = offset + 72 + 80 * index
                section = data[start:start + 16].split(b'\0')[0].decode()
                segment = data[start + 16:start + 32].split(b'\0')[0].decode()
                length, position = struct.unpack_from('<QI', data, start + 40)
                if segment == '__TEXT':
                    sections[section] = {
                        'bytes': length,
                        'sha256': hashlib.sha256(data[position:position + length]).hexdigest(),
                    }
        offset += size
    return {
        'bytes': len(data),
        'text_sections': sections,
        'boringssl_path_mentions': data.count(b'boringssl/src/'),
    }


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mimir-strip-') as folder:
        copy = Path(folder) / args.binary.name
        architectures = subprocess.check_output(
            ['xcrun', 'lipo', '-archs', str(args.binary)], text=True).split()
        if 'arm64' not in architectures:
            raise ValueError('Expected an ARM64 slice')
        if len(architectures) > 1:
            subprocess.run(['xcrun', 'lipo', str(args.binary), '-thin', 'arm64',
                            '-output', str(copy)], check=True)
        else:
            shutil.copy2(args.binary, copy)
        before = _inspect(copy)
        result = subprocess.run(['xcrun', 'strip', '-x', '-S', str(copy)],
                                capture_output=True, text=True, check=True)
        after = _inspect(copy)
    print(json.dumps({
        'binary': str(args.binary), 'slice': 'arm64', 'command': 'xcrun strip -x -S COPY',
        'before': before, 'after': after,
        'text_sections_unchanged': before['text_sections'] == after['text_sections'],
        'strip_stderr': result.stderr.strip(),
        'interpretation': 'Symbol stripping is not dead-code elimination. '
                          'The modified copy is discarded, not signed or shipped.',
    }, indent=2))


if __name__ == '__main__':
    _main()
