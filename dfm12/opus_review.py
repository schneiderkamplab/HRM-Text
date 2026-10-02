"""Collect version-specific OPUS evidence, without granting approvals."""
from pathlib import Path
import argparse
from datetime import date, datetime
import urllib.request
import urllib.error
import json
import yaml

from .io import load, lock, write_json


def json_metadata(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_metadata(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_metadata(v) for v in value]
    return value


def collect(root, revision=None):
    inventory = load(root / 'inventory.json')
    if revision is None:
        request = urllib.request.Request('https://api.github.com/repos/Helsinki-NLP/OPUS/commits/main',
                                         headers={'User-Agent': 'DFM12-source-review'})
        revision = json.load(urllib.request.urlopen(request, timeout=30))['sha']
    entries = {(e['corpus'], e['version']) for item in inventory['pairs'].values() for e in item['corpora']}
    results = []
    for corpus, version in sorted(entries):
        path = root / 'review_evidence' / corpus / version / 'info.json'
        if path.exists():
            evidence = load(path)
        else:
            url = f'https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{revision}/corpus/{corpus}/{version}/info.yaml'
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    raw = response.read().decode()
                evidence = {'url': url, 'raw': raw, 'metadata': json_metadata(yaml.safe_load(raw)), 'revision': revision}
            except Exception as exc:
                evidence = {'url': url, 'error': str(exc), 'revision': revision}
            write_json(path, evidence)
        metadata = evidence.get('metadata') or {}
        result = {'corpus': corpus, 'version': version, 'license': metadata.get('license'),
                  'copyright': metadata.get('copyright'), 'evidence': str(path),
                  'error': evidence.get('error')}
        results.append(result)
        print(corpus, version, result['license'], result['error'] or '', flush=True)
        write_json(root / 'license-review.json', results)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm12/opus'))
    parser.add_argument('--revision', help='Pinned OPUS Git commit; avoids an unauthenticated GitHub API lookup')
    args = parser.parse_args()
    with lock(args.root / '.license-evidence.lock'):
        collect(args.root, args.revision)


if __name__ == '__main__':
    main()
