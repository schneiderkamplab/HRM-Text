#!/usr/bin/env python3
"""Build or verify the four-patch candidate without changing a checkout or index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

__all__ = []

_ROOT = Path(__file__).resolve().parents[3]
_REPO = _ROOT / 'llama.cpp'
_OUT = _ROOT / 'native/mimir/patches/release-candidate'
_BASE = 'c9a5eeeb34ab8f794ea7510ca52d25da13728a5b'
_GGML = 'c3e60e59dd065fae4679e1d670adffbc3efa96ec'
_CODEC = '0b29d4555816e0f60b25c48be4be58257d79b379'
_MAIN = 'b417698f58084c38912072b03493d1196b390e6a'
_PERSISTENCE = '6f60f7472fead8da5289e06c9d79b47dd4763043'
_HEAD = '8f4f4ef8f3139d7d262763936f1f34e48ad46d9c'


def _git(*args, env=None, data=None):
    return subprocess.check_output(['git', '-C', str(_REPO), *args], env=env, input=data)


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='write candidates; default verifies existing files')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mimir-patches-') as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
        _git('read-tree', _MAIN, env=env)
        fix = _git('diff', '--binary', _PERSISTENCE, _HEAD)
        _git('apply', '--cached', '--whitespace=error', '-', env=env, data=fix)
        main_tree = _git('write-tree', env=env).decode().strip()
        patches = {}
        for name, before, after in [
            ('01-ggml.patch', _BASE, _GGML),
            ('02-text-codec.patch', _GGML, _CODEC),
            ('03-prefixlm.patch', _CODEC, main_tree),
            ('04-generation-persistence.patch', main_tree, _HEAD),
        ]:
            patches[name] = _git('diff', '--binary', before, after)
        patches['generation-persistence-standalone.patch'] = (
            _ROOT / 'native/mimir/patches/review-drafts/generation-persistence-standalone.patch'
        ).read_bytes()
        _git('read-tree', _BASE, env=env)
        trees = {}
        for name, patch in patches.items():
            if name == 'generation-persistence-standalone.patch':
                _git('read-tree', _CODEC, env=env)
            _git('apply', '--cached', '--check', '--whitespace=error', '-', env=env, data=patch)
            _git('apply', '--cached', '--whitespace=error', '-', env=env, data=patch)
            trees[name] = _git('write-tree', env=env).decode().strip()
        expected = _git('rev-parse', _HEAD + '^{tree}').decode().strip()
        assert trees['04-generation-persistence.patch'] == expected
        assert trees['03-prefixlm.patch'] == main_tree
        header = _git('show', main_tree + ':include/llama.h')
        assert b'llama_decode_prefix' in header and b'llama_sampler_state_get_size' not in header
        generic_header = _git('show', trees['generation-persistence-standalone.patch'] + ':include/llama.h')
        assert b'llama_decode_prefix' not in generic_header and b'llama_sampler_state_get_size' in generic_header
        manifest = {
            'status': 'release-candidate; final Linux sanitizer runner validation pending',
            'base': _BASE, 'qualified_head': _HEAD, 'combined_tree': expected,
            'main_tree': main_tree, 'standalone_tree': trees['generation-persistence-standalone.patch'],
            'patch_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in patches.items()},
            'trees_after_application': trees,
        }
        patches['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
        for name, data in patches.items():
            path = _OUT / name
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            elif path.read_bytes() != data:
                raise SystemExit(f'Package differs from qualified Git trees: {path}')
        print('Verified four-patch reconstruction, main-only boundary and standalone persistence')


if __name__ == '__main__':
    _main()
