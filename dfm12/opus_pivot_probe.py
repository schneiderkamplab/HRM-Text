"""Inspect exact English anchors for FO/NL; not an approved training export."""
import io
import json
from itertools import zip_longest
from pathlib import Path
import urllib.request
import zipfile

from .io import atomic, digest, load, write_json


def aligned(archive, a, b):
    with zipfile.ZipFile(archive) as z:
        if 'creativecommons.org/licenses/by/2.0/fr/' not in z.read('README').decode():
            raise ValueError('Unexpected Tatoeba license')
        names = z.namelist()
        aa = [n for n in names if n.endswith('.' + a)]
        bb = [n for n in names if n.endswith('.' + b)]
        if len(aa) != 1 or len(bb) != 1:
            raise ValueError('Ambiguous archive members')
        with z.open(aa[0]) as fa, z.open(bb[0]) as fb:
            for i, (x, y) in enumerate(zip_longest(io.TextIOWrapper(fa), io.TextIOWrapper(fb))):
                if x is None or y is None:
                    raise ValueError('Misaligned archive')
                yield i, x.strip(), y.strip()


def main():
    root = Path('data/dfm12/opus')
    url = 'https://opus.nlpl.eu/opusapi/?source=en&target=fo&preprocessing=moses&version=latest'
    with urllib.request.urlopen(url, timeout=30) as response:
        entries = json.load(response)['corpora']
    entry = next(e for e in entries if e['corpus'] == 'Tatoeba')
    nl = next(e for e in load(root / 'inventory.json')['pairs']['en-nl']['corpora']
              if e['corpus'] == 'Tatoeba')
    if nl['version'] != entry['version']:
        raise ValueError('Different release snapshots')
    anchors = {}
    for e in [entry, nl]:
        archive = root / 'downloads' / (digest(e['url']) + '.zip')
        if not archive.exists():
            with urllib.request.urlopen(e['url'], timeout=60) as response:
                data = response.read()
            temporary = archive.with_suffix('.probe-part')
            temporary.write_bytes(data)
            temporary.replace(archive)
        for line, english, target in aligned(archive, 'en', e['target']):
            if e['target'] == 'fo':
                anchors.setdefault(english, {'fo': set(), 'nl': set()})['fo'].add(target)
            elif english in anchors:
                anchors[english]['nl'].add(target)
    matches = [{ 'en': en, 'fo': sorted(v['fo']), 'nl': sorted(v['nl'])}
               for en, v in anchors.items() if v['nl']]
    report = {'status': 'probe_only_not_training_data', 'sources': [entry, nl],
              'english_anchors': len(anchors), 'matched_anchors': len(matches),
              'unambiguous_anchors': sum(len(x['fo']) == len(x['nl']) == 1 for x in matches),
              'matches': matches, 'blocking': False,
              'caveat': 'Exact English string equality does not prove shared sentence IDs or equivalent sense. Audit required.'}
    write_json(root / 'fo-nl-pivot-probe.json', report)
    print({k: v for k, v in report.items() if k not in {'sources', 'matches'}})


if __name__ == '__main__':
    main()
